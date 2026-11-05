"""Exhaustive oracle for Phase 3A repair, with no model, compiler or repair helper reused.

Tiny random instances (2 days x AM/PM x 3 periods, at most four occurrences) get a random
previous schedule, optional lock, teacher unavailability, preferences and a random request.
The oracle enumerates every start-slot assignment itself, filters calendar fit, availability,
locks and class/teacher overlap, counts changes itself, and scores with the independent
validator/evaluator. It compares status and the lexicographic optimum of
``(changes, P1, P2, P3)`` (BEFORE) or ``(P1, P2, P3, changes)`` (AFTER) with ``repair``.
"""

import random
from itertools import product
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.repair import PreviousSchedule, RepairRequest
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.repair.pipeline import repair
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.repair_evaluator import check_report, evaluate_repair
from tkb_core.validation.score_evaluator import evaluate_score

SESSIONS = ("AM", "PM")
SLOTS = [(d, s, p) for d in (1, 2) for s in SESSIONS for p in (1, 2, 3)]


def _sid(day: int, session: str, period: int) -> str:
    return f"{day}-{session}-{period}"


def instance(seed: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    rng = random.Random(seed)
    ids = [_sid(*s) for s in SLOTS]
    blocked = rng.sample(ids, rng.randint(0, 5))
    teachers = [{"id": "t1", "available_slot_ids": [i for i in ids if i not in blocked]}]
    teachers.append({"id": "t2"})
    requirements = []
    count = rng.randint(1, 2)
    for i in range(count):
        options = [[1, 1], [2, 1], [1, 1, 1]] if count == 1 else ([[1, 1], [2, 1]], [[1]])[i]
        blocks = rng.choice(options)
        requirements.append(
            {
                "id": f"r{i}",
                "class_ids": [f"c{i}"],
                "teacher_ids": [rng.choice(["t1", "t1", "t2"])],
                "subject_id": f"s{i}",
                "periods_per_cycle": sum(blocks),
                "block_durations": blocks,
            }
        )
    soft: list[dict[str, Any]] = []
    candidates = {
        "TEACHER_AVOID_SLOTS": lambda: {"slot_ids": rng.sample(ids, 3)},
        "TEACHER_MAX_PERIODS_PER_SESSION": lambda: {"limit": 1, "session_ids": ["AM"]},
        "TEACHER_MAX_PERIODS_PER_DAY": lambda: {"limit": rng.randint(1, 2)},
        "TEACHER_PREFERRED_PERIOD_WINDOW": lambda: {
            "first_period": 2,
            "last_period": 3,
            "session_ids": list(SESSIONS),
        },
        "TEACHER_TOTAL_GAPS": lambda: {"session_ids": list(SESSIONS)},
        "TEACHER_SINGLE_PERIOD_SESSION": lambda: {"session_ids": list(SESSIONS)},
    }
    for code in rng.sample(sorted(candidates), rng.randint(0, 3)):
        soft.append(
            {
                "id": code.lower(),
                "code": code,
                "parameters": candidates[code](),
                "priority": rng.randint(1, 3),
                "weight": rng.randint(1, 2),
            }
        )
    data: dict[str, Any] = {
        "schema_version": "1.1",
        "school": {"school_id": "oracle", "academic_year": "oracle", "term": "oracle"},
        "time_slots": [
            {"id": _sid(*s), "day": s[0], "session": s[1], "period": s[2]} for s in SLOTS
        ],
        "classes": [{"id": f"c{i}"} for i in range(count)],
        "teachers": teachers,
        "subjects": [{"id": f"s{i}"} for i in range(count)],
        "teaching_requirements": requirements,
        "constraint_config": {"policy_version": "0.4", "hard": [], "soft": soft},
    }
    occurrences = _occurrences(data)
    allowed = {o: _allowed(data, o, d) for o, (_, d) in occurrences.items()}
    if rng.random() < 0.25:
        o = rng.choice(sorted(occurrences))
        if allowed[o]:
            data["locked_assignments"] = [{"occurrence_id": o, "slot_id": rng.choice(allowed[o])}]
    previous = []
    for o, (req, _) in sorted(occurrences.items()):
        if rng.random() < 0.85:
            previous.append(_assignment(o, req, rng.choice(ids)))
    if rng.random() < 0.3:
        previous.append(_assignment("gone::1", requirements[0], rng.choice(ids)))
    scope = rng.choice([None, None, {"days": [1]}, {"class_ids": ["c0"]}, {"teacher_ids": ["t2"]}])
    request = {
        "schema_version": "1.0",
        "change_order": "BEFORE_QUALITY",
        "max_changes": rng.choice([None, 0, 0, 1, 2]),
        "change_scope": scope,
        "use_previous_as_hint": rng.random() < 0.5,
    }
    return data, {"schema_version": "1.0", "assignments": previous}, request


def _assignment(occurrence: str, req: dict[str, Any], slot: str) -> dict[str, Any]:
    return {
        "occurrence_id": occurrence,
        "slot_id": slot,
        "class_ids": req["class_ids"],
        "teacher_ids": req["teacher_ids"],
    }


def _occurrences(data: dict[str, Any]) -> dict[str, tuple[dict[str, Any], int]]:
    return {
        f"{r['id']}::{i}": (r, d)
        for r in data["teaching_requirements"]
        for i, d in enumerate(r["block_durations"], 1)
    }


def _footprint(start: str, duration: int) -> list[str]:
    day, session, period = start.split("-")
    return [f"{day}-{session}-{int(period) + k}" for k in range(duration)]


def _allowed(data: dict[str, Any], occurrence: str, duration: int) -> list[str]:
    req = next(
        r for r in data["teaching_requirements"] if r["id"] == occurrence.rpartition("::")[0]
    )
    teacher = next(t for t in data["teachers"] if t["id"] == req["teacher_ids"][0])
    available = teacher.get("available_slot_ids")
    locks = {lock["occurrence_id"]: lock["slot_id"] for lock in data.get("locked_assignments", [])}
    result = []
    for day, session, period in SLOTS:
        if period + duration - 1 > 3:
            continue
        start = _sid(day, session, period)
        if available is not None and any(s not in available for s in _footprint(start, duration)):
            continue
        if occurrence in locks and locks[occurrence] != start:
            continue
        result.append(start)
    return result


def oracle(
    data: dict[str, Any], previous: dict[str, Any], request: dict[str, Any]
) -> tuple[str, tuple[int, ...] | None]:
    """Return (expected status, optimum vector or None)."""
    problem = ScheduleInput.model_validate(data)
    occurrences = _occurrences(data)
    allowed = {o: _allowed(data, o, d) for o, (_, d) in occurrences.items()}
    before = {a["occurrence_id"]: a["slot_id"] for a in previous["assignments"]}
    scope = request["change_scope"]
    frozen = set()
    for o, (req, _) in occurrences.items():
        if o in before and scope is not None:
            in_scope = (
                req["class_ids"][0] in scope.get("class_ids", [])
                or req["teacher_ids"][0] in scope.get("teacher_ids", [])
                or req["subject_id"] in scope.get("subject_ids", [])
                or int(before[o].split("-")[0]) in scope.get("days", [])
            )
            if not in_scope:
                frozen.add(o)
    names = sorted(occurrences)
    base_feasible = False
    vectors = []
    for starts in product(*(allowed[o] for o in names)):
        used: set[tuple[str, str]] = set()
        clash = False
        for o, start in zip(names, starts, strict=True):
            req, duration = occurrences[o]
            for slot in _footprint(start, duration):
                for key in (("c", req["class_ids"][0] + slot), ("t", req["teacher_ids"][0] + slot)):
                    clash = clash or key in used
                    used.add(key)
        if clash:
            continue
        chosen = dict(zip(names, starts, strict=True))
        assignments = tuple(
            ScheduleAssignment.model_validate(_assignment(o, occurrences[o][0], chosen[o]))
            for o in names
        )
        assert validate_schedule(problem, assignments).valid
        base_feasible = True
        changes = sum(o in before and chosen[o] != before[o] for o in names)
        if any(chosen[o] != before[o] for o in frozen):
            continue
        if request["max_changes"] is not None and changes > request["max_changes"]:
            continue
        tiers = evaluate_score(problem, assignments).tiers
        assert tiers is not None
        active = sorted({r["priority"] for r in data["constraint_config"]["soft"]})
        quality = tuple(tiers[p - 1] for p in active)
        vectors.append(
            (changes, *quality)
            if request["change_order"] == "BEFORE_QUALITY"
            else (*quality, changes)
        )
    if any(before[o] not in allowed[o] for o in frozen):
        return ("INPUT_INVALID" if base_feasible else "INPUT_INVALID|INFEASIBLE"), None
    if not vectors:
        return "INFEASIBLE", None
    return "OPTIMAL", min(vectors)


@pytest.mark.parametrize("seed", range(60))
@pytest.mark.parametrize("order", ["BEFORE_QUALITY", "AFTER_QUALITY"])
def test_repair_matches_exhaustive_oracle(seed: int, order: str) -> None:
    data, previous_data, request_data = instance(seed)
    request_data["change_order"] = order
    expected_status, optimum = oracle(data, previous_data, request_data)
    problem = ScheduleInput.model_validate(data)
    previous = PreviousSchedule.model_validate(previous_data)
    request = RepairRequest.model_validate(request_data)
    result = repair(problem, previous, request, SolveOptions(time_limit_seconds=10.0))
    status = result.result.status.value
    assert status in expected_status.split("|"), (seed, status, result.result.diagnostics)
    if status == "INPUT_INVALID":
        assert result.result.diagnostics[0].code == "REPAIR_FROZEN_TARGET_INVALID"
    if optimum is None:
        assert result.repair is None
        return
    assert result.repair is not None and result.repair.min_changes_proved
    assert result.result.quality is not None and result.result.quality.score is not None
    tiers = result.result.quality.score.tiers
    assert tiers is not None
    active = sorted({r["priority"] for r in data["constraint_config"]["soft"]})
    quality = tuple(tiers[p - 1] for p in active)
    changed = result.repair.changed
    actual = (changed, *quality) if order == "BEFORE_QUALITY" else (*quality, changed)
    assert actual == optimum, seed
    evaluation = evaluate_repair(problem, previous, request, result.result.assignments)
    assert check_report(evaluation, result.repair) == ()


def test_oracle_corpus_is_mixed() -> None:
    kinds = set()
    for seed in range(60):
        data, previous, request = instance(seed)
        status, optimum = oracle(data, previous, request)
        kinds.add(status)
        if optimum is not None and optimum[0] > 0:
            kinds.add("CHANGES")
        if data["constraint_config"]["soft"]:
            kinds.add("SOFT")
        if request["change_scope"] is not None:
            kinds.add("SCOPE")
        if request["max_changes"] is not None:
            kinds.add("LIMIT")
        if request["use_previous_as_hint"]:
            kinds.add("HINT")
        if data.get("locked_assignments"):
            kinds.add("LOCK")
    assert {"OPTIMAL", "INFEASIBLE", "CHANGES", "SOFT", "SCOPE", "LIMIT", "HINT", "LOCK"} <= kinds
    assert any(k.startswith("INPUT_INVALID") for k in kinds)
