"""Independently recompute Phase 3B precheck proofs from the raw input.

This module never imports OR-Tools, ``preprocessing``, ``constraints``, ``solver``,
``repair`` or ``diagnostics``. It rebuilds candidate placements with its own slot, lock,
availability, room and S01/S04 logic, recomputes every counting check of spec §5 and
compares the full sorted list with a report. A subset (CORE_SUBSET) is a solver claim and is
not rechecked here; only its fingerprint and the absence of precheck proofs are.
"""

from collections import defaultdict

from tkb_core.contracts.diagnostics import InfeasibilityReport, PrecheckProof
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import AvailableResource, ConstraintConfigV11, TimeSlot
from tkb_core.domain.rule_parameters import (
    AvoidSlotsParameters,
    DaySpreadParameters,
    MaxDayParameters,
    MaxSessionParameters,
    PeriodWindowParameters,
    SubjectDayLimitParameters,
)

_HARD_POLICIES = ("0.2", "0.3", "0.4")
_PARAMETERS: dict[
    str,
    type[AvoidSlotsParameters]
    | type[PeriodWindowParameters]
    | type[MaxSessionParameters]
    | type[MaxDayParameters]
    | type[DaySpreadParameters]
    | type[SubjectDayLimitParameters],
] = {
    "TEACHER_AVOID_SLOTS": AvoidSlotsParameters,
    "TEACHER_PREFERRED_PERIOD_WINDOW": PeriodWindowParameters,
    "TEACHER_MAX_PERIODS_PER_SESSION": MaxSessionParameters,
    "TEACHER_MAX_PERIODS_PER_DAY": MaxDayParameters,
    "SUBJECT_COMPONENT_DAY_SPREAD": DaySpreadParameters,
    "CLASS_SUBJECT_MAX_PERIODS_PER_DAY": SubjectDayLimitParameters,
}
# (start slot ID, covered slot IDs, room ID or None)
_Placement = tuple[str, tuple[str, ...], str | None]


def _overlap(a: TimeSlot, b: TimeSlot) -> bool:
    if a.start_minute is None or b.start_minute is None:
        return a.id == b.id
    assert a.end_minute is not None and b.end_minute is not None
    return a.start_minute < b.end_minute and b.start_minute < a.end_minute


def _free(resource: AvailableResource, covered: list[TimeSlot]) -> bool:
    return resource.available_slot_ids is None or all(
        s.id in resource.available_slot_ids for s in covered
    )


def _key(p: PrecheckProof) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    return (p.code, p.rule_id or "", p.resource_kind or "", p.resource_ids, p.occurrence_ids)


def _spread(days: set[int], gap: int) -> int:
    chosen: list[int] = []
    for day in sorted(days):
        if not chosen or day - chosen[-1] >= gap:
            chosen.append(day)
    return len(chosen)


