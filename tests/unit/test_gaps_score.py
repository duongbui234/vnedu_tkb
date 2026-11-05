"""Independent S07-S11 scoring from raw assignments (Phase 2C-2)."""

from typing import Any

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.validation.score_evaluator import evaluate_score

ALL_SLOTS = [f"{d}-{s}-{p}" for d in (1, 2) for s in ("AM", "PM") for p in (1, 2, 3, 4)]


def _rule(code: str, **parameters: Any) -> dict[str, Any]:
    return {"id": code.lower(), "code": code, "parameters": parameters, "priority": 2, "weight": 1}


def _raw(
    data: dict[str, Any],
    rule: dict[str, Any],
    starts: list[str],
    blocks: list[int] | None = None,
    occupied: list[str] | None = None,
    no_teach: list[str] | None = None,
) -> tuple[int, str]:
    blocks = blocks or [1] * len(starts)
    data["teaching_requirements"][0].update(periods_per_cycle=sum(blocks), block_durations=blocks)
    for slot in data["time_slots"]:
        slot["can_teach"] = slot["id"] not in (no_teach or [])
    data["teachers"][0]["available_slot_ids"] = [s for s in ALL_SLOTS if s not in (occupied or [])]
    data["constraint_config"]["occupied_work"] = (
        [{"teacher_id": "t", "slot_ids": occupied}] if occupied else []
    )
    data["constraint_config"]["soft"] = [rule]
    assignments = tuple(
        ScheduleAssignment(occurrence_id=f"r::{i}", slot_id=s, class_ids=("c",), teacher_ids=("t",))
        for i, s in enumerate(starts, 1)
    )
    report = evaluate_score(ScheduleInput.model_validate(data), assignments)
    assert report.status == "OK", report.diagnostics
    assert report.schema_version == "1.2"
    (row,) = report.rules
    assert row.weighted_penalty == row.raw_penalty and report.tiers == (0, row.raw_penalty, 0)
    return row.raw_penalty, row.unit


GAPS = _rule("TEACHER_TOTAL_GAPS", session_ids=["AM"])


def test_total_gaps_between_first_and_last(gap_case: dict[str, Any]) -> None:
    assert _raw(gap_case, GAPS, ["1-AM-1", "1-AM-4"]) == (2, "idle_periods")


def test_non_teaching_and_occupied_slots_are_not_idle(gap_case: dict[str, Any]) -> None:
    assert _raw(gap_case, GAPS, ["1-AM-1", "1-AM-4"], no_teach=["1-AM-2"])[0] == 1
    assert _raw(gap_case, GAPS, ["1-AM-1", "1-AM-4"], occupied=["1-AM-3"])[0] == 1


def test_double_and_single_sessions(gap_case: dict[str, Any]) -> None:
    assert _raw(gap_case, GAPS, ["1-AM-1", "1-AM-4"], blocks=[2, 1])[0] == 1
    assert _raw(gap_case, GAPS, ["1-AM-2", "2-AM-4"])[0] == 0  # one period per session
    assert _raw(gap_case, GAPS, ["1-PM-1", "1-PM-4"])[0] == 0  # PM not selected


def test_gap_run(gap_case: dict[str, Any]) -> None:
    run = _rule("TEACHER_MAX_GAP_RUN", limit=1, session_ids=["AM", "PM"])
    assert _raw(gap_case, run, ["1-AM-1", "1-AM-4"]) == (1, "idle_periods")
    zero = _rule("TEACHER_MAX_GAP_RUN", limit=0, session_ids=["AM"])
    assert _raw(gap_case, zero, ["1-AM-1", "1-AM-4"])[0] == 2
    # A non-teaching or occupied slot cuts the run: longest run becomes 1.
    assert _raw(gap_case, zero, ["1-AM-1", "1-AM-4"], no_teach=["1-AM-2"])[0] == 1
    assert _raw(gap_case, zero, ["1-AM-1", "1-AM-4"], occupied=["1-AM-2"])[0] == 1
    # Each session contributes its own excess.
    assert _raw(gap_case, run, ["1-AM-1", "1-AM-4", "1-PM-1", "1-PM-4"])[0] == 2


def test_free_days_and_sessions(gap_case: dict[str, Any]) -> None:
    days = _rule("TEACHER_MIN_FREE_TIME", unit="day", target=2)
    assert _raw(gap_case, days, ["1-AM-1", "1-PM-1"]) == (1, "free_days")
    assert (
        _raw(gap_case, _rule("TEACHER_MIN_FREE_TIME", unit="day", target=1), ["1-AM-1", "1-PM-1"])[
            0
        ]
        == 0
    )
    # A day holding only a meeting is not free.
    assert _raw(gap_case, days, ["1-AM-1", "1-PM-1"], occupied=["2-PM-3"])[0] == 2
    sessions = _rule("TEACHER_MIN_FREE_TIME", unit="session", target=4)
    assert _raw(gap_case, sessions, ["1-AM-1", "1-AM-2"]) == (1, "free_sessions")


def test_days_without_teaching_slots_are_not_eligible(gap_case: dict[str, Any]) -> None:
    days = _rule("TEACHER_MIN_FREE_TIME", unit="day", target=1)
    day_2 = [s for s in ALL_SLOTS if s.startswith("2-")]
    assert _raw(gap_case, days, ["1-AM-1"], no_teach=day_2)[0] == 1


def test_single_period_sessions(gap_case: dict[str, Any]) -> None:
    single = _rule("TEACHER_SINGLE_PERIOD_SESSION", session_ids=["AM", "PM"])
    assert _raw(gap_case, single, ["1-AM-1", "2-AM-1"]) == (2, "single_period_sessions")
    assert _raw(gap_case, single, ["1-AM-1", "1-PM-1"], blocks=[2, 1])[0] == 1
    assert _raw(gap_case, single, ["1-AM-1", "1-AM-3"])[0] == 0


def test_restricted_slots_count_covered_periods(gap_case: dict[str, Any]) -> None:
    restricted = _rule("TEACHER_RESTRICTED_SLOTS", slot_ids=["1-AM-2"])
    assert _raw(gap_case, restricted, ["1-AM-1"], blocks=[2]) == (1, "teaching_periods")
    assert _raw(gap_case, restricted, ["1-AM-3"], blocks=[2])[0] == 0
