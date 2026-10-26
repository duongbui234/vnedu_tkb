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
