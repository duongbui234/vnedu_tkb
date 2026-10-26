"""Exhaustive quality oracle with no model, validator or evaluator helpers."""

import json
import random
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.score_evaluator import evaluate_score


def oracle(data: dict[str, Any]) -> tuple[int, int, int] | None:
    slots = data["time_slots"]
    coords = {(s["day"], s["session"], s["period"]): s for s in slots}
    teachers = {t["id"]: t for t in data["teachers"]}
    classes = {c["id"]: c for c in data["classes"]}
    components = []
    choices = []
    for r in data["teaching_requirements"]:
        for duration in r.get("block_durations", [1] * r["periods_per_cycle"]):
            components.append(r)
            candidates = []
            for start in slots:
                covered = [
                    coords.get((start["day"], start["session"], start["period"] + i))
                    for i in range(duration)
                ]
                if any(s is None or not s.get("can_teach", True) for s in covered):
                    continue
                if any(
                    resource.get("available_slot_ids") is not None
                    and any(s["id"] not in resource["available_slot_ids"] for s in covered)
                    for resource in (teachers[r["teacher_ids"][0]], classes[r["class_ids"][0]])
                ):
                    continue
                candidates.append(covered)
            choices.append(candidates)
    assert __import__("math").prod(len(c) for c in choices) <= 50000
    best = None
    for placements in product(*choices):
        seen = set()
        periods = []
        valid = True
        for r, covered in zip(components, placements, strict=True):
            for s in covered:
                for kind, key in [("t", r["teacher_ids"][0]), ("c", r["class_ids"][0])]:
                    token = (kind, key, s["id"])
                    if token in seen:
                        valid = False
                    seen.add(token)
                periods.append((r["teacher_ids"][0], s))
        if not valid:
            continue
        vector = [0, 0, 0]
        for rule in data["constraint_config"]["soft"]:
            if not rule.get("enabled", True):
                continue
            selected = rule.get("scope", {}).get("teacher_ids") or list(teachers)
            rows = [(t, s) for t, s in periods if t in selected]
            p = rule["parameters"]
            code = rule["code"]
            if code == "TEACHER_AVOID_SLOTS":
                raw = sum(s["id"] in p["slot_ids"] for _, s in rows)
            elif code == "TEACHER_PREFERRED_PERIOD_WINDOW":
                raw = sum(
                    s["session"] in p["session_ids"]
                    and not p["first_period"] <= s["period"] <= p["last_period"]
                    for _, s in rows
                )
            else:
                loads = {}
                for t, s in rows:
                    if code == "TEACHER_MAX_PERIODS_PER_SESSION":
                        if s["session"] not in p["session_ids"]:
                            continue
                        bucket = (t, s["day"], s["session"])
                    else:
                        bucket = (t, s["day"])
                    loads[bucket] = loads.get(bucket, 0) + 1
                raw = sum(max(0, n - p["limit"]) for n in loads.values())
            vector[rule["priority"] - 1] += raw * rule["weight"]
        value = tuple(vector)
        best = value if best is None or value < best else best
    return best


@pytest.mark.parametrize("seed", range(10))
def test_small_quality_matches_exhaustive_oracle(quality_case: dict[str, Any], seed: int) -> None:
    rng = random.Random(seed)
    data = quality_case
    data["time_slots"] = [s for s in data["time_slots"] if s["period"] <= 3]
    data["teachers"] = [{"id": "t"}, {"id": "u"}]
    data["classes"] = [{"id": "c"}, {"id": "b"}]
    data["teaching_requirements"] = [
        {
            "id": f"r{i}",
            "subject_id": "sub",
            "class_ids": [rng.choice(["c", "b"])],
            "teacher_ids": [rng.choice(["t", "u"])],
            "periods_per_cycle": d,
            "block_durations": [d],
        }
        for i, d in enumerate([rng.choice([1, 2]) for _ in range(3)])
    ]
    data["constraint_config"]["soft"] = [
        {
            "id": "avoid",
            "code": "TEACHER_AVOID_SLOTS",
            "parameters": {"slot_ids": ["1-AM-1"]},
            "weight": 2,
            "priority": 1,
        },
        {
            "id": "session",
            "code": "TEACHER_MAX_PERIODS_PER_SESSION",
            "parameters": {"limit": 1, "session_ids": ["AM", "PM"]},
            "weight": 1,
            "priority": 2,
        },
        {
            "id": "daily",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 2},
            "weight": 1,
            "priority": 1,
        },
        {
            "id": "window",
            "code": "TEACHER_PREFERRED_PERIOD_WINDOW",
            "parameters": {"first_period": 2, "last_period": 3, "session_ids": ["AM", "PM"]},
            "weight": 3,
            "priority": 3,
        },
    ]
    expected = oracle(data)
    result = solve(ScheduleInput.model_validate(data), SolveOptions(time_limit_seconds=5.0))
    if expected is None:
        assert result.status == "INFEASIBLE"
    else:
        assert result.status == "OPTIMAL"
        assert result.quality.score.tiers == expected


@pytest.mark.parametrize(
    "name,expected,slot",
    [("priority_tradeoff", (0, 5, 0), "A"), ("weighted_tradeoff", (1, 0, 0), "B")],
)
def test_fixed_baseline_improvement(name: str, expected: tuple[int, int, int], slot: str) -> None:
    path = Path(__file__).parents[1] / f"fixtures/quality/{name}.json"
    data = json.loads(path.read_text())
    p = ScheduleInput.model_validate(data)
    result = solve(p, SolveOptions(time_limit_seconds=5.0))
    assert oracle(data) == expected == result.quality.score.tiers
    assert result.assignments[0].slot_id == slot
    baseline = (
        ScheduleAssignment(occurrence_id="r::1", slot_id="B", teacher_ids=("t",), class_ids=("c",)),
    )
    if name == "priority_tradeoff":
        assert evaluate_score(p, baseline).tiers == (1, 0, 0)
        assert expected < evaluate_score(p, baseline).tiers
