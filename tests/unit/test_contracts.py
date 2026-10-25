"""Contract tests catch rejected inputs and unsafe result claims, not solver correctness."""

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult


def test_fixture_roundtrip_and_fingerprint(problem_data: dict[str, Any]) -> None:
    problem = ScheduleInput.model_validate(problem_data)
    restored = ScheduleInput.model_validate_json(problem.model_dump_json())
    assert restored == problem
    assert restored.fingerprint() == problem.fingerprint()
    assert len(problem.fingerprint()) == 64
    assert problem.teaching_requirements[0].occurrence_count == 2


@pytest.mark.parametrize("version", ["0.9", "2.0", None, 1])
def test_rejects_unsupported_schema_version(problem_data: dict[str, Any], version: Any) -> None:
    problem_data["schema_version"] = version
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(problem_data)


@pytest.mark.parametrize("value", [-1, 1.5, "2", True])
def test_rejects_invalid_period_counts(problem_data: dict[str, Any], value: Any) -> None:
    problem_data["teaching_requirements"][0]["periods_per_cycle"] = value
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(problem_data)


@pytest.mark.parametrize(
    "collection", ["classes", "teachers", "subjects", "time_slots", "teaching_requirements"]
)
def test_rejects_duplicate_ids(problem_data: dict[str, Any], collection: str) -> None:
    problem_data[collection].append(copy.deepcopy(problem_data[collection][0]))
    with pytest.raises(ValidationError, match="Duplicate"):
        ScheduleInput.model_validate(problem_data)


@pytest.mark.parametrize(
    "field,value",
    [("class_ids", ["missing"]), ("teacher_ids", ["missing"]), ("subject_id", "missing")],
)
def test_rejects_dangling_references(problem_data: dict[str, Any], field: str, value: Any) -> None:
    problem_data["teaching_requirements"][0][field] = value
    with pytest.raises(ValidationError, match="Unknown"):
        ScheduleInput.model_validate(problem_data)


def test_rejects_nested_unknown_fields(problem_data: dict[str, Any]) -> None:
    problem_data["teachers"][0]["guessed_vnedu_column"] = "ignored?"
    with pytest.raises(ValidationError, match="Extra inputs"):
        ScheduleInput.model_validate(problem_data)


@pytest.mark.parametrize("value", ["", "  ", 123])
def test_rejects_empty_or_nonstring_ids(problem_data: dict[str, Any], value: Any) -> None:
    problem_data["teachers"][0]["id"] = value
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(problem_data)


def test_rejects_unknown_availability_slot(problem_data: dict[str, Any]) -> None:
    problem_data["teachers"][0]["available_slot_ids"] = ["missing"]
    with pytest.raises(ValidationError, match="Unknown"):
        ScheduleInput.model_validate(problem_data)


def test_preserves_empty_availability(problem_data: dict[str, Any]) -> None:
    problem_data["teachers"][0]["available_slot_ids"] = []
    problem = ScheduleInput.model_validate(problem_data)
    assert problem.teachers[0].available_slot_ids == ()
    assert problem.teachers[1].available_slot_ids is None


def test_split_must_preserve_demand(problem_data: dict[str, Any]) -> None:
    problem_data["teaching_requirements"][0]["block_durations"] = [2, 1]
    with pytest.raises(ValidationError, match="duration"):
        ScheduleInput.model_validate(problem_data)
    problem_data["teaching_requirements"][0]["block_durations"] = [2]
    assert ScheduleInput.model_validate(problem_data).teaching_requirements[0].occurrence_count == 1


@pytest.mark.parametrize(
    "lock",
    [
        {"occurrence_id": "missing::1", "slot_id": "day1-am-1"},
        {"occurrence_id": "demo-requirement-a::3", "slot_id": "day1-am-1"},
        {"occurrence_id": "demo-requirement-a::01", "slot_id": "day1-am-1"},
        {"occurrence_id": "demo-requirement-a::1", "slot_id": "missing"},
        {"occurrence_id": "demo-requirement-a::1", "room_id": "missing"},
        {"occurrence_id": "demo-requirement-a::1"},
    ],
)
def test_rejects_invalid_lock_reference(problem_data: dict[str, Any], lock: Any) -> None:
    problem_data["locked_assignments"] = [lock]
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(problem_data)


def test_room_requirements_are_explicit(problem_data: dict[str, Any]) -> None:
    problem_data["teaching_requirements"][0].update(room_required=True, required_room_type="lab")
    with pytest.raises(ValidationError, match="manage_rooms"):
        ScheduleInput.model_validate(problem_data)
    problem_data["manage_rooms"] = True
    # Existence of an eligible room is a Phase 1 feasibility question.
    assert ScheduleInput.model_validate(problem_data).manage_rooms


def test_fingerprint_ignores_catalog_order_but_detects_changes(
    problem_data: dict[str, Any],
) -> None:
    original = ScheduleInput.model_validate(problem_data).fingerprint()
    problem_data["teachers"].reverse()
    problem_data["teaching_requirements"].reverse()
    assert ScheduleInput.model_validate(problem_data).fingerprint() == original
    problem_data["teaching_requirements"][0]["periods_per_cycle"] += 1
    assert ScheduleInput.model_validate(problem_data).fingerprint() != original


