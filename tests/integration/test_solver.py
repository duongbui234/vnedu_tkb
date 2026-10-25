"""Actual CP-SAT integration, not a mocked solver or benchmark."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult, ValidationReport
from tkb_core.solver.cp_sat import map_status, solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule


def test_actual_solver_validates_single_and_double(problem_data: dict[str, Any]) -> None:
    problem_data["teaching_requirements"][0]["block_durations"] = [2]
    problem = ScheduleInput.model_validate(problem_data)
    result = solve(problem, SolveOptions(time_limit_seconds=5.0))
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.schema_version == "1.1" and result.valid_schedule
    assert len(result.assignments) == 2
    assert validate_schedule(problem, result.assignments).valid
    assert result.assignments[0].slot_id == "day1-am-1"
    assert result.metadata.solver_executed
    assert result.metadata.seed == 42 and result.metadata.num_workers == 1
    assert result.metadata.objective_value is None
    assert ScheduleResult.model_validate_json(result.model_dump_json()) == result


def test_infeasible_requires_actual_search_not_just_load_precheck() -> None:
    # Three teachers' lessons require the same two slot choices in a single class.
    # Each class has a third eligible slot only via a fourth lesson, so load union passes.
    problem = ScheduleInput.model_validate(
        {
            "schema_version": "1.0",
            "school": {"school_id": "demo", "academic_year": "demo", "term": "demo"},
            "time_slots": [
                {"id": str(i), "day": 1, "session": "AM", "period": i + 1} for i in range(4)
            ],
            "classes": [{"id": "c"}],
            "teachers": [
                {"id": str(i), "available_slot_ids": ["0", "1"] if i < 3 else ["2", "3"]}
                for i in range(4)
            ],
            "subjects": [{"id": "s"}],
            "teaching_requirements": [
                {
                    "id": str(i),
                    "class_ids": ["c"],
                    "teacher_ids": [str(i)],
                    "subject_id": "s",
                    "periods_per_cycle": 1,
                }
                for i in range(4)
            ],
        }
    )
    result = solve(problem)
    assert result.status == "INFEASIBLE"
    assert result.metadata.solver_executed and not result.assignments
    assert not result.valid_schedule


def test_empty_problem_does_not_claim_solver_execution(problem_data: dict[str, Any]) -> None:
    problem_data["teaching_requirements"] = []
    problem_data["locked_assignments"] = []
    result = solve(ScheduleInput.model_validate(problem_data))
    assert result.status == "FEASIBLE" and result.valid_schedule
    assert not result.metadata.solver_executed
    assert result.metadata.solver_wall_time is None
    assert result.diagnostics[0].code == "EMPTY_PROBLEM"


@pytest.mark.parametrize(
    "fault,status",
    [
        ("lock", "INPUT_INVALID"),
        ("unsupported", "UNSUPPORTED_FEATURE"),
        ("load", "INFEASIBLE"),
        ("guard", "UNKNOWN"),
    ],
)
def test_preflight_statuses_do_not_run_solver(
    problem_data: dict[str, Any], fault: str, status: str
) -> None:
    options = SolveOptions()
    if fault == "lock":
        problem_data["time_slots"][0]["can_teach"] = False
    elif fault == "unsupported":
        problem_data["constraint_config"]["soft"] = [{"code": "demo", "weight": 1}]
    elif fault == "load":
        problem_data["teaching_requirements"][0]["periods_per_cycle"] = 4
    else:
        options = SolveOptions(max_placements=1)
    result = solve(ScheduleInput.model_validate(problem_data), options)
    assert result.status == status
    assert (
        not result.metadata.solver_executed and not result.valid_schedule and not result.assignments
    )


def test_corrupted_mutable_input_and_options_are_errors(problem_data: dict[str, Any]) -> None:
    problem = ScheduleInput.model_validate(problem_data)
    bad = SolveOptions.model_construct(num_workers=0)
    assert solve(problem, bad).status == "INPUT_INVALID"
    problem.teaching_requirements[0].teacher_ids = ("missing",)
    assert solve(problem).status == "INPUT_INVALID"


def test_validator_failure_prevents_export(
    problem_data: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fault injection at the validator boundary, after real CP-SAT has found a schedule.
    import tkb_core.solver.cp_sat as entry

    monkeypatch.setattr(entry, "validate_schedule", lambda *args: ValidationReport(valid=False))
    result = entry.solve(ScheduleInput.model_validate(problem_data))
    assert result.status == "MODEL_INVALID" and not result.assignments
    assert result.diagnostics[0].code == "INTERNAL_VALIDATION_FAILED"


def test_status_mapping_is_explicit() -> None:
    from ortools.sat.python import cp_model

    for raw, expected in [
        (cp_model.OPTIMAL, "OPTIMAL"),
        (cp_model.FEASIBLE, "FEASIBLE"),
        (cp_model.INFEASIBLE, "INFEASIBLE"),
        (cp_model.UNKNOWN, "UNKNOWN"),
        (cp_model.MODEL_INVALID, "MODEL_INVALID"),
    ]:
        assert map_status(int(raw)) == expected


def test_tiny_budget_never_exports_an_unvalidated_schedule(problem_data: dict[str, Any]) -> None:
    result = solve(
        ScheduleInput.model_validate(problem_data), SolveOptions(time_limit_seconds=1e-9)
    )
    assert result.status in {"UNKNOWN", "FEASIBLE", "OPTIMAL"}
    assert bool(result.assignments) == result.valid_schedule
    if not result.valid_schedule:
        assert result.status == "UNKNOWN"


def test_room_and_actual_time_constraints(problem_data: dict[str, Any]) -> None:
    problem_data["manage_rooms"] = True
    for cls in problem_data["classes"]:
        cls["size"] = 20
    problem_data["rooms"] = [{"id": "lab", "room_type": "lab", "capacity": 25}]
    for req in problem_data["teaching_requirements"]:
        req.update(room_required=True, required_room_type="lab")
    problem_data["teaching_requirements"][0]["block_durations"] = [2]
    for slot, begin, end in zip(
        problem_data["time_slots"], [0, 45, 100], [45, 90, 145], strict=True
    ):
        slot.update(start_minute=begin, end_minute=end)
    result = solve(ScheduleInput.model_validate(problem_data))
    assert result.valid_schedule and all(a.room_id == "lab" for a in result.assignments)
    assert {a.slot_id for a in result.assignments} == {"day1-am-1", "day1-pm-1"}


def test_room_only_lock_does_not_require_unreachable_room_metadata(
    problem_data: dict[str, Any],
) -> None:
    problem_data["manage_rooms"] = True
    problem_data["classes"][0]["size"] = 20
    problem_data["teaching_requirements"] = problem_data["teaching_requirements"][:1]
    problem_data["teaching_requirements"][0].update(
        periods_per_cycle=1, room_required=True, required_room_type="lab"
    )
    problem_data["rooms"] = [
        {"id": "chosen", "room_type": "lab", "capacity": 25},
        {"id": "not-used", "room_type": "lab"},
    ]
    problem_data["locked_assignments"] = [
        {"occurrence_id": "demo-requirement-a::1", "room_id": "chosen"}
    ]
    result = solve(ScheduleInput.model_validate(problem_data))
    assert result.valid_schedule and result.assignments[0].room_id == "chosen"


def test_invalid_metadata_takes_precedence_over_empty_domain(problem_data: dict[str, Any]) -> None:
    problem_data["locked_assignments"] = []
    problem_data["teachers"][0]["available_slot_ids"] = []
    problem_data["manage_rooms"] = True
    problem_data["teaching_requirements"][1]["room_required"] = True
    problem_data["rooms"] = [{"id": "missing-capacity"}]
    result = solve(ScheduleInput.model_validate(problem_data))
    assert result.status == "INPUT_INVALID" and not result.metadata.solver_executed


def test_empty_validator_failure_is_also_an_internal_error(
    problem_data: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import tkb_core.solver.cp_sat as entry

    problem_data["teaching_requirements"] = []
    problem_data["locked_assignments"] = []
    monkeypatch.setattr(entry, "validate_schedule", lambda *args: ValidationReport(valid=False))
    result = entry.solve(ScheduleInput.model_validate(problem_data))
    assert result.status == "MODEL_INVALID"
