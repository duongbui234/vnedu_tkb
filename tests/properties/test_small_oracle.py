"""Tiny exhaustive oracle, independent of model/normalization/validator helpers."""

import random
from itertools import product
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions


def brute_force(data: dict[str, Any]) -> bool:
    choices = []
    for req in data["teaching_requirements"]:
        teacher = next(t for t in data["teachers"] if t["id"] == req["teacher_ids"][0])
        count = req["periods_per_cycle"]
        eligible = []
        for start in range(1, 4):
            slots = tuple(range(start, start + count))
            if slots[-1] <= 3 and all(str(s) in teacher["available_slot_ids"] for s in slots):
                eligible.append(slots)
        choices.append(eligible)
    for combination in product(*choices):
        occupied: set[tuple[str, str, int]] = set()
        valid = True
        for req, slots in zip(data["teaching_requirements"], combination, strict=True):
            footprint = {
                (kind, resource, slot)
                for kind, resource in [("c", req["class_ids"][0]), ("t", req["teacher_ids"][0])]
                for slot in slots
            }
            if occupied & footprint:
                valid = False
                break
            occupied |= footprint
        if valid:
            return True
    return False


@pytest.mark.parametrize("seed", range(20))
def test_matches_exhaustive_small_feasibility(seed: int) -> None:
    rng = random.Random(seed)
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "school": {"school_id": "demo", "academic_year": "demo", "term": "demo"},
        "time_slots": [{"id": str(i), "day": 1, "session": "AM", "period": i} for i in range(1, 4)],
        "classes": [{"id": f"c{i}"} for i in range(2)],
        "teachers": [
            {
                "id": f"t{i}",
                "available_slot_ids": [str(s) for s in range(1, 4) if rng.random() > 0.2],
            }
            for i in range(2)
        ],
        "subjects": [{"id": "s"}],
        "teaching_requirements": [],
    }
    for i in range(3):
        duration = rng.choice([1, 1, 2])
        data["teaching_requirements"].append(
            {
                "id": f"r{i}",
                "subject_id": "s",
                "class_ids": [f"c{rng.randrange(2)}"],
                "teacher_ids": [f"t{rng.randrange(2)}"],
                "periods_per_cycle": duration,
                "block_durations": [duration],
            }
        )
    expected = brute_force(data)
    result = solve(ScheduleInput.model_validate(data), SolveOptions(time_limit_seconds=5.0))
    assert result.valid_schedule == expected
    assert result.status in ({"OPTIMAL", "FEASIBLE"} if expected else {"INFEASIBLE"})
