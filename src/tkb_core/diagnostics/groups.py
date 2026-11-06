"""Enumerate diagnostic constraint groups from an input (Phase 3B spec §3.2).

A group is one condition a timetabler understands (a requirement's demand, a teacher's
availability, one hard rule). IDs come from the input; order is (kind, id), independent of
input order. Groups with nothing to constrain are omitted.
"""

from tkb_core.constraints.hard_variants import enabled_hard
from tkb_core.contracts.diagnostics import Granularity, GroupRef
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.rule_parameters import (
    AvoidSlotsParameters,
    DaySpreadParameters,
    MaxDayParameters,
    MaxSessionParameters,
    PeriodWindowParameters,
    SubjectDayLimitParameters,
)

MODEL_RULES = (
    MaxSessionParameters,
    MaxDayParameters,
    DaySpreadParameters,
    SubjectDayLimitParameters,
)
PLACEMENT_RULES = (AvoidSlotsParameters, PeriodWindowParameters)


def enumerate_groups(problem: ScheduleInput, granularity: Granularity) -> tuple[GroupRef, ...]:
    """Return every diagnosable group at ``granularity``, sorted by (kind, id)."""
    active = [r for r in problem.teaching_requirements if r.occurrence_count > 0]
    locks = {lock.occurrence_id: lock for lock in problem.locked_assignments}
    needs_room = any(r.room_required for r in active) or any(
        lock.room_id is not None for lock in locks.values()
    )
    keys: set[tuple[str, str]] = set()
    for req in active:
        keys.add(("DEMAND", req.id))
        keys.add(("CLASS_OCCUPANCY", req.class_ids[0]))
        keys.add(("TEACHER_OCCUPANCY", req.teacher_ids[0]))
    if needs_room:
        keys.update(("ROOM_OCCUPANCY", room.id) for room in problem.rooms)
    hard = enabled_hard(problem)
    keys.update(("HARD_RULE", rule.id) for rule, _, p in hard if isinstance(p, MODEL_RULES))
    if granularity == "FULL":
        used_classes = {r.class_ids[0] for r in active}
        used_teachers = {r.teacher_ids[0] for r in active}
        occurrence_ids = {f"{r.id}::{i}" for r in active for i in range(1, r.occurrence_count + 1)}
        keys.update(("LOCK", o) for o in locks if o in occurrence_ids)
        keys.update(
            ("CLASS_AVAILABILITY", c.id)
            for c in problem.classes
            if c.id in used_classes and c.available_slot_ids is not None
        )
        keys.update(
            ("TEACHER_AVAILABILITY", t.id)
            for t in problem.teachers
            if t.id in used_teachers and t.available_slot_ids is not None
        )
        if needs_room:
            keys.update(
                ("ROOM_AVAILABILITY", room.id)
                for room in problem.rooms
                if room.available_slot_ids is not None
            )
        keys.update(
            ("HARD_PLACEMENT_RULE", rule.id)
            for rule, _, p in hard
            if isinstance(p, PLACEMENT_RULES)
        )
    return tuple(GroupRef(kind=kind, id=i) for kind, i in sorted(keys))
