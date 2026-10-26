"""Public quality solve keeps hard semantics and legacy contracts."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score


@pytest.mark.parametrize(
    "code,params",
    [
        ("TEACHER_AVOID_SLOTS", {"slot_ids": ["1-AM-1"]}),
        ("TEACHER_MAX_PERIODS_PER_SESSION", {"limit": 2, "session_ids": ["AM", "PM"]}),
        ("TEACHER_MAX_PERIODS_PER_DAY", {"limit": 2}),
        (
            "TEACHER_PREFERRED_PERIOD_WINDOW",
            {"first_period": 2, "last_period": 3, "session_ids": ["AM", "PM"]},
        ),
    ],
)
def test_v11_soft_solve_then_independent_score(
    quality_case: dict[str, Any], code: str, params: dict[str, Any]
) -> None:
    quality_case["constraint_config"]["soft"] = [
        {"id": "rule", "code": code, "parameters": params, "weight": 1, "priority": 1}
    ]
    p = ScheduleInput.model_validate(quality_case)
    r = solve(p, SolveOptions(time_limit_seconds=5.0))
    assert r.valid_schedule and r.schema_version == "1.2"
    assert r.status == "OPTIMAL" and r.quality.status == "LEXICOGRAPHIC_OPTIMAL"
    assert evaluate_score(p, r.assignments) == r.quality.score
    assert validate_schedule(p, r.assignments).valid
    assert ScheduleResult.model_validate_json(r.model_dump_json()) == r


def test_empty_and_no_soft(quality_case: dict[str, Any]) -> None:
    p = ScheduleInput.model_validate(quality_case)
    r = solve(p)
    assert r.valid_schedule and r.quality.status == "NOT_REQUESTED"
    quality_case["teaching_requirements"] = []
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 0},
            "weight": 1,
            "priority": 1,
        }
    ]
    r = solve(ScheduleInput.model_validate(quality_case))
    assert r.status == "FEASIBLE" and r.quality.score.tiers == (0, 0, 0)
    assert not r.metadata.solver_executed


def test_hard_modes_and_unknown_rejected(quality_case: dict[str, Any]) -> None:
    quality_case["constraint_config"]["hard"] = [
        {"id": "h", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 0}}
    ]
    assert solve(ScheduleInput.model_validate(quality_case)).status == "UNSUPPORTED_FEATURE"
    quality_case["constraint_config"]["hard"] = []
    quality_case["constraint_config"]["soft"] = [
        {"id": "x", "code": "x", "weight": 1, "priority": 1}
    ]
    p = ScheduleInput.model_validate(quality_case)
    assert solve(p).status == "UNSUPPORTED_FEATURE"
    assert evaluate_score(p, ()).status == "UNSUPPORTED_FEATURE"
