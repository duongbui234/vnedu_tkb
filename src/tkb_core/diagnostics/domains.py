"""Placement domains for diagnosis, tagged with the domain groups each placement violates.

``preprocessing.prepare`` removes placements that break a lock, an availability or a
placement-local hard rule (S01/S04), so the solve model has nothing to relax there. This
module rebuilds the same domains but keeps, per placement, the set of such groups it
violates. With ``expanded=False`` only clean placements are kept (same domain as
``prepare``); with ``expanded=True`` violating placements stay and the diagnostic model links
them to the group literals. The fixed background (calendar, ``can_teach``, block
continuity, room type and capacity) is never relaxed. ``prepare`` itself is not changed.
"""

from dataclasses import dataclass

from tkb_core.constraints.hard_variants import enabled_hard
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import AvailableResource, Room, TimeSlot
from tkb_core.domain.rule_parameters import AvoidSlotsParameters, PeriodWindowParameters
from tkb_core.preprocessing.feasibility import Placement
from tkb_core.preprocessing.normalize import NormalizedProblem, resource_limit

GroupKey = tuple[str, str]


@dataclass(frozen=True)
class Candidate:
    """One placement and the domain groups (kind, id) it violates; empty means clean."""

    placement: Placement
    violations: frozenset[GroupKey]


@dataclass(frozen=True)
class DiagnosticDomains:
    """Candidates per occurrence, in ``prepare`` order (start slot, then room ID)."""

    normalized: NormalizedProblem
    candidates: dict[str, tuple[Candidate, ...]]
    expanded: bool

    def clean(self, occurrence_id: str) -> tuple[Placement, ...]:
        """Placements satisfying every constraint: the ``prepare`` domain."""
        return tuple(c.placement for c in self.candidates[occurrence_id] if not c.violations)


def _available(resource: AvailableResource, slots: tuple[TimeSlot, ...]) -> bool:
    return resource.available_slot_ids is None or all(
        s.id in resource.available_slot_ids for s in slots
    )


def placement_rule_blocks(problem_slots: tuple[TimeSlot, ...], params: object) -> frozenset[str]:
    """Slot IDs one S01/S04 hard rule forbids (same semantics as ``placement_filter``)."""
    blocked: set[str] = set()
    if isinstance(params, AvoidSlotsParameters):
        targets = [s for s in problem_slots if s.id in params.slot_ids]
        for slot in problem_slots:
            if slot.start_minute is None:
                if slot.id in params.slot_ids:
                    blocked.add(slot.id)
                continue
            assert slot.end_minute is not None
            for target in targets:
                assert target.start_minute is not None and target.end_minute is not None
                if max(slot.start_minute, target.start_minute) < min(
                    slot.end_minute, target.end_minute
                ):
                    blocked.add(slot.id)
                    break
    elif isinstance(params, PeriodWindowParameters):
        blocked = {
            s.id
            for s in problem_slots
            if s.session in params.session_ids
            and not params.first_period <= s.period <= params.last_period
        }
    return frozenset(blocked)


def build_domains(
    normalized: NormalizedProblem,
    *,
    expanded: bool,
    max_placements: int,
    max_occupancy_terms: int,
) -> DiagnosticDomains:
    """Return tagged candidates; raise the ``prepare`` metadata error or a resource limit."""
    problem = normalized.problem
    requirements = {r.id: r for r in problem.teaching_requirements}
    teachers = {r.id: r for r in problem.teachers}
    classes = {r.id: r for r in problem.classes}
    locks = {lock.occurrence_id: lock for lock in problem.locked_assignments}
    coordinates = {(s.day, s.session, s.period): s for s in problem.time_slots}
    ordered_slots = sorted(problem.time_slots, key=lambda s: (s.day, s.session, s.period))
    placement_rules = [
        (rule.id, scoped, placement_rule_blocks(problem.time_slots, params))
        for rule, scoped, params in enabled_hard(problem)
        if isinstance(params, (AvoidSlotsParameters, PeriodWindowParameters))
    ]
    total_placements = total_terms = 0
    candidates: dict[str, tuple[Candidate, ...]] = {}
    for occurrence in normalized.occurrences:
        req = requirements[occurrence.requirement_id]
        learner, teacher = classes[req.class_ids[0]], teachers[req.teacher_ids[0]]
        lock = locks.get(occurrence.id)
        room_lock = lock.room_id if lock else None
        rooms: list[Room | None] = [None]
        if req.room_required or room_lock is not None:
            typed = [
                r
                for r in sorted(problem.rooms, key=lambda r: r.id)
                if req.required_room_type is None or r.room_type == req.required_room_type
            ]
            locked_view = [r for r in typed if room_lock is None or r.id == room_lock]
            # Same metadata refusal as prepare(): it is an input error, not a conflict.
            if locked_view and (
                learner.size is None or any(r.capacity is None for r in locked_view)
            ):
                raise CoreError(
                    "INPUT_INVALID",
                    "ROOM_METADATA",
                    "Room allocation requires class size and candidate room capacity",
                    resource_ids=(learner.id,),
                    occurrence_ids=(occurrence.id,),
                )
            rooms = [
                r
                for r in typed
                if r.capacity is not None
                and learner.size is not None
                and r.capacity >= learner.size
            ]
        found: list[Candidate] = []
        for start in ordered_slots:
            footprint = tuple(
                coordinates.get((start.day, start.session, start.period + delta))
                for delta in range(occurrence.duration)
            )
            covered = tuple(s for s in footprint if s is not None)
            if len(covered) != occurrence.duration or not all(s.can_teach for s in covered):
                continue
            if normalized.timed and occurrence.duration == 2:
                if covered[0].end_minute != covered[1].start_minute:
                    continue
            base: set[GroupKey] = set()
            if lock and lock.slot_id is not None and start.id != lock.slot_id:
                base.add(("LOCK", occurrence.id))
            if not _available(learner, covered):
                base.add(("CLASS_AVAILABILITY", learner.id))
            if not _available(teacher, covered):
                base.add(("TEACHER_AVAILABILITY", teacher.id))
            for rule_id, scoped, blocked in placement_rules:
                if teacher.id in scoped and any(s.id in blocked for s in covered):
                    base.add(("HARD_PLACEMENT_RULE", rule_id))
            for room in rooms:
                violations = set(base)
                if room is not None:
                    if not _available(room, covered):
                        violations.add(("ROOM_AVAILABILITY", room.id))
                    if room_lock is not None and room.id != room_lock:
                        violations.add(("LOCK", occurrence.id))
                if violations and not expanded:
                    continue
                tokens = tuple(t for s in covered for t in normalized.slot_tokens[s.id])
                total_placements += 1
                total_terms += len(tokens) * (2 + (room is not None))
                if total_placements > max_placements or total_terms > max_occupancy_terms:
                    raise resource_limit()
                found.append(
                    Candidate(
                        Placement(
                            start.id,
                            tuple(s.id for s in covered),
                            room.id if room else None,
                            tokens,
                        ),
                        frozenset(violations),
                    )
                )
        candidates[occurrence.id] = tuple(found)
    return DiagnosticDomains(normalized, candidates, expanded)
