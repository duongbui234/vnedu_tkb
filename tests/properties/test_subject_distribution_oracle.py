"""Exhaustive oracle for policy 0.3 (S05/S06 with S01-S04), with no Core helper reused.

Enumerates every start-slot assignment of tiny random instances, applies occupancy and
all hard rules itself, and compares feasibility and the lexicographic optimum with
``solve`` with and without interchangeable-occurrence ordering.
"""

import math
import random
from itertools import combinations, product
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule

SESSIONS = ("AM", "PM")
TEACHER_CODES = (
    "TEACHER_AVOID_SLOTS",
    "TEACHER_MAX_PERIODS_PER_DAY",
    "TEACHER_PREFERRED_PERIOD_WINDOW",
)
DIST_CODES = ("SUBJECT_COMPONENT_DAY_SPREAD", "CLASS_SUBJECT_MAX_PERIODS_PER_DAY")


def _params(rng: random.Random, code: str, data: dict[str, Any]) -> dict[str, Any]:
    if code == "TEACHER_AVOID_SLOTS":
        return {"slot_ids": rng.sample([s["id"] for s in data["time_slots"]], rng.randint(1, 3))}
    if code == "TEACHER_MAX_PERIODS_PER_DAY":
        return {"limit": rng.randint(1, 3)}
    if code == "TEACHER_PREFERRED_PERIOD_WINDOW":
        return {"first_period": 1, "last_period": 1, "session_ids": rng.sample(SESSIONS, 1)}
    if code == "SUBJECT_COMPONENT_DAY_SPREAD":
        ids = [r["id"] for r in data["teaching_requirements"]]
        return {
            "requirement_ids": rng.sample(ids, rng.randint(1, len(ids))),
            "min_day_gap": rng.randint(1, 3),
        }
    return {"limit": rng.randint(0, 3)}


