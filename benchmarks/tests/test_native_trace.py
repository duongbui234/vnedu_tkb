"""Native-call tracing is observational and retains partial failures."""

import json
from pathlib import Path
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions


def test_native_trace_preserves_model_parameters_and_result(tmp_path: Path) -> None:
    from ortools.sat.python import cp_model

    from benchmarks.native_trace import trace_calls
    from tkb_core.solver import objectives

    fixture = Path("tests/fixtures/quality/priority_tradeoff.json")
    problem = ScheduleInput.model_validate_json(fixture.read_text())
    options = SolveOptions(time_limit_seconds=5.0)
    original_stage, original_solve = objectives._run_stage, cp_model.CpSolver.solve
    plain = solve(problem, options)
    path = tmp_path / "native-calls.jsonl"
    with trace_calls(path):
        traced = solve(problem, options)
    assert cp_model.CpSolver.solve is original_solve and objectives._run_stage is original_stage
    assert traced.assignments == plain.assignments
    assert traced.quality.score == plain.quality.score and traced.status == plain.status
    model = cp_model.CpModel()
    choice = model.new_bool_var("opaque")
    model.add_hint(choice, 1)
    model.minimize(choice)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    solver.parameters.max_time_in_seconds = 5.0
    before = str(model.proto), str(solver.parameters)
    with trace_calls(tmp_path / "model-check.jsonl"):
        solver.solve(model)
    assert (str(model.proto), str(solver.parameters)) == before
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    starts = [r for r in rows if r["event"] == "native_start"]
    ends = [r for r in rows if r["event"] == "native_end"]
    assert starts and len(starts) == len(ends)
    for start, end in zip(starts, ends, strict=True):
        assert start["call"] == end["call"]
        assert start["workers"] == 1 and start["seed"] == 42
        assert 0 < start["budget"] <= 5.0
        assert end["monotonic"] >= start["monotonic"]
        assert end["deterministic_time"] >= 0 and end["response_stats"]
        assert start["parameters_before"] == end["parameters_after"]
    assert [r for r in rows if r["event"] == "stage_end"]


def test_native_trace_keeps_exception_and_restores_methods(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from ortools.sat.python import cp_model

    from benchmarks.native_trace import trace_calls

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("native failure")

    monkeypatch.setattr(cp_model.CpSolver, "solve", fail)
    path = tmp_path / "partial.jsonl"
    model = cp_model.CpModel()
    with pytest.raises(RuntimeError, match="native failure"), trace_calls(path):
        cp_model.CpSolver().solve(model)
    assert cp_model.CpSolver.solve is fail
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [r["event"] for r in rows] == ["native_start", "native_error"]
    assert rows[-1]["error_type"] == "RuntimeError"
    with pytest.raises(FileExistsError), trace_calls(path):
        pytest.fail("Must never overwrite an existing trace")
