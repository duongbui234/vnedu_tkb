"""Public solve with policy 0.4 S07-S11: output 1.5, ScoreReport 1.2, occupied work."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.score_evaluator import evaluate_score

OPTIONS = SolveOptions(time_limit_seconds=10.0)


def _soft(code: str, priority: int, **parameters: Any) -> dict[str, Any]:
    return {
        "id": code.lower(),
        "code": code,
        "parameters": parameters,
        "priority": priority,
        "weight": 1,
    }


def _solve(data: dict[str, Any]) -> tuple[ScheduleInput, ScheduleResult]:
    p = ScheduleInput.model_validate(data)
    return p, solve(p, OPTIONS)


def test_lexicographic_tradeoff_with_output_15(gap_case: dict[str, Any]) -> None:
    # Avoiding one-period sessions (P1) is free; two free days (P2) are impossible with demand.
    gap_case["constraint_config"]["soft"] = [
        _soft("TEACHER_SINGLE_PERIOD_SESSION", 1, session_ids=["AM", "PM"]),
        _soft("TEACHER_MIN_FREE_TIME", 2, unit="day", target=2),
    ]
    p, r = _solve(gap_case)
    assert r.status == "OPTIMAL" and r.quality.status == "LEXICOGRAPHIC_OPTIMAL"
    assert (r.schema_version, r.quality.policy_version, r.quality.score.schema_version) == (
        "1.5",
        "0.4",
        "1.2",
    )
    assert r.quality.score.tiers == (0, 1, 0)
    assert evaluate_score(p, r.assignments) == r.quality.score
    assert ScheduleResult.model_validate_json(r.model_dump_json()) == r


def _forced_gap(data: dict[str, Any], occupied: bool) -> dict[str, Any]:
    # Only 1-AM-1, 1-AM-3 and 1-AM-4 are available, so 1-AM-2 always sits between lessons.
    data["teachers"][0]["available_slot_ids"] = ["1-AM-1", "1-AM-3", "1-AM-4"]
    data["teaching_requirements"][0].update(periods_per_cycle=3, block_durations=[1, 1, 1])
    data["constraint_config"]["soft"] = [_soft("TEACHER_TOTAL_GAPS", 1, session_ids=["AM"])]
    data["constraint_config"]["occupied_work"] = (
        [{"teacher_id": "t", "slot_ids": ["1-AM-2"]}] if occupied else []
    )
    return data


def test_occupied_work_is_not_a_gap(gap_case: dict[str, Any]) -> None:
    _, unavailable = _solve(_forced_gap(gap_case, occupied=False))
    assert unavailable.quality.score.tiers == (1, 0, 0)  # unavailable but not occupied: idle
    _, meeting = _solve(_forced_gap(gap_case, occupied=True))
    assert meeting.quality.score.tiers == (0, 0, 0)


def test_wrong_gap_compiler_is_caught(
    gap_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from tkb_core.constraints import soft

    original = soft.compile_gap_rule

    def drop_penalty(*args: Any) -> Any:
        raw, bound = original(*args)
        zero = args[1].model.new_int_var(0, bound, "forged_zero")
        args[1].model.add(zero == 0)
        return zero, bound

    monkeypatch.setattr(soft, "compile_gap_rule", drop_penalty)
    _, r = _solve(_forced_gap(gap_case, occupied=False))
    assert r.status == "MODEL_INVALID" and not r.assignments


def test_ambiguous_timeline_is_unsupported(gap_case: dict[str, Any]) -> None:
    gap_case["time_slots"] = [
        {"id": "a1", "day": 1, "session": "A", "period": 1, "start_minute": 0, "end_minute": 45},
        {"id": "b1", "day": 1, "session": "B", "period": 1, "start_minute": 30, "end_minute": 75},
    ]
    gap_case["teaching_requirements"][0].update(periods_per_cycle=1, block_durations=[1])
    gap_case["constraint_config"]["soft"] = [_soft("TEACHER_TOTAL_GAPS", 1, session_ids=["A"])]
    _, r = _solve(gap_case)
    assert r.status == "UNSUPPORTED_FEATURE" and r.diagnostics[0].code == "GAP_TIMELINE"


def test_older_policy_keeps_its_versions(gap_case: dict[str, Any]) -> None:
    gap_case["constraint_config"]["policy_version"] = "0.3"
    _, r = _solve(gap_case)
    assert r.schema_version == "1.4" and r.quality.score.schema_version == "1.1"
