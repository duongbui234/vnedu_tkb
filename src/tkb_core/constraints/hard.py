"""Resource occupancy indexed by symbolic slots or elementary physical-time segments."""

from collections import defaultdict

from ortools.sat.python import cp_model

from tkb_core.constraints.hard_variants import enabled_hard
from tkb_core.domain.errors import CoreError
from tkb_core.domain.rule_parameters import MaxDayParameters, MaxSessionParameters
from tkb_core.preprocessing.feasibility import PreparedProblem

_MAX_INTEGER = 2**63 - 1


def add_occupancy(
    model: cp_model.CpModel,
    prepared: PreparedProblem,
    variables: dict[str, tuple[cp_model.IntVar, ...]],
) -> None:
    """Add AtMostOne per resource/token; all slots of a block share its Boolean."""
    index: dict[tuple[str, str, int], list[cp_model.IntVar]] = defaultdict(list)
    requirements = {r.id: r for r in prepared.normalized.problem.teaching_requirements}
    for occurrence in prepared.normalized.occurrences:
        req = requirements[occurrence.requirement_id]
        for placement, variable in zip(
            prepared.domains[occurrence.id], variables[occurrence.id], strict=True
        ):
            resources = [("class", req.class_ids[0]), ("teacher", req.teacher_ids[0])]
            if placement.room_id is not None:
                resources.append(("room", placement.room_id))
            for kind, resource_id in resources:
                for token in placement.tokens:
                    index[kind, resource_id, token].append(variable)
    for choices in index.values():
        if len(choices) > 1:
            model.add_at_most_one(choices)


def add_load_limits(
    model: cp_model.CpModel,
    prepared: PreparedProblem,
    variables: dict[str, tuple[cp_model.IntVar, ...]],
) -> None:
    """Add policy 0.2 hard S02/S03 limits: Σ duration·x ≤ limit per teacher bucket.

    A block lies in one day/session, so its whole duration counts in the bucket of its
    start slot. Limits and coefficient sums are checked in signed int64 before adding.
    """
    problem = prepared.normalized.problem
    slots = {s.id: s for s in problem.time_slots}
    requirements = {r.id: r for r in problem.teaching_requirements}
    for teachers, params in enabled_hard(problem):
        if not isinstance(params, (MaxSessionParameters, MaxDayParameters)):
            continue
        buckets: dict[tuple[str, int, str], list[tuple[int, cp_model.IntVar]]] = defaultdict(list)
        for occurrence in prepared.normalized.occurrences:
            teacher = requirements[occurrence.requirement_id].teacher_ids[0]
            if teacher not in teachers:
                continue
            for placement, variable in zip(
                prepared.domains[occurrence.id], variables[occurrence.id], strict=True
            ):
                start = slots[placement.start_slot_id]
                if isinstance(params, MaxSessionParameters):
                    if start.session not in params.session_ids:
                        continue
                    key = (teacher, start.day, start.session)
                else:
                    key = (teacher, start.day, "")
                buckets[key].append((len(placement.slot_ids), variable))
        for terms in buckets.values():
            if params.limit > _MAX_INTEGER or sum(n for n, _ in terms) > _MAX_INTEGER:
                raise CoreError(
                    "INPUT_INVALID", "HARD_RULE_RANGE", "Hard limit exceeds exact integer range"
                )
            if sum(n for n, _ in terms) > params.limit:
                model.add(sum(n * v for n, v in terms) <= params.limit)
