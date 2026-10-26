"""Hand-calculated scores, deliberately independent of compiler implementation."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.validation.score_evaluator import _evaluate_validated, evaluate_score


@pytest.mark.parametrize(
    "code,params,expected",
    [
        ("TEACHER_AVOID_SLOTS", {"slot_ids": ["1-AM-2"]}, 1),
        ("TEACHER_AVOID_SLOTS", {"slot_ids": ["1-AM-1", "1-AM-2"]}, 2),
        ("TEACHER_MAX_PERIODS_PER_SESSION", {"session_ids": ["AM"], "limit": 3}, 1),
        ("TEACHER_MAX_PERIODS_PER_SESSION", {"session_ids": ["AM"], "limit": 0}, 4),
        ("TEACHER_MAX_PERIODS_PER_DAY", {"limit": 3}, 1),
        (
            "TEACHER_PREFERRED_PERIOD_WINDOW",
            {"session_ids": ["AM"], "first_period": 2, "last_period": 3},
            2,
        ),
    ],
)
def test_hand_calculated(
    quality_case: dict[str, Any], code: str, params: dict[str, Any], expected: int
) -> None:
    quality_case["constraint_config"]["soft"] = [
        {"id": "pref", "code": code, "parameters": params, "weight": 3, "priority": 1}
    ]
    p = ScheduleInput.model_validate(quality_case)
    assignments = tuple(
        ScheduleAssignment(
            occurrence_id=f"r::{i}", slot_id=f"1-AM-{start}", class_ids=("c",), teacher_ids=("t",)
        )
        for i, start in enumerate((1, 3, 4), 1)
    )
    report = _evaluate_validated(p, assignments)
    assert report.status == "OK"
    assert report.rules[0].raw_penalty == expected
    assert report.tiers == (3 * expected, 0, 0)


def test_public_rejects_missing_schedule(quality_case: dict[str, Any]) -> None:
    report = evaluate_score(ScheduleInput.model_validate(quality_case), ())
    assert report.status == "INVALID_SCHEDULE"
    assert report.tiers is None and not report.rules


def test_empty_and_no_soft(quality_case: dict[str, Any]) -> None:
    quality_case["teaching_requirements"] = []
    p = ScheduleInput.model_validate(quality_case)
    report = evaluate_score(p, ())
    assert report.status == "OK" and report.tiers == (0, 0, 0)
