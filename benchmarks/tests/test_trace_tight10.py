"""Trace preparation and instrumentation contracts; native solver construction is forbidden."""

import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from ortools.sat.python import cp_model
from ortools.sat.python.cp_model_helper import SatParameters

from benchmarks import trace_tight10 as trace
from tkb_core.contracts.input import ScheduleInput
from tkb_core.solver.options import SolveOptions


@pytest.fixture(autouse=True)
def no_native_solver(monkeypatch):
    monkeypatch.setattr(cp_model, "CpSolver", Mock(side_effect=AssertionError("NATIVE_FORBIDDEN")))


def identity():
    return {
        "schema_version": "1.0",
        "dataset_id": "c10-tight-s101",
        "input_sha256": trace.INPUT_SHA,
        "witness_sha256": trace.WITNESS_SHA,
        "model_sha256": trace.MODEL_SHA,
        "runtime": {"unit": True},
        "machine": {"mem_total": "current"},
        "source_ids": {"unit": "a" * 64},
        "driver_sha256": "b" * 64,
        "options": SolveOptions().model_dump(mode="json"),
        "limits": {"watchdog_seconds": 150.0, "max_resident_bytes": 1024**3},
        "logging": trace.LOGGING,
    }


@pytest.fixture
def prepared_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        trace,
        "_target",
        lambda: (
            SimpleNamespace(bundle_dir=tmp_path / "bundle", preflight_dir=tmp_path / "preflight"),
            None,
        ),
    )
    monkeypatch.setattr(trace, "capture_identity", lambda: identity())
    monkeypatch.setattr(
        trace,
        "legacy_comparison",
        lambda i: (
            "BLOCKED_MACHINE_DRIFT",
            {"machine.mem_total": {"frozen": "old", "current": "current"}},
        ),
    )
    root = tmp_path / "trace"
    result = trace.prepare_trace(root, "unit-trace")
    assert result["status"] == "PREPARED_NOT_AUTHORIZED"
    return root


def test_prepare_never_constructs_solver(prepared_root):
    assert cp_model.CpSolver.call_count == 0
    data = json.loads((prepared_root / "candidate-baseline.json").read_text())
    assert data["status"] == "PREPARED_NOT_AUTHORIZED"
    assert data["legacy_gate"] == "BLOCKED_MACHINE_DRIFT"
    assert not (prepared_root / "authorization.json").exists()
    assert not (prepared_root / "attempt").exists()


def test_legacy_memtotal_drift_needs_explicit_new_baseline(prepared_root):
    data = trace.Candidate.model_validate_json(
        (prepared_root / "candidate-baseline.json").read_text()
    )
    assert data.legacy_differences["machine.mem_total"]["current"] == "current"
    with pytest.raises((OSError, ValueError)):
        trace.check_authorization(prepared_root, prepared_root / "missing.json")


def test_prepare_is_exclusive_and_capture_error_is_blocked(prepared_root, tmp_path, monkeypatch):
    before = (prepared_root / "candidate-baseline.json").read_bytes()
    with pytest.raises(FileExistsError):
        trace.prepare_trace(prepared_root, "unit-trace")
    assert (prepared_root / "candidate-baseline.json").read_bytes() == before
    monkeypatch.setattr(trace, "capture_identity", Mock(side_effect=ValueError("RUNTIME_DRIFT")))
    root = tmp_path / "blocked"
    assert trace.prepare_trace(root, "blocked")["status"] == "BLOCKED"
    assert not (root / "candidate-baseline.json").exists()


@pytest.mark.parametrize(
    "path",
    [
        ("runtime", "unit"),
        ("model_sha256",),
        ("driver_sha256",),
        ("machine", "mem_total"),
        ("options", "seed"),
    ],
)
def test_runtime_or_model_drift_blocks(path):
    before = identity()
    after = copy.deepcopy(before)
    obj = after
    for p in path[:-1]:
        obj = obj[p]
    obj[path[-1]] = "different"
    assert ".".join(path) in trace.compare_identity(before, after)


