"""Guarded occurrence/domain construction; all inputs are synthetic."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.errors import CoreError
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.preprocessing.normalize import normalize
from tkb_core.solver.options import SolveOptions


def test_normalization_is_stable_and_detached(problem_data: dict[str, Any]) -> None:
    source = ScheduleInput.model_validate(problem_data)
    normalized = normalize(source)
    assert [(o.id, o.duration) for o in normalized.occurrences] == [
        ("demo-requirement-a::1", 1),
        ("demo-requirement-a::2", 1),
        ("demo-requirement-b::1", 1),
    ]
    source.teaching_requirements[0].periods_per_cycle = 20
    assert normalized.problem.teaching_requirements[0].periods_per_cycle == 2
    assert normalized.fingerprint == ScheduleInput.model_validate(problem_data).fingerprint()


def test_double_occupies_two_slots_and_preserves_identity(problem_data: dict[str, Any]) -> None:
    problem_data["teaching_requirements"][0]["block_durations"] = [2]
    prepared = prepare(ScheduleInput.model_validate(problem_data))
    assert [o.duration for o in prepared.normalized.occurrences] == [2, 1]
    candidates = prepared.domains["demo-requirement-a::1"]
    assert len(candidates) == 1
    assert candidates[0].slot_ids == ("day1-am-1", "day1-am-2")


@pytest.mark.parametrize("change", ["availability", "break", "missing_period", "other_session"])
def test_double_cannot_cross_forbidden_second_slot(
    problem_data: dict[str, Any], change: str
) -> None:
    problem_data["teaching_requirements"][0]["block_durations"] = [2]
    problem_data["locked_assignments"] = []
    if change == "availability":
        problem_data["teachers"][0]["available_slot_ids"] = ["day1-am-1"]
    elif change == "break":
        problem_data["time_slots"][1]["can_teach"] = False
    elif change == "missing_period":
        problem_data["time_slots"][1]["period"] = 3
    else:
        problem_data["time_slots"][1]["session"] = "OTHER"
    with pytest.raises(CoreError) as caught:
        prepare(ScheduleInput.model_validate(problem_data))
    assert caught.value.status == "INFEASIBLE"


def test_room_filter_ignores_out_of_scope_metadata(problem_data: dict[str, Any]) -> None:
    problem_data["manage_rooms"] = True
    problem_data["classes"][0]["size"] = 25
    problem_data["rooms"] = [
        {"id": "lab", "room_type": "lab", "capacity": 30},
        {"id": "unrelated", "room_type": "gym"},
    ]
    problem_data["teaching_requirements"][0].update(
        room_required=True,
        required_room_type="lab",
        block_durations=[2],
    )
    prepared = prepare(ScheduleInput.model_validate(problem_data))
    assert {p.room_id for p in prepared.domains["demo-requirement-a::1"]} == {"lab"}
    assert {p.room_id for p in prepared.domains["demo-requirement-b::1"]} == {None}
    del problem_data["classes"][0]["size"]
    with pytest.raises(CoreError) as caught:
        prepare(ScheduleInput.model_validate(problem_data))
    assert caught.value.status == "INPUT_INVALID"


def test_lock_into_forbidden_block_is_input_error(problem_data: dict[str, Any]) -> None:
    problem_data["teaching_requirements"][0]["block_durations"] = [2]
    problem_data["time_slots"][1]["can_teach"] = False
    with pytest.raises(CoreError) as caught:
        prepare(ScheduleInput.model_validate(problem_data))
    assert caught.value.status == "INPUT_INVALID"
    assert caught.value.diagnostics[0].code == "LOCK_CONFLICT"


def test_resource_guard_does_not_allocate_huge_demand(problem_data: dict[str, Any]) -> None:
    problem_data["teaching_requirements"][0]["periods_per_cycle"] = 10**12
    with pytest.raises(CoreError) as caught:
        normalize(ScheduleInput.model_validate(problem_data), SolveOptions(max_occurrences=10))
    assert caught.value.status == "UNKNOWN"
    assert caught.value.diagnostics[0].code == "RESOURCE_LIMIT"


@pytest.mark.parametrize("feature", ["long_block", "co_teaching", "rule"])
def test_unsupported_features_are_not_ignored(problem_data: dict[str, Any], feature: str) -> None:
    if feature == "long_block":
        problem_data["teaching_requirements"][0].update(periods_per_cycle=3, block_durations=[3])
    elif feature == "co_teaching":
        problem_data["teaching_requirements"][0]["teacher_ids"].append("demo-teacher-b")
    else:
        problem_data["constraint_config"]["soft"] = [{"code": "custom", "weight": 1}]
    with pytest.raises(CoreError) as caught:
        prepare(ScheduleInput.model_validate(problem_data))
    assert caught.value.status == "UNSUPPORTED_FEATURE"


def test_timed_double_rejects_gap_and_mixed_calendar(problem_data: dict[str, Any]) -> None:
    problem_data["locked_assignments"] = []
    problem_data["teaching_requirements"][0]["block_durations"] = [2]
    for slot, start, end in zip(
        problem_data["time_slots"], [0, 45, 100], [45, 90, 145], strict=True
    ):
        slot.update(start_minute=start, end_minute=end)
    assert prepare(ScheduleInput.model_validate(problem_data)).domains["demo-requirement-a::1"]
    problem_data["time_slots"][1]["start_minute"] = 50
    with pytest.raises(CoreError) as caught:
        prepare(ScheduleInput.model_validate(problem_data))
    assert caught.value.status == "INFEASIBLE"
    del problem_data["time_slots"][1]["start_minute"]
    del problem_data["time_slots"][1]["end_minute"]
    with pytest.raises(CoreError) as caught:
        prepare(ScheduleInput.model_validate(problem_data))
    assert caught.value.status == "INPUT_INVALID"
