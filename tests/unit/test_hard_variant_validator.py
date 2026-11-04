"""Independent hard-variant checks on forged schedules (Phase 2B)."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score

AVOID = {"id": "h1", "code": "TEACHER_AVOID_SLOTS", "parameters": {"slot_ids": ["1-AM-2"]}}
SESSION = {
    "id": "h2",
    "code": "TEACHER_MAX_PERIODS_PER_SESSION",
    "parameters": {"limit": 2, "session_ids": ["AM"]},
}
DAY = {"id": "h3", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 2}}
WINDOW = {
    "id": "h4",
    "code": "TEACHER_PREFERRED_PERIOD_WINDOW",
    "parameters": {"first_period": 1, "last_period": 2, "session_ids": ["AM"]},
}


def _schedule(*slots: str) -> tuple[ScheduleAssignment, ...]:
    return tuple(
        ScheduleAssignment(
            occurrence_id=f"r::{i}", slot_id=slot, class_ids=("c",), teacher_ids=("t",)
        )
        for i, slot in enumerate(slots, 1)
    )


def _violations(data: dict[str, Any], rule: dict[str, Any], *slots: str) -> list[Any]:
    data["constraint_config"]["hard"] = [rule]
    report = validate_schedule(ScheduleInput.model_validate(data), _schedule(*slots))
    return list(report.violations)


@pytest.mark.parametrize("rule", [AVOID, SESSION, DAY, WINDOW])
def test_valid_schedule_has_no_hard_violation(hard_case: dict[str, Any], rule: Any) -> None:
    assert _violations(hard_case, rule, "2-AM-1", "1-PM-1", "1-PM-2") == []


def test_avoid_slot_checks_second_period_of_double(hard_case: dict[str, Any]) -> None:
    (v,) = _violations(hard_case, AVOID, "1-AM-1", "1-PM-1", "2-PM-1")
    assert (v.code, v.resource_ids, v.slot_ids, v.occurrence_ids) == (
        "HARD_AVOID_SLOT",
        ("t",),
        ("1-AM-2",),
        ("r::1",),
    )


def test_session_limit_counts_double_as_two(hard_case: dict[str, Any]) -> None:
    (v,) = _violations(hard_case, SESSION, "1-AM-1", "1-AM-3", "1-PM-1")
    assert v.code == "HARD_SESSION_LIMIT" and v.resource_ids == ("t",)
    assert v.slot_ids == ("1-AM-1", "1-AM-2", "1-AM-3")
    assert v.occurrence_ids == ("r::1", "r::2")
    # PM is outside session_ids: three PM periods are not limited.
    assert _violations(hard_case, SESSION, "1-PM-1", "1-PM-3", "1-AM-1") == []


def test_day_limit_sums_sessions_and_limit_zero(hard_case: dict[str, Any]) -> None:
    (v,) = _violations(hard_case, DAY, "1-AM-1", "1-PM-1", "2-PM-1")
    assert v.code == "HARD_DAY_LIMIT" and v.occurrence_ids == ("r::1", "r::2")
    assert v.slot_ids == ("1-AM-1", "1-AM-2", "1-PM-1")
    zero = {**DAY, "parameters": {"limit": 0}}
    assert len(_violations(hard_case, zero, "1-AM-1", "1-PM-1", "2-PM-1")) == 2


def test_window_checks_second_period(hard_case: dict[str, Any]) -> None:
    (v,) = _violations(hard_case, WINDOW, "1-AM-2", "1-PM-1", "2-PM-4")
    assert (v.code, v.slot_ids, v.occurrence_ids) == (
        "HARD_PERIOD_WINDOW",
        ("1-AM-3",),
        ("r::1",),
    )


def test_disabled_scope_and_policy_01(hard_case: dict[str, Any]) -> None:
    assert _violations(hard_case, {**AVOID, "enabled": False}, "1-AM-1", "1-PM-1", "2-PM-1") == []
    hard_case["teachers"].append({"id": "other"})
    scoped = {**AVOID, "scope": {"teacher_ids": ["other"]}}
    assert _violations(hard_case, scoped, "1-AM-1", "1-PM-1", "2-PM-1") == []
    hard_case["constraint_config"]["policy_version"] = "0.1"
    (v,) = _violations(hard_case, AVOID, "2-AM-1", "1-PM-1", "2-PM-1")
    assert v.code == "UNSUPPORTED_FEATURE"


def test_timed_alias_intersection(hard_case: dict[str, Any]) -> None:
    hard_case["time_slots"] = [
        {"id": "a1", "day": 1, "session": "A", "period": 1, "start_minute": 0, "end_minute": 45},
        {"id": "a2", "day": 1, "session": "A", "period": 2, "start_minute": 45, "end_minute": 90},
        {"id": "b1", "day": 1, "session": "B", "period": 1, "start_minute": 30, "end_minute": 75},
        {"id": "c1", "day": 1, "session": "C", "period": 1, "start_minute": 200, "end_minute": 245},
        {"id": "c2", "day": 1, "session": "C", "period": 2, "start_minute": 245, "end_minute": 290},
    ]
    hard_case["teaching_requirements"][0].update(periods_per_cycle=2, block_durations=[2])
    rule = {**AVOID, "parameters": {"slot_ids": ["b1"]}}
    (v,) = _violations(hard_case, rule, "a1")
    assert v.slot_ids == ("a1", "a2")
    assert _violations(hard_case, rule, "c1") == []


def test_evaluate_score_rejects_hard_variant_violation(hard_case: dict[str, Any]) -> None:
    hard_case["constraint_config"]["hard"] = [AVOID]
    p = ScheduleInput.model_validate(hard_case)
    assert evaluate_score(p, _schedule("1-AM-1", "1-PM-1", "2-PM-1")).status == "INVALID_SCHEDULE"
    ok = evaluate_score(p, _schedule("2-AM-1", "1-PM-1", "2-PM-1"))
    assert ok.status == "OK" and ok.rules == () and ok.tiers == (0, 0, 0)


def test_checker_imports_no_compiler_or_solver_code() -> None:
    import subprocess
    import sys

    script = """
import builtins
original=builtins.__import__
def guarded(name,*args,**kwargs):
    blocked=('ortools','tkb_core.preprocessing','tkb_core.constraints.soft',
             'tkb_core.constraints.hard','tkb_core.constraints.hard_variants',
             'tkb_core.solver')
    if name.startswith(blocked):
        raise ImportError('blocked '+name)
    return original(name,*args,**kwargs)
builtins.__import__=guarded
import tkb_core.validation.independent_validator
import tkb_core.validation.score_evaluator
"""
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
