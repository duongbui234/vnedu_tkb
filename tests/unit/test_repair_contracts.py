"""Phase 3A repair contracts: PreviousSchedule, RepairRequest, RepairReport, RepairResult."""

import json
from typing import Any

import pytest
from pydantic import ValidationError

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult
from tkb_core.contracts.repair import (
    ChangeScope,
    ChangeStage,
    PreviousSchedule,
    RepairChange,
    RepairReport,
    RepairRequest,
    RepairResult,
)
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions


def _assignment(occurrence: str, slot: str, room: str | None = None) -> dict[str, Any]:
    return {
        "occurrence_id": occurrence,
        "slot_id": slot,
        "class_ids": ["c"],
        "teacher_ids": ["t"],
        "room_id": room,
    }


def _request(**update: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "change_order": "BEFORE_QUALITY",
        "max_changes": None,
        "change_scope": None,
        "use_previous_as_hint": False,
    }
    return data | update


def test_previous_schedule_roundtrip_and_fingerprint_is_order_free() -> None:
    a = PreviousSchedule.model_validate(
        {
            "schema_version": "1.0",
            "assignments": [_assignment("r::1", "1-AM-1"), _assignment("r::2", "1-AM-2")],
        }
    )
    b = PreviousSchedule.model_validate(
        {
            "schema_version": "1.0",
            "assignments": [_assignment("r::2", "1-AM-2"), _assignment("r::1", "1-AM-1")],
        }
    )
    assert PreviousSchedule.model_validate_json(a.model_dump_json()) == a
    assert a.fingerprint() == b.fingerprint()
    assert a.source_input_fingerprint is None
    moved = PreviousSchedule.model_validate(
        {"schema_version": "1.0", "assignments": [_assignment("r::1", "1-AM-3")]}
    )
    assert moved.fingerprint() != a.fingerprint()


