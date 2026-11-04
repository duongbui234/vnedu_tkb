"""Exhaustive oracle for policy 0.2 hard variants, with no Core helper reused.

Enumerates every start-slot assignment of tiny random instances, applies built-in
occupancy plus hard S01-S04 itself, and compares feasibility and the lexicographic
optimum with ``solve`` both with and without interchangeable-occurrence ordering.
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
CODES = (
    "TEACHER_AVOID_SLOTS",
    "TEACHER_MAX_PERIODS_PER_SESSION",
    "TEACHER_MAX_PERIODS_PER_DAY",
    "TEACHER_PREFERRED_PERIOD_WINDOW",
)


def _params(rng: random.Random, code: str, slot_ids: list[str]) -> dict[str, Any]:
    if code == "TEACHER_AVOID_SLOTS":
        return {"slot_ids": rng.sample(slot_ids, rng.randint(1, 4))}
    if code == "TEACHER_MAX_PERIODS_PER_SESSION":
        return {"limit": rng.randint(0, 2), "session_ids": rng.sample(SESSIONS, rng.randint(1, 2))}
    if code == "TEACHER_MAX_PERIODS_PER_DAY":
        return {"limit": rng.randint(1, 3)}
    first = rng.randint(1, 3)
    return {
        "first_period": first,
        "last_period": rng.randint(first, 3),
        "session_ids": rng.sample(SESSIONS, rng.randint(1, 2)),
    }


def instance(seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    slots = [
        {"id": f"{d}-{s}-{p}", "day": d, "session": s, "period": p}
        for d in (1, 2)
        for s in SESSIONS
        for p in (1, 2, 3)
    ]
    teachers = ["t1", "t2"][: rng.randint(1, 2)]
    requirements = []
    for i in range(rng.randint(1, 2)):
        blocks = rng.choice([[1, 1], [2], [2, 1]])
        requirements.append(
            {
                "id": f"r{i}",
                "class_ids": [f"c{i}"],
                "teacher_ids": [rng.choice(teachers)],
                "subject_id": "sub",
                "periods_per_cycle": sum(blocks),
                "block_durations": blocks,
            }
        )
    hard_codes = rng.sample(CODES, rng.randint(1, 2))
    soft_codes = [c for c in CODES if c not in hard_codes]
    ids = [s["id"] for s in slots]
    hard = [
        {"id": f"h{i}", "code": c, "parameters": _params(rng, c, ids)}
        for i, c in enumerate(hard_codes)
    ]
    soft = [
        {
            "id": f"s{i}",
            "code": c,
            "parameters": _params(rng, c, ids),
            "priority": rng.randint(1, 3),
            "weight": rng.randint(1, 3),
        }
        for i, c in enumerate(rng.sample(soft_codes, rng.randint(0, len(soft_codes))))
    ]
    return {
        "schema_version": "1.1",
        "school": {"school_id": "demo", "academic_year": "demo", "term": "demo"},
        "time_slots": slots,
        "classes": [{"id": f"c{i}"} for i in range(len(requirements))],
        "teachers": [{"id": t} for t in teachers],
        "subjects": [{"id": "sub"}],
        "teaching_requirements": requirements,
        "constraint_config": {"policy_version": "0.2", "hard": hard, "soft": soft},
    }


def _penalty(rule: dict[str, Any], periods: list[tuple[str, dict[str, Any]]]) -> int:
    """Raw S01-S04 penalty of covered (teacher, slot) periods; zero means hard-satisfied."""
    p, code = rule["parameters"], rule["code"]
    if code == "TEACHER_AVOID_SLOTS":
        return sum(s["id"] in p["slot_ids"] for _, s in periods)
    if code == "TEACHER_PREFERRED_PERIOD_WINDOW":
        return sum(
            s["session"] in p["session_ids"]
            and not p["first_period"] <= s["period"] <= p["last_period"]
            for _, s in periods
        )
    loads: dict[tuple[str, int, str], int] = {}
    for t, s in periods:
        if code == "TEACHER_MAX_PERIODS_PER_SESSION" and s["session"] not in p["session_ids"]:
            continue
        key = (t, s["day"], s["session"] if code == "TEACHER_MAX_PERIODS_PER_SESSION" else "")
        loads[key] = loads.get(key, 0) + 1
    return sum(max(0, n - p["limit"]) for n in loads.values())


def _scoped(
    data: dict[str, Any], rule: dict[str, Any], periods: list[tuple[str, dict[str, Any]]]
) -> list[tuple[str, dict[str, Any]]]:
    chosen = rule.get("scope", {}).get("teacher_ids") or [t["id"] for t in data["teachers"]]
    return [(t, s) for t, s in periods if t in chosen]


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
    assert math.prod(len(c) for c in choices) <= 30000
    best = None
    for placements in product(*choices):
        seen: set[tuple[str, str, str]] = set()
        periods = []
        clash = False
        for r, covered in zip(owners, placements, strict=True):
            for s in covered:
                for token in (
                    ("t", r["teacher_ids"][0], s["id"]),
                    ("c", r["class_ids"][0], s["id"]),
                ):
                    clash = clash or token in seen
                    seen.add(token)
                periods.append((r["teacher_ids"][0], s))
        if clash:
            continue
        if any(
            _penalty(rule, _scoped(data, rule, periods))
            for rule in data["constraint_config"]["hard"]
        ):
            continue
        vector = [0, 0, 0]
        for rule in data["constraint_config"]["soft"]:
            raw = _penalty(rule, _scoped(data, rule, periods))
            vector[rule["priority"] - 1] += rule["weight"] * raw
        candidate = (vector[0], vector[1], vector[2])
        best = candidate if best is None or candidate < best else best
    return best


@pytest.mark.parametrize("ordering", [True, False])
@pytest.mark.parametrize("seed", range(60))
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
        assert result.status == "INFEASIBLE"
        return
    assert result.valid_schedule and validate_schedule(problem, result.assignments).valid
    assert result.schema_version == "1.3"
    if data["constraint_config"]["soft"]:
        assert result.status == "OPTIMAL", result.diagnostics
        assert result.quality.score.tiers == expected
    else:
        assert result.quality.status == "NOT_REQUESTED"


def test_oracle_corpus_is_mixed() -> None:
    data = [instance(seed) for seed in range(60)]
    outcomes = [oracle(d) for d in data]
    assert any(o is None for o in outcomes) and any(o is not None and any(o) for o in outcomes)
    # Ordering only applies with active preferences and interchangeable occurrences.
    assert any(
        d["constraint_config"]["soft"]
        and any(r["block_durations"] == [1, 1] for r in d["teaching_requirements"])
        and o is not None
        for d, o in zip(data, outcomes, strict=True)
    )


def test_ordering_is_added_with_resource_only_hard(monkeypatch: pytest.MonkeyPatch) -> None:
    from tkb_core.preprocessing.feasibility import prepare
    from tkb_core.solver import model_builder

    calls = []
    original = model_builder._add_interchangeable_ordering

    def spy(prepared: Any, built: Any) -> None:
        before = len(built.model.proto.constraints)
        original(prepared, built)
        calls.append(len(built.model.proto.constraints) - before)

    monkeypatch.setattr(model_builder, "_add_interchangeable_ordering", spy)
    data = instance(0)
    data["teaching_requirements"] = [
        data["teaching_requirements"][0] | {"periods_per_cycle": 2, "block_durations": [1, 1]}
    ]
    data["constraint_config"]["soft"] = [
        {
            "id": "s",
            "code": "TEACHER_AVOID_SLOTS",
            "parameters": {"slot_ids": ["1-AM-1"]},
            "priority": 1,
            "weight": 1,
        }
    ]
    data["constraint_config"]["hard"] = [
        {"id": "h", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 2}}
    ]
    prepared = prepare(ScheduleInput.model_validate(data))
    model_builder.build_model(prepared, order_interchangeable=True)
    assert calls == [1]
