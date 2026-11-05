"""Match previous positions to the new input's placement domains (Phase 3A, spec §2.1)."""

from dataclasses import dataclass

from tkb_core.contracts.repair import ForcedReason, PreviousSchedule, RepairRequest
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.feasibility import PreparedProblem


@dataclass(frozen=True)
class RepairMatching:
    """Per-occurrence classification against the previous schedule.

    ``targets`` maps a matched occurrence to the domain index of its previous placement;
    ``forced`` holds matched occurrences whose previous placement left the domain (a change
    is unavoidable). ``frozen`` occurrences are matched, outside the change scope, and always
    have a target.
    """

    targets: dict[str, int]
    forced: dict[str, ForcedReason]
    frozen: frozenset[str]
    new: tuple[str, ...]
    dropped: tuple[str, ...]
    previous: dict[str, ScheduleAssignment]


def match(
    prepared: PreparedProblem, previous: PreviousSchedule, request: RepairRequest
) -> RepairMatching:
    """Classify by stable occurrence ID; never infer a match from names or content."""
    problem = prepared.normalized.problem
    requirements = {r.id: r for r in problem.teaching_requirements}
    occurrences = {o.id: o for o in prepared.normalized.occurrences}
    locked = {lock.occurrence_id for lock in problem.locked_assignments}
    days = {s.id: s.day for s in problem.time_slots}
    before = {a.occurrence_id: a for a in previous.assignments}
    scope = request.change_scope
    targets: dict[str, int] = {}
    forced: dict[str, ForcedReason] = {}
    frozen: set[str] = set()
    for occurrence_id in sorted(occurrences):
        old = before.get(occurrence_id)
        if old is None:
            continue
        index = next(
            (
                i
                for i, p in enumerate(prepared.domains[occurrence_id])
                if (p.start_slot_id, p.room_id) == (old.slot_id, old.room_id)
            ),
            None,
        )
        if index is None:
            forced[occurrence_id] = "LOCK" if occurrence_id in locked else "DOMAIN"
        else:
            targets[occurrence_id] = index
        if scope is not None:
            req = requirements[occurrences[occurrence_id].requirement_id]
            in_scope = (
                bool(set(req.class_ids) & set(scope.class_ids))
                or bool(set(req.teacher_ids) & set(scope.teacher_ids))
                or req.subject_id in scope.subject_ids
                or days.get(old.slot_id) in scope.days
            )
            if not in_scope:
                frozen.add(occurrence_id)
    invalid = tuple(sorted(frozen & set(forced)))
    if invalid:
        raise CoreError(
            "INPUT_INVALID",
            "REPAIR_FROZEN_TARGET_INVALID",
            "An occurrence outside the change scope cannot keep its previous position",
            occurrence_ids=invalid,
        )
    return RepairMatching(
        targets=targets,
        forced=forced,
        frozen=frozenset(frozen),
        new=tuple(sorted(o for o in occurrences if o not in before)),
        dropped=tuple(sorted(o for o in before if o not in occurrences)),
        previous=before,
    )