def recompute_precheck_proofs(problem: ScheduleInput) -> tuple[PrecheckProof, ...]:
    """Return every failing counting check for ``problem``, sorted canonically."""
    slots = {s.id: s for s in problem.time_slots}
    at = {(s.day, s.session, s.period): s for s in problem.time_slots}
    classes = {c.id: c for c in problem.classes}
    teachers = {t.id: t for t in problem.teachers}
    locks = {lock.occurrence_id: lock for lock in problem.locked_assignments}
    timed = any(s.start_minute is not None for s in problem.time_slots)
    config = problem.constraint_config
    rules = []
    if isinstance(config, ConstraintConfigV11) and config.policy_version in _HARD_POLICIES:
        everyone = {t.id for t in problem.teachers}
        for rule in sorted(config.hard, key=lambda r: r.id):
            if rule.enabled:
                params = _PARAMETERS[rule.code].model_validate(rule.parameters)
                rules.append((rule, set(rule.scope.teacher_ids) or everyone, params))
    forbidden: list[tuple[set[str], AvoidSlotsParameters | PeriodWindowParameters]] = [
        (scoped, params)
        for _, scoped, params in rules
        if isinstance(params, (AvoidSlotsParameters, PeriodWindowParameters))
    ]

    def blocked(teacher: str, covered: list[TimeSlot]) -> bool:
        for scoped, params in forbidden:
            if teacher not in scoped:
                continue
            for c in covered:
                if isinstance(params, AvoidSlotsParameters):
                    if any(_overlap(c, slots[t]) for t in params.slot_ids):
                        return True
                elif c.session in params.session_ids and not (
                    params.first_period <= c.period <= params.last_period
                ):
                    return True
        return False

    # occurrence ID -> (requirement, duration)
    occurrences: list[tuple[str, str, int]] = []
    for req in sorted(problem.teaching_requirements, key=lambda r: r.id):
        durations = req.block_durations or (1,) * req.periods_per_cycle
        occurrences += [(f"{req.id}::{i}", req.id, d) for i, d in enumerate(durations, 1)]
    requirements = {r.id: r for r in problem.teaching_requirements}
    placements: dict[str, list[_Placement]] = {}
    for oid, rid, duration in occurrences:
        req = requirements[rid]
        learner, teacher = classes[req.class_ids[0]], teachers[req.teacher_ids[0]]
        lock = locks.get(oid)
        room_lock = lock.room_id if lock else None
        needs_room = req.room_required or room_lock is not None
        room_choices = [
            r
            for r in problem.rooms
            if (req.required_room_type is None or r.room_type == req.required_room_type)
            and (room_lock is None or r.id == room_lock)
            and r.capacity is not None
            and learner.size is not None
            and r.capacity >= learner.size
        ]
        found: list[_Placement] = []
        for start in problem.time_slots:
            if lock and lock.slot_id is not None and lock.slot_id != start.id:
                continue
            covered = [
                at.get((start.day, start.session, start.period + d)) for d in range(duration)
            ]
            if any(c is None for c in covered):
                continue
            cells = [c for c in covered if c is not None]
            if not all(c.can_teach for c in cells):
                continue
            if timed and duration == 2 and cells[0].end_minute != cells[1].start_minute:
                continue
            if not _free(learner, cells) or not _free(teacher, cells):
                continue
            if blocked(teacher.id, cells):
                continue
            ids = tuple(c.id for c in cells)
            if needs_room:
                found += [(start.id, ids, r.id) for r in room_choices if _free(r, cells)]
            else:
                found.append((start.id, ids, None))
        placements[oid] = found
    usable = {oid: {s for _, ids, _ in found for s in ids} for oid, found in placements.items()}
    proofs: list[PrecheckProof] = []

    for oid, found in placements.items():
        if not found:
            proofs.append(
                PrecheckProof(
                    code="PC_EMPTY_DOMAIN", occurrence_ids=(oid,), required=1, available=0
                )
            )
    for kind in ("CLASS", "TEACHER"):
        need: dict[str, int] = defaultdict(int)
        have: dict[str, set[str]] = defaultdict(set)
        for oid, rid, duration in occurrences:
            req = requirements[rid]
            resource = req.class_ids[0] if kind == "CLASS" else req.teacher_ids[0]
            need[resource] += duration
            have[resource] |= usable[oid]
        for resource in need:
            if need[resource] > len(have[resource]):
                proofs.append(
                    PrecheckProof(
                        code="PC_RESOURCE_CAPACITY",
                        resource_kind=kind,
                        resource_ids=(resource,),
                        required=need[resource],
                        available=len(have[resource]),
                    )
                )
    room_need: dict[str | None, int] = defaultdict(int)
    room_have: dict[str | None, set[tuple[str, str]]] = defaultdict(set)
    for oid, rid, duration in occurrences:
        req = requirements[rid]
        lock = locks.get(oid)
        if req.room_required or (lock is not None and lock.room_id is not None):
            room_need[req.required_room_type] += duration
            for _, ids, room in placements[oid]:
                if room is not None:
                    room_have[req.required_room_type] |= {(room, s) for s in ids}
    for room_type, needed in room_need.items():
        if needed > len(room_have[room_type]):
            proofs.append(
                PrecheckProof(
                    code="PC_ROOM_CAPACITY",
                    resource_kind="ROOM_TYPE",
                    resource_ids=() if room_type is None else (room_type,),
                    required=needed,
                    available=len(room_have[room_type]),
                )
            )
    if len(room_need) > 1:
        all_pairs: set[tuple[str, str]] = set()
        for pairs in room_have.values():
            all_pairs |= pairs
        if sum(room_need.values()) > len(all_pairs):
            proofs.append(
                PrecheckProof(
                    code="PC_ROOM_CAPACITY",
                    resource_kind="ROOM_ALL",
                    required=sum(room_need.values()),
                    available=len(all_pairs),
                )
            )
    pinned = []
    for oid, rid, duration in occurrences:
        lock = locks.get(oid)
        if lock is None or lock.slot_id is None:
            continue
        start = slots[lock.slot_id]
        lookup = [at.get((start.day, start.session, start.period + d)) for d in range(duration)]
        if any(c is None for c in lookup):
            continue
        cells = [c for c in lookup if c is not None]
        pinned.append((oid, requirements[rid], lock.room_id, cells))
    for i, (a, req_a, room_a, cells_a) in enumerate(pinned):
        for b, req_b, room_b, cells_b in pinned[i + 1 :]:
            if not any(_overlap(x, y) for x in cells_a for y in cells_b):
                continue
            pair = tuple(sorted((a, b)))
            for kind, left, right in (
                ("CLASS", req_a.class_ids[0], req_b.class_ids[0]),
                ("TEACHER", req_a.teacher_ids[0], req_b.teacher_ids[0]),
                ("ROOM", room_a, room_b),
            ):
                if left is not None and left == right:
                    proofs.append(
                        PrecheckProof(
                            code="PC_LOCK_OVERLAP",
                            resource_kind=kind,
                            resource_ids=(left,),
                            occurrence_ids=pair,
                            required=2,
                            available=1,
                        )
                    )
    for rule, scoped, params in rules:
        if isinstance(params, (MaxDayParameters, MaxSessionParameters)):
            members: dict[str, list[tuple[str, int]]] = defaultdict(list)
            for oid, rid, duration in occurrences:
                teacher_id = requirements[rid].teacher_ids[0]
                if teacher_id in scoped:
                    members[teacher_id].append((oid, duration))
            for teacher_id, mine in sorted(members.items()):
                cells_by: dict[tuple[int, str], set[str]] = defaultdict(set)
                for oid, _ in mine:
                    for s in usable[oid]:
                        cells_by[slots[s].day, slots[s].session].add(s)
                if isinstance(params, MaxDayParameters):
                    days: dict[int, set[str]] = defaultdict(set)
                    for (day, _), cell_ids in cells_by.items():
                        days[day] |= cell_ids
                    cap = sum(min(params.limit, len(day_ids)) for day_ids in days.values())
                    code = "PC_HARD_DAY_LOAD"
                else:
                    cap = 0
                    for (_, session), cell_ids in cells_by.items():
                        cap += (
                            min(params.limit, len(cell_ids))
                            if session in params.session_ids
                            else len(cell_ids)
                        )
                    code = "PC_HARD_SESSION_LOAD"
                needed = sum(d for _, d in mine)
                if needed > cap:
                    proofs.append(
                        PrecheckProof(
                            code=code,
                            rule_id=rule.id,
                            resource_kind="TEACHER",
                            resource_ids=(teacher_id,),
                            required=needed,
                            available=cap,
                        )
                    )
        elif isinstance(params, SubjectDayLimitParameters):
            in_classes = set(rule.scope.class_ids) or set(classes)
            in_subjects = set(rule.scope.subject_ids) or {s.id for s in problem.subjects}
            need_cs: dict[tuple[str, str], int] = defaultdict(int)
            have_cs: dict[tuple[str, str], dict[int, set[str]]] = defaultdict(
                lambda: defaultdict(set)
            )
            for oid, rid, duration in occurrences:
                req = requirements[rid]
                pair_cs = (req.class_ids[0], req.subject_id)
                if pair_cs[0] in in_classes and pair_cs[1] in in_subjects:
                    need_cs[pair_cs] += duration
                    for s in usable[oid]:
                        have_cs[pair_cs][slots[s].day].add(s)
            for pair_cs, needed in sorted(need_cs.items()):
                cap = sum(min(params.limit, len(ids)) for ids in have_cs[pair_cs].values())
                if needed > cap:
                    proofs.append(
                        PrecheckProof(
                            code="PC_HARD_SUBJECT_DAY",
                            rule_id=rule.id,
                            resource_kind="CLASS_SUBJECT",
                            resource_ids=pair_cs,
                            required=needed,
                            available=cap,
                        )
                    )
        elif isinstance(params, DaySpreadParameters):
            group = [oid for oid, rid, _ in occurrences if rid in params.requirement_ids]
            start_days = {slots[start].day for oid in group for start, _, _ in placements[oid]}
            cap = _spread(start_days, params.min_day_gap)
            if len(group) > cap:
                proofs.append(
                    PrecheckProof(
                        code="PC_HARD_DAY_SPREAD",
                        rule_id=rule.id,
                        resource_ids=tuple(sorted(params.requirement_ids)),
                        required=len(group),
                        available=cap,
                    )
                )
    return tuple(sorted(proofs, key=_key))


