"""Exhaustive S03 bound oracle; hard validity and loads are rebuilt from raw fixtures."""

import json
from collections import Counter
from collections.abc import Callable
from itertools import product
from math import prod
from typing import Any

import pytest

from tkb_core.constraints.s03_bounds import derive_s03_bounds
from tkb_core.constraints.soft import compile_soft
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver.model_builder import build_model
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score

MAX_COMBINATIONS = 10_000
MAX_TOTAL_COMBINATIONS = 120_000

Data = dict[str, Any]
Candidate = tuple[str, str | None, tuple[dict[str, Any], ...]]
Occurrence = tuple[str, dict[str, Any], list[Candidate]]


def _sym(day: int, session: str, period: int) -> dict[str, Any]:
    return {"id": f"{day}-{session}-{period}", "day": day, "session": session, "period": period}


def _tim(day: int, session: str, period: int, start: int, end: int) -> dict[str, Any]:
    return {
        "id": f"{day}{session}{period}",
        "day": day,
        "session": session,
        "period": period,
        "start_minute": start,
        "end_minute": end,
    }


def _req(rid: str, cls: str, teacher: str, blocks: list[int], **extra: Any) -> dict[str, Any]:
    return {
        "id": rid,
        "class_ids": [cls],
        "teacher_ids": [teacher],
        "subject_id": "sub",
        "periods_per_cycle": sum(blocks),
        "block_durations": blocks,
        **extra,
    }


def _case(
    slots: list[dict[str, Any]],
    reqs: list[dict[str, Any]],
    *,
    teachers: list[Any],
    classes: list[Any],
    rooms: list[dict[str, Any]] | None = None,
    locks: list[dict[str, Any]] | None = None,
    scope: list[str] | None = None,
    limit: int = 1,
) -> Data:
    return {
        "schema_version": "1.1",
        "school": {"school_id": "demo", "academic_year": "demo", "term": "demo"},
        "time_slots": slots,
        "classes": [c if isinstance(c, dict) else {"id": c} for c in classes],
        "teachers": [t if isinstance(t, dict) else {"id": t} for t in teachers],
        "subjects": [{"id": "sub"}],
        "rooms": rooms or [],
        "manage_rooms": bool(rooms),
        "teaching_requirements": reqs,
        "locked_assignments": locks or [],
        "constraint_config": {
            "policy_version": "0.1",
            "hard": [],
            "soft": [
                {
                    "id": "s03",
                    "code": "TEACHER_MAX_PERIODS_PER_DAY",
                    "scope": {"teacher_ids": scope or []},
                    "parameters": {"limit": limit},
                    "weight": 3,
                    "priority": 1,
                }
            ],
        },
    }


def sym_sparse_days() -> Data:
    slots = [_sym(d, "AM", p) for d, p in [(11, 1), (11, 2), (7, 2), (7, 1), (2, 2), (2, 1)]]
    u = {"id": "u", "available_slot_ids": ["2-AM-1", "2-AM-2", "7-AM-1", "7-AM-2"]}
    reqs = [_req("r2", "c2", "u", [2, 1]), _req("r1", "c1", "t", [1, 1, 1])]
    return _case(slots, reqs, teachers=["t", u], classes=["c1", "c2"])


def sym_multi_scope() -> Data:
    slots = [_sym(2, "AM", p) for p in (1, 2, 3)] + [_sym(7, "AM", p) for p in (1, 2)]
    reqs = [_req("r2", "c2", "u", [1, 1]), _req("r1", "c1", "t", [1, 1, 1])]
    return _case(slots, reqs, teachers=["t", "u", "v"], classes=["c1", "c2"], scope=["u", "t"])


def sym_locks() -> Data:
    slots = [_sym(d, "AM", p) for d in (2, 7) for p in (1, 2)]
    rooms = [{"id": "R1", "capacity": 30}, {"id": "R2", "capacity": 30}]
    reqs = [_req("r1", "c1", "t", [1, 1, 1], room_required=True), _req("r2", "c2", "u", [1, 1])]
    locks = [
        {"occurrence_id": "r1::1", "slot_id": "2-AM-1"},
        {"occurrence_id": "r1::2", "slot_id": "7-AM-1", "room_id": "R2"},
        {"occurrence_id": "r1::3", "room_id": "R1"},
    ]
    classes = [{"id": "c1", "size": 20}, {"id": "c2", "size": 20}]
    return _case(slots, reqs, teachers=["t", "u"], classes=classes, rooms=rooms, locks=locks)


