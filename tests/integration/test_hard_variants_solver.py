"""Public solve with policy 0.2 hard variants: status, output 1.3 and validation."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score

OPTIONS = SolveOptions(time_limit_seconds=10.0)
HARD = [
    ("TEACHER_AVOID_SLOTS", {"slot_ids": ["1-AM-1", "1-AM-2", "2-AM-1"]}),
    ("TEACHER_MAX_PERIODS_PER_SESSION", {"limit": 1, "session_ids": ["AM", "PM"]}),
    ("TEACHER_MAX_PERIODS_PER_DAY", {"limit": 2}),
    (
        "TEACHER_PREFERRED_PERIOD_WINDOW",
        {"first_period": 2, "last_period": 3, "session_ids": ["AM", "PM"]},
    ),
]
AVOID_DAY_2 = {
    "id": "soft-day-2",
    "code": "TEACHER_AVOID_SLOTS",
    "parameters": {"slot_ids": [f"2-{s}-{p}" for s in ("AM", "PM") for p in range(1, 5)]},
    "priority": 1,
    "weight": 1,
}


def _hard(code: str, params: dict[str, Any]) -> dict[str, Any]:
    return {"id": "hard", "code": code, "parameters": params}


@pytest.mark.parametrize("code,params", HARD)
def test_hard_only_solve_outputs_13(
    hard_case: dict[str, Any], code: str, params: dict[str, Any]
) -> None:
    if code == "TEACHER_MAX_PERIODS_PER_SESSION":
        hard_case["teaching_requirements"][0]["block_durations"] = [1, 1, 1, 1]
    hard_case["constraint_config"]["hard"] = [_hard(code, params)]
    p = ScheduleInput.model_validate(hard_case)
    r = solve(p, OPTIONS)
    assert r.valid_schedule and r.status in ("OPTIMAL", "FEASIBLE")
    assert r.schema_version == "1.3" and r.quality is not None
    assert (r.quality.policy_version, r.quality.status) == ("0.2", "NOT_REQUESTED")
    assert validate_schedule(p, r.assignments).valid
    assert ScheduleResult.model_validate_json(r.model_dump_json()) == r


def test_hard_and_soft_lexicographic(hard_case: dict[str, Any]) -> None:
    hard_case["constraint_config"]["soft"] = [AVOID_DAY_2]
    unconstrained = solve(ScheduleInput.model_validate(hard_case), OPTIONS)
    assert unconstrained.quality.score.tiers == (0, 0, 0)
    hard_case["constraint_config"]["hard"] = [_hard(*HARD[2])]
    p = ScheduleInput.model_validate(hard_case)
    r = solve(p, OPTIONS)
    assert r.status == "OPTIMAL" and r.quality.status == "LEXICOGRAPHIC_OPTIMAL"
    assert r.schema_version == "1.3" and r.quality.score.tiers == (2, 0, 0)
    assert evaluate_score(p, r.assignments) == r.quality.score


def test_infeasible_by_load_and_by_domain(hard_case: dict[str, Any]) -> None:
    hard_case["constraint_config"]["hard"] = [_hard(*HARD[2]) | {"parameters": {"limit": 1}}]
    r = solve(ScheduleInput.model_validate(hard_case), OPTIONS)
    assert r.status == "INFEASIBLE" and r.schema_version == "1.3" and not r.assignments
    every = [s["id"] for s in hard_case["time_slots"]]
    hard_case["constraint_config"]["hard"] = [_hard("TEACHER_AVOID_SLOTS", {"slot_ids": every})]
    r = solve(ScheduleInput.model_validate(hard_case), OPTIONS)
    assert r.status == "INFEASIBLE" and r.diagnostics[0].code == "EMPTY_DOMAIN"
    assert not r.metadata.solver_executed


def test_empty_demand(hard_case: dict[str, Any]) -> None:
    hard_case["teaching_requirements"] = []
    hard_case["constraint_config"]["hard"] = [_hard(*HARD[2])]
    r = solve(ScheduleInput.model_validate(hard_case), OPTIONS)
    assert r.status == "FEASIBLE" and r.diagnostics[0].code == "EMPTY_PROBLEM"
    assert r.schema_version == "1.3" and r.quality.policy_version == "0.2"


def test_missing_compiler_is_caught_by_checker(
    hard_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tkb_core.solver.model_builder.add_load_limits", lambda *a: None)
    hard_case["constraint_config"]["soft"] = [AVOID_DAY_2]
    hard_case["constraint_config"]["hard"] = [_hard(*HARD[2])]
    r = solve(ScheduleInput.model_validate(hard_case), OPTIONS)
    assert r.status == "MODEL_INVALID" and not r.assignments
    assert r.diagnostics[0].code == "INTERNAL_VALIDATION_FAILED"


def test_policy_01_still_refuses_hard(quality_case: dict[str, Any]) -> None:
    quality_case["constraint_config"]["hard"] = [_hard(*HARD[2])]
    r = solve(ScheduleInput.model_validate(quality_case), OPTIONS)
    assert r.status == "UNSUPPORTED_FEATURE" and r.schema_version == "1.2"
    assert r.diagnostics[0].code == "CUSTOM_HARD_RULE"
