"""Repair pipeline: hand-computed minima, limits, ordering, hint and failure handling."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.repair import PreviousSchedule, RepairRequest
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.repair import pipeline
from tkb_core.repair.pipeline import repair
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.repair_evaluator import check_report, evaluate_repair

OPTIONS = SolveOptions(time_limit_seconds=10.0)


def _a(occurrence: str, slot: str) -> ScheduleAssignment:
    return ScheduleAssignment(
        occurrence_id=occurrence, slot_id=slot, class_ids=("c",), teacher_ids=("t",)
    )


def _request(**update: Any) -> RepairRequest:
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "change_order": "BEFORE_QUALITY",
        "max_changes": None,
        "change_scope": None,
        "use_previous_as_hint": False,
    }
    return RepairRequest.model_validate(data | update)


# r::1 is a double; previous schedule fits the gap_case calendar (2 days x AM/PM x 4).
PREVIOUS = PreviousSchedule(
    schema_version="1.0",
    assignments=(_a("r::1", "2-AM-1"), _a("r::2", "1-AM-1"), _a("r::3", "1-PM-1")),
)


def _check_envelope(problem: ScheduleInput, previous: PreviousSchedule, result: Any) -> None:
    """Every returned schedule is hard-valid and its report matches the recomputation."""
    assert result.result.valid_schedule and result.repair is not None
    assert validate_schedule(problem, result.result.assignments).valid
    evaluation = evaluate_repair(problem, previous, result.request, result.result.assignments)
    assert check_report(evaluation, result.repair) == ()
    assert result.previous_fingerprint == previous.fingerprint()


def test_unchanged_input_keeps_the_previous_schedule(gap_case: dict[str, Any]) -> None:
    problem = ScheduleInput.model_validate(gap_case)
    solved = solve(problem, OPTIONS)
    previous = PreviousSchedule.from_result(solved)
    result = repair(problem, previous, _request(), OPTIONS)
    _check_envelope(problem, previous, result)
    assert result.result.schema_version == "1.5" and result.result.status == "OPTIMAL"
    assert result.repair.changed == 0 and result.repair.min_changes_proved
    assert sorted(a.model_dump_json() for a in result.result.assignments) == sorted(
        a.model_dump_json() for a in solved.assignments
    )


def test_teacher_unavailable_forces_exactly_one_change(gap_case: dict[str, Any]) -> None:
    gap_case["teachers"][0]["available_slot_ids"] = [
        s["id"] for s in gap_case["time_slots"] if s["id"] != "1-AM-1"
    ]
    problem = ScheduleInput.model_validate(gap_case)
    result = repair(problem, PREVIOUS, _request(), OPTIONS)
    _check_envelope(problem, PREVIOUS, result)
    assert result.repair.changed == 1 and result.repair.forced == 1
    assert result.repair.changes[0].occurrence_id == "r::2"
    assert result.repair.changes[0].forced == "DOMAIN"


def test_max_changes_below_forced_is_infeasible(gap_case: dict[str, Any]) -> None:
    gap_case["teachers"][0]["available_slot_ids"] = [
        s["id"] for s in gap_case["time_slots"] if s["id"] != "1-AM-1"
    ]
    problem = ScheduleInput.model_validate(gap_case)
    result = repair(problem, PREVIOUS, _request(max_changes=0), OPTIONS)
    assert result.result.status == "INFEASIBLE"
    assert not result.result.valid_schedule and result.repair is None


def test_frozen_target_invalid_is_input_error(gap_case: dict[str, Any]) -> None:
    gap_case["teachers"][0]["available_slot_ids"] = [
        s["id"] for s in gap_case["time_slots"] if s["id"] != "1-AM-1"
    ]
    problem = ScheduleInput.model_validate(gap_case)
    result = repair(problem, PREVIOUS, _request(change_scope={"days": [2]}), OPTIONS)
    assert result.result.status == "INPUT_INVALID"
    assert result.result.diagnostics[0].code == "REPAIR_FROZEN_TARGET_INVALID"


def test_a_new_lock_wins(gap_case: dict[str, Any]) -> None:
    gap_case["locked_assignments"] = [{"occurrence_id": "r::2", "slot_id": "2-PM-4"}]
    problem = ScheduleInput.model_validate(gap_case)
    result = repair(problem, PREVIOUS, _request(), OPTIONS)
    _check_envelope(problem, PREVIOUS, result)
    assert [(c.occurrence_id, c.slot_id, c.forced) for c in result.repair.changes] == [
        ("r::2", "2-PM-4", "LOCK")
    ]


def _avoid_case(gap_case: dict[str, Any]) -> ScheduleInput:
    gap_case["constraint_config"]["soft"] = [
        {
            "id": "avoid",
            "code": "TEACHER_AVOID_SLOTS",
            "parameters": {"slot_ids": ["1-AM-1"]},
            "priority": 1,
            "weight": 1,
            "scope": {"teacher_ids": ["t"]},
        }
    ]
    return ScheduleInput.model_validate(gap_case)


def test_change_order_trades_changes_against_quality(gap_case: dict[str, Any]) -> None:
    problem = _avoid_case(gap_case)
    before = repair(problem, PREVIOUS, _request(change_order="BEFORE_QUALITY"), OPTIONS)
    after = repair(problem, PREVIOUS, _request(change_order="AFTER_QUALITY"), OPTIONS)
    for result in (before, after):
        _check_envelope(problem, PREVIOUS, result)
        assert result.result.status == "OPTIMAL"
        assert result.result.quality.status == "LEXICOGRAPHIC_OPTIMAL"
        assert result.repair.min_changes_proved
    # Keeping r::2 in the avoided slot costs P1=1; moving it costs one change.
    assert (before.repair.changed, before.result.quality.score.tiers) == (0, (1, 0, 0))
    assert (after.repair.changed, after.result.quality.score.tiers) == (1, (0, 0, 0))


@pytest.mark.parametrize("order", ["BEFORE_QUALITY", "AFTER_QUALITY"])
def test_hint_does_not_change_the_optimum(gap_case: dict[str, Any], order: str) -> None:
    problem = _avoid_case(gap_case)
    plain = repair(problem, PREVIOUS, _request(change_order=order), OPTIONS)
    hinted = repair(
        problem, PREVIOUS, _request(change_order=order, use_previous_as_hint=True), OPTIONS
    )
    assert hinted.request.use_previous_as_hint
    assert (plain.repair.changed, plain.result.quality.score.tiers) == (
        hinted.repair.changed,
        hinted.result.quality.score.tiers,
    )


def test_new_and_dropped_occurrences_are_reported(gap_case: dict[str, Any]) -> None:
    previous = PreviousSchedule(
        schema_version="1.0",
        assignments=(_a("r::1", "2-AM-1"), _a("r::2", "1-AM-1"), _a("gone::1", "1-PM-2")),
    )
    problem = ScheduleInput.model_validate(gap_case)
    result = repair(problem, previous, _request(), OPTIONS)
    _check_envelope(problem, previous, result)
    assert result.repair.new_occurrence_ids == ("r::3",)
    assert result.repair.dropped_occurrence_ids == ("gone::1",)
    assert result.repair.changed == 0


def test_wrong_change_terms_never_publish_a_schedule(
    gap_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = pipeline.add_repair_terms

    def off_by_one(*args: Any, **kwargs: Any) -> Any:
        return original(*args, **kwargs) + 1

    monkeypatch.setattr(pipeline, "add_repair_terms", off_by_one)
    problem = ScheduleInput.model_validate(gap_case)
    for request in (_request(), _request(change_order="AFTER_QUALITY")):
        result = repair(problem, PREVIOUS, request, OPTIONS)
        assert result.result.status == "MODEL_INVALID"
        assert result.result.diagnostics[0].code == "REPAIR_REPORT_MISMATCH"
        assert not result.result.valid_schedule and result.repair is None


def test_legacy_input_is_unsupported(problem_data: dict[str, Any]) -> None:
    problem = ScheduleInput.model_validate(problem_data)
    assert problem.schema_version == "1.0"
    result = repair(problem, PREVIOUS, _request(), OPTIONS)
    assert result.result.status == "UNSUPPORTED_FEATURE"
    assert result.result.diagnostics[0].code == "REPAIR_INPUT_VERSION"


def test_tiny_budget_never_claims_unproved_minimum(gap_case: dict[str, Any]) -> None:
    problem = _avoid_case(gap_case)
    for order in ("BEFORE_QUALITY", "AFTER_QUALITY"):
        result = repair(
            problem, PREVIOUS, _request(change_order=order), SolveOptions(time_limit_seconds=1e-9)
        )
        assert result.result.status in ("UNKNOWN", "FEASIBLE", "OPTIMAL")
        if result.repair is not None:
            _check_envelope(problem, PREVIOUS, result)
            stage = result.repair.change_stage
            assert result.repair.min_changes_proved == (stage.raw_status == "OPTIMAL")


def test_every_policy_keeps_its_output_version(quality_case: dict[str, Any]) -> None:
    for policy, version in (("0.1", "1.2"), ("0.2", "1.3"), ("0.3", "1.4"), ("0.4", "1.5")):
        quality_case["constraint_config"]["policy_version"] = policy
        problem = ScheduleInput.model_validate(quality_case)
        result = repair(problem, PREVIOUS, _request(), OPTIONS)
        assert result.result.schema_version == version
        _check_envelope(problem, PREVIOUS, result)
