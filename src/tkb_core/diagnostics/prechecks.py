"""Exhaustive diagnostic prechecks (Phase 3B spec §5): counting proofs of infeasibility.

Every check is a necessary condition computed on the clean domains (all constraints on).
Unlike the ``solve()`` precheck, which stops at the first failure, this returns every failing
check, sorted. ``validation.precheck_verifier`` recomputes the same list independently.
"""

from collections import defaultdict

from tkb_core.constraints.hard_variants import enabled_hard
from tkb_core.contracts.diagnostics import PrecheckProof
from tkb_core.diagnostics.domains import DiagnosticDomains
from tkb_core.domain.rule_parameters import (
    DaySpreadParameters,
    MaxDayParameters,
    MaxSessionParameters,
    SubjectDayLimitParameters,
)


def proof_key(p: PrecheckProof) -> tuple[str, str, str, tuple[str, ...], tuple[str, ...]]:
    """Canonical order shared with the independent verifier."""
    return (p.code, p.rule_id or "", p.resource_kind or "", p.resource_ids, p.occurrence_ids)


def greedy_spread(days: set[int], gap: int) -> int:
    """Largest number of start days pairwise at least ``gap`` apart (earliest-first greedy)."""
    count, last = 0, None
    for day in sorted(days):
        if last is None or day - last >= gap:
            count, last = count + 1, day
    return count


