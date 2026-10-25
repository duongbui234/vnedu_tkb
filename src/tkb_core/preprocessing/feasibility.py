"""Construct eligible placements and check necessary resource/lock conditions."""

from collections import defaultdict
from dataclasses import dataclass

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import AvailableResource, Room, TimeSlot
from tkb_core.preprocessing.normalize import NormalizedProblem, normalize, resource_limit
from tkb_core.solver.options import SolveOptions


@dataclass(frozen=True)
class Placement:
    """One indivisible start/room choice, including every occupied token."""

    start_slot_id: str
    slot_ids: tuple[str, ...]
    room_id: str | None
    tokens: tuple[int, ...]


@dataclass(frozen=True)
class PreparedProblem:
    """Validated snapshot and complete, untruncated placement domains."""

    normalized: NormalizedProblem
    domains: dict[str, tuple[Placement, ...]]


def _available(resource: AvailableResource, slots: tuple[TimeSlot, ...]) -> bool:
    return resource.available_slot_ids is None or all(
        s.id in resource.available_slot_ids for s in slots
    )


def prepare(problem: ScheduleInput, options: SolveOptions | None = None) -> PreparedProblem:
    """Return a model-ready problem or a classified failure with diagnostic context."""
    options = SolveOptions() if options is None else options
    normalized = normalize(problem, options)
    problem = normalized.problem
    requirements = {r.id: r for r in problem.teaching_requirements}
    teachers = {r.id: r for r in problem.teachers}
    classes = {r.id: r for r in problem.classes}
    locks = {lock.occurrence_id: lock for lock in problem.locked_assignments}
    coordinates = {(s.day, s.session, s.period): s for s in problem.time_slots}
    domains: dict[str, tuple[Placement, ...]] = {}
    fixed: dict[tuple[str, str, int], str] = {}
    resource_demand: dict[tuple[str, str], int] = defaultdict(int)
    resource_slots: dict[tuple[str, str], set[str]] = defaultdict(set)
    room_demand = 0
    room_slots: set[tuple[str, str]] = set()
    total_placements = total_terms = 0
    for occurrence in normalized.occurrences:
        req = requirements[occurrence.requirement_id]
        learner, teacher = classes[req.class_ids[0]], teachers[req.teacher_ids[0]]
        lock = locks.get(occurrence.id)
        room_lock = lock.room_id if lock else None
        needs_room = req.room_required or room_lock is not None
        rooms: list[Room | None] = [None]
        if needs_room:
            rooms = [
                r
                for r in sorted(problem.rooms, key=lambda r: r.id)
                if (room_lock is None or r.id == room_lock)
                and (req.required_room_type is None or r.room_type == req.required_room_type)
            ]
            if rooms and (
                learner.size is None or any(r is not None and r.capacity is None for r in rooms)
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
                for r in rooms
                if r is not None
                and r.capacity is not None
                and learner.size is not None
                and r.capacity >= learner.size
            ]
            if room_lock is not None and not rooms:
                raise CoreError(
                    "INPUT_INVALID",
                    "LOCK_CONFLICT",
                    "Locked room is incompatible with the requirement",
                    occurrence_ids=(occurrence.id,),
                )
        candidates: list[Placement] = []
        for start in sorted(problem.time_slots, key=lambda s: (s.day, s.session, s.period)):
            if lock and lock.slot_id is not None and start.id != lock.slot_id:
                continue
            footprint = tuple(
                coordinates.get((start.day, start.session, start.period + delta))
                for delta in range(occurrence.duration)
            )
            valid_slots = tuple(s for s in footprint if s is not None)
            valid = len(valid_slots) == occurrence.duration and all(
                s.can_teach for s in valid_slots
            )
            valid = valid and _available(learner, valid_slots) and _available(teacher, valid_slots)
            if normalized.timed and occurrence.duration == 2 and len(valid_slots) == 2:
                valid = valid and valid_slots[0].end_minute == valid_slots[1].start_minute
            if not valid:
                if lock and lock.slot_id is not None:
                    raise CoreError(
                        "INPUT_INVALID",
                        "LOCK_CONFLICT",
                        "Locked block violates calendar or availability",
                        slot_ids=(start.id,),
                        occurrence_ids=(occurrence.id,),
                    )
                continue
            for room in rooms:
                if room is not None and not _available(room, valid_slots):
                    if room_lock is not None and lock and lock.slot_id is not None:
                        raise CoreError(
                            "INPUT_INVALID",
                            "LOCK_CONFLICT",
                            "Locked room is unavailable for the full block",
                            occurrence_ids=(occurrence.id,),
                        )
                    continue
                tokens = tuple(t for slot in valid_slots for t in normalized.slot_tokens[slot.id])
                total_placements += 1
                total_terms += len(tokens) * (2 + (room is not None))
                if (
                    total_placements > options.max_placements
                    or total_terms > options.max_occupancy_terms
                ):
                    raise resource_limit()
                candidates.append(
                    Placement(
                        start.id,
                        tuple(s.id for s in valid_slots),
                        room.id if room else None,
                        tokens,
                    )
                )
        if not candidates:
            raise CoreError(
                "INFEASIBLE",
                "EMPTY_DOMAIN",
                "No eligible placement remains for an occurrence",
                occurrence_ids=(occurrence.id,),
            )
        domains[occurrence.id] = tuple(candidates)
        if lock and lock.slot_id is not None:
            actors = [("class", learner.id), ("teacher", teacher.id)]
            if room_lock is not None:
                actors.append(("room", room_lock))
            for kind, resource in actors:
                for token in candidates[0].tokens:
                    key = kind, resource, token
                    if key in fixed:
                        raise CoreError(
                            "INPUT_INVALID",
                            "LOCK_CONFLICT",
                            "Locked assignments overlap on a resource",
                            resource_ids=(resource,),
                            occurrence_ids=(fixed[key], occurrence.id),
                        )
                    fixed[key] = occurrence.id
        for actor in (("class", learner.id), ("teacher", teacher.id)):
            resource_demand[actor] += occurrence.duration
            resource_slots[actor].update(s for p in candidates for s in p.slot_ids)
        if needs_room:
            room_demand += occurrence.duration
            room_slots.update(
                (p.room_id, s) for p in candidates if p.room_id is not None for s in p.slot_ids
            )
    for actor, demand in resource_demand.items():
        if demand > len(resource_slots[actor]):
            raise CoreError(
                "INFEASIBLE",
                "RESOURCE_CAPACITY",
                "Demand exceeds eligible resource slots",
                resource_ids=(actor[1],),
            )
    if room_demand > len(room_slots):
        raise CoreError(
            "INFEASIBLE", "ROOM_CAPACITY", "Required room time exceeds candidate room slots"
        )
    return PreparedProblem(normalized, domains)