_MODEL_RULE_CODES = frozenset(
    {
        "TEACHER_MAX_PERIODS_PER_SESSION",
        "TEACHER_MAX_PERIODS_PER_DAY",
        "SUBJECT_COMPONENT_DAY_SPREAD",
        "CLASS_SUBJECT_MAX_PERIODS_PER_DAY",
    }
)
_PLACEMENT_RULE_CODES = frozenset({"TEACHER_AVOID_SLOTS", "TEACHER_PREFERRED_PERIOD_WINDOW"})


def recompute_groups(problem: ScheduleInput, granularity: str) -> set[tuple[str, str]]:
    """Every diagnosable (kind, id) of ``problem`` at ``granularity``, from the raw input."""
    active = [r for r in problem.teaching_requirements if r.occurrence_count > 0]
    locks = {lock.occurrence_id: lock for lock in problem.locked_assignments}
    rooms_used = any(r.room_required for r in active) or any(
        lock.room_id is not None for lock in locks.values()
    )
    groups: set[tuple[str, str]] = set()
    for req in active:
        groups |= {
            ("DEMAND", req.id),
            ("CLASS_OCCUPANCY", req.class_ids[0]),
            ("TEACHER_OCCUPANCY", req.teacher_ids[0]),
        }
    if rooms_used:
        groups |= {("ROOM_OCCUPANCY", room.id) for room in problem.rooms}
    config = problem.constraint_config
    hard = []
    if isinstance(config, ConstraintConfigV11) and config.policy_version in _HARD_POLICIES:
        hard = [r for r in config.hard if r.enabled]
    groups |= {("HARD_RULE", r.id) for r in hard if r.code in _MODEL_RULE_CODES}
    if granularity == "FULL":
        occurrences = {f"{r.id}::{i}" for r in active for i in range(1, r.occurrence_count + 1)}
        classes = {r.class_ids[0] for r in active}
        teachers = {r.teacher_ids[0] for r in active}
        groups |= {("LOCK", o) for o in locks if o in occurrences}
        groups |= {
            ("CLASS_AVAILABILITY", c.id)
            for c in problem.classes
            if c.id in classes and c.available_slot_ids is not None
        }
        groups |= {
            ("TEACHER_AVAILABILITY", t.id)
            for t in problem.teachers
            if t.id in teachers and t.available_slot_ids is not None
        }
        if rooms_used:
            groups |= {
                ("ROOM_AVAILABILITY", room.id)
                for room in problem.rooms
                if room.available_slot_ids is not None
            }
        groups |= {("HARD_PLACEMENT_RULE", r.id) for r in hard if r.code in _PLACEMENT_RULE_CODES}
    return groups


def check_explanation(problem: ScheduleInput, report: InfeasibilityReport) -> tuple[str, ...]:
    """Return mismatch codes; empty means every independently checkable claim holds."""
    problems: list[str] = []
    if report.input_fingerprint != problem.fingerprint():
        return ("STALE_REPORT",)
    if report.status == "RESOURCE_LIMIT":
        # The guard stopped the diagnosis before or while computing prechecks (review F1).
        return ()
    expected = recompute_precheck_proofs(problem)
    declared = tuple(sorted(report.precheck_proofs, key=_key))
    if report.status == "PRECHECK_PROOF":
        if declared != expected:
            problems.append("PRECHECK_MISMATCH")
    elif expected:
        # The pipeline only reaches CP-SAT when no counting proof exists.
        problems.append("PRECHECK_PROOF_MISSING")
    if report.status == "CORE_SUBSET":
        valid = recompute_groups(problem, report.granularity)
        evidence = report.evidence
        named = [*report.subset, *report.unresolved]
        if evidence is not None:
            named += [w.group for w in evidence.minimality_witnesses]
        if any((g.kind, g.id) not in valid for g in named):
            problems.append("UNKNOWN_GROUP")
    return tuple(problems)