def instance(seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    data: dict[str, Any] = {
        "schema_version": "1.1",
        "school": {"school_id": "demo", "academic_year": "demo", "term": "demo"},
        "time_slots": [
            {"id": f"{d}-{s}-{p}", "day": d, "session": s, "period": p}
            for d in (1, 2, 3)
            for s in SESSIONS
            for p in (1, 2)
        ],
        "teachers": [{"id": "t1"}, {"id": "t2"}],
        "subjects": [{"id": "s1"}, {"id": "s2"}],
    }
    requirements = []
    for i in range(rng.randint(1, 2)):
        blocks = rng.choice([[1, 1], [2, 1], [1, 1] if i else [1, 1, 1]])
        requirements.append(
            {
                "id": f"r{i}",
                "class_ids": [f"c{i}"],
                "teacher_ids": [rng.choice(["t1", "t2"])],
                "subject_id": rng.choice(["s1", "s2"]),
                "periods_per_cycle": sum(blocks),
                "block_durations": blocks,
            }
        )
    if sum(len(r["block_durations"]) for r in requirements) > 4:
        requirements[-1]["block_durations"] = [2]
        requirements[-1]["periods_per_cycle"] = 2
    data["teaching_requirements"] = requirements
    data["classes"] = [{"id": f"c{i}"} for i in range(len(requirements))]
    codes = list(DIST_CODES) + rng.sample(TEACHER_CODES, rng.randint(0, 2))
    hard, soft = [], []
    for i, code in enumerate(codes):
        rule = {"id": f"rule{i}", "code": code, "parameters": _params(rng, code, data)}
        if code == "CLASS_SUBJECT_MAX_PERIODS_PER_DAY" and rng.random() < 0.5:
            rule["scope"] = {"class_ids": ["c0"]}
        if rng.random() < 0.4:
            hard.append(rule)
        else:
            soft.append({**rule, "priority": rng.randint(1, 3), "weight": rng.randint(1, 3)})
    data["constraint_config"] = {"policy_version": "0.3", "hard": hard, "soft": soft}
    return data


def _penalty(rule: dict[str, Any], data: dict[str, Any], placed: list[Any]) -> int:
    """Raw penalty from (requirement, covered slots) pairs; zero means hard-satisfied."""
    p, code = rule["parameters"], rule["code"]
    teachers = rule.get("scope", {}).get("teacher_ids") or [t["id"] for t in data["teachers"]]
    periods = [(r["teacher_ids"][0], s) for r, cov in placed for s in cov]
    mine = [(t, s) for t, s in periods if t in teachers]
    if code == "TEACHER_AVOID_SLOTS":
        return sum(s["id"] in p["slot_ids"] for _, s in mine)
    if code == "TEACHER_PREFERRED_PERIOD_WINDOW":
        return sum(
            s["session"] in p["session_ids"]
            and not p["first_period"] <= s["period"] <= p["last_period"]
            for _, s in mine
        )
    if code == "TEACHER_MAX_PERIODS_PER_DAY":
        loads: dict[tuple[str, int], int] = {}
        for t, s in mine:
            loads[t, s["day"]] = loads.get((t, s["day"]), 0) + 1
        return sum(max(0, n - p["limit"]) for n in loads.values())
    if code == "SUBJECT_COMPONENT_DAY_SPREAD":
        days = [cov[0]["day"] for r, cov in placed if r["id"] in p["requirement_ids"]]
        return sum(max(0, p["min_day_gap"] - abs(a - b)) for a, b in combinations(days, 2))
    classes = rule.get("scope", {}).get("class_ids") or [c["id"] for c in data["classes"]]
    counts: dict[tuple[str, str, int], int] = {}
    for r, cov in placed:
        if r["class_ids"][0] in classes:
            for s in cov:
                key = (r["class_ids"][0], r["subject_id"], s["day"])
                counts[key] = counts.get(key, 0) + 1
    return sum(max(0, n - p["limit"]) for n in counts.values())


def oracle(data: dict[str, Any]) -> tuple[int, int, int] | None:
    coords = {(s["day"], s["session"], s["period"]): s for s in data["time_slots"]}
    owners, choices = [], []
    for r in data["teaching_requirements"]:
        for duration in r["block_durations"]:
            owners.append(r)
            starts = []
            for start in data["time_slots"]:
                covered = [
                    coords.get((start["day"], start["session"], start["period"] + i))
                    for i in range(duration)
                ]
                if all(c is not None for c in covered):
                    starts.append(covered)
            choices.append(starts)
    assert math.prod(len(c) for c in choices) <= 25000
    best = None
    for placements in product(*choices):
        seen: set[tuple[str, str, str]] = set()
        clash = False
        for r, covered in zip(owners, placements, strict=True):
            for s in covered:
                for token in (
                    ("t", r["teacher_ids"][0], s["id"]),
                    ("c", r["class_ids"][0], s["id"]),
                ):
                    clash = clash or token in seen
                    seen.add(token)
        if clash:
            continue
        placed = list(zip(owners, placements, strict=True))
        if any(_penalty(rule, data, placed) for rule in data["constraint_config"]["hard"]):
            continue
        vector = [0, 0, 0]
        for rule in data["constraint_config"]["soft"]:
            vector[rule["priority"] - 1] += rule["weight"] * _penalty(rule, data, placed)
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
    assert result.schema_version == "1.4"
    if data["constraint_config"]["soft"]:
        assert result.status == "OPTIMAL", result.diagnostics
        assert result.quality.score.tiers == expected
    else:
        assert result.quality.status == "NOT_REQUESTED"


def test_oracle_corpus_is_mixed() -> None:
    data = [instance(seed) for seed in SEEDS]
    outcomes = [oracle(d) for d in data]
    assert any(o is None for o in outcomes) and any(o is not None and any(o) for o in outcomes)
    for code in DIST_CODES:
        for mode in ("hard", "soft"):
            assert any(
                any(r["code"] == code for r in d["constraint_config"][mode]) for d in data
            ), (code, mode)
    # Ordering only applies with active preferences and interchangeable occurrences.
    assert any(
        d["constraint_config"]["soft"]
        and any(r["block_durations"] in ([1, 1], [1, 1, 1]) for r in d["teaching_requirements"])
        and o is not None
        for d, o in zip(data, outcomes, strict=True)
    )


def test_ordering_is_added_with_distribution_rules(monkeypatch: pytest.MonkeyPatch) -> None:
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
    data["constraint_config"]["hard"] = [
        {"id": "h", "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY", "parameters": {"limit": 1}}
    ]
    data["constraint_config"]["soft"] = [
        {
            "id": "s",
            "code": "SUBJECT_COMPONENT_DAY_SPREAD",
            "parameters": {"requirement_ids": ["r0"], "min_day_gap": 2},
            "priority": 1,
            "weight": 1,
        }
    ]
    model_builder.build_model(
        prepare(ScheduleInput.model_validate(data)), order_interchangeable=True
    )
    assert added == [1]
