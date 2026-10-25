"""Recompute validity from raw assignments, never model variables or candidate domains."""

from collections import Counter, defaultdict
from collections.abc import Sequence
from itertools import pairwise

from tkb_core.contracts.capabilities import check_capabilities
from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ValidationReport
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import Diagnostic, ScheduleAssignment


def validate_schedule(
    problem: ScheduleInput, assignments: Sequence[ScheduleAssignment]
) -> ValidationReport:
    """Check all Phase 1 hard semantics using independent Python occupancy logic."""
    violations: list[Diagnostic] = []

    def add(
        code: str,
        message: str,
        resource_ids: tuple[str, ...] = (),
        slot_ids: tuple[str, ...] = (),
        occurrence_ids: tuple[str, ...] = (),
    ) -> None:
        violations.append(
            Diagnostic(
                code=code,
                message=message,
                resource_ids=resource_ids,
                slot_ids=slot_ids,
                occurrence_ids=occurrence_ids,
            )
        )

    try:
        problem = ScheduleInput.model_validate(problem.model_dump(warnings="error"))
        assignments = tuple(
            ScheduleAssignment.model_validate(a.model_dump(warnings="error")) for a in assignments
        )
        check_capabilities(problem)
    except CoreError as exc:
        return ValidationReport(
            valid=False,
            violations=(Diagnostic(code=exc.status.value, message=exc.diagnostics[0].message),),
        )
    except (ValueError, TypeError, AttributeError):
        return ValidationReport(
            valid=False,
            violations=(
                Diagnostic(
                    code="INPUT_INVALID", message="Problem/assignments failed contract revalidation"
                ),
            ),
        )

    slots = {s.id: s for s in problem.time_slots}
    coordinates = {(s.day, s.session, s.period): s for s in problem.time_slots}
    requirements = {r.id: r for r in problem.teaching_requirements}
    learners = {c.id: c for c in problem.classes}
    teachers = {t.id: t for t in problem.teachers}
    rooms = {r.id: r for r in problem.rooms}
    locks = {lock.occurrence_id: lock for lock in problem.locked_assignments}
    timed_count = sum(s.start_minute is not None for s in problem.time_slots)
    timed = bool(timed_count)
    if timed_count not in (0, len(slots)):
        add("INPUT_INVALID", "Mixed timeline modes cannot be verified")
        return ValidationReport(valid=False, violations=tuple(violations))
    if timed:
        sessions: dict[tuple[int, str], list[tuple[int, int, int]]] = defaultdict(list)
        days: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for s in slots.values():
            assert s.start_minute is not None and s.end_minute is not None
            sessions[s.day, s.session].append((s.period, s.start_minute, s.end_minute))
            days[s.day].append((s.start_minute, s.end_minute))
        for group in sessions.values():
            ordered = sorted(group)
            if any(a[2] > b[1] for a, b in pairwise(ordered)):
                add("INPUT_INVALID", "Invalid chronological period order")
        day_ranges = [
            (min(a for a, _ in span), max(b for _, b in span)) for _, span in sorted(days.items())
        ]
        if any(a[1] > b[0] for a, b in pairwise(day_ranges)):
            add("INPUT_INVALID", "Day ranges do not follow cycle-wide minute order")
        if violations:
            return ValidationReport(valid=False, violations=tuple(violations))

    # Check data required for the enabled room scope, even if the proposed schedule omits rooms.
    for room_requirement in requirements.values():
        if not room_requirement.periods_per_cycle:
            continue
        room_locks = [
            lock.room_id
            for lock in locks.values()
            if lock.occurrence_id.rpartition("::")[0] == room_requirement.id
            and lock.room_id is not None
        ]
        needs_unlocked_room = (
            room_requirement.room_required and len(room_locks) < room_requirement.occurrence_count
        )
        candidates = [
            room
            for room in rooms.values()
            if (
                room_requirement.required_room_type is None
                or room.room_type == room_requirement.required_room_type
            )
            and (needs_unlocked_room or room.id in room_locks)
        ]
        if candidates and (
            learners[room_requirement.class_ids[0]].size is None
            or any(r.capacity is None for r in candidates)
        ):
            add("INPUT_INVALID", "Room allocation requires class size and candidate room capacity")
    if violations:
        return ValidationReport(valid=False, violations=tuple(violations))

    expected_total = sum(req.occurrence_count for req in requirements.values())
    if len(assignments) != expected_total:
        add("OCCURRENCE_COUNT", "Assignment count does not match required occurrence count")
    seen: set[str] = set()
    observed: Counter[str] = Counter()
    symbolic: dict[tuple[str, str, str], str] = {}
    intervals: dict[tuple[str, str], list[tuple[int, int, str]]] = defaultdict(list)
    for a in assignments:
        if a.occurrence_id in seen:
            add(
                "DUPLICATE_OCCURRENCE",
                "Occurrence is assigned more than once",
                occurrence_ids=(a.occurrence_id,),
            )
            continue
        seen.add(a.occurrence_id)
        requirement_id, sep, ordinal = a.occurrence_id.rpartition("::")
        req = requirements.get(requirement_id)
        if (
            not sep
            or req is None
            or not ordinal.isascii()
            or not ordinal.isdecimal()
            or len(ordinal) > 20
        ):
            add(
                "UNKNOWN_OCCURRENCE",
                "Assignment references an unknown occurrence",
                occurrence_ids=(a.occurrence_id,),
            )
            continue
        number = int(ordinal)
        if str(number) != ordinal or not 1 <= number <= req.occurrence_count:
            add(
                "UNKNOWN_OCCURRENCE",
                "Occurrence ordinal is outside its requirement",
                occurrence_ids=(a.occurrence_id,),
            )
            continue
        observed[req.id] += 1
        duration = req.block_durations[number - 1] if req.block_durations is not None else 1
        if a.class_ids != req.class_ids or a.teacher_ids != req.teacher_ids:
            add(
                "PARTICIPANTS",
                "Assignment participants differ from teaching requirement",
                occurrence_ids=(a.occurrence_id,),
            )
        start = slots.get(a.slot_id)
        if start is None:
            add("UNKNOWN_SLOT", "Assignment references an unknown slot", slot_ids=(a.slot_id,))
            continue
        footprint = [
            coordinates.get((start.day, start.session, start.period + d)) for d in range(duration)
        ]
        if any(s is None for s in footprint):
            add(
                "BLOCK_BOUNDARY",
                "Block extends beyond consecutive periods in its session",
                occurrence_ids=(a.occurrence_id,),
            )
            continue
        covered = [s for s in footprint if s is not None]
        if any(not s.can_teach for s in covered):
            add(
                "FORBIDDEN_SLOT",
                "Block occupies a non-teaching slot",
                occurrence_ids=(a.occurrence_id,),
            )
        if timed and duration == 2 and covered[0].end_minute != covered[1].start_minute:
            add(
                "BLOCK_BREAK",
                "Block crosses a positive time gap",
                occurrence_ids=(a.occurrence_id,),
            )
        learner, teacher = learners[req.class_ids[0]], teachers[req.teacher_ids[0]]
        resources = [("CLASS", learner), ("TEACHER", teacher)]
        lock = locks.get(a.occurrence_id)
        needs_room = req.room_required or bool(lock and lock.room_id is not None)
        if lock and (
            (lock.slot_id is not None and a.slot_id != lock.slot_id)
            or (lock.room_id is not None and a.room_id != lock.room_id)
        ):
            add(
                "LOCK_MISMATCH",
                "Assignment violates a time or room lock",
                occurrence_ids=(a.occurrence_id,),
            )
        if needs_room and a.room_id is None:
            add(
                "ROOM_REQUIRED",
                "Occurrence requires a physical room",
                occurrence_ids=(a.occurrence_id,),
            )
        elif not needs_room and a.room_id is not None:
            add(
                "ROOM_UNEXPECTED",
                "Occurrence has no room allocation in this scope",
                occurrence_ids=(a.occurrence_id,),
            )
        if a.room_id is not None:
            room = rooms.get(a.room_id)
            if room is None:
                add(
                    "UNKNOWN_ROOM",
                    "Assignment references an unknown room",
                    resource_ids=(a.room_id,),
                )
            else:
                resources.append(("ROOM", room))
                if req.required_room_type is not None and room.room_type != req.required_room_type:
                    add(
                        "ROOM_TYPE",
                        "Room type does not satisfy the requirement",
                        resource_ids=(room.id,),
                    )
                if room.capacity is None or learner.size is None:
                    add("INPUT_INVALID", "Capacity check requires room capacity and learner size")
                elif room.capacity < learner.size:
                    add(
                        "ROOM_CAPACITY",
                        "Room capacity is smaller than the assigned class",
                        resource_ids=(room.id,),
                    )
        for kind, resource in resources:
            if resource.available_slot_ids is not None and any(
                s.id not in resource.available_slot_ids for s in covered
            ):
                add(
                    "AVAILABILITY",
                    "Resource is unavailable for part of the block",
                    resource_ids=(resource.id,),
                    occurrence_ids=(a.occurrence_id,),
                )
            if timed:
                begin, end = covered[0].start_minute, covered[-1].end_minute
                assert begin is not None and end is not None
                intervals[kind, resource.id].append((begin, end, a.occurrence_id))
            else:
                for s in covered:
                    key = kind, resource.id, s.id
                    if key in symbolic:
                        add(
                            f"{kind}_OVERLAP",
                            "Resource is occupied by overlapping occurrences",
                            resource_ids=(resource.id,),
                            slot_ids=(s.id,),
                            occurrence_ids=(symbolic[key], a.occurrence_id),
                        )
                    symbolic[key] = a.occurrence_id
    for requirement_id, req in requirements.items():
        if observed[requirement_id] != req.occurrence_count:
            add("OCCURRENCE_COUNT", "Requirement has missing or excess assignments")
    for (kind, resource_id), spans in intervals.items():
        farthest_end = -1
        farthest_occurrence = ""
        for begin, end, occurrence_id in sorted(spans):
            if begin < farthest_end:
                add(
                    f"{kind}_OVERLAP",
                    "Resource intervals overlap in physical time",
                    resource_ids=(resource_id,),
                    occurrence_ids=(farthest_occurrence, occurrence_id),
                )
            if end > farthest_end:
                farthest_end, farthest_occurrence = end, occurrence_id
    return ValidationReport(valid=not violations, violations=tuple(violations))
