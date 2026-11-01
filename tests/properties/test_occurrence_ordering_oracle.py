"""Exhaustive hard/score projections, independent of the rank inequality arithmetic."""

from collections import Counter
from itertools import product
from math import prod
from typing import Any

import pytest
from ortools.sat.python import cp_model

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.feasibility import PreparedProblem, prepare
from tkb_core.solver.model_builder import BuiltModel, build_model
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score


def _assignments(
    prepared: PreparedProblem, indices: tuple[int, ...]
) -> tuple[ScheduleAssignment, ...]:
    reqs = {r.id: r for r in prepared.normalized.problem.teaching_requirements}
    result = []
    for o, i in zip(prepared.normalized.occurrences, indices, strict=True):
        p = prepared.domains[o.id][i]
        req = reqs[o.requirement_id]
        result.append(
            ScheduleAssignment(
                occurrence_id=o.id,
                slot_id=p.start_slot_id,
                room_id=p.room_id,
                class_ids=req.class_ids,
                teacher_ids=req.teacher_ids,
            )
        )
    return tuple(result)


def _projection(
    prepared: PreparedProblem, assignments: tuple[ScheduleAssignment, ...]
) -> tuple[Any, ...]:
    by_id = {o.id: o for o in prepared.normalized.occurrences}
    shape = tuple(
        sorted(
            (
                by_id[a.occurrence_id].requirement_id,
                by_id[a.occurrence_id].duration,
                a.slot_id,
                a.room_id or "",
            )
            for a in assignments
        )
    )
    score = evaluate_score(prepared.normalized.problem, assignments)
    assert score.status == "OK" and score.tiers is not None
    locked = {lock.occurrence_id for lock in prepared.normalized.problem.locked_assignments}
    # Even a room-only lock excludes its occurrence from the permutation orbit:
    # its chosen start can differ across schedules but may not be relabeled away.
    locked_identity = tuple(
        sorted(
            (a.occurrence_id, a.slot_id, a.room_id or "")
            for a in assignments
            if a.occurrence_id in locked
        )
    )
    return shape, locked_identity, score.tiers


class _Selections(cp_model.CpSolverSolutionCallback):
    def __init__(self, prepared: PreparedProblem, built: BuiltModel) -> None:
        super().__init__()
        self.prepared = prepared
        self.built = built
        self.indices: list[tuple[int, ...]] = []

    def on_solution_callback(self) -> None:
        self.indices.append(
            tuple(
                next(i for i, v in enumerate(self.built.variables[o.id]) if self.boolean_value(v))
                for o in self.prepared.normalized.occurrences
            )
        )


def _native_all(prepared: PreparedProblem, ordered: bool) -> list[tuple[int, ...]]:
    built = build_model(prepared, order_interchangeable=ordered)
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 5.0
    callback = _Selections(prepared, built)
    assert solver.solve(built.model, callback) == cp_model.OPTIMAL
    return callback.indices


@pytest.mark.parametrize(
    "variant",
    [
        "two",
        "three",
        "mixed",
        "slot_lock",
        "rooms",
        "room_lock",
        "both_lock",
        "timed_aliases",
        "mixed_timed",
    ],
)
def test_ordering_preserves_every_valid_projection(
    ordering_case: dict[str, Any], variant: str
) -> None:
    req = ordering_case["teaching_requirements"][0]
    if variant == "two":
        req.update(periods_per_cycle=2, block_durations=[1, 1])
    if variant in ("mixed", "mixed_timed"):
        req.update(periods_per_cycle=4, block_durations=[2, 1, 1])
    if variant in ("rooms", "room_lock", "both_lock"):
        ordering_case["manage_rooms"] = True
        ordering_case["classes"][0]["size"] = 10
        ordering_case["rooms"] = [
            {"id": rid, "room_type": "lab", "capacity": 20} for rid in ("opaque-z", "opaque-a")
        ]
        req.update(room_required=True, required_room_type="lab")
    if variant in ("slot_lock", "both_lock"):
        ordering_case["locked_assignments"] = [
            {
                "occurrence_id": "r::2",
                "slot_id": "1-AM-2",
                **({"room_id": "opaque-a"} if variant == "both_lock" else {}),
            }
        ]
    if variant == "room_lock":
        ordering_case["locked_assignments"] = [{"occurrence_id": "r::2", "room_id": "opaque-a"}]
    if variant == "timed_aliases":
        ordering_case["time_slots"] = [
            {
                "id": f"1-{s}-{i}",
                "day": 1,
                "session": s,
                "period": i,
                "start_minute": (i - 1) * 40,
                "end_minute": i * 40,
            }
            for s in ("AM", "PM")
            for i in range(1, 4)
        ]
    if variant == "mixed_timed":
        for i, slot in enumerate(ordering_case["time_slots"]):
            slot.update(start_minute=i * 40, end_minute=(i + 1) * 40)
    problem = ScheduleInput.model_validate(ordering_case)
    prepared = prepare(problem)
    assert prod(len(prepared.domains[o.id]) for o in prepared.normalized.occurrences) <= 4096
    expected: Counter[tuple[Any, ...]] = Counter()
    labelled_count = 0
    noncanonical_witness = None
    for indices in product(
        *(range(len(prepared.domains[o.id])) for o in prepared.normalized.occurrences)
    ):
        assignments = _assignments(prepared, indices)
        if not validate_schedule(problem, assignments).valid:
            continue
        expected[_projection(prepared, assignments)] += 1
        labelled_count += 1
        noncanonical_witness = assignments
    assert expected and noncanonical_witness is not None
    plain = _native_all(prepared, False)
    canonical = _native_all(prepared, True)
    plain_projections = Counter(_projection(prepared, _assignments(prepared, xs)) for xs in plain)
    canonical_projections = Counter(
        _projection(prepared, _assignments(prepared, xs)) for xs in canonical
    )
    assert plain_projections == expected
    assert set(canonical_projections) == set(expected)
    assert set(canonical_projections.values()) == {1}
    assert len(canonical) < len(plain) == labelled_count
    # Independent validation remains a hard-business checker, not a canonical-label checker.
    assert validate_schedule(problem, noncanonical_witness).valid
