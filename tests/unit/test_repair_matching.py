"""Repair matching: previous positions against the new input's placement domains."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.repair import PreviousSchedule, RepairRequest
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.repair.matching import match


def _a(occurrence: str, slot: str, room: str | None = None) -> ScheduleAssignment:
    return ScheduleAssignment(
        occurrence_id=occurrence, slot_id=slot, room_id=room, class_ids=("c",), teacher_ids=("t",)
    )


def _request(scope: dict[str, Any] | None = None) -> RepairRequest:
    return RepairRequest.model_validate(
        {
            "schema_version": "1.0",
            "change_order": "BEFORE_QUALITY",
            "max_changes": None,
            "change_scope": scope,
            "use_previous_as_hint": False,
        }
    )


def _match(case: dict[str, Any], *assignments: ScheduleAssignment, scope: Any = None) -> Any:
    problem = ScheduleInput.model_validate(case)
    prepared = prepare(problem)
    previous = PreviousSchedule(schema_version="1.0", assignments=assignments)
    return prepared, match(prepared, previous, _request(scope))


def test_targets_new_and_dropped(quality_case: dict[str, Any]) -> None:
    prepared, m = _match(
        quality_case, _a("r::1", "1-AM-1"), _a("r::2", "1-AM-4"), _a("old::1", "2-AM-1")
    )
    assert set(m.targets) == {"r::1", "r::2"} and m.forced == {}
    for occurrence, slot in (("r::1", "1-AM-1"), ("r::2", "1-AM-4")):
        placement = prepared.domains[occurrence][m.targets[occurrence]]
        assert (placement.start_slot_id, placement.room_id) == (slot, None)
    assert m.new == ("r::3",) and m.dropped == ("old::1",) and m.frozen == frozenset()


def test_unavailable_unknown_and_unfitting_targets_are_forced(
    quality_case: dict[str, Any],
) -> None:
    quality_case["teachers"][0]["available_slot_ids"] = [
        s["id"] for s in quality_case["time_slots"] if s["id"] != "1-AM-3"
    ]
    _, m = _match(
        quality_case,
        _a("r::1", "1-AM-4"),  # a double cannot start at the last period
        _a("r::2", "1-AM-3"),  # teacher no longer available
        _a("r::3", "9-AM-1"),  # slot no longer in the calendar
    )
    assert m.targets == {}
    assert m.forced == {"r::1": "DOMAIN", "r::2": "DOMAIN", "r::3": "DOMAIN"}


def test_a_new_lock_wins_over_the_previous_position(quality_case: dict[str, Any]) -> None:
    quality_case["locked_assignments"] = [{"occurrence_id": "r::2", "slot_id": "2-AM-1"}]
    _, m = _match(quality_case, _a("r::2", "1-AM-4"), _a("r::3", "2-AM-1"))
    assert m.forced == {"r::2": "LOCK"}
    # r::3's old position is now taken by the lock: still in its domain, so not forced here;
    # occupancy decides in the model.
    assert set(m.targets) == {"r::3"}


def test_previous_room_on_a_roomless_problem_is_forced(quality_case: dict[str, Any]) -> None:
    _, m = _match(quality_case, _a("r::2", "1-AM-4", "lab"))
    assert m.forced == {"r::2": "DOMAIN"}


def test_scope_freezes_out_of_scope_matches(quality_case: dict[str, Any]) -> None:
    _, m = _match(quality_case, _a("r::1", "1-AM-1"), _a("r::2", "2-AM-4"), scope={"days": [2]})
    assert m.frozen == frozenset({"r::1"})
    _, m = _match(
        quality_case, _a("r::1", "1-AM-1"), _a("r::2", "2-AM-4"), scope={"teacher_ids": ["t"]}
    )
    assert m.frozen == frozenset()


def test_frozen_invalid_target_is_an_input_error(quality_case: dict[str, Any]) -> None:
    quality_case["teachers"][0]["available_slot_ids"] = [
        s["id"] for s in quality_case["time_slots"] if s["id"] != "1-AM-3"
    ]
    with pytest.raises(CoreError) as error:
        _match(quality_case, _a("r::2", "1-AM-3"), scope={"days": [2]})
    assert error.value.status.value == "INPUT_INVALID"
    diagnostic = error.value.diagnostics[0]
    assert diagnostic.code == "REPAIR_FROZEN_TARGET_INVALID"
    assert diagnostic.occurrence_ids == ("r::2",)