@pytest.mark.parametrize(
    "data",
    [
        {"schema_version": "1.1", "assignments": []},
        {"schema_version": "1.0", "assignments": [], "extra": 1},
        {
            "schema_version": "1.0",
            "assignments": [_assignment("r::1", "1-AM-1"), _assignment("r::1", "1-AM-2")],
        },
        {"schema_version": "1.0", "assignments": [], "source_input_fingerprint": "abc"},
    ],
)
def test_previous_schedule_rejects_invalid(data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PreviousSchedule.model_validate(data)


def test_request_requires_every_decision_explicitly() -> None:
    request = RepairRequest.model_validate(_request())
    assert request.change_order == "BEFORE_QUALITY"
    for key in ("change_order", "max_changes", "change_scope", "use_previous_as_hint"):
        data = _request()
        del data[key]
        with pytest.raises(ValidationError):
            RepairRequest.model_validate(data)


@pytest.mark.parametrize(
    "update",
    [
        {"change_order": "FIRST"},
        {"max_changes": -1},
        {"max_changes": 1.0},
        {"use_previous_as_hint": 1},
        {"change_scope": {}},
        {"change_scope": {"class_ids": ["c", "c"]}},
        {"change_scope": {"days": [0]}},
        {"change_scope": {"rooms": ["x"]}},
        {"schema_version": "2.0"},
    ],
)
def test_request_rejects_invalid(update: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        RepairRequest.model_validate(_request(**update))


def test_scope_accepts_any_non_empty_criterion() -> None:
    scope = ChangeScope.model_validate({"teacher_ids": ["t"], "days": [2]})
    assert scope.class_ids == () and scope.days == (2,)


def _report(**update: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "change_order": "BEFORE_QUALITY",
        "max_changes": None,
        "change_scope": None,
        "matched": 2,
        "new": 1,
        "dropped": 0,
        "changed": 1,
        "slot_changes": 1,
        "room_only_changes": 0,
        "unchanged": 1,
        "frozen": 0,
        "forced": 0,
        "changes": [
            {
                "occurrence_id": "r::1",
                "previous_slot_id": "1-AM-1",
                "previous_room_id": None,
                "slot_id": "1-AM-2",
                "room_id": None,
                "forced": None,
            }
        ],
        "new_occurrence_ids": ["r::3"],
        "dropped_occurrence_ids": [],
        "change_stage": {
            "raw_status": "OPTIMAL",
            "incumbent_value": 1,
            "best_bound": 1.0,
            "wall_time": 0.1,
            "proved_optimal": True,
        },
        "min_changes_proved": True,
    }
    return data | update


def test_report_arithmetic_is_checked() -> None:
    RepairReport.model_validate(_report())
    for update in (
        {"changed": 2},
        {"unchanged": 0},
        {"slot_changes": 0, "room_only_changes": 1},
        {"forced": 1},
        {"new": 2},
        {"max_changes": 0},
        {"min_changes_proved": True, "change_stage": {"raw_status": "FEASIBLE"}},
        {
            "change_stage": {
                "raw_status": "OPTIMAL",
                "incumbent_value": 2,
                "proved_optimal": True,
            }
        },
    ):
        with pytest.raises(ValidationError):
            RepairReport.model_validate(_report(**update))


def test_change_record_kind() -> None:
    room_only = RepairChange(
        occurrence_id="r::1",
        previous_slot_id="1-AM-1",
        previous_room_id="a",
        slot_id="1-AM-1",
        room_id="b",
        forced="DOMAIN",
    )
    assert not room_only.slot_changed
    with pytest.raises(ValidationError):
        RepairChange(
            occurrence_id="r::1",
            previous_slot_id="1-AM-1",
            previous_room_id=None,
            slot_id="1-AM-1",
            room_id=None,
        )


def test_stage_claims_need_evidence() -> None:
    assert ChangeStage().raw_status == "NOT_RUN"
    with pytest.raises(ValidationError):
        ChangeStage(raw_status="NOT_RUN", wall_time=1.0)
    with pytest.raises(ValidationError):
        ChangeStage(raw_status="FEASIBLE", proved_optimal=True, incumbent_value=1)


def _solved(case: dict[str, Any]) -> tuple[ScheduleInput, ScheduleResult]:
    problem = ScheduleInput.model_validate(case)
    return problem, solve(problem, SolveOptions(time_limit_seconds=5.0))


@pytest.mark.parametrize("policy", ["0.1", "0.2", "0.3", "0.4"])
def test_result_envelope_keeps_existing_output_version(
    quality_case: dict[str, Any], policy: str
) -> None:
    quality_case["constraint_config"]["policy_version"] = policy
    problem, result = _solved(quality_case)
    assert result.valid_schedule
    previous = PreviousSchedule.from_result(result)
    assert previous.source_input_fingerprint == problem.fingerprint()
    assert len(previous.assignments) == len(result.assignments)
    envelope = RepairResult(
        result=result,
        previous_fingerprint=previous.fingerprint(),
        previous_source_input_fingerprint=previous.source_input_fingerprint,
        previous_assignment_count=len(previous.assignments),
        request=RepairRequest.model_validate(_request()),
        repair=RepairReport.model_validate(
            _report(
                matched=3,
                new=0,
                changed=0,
                slot_changes=0,
                unchanged=3,
                changes=[],
                new_occurrence_ids=[],
                change_stage={
                    "raw_status": "OPTIMAL",
                    "incumbent_value": 0,
                    "proved_optimal": True,
                },
            )
        ),
    )
    again = RepairResult.model_validate_json(envelope.model_dump_json())
    assert again == envelope
    assert (
        json.loads(envelope.model_dump_json())["result"]["schema_version"]
        == ({"0.1": "1.2", "0.2": "1.3", "0.3": "1.4", "0.4": "1.5"}[policy])
    )


def test_result_envelope_requires_report_iff_schedule(quality_case: dict[str, Any]) -> None:
    _, result = _solved(quality_case)
    with pytest.raises(ValidationError):
        RepairResult(
            result=result,
            previous_fingerprint="0" * 64,
            previous_source_input_fingerprint=None,
            previous_assignment_count=0,
            request=RepairRequest.model_validate(_request()),
            repair=None,
        )


def test_previous_from_result_requires_valid_schedule(quality_case: dict[str, Any]) -> None:
    quality_case["teaching_requirements"][0]["periods_per_cycle"] = 40
    quality_case["teaching_requirements"][0]["block_durations"] = None
    _, result = _solved(quality_case)
    assert not result.valid_schedule
    with pytest.raises(ValueError, match="valid"):
        PreviousSchedule.from_result(result)
