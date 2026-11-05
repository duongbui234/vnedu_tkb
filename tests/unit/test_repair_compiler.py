"""Repair change terms: raw counts on forced placements match the independent evaluator."""

from typing import Any

from ortools.sat.python import cp_model

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.repair import PreviousSchedule, RepairRequest
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.repair.compiler import add_previous_hint, add_repair_terms
from tkb_core.repair.matching import match
from tkb_core.solver.model_builder import build_model
from tkb_core.validation.repair_evaluator import evaluate_repair


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


PREVIOUS = (_a("r::1", "1-AM-1"), _a("r::2", "1-AM-3"), _a("r::3", "1-AM-4"), _a("x::1", "2-AM-1"))


def _solve_fixed(
    case: dict[str, Any], schedule: dict[str, str], request: RepairRequest
) -> tuple[int, int | None, int]:
    """Fix every placement to ``schedule``; return CP-SAT status, change value, evaluator count."""
    problem = ScheduleInput.model_validate(case)
    prepared = prepare(problem)
    previous = PreviousSchedule(schema_version="1.0", assignments=PREVIOUS)
    matching = match(prepared, previous, request)
    built = build_model(prepared)
    expression = add_repair_terms(built, matching, request)
    for o in prepared.normalized.occurrences:
        for p, v in zip(prepared.domains[o.id], built.variables[o.id], strict=True):
            built.model.add_hint(v, p.start_slot_id == schedule[o.id])
    solver = cp_model.CpSolver()
    solver.parameters.fix_variables_to_their_hinted_value = True
    status = solver.solve(built.model)
    assignments = tuple(_a(o, s) for o, s in schedule.items())
    expected = evaluate_repair(problem, previous, request, assignments).changed
    value = (
        int(solver.value(expression)) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None
    )
    return int(status), value, expected


def test_raw_change_count_matches_evaluator(quality_case: dict[str, Any]) -> None:
    for schedule in (
        {"r::1": "1-AM-1", "r::2": "1-AM-3", "r::3": "1-AM-4"},
        {"r::1": "1-AM-1", "r::2": "1-PM-1", "r::3": "1-AM-4"},
        {"r::1": "2-AM-1", "r::2": "2-AM-3", "r::3": "2-AM-4"},
    ):
        status, value, expected = _solve_fixed(quality_case, schedule, _request())
        assert status == cp_model.OPTIMAL and value == expected


def test_forced_changes_are_constant(quality_case: dict[str, Any]) -> None:
    quality_case["teachers"][0]["available_slot_ids"] = [
        s["id"] for s in quality_case["time_slots"] if s["id"] != "1-AM-3"
    ]
    status, value, expected = _solve_fixed(
        quality_case, {"r::1": "1-AM-1", "r::2": "1-PM-1", "r::3": "1-AM-4"}, _request()
    )
    assert status == cp_model.OPTIMAL and value == expected == 1


def test_max_changes_is_a_hard_limit(quality_case: dict[str, Any]) -> None:
    moved = {"r::1": "2-AM-1", "r::2": "2-AM-3", "r::3": "2-AM-4"}
    assert _solve_fixed(quality_case, moved, _request(max_changes=2))[0] == cp_model.INFEASIBLE
    assert _solve_fixed(quality_case, moved, _request(max_changes=3))[0] == cp_model.OPTIMAL


def test_frozen_occurrences_cannot_move(quality_case: dict[str, Any]) -> None:
    request = _request(change_scope={"days": [2]})
    moved = {"r::1": "1-AM-1", "r::2": "1-PM-1", "r::3": "1-AM-4"}
    assert _solve_fixed(quality_case, moved, request)[0] == cp_model.INFEASIBLE
    kept = {"r::1": "1-AM-1", "r::2": "1-AM-3", "r::3": "1-AM-4"}
    assert _solve_fixed(quality_case, kept, request)[0] == cp_model.OPTIMAL


def test_minimizing_finds_zero_and_hint_covers_targets(quality_case: dict[str, Any]) -> None:
    problem = ScheduleInput.model_validate(quality_case)
    prepared = prepare(problem)
    previous = PreviousSchedule(schema_version="1.0", assignments=PREVIOUS)
    request = _request()
    matching = match(prepared, previous, request)
    built = build_model(prepared)
    expression = add_repair_terms(built, matching, request)
    add_previous_hint(built, matching)
    hinted = len(built.model.proto.solution_hint.vars)
    assert hinted == sum(len(prepared.domains[o]) for o in matching.targets)
    built.model.minimize(expression)
    solver = cp_model.CpSolver()
    assert solver.solve(built.model) == cp_model.OPTIMAL
    assert solver.objective_value == 0
