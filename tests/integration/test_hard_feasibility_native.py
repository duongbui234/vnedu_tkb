"""Native checks: hard schedules extend to the soft model; public solve uses hard feasibility."""

from typing import Any

import pytest
from google.protobuf import text_format
from ortools.sat import cp_model_pb2
from ortools.sat.python import cp_model

from tkb_core.constraints.soft import compile_soft
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver import objectives
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.model_builder import build_model
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score

SCHEDULE = tuple(
    ScheduleAssignment(
        occurrence_id=f"r::{i}", slot_id=f"1-PM-{start}", class_ids=("c",), teacher_ids=("t",)
    )
    for i, start in enumerate((1, 3, 4), 1)
)


@pytest.mark.parametrize(
    "code,params",
    [
        ("TEACHER_AVOID_SLOTS", {"slot_ids": ["1-PM-3"]}),
        ("TEACHER_MAX_PERIODS_PER_SESSION", {"limit": 1, "session_ids": ["PM"]}),
        ("TEACHER_MAX_PERIODS_PER_DAY", {"limit": 1}),
        (
            "TEACHER_PREFERRED_PERIOD_WINDOW",
            {"first_period": 2, "last_period": 3, "session_ids": ["PM"]},
        ),
    ],
)
def test_hard_schedule_extends_to_soft_model(
    quality_case: dict[str, Any], code: str, params: dict[str, Any]
) -> None:
    quality_case["constraint_config"]["soft"] = [
        {"id": "rule", "code": code, "parameters": params, "weight": 3, "priority": 2}
    ]
    problem = ScheduleInput.model_validate(quality_case)
    p = prepare(problem)
    built = build_model(p)
    compiled = compile_soft(p, built)
    objectives._hint(p, built, SCHEDULE)
    out = objectives._run_stage(
        p, built, compiled, SolveOptions(time_limit_seconds=5.0), None, 5.0, fix_hint=True
    )
    assert out.status == SolveStatus.OPTIMAL and out.assignments == SCHEDULE
    score = evaluate_score(problem, SCHEDULE)
    assert score.status == "OK" and score.tiers is not None and score.tiers[1] > 0
    assert out.rule_values == {
        "rule": (score.rules[0].raw_penalty, score.rules[0].weighted_penalty)
    }
    assert out.tier_values == {2: score.tiers[1]}


def test_objective_range_still_rejected_before_any_solve(quality_case: dict[str, Any]) -> None:
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 0},
            "weight": 2**53,
            "priority": 1,
        }
    ]
    result = solve(ScheduleInput.model_validate(quality_case))
    assert result.status == "INPUT_INVALID" and not result.metadata.solver_executed
    assert result.diagnostics[0].code == "OBJECTIVE_RANGE"


def test_public_solve_runs_feasibility_on_hard_model(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 2},
            "weight": 1,
            "priority": 1,
        }
    ]
    real = objectives._run_stage
    seen: list[tuple[Any, Any, bool]] = []

    def spy(*args: Any, **kwargs: Any) -> objectives.StageOutcome:
        seen.append((args[4], kwargs.get("model"), kwargs.get("fix_hint", False)))
        return real(*args, **kwargs)

    monkeypatch.setattr(objectives, "_run_stage", spy)
    problem = ScheduleInput.model_validate(quality_case)
    result = solve(problem, SolveOptions(time_limit_seconds=5.0))
    assert result.status == "OPTIMAL" and result.valid_schedule
    assert [(pr, m is not None, f) for pr, m, f in seen] == [
        (None, True, False),
        (None, False, True),
        (1, False, False),
    ]
    assert not any(v.name.startswith(("excess_", "raw_")) for v in seen[0][1].proto.variables)
    assert evaluate_score(problem, result.assignments) == result.quality.score


@pytest.mark.parametrize("gap,expected", [(1, "OPTIMAL"), (2, "INFEASIBLE")])
def test_no_lp_preserves_hard_model_and_native_truth(
    dist_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch, gap: int, expected: str
) -> None:
    dist_case["manage_rooms"] = True
    dist_case["rooms"] = [{"id": "room", "capacity": 30}]
    dist_case["classes"][0]["size"] = 20
    dist_case["teaching_requirements"][0]["room_required"] = True
    dist_case["locked_assignments"] = [
        {"occurrence_id": "r::1", "slot_id": "1-AM-1", "room_id": "room"}
    ]
    dist_case["constraint_config"]["hard"] = [
        {
            "id": "session",
            "code": "TEACHER_MAX_PERIODS_PER_SESSION",
            "parameters": {"limit": 2, "session_ids": ["AM", "PM"]},
        },
        {"id": "day", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 2}},
        {
            "id": "spread",
            "code": "SUBJECT_COMPONENT_DAY_SPREAD",
            "parameters": {"requirement_ids": ["r"], "min_day_gap": gap},
        },
        {"id": "subject", "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY", "parameters": {"limit": 2}},
    ]
    dist_case["constraint_config"]["soft"] = [
        {
            "id": "avoid",
            "code": "TEACHER_AVOID_SLOTS",
            "parameters": {"slot_ids": ["1-PM-1"]},
            "weight": 1,
            "priority": 1,
        }
    ]
    problem = ScheduleInput.model_validate(dist_case)
    captures: list[tuple[bytes, str, int]] = []
    real_solve = cp_model.CpSolver.solve

    def spy(solver: Any, model: Any, *args: Any, **kwargs: Any) -> Any:
        assert not model.proto.has_objective() and not list(model.proto.solution_hint.vars)
        proto = text_format.Parse(str(model.proto), cp_model_pb2.CpModelProto())
        captures.append(
            (
                proto.SerializeToString(deterministic=True),
                str(solver.parameters),
                solver.parameters.linearization_level,
            )
        )
        return real_solve(solver, model, *args, **kwargs)

    monkeypatch.setattr(cp_model.CpSolver, "solve", spy)
    for mode in ("default", "feasibility_no_lp"):
        prepared = prepare(problem)
        built = build_model(prepared, order_interchangeable=True)
        hard = built.model.clone()
        compiled = compile_soft(prepared, built)
        out = objectives._run_stage(
            prepared,
            built,
            compiled,
            SolveOptions(time_limit_seconds=5.0),
            None,
            5.0,
            model=hard,
            search=mode,
        )
        assert out.status == expected
        if expected == "OPTIMAL":
            assert validate_schedule(problem, out.assignments).valid
            assert evaluate_score(problem, out.assignments).status == "OK"
            assert next(a for a in out.assignments if a.occurrence_id == "r::1").room_id == "room"
        else:
            assert not out.assignments
    assert captures[0][0] == captures[1][0]
    assert captures[0][2] == 1 and captures[1][2] == 0
    assert captures[1][1].replace("linearization_level: 0\n", "") == captures[0][1]


@pytest.mark.parametrize("fixture_name", ["problem_data", "quality_case"])
def test_hard_solve_without_active_quality_keeps_default_lp(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, fixture_name: str
) -> None:
    seen = []
    real_solve = cp_model.CpSolver.solve

    def spy(solver: Any, *args: Any, **kwargs: Any) -> Any:
        seen.append(solver.parameters.linearization_level)
        return real_solve(solver, *args, **kwargs)

    monkeypatch.setattr(cp_model.CpSolver, "solve", spy)
    result = solve(ScheduleInput.model_validate(request.getfixturevalue(fixture_name)))
    assert result.valid_schedule and seen == [1]
