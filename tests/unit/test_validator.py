"""Hand-written valid/invalid schedules; never use model domains as an oracle."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.validation.independent_validator import validate_schedule


@pytest.fixture
def assignments() -> list[ScheduleAssignment]:
    return [
        ScheduleAssignment(occurrence_id=occ, slot_id=slot, class_ids=(cls,), teacher_ids=(gv,))
        for occ, slot, cls, gv in [
            ("demo-requirement-a::1", "day1-am-1", "demo-class-a", "demo-teacher-a"),
            ("demo-requirement-a::2", "day1-am-2", "demo-class-a", "demo-teacher-a"),
            ("demo-requirement-b::1", "day1-am-1", "demo-class-b", "demo-teacher-b"),
        ]
    ]


def codes(problem_data: dict[str, Any], assignments: list[ScheduleAssignment]) -> set[str]:
    report = validate_schedule(ScheduleInput.model_validate(problem_data), assignments)
    assert not report.valid
    return {v.code for v in report.violations}


def test_hand_written_schedule_is_valid(
    problem_data: dict[str, Any], assignments: list[ScheduleAssignment]
) -> None:
    assert validate_schedule(ScheduleInput.model_validate(problem_data), assignments).valid


@pytest.mark.parametrize(
    "fault,code",
    [
        ("missing", "OCCURRENCE_COUNT"),
        ("duplicate", "DUPLICATE_OCCURRENCE"),
        ("unknown", "UNKNOWN_OCCURRENCE"),
        ("slot", "UNKNOWN_SLOT"),
        ("participant", "PARTICIPANTS"),
        ("lock", "LOCK_MISMATCH"),
    ],
)
def test_rejects_corrupt_assignments(
    problem_data: dict[str, Any], assignments: list[ScheduleAssignment], fault: str, code: str
) -> None:
    if fault == "missing":
        assignments.pop()
    elif fault == "duplicate":
        assignments[2] = assignments[0].model_copy(deep=True)
    elif fault == "unknown":
        assignments[2].occurrence_id = "unknown::1"
    elif fault == "slot":
        assignments[2].slot_id = "unknown-slot"
    elif fault == "participant":
        assignments[2].teacher_ids = ("demo-teacher-a",)
    else:
        assignments[0].slot_id = "day1-pm-1"
    assert code in codes(problem_data, assignments)


@pytest.mark.parametrize(
    "resource,expected", [("teacher", "TEACHER_OVERLAP"), ("class", "CLASS_OVERLAP")]
)
def test_detects_overlap_on_second_slot_of_double(
    problem_data: dict[str, Any],
    assignments: list[ScheduleAssignment],
    resource: str,
    expected: str,
) -> None:
    problem_data["teaching_requirements"][0]["block_durations"] = [2]
    assignments.pop(1)
    assignments[1].slot_id = "day1-am-2"
    field = "teacher_ids" if resource == "teacher" else "class_ids"
    value = "demo-teacher-a" if resource == "teacher" else "demo-class-a"
    problem_data["teaching_requirements"][1][field] = [value]
    setattr(assignments[1], field, (value,))
    assert expected in codes(problem_data, assignments)


@pytest.mark.parametrize("resource", ["teachers", "classes"])
def test_availability_is_checked_on_entire_block(
    problem_data: dict[str, Any], assignments: list[ScheduleAssignment], resource: str
) -> None:
    problem_data["teaching_requirements"][0]["block_durations"] = [2]
    problem_data[resource][0]["available_slot_ids"] = ["day1-am-1"]
    assignments.pop(1)
    assert "AVAILABILITY" in codes(problem_data, assignments)


def test_timed_overlap_with_distinct_slot_ids(
    problem_data: dict[str, Any], assignments: list[ScheduleAssignment]
) -> None:
    for slot, begin, end in zip(problem_data["time_slots"], [0, 45, 30], [45, 90, 75], strict=True):
        slot.update(start_minute=begin, end_minute=end)
    problem_data["teaching_requirements"][1]["teacher_ids"] = ["demo-teacher-a"]
    assignments[2].teacher_ids = ("demo-teacher-a",)
    assignments[2].slot_id = "day1-pm-1"
    assert "TEACHER_OVERLAP" in codes(problem_data, assignments)


@pytest.mark.parametrize(
    "fault,expected",
    [
        ("capacity", "ROOM_CAPACITY"),
        ("type", "ROOM_TYPE"),
        ("busy", "AVAILABILITY"),
        ("overlap", "ROOM_OVERLAP"),
        ("missing", "ROOM_REQUIRED"),
    ],
)
def test_room_rules_are_independent(
    problem_data: dict[str, Any], assignments: list[ScheduleAssignment], fault: str, expected: str
) -> None:
    problem_data["manage_rooms"] = True
    problem_data["classes"][0]["size"] = 25
    problem_data["classes"][1]["size"] = 25
    problem_data["rooms"] = [{"id": "r", "capacity": 30, "room_type": "lab"}]
    for req in problem_data["teaching_requirements"]:
        req.update(room_required=True, required_room_type="lab")
    for a in assignments:
        a.room_id = "r"
    assignments[2].slot_id = "day1-pm-1"
    if fault == "capacity":
        problem_data["rooms"][0]["capacity"] = 20
    elif fault == "type":
        problem_data["rooms"][0]["room_type"] = "gym"
    elif fault == "busy":
        problem_data["rooms"][0]["available_slot_ids"] = ["day1-am-1", "day1-pm-1"]
    elif fault == "overlap":
        assignments[2].slot_id = "day1-am-1"
    else:
        assignments[0].room_id = None
    assert expected in codes(problem_data, assignments)


def test_break_invalidates_double(
    problem_data: dict[str, Any], assignments: list[ScheduleAssignment]
) -> None:
    problem_data["teaching_requirements"][0]["block_durations"] = [2]
    problem_data["time_slots"][1]["can_teach"] = False
    assignments.pop(1)
    assert "FORBIDDEN_SLOT" in codes(problem_data, assignments)


def test_bad_mutable_input_is_not_trusted(
    problem_data: dict[str, Any], assignments: list[ScheduleAssignment]
) -> None:
    problem = ScheduleInput.model_validate(problem_data)
    problem.teaching_requirements[0].periods_per_cycle = -1
    result = validate_schedule(problem, assignments)
    assert not result.valid and result.violations[0].code == "INPUT_INVALID"


def test_unknown_enabled_rule_is_not_silently_ignored(
    problem_data: dict[str, Any], assignments: list[ScheduleAssignment]
) -> None:
    problem_data["constraint_config"]["hard"] = [{"code": "not-implemented"}]
    assert "UNSUPPORTED_FEATURE" in codes(problem_data, assignments)
