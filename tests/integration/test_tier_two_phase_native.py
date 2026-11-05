"""Native single-worker tier search: deterministic slice, then sticky interleaving."""

from copy import deepcopy
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.solver import objectives
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.score_evaluator import evaluate_score

RULES = [
    {
        "id": "avoid",
        "code": "TEACHER_AVOID_SLOTS",
        "parameters": {"slot_ids": ["1-AM-1"]},
        "weight": 1,
        "priority": 1,
    },
    {
        "id": "day",
        "code": "TEACHER_MAX_PERIODS_PER_DAY",
        "parameters": {"limit": 1},
        "weight": 1,
        "priority": 2,
    },
]


def test_unproved_slice_switches_to_sticky_interleaving(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    quality_case["constraint_config"]["soft"] = RULES
    # A zero slice cannot prove a tier, so the interleaved path runs natively.
    monkeypatch.setattr(objectives, "_TIER_SLICE_DETERMINISTIC_SECONDS", 0.0)
    real = objectives._run_stage
    seen: list[tuple[Any, str, str]] = []

    def spy(*args: Any, **kwargs: Any) -> objectives.StageOutcome:
        out = real(*args, **kwargs)
        seen.append((args[4], kwargs.get("search", "default"), str(out.status)))
        return out

    monkeypatch.setattr(objectives, "_run_stage", spy)
    problem = ScheduleInput.model_validate(quality_case)
    result = solve(problem, SolveOptions(time_limit_seconds=10.0))
    assert result.status == "OPTIMAL" and result.valid_schedule
    assert [(p, s) for p, s, _ in seen] == [
        (None, "feasibility_no_lp"),
        (None, "default"),
        (1, "slice"),
        (1, "interleave"),
        (2, "interleave"),
    ]
    assert seen[2][2] != "OPTIMAL"
    assert evaluate_score(problem, result.assignments) == result.quality.score


@pytest.mark.parametrize("slice_seconds", [None, 0.0])
def test_same_seed_repeats_lexicographic_result(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch, slice_seconds: float | None
) -> None:
    if slice_seconds is not None:
        monkeypatch.setattr(objectives, "_TIER_SLICE_DETERMINISTIC_SECONDS", slice_seconds)
    quality_case["constraint_config"]["soft"] = RULES
    problem = ScheduleInput.model_validate(quality_case)
    options = SolveOptions(time_limit_seconds=10.0, num_workers=1, seed=42)
    first, second = solve(problem, options), solve(problem, options)
    assert first.status == second.status == "OPTIMAL"
    assert first.assignments == second.assignments
    assert first.quality.score == second.quality.score
    assert first.validation is not None and first.validation.valid


def test_native_zero_probe_and_positive_optimum_fallback(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    quality_case["constraint_config"]["soft"] = deepcopy(RULES)
    quality_case["constraint_config"]["soft"][1]["parameters"]["limit"] = 0
    real = objectives._run_stage
    seen: list[tuple[Any, str, str, int | None]] = []

    def spy(*args: Any, **kwargs: Any) -> objectives.StageOutcome:
        built, compiled, priority = args[1], args[2], args[4]
        out = real(*args, **kwargs)
        seen.append(
            (
                priority,
                kwargs.get("search", "default"),
                str(out.status),
                out.tier_values.get(priority),
            )
        )
        if kwargs.get("search") == "slice":
            # The actual native model contains the zero equality, not a changed hint.
            constraints = built.model.proto.constraints
            last = constraints[len(constraints) - 1].linear
            assert list(last.domain) == [0, 0]
            assert priority in compiled.tiers
        return out

    monkeypatch.setattr(objectives, "_run_stage", spy)
    problem = ScheduleInput.model_validate(quality_case)
    result = solve(problem, SolveOptions(time_limit_seconds=10.0))
    assert result.status == "OPTIMAL" and result.valid_schedule
    # A conflicting lower tier must not turn P1's attainable zero into infeasibility.
    assert seen[2] == (1, "slice", "INFEASIBLE", None)
    assert seen[3] == (1, "interleave", "OPTIMAL", 0)
    assert seen[4][0:3] == (2, "interleave", "OPTIMAL")
    assert seen[4][3] is not None and seen[4][3] > 0
    assert evaluate_score(problem, result.assignments) == result.quality.score


def test_native_joint_zero_probe_returns_compatible_lower_tiers(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    rules = deepcopy(RULES)
    rules[1]["parameters"]["limit"] = 2
    rules.append(
        {
            "id": "window",
            "code": "TEACHER_PREFERRED_PERIOD_WINDOW",
            "parameters": {"first_period": 2, "last_period": 4, "session_ids": ["AM", "PM"]},
            "weight": 1,
            "priority": 3,
        }
    )
    quality_case["constraint_config"]["soft"] = rules
    real = objectives._run_stage
    seen: list[objectives.StageOutcome] = []

    def spy(*args: Any, **kwargs: Any) -> objectives.StageOutcome:
        out = real(*args, **kwargs)
        if args[4] is not None:
            assert kwargs["search"] == "slice"
            assert out.tier_values == {1: 0, 2: 0, 3: 0}
            seen.append(out)
        return out

    monkeypatch.setattr(objectives, "_run_stage", spy)
    problem = ScheduleInput.model_validate(quality_case)
    result = solve(problem, SolveOptions(time_limit_seconds=10.0))
    assert result.status == "OPTIMAL" and result.valid_schedule
    assert len(seen) == 3 and result.quality.optimal_prefix == (1, 2, 3)
    assert evaluate_score(problem, result.assignments).tiers == (0, 0, 0)
