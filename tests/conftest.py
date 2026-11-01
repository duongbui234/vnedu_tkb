"""Synthetic domain fixtures, unrelated to any vnEdu API schema."""

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def problem_data() -> dict[str, Any]:
    return json.loads((Path(__file__).parent / "fixtures/feasible_small.json").read_text())


@pytest.fixture
def quality_data() -> dict[str, Any]:
    return json.loads(
        (Path(__file__).parent / "fixtures/quality/teacher_preferences.json").read_text()
    )


@pytest.fixture
def quality_case() -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "school": {"school_id": "demo", "academic_year": "demo", "term": "demo"},
        "time_slots": [
            {"id": f"{d}-{s}-{p}", "day": d, "session": s, "period": p}
            for d in (1, 2)
            for s in ("AM", "PM")
            for p in range(1, 5)
        ],
        "classes": [{"id": "c"}],
        "teachers": [{"id": "t"}],
        "subjects": [{"id": "sub"}],
        "teaching_requirements": [
            {
                "id": "r",
                "class_ids": ["c"],
                "teacher_ids": ["t"],
                "subject_id": "sub",
                "periods_per_cycle": 4,
                "block_durations": [2, 1, 1],
            }
        ],
        "constraint_config": {"policy_version": "0.1", "hard": [], "soft": []},
    }


@pytest.fixture
def ordering_case(quality_case: dict[str, Any]) -> dict[str, Any]:
    """Three interchangeable synthetic singles and all four resource-only preferences."""
    quality_case["time_slots"] = quality_case["time_slots"][:4]
    quality_case["teaching_requirements"][0].update(periods_per_cycle=3, block_durations=[1, 1, 1])
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "avoid",
            "code": "TEACHER_AVOID_SLOTS",
            "parameters": {"slot_ids": ["1-AM-1"]},
            "priority": 1,
            "weight": 1,
        },
        {
            "id": "session",
            "code": "TEACHER_MAX_PERIODS_PER_SESSION",
            "parameters": {"limit": 2, "session_ids": ["AM"]},
            "priority": 1,
            "weight": 1,
        },
        {
            "id": "day",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 2},
            "priority": 2,
            "weight": 1,
        },
        {
            "id": "window",
            "code": "TEACHER_PREFERRED_PERIOD_WINDOW",
            "parameters": {"first_period": 2, "last_period": 3, "session_ids": ["AM"]},
            "priority": 3,
            "weight": 1,
        },
    ]
    return quality_case
