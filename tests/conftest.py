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
