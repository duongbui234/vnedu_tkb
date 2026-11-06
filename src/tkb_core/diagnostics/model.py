"""CP-SAT model with one assumption literal per diagnostic group (Phase 3B spec §3, B11).

Each group literal ``a`` only ever *adds* restrictions when true: model groups are written as
``constraint.only_enforce_if(a)`` and domain groups as ``x ⇒ ¬a``. Setting a literal false
therefore only relaxes the model (monotonicity), which makes cores and deletion sound. The
fixed background is ``AtMostOne`` per occurrence plus B11 symmetry breaking between
interchangeable occurrences. ``solver.model_builder`` and ``constraints.hard`` are not used or
changed; the bucket logic below mirrors them and is cross-checked by tests.
"""

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import pairwise

from ortools.sat.python import cp_model

from tkb_core.constraints.hard_variants import enabled_hard
from tkb_core.contracts.diagnostics import GroupRef
from tkb_core.diagnostics.domains import Candidate, DiagnosticDomains, GroupKey
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.domain.rule_parameters import (
    DaySpreadParameters,
    MaxDayParameters,
    MaxSessionParameters,
    SubjectDayLimitParameters,
)

_MAX_INTEGER = 2**63 - 1


@dataclass(frozen=True)
class DiagnosticModel:
    """Model, placement variables and the group literal of every (kind, id)."""

    model: cp_model.CpModel
    domains: DiagnosticDomains
    variables: dict[str, tuple[cp_model.IntVar, ...]]
    literals: dict[GroupKey, cp_model.IntVar]


@dataclass(frozen=True)
class SubsetOutcome:
    """Status with only the active groups on; core or witness when applicable."""

    status: str  # FEASIBLE / INFEASIBLE / UNKNOWN
    core: tuple[GroupKey, ...]
    assignments: tuple[ScheduleAssignment, ...]


def _rank_safe(size: int) -> bool:
    return size > 1 and size * (size - 1) <= _MAX_INTEGER


def _check_range(limit: int, terms: list[tuple[int, cp_model.IntVar]]) -> None:
    if limit > _MAX_INTEGER or sum(n for n, _ in terms) > _MAX_INTEGER:
        raise CoreError(
            "INPUT_INVALID", "HARD_RULE_RANGE", "Hard limit exceeds exact integer range"
        )


