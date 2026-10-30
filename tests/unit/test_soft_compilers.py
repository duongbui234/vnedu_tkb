"""Compiler expressions equal hand-calculated scores, without relying on objective."""

from typing import Any

import pytest
from ortools.sat.python import cp_model

from tkb_core.constraints.soft import compile_soft
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.errors import CoreError
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver.model_builder import build_model


@pytest.mark.parametrize(
    "code,params,expected",
    [
        ("TEACHER_AVOID_SLOTS", {"slot_ids": ["1-AM-2"]}, 1),
        ("TEACHER_MAX_PERIODS_PER_SESSION", {"limit": 3, "session_ids": ["AM"]}, 1),
        ("TEACHER_MAX_PERIODS_PER_DAY", {"limit": 3}, 1),
        (
            "TEACHER_PREFERRED_PERIOD_WINDOW",
            {"first_period": 2, "last_period": 3, "session_ids": ["AM"]},
            2,
        ),
    ],
)
def test_exact_expression_without_objective(
    quality_case: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    params: dict[str, Any],
    expected: int,
) -> None:
    monkeypatch.setattr("tkb_core.preprocessing.normalize.check_capabilities", lambda p: None)
    quality_case["constraint_config"]["soft"] = [
        {"id": "rule", "code": code, "parameters": params, "weight": 3, "priority": 2}
    ]
    p = prepare(ScheduleInput.model_validate(quality_case))
    built = build_model(p)
    compiled = compile_soft(p, built)
    for oid, domain in p.domains.items():
        target = {"r::1": "1-AM-1", "r::2": "1-AM-3", "r::3": "1-AM-4"}[oid]
        for placement, v in zip(domain, built.variables[oid], strict=True):
            built.model.add(v == int(placement.start_slot_id == target))
    solver = cp_model.CpSolver()
    assert solver.solve(built.model) == cp_model.OPTIMAL
    assert solver.value(compiled.rules[0].raw_expression) == expected
    assert solver.value(compiled.tiers[2]) == 3 * expected


def test_objective_bound_guard(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tkb_core.preprocessing.normalize.check_capabilities", lambda p: None)
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 0},
            "weight": 2**53,
            "priority": 1,
        }
    ]
    p = prepare(ScheduleInput.model_validate(quality_case))
    with pytest.raises(CoreError) as err:
        compile_soft(p, build_model(p))
    assert err.value.diagnostics[0].code == "OBJECTIVE_RANGE"


def test_exact_bound_with_many_alternatives(quality_case: dict[str, Any]) -> None:
    quality_case["time_slots"] = [
        {"id": str(i), "day": 1, "session": "AM", "period": i} for i in range(1, 2001)
    ]
    quality_case["teaching_requirements"][0].update(periods_per_cycle=1, block_durations=[1])
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_AVOID_SLOTS",
            "parameters": {"slot_ids": [str(i) for i in range(1, 2001)]},
            "weight": 2**53 - 1,
            "priority": 1,
        }
    ]
    p = prepare(ScheduleInput.model_validate(quality_case))
    built = build_model(p)
    compiled = compile_soft(p, built)
    built.model.minimize(compiled.tiers[1])
    assert not built.model.validate()


def _s03_case(quality_case: dict[str, Any]) -> ScheduleInput:
    """Three singles on two days: production adds raw [1, 1] and excess <= 1 per day."""
    quality_case["time_slots"] = [
        {"id": f"{d}-AM-{p}", "day": d, "session": "AM", "period": p}
        for d in (2, 7)
        for p in (1, 2, 3)
    ]
    quality_case["teachers"] = [
        {"id": "t", "available_slot_ids": ["2-AM-1", "2-AM-2", "7-AM-1", "7-AM-2"]}
    ]
    quality_case["teaching_requirements"][0].update(periods_per_cycle=3, block_durations=[1, 1, 1])
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "s03",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 1},
            "weight": 3,
            "priority": 1,
        }
    ]
    return ScheduleInput.model_validate(quality_case)


def _compiled_proto(problem: ScheduleInput) -> Any:
    p = prepare(problem)
    built = build_model(p)
    compile_soft(p, built)
    return built.model.proto


def test_s03_appends_only_linear_bounds(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from tkb_core.constraints.s03_bounds import S03BoundsDecision

    problem = _s03_case(quality_case)
    production = _compiled_proto(problem)
    monkeypatch.setattr(
        "tkb_core.constraints.soft.derive_s03_bounds",
        lambda *a: S03BoundsDecision(None, "TEST_BASELINE"),
    )
    baseline = _compiled_proto(problem)
    assert [str(v) for v in production.variables] == [str(v) for v in baseline.variables]
    count = len(baseline.constraints)
    old = [str(c) for c in production.constraints]
    assert old[:count] == [str(c) for c in baseline.constraints]
    assert not production.has_objective() and not baseline.has_objective()
    assert not production.has_solution_hint() and not baseline.has_solution_hint()
    added = set()
    for constraint in list(production.constraints)[count:]:
        assert constraint.has_linear()
        assert list(constraint.linear.coeffs) == [1] and len(constraint.linear.vars) == 1
        variable = production.variables[constraint.linear.vars[0]]
        low, high = list(constraint.linear.domain)
        old_low, old_high = list(variable.domain)
        assert (low, high) != (old_low, old_high)
        assert old_low <= low <= high <= old_high
        added.add((variable.name, low, high))
    assert added == {
        ("excess_s03_('t', 2, '')", 0, 1),
        ("excess_s03_('t', 7, '')", 0, 1),
        ("raw_s03", 1, 1),
    }


@pytest.mark.parametrize(
    "code,params",
    [
        ("TEACHER_AVOID_SLOTS", {"slot_ids": ["1-AM-2"]}),
        ("TEACHER_MAX_PERIODS_PER_SESSION", {"limit": 1, "session_ids": ["AM"]}),
        (
            "TEACHER_PREFERRED_PERIOD_WINDOW",
            {"first_period": 2, "last_period": 3, "session_ids": ["AM"]},
        ),
    ],
)
def test_bound_helper_is_s03_only(
    quality_case: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    params: dict[str, Any],
) -> None:
    def forbidden(*args: Any) -> None:
        raise AssertionError("bound helper is S03-only")

    monkeypatch.setattr("tkb_core.constraints.soft.derive_s03_bounds", forbidden)
    quality_case["constraint_config"]["soft"] = [
        {"id": "rule", "code": code, "parameters": params, "weight": 1, "priority": 1}
    ]
    _compiled_proto(ScheduleInput.model_validate(quality_case))
    quality_case["constraint_config"]["soft"][0].update(
        code="TEACHER_MAX_PERIODS_PER_DAY", parameters={"limit": 1}, enabled=False
    )
    _compiled_proto(ScheduleInput.model_validate(quality_case))
    legacy = {k: v for k, v in quality_case.items() if k != "constraint_config"}
    p = prepare(ScheduleInput.model_validate({**legacy, "schema_version": "1.0"}))
    assert compile_soft(p, build_model(p)).rules == ()
