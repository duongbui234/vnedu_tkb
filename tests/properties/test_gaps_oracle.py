"""Exhaustive oracle for policy 0.4 gap rules (S07-S11), with no Core helper reused.

Tiny random instances include non-teaching slots and occupied work. The oracle enumerates
start slots, applies calendar/availability/occupancy and the hard rules itself, and compares
feasibility and the lexicographic optimum with ``solve`` with and without ordering.
"""

import math
import random
from itertools import product
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule

SESSIONS = ("AM", "PM")
GAP_CODES = (
    "TEACHER_RESTRICTED_SLOTS",
    "TEACHER_TOTAL_GAPS",
    "TEACHER_MAX_GAP_RUN",
    "TEACHER_MIN_FREE_TIME",
    "TEACHER_SINGLE_PERIOD_SESSION",
)


def instance(seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    slots = [
        {"id": f"{d}-{s}-{p}", "day": d, "session": s, "period": p}
        for d in (1, 2)
        for s in SESSIONS
        for p in (1, 2, 3)
    ]
    for slot in rng.sample(slots, 2):
        slot["can_teach"] = False
    ids = [s["id"] for s in slots]
    occupied = rng.sample(ids, rng.randint(0, 2))
    teachers = [
        {"id": "t1", "available_slot_ids": [i for i in ids if i not in occupied]},
        {"id": "t2"},
    ]
    requirements = []
    count = rng.randint(1, 2)
    for i in range(count):
        # At most four occurrences keep exhaustive enumeration small.
        options = [[1, 1], [2, 1], [1, 1, 1]] if count == 1 else ([[1, 1], [2, 1]], [[1]])[i]
        blocks = rng.choice(options)
        requirements.append(
            {
                "id": f"r{i}",
                "class_ids": [f"c{i}"],
                "teacher_ids": [rng.choice(["t1", "t1", "t2"])],
                "subject_id": "sub",
                "periods_per_cycle": sum(blocks),
                "block_durations": blocks,
            }
        )
    teaching = [s["id"] for s in slots if s.get("can_teach", True)]
    soft = []
    for code in rng.sample(GAP_CODES, rng.randint(1, 3)):
        sessions = rng.sample(SESSIONS, rng.randint(1, 2))
        params: dict[str, Any] = {
            "TEACHER_RESTRICTED_SLOTS": {"slot_ids": rng.sample(teaching, 3)},
            "TEACHER_TOTAL_GAPS": {"session_ids": sessions},
            "TEACHER_MAX_GAP_RUN": {"limit": rng.randint(0, 1), "session_ids": sessions},
            "TEACHER_MIN_FREE_TIME": {
                "unit": rng.choice(["day", "session"]),
                "target": rng.randint(1, 3),
            },
            "TEACHER_SINGLE_PERIOD_SESSION": {"session_ids": sessions},
        }[code]
        rule: dict[str, Any] = {
            "id": code.lower(),
            "code": code,
            "parameters": params,
            "priority": rng.randint(1, 3),
            "weight": rng.randint(1, 3),
        }
        if rng.random() < 0.3:
            rule["scope"] = {"teacher_ids": ["t1"]}
        soft.append(rule)
    hard = []
    if rng.random() < 0.4:
        hard.append(
            {"id": "h6", "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY", "parameters": {"limit": 2}}
        )
    return {
        "schema_version": "1.1",
        "school": {"school_id": "demo", "academic_year": "demo", "term": "demo"},
        "time_slots": slots,
        "classes": [{"id": f"c{i}"} for i in range(len(requirements))],
        "teachers": teachers,
        "subjects": [{"id": "sub"}],
        "teaching_requirements": requirements,
        "constraint_config": {
            "policy_version": "0.4",
            "hard": hard,
            "soft": soft,
            "occupied_work": [{"teacher_id": "t1", "slot_ids": occupied}] if occupied else [],
        },
    }


def _penalty(rule: dict[str, Any], data: dict[str, Any], taught: dict[Any, set[str]]) -> int:
    """taught[(teacher, day, session)] = slot IDs covered by that teacher's lessons."""
    p, code = rule["parameters"], rule["code"]
    teachers = rule.get("scope", {}).get("teacher_ids") or [t["id"] for t in data["teachers"]]
    occupied: set[str] = set()
    for entry in data["constraint_config"]["occupied_work"]:
        occupied |= set(entry["slot_ids"])  # only t1 has occupied work in this corpus
    sessions: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for s in sorted(data["time_slots"], key=lambda s: (s["day"], s["session"], s["period"])):
        sessions.setdefault((s["day"], s["session"]), []).append(s)
    total = 0
    for t in teachers:
        occ = occupied if t == "t1" else set()
        if code == "TEACHER_RESTRICTED_SLOTS":
            total += sum(
                len(ids & set(p["slot_ids"])) for (tt, _, _), ids in taught.items() if tt == t
            )
        elif code == "TEACHER_MIN_FREE_TIME":
            units, busy = set(), set()
            for (d, s), ss in sessions.items():
                key = d if p["unit"] == "day" else (d, s)
                if any(x.get("can_teach", True) for x in ss):
                    units.add(key)
                if taught.get((t, d, s)) or any(x["id"] in occ for x in ss):
                    busy.add(key)
            total += max(0, p["target"] - len(units - busy))
        else:
            for (d, s), ss in sessions.items():
                if s not in p["session_ids"]:
                    continue
                mine = taught.get((t, d, s), set())
                if code == "TEACHER_SINGLE_PERIOD_SESSION":
                    total += int(len(mine) == 1)
                    continue
                if len(mine) < 2:
                    continue
                periods = [x["period"] for x in ss if x["id"] in mine]
                lo, hi = min(periods), max(periods)
                flags = [
                    lo < x["period"] < hi
                    and x.get("can_teach", True)
                    and x["id"] not in mine
                    and x["id"] not in occ
                    for x in ss
                ]
                if code == "TEACHER_TOTAL_GAPS":
                    total += sum(flags)
                else:
                    run = longest = 0
                    for f in flags:
                        run = run + 1 if f else 0
                        longest = max(longest, run)
                    total += max(0, longest - p["limit"])
    return total


def oracle(data: dict[str, Any]) -> tuple[int, int, int] | None:
    coords = {(s["day"], s["session"], s["period"]): s for s in data["time_slots"]}
    teachers = {t["id"]: t for t in data["teachers"]}
    owners, choices = [], []
    for r in data["teaching_requirements"]:
        available = teachers[r["teacher_ids"][0]].get("available_slot_ids")
        for duration in r["block_durations"]:
            owners.append(r)
            starts = []
            for start in data["time_slots"]:
                cov = [
                    coords.get((start["day"], start["session"], start["period"] + i))
                    for i in range(duration)
                ]
                if any(c is None or not c.get("can_teach", True) for c in cov):
                    continue
                if available is not None and any(c["id"] not in available for c in cov):
                    continue
                starts.append(cov)
            choices.append(starts)
    assert math.prod(len(c) for c in choices) <= 40000
    best = None
    for placements in product(*choices):
        seen: set[tuple[str, str, str]] = set()
        clash = False
        taught: dict[Any, set[str]] = {}
        subject_day: dict[tuple[str, int], int] = {}
        for r, cov in zip(owners, placements, strict=True):
            for s in cov:
                for token in (
                    ("t", r["teacher_ids"][0], s["id"]),
                    ("c", r["class_ids"][0], s["id"]),
                ):
                    clash = clash or token in seen
                    seen.add(token)
                taught.setdefault((r["teacher_ids"][0], s["day"], s["session"]), set()).add(s["id"])
                key = (r["class_ids"][0], s["day"])
                subject_day[key] = subject_day.get(key, 0) + 1
        if clash:
            continue
        if data["constraint_config"]["hard"] and any(n > 2 for n in subject_day.values()):
            continue
        vector = [0, 0, 0]
        for rule in data["constraint_config"]["soft"]:
            vector[rule["priority"] - 1] += rule["weight"] * _penalty(rule, data, taught)
        candidate = (vector[0], vector[1], vector[2])
        best = candidate if best is None or candidate < best else best
    return best


SEEDS = range(60)


@pytest.mark.parametrize("ordering", [True, False])
@pytest.mark.parametrize("seed", SEEDS)
def test_solver_matches_exhaustive_oracle(
    seed: int, ordering: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    if not ordering:
        monkeypatch.setattr(
            "tkb_core.solver.model_builder._add_interchangeable_ordering", lambda *a: None
        )
    data = instance(seed)
    expected = oracle(data)
    problem = ScheduleInput.model_validate(data)
    result = solve(problem, SolveOptions(time_limit_seconds=20.0))
    if expected is None:
        assert result.status == "INFEASIBLE", result.diagnostics
        return
    assert result.valid_schedule and validate_schedule(problem, result.assignments).valid
    assert result.schema_version == "1.5"
    assert result.status == "OPTIMAL", result.diagnostics
    assert result.quality.score.tiers == expected


def test_oracle_corpus_is_mixed() -> None:
    data = [instance(seed) for seed in SEEDS]
    outcomes = [oracle(d) for d in data]
    assert any(o is not None and any(o) for o in outcomes)
    for code in GAP_CODES:
        assert any(any(r["code"] == code for r in d["constraint_config"]["soft"]) for d in data)
    assert any(d["constraint_config"]["occupied_work"] for d in data)
    assert any(
        any(r["block_durations"] in ([1, 1], [1, 1, 1]) for r in d["teaching_requirements"])
        and o is not None
        for d, o in zip(data, outcomes, strict=True)
    )


def test_ordering_is_added_with_gap_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    from tkb_core.preprocessing.feasibility import prepare
    from tkb_core.solver import model_builder

    added = []
    original = model_builder._add_interchangeable_ordering

    def spy(prepared: Any, built: Any) -> None:
        before = len(built.model.proto.constraints)
        original(prepared, built)
        added.append(len(built.model.proto.constraints) - before)

    monkeypatch.setattr(model_builder, "_add_interchangeable_ordering", spy)
    data = instance(0)
    data["teaching_requirements"] = [
        data["teaching_requirements"][0] | {"periods_per_cycle": 2, "block_durations": [1, 1]}
    ]
    data["classes"] = [{"id": "c0"}]
    data["constraint_config"]["hard"] = []
    data["constraint_config"]["soft"] = [
        {
            "id": "g",
            "code": "TEACHER_TOTAL_GAPS",
            "parameters": {"session_ids": ["AM"]},
            "priority": 1,
            "weight": 1,
        }
    ]
    model_builder.build_model(
        prepare(ScheduleInput.model_validate(data)), order_interchangeable=True
    )
    assert added == [1]