def sym_locked_double() -> Data:
    slots = [_sym(2, "AM", p) for p in (1, 2, 3)] + [_sym(2, "PM", 1)]
    slots += [_sym(11, "AM", p) for p in (1, 2)]
    reqs = [_req("r1", "c1", "t", [2, 1, 1]), _req("r2", "c2", "u", [2])]
    locks = [{"occurrence_id": "r1::1", "slot_id": "2-AM-2"}]
    return _case(
        slots,
        reqs,
        teachers=["t", "u"],
        classes=["c1", "c2"],
        locks=locks,
        scope=["t", "u"],
        limit=0,
    )


def sym_room_alternatives() -> Data:
    slots = [_sym(d, "AM", p) for d in (2, 7) for p in (1, 2)]
    rooms = [
        {"id": "R1", "capacity": 40, "room_type": "lab"},
        {
            "id": "R2",
            "capacity": 25,
            "room_type": "lab",
            "available_slot_ids": ["7-AM-1", "7-AM-2"],
        },
    ]
    reqs = [
        _req("r1", "c1", "t", [1, 1], room_required=True, required_room_type="lab"),
        _req("r2", "c2", "u", [2], room_required=True, required_room_type="lab"),
        _req("r3", "c2", "t", [1]),
    ]
    classes = [{"id": "c1", "size": 30}, {"id": "c2", "size": 20}]
    return _case(slots, reqs, teachers=["t", "u"], classes=classes, rooms=rooms)


def sym_fixed_zero() -> Data:
    slots = [_sym(2, "AM", p) for p in (1, 2, 3)] + [_sym(7, "AM", 1)]
    reqs = [_req("r1", "c1", "t", [1, 1]), _req("r2", "c2", "u", [1, 1])]
    locks = [
        {"occurrence_id": "r1::1", "slot_id": "2-AM-1"},
        {"occurrence_id": "r1::2", "slot_id": "2-AM-2"},
    ]
    return _case(slots, reqs, teachers=["t", "u"], classes=["c1", "c2"], locks=locks)


def tim_overlap() -> Data:
    slots = [
        _tim(2, "A", 1, 0, 45),
        _tim(2, "A", 2, 45, 90),
        _tim(2, "B", 1, 30, 75),
        _tim(2, "B", 2, 80, 120),
        _tim(7, "A", 1, 1000, 1045),
        _tim(7, "A", 2, 1045, 1090),
    ]
    reqs = [_req("r1", "c1", "t", [1, 1, 1]), _req("r2", "c2", "u", [1, 1])]
    return _case(slots, reqs, teachers=["t", "u"], classes=["c1", "c2"])


def tim_double_gap() -> Data:
    slots = [
        _tim(2, "A", 1, 0, 45),
        _tim(2, "A", 2, 50, 95),
        _tim(2, "B", 1, 100, 145),
        _tim(2, "B", 2, 145, 190),
        _tim(11, "A", 1, 2000, 2045),
        _tim(11, "A", 2, 2045, 2090),
    ]
    reqs = [
        _req("r1", "c1", "t", [2, 1]),
        _req("r2", "c2", "u", [2]),
        _req("r3", "c2", "t", [1]),
    ]
    return _case(slots, reqs, teachers=["t", "u"], classes=["c1", "c2"])


def tim_sparse_scope() -> Data:
    slots = [
        _tim(11, "A", 2, 935, 980),
        _tim(11, "A", 1, 900, 930),
        _tim(7, "A", 1, 500, 560),
        _tim(2, "A", 2, 40, 80),
        _tim(2, "A", 1, 0, 40),
    ]
    t = {"id": "t", "available_slot_ids": ["2A1", "2A2", "7A1"]}
    reqs = [_req("r2", "c2", "u", [1, 1]), _req("r1", "c1", "t", [1, 1, 1])]
    return _case(slots, reqs, teachers=[t, "u"], classes=["c1", "c2"], scope=["t"])


def tim_locked_double() -> Data:
    slots = [_tim(2, "A", p, 45 * (p - 1), 45 * p) for p in (1, 2, 3)]
    slots += [_tim(7, "A", 1, 1000, 1045), _tim(7, "A", 2, 1045, 1090)]
    reqs = [_req("r1", "c1", "t", [2, 1, 1]), _req("r2", "c2", "u", [1, 1])]
    locks = [
        {"occurrence_id": "r1::1", "slot_id": "2A1"},
        {"occurrence_id": "r2::2", "slot_id": "7A2"},
    ]
    return _case(
        slots, reqs, teachers=["t", "u"], classes=["c1", "c2"], locks=locks, scope=["t", "u"]
    )