def test_compare_distinguishes_missing_null_and_bool_number():
    assert trace.compare_identity({"a": None}, {}) == ("a",)
    assert trace.compare_identity({"a": True}, {"a": 1}) == ("a",)


def authorize(root):
    candidate = json.loads((root / "candidate-baseline.json").read_text())
    path = root / "approval.json"
    data = {
        "schema_version": "1.0",
        "approved": True,
        "action": "RUN_ONE_FEASIBILITY_TRACE",
        "baseline_sha256": trace.runner._sha(root / "candidate-baseline.json"),
        "run_id": candidate["run_id"],
        "output_root": str(root.resolve()),
    }
    path.write_text(json.dumps(data))
    return path


def test_approved_snapshot_new_drift_blocks(prepared_root, monkeypatch):
    approval = authorize(prepared_root)
    trace.check_authorization(prepared_root, approval)
    changed = identity()
    changed["machine"]["mem_total"] = "new"
    monkeypatch.setattr(trace, "capture_identity", lambda: changed)
    with pytest.raises(ValueError, match="IDENTITY_DRIFT"):
        trace.check_authorization(prepared_root, approval)


@pytest.mark.parametrize(
    "field,value",
    [("schema_version", "2.0"), ("unknown", True), ("approved", False), ("run_id", "other")],
)
def test_authorization_is_strict(prepared_root, field, value):
    approval = authorize(prepared_root)
    data = json.loads(approval.read_text())
    data[field] = value
    approval.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        trace.check_authorization(prepared_root, approval)


def test_missing_approval_or_owner_prevents_spawn(prepared_root, monkeypatch, capsys):
    monkeypatch.setattr(
        trace.runner, "supervise_linux", Mock(side_effect=AssertionError("SPAWN_FORBIDDEN"))
    )
    assert (
        trace.main(
            ["run", "--root", str(prepared_root), "--authorization", str(prepared_root / "missing")]
        )
        == 2
    )
    assert cp_model.CpSolver.call_count == 0
    capsys.readouterr()


def test_direct_child_requires_matching_parent_lease_and_authorization(prepared_root, monkeypatch):
    approval = authorize(prepared_root)
    monkeypatch.setattr(trace.runner, "_OWNER_ROOT", prepared_root / "owner")
    with pytest.raises((OSError, ValueError)):
        trace.check_authorization(prepared_root, approval, child=True)


def test_start_marker_or_attempt_blocks_reexecution(prepared_root):
    approval = authorize(prepared_root)
    (prepared_root / "START.json").write_text("{}")
    with pytest.raises(ValueError, match="ALREADY_STARTED"):
        trace.check_authorization(prepared_root, approval)


class FakeSolver:
    instances = []
    status_code = 0
    messages = ["Starting presolve at 0.00s\n", "Starting search at 0.01s\n"]

    def __init__(self):
        self.parameters = SatParameters()
        self.log_callback = None
        self.wall_time = 0.02
        self.response_proto = SimpleNamespace(num_restarts=0)
        self.num_branches = 3
        self.num_conflicts = 1
        self.num_booleans = 4
        self.num_binary_propagations = 6
        self.num_integer_propagations = 7
        self.deterministic_time = 0.001
        self.user_time = 0.01
        self.calls = 0
        self.instances.append(self)

    def solve(self, model):
        self.calls += 1
        for message in self.messages:
            self.log_callback(message)
        return self.status_code

    def response_stats(self):
        return "fake response, no native search"


@pytest.fixture
def stage_inputs(monkeypatch):
    FakeSolver.instances = []
    monkeypatch.setattr(cp_model, "CpSolver", FakeSolver)
    monkeypatch.setattr(trace, "model_hash", lambda built: trace.MODEL_SHA)
    problem = ScheduleInput.model_validate(
        {
            "schema_version": "1.1",
            "school": {"school_id": "unit", "academic_year": "unit", "term": "unit"},
            "classes": [],
            "teachers": [],
            "subjects": [],
            "time_slots": [],
            "teaching_requirements": [],
            "constraint_config": {"policy_version": "0.1", "hard": [], "soft": []},
        }
    )
    prepared = SimpleNamespace(normalized=SimpleNamespace(problem=problem, occurrences=()))
    built = SimpleNamespace(model=cp_model.CpModel(), variables={})
    compiled = SimpleNamespace(rules=(), tiers={})
    return prepared, built, compiled


