"""Redundant S03 teacher-day load bounds derived from prepared domains only.

Every hard-valid selection satisfies these intervals, so adding them keeps the set of
schedules and their penalties unchanged. Nothing here imports OR-Tools or solved data.
"""

from collections import defaultdict
from dataclasses import dataclass

from tkb_core.preprocessing.feasibility import PreparedProblem

MAX_INTEGER = 2**63 - 1
UNVERIFIED_SEMANTICS = "UNVERIFIED_SEMANTICS"
INCOMPLETE_PREPARED_DATA = "INCOMPLETE_PREPARED_DATA"
INCONSISTENT_BOUNDS = "INCONSISTENT_BOUNDS"
UNSAFE_INTEGER_RANGE = "UNSAFE_INTEGER_RANGE"


@dataclass(frozen=True)
class BoundInterval:
    """Inclusive integer interval."""

    lower: int
    upper: int


@dataclass(frozen=True)
class TeacherDayBound:
    """Load and excess intervals of one scoped teacher on one calendar day."""

    teacher_id: str
    day: int
    load: BoundInterval
    excess: BoundInterval


@dataclass(frozen=True)
class S03Bounds:
    """Per teacher-day intervals sorted by (teacher, day) and the rule raw interval."""

    days: tuple[TeacherDayBound, ...]
    raw: BoundInterval


@dataclass(frozen=True)
class S03BoundsDecision:
    """Bounds, or None with the internal fallback reason; never a feasibility verdict."""

    bounds: S03Bounds | None
    reason: str | None


def _fallback(reason: str) -> S03BoundsDecision:
    return S03BoundsDecision(None, reason)


def derive_s03_bounds(
    prepared: PreparedProblem, teacher_ids: frozenset[str], limit: int
) -> S03BoundsDecision:
    """Derive S03 intervals for already resolved teachers and a non-negative limit.

    ``prepared`` must be the snapshot returned by ``prepare`` and the bounds may only be
    used with the model ``build_model`` creates from it. Unverifiable or inconsistent
    data yields ``bounds=None`` so the caller keeps its unbounded compilation.
    """
    if not 0 <= limit <= MAX_INTEGER:
        return _fallback(UNSAFE_INTEGER_RANGE)
    problem = prepared.normalized.problem
    slots = {s.id: s for s in problem.time_slots}
    reqs = {r.id: r for r in problem.teaching_requirements}
    locks = {lock.occurrence_id: lock for lock in problem.locked_assignments}
    calendar = sorted({s.day for s in problem.time_slots})
    demand: dict[str, int] = defaultdict(int)
    union: dict[tuple[str, int], set[str]] = defaultdict(set)
    fixed: dict[tuple[str, int], int] = defaultdict(int)
    for occurrence in prepared.normalized.occurrences:
        req = reqs.get(occurrence.requirement_id)
        if req is None:
            return _fallback(INCOMPLETE_PREPARED_DATA)
        if len(req.teacher_ids) != 1 or len(req.class_ids) != 1:
            return _fallback(UNVERIFIED_SEMANTICS)
        if occurrence.duration not in (1, 2):
            return _fallback(UNVERIFIED_SEMANTICS)
        teacher = req.teacher_ids[0]
        if teacher not in teacher_ids:
            continue
        domain = prepared.domains.get(occurrence.id)
        if not domain:
            return _fallback(INCOMPLETE_PREPARED_DATA)
        lock = locks.get(occurrence.id)
        lock_slot = lock.slot_id if lock is not None else None
        for placement in domain:
            if any(s not in slots for s in (placement.start_slot_id, *placement.slot_ids)):
                return _fallback(INCOMPLETE_PREPARED_DATA)
            covered = [slots[s] for s in placement.slot_ids]
            start = covered[0]
            if (
                len(covered) != occurrence.duration
                or len(set(placement.slot_ids)) != occurrence.duration
                or placement.start_slot_id != start.id
                or any(s.day != start.day or s.session != start.session for s in covered)
                or [s.period - start.period for s in covered] != list(range(len(covered)))
                or (lock_slot is not None and placement.start_slot_id != lock_slot)
            ):
                return _fallback(UNVERIFIED_SEMANTICS)
            if prepared.normalized.timed and len(covered) == 2:
                if covered[0].end_minute != covered[1].start_minute:
                    return _fallback(UNVERIFIED_SEMANTICS)
            union[teacher, start.day].update(placement.slot_ids)
        demand[teacher] += occurrence.duration
        if lock_slot is not None:
            locked = slots.get(lock_slot)
            if locked is None:
                return _fallback(INCOMPLETE_PREPARED_DATA)
            fixed[teacher, locked.day] += occurrence.duration

    days: list[TeacherDayBound] = []
    raw_lower = raw_upper = 0
    for teacher in sorted(teacher_ids):
        total = demand[teacher]
        upper = {d: len(union[teacher, d]) for d in calendar}
        capacity = sum(upper.values())
        if total > capacity or sum(fixed[teacher, d] for d in calendar) > total:
            return _fallback(INCONSISTENT_BOUNDS)
        lower = {d: max(0, fixed[teacher, d], total - (capacity - upper[d])) for d in calendar}
        if any(lower[d] > upper[d] for d in calendar) or sum(lower.values()) > total:
            return _fallback(INCONSISTENT_BOUNDS)
        low = max(
            sum(max(0, lower[d] - limit) for d in calendar),
            total - sum(min(upper[d], limit) for d in calendar),
        )
        high = min(
            sum(max(0, upper[d] - limit) for d in calendar),
            total - sum(min(lower[d], limit) for d in calendar),
        )
        if low > high:
            return _fallback(INCONSISTENT_BOUNDS)
        raw_lower += low
        raw_upper += high
        days.extend(
            TeacherDayBound(
                teacher,
                d,
                BoundInterval(lower[d], upper[d]),
                BoundInterval(max(0, lower[d] - limit), max(0, upper[d] - limit)),
            )
            for d in calendar
        )
    if raw_upper > MAX_INTEGER:
        return _fallback(UNSAFE_INTEGER_RANGE)
    return S03BoundsDecision(S03Bounds(tuple(days), BoundInterval(raw_lower, raw_upper)), None)