def build_diagnostic_model(
    domains: DiagnosticDomains,
    groups: tuple[GroupRef, ...],
    *,
    order_interchangeable: bool = True,
) -> DiagnosticModel:
    """Build every group's constraints behind its literal; groups not listed stay absent.

    ``order_interchangeable=False`` drops B11 and exists only for the oracle reference.
    """
    normalized = domains.normalized
    problem = normalized.problem
    slots = {s.id: s for s in problem.time_slots}
    requirements = {r.id: r for r in problem.teaching_requirements}
    model = cp_model.CpModel()
    literals: dict[GroupKey, cp_model.IntVar] = {
        (str(g.kind), g.id): model.new_bool_var(f"a_{g.kind}_{g.id}") for g in groups
    }
    variables: dict[str, tuple[cp_model.IntVar, ...]] = {}
    for occurrence in normalized.occurrences:
        choices = tuple(
            model.new_bool_var(f"x_{len(variables)}_{i}")
            for i in range(len(domains.candidates[occurrence.id]))
        )
        variables[occurrence.id] = choices
        if choices:
            model.add_at_most_one(choices)
        demand = literals.get(("DEMAND", occurrence.requirement_id))
        if demand is not None:
            if choices:
                model.add(sum(choices) == 1).only_enforce_if(demand)
            else:
                model.add_bool_and([demand.Not()])
        for candidate, variable in zip(domains.candidates[occurrence.id], choices, strict=True):
            for group in sorted(candidate.violations):
                if group in literals:
                    model.add_implication(variable, literals[group].Not())
                else:  # not diagnosed at this granularity: the placement is simply forbidden
                    model.add(variable == 0)

    def pairs(occurrence_id: str) -> Iterator[tuple[Candidate, cp_model.IntVar]]:
        return zip(domains.candidates[occurrence_id], variables[occurrence_id], strict=True)

    index: dict[tuple[str, str, int], list[cp_model.IntVar]] = defaultdict(list)
    for occurrence in normalized.occurrences:
        req = requirements[occurrence.requirement_id]
        for candidate, variable in pairs(occurrence.id):
            owners = [("CLASS", req.class_ids[0]), ("TEACHER", req.teacher_ids[0])]
            if candidate.placement.room_id is not None:
                owners.append(("ROOM", candidate.placement.room_id))
            for kind, resource in owners:
                for token in candidate.placement.tokens:
                    index[kind, resource, token].append(variable)
    for (kind, resource, _), sharing in index.items():
        owner = literals.get((f"{kind}_OCCUPANCY", resource))
        if owner is not None and len(sharing) > 1:
            model.add(sum(sharing) <= 1).only_enforce_if(owner)

    for rule, scoped, params in enabled_hard(problem):
        literal = literals.get(("HARD_RULE", rule.id))
        if literal is None:
            continue
        buckets: dict[tuple[str, str, int, str], list[tuple[int, cp_model.IntVar]]] = defaultdict(
            list
        )
        limit: int | None = None
        if isinstance(params, (MaxSessionParameters, MaxDayParameters)):
            limit = params.limit
            for occurrence in normalized.occurrences:
                teacher = requirements[occurrence.requirement_id].teacher_ids[0]
                if teacher not in scoped:
                    continue
                for candidate, variable in pairs(occurrence.id):
                    start = slots[candidate.placement.start_slot_id]
                    if isinstance(params, MaxSessionParameters):
                        if start.session not in params.session_ids:
                            continue
                        key = (teacher, "", start.day, start.session)
                    else:
                        key = (teacher, "", start.day, "")
                    buckets[key].append((len(candidate.placement.slot_ids), variable))
        elif isinstance(params, SubjectDayLimitParameters):
            limit = params.limit
            classes = set(rule.scope.class_ids) or {c.id for c in problem.classes}
            subjects = set(rule.scope.subject_ids) or {s.id for s in problem.subjects}
            for occurrence in normalized.occurrences:
                req = requirements[occurrence.requirement_id]
                if req.class_ids[0] not in classes or req.subject_id not in subjects:
                    continue
                for candidate, variable in pairs(occurrence.id):
                    day = slots[candidate.placement.start_slot_id].day
                    key = (req.class_ids[0], req.subject_id, day, "")
                    buckets[key].append((len(candidate.placement.slot_ids), variable))
        elif isinstance(params, DaySpreadParameters):
            k = params.min_day_gap
            components = [
                o for o in normalized.occurrences if o.requirement_id in params.requirement_ids
            ]
            for first in sorted({s.day for s in problem.time_slots}):
                window = [
                    variable
                    for o in components
                    for candidate, variable in pairs(o.id)
                    if first <= slots[candidate.placement.start_slot_id].day < first + k
                ]
                if len(window) > 1:
                    model.add(sum(window) <= 1).only_enforce_if(literal)
        for terms in buckets.values():
            assert limit is not None
            _check_range(limit, terms)
            if sum(n for n, _ in terms) > limit:
                model.add(sum(n * v for n, v in terms) <= limit).only_enforce_if(literal)

    # B11: rank ordering between interchangeable occurrences (same requirement, duration and
    # tagged domain, not locked). Unplaced occurrences rank 0, so any solution of any active
    # subset can be relabelled into this order; oracle-checked in the property tests.
    if not order_interchangeable:
        return DiagnosticModel(model, domains, variables, literals)
    locked = {lock.occurrence_id for lock in problem.locked_assignments}
    by_key: dict[tuple[str, int, tuple[Candidate, ...]], list[str]] = defaultdict(list)
    for occurrence in sorted(normalized.occurrences, key=lambda o: (o.requirement_id, o.ordinal)):
        if occurrence.id not in locked:
            by_key[
                (occurrence.requirement_id, occurrence.duration, domains.candidates[occurrence.id])
            ].append(occurrence.id)
    for (_, _, domain), members in by_key.items():
        if len(members) < 2 or not _rank_safe(len(domain)):
            continue
        weights = list(range(len(domain)))
        ranks = [cp_model.LinearExpr.weighted_sum(variables[o], weights) for o in members]
        for left, right in pairwise(ranks):
            model.add(left <= right)
    return DiagnosticModel(model, domains, variables, literals)


def solve_subset(
    built: DiagnosticModel, active: set[GroupKey], seconds: float, seed: int
) -> SubsetOutcome:
    """Solve with ``active`` literals assumed true; other literals stay free (monotone)."""
    model = built.model
    model.clear_assumptions()
    ordered = sorted(active)
    model.add_assumptions([built.literals[g] for g in ordered])
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_time_in_seconds = max(seconds, 0.001)
    status = solver.solve(model)
    model.clear_assumptions()
    if status == cp_model.MODEL_INVALID:
        raise CoreError("MODEL_INVALID", "DIAGNOSTIC_MODEL", "Diagnostic model was rejected")
    if status == cp_model.INFEASIBLE:
        by_index = {built.literals[g].Index(): g for g in ordered}
        core = tuple(
            sorted(
                by_index[i]
                for i in solver.sufficient_assumptions_for_infeasibility()
                if i in by_index
            )
        )
        return SubsetOutcome("INFEASIBLE", core, ())
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        problem = built.domains.normalized.problem
        requirements = {r.id: r for r in problem.teaching_requirements}
        chosen: list[ScheduleAssignment] = []
        for occurrence in built.domains.normalized.occurrences:
            req = requirements[occurrence.requirement_id]
            for candidate, variable in zip(
                built.domains.candidates[occurrence.id],
                built.variables[occurrence.id],
                strict=True,
            ):
                if solver.boolean_value(variable):
                    chosen.append(
                        ScheduleAssignment(
                            occurrence_id=occurrence.id,
                            slot_id=candidate.placement.start_slot_id,
                            class_ids=req.class_ids,
                            teacher_ids=req.teacher_ids,
                            room_id=candidate.placement.room_id,
                        )
                    )
        return SubsetOutcome("FEASIBLE", (), tuple(chosen))
    return SubsetOutcome("UNKNOWN", (), ())
