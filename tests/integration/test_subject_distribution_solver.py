"""Public solve with policy 0.3 S05/S06: output 1.4, ScoreReport 1.1 and validation."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score

OPTIONS = SolveOptions(time_limit_seconds=10.0)
SPREAD = {
    "id": "spread",
    "code": "SUBJECT_COMPONENT_DAY_SPREAD",
    "parameters": {"requirement_ids": ["r"], "min_day_gap": 1},
}
SUBJECT_DAY = {"id": "sd", "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY", "parameters": {"limit": 2}}
AVOID_DAYS_2_3 = {
    "id": "avoid",
    "code": "TEACHER_AVOID_SLOTS",
    "parameters": {
        "slot_ids": [f"{d}-{s}-{p}" for d in (2, 3) for s in ("AM", "PM") for p in range(1, 5)]
    },
    "priority": 1,
    "weight": 1,
}


def _soft(rule: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {**rule, "priority": 1, "weight": 1, **extra}


def _solve(data: dict[str, Any]) -> tuple[ScheduleInput, ScheduleResult]:
    p = ScheduleInput.model_validate(data)
    return p, solve(p, OPTIONS)


def test_soft_spread_optimal_with_output_14(dist_case: dict[str, Any]) -> None:
    dist_case["constraint_config"]["soft"] = [
        _soft(SPREAD, parameters={"requirement_ids": ["r"], "min_day_gap": 2})
    ]
    p, r = _solve(dist_case)
    assert r.status == "OPTIMAL" and r.quality.status == "LEXICOGRAPHIC_OPTIMAL"
    assert (r.schema_version, r.quality.policy_version, r.quality.score.schema_version) == (
        "1.4",
        "0.3",
        "1.1",
    )
    # Three components on three days with k=2: best is days 1,2,3 -> (1,2)=1 (2,3)=1 (1,3)=0.
    assert r.quality.score.tiers == (2, 0, 0)
    assert evaluate_score(p, r.assignments) == r.quality.score
    assert ScheduleResult.model_validate_json(r.model_dump_json()) == r


@pytest.mark.parametrize("rule", [SPREAD, SUBJECT_DAY])
def test_hard_only(dist_case: dict[str, Any], rule: dict[str, Any]) -> None:
    dist_case["constraint_config"]["hard"] = [rule]
    p, r = _solve(dist_case)
    assert r.valid_schedule and r.schema_version == "1.4"
    assert (r.quality.status, r.quality.score.schema_version) == ("NOT_REQUESTED", "1.1")
    assert validate_schedule(p, r.assignments).valid


def test_hard_subject_day_forces_soft_penalty(dist_case: dict[str, Any]) -> None:
    dist_case["constraint_config"]["soft"] = [AVOID_DAYS_2_3]
    _, free = _solve(dist_case)
    assert free.quality.score.tiers == (0, 0, 0)
    dist_case["constraint_config"]["hard"] = [SUBJECT_DAY]
    p, r = _solve(dist_case)
    assert r.status == "OPTIMAL" and r.quality.score.tiers == (2, 0, 0)
    assert evaluate_score(p, r.assignments) == r.quality.score


def test_infeasible_spread(dist_case: dict[str, Any]) -> None:
    dist_case["constraint_config"]["hard"] = [
        {**SPREAD, "parameters": {"requirement_ids": ["r"], "min_day_gap": 2}}
    ]
    _, r = _solve(dist_case)
    assert r.status == "INFEASIBLE" and r.schema_version == "1.4" and not r.assignments


def test_missing_hard_compiler_is_caught(
    dist_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("tkb_core.solver.model_builder.add_distribution_limits", lambda *a: None)
    dist_case["constraint_config"]["soft"] = [AVOID_DAYS_2_3]
    dist_case["constraint_config"]["hard"] = [SUBJECT_DAY]
    _, r = _solve(dist_case)
    assert r.status == "MODEL_INVALID" and not r.assignments
    assert r.diagnostics[0].code == "INTERNAL_VALIDATION_FAILED"


def test_wrong_soft_compiler_is_caught(
    dist_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from tkb_core.constraints import soft

    original = soft._compile_distribution

    def drop_penalty(*args: Any) -> Any:
        raw, bound = original(*args)
        zero = args[1].model.new_int_var(0, bound, "forged_zero")
        args[1].model.add(zero == 0)
        return zero, bound

    monkeypatch.setattr(soft, "_compile_distribution", drop_penalty)
    dist_case["constraint_config"]["soft"] = [_soft(SUBJECT_DAY, parameters={"limit": 0})]
    _, r = _solve(dist_case)
    assert r.status == "MODEL_INVALID" and not r.assignments


def test_older_policies_keep_their_versions(dist_case: dict[str, Any]) -> None:
    dist_case["constraint_config"]["policy_version"] = "0.2"
    _, r = _solve(dist_case)
    assert r.schema_version == "1.3" and r.quality.score.schema_version == "1.0"