def tim_room_only() -> Data:
    slots = [
        _tim(2, "A", 1, 0, 45),
        _tim(2, "A", 2, 45, 90),
        _tim(2, "B", 1, 60, 100),
        _tim(7, "A", 1, 1000, 1045),
    ]
    rooms = [
        {"id": "R1", "capacity": 30},
        {"id": "R2", "capacity": 30, "available_slot_ids": ["2A2", "2B1", "7A1"]},
    ]
    reqs = [
        _req("r1", "c1", "t", [1, 1], room_required=True),
        _req("r2", "c2", "u", [1], room_required=True),
        _req("r3", "c2", "t", [1]),
    ]
    locks = [{"occurrence_id": "r1::1", "room_id": "R2"}]
    classes = [{"id": "c1", "size": 25}, {"id": "c2", "size": 25}]
    return _case(slots, reqs, teachers=["t", "u"], classes=classes, rooms=rooms, locks=locks)


def tim_minutes_zero() -> Data:
    slots = [
        _tim(2, "A", 1, 0, 30),
        _tim(2, "A", 2, 30, 90),
        _tim(2, "A", 3, 90, 100),
        _tim(7, "A", 1, 1000, 1050),
        _tim(7, "A", 2, 1050, 1055),
    ]
    reqs = [_req("r1", "c1", "t", [1, 1]), _req("r2", "c2", "u", [2])]
    locks = [{"occurrence_id": "r2::1", "slot_id": "7A1"}]
    return _case(slots, reqs, teachers=["t", "u"], classes=["c1", "c2"], locks=locks, limit=0)


CORPUS: dict[str, Callable[[], Data]] = {
    f.__name__: f
    for f in (
        sym_sparse_days,
        sym_multi_scope,
        sym_locks,
        sym_locked_double,
        sym_room_alternatives,
        sym_fixed_zero,
        tim_overlap,
        tim_double_gap,
        tim_sparse_scope,
        tim_locked_double,
        tim_room_only,
        tim_minutes_zero,
    )
}


def candidates(data: Data) -> tuple[bool, list[Occurrence]]:
    """Enumerate start/room choices from raw JSON, without prepare or placements."""
    slots = data["time_slots"]
    timed = any("start_minute" in s for s in slots)
    coords = {(s["day"], s["session"], s["period"]): s for s in slots}
    teachers = {t["id"]: t for t in data["teachers"]}
    classes = {c["id"]: c for c in data["classes"]}
    rooms = sorted(data["rooms"], key=lambda r: r["id"])
    locks = {lock["occurrence_id"]: lock for lock in data["locked_assignments"]}

    def available(resource: dict[str, Any], covered: tuple[dict[str, Any], ...]) -> bool:
        allowed = resource.get("available_slot_ids")
        return allowed is None or all(s["id"] in allowed for s in covered)

    occurrences: list[Occurrence] = []
    for req in sorted(data["teaching_requirements"], key=lambda r: r["id"]):
        teacher, learner = teachers[req["teacher_ids"][0]], classes[req["class_ids"][0]]
        for ordinal, duration in enumerate(req["block_durations"], 1):
            oid = f"{req['id']}::{ordinal}"
            lock = locks.get(oid, {})
            choices: list[Candidate] = []
            for start in slots:
                if lock.get("slot_id") not in (None, start["id"]):
                    continue
                found = [
                    coords.get((start["day"], start["session"], start["period"] + i))
                    for i in range(duration)
                ]
                if any(s is None or not s.get("can_teach", True) for s in found):
                    continue
                covered = tuple(s for s in found if s is not None)
                if (
                    timed
                    and duration == 2
                    and covered[0]["end_minute"] != covered[1]["start_minute"]
                ):
                    continue
                if not (available(teacher, covered) and available(learner, covered)):
                    continue
                room_ids: list[str | None] = [None]
                if req.get("room_required") or lock.get("room_id"):
                    room_ids = [
                        r["id"]
                        for r in rooms
                        if lock.get("room_id") in (None, r["id"])
                        and req.get("required_room_type") in (None, r.get("room_type"))
                        and r["capacity"] >= learner["size"]
                        and available(r, covered)
                    ]
                choices.extend((start["id"], room_id, covered) for room_id in room_ids)
            occurrences.append((oid, req, choices))
    return timed, occurrences


def hard_valid(selection: tuple[tuple[str, dict[str, Any], Candidate], ...], timed: bool) -> bool:
    """Class/teacher/room exclusivity by slot ID or overlapping physical minutes."""
    used: list[tuple[tuple[str, str], dict[str, Any]]] = []
    for _, req, (_, room_id, covered) in selection:
        resources = [("class", req["class_ids"][0]), ("teacher", req["teacher_ids"][0])]
        if room_id is not None:
            resources.append(("room", room_id))
        for resource in resources:
            for slot in covered:
                for other_resource, other in used:
                    if other_resource != resource:
                        continue
                    if timed:
                        if (
                            slot["start_minute"] < other["end_minute"]
                            and other["start_minute"] < slot["end_minute"]
                        ):
                            return False
                    elif slot["id"] == other["id"]:
                        return False
            used.extend((resource, slot) for slot in covered)
    return True