def run_prechecks(domains: DiagnosticDomains) -> tuple[PrecheckProof, ...]:
    """Return every failing counting check, sorted by ``proof_key``."""
    normalized = domains.normalized
    problem = normalized.problem
    slots = {s.id: s for s in problem.time_slots}
    coordinates = {(s.day, s.session, s.period): s for s in problem.time_slots}
    requirements = {r.id: r for r in problem.teaching_requirements}
    locks = {lock.occurrence_id: lock for lock in problem.locked_assignments}
    occurrences = normalized.occurrences
    clean = {o.id: domains.clean(o.id) for o in occurrences}
    usable = {o.id: {s for p in clean[o.id] for s in p.slot_ids} for o in occurrences}
    proofs: list[PrecheckProof] = []

    for o in occurrences:
        if not clean[o.id]:
            proofs.append(
                PrecheckProof(
                    code="PC_EMPTY_DOMAIN", occurrence_ids=(o.id,), required=1, available=0
                )
            )

    for kind, index in (("CLASS", 0), ("TEACHER", 1)):
        demand: dict[str, int] = defaultdict(int)
        space: dict[str, set[str]] = defaultdict(set)
        for o in occurrences:
            req = requirements[o.requirement_id]
            resource = (req.class_ids, req.teacher_ids)[index][0]
            demand[resource] += o.duration
            space[resource] |= usable[o.id]
        for resource, needed in demand.items():
            if needed > len(space[resource]):
                proofs.append(
                    PrecheckProof(
                        code="PC_RESOURCE_CAPACITY",
                        resource_kind=kind,
                        resource_ids=(resource,),
                        required=needed,
                        available=len(space[resource]),
                    )
                )

    room_demand: dict[str | None, int] = defaultdict(int)
    room_pairs: dict[str | None, set[tuple[str, str]]] = defaultdict(set)
    for o in occurrences:
        req = requirements[o.requirement_id]
        lock = locks.get(o.id)
        if req.room_required or (lock is not None and lock.room_id is not None):
            room_demand[req.required_room_type] += o.duration
            room_pairs[req.required_room_type] |= {
                (p.room_id, s) for p in clean[o.id] if p.room_id is not None for s in p.slot_ids
            }
    for room_type, needed in room_demand.items():
        if needed > len(room_pairs[room_type]):
            proofs.append(
                PrecheckProof(
                    code="PC_ROOM_CAPACITY",
                    resource_kind="ROOM_TYPE",
                    resource_ids=() if room_type is None else (room_type,),
                    required=needed,
                    available=len(room_pairs[room_type]),
                )
            )
    if len(room_demand) > 1:
        needed = sum(room_demand.values())
        pairs = set().union(*room_pairs.values())
        if needed > len(pairs):
            proofs.append(
                PrecheckProof(
                    code="PC_ROOM_CAPACITY",
                    resource_kind="ROOM_ALL",
                    required=needed,
                    available=len(pairs),
                )
            )

    locked: list[tuple[str, str, str, str | None, frozenset[int]]] = []
    for o in occurrences:
        lock = locks.get(o.id)
        if lock is None or lock.slot_id is None:
            continue
        start = slots[lock.slot_id]
        footprint = [
            coordinates.get((start.day, start.session, start.period + d)) for d in range(o.duration)
        ]
        if any(s is None for s in footprint):
            continue
        tokens = frozenset(
            t for s in footprint if s is not None for t in normalized.slot_tokens[s.id]
        )
        req = requirements[o.requirement_id]
        locked.append((o.id, req.class_ids[0], req.teacher_ids[0], lock.room_id, tokens))
    for i, (first, cls_a, tea_a, room_a, tok_a) in enumerate(locked):
        for second, cls_b, tea_b, room_b, tok_b in locked[i + 1 :]:
            if not tok_a & tok_b:
                continue
            pair = tuple(sorted((first, second)))
            shared = [("CLASS", cls_a) if cls_a == cls_b else None]
            shared.append(("TEACHER", tea_a) if tea_a == tea_b else None)
            shared.append(("ROOM", room_a) if room_a is not None and room_a == room_b else None)
            for item in shared:
                if item is not None:
                    proofs.append(
                        PrecheckProof(
                            code="PC_LOCK_OVERLAP",
                            resource_kind=item[0],
                            resource_ids=(item[1],),
                            occurrence_ids=pair,
                            required=2,
                            available=1,
                        )
                    )

    for rule, scoped, params in enabled_hard(problem):
        if isinstance(params, (MaxDayParameters, MaxSessionParameters)):
            per_teacher: dict[str, list[str]] = defaultdict(list)
            for o in occurrences:
                teacher = requirements[o.requirement_id].teacher_ids[0]
                if teacher in scoped:
                    per_teacher[teacher].append(o.id)
            durations = {o.id: o.duration for o in occurrences}
            for teacher, members in sorted(per_teacher.items()):
                buckets: dict[tuple[int, str], set[str]] = defaultdict(set)
                for member in members:
                    for s in usable[member]:
                        buckets[slots[s].day, slots[s].session].add(s)
                if isinstance(params, MaxDayParameters):
                    by_day: dict[int, set[str]] = defaultdict(set)
                    for (day, _), ids in buckets.items():
                        by_day[day] |= ids
                    capacity = sum(min(params.limit, len(ids)) for ids in by_day.values())
                    code = "PC_HARD_DAY_LOAD"
                else:
                    capacity = sum(
                        min(params.limit, len(ids)) if session in params.session_ids else len(ids)
                        for (_, session), ids in buckets.items()
                    )
                    code = "PC_HARD_SESSION_LOAD"
                needed = sum(durations[m] for m in members)
                if needed > capacity:
                    proofs.append(
                        PrecheckProof(
                            code=code,
                            rule_id=rule.id,
                            resource_kind="TEACHER",
                            resource_ids=(teacher,),
                            required=needed,
                            available=capacity,
                        )
                    )
        elif isinstance(params, SubjectDayLimitParameters):
            classes = set(rule.scope.class_ids) or {c.id for c in problem.classes}
            subjects = set(rule.scope.subject_ids) or {s.id for s in problem.subjects}
            demand_cs: dict[tuple[str, str], int] = defaultdict(int)
            space_cs: dict[tuple[str, str], dict[int, set[str]]] = defaultdict(
                lambda: defaultdict(set)
            )
            for o in occurrences:
                req = requirements[o.requirement_id]
                key = (req.class_ids[0], req.subject_id)
                if key[0] not in classes or key[1] not in subjects:
                    continue
                demand_cs[key] += o.duration
                for s in usable[o.id]:
                    space_cs[key][slots[s].day].add(s)
            for key, needed in sorted(demand_cs.items()):
                capacity = sum(min(params.limit, len(ids)) for ids in space_cs[key].values())
                if needed > capacity:
                    proofs.append(
                        PrecheckProof(
                            code="PC_HARD_SUBJECT_DAY",
                            rule_id=rule.id,
                            resource_kind="CLASS_SUBJECT",
                            resource_ids=key,
                            required=needed,
                            available=capacity,
                        )
                    )
        elif isinstance(params, DaySpreadParameters):
            group = [o for o in occurrences if o.requirement_id in params.requirement_ids]
            days = {slots[p.start_slot_id].day for o in group for p in clean[o.id]}
            capacity = greedy_spread(days, params.min_day_gap)
            if len(group) > capacity:
                proofs.append(
                    PrecheckProof(
                        code="PC_HARD_DAY_SPREAD",
                        rule_id=rule.id,
                        resource_ids=tuple(sorted(params.requirement_ids)),
                        required=len(group),
                        available=capacity,
                    )
                )
    return tuple(sorted(proofs, key=proof_key))
