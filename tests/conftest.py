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
