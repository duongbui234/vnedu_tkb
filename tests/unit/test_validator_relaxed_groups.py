"""Independent validator: Phase 3B relaxed-group mode for minimality witnesses (Task 6)."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.validation.independent_validator import validate_schedule


def _a(
    occurrence: str, slot: str, cls: str, teacher: str, room: str | None = None
) -> ScheduleAssignment:
    return ScheduleAssignment(
        occurrence_id=occurrence,
        slot_id=slot,
        class_ids=(cls,),
        teacher_ids=(teacher,),
        room_id=room,
    )


def _codes(problem: ScheduleInput, rows: list[ScheduleAssignment], relaxed: Any = ()) -> list[str]:
    return sorted(
        v.code for v in validate_schedule(problem, rows, relaxed_groups=relaxed).violations
    )


def test_default_matches_full_validation(triangle_case: dict[str, Any]) -> None:
    problem = ScheduleInput.model_validate(triangle_case)
    rows = [_a("r1::1", "d1p1", "c1", "t1"), _a("r2::1", "d1p1", "c1", "t2", "lab")]
    assert validate_schedule(problem, rows) == validate_schedule(problem, rows, relaxed_groups=())
    assert _codes(problem, rows) == ["CLASS_OVERLAP", "OCCURRENCE_COUNT", "OCCURRENCE_COUNT"]


def test_demand_allows_missing_but_never_extra(triangle_case: dict[str, Any]) -> None:
    problem = ScheduleInput.model_validate(triangle_case)
    rows = [_a("r1::1", "d1p1", "c1", "t1"), _a("r2::1", "d1p2", "c1", "t2", "lab")]
    assert _codes(problem, rows, {("DEMAND", "r3")}) == []
    assert _codes(problem, rows, {("DEMAND", "r2")}) == ["OCCURRENCE_COUNT"]  # r3 still missing


def test_occupancy_relaxation_is_per_resource(triangle_case: dict[str, Any]) -> None:
    problem = ScheduleInput.model_validate(triangle_case)
    rows = [
        _a("r1::1", "d1p1", "c1", "t1"),
        _a("r2::1", "d1p1", "c1", "t2", "lab"),
        _a("r3::1", "d1p2", "c2", "t1", "lab"),
    ]
    assert _codes(problem, rows) == ["CLASS_OVERLAP"]
    assert _codes(problem, rows, {("CLASS_OCCUPANCY", "c1")}) == []
    assert _codes(problem, rows, {("CLASS_OCCUPANCY", "c2")}) == ["CLASS_OVERLAP"]
    assert _codes(problem, rows, {("TEACHER_OCCUPANCY", "t1")}) == ["CLASS_OVERLAP"]


def test_lock_availability_and_hard_rule_relaxation(spread_case: dict[str, Any]) -> None:
    spread_case["teachers"][0]["available_slot_ids"] = ["d1p1", "d1p2"]
    problem = ScheduleInput.model_validate(spread_case)
    rows = [
        _a("r::1", "d1p1", "c1", "t1"),
        _a("r::2", "d1p2", "c1", "t1"),
        _a("r3::1", "d2p1", "c2", "t1"),
    ]
    assert _codes(problem, rows) == ["AVAILABILITY", "HARD_DAY_SPREAD"]
    assert _codes(problem, rows, {("TEACHER_AVAILABILITY", "t1")}) == ["HARD_DAY_SPREAD"]
    relaxed = {("TEACHER_AVAILABILITY", "t1"), ("HARD_RULE", "spread")}
    assert _codes(problem, rows, relaxed) == []
    moved = [rows[0], rows[1], _a("r3::1", "d1p1", "c2", "t1")]
    assert "LOCK_MISMATCH" in _codes(problem, moved, relaxed)
    assert "LOCK_MISMATCH" not in _codes(problem, moved, relaxed | {("LOCK", "r3::1")})
    # Background is never relaxed: a slot outside the calendar stays invalid.
    every = relaxed | {("LOCK", "r3::1"), ("DEMAND", "r"), ("DEMAND", "r3")}
    bad = [_a("r::1", "nowhere", "c1", "t1")]
    assert _codes(problem, bad, every) == ["UNKNOWN_SLOT"]


def test_unknown_kind_is_refused(triangle_case: dict[str, Any]) -> None:
    problem = ScheduleInput.model_validate(triangle_case)
    with pytest.raises(ValueError):
        validate_schedule(problem, [], relaxed_groups={("CALENDAR", "x")})
