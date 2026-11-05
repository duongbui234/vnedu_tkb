"""Resource occupancy indexed by symbolic slots or elementary physical-time segments."""

from collections import defaultdict

from ortools.sat.python import cp_model

from tkb_core.constraints.hard_variants import enabled_hard
from tkb_core.domain.errors import CoreError
from tkb_core.domain.rule_parameters import (
    DaySpreadParameters,
    MaxDayParameters,
    MaxSessionParameters,
    SubjectDayLimitParameters,
)
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
    for _, teachers, params in enabled_hard(problem):
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


def add_distribution_limits(
    model: cp_model.CpModel,
    prepared: PreparedProblem,
    variables: dict[str, tuple[cp_model.IntVar, ...]],
) -> None:
    """Add policy 0.3 hard S05/S06.

    S05: every pair of group components is at least k days apart, written as "each window of
    k consecutive day values holds at most one component" (equivalent on integers; a closer
    pair always fits the window starting at its earlier day). S06: periods of each scoped
    class+subject on a day stay within the limit.
    """
    problem = prepared.normalized.problem
    slots = {s.id: s for s in problem.time_slots}
    requirements = {r.id: r for r in problem.teaching_requirements}
    calendar_days = sorted({s.day for s in problem.time_slots})
    for rule, _, params in enabled_hard(problem):
        if isinstance(params, DaySpreadParameters):
            k = params.min_day_gap
            group = [
                o
                for o in prepared.normalized.occurrences
                if o.requirement_id in params.requirement_ids
            ]
            for first in calendar_days:
                window = [
                    variable
                    for o in group
                    for placement, variable in zip(
                        prepared.domains[o.id], variables[o.id], strict=True
                    )
                    if first <= slots[placement.start_slot_id].day < first + k
                ]
                if len(window) > 1:
                    model.add(sum(window) <= 1)
        elif isinstance(params, SubjectDayLimitParameters):
            classes = set(rule.scope.class_ids) or {c.id for c in problem.classes}
            subjects = set(rule.scope.subject_ids) or {s.id for s in problem.subjects}
            buckets: dict[tuple[str, str, int], list[tuple[int, cp_model.IntVar]]] = defaultdict(
                list
            )
            for occurrence in prepared.normalized.occurrences:
                req = requirements[occurrence.requirement_id]
                if req.class_ids[0] not in classes or req.subject_id not in subjects:
                    continue
                for placement, variable in zip(
                    prepared.domains[occurrence.id], variables[occurrence.id], strict=True
                ):
                    key = (req.class_ids[0], req.subject_id, slots[placement.start_slot_id].day)
                    buckets[key].append((len(placement.slot_ids), variable))
            for terms in buckets.values():
                if params.limit > _MAX_INTEGER or sum(n for n, _ in terms) > _MAX_INTEGER:
                    raise CoreError(
                        "INPUT_INVALID", "HARD_RULE_RANGE", "Hard limit exceeds exact integer range"
                    )
                if sum(n for n, _ in terms) > params.limit:
                    model.add(sum(n * v for n, v in terms) <= params.limit)