def test_result_roundtrip_does_not_claim_solving(problem_data: dict[str, Any]) -> None:
    result = ScheduleResult(
        schema_version="1.0",
        status="NOT_RUN",
        input_fingerprint=ScheduleInput.model_validate(problem_data).fingerprint(),
    )
    restored = ScheduleResult.model_validate_json(result.model_dump_json())
    assert restored.status == "NOT_RUN"
    assert restored.valid_schedule is False
    assert restored.assignments == ()


@pytest.mark.parametrize(
    "status",
    ["NOT_RUN", "UNKNOWN", "INFEASIBLE", "INPUT_INVALID", "MODEL_INVALID", "UNSUPPORTED_FEATURE"],
)
def test_unsuccessful_status_cannot_claim_valid_schedule(status: str) -> None:
    with pytest.raises(ValidationError):
        ScheduleResult(
            schema_version="1.0", status=status, valid_schedule=True, validation={"valid": True}
        )


def test_valid_claim_requires_validator_report() -> None:
    with pytest.raises(ValidationError):
        ScheduleResult(schema_version="1.0", status="FEASIBLE", valid_schedule=True)


def test_invalid_result_cannot_leak_assignments() -> None:
    with pytest.raises(ValidationError):
        ScheduleResult(
            schema_version="1.0",
            status="UNKNOWN",
            assignments=[
                {
                    "occurrence_id": "demo::1",
                    "slot_id": "slot",
                    "class_ids": ["c"],
                    "teacher_ids": ["t"],
                }
            ],
        )


def test_room_mode_rejects_string_boolean(problem_data: dict[str, Any]) -> None:
    problem_data["manage_rooms"] = "false"
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(problem_data)


def test_valid_claim_roundtrips_with_explicit_evidence(problem_data: dict[str, Any]) -> None:
    # A synthetic report tests the result contract only, never solver correctness.
    result = ScheduleResult.model_validate(
        {
            "schema_version": "1.0",
            "status": "FEASIBLE",
            "input_fingerprint": ScheduleInput.model_validate(problem_data).fingerprint(),
            "valid_schedule": True,
            "validation": {"valid": True},
        }
    )
    assert ScheduleResult.model_validate_json(result.model_dump_json()) == result


def test_report_rejects_valid_with_violations() -> None:
    with pytest.raises(ValidationError):
        ScheduleResult.model_validate(
            {
                "schema_version": "1.0",
                "status": "FEASIBLE",
                "valid_schedule": True,
                "input_fingerprint": "0" * 64,
                "validation": {"valid": True, "violations": [{"code": "DEMO", "message": "bad"}]},
            }
        )


@pytest.mark.parametrize(
    "field,value",
    [("class_ids", []), ("teacher_ids", []), ("teacher_ids", ["demo-teacher-a", "demo-teacher-a"])],
)
def test_rejects_empty_or_repeated_participants(
    problem_data: dict[str, Any], field: str, value: Any
) -> None:
    problem_data["teaching_requirements"][0][field] = value
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(problem_data)


def test_rejects_duplicate_lock(problem_data: dict[str, Any]) -> None:
    problem_data["locked_assignments"] *= 2
    with pytest.raises(ValidationError, match="Duplicate"):
        ScheduleInput.model_validate(problem_data)


def test_explicit_room_and_time_locks_roundtrip(problem_data: dict[str, Any]) -> None:
    problem_data["manage_rooms"] = True
    problem_data["rooms"] = [{"id": "demo-room"}]
    problem_data["locked_assignments"][0] = {
        "occurrence_id": "demo-requirement-a::1",
        "room_id": "demo-room",
    }
    assert ScheduleInput.model_validate(problem_data).locked_assignments[0].slot_id is None


def test_time_intervals_require_positive_duration(problem_data: dict[str, Any]) -> None:
    problem_data["time_slots"][0].update(start_minute=60, end_minute=50)
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(problem_data)


def test_zero_period_requirement_is_structurally_valid(problem_data: dict[str, Any]) -> None:
    problem_data["teaching_requirements"][0]["periods_per_cycle"] = 0
    problem_data["locked_assignments"] = []
    assert ScheduleInput.model_validate(problem_data).teaching_requirements[0].occurrence_count == 0


@pytest.mark.parametrize("kind", ["hard", "soft"])
def test_fingerprint_normalizes_rule_scope_sets(problem_data: dict[str, Any], kind: str) -> None:
    rule: dict[str, Any] = {
        "code": "demo-rule",
        "scope": {"teacher_ids": ["demo-teacher-a", "demo-teacher-b"]},
    }
    if kind == "soft":
        rule["weight"] = 1
    problem_data["constraint_config"][kind] = [rule]
    before = ScheduleInput.model_validate(problem_data).fingerprint()
    rule["scope"]["teacher_ids"].reverse()
    assert ScheduleInput.model_validate(problem_data).fingerprint() == before