def test_only_one_feasibility_call_and_parameters_unchanged(stage_inputs, tmp_path):
    result = trace.trace_feasibility(*stage_inputs, SolveOptions(), tmp_path / "trace.log")
    assert result["raw_solver_status"] == "UNKNOWN"
    assert result["constructor_calls"] == result["solve_calls"] == 1
    solver = FakeSolver.instances[0]
    assert solver.calls == 1 and cp_model.CpSolver is FakeSolver
    assert solver.parameters.max_time_in_seconds == 60.0
    assert solver.parameters.num_search_workers == 1 and solver.parameters.random_seed == 42
    assert solver.parameters.relative_gap_limit == solver.parameters.absolute_gap_limit == 0
    assert solver.parameters.log_search_progress and not solver.parameters.log_to_stdout
    assert not solver.parameters.log_to_response
    assert result["assignments"] == [] and result["optimal_prefix"] == []


def test_callback_error_and_truncated_log_remain_incomplete(stage_inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(trace, "write_log_chunk", Mock(side_effect=OSError("unit write failure")))
    result = trace.trace_feasibility(*stage_inputs, SolveOptions(), tmp_path / "trace.log")
    assert not result["trace_complete"] and result["phase"] == "UNDETERMINED"
    assert result["assignments"] == [] and cp_model.CpSolver is FakeSolver
    assert trace.classify_trace("Starting presolve at 0.00s\n", 0, True) == "UNDETERMINED"


def test_zero_branches_is_not_presolve_proof():
    assert trace.classify_trace("", 0, True) == "UNDETERMINED"
    assert trace.classify_trace("Starting search at 1.0s", 0, True) == "SEARCH_ENTERED"
    assert trace.classify_trace("", 3, True) == "SEARCH_ENTERED"
    assert trace.classify_trace("Starting search at 1.0s", 3, False) == "UNDETERMINED"


def test_unknown_and_feasibility_optimal_have_no_quality_proof(stage_inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(FakeSolver, "status_code", 4)
    result = trace.trace_feasibility(*stage_inputs, SolveOptions(), tmp_path / "trace.log")
    assert result["raw_solver_status"] == "OPTIMAL"
    assert result["valid_schedule"] and result["score"]["tiers"] == [0, 0, 0]
    assert result["optimal_prefix"] == [] and not result["quality_proved"]


def test_no_schedule_on_independent_mismatch(stage_inputs, tmp_path, monkeypatch):
    from tkb_core.validation import independent_validator

    monkeypatch.setattr(FakeSolver, "status_code", 4)
    monkeypatch.setattr(
        independent_validator, "validate_schedule", lambda *a: SimpleNamespace(valid=False)
    )
    result = trace.trace_feasibility(*stage_inputs, SolveOptions(), tmp_path / "trace.log")
    assert result["correctness"] == "FAIL" and not result["valid_schedule"]
    assert result["assignments"] == [] and result["score"] is None


def test_candidate_rejects_unknown_or_changed_budget(prepared_root):
    data = json.loads((prepared_root / "candidate-baseline.json").read_text())
    data["identity"]["options"]["time_limit_seconds"] = 61.0
    with pytest.raises(ValueError):
        trace.Candidate.model_validate(data)


def test_capture_identity_blocks_constructor_and_requires_installed_runtime(tmp_path, monkeypatch):
    plan = SimpleNamespace(
        preflight_dir=tmp_path, runtime_identity={"unit": True}, source_ids={"unit": "a" * 64}
    )
    monkeypatch.setattr(trace, "_target", lambda: (plan, None))
    monkeypatch.setattr(trace.runner, "_runtime_identity", lambda **kw: plan.runtime_identity)
    monkeypatch.setattr(trace.runner, "_source_ids", lambda: plan.source_ids)
    monkeypatch.setattr(trace.runner, "_machine_identity", lambda: {"unit": True})

    def build():
        assert isinstance(cp_model.CpSolver, Mock)
        assert str(cp_model.CpSolver.side_effect) == "SEARCH_FORBIDDEN"

    monkeypatch.setattr(trace, "_build_target", build)
    assert trace.capture_identity()["runtime"] == {"unit": True}
    assert cp_model.CpSolver.call_count == 0
    monkeypatch.setattr(
        trace.runner,
        "_runtime_identity",
        Mock(side_effect=ValueError("EDITABLE_PACKAGE_NOT_ALLOWED")),
    )
    with pytest.raises(ValueError, match="EDITABLE"):
        trace.capture_identity()


def test_unplanned_parameters_are_rejected_before_solve(stage_inputs, tmp_path, monkeypatch):
    class ChangedSolver(FakeSolver):
        def __init__(self):
            super().__init__()
            self.parameters.stop_after_first_solution = True

    monkeypatch.setattr(cp_model, "CpSolver", ChangedSolver)
    result = trace.trace_feasibility(*stage_inputs, SolveOptions(), tmp_path / "trace.log")
    assert not result["trace_complete"] and "PARAMETER" in result["error"]
    assert FakeSolver.instances[0].calls == 0
    assert cp_model.CpSolver is ChangedSolver


def test_second_constructor_is_rejected_and_patch_restored(stage_inputs, tmp_path, monkeypatch):
    from tkb_core.solver import objectives

    def twice(*args):
        cp_model.CpSolver()
        cp_model.CpSolver()

    monkeypatch.setattr(objectives, "_run_stage", twice)
    result = trace.trace_feasibility(*stage_inputs, SolveOptions(), tmp_path / "trace.log")
    assert "MULTIPLE_SOLVER_CONSTRUCTORS" in result["error"]
    assert len(FakeSolver.instances) == 1 and cp_model.CpSolver is FakeSolver


def test_log_is_exclusive_and_reordered_markers_are_not_proof(stage_inputs, tmp_path):
    path = tmp_path / "trace.log"
    path.write_text("preserve")
    with pytest.raises(FileExistsError):
        trace.trace_feasibility(*stage_inputs, SolveOptions(), path)
    assert path.read_text() == "preserve"
    assert (
        trace.classify_trace("Starting search at 1s\nStarting presolve at 2s", 0, True)
        == "UNDETERMINED"
    )


def test_valid_child_lease_is_checked_before_any_solver(prepared_root, monkeypatch):
    approval = authorize(prepared_root)
    owner = prepared_root / "owner"
    owner.mkdir()
    monkeypatch.setattr(trace.runner, "_OWNER_ROOT", owner)
    monkeypatch.setattr(trace.os, "getppid", lambda: 321)
    (owner / "active.json").write_text(
        json.dumps(
            {
                "state": "RUNNING",
                "pid": 321,
                "campaign_root": str(prepared_root.resolve()),
                "campaign_id": "unit-trace",
            }
        )
    )
    (prepared_root / "START.json").write_text(
        json.dumps(
            {
                "parent_pid": 321,
                "run_id": "unit-trace",
                "baseline_sha256": trace.runner._sha(prepared_root / "candidate-baseline.json"),
            }
        )
    )
    assert trace.check_authorization(prepared_root, approval, child=True).run_id == "unit-trace"
    assert cp_model.CpSolver.call_count == 0


@pytest.mark.parametrize("blocked", ["headroom", "owner", "reap"])
def test_admission_owner_and_unconfirmed_reap_keep_protocol(prepared_root, monkeypatch, blocked):
    approval = authorize(prepared_root)
    owner = prepared_root / "owner"
    monkeypatch.setattr(trace.runner, "_OWNER_ROOT", owner)
    if blocked == "owner":
        owner.mkdir()
        (owner / "active.json").write_text(json.dumps({"state": "NEEDS_REVIEW"}))

    def headroom(cap):
        return trace.runner.HeadroomCheck(
            status="BLOCKED" if blocked == "headroom" else "PASS",
            target_bytes=cap,
            required_bytes=cap + 2 * 1024**3,
            available_bytes=4 * 1024**3,
            host_available_bytes=4 * 1024**3,
            reason="UNIT" if blocked == "headroom" else None,
        )

    monkeypatch.setattr(trace.runner, "check_headroom", headroom)
    monkeypatch.setattr(trace.shutil, "disk_usage", lambda p: SimpleNamespace(free=1024**3))
    calls = []

    def supervise(argv, run_dir, limits):
        calls.append(argv)
        run_dir.mkdir()
        return trace.runner.ExecutionRecord(
            argv=argv,
            run_dir=run_dir,
            stdout_path=run_dir / "stdout.json",
            stderr_path=run_dir / "stderr.txt",
            pid=123,
            raw_wait_status=0,
            exit_code=0,
            measurement_status="BLOCKED",
            measurement_reason="REAP_UNCONFIRMED",
        )

    monkeypatch.setattr(trace.runner, "supervise_linux", supervise)
    if blocked == "owner":
        with pytest.raises(ValueError, match="STALE"):
            trace._run_parent(prepared_root, approval)
        assert not calls
    else:
        result = trace._run_parent(prepared_root, approval)
        if blocked == "headroom":
            assert result["status"] == "BLOCKED" and not calls
        else:
            assert len(calls) == 1
            assert json.loads((owner / "active.json").read_text())["state"] == "NEEDS_REVIEW"
            assert result["harness_status"] != "COMPLETE"


def test_no_response_fields_are_null_with_reason(stage_inputs, tmp_path, monkeypatch):
    class NoResponse(FakeSolver):
        def solve(self, model):
            raise RuntimeError("unit no response")

        @property
        def response_proto(self):
            raise RuntimeError("No response")

        @response_proto.setter
        def response_proto(self, v):
            pass

    monkeypatch.setattr(cp_model, "CpSolver", NoResponse)
    result = trace.trace_feasibility(*stage_inputs, SolveOptions(), tmp_path / "trace.log")
    assert result["counters"]["num_branches"] is None
    assert result["response_reason"] == "NO_RESPONSE"


@pytest.mark.parametrize("failure", ["close", "read"])
def test_log_close_or_read_failure_retains_incomplete_response(
    stage_inputs, tmp_path, monkeypatch, failure
):
    path = tmp_path / "trace.log"
    path_type = type(path)
    original_open, original_read = path_type.open, path_type.read_text
    if failure == "close":

        class CloseFailure:
            def __init__(self, handle):
                self.handle = handle

            def __enter__(self):
                return self.handle

            def __exit__(self, *args):
                self.handle.close()
                raise OSError("UNIT_LOG_CLOSE")

        def open_file(p, *args, **kwargs):
            handle = original_open(p, *args, **kwargs)
            return CloseFailure(handle) if p == path and args and args[0] == "x" else handle

        monkeypatch.setattr(path_type, "open", open_file)
    else:

        def read_file(p, *args, **kwargs):
            if p == path:
                raise OSError("UNIT_LOG_READ")
            return original_read(p, *args, **kwargs)

        monkeypatch.setattr(path_type, "read_text", read_file)
    result = trace.trace_feasibility(*stage_inputs, SolveOptions(), path)
    assert not result["trace_complete"] and result["phase"] == "UNDETERMINED"
    assert result["raw_solver_status"] == "UNKNOWN"
    assert result["response"] is not None and result["parameters"] is not None
    assert "UNIT_LOG_" in result["error"]
    assert not result["valid_schedule"] and result["assignments"] == []
    assert cp_model.CpSolver is FakeSolver
