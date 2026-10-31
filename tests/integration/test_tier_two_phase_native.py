"""Native single-worker tier search: deterministic slice, then sticky interleaving."""

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
        (None, "default"),
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
