"""Independent recomputation of repair counts; never imports a solver, compiler or domain.

It reads only the new input, the previous schedule, the request and the returned
assignments. Whether a previous position was still feasible (a "forced" change) is a
solver-side classification and is checked only for being a real change.
"""

from typing import Literal

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.repair import PreviousSchedule, RepairReport, RepairRequest
from tkb_core.domain.models import DomainModel, ScheduleAssignment

Change = tuple[str, str, str | None, str, str | None]


class RepairEvaluation(DomainModel):
    status: Literal["OK", "INPUT_INVALID"]
    reason: str | None = None
    matched: int = 0
    new: int = 0
    dropped: int = 0
    changed: int = 0
    slot_changes: int = 0
    room_only_changes: int = 0
    unchanged: int = 0
    frozen: int = 0
    changes: tuple[Change, ...] = ()
    new_occurrence_ids: tuple[str, ...] = ()
    dropped_occurrence_ids: tuple[str, ...] = ()
    frozen_violations: tuple[str, ...] = ()
    max_changes_ok: bool = True


def evaluate_repair(
    problem: ScheduleInput,
    previous: PreviousSchedule,
    request: RepairRequest,
    assignments: tuple[ScheduleAssignment, ...],
) -> RepairEvaluation:
    """Diff the returned schedule against the previous one, in occurrences."""
    owners = {}
    for req in problem.teaching_requirements:
        for ordinal in range(1, req.occurrence_count + 1):
            owners[f"{req.id}::{ordinal}"] = req
    chosen: dict[str, ScheduleAssignment] = {}
    for a in assignments:
        if a.occurrence_id not in owners or a.occurrence_id in chosen:
            return RepairEvaluation(status="INPUT_INVALID", reason="UNKNOWN_OR_DUPLICATE")
        chosen[a.occurrence_id] = a
    if set(chosen) != set(owners):
        return RepairEvaluation(status="INPUT_INVALID", reason="SCHEDULE_INCOMPLETE")
    before = {a.occurrence_id: a for a in previous.assignments}
    days = {s.id: s.day for s in problem.time_slots}
    scope = request.change_scope
    changes: list[Change] = []
    frozen: list[str] = []
    violations: list[str] = []
    for occurrence in sorted(owners):
        if occurrence not in before:
            continue
        old, new = before[occurrence], chosen[occurrence]
        moved = (old.slot_id, old.room_id) != (new.slot_id, new.room_id)
        if moved:
            changes.append((occurrence, old.slot_id, old.room_id, new.slot_id, new.room_id))
        if scope is not None:
            req = owners[occurrence]
            in_scope = (
                bool(set(req.class_ids) & set(scope.class_ids))
                or bool(set(req.teacher_ids) & set(scope.teacher_ids))
                or req.subject_id in scope.subject_ids
                or days.get(old.slot_id) in scope.days
            )
            if not in_scope:
                frozen.append(occurrence)
                if moved:
                    violations.append(occurrence)
    matched = sum(o in before for o in owners)
    slot = sum(c[1] != c[3] for c in changes)
    return RepairEvaluation(
        status="OK",
        matched=matched,
        new=len(owners) - matched,
        dropped=sum(o not in owners for o in before),
        changed=len(changes),
        slot_changes=slot,
        room_only_changes=len(changes) - slot,
        unchanged=matched - len(changes),
        frozen=len(frozen),
        changes=tuple(changes),
        new_occurrence_ids=tuple(sorted(o for o in owners if o not in before)),
        dropped_occurrence_ids=tuple(sorted(o for o in before if o not in owners)),
        frozen_violations=tuple(violations),
        max_changes_ok=request.max_changes is None or len(changes) <= request.max_changes,
    )


def check_report(evaluation: RepairEvaluation, report: RepairReport) -> tuple[str, ...]:
    """Return mismatch codes between a declared report and the recomputation."""
    if evaluation.status != "OK":
        return ("EVALUATION_FAILED",)
    problems: list[str] = []
    counts = (
        "matched",
        "new",
        "dropped",
        "changed",
        "slot_changes",
        "room_only_changes",
        "unchanged",
        "frozen",
    )
    if any(getattr(evaluation, c) != getattr(report, c) for c in counts) or (
        set(evaluation.new_occurrence_ids) != set(report.new_occurrence_ids)
        or set(evaluation.dropped_occurrence_ids) != set(report.dropped_occurrence_ids)
    ):
        problems.append("COUNTS")
    declared = {
        (c.occurrence_id, c.previous_slot_id, c.previous_room_id, c.slot_id, c.room_id)
        for c in report.changes
    }
    if declared != set(evaluation.changes):
        problems.append("CHANGES")
    if evaluation.frozen_violations:
        problems.append("FROZEN_VIOLATION")
    if not evaluation.max_changes_ok:
        problems.append("MAX_CHANGES")
    return tuple(problems)
