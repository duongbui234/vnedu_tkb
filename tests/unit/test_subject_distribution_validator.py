"""Independent hard checks for S05/S06 on forged schedules (Phase 2C-1)."""

import subprocess
import sys
from typing import Any

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score

SPREAD = {
    "id": "spread",
    "code": "SUBJECT_COMPONENT_DAY_SPREAD",
    "parameters": {"requirement_ids": ["r"], "min_day_gap": 2},
}
SUBJECT_DAY = {"id": "sd", "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY", "parameters": {"limit": 2}}


def _schedule(*slots: str) -> tuple[ScheduleAssignment, ...]:
    return tuple(
        ScheduleAssignment(
            occurrence_id=f"r::{i}", slot_id=slot, class_ids=("c",), teacher_ids=("t",)
        )
        for i, slot in enumerate(slots, 1)
    )


def _violations(data: dict[str, Any], rule: dict[str, Any], *slots: str) -> list[Any]:
    data["constraint_config"]["hard"] = [rule]
    return list(validate_schedule(ScheduleInput.model_validate(data), _schedule(*slots)).violations)


def test_spread_valid_and_pair_violation(dist_case: dict[str, Any]) -> None:
    dist_case["teaching_requirements"][0].update(periods_per_cycle=2, block_durations=[1, 1])
    assert _violations(dist_case, SPREAD, "1-AM-1", "3-AM-1") == []
    (v,) = _violations(dist_case, SPREAD, "1-AM-1", "2-PM-4")
    assert (v.code, v.resource_ids, v.slot_ids, v.occurrence_ids) == (
        "HARD_DAY_SPREAD",
        ("r",),
        ("1-AM-1", "2-PM-4"),
        ("r::1", "r::2"),
    )


def test_spread_reports_every_close_pair(dist_case: dict[str, Any]) -> None:
    found = _violations(dist_case, SPREAD, "1-AM-1", "1-PM-1", "2-AM-1")
    assert [v.occurrence_ids for v in found] == [
        ("r::1", "r::2"),
        ("r::1", "r::3"),
        ("r::2", "r::3"),
    ]


def test_subject_day_limit(dist_case: dict[str, Any]) -> None:
    assert _violations(dist_case, SUBJECT_DAY, "1-AM-1", "2-AM-1", "3-AM-1") == []
    (v,) = _violations(dist_case, SUBJECT_DAY, "1-AM-1", "1-PM-1", "3-AM-1")
    assert (v.code, v.resource_ids, v.slot_ids, v.occurrence_ids) == (
        "HARD_SUBJECT_DAY_LIMIT",
        ("c", "sub"),
        ("1-AM-1", "1-AM-2", "1-PM-1"),
        ("r::1", "r::2"),
    )
    scoped = {**SUBJECT_DAY, "scope": {"subject_ids": ["other"]}}
    dist_case["subjects"].append({"id": "other"})
    assert _violations(dist_case, scoped, "1-AM-1", "1-PM-1", "3-AM-1") == []


def test_disabled_and_older_policy(dist_case: dict[str, Any]) -> None:
    disabled = {**SUBJECT_DAY, "enabled": False}
    assert _violations(dist_case, disabled, "1-AM-1", "1-PM-1", "3-AM-1") == []
    dist_case["constraint_config"]["policy_version"] = "0.2"
    (v,) = _violations(dist_case, SUBJECT_DAY, "1-AM-1", "2-AM-1", "3-AM-1")
    assert v.code == "UNSUPPORTED_FEATURE"


def test_evaluate_score_rejects_hard_violation(dist_case: dict[str, Any]) -> None:
    dist_case["constraint_config"]["hard"] = [SUBJECT_DAY]
    p = ScheduleInput.model_validate(dist_case)
    bad = evaluate_score(p, _schedule("1-AM-1", "1-PM-1", "3-AM-1"))
    assert (bad.status, bad.schema_version) == ("INVALID_SCHEDULE", "1.1")
    assert evaluate_score(p, _schedule("1-AM-1", "2-AM-1", "3-AM-1")).status == "OK"


def test_checker_imports_no_compiler_or_solver_code() -> None:
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