def _rule(data: Data) -> tuple[frozenset[str], int]:
    rule = data["constraint_config"]["soft"][0]
    scope = rule["scope"]["teacher_ids"] or [t["id"] for t in data["teachers"]]
    return frozenset(scope), rule["parameters"]["limit"]


def test_corpus_size_is_within_exhaustive_ceiling() -> None:
    total = 0
    for make in CORPUS.values():
        _, occurrences = candidates(make())
        combinations = prod(len(c) for _, _, c in occurrences)
        assert 0 < combinations <= MAX_COMBINATIONS
        assert len(occurrences) <= 6
        total += combinations
    assert total <= MAX_TOTAL_COMBINATIONS
    assert len(CORPUS) == 12
    assert sum(name.startswith("tim_") for name in CORPUS) == 6


@pytest.mark.parametrize("name", sorted(CORPUS))
def test_bounds_keep_every_hard_valid_schedule(name: str) -> None:
    data = CORPUS[name]()
    timed, occurrences = candidates(data)
    combinations = prod(len(c) for _, _, c in occurrences)
    assert 0 < combinations <= MAX_COMBINATIONS
    scope, limit = _rule(data)
    problem = ScheduleInput.model_validate(data)
    prepared = prepare(problem)
    decision = derive_s03_bounds(prepared, scope, limit)
    assert decision.reason is None and decision.bounds is not None
    bounds = decision.bounds
    days = {s["day"] for s in data["time_slots"]}
    assert [(b.teacher_id, b.day) for b in bounds.days] == sorted(
        (t, d) for t in scope for d in days
    )
    built = build_model(prepared)
    old_raw_bound = compile_soft(prepared, built).rules[0].raw_upper_bound
    old_domains = {v.name: tuple(v.domain) for v in built.model.proto.variables if v.name}

    valid = rejected = 0
    extremes: dict[str, tuple[int, tuple[Any, ...]]] = {}
    options = [[(oid, req, c) for c in choices] for oid, req, choices in occurrences]
    for selection in product(*options):
        if not hard_valid(selection, timed):
            continue
        valid += 1
        loads: Counter[tuple[str, int]] = Counter()
        for _, req, (_, _, covered) in selection:
            if req["teacher_ids"][0] in scope:
                for slot in covered:
                    loads[req["teacher_ids"][0], slot["day"]] += 1
        raw = sum(max(0, n - limit) for n in loads.values())
        inside = bounds.raw.lower <= raw <= bounds.raw.upper
        for b in bounds.days:
            load = loads[b.teacher_id, b.day]
            excess = max(0, load - limit)
            inside = inside and b.load.lower <= load <= b.load.upper
            inside = inside and b.excess.lower <= excess <= b.excess.upper
            name_key = f"excess_s03_{(b.teacher_id, b.day, '')}"
            if name_key in old_domains:
                low, high = old_domains[name_key]
                assert low <= excess <= high
            else:
                assert excess == 0
        assert raw <= old_raw_bound
        rejected += not inside
        if "min" not in extremes or raw < extremes["min"][0]:
            extremes["min"] = (raw, selection)
        if "max" not in extremes or raw > extremes["max"][0]:
            extremes["max"] = (raw, selection)

    counts = {
        "fixture": name,
        "raw_combinations": combinations,
        "hard_valid": valid,
        "rejected_by_bounds": rejected,
        "oracle_raw_min": extremes["min"][0] if extremes else None,
        "oracle_raw_max": extremes["max"][0] if extremes else None,
        "bound_raw": [bounds.raw.lower, bounds.raw.upper],
    }
    print(json.dumps(counts, sort_keys=True))
    assert valid > 0
    assert rejected == 0
    for raw, selection in extremes.values():
        assignments = tuple(
            ScheduleAssignment(
                occurrence_id=oid,
                slot_id=start,
                room_id=room_id,
                class_ids=tuple(req["class_ids"]),
                teacher_ids=tuple(req["teacher_ids"]),
            )
            for oid, req, (start, room_id, _) in selection
        )
        assert validate_schedule(problem, assignments).valid
        score = evaluate_score(problem, assignments)
        assert score.status == "OK" and score.rules[0].raw_penalty == raw


def test_corpus_exercises_non_trivial_bounds() -> None:
    tightened = 0
    for make in CORPUS.values():
        data = make()
        scope, limit = _rule(data)
        bounds = derive_s03_bounds(prepare(ScheduleInput.model_validate(data)), scope, limit)
        assert bounds.bounds is not None
        tightened += bounds.bounds.raw.lower > 0 or any(
            b.load.lower > 0 for b in bounds.bounds.days
        )
    assert tightened >= 8
