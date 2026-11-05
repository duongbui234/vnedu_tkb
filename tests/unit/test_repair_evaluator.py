"""Independent repair evaluator: hand-computed diffs, scope, limits and report checks."""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.repair import (
    ChangeStage,
    PreviousSchedule,
    RepairChange,
    RepairReport,
    RepairRequest,
)
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.validation.repair_evaluator import check_report, evaluate_repair

ROOT = Path(__file__).resolve().parents[2]


def _a(occurrence: str, slot: str, room: str | None = None) -> ScheduleAssignment:
    return ScheduleAssignment(
        occurrence_id=occurrence, slot_id=slot, room_id=room, class_ids=("c",), teacher_ids=("t",)
    )


def _previous(*assignments: ScheduleAssignment) -> PreviousSchedule:
    return PreviousSchedule(schema_version="1.0", assignments=assignments)


def _request(**update: Any) -> RepairRequest:
    data: dict[str, Any] = {
        "schema_version": "1.0",
        "change_order": "BEFORE_QUALITY",
        "max_changes": None,
        "change_scope": None,
        "use_previous_as_hint": False,
    }
    return RepairRequest.model_validate(data | update)


@pytest.fixture
def problem(quality_case: dict[str, Any]) -> ScheduleInput:
    # r::1 is a double, r::2 and r::3 are singles.
    return ScheduleInput.model_validate(quality_case)


def test_hand_computed_diff(problem: ScheduleInput) -> None:
    previous = _previous(_a("r::1", "1-AM-1"), _a("r::2", "1-AM-3"), _a("old::1", "2-AM-1"))
    assignments = (_a("r::1", "1-AM-1"), _a("r::2", "1-PM-1"), _a("r::3", "2-AM-1"))
    e = evaluate_repair(problem, previous, _request(), assignments)
    assert e.status == "OK"
    assert (e.matched, e.new, e.dropped, e.changed, e.unchanged) == (2, 1, 1, 1, 1)
    assert (e.slot_changes, e.room_only_changes, e.frozen) == (1, 0, 0)
    assert e.new_occurrence_ids == ("r::3",)
    assert e.dropped_occurrence_ids == ("old::1",)
    assert e.changes == (("r::2", "1-AM-3", None, "1-PM-1", None),)
    assert e.frozen_violations == () and e.max_changes_ok


def test_room_only_change_and_double_count_once(problem: ScheduleInput) -> None:
    previous = _previous(_a("r::1", "1-AM-1", "x"), _a("r::2", "1-AM-3", "x"))
    assignments = (_a("r::1", "1-PM-1", "x"), _a("r::2", "1-AM-3", "y"), _a("r::3", "2-AM-1"))
    e = evaluate_repair(problem, previous, _request(), assignments)
    assert (e.changed, e.slot_changes, e.room_only_changes) == (2, 1, 1)


def test_scope_freezes_and_limit(problem: ScheduleInput) -> None:
    previous = _previous(_a("r::1", "1-AM-1"), _a("r::2", "2-AM-3"))
    moved = (_a("r::1", "1-PM-1"), _a("r::2", "2-AM-2"), _a("r::3", "2-AM-1"))
    # Only day 2 may change: r::1 (previously on day 1) is frozen and must not move.
    e = evaluate_repair(problem, previous, _request(change_scope={"days": [2]}), moved)
    assert e.frozen == 1 and e.frozen_violations == ("r::1",)
    by_teacher = evaluate_repair(
        problem, previous, _request(change_scope={"teacher_ids": ["t"]}), moved
    )
    assert by_teacher.frozen == 0 and by_teacher.frozen_violations == ()
    other = evaluate_repair(
        problem, previous, _request(change_scope={"class_ids": ["other"]}), moved
    )
    assert other.frozen == 2 and set(other.frozen_violations) == {"r::1", "r::2"}
    limited = evaluate_repair(problem, previous, _request(max_changes=1), moved)
    assert not limited.max_changes_ok


@pytest.mark.parametrize(
    "assignments",
    [
        (_a("r::1", "1-AM-1"), _a("r::2", "1-AM-3")),
        (_a("r::1", "1-AM-1"), _a("r::2", "1-AM-3"), _a("r::3", "1-PM-1"), _a("r::3", "2-PM-1")),
        (_a("r::1", "1-AM-1"), _a("r::2", "1-AM-3"), _a("r::9", "1-PM-1")),
    ],
)
def test_incomplete_or_unknown_assignments_are_rejected(
    problem: ScheduleInput, assignments: tuple[ScheduleAssignment, ...]
) -> None:
    e = evaluate_repair(problem, _previous(), _request(), assignments)
    assert e.status == "INPUT_INVALID"


def _report(**update: Any) -> RepairReport:
    data: dict[str, Any] = dict(
        change_order="BEFORE_QUALITY",
        max_changes=None,
        change_scope=None,
        matched=2,
        new=1,
        dropped=1,
        changed=1,
        slot_changes=1,
        room_only_changes=0,
        unchanged=1,
        frozen=0,
        forced=0,
        changes=(
            RepairChange(
                occurrence_id="r::2",
                previous_slot_id="1-AM-3",
                previous_room_id=None,
                slot_id="1-PM-1",
                room_id=None,
            ),
        ),
        new_occurrence_ids=("r::3",),
        dropped_occurrence_ids=("old::1",),
        change_stage=ChangeStage(),
        min_changes_proved=False,
    )
    return RepairReport.model_validate(data | update)


def test_check_report_accepts_match_and_flags_mismatch(problem: ScheduleInput) -> None:
    previous = _previous(_a("r::1", "1-AM-1"), _a("r::2", "1-AM-3"), _a("old::1", "2-AM-1"))
    assignments = (_a("r::1", "1-AM-1"), _a("r::2", "1-PM-1"), _a("r::3", "2-AM-1"))
    e = evaluate_repair(problem, previous, _request(), assignments)
    assert check_report(e, _report()) == ()
    forced = _report(
        forced=1,
        changes=(
            RepairChange(
                occurrence_id="r::2",
                previous_slot_id="1-AM-3",
                previous_room_id=None,
                slot_id="1-PM-1",
                room_id=None,
                forced="DOMAIN",
            ),
        ),
    )
    # The solver-side forced reason is not recomputed, only that it is a real change.
    assert check_report(e, forced) == ()
    wrong_target = _report(
        changes=(
            RepairChange(
                occurrence_id="r::2",
                previous_slot_id="1-AM-3",
                previous_room_id=None,
                slot_id="2-PM-1",
                room_id=None,
            ),
        )
    )
    assert check_report(e, wrong_target) == ("CHANGES",)
    assert "COUNTS" in check_report(e, _report(dropped=0, dropped_occurrence_ids=(), matched=2))
    frozen_e = evaluate_repair(
        problem, previous, _request(change_scope={"class_ids": ["other"]}), assignments
    )
    assert "FROZEN_VIOLATION" in check_report(frozen_e, _report())


def test_evaluator_never_imports_solver_or_compilers() -> None:
    script = """
import builtins
original = builtins.__import__
blocked = ('ortools', 'tkb_core.solver', 'tkb_core.constraints', 'tkb_core.preprocessing',
           'tkb_core.repair')
def guarded(name, *args, **kwargs):
    if name.startswith(blocked):
        raise ImportError('forbidden import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from tkb_core.validation.repair_evaluator import evaluate_repair, check_report
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
