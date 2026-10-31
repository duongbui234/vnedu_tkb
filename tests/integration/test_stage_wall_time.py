"""Reported solver wall times come from the monotonic clock, not CP-SAT's system clock."""

import itertools
from typing import Any

import pytest
from ortools.sat.python import cp_model

from tkb_core.constraints.soft import compile_soft
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.enums import SolveStatus
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver import cp_sat, objectives
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.model_builder import build_model
from tkb_core.solver.options import SolveOptions

JUMPED = 25_000.0  # what CP-SAT reported after a +7 h system clock jump (d1b-validation-v1)
RULE = {
    "id": "rule",
    "code": "TEACHER_AVOID_SLOTS",
    "parameters": {"slot_ids": ["1-AM-1"]},
    "weight": 1,
    "priority": 1,
}


class JumpedClockSolver(cp_model.CpSolver):
    """Real search, but a wall_time as if the system clock jumped during the solve."""

    @property
    def wall_time(self) -> float:
        return JUMPED


class JumpedUnknownSolver(JumpedClockSolver):
    """Returns UNKNOWN without searching, to reach the no-solution branch."""

    def solve(self, model: Any, solution_callback: Any = None) -> Any:  # type: ignore[override]
        return cp_model.UNKNOWN


def _setup(quality_case: dict[str, Any]) -> tuple[Any, Any, Any]:
    quality_case["constraint_config"]["soft"] = [RULE]
    prepared = prepare(ScheduleInput.model_validate(quality_case))
    built = build_model(prepared)
    return prepared, built, compile_soft(prepared, built)


@pytest.mark.parametrize("solver_class", [JumpedClockSolver, JumpedUnknownSolver])
def test_stage_wall_time_is_perf_counter_around_solve(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch, solver_class: type
) -> None:
    prepared, built, compiled = _setup(quality_case)
    monkeypatch.setattr(objectives.cp_model, "CpSolver", solver_class)
    clock = itertools.count(100.0, 1.5)
    monkeypatch.setattr(objectives, "perf_counter", lambda: next(clock))
    outcome = objectives._run_stage(prepared, built, compiled, SolveOptions(), 1, 10.0)
    assert outcome.wall_time == 1.5
    if solver_class is JumpedUnknownSolver:
        assert outcome.status == SolveStatus.UNKNOWN


def test_quality_run_reports_monotonic_wall_times(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    quality_case["constraint_config"]["soft"] = [RULE]
    monkeypatch.setattr(objectives.cp_model, "CpSolver", JumpedClockSolver)
    clock = itertools.count(0.0, 0.01)
    monkeypatch.setattr(objectives, "perf_counter", lambda: next(clock))
    result = solve(
        ScheduleInput.model_validate(quality_case), SolveOptions(time_limit_seconds=10.0)
    )
    assert result.status == "OPTIMAL"
    assert result.metadata.feasibility_run.wall_time == pytest.approx(0.01)
    assert all(t.wall_time == pytest.approx(0.01) for t in result.quality.tier_runs)
    assert result.metadata.solver_wall_time is not None
    assert 0 < result.metadata.solver_wall_time < 1.0


def test_hard_only_solve_reports_monotonic_wall_time(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Without active soft tiers, solve() takes the single hard-only CP-SAT call.
    monkeypatch.setattr(cp_model, "CpSolver", JumpedClockSolver)
    clock = itertools.count(0.0, 1.0)
    monkeypatch.setattr(cp_sat, "perf_counter", lambda: next(clock))
    result = solve(ScheduleInput.model_validate(quality_case), SolveOptions(time_limit_seconds=5.0))
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.metadata.solver_wall_time == 1.0
    assert result.metadata.feasibility_run.wall_time == 1.0
