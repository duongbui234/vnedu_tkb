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
            if self.log_callback is not None:
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


@pytest.fixture
def pair_root(prepared_root, tmp_path):
    root = tmp_path / "pair"
    result = trace.prepare_pair(root, "unit-pair")
    assert result["status"] == "PREPARED_NOT_AUTHORIZED"
    return root


def pair_approval(root):
    path = root / "user-pair-approval.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "approved": True,
                "action": "RUN_ONE_LOGGING_PAIR",
                "baseline_sha256": trace.runner._sha(root / "pair-candidate.json"),
                "pair_id": "unit-pair",
                "output_root": str(root.resolve()),
                "run_ids": ["unit-pair-off", "unit-pair-on"],
                "order": ["logging_off", "logging_on"],
            }
        )
    )
    return path


def test_pair_exact_members_and_off_on_order(pair_root):
    data = json.loads((pair_root / "pair-candidate.json").read_text())
    assert data["order"] == ["logging_off", "logging_on"]
    assert data["run_ids"] == ["unit-pair-off", "unit-pair-on"]
    assert data["run_paths"] == ["runs/01-off", "runs/02-on"]
    for field, value in [
        ("order", ["logging_on", "logging_off"]),
        ("run_ids", ["unit-pair-off", "unit-pair-on", "extra"]),
        ("run_paths", ["../escape", "runs/02-on"]),
        ("schema_version", "2.0"),
        ("unknown", True),
        ("pair_id", "a" * 61),
    ]:
        changed = copy.deepcopy(data)
        changed[field] = value
        with pytest.raises(ValueError):
            trace.PairCandidate.model_validate(changed)


def test_common_identity_and_model_equal_profile_difference_only(pair_root, stage_inputs, tmp_path):
    data = json.loads((pair_root / "pair-candidate.json").read_text())
    assert "logging" not in data["common_identity"]
    assert data["common_identity"]["model_sha256"] == trace.MODEL_SHA
    off = trace.trace_feasibility(
        *stage_inputs, SolveOptions(), tmp_path / "off.log", logging_mode="logging_off"
    )
    on = trace.trace_feasibility(
        *stage_inputs, SolveOptions(), tmp_path / "on.log", logging_mode="logging_on"
    )
    params = []
    for solver in FakeSolver.instances[-2:]:
        p = solver.parameters
        p.log_search_progress = False
        params.append(str(p))
    assert params[0] == params[1]
    assert off["solve_calls"] == on["solve_calls"] == 1
    changed = copy.deepcopy(data)
    changed["profiles"]["logging_off"]["log_to_stdout"] = True
    with pytest.raises(ValueError):
        trace.PairCandidate.model_validate(changed)


def test_off_has_no_callback_or_log_but_validates_schedule(stage_inputs, tmp_path, monkeypatch):
    monkeypatch.setattr(FakeSolver, "status_code", 4)
    path = tmp_path / "off.log"
    result = trace.trace_feasibility(
        *stage_inputs, SolveOptions(), path, logging_mode="logging_off"
    )
    assert result["stage_complete"] and result["trace_complete"] is None
    assert result["trace_capture_status"] == "DISABLED"
    assert result["missing_log_reason"] == "LOGGING_DISABLED" and not path.exists()
    assert FakeSolver.instances[-1].log_callback is None
    assert result["correctness"] == "PASS" and result["valid_schedule"]
    assert result["score"]["tiers"] == [0, 0, 0]
    assert not result["quality_proved"] and result["optimal_prefix"] == []
    from tkb_core.validation import independent_validator

    monkeypatch.setattr(
        independent_validator, "validate_schedule", lambda *a: SimpleNamespace(valid=False)
    )
    bad = trace.trace_feasibility(*stage_inputs, SolveOptions(), path, logging_mode="logging_off")
    assert bad["correctness"] == "FAIL" and bad["score"] is None


def test_off_unknown_is_complete_measurement_not_infeasible(stage_inputs, tmp_path):
    result = trace.trace_feasibility(
        *stage_inputs, SolveOptions(), tmp_path / "off.log", logging_mode="logging_off"
    )
    assert result["raw_solver_status"] == "UNKNOWN" and result["stage_complete"]
    assert result["correctness"] == "NOT_ASSESSED" and result["score"] is None
    assert result["response"] and result["counters"]["num_branches"] == 3
    assert result["phase"] == "SEARCH_ENTERED"
    assert result["elapsed_to_search_marker_seconds"] is None
    assert result["search_marker_reason"] == "LOGGING_DISABLED"


def test_on_close_read_error_preserves_response(stage_inputs, tmp_path, monkeypatch):
    path = tmp_path / "on.log"
    old = type(path).read_text

    def read(p, *a, **kw):
        if p == path:
            raise OSError("UNIT_READ")
        return old(p, *a, **kw)

    monkeypatch.setattr(type(path), "read_text", read)
    result = trace.trace_feasibility(*stage_inputs, SolveOptions(), path, logging_mode="logging_on")
    assert result["stage_complete"] and result["trace_capture_status"] == "FAILED"
    assert not result["trace_complete"] and result["response"]
    assert not result["valid_schedule"]


def test_single_authorization_cannot_authorize_pair(pair_root, prepared_root):
    with pytest.raises(ValueError):
        trace.check_pair_authorization(pair_root, authorize(prepared_root))


def test_pair_scope_and_started_member_cannot_be_reused(pair_root):
    approval = pair_approval(pair_root)
    assert trace.check_pair_authorization(pair_root, approval).pair_id == "unit-pair"
    data = json.loads(approval.read_text())
    for field, value in [
        ("output_root", str(pair_root / "elsewhere")),
        ("run_ids", ["other-off", "other-on"]),
        ("order", ["logging_on", "logging_off"]),
        ("baseline_sha256", "0" * 64),
    ]:
        changed = data | {field: value}
        approval.write_text(json.dumps(changed))
        with pytest.raises(ValueError):
            trace.check_pair_authorization(pair_root, approval)
    approval.write_text(json.dumps(data))
    (pair_root / "runs/01-off").mkdir(parents=True)
    with pytest.raises(ValueError, match="ALREADY_STARTED"):
        trace.check_pair_authorization(pair_root, approval)


@pytest.mark.parametrize("field", ["machine", "driver_sha256", "options", "logging"])
def test_common_or_profile_drift_blocks(pair_root, monkeypatch, field):
    approval = pair_approval(pair_root)
    changed = copy.deepcopy(identity())
    changed[field] = {"unexpected": True} if field != "driver_sha256" else "c" * 64
    monkeypatch.setattr(trace, "capture_identity", lambda: changed)
    with pytest.raises(ValueError):
        trace.check_pair_authorization(pair_root, approval)


def context(ac=True):
    return {
        "timestamp_utc": "2026-10-27T00:00:00+00:00",
        "load_average": None,
        "load_status": "UNKNOWN",
        "power": {"AC": {"type": "Mains", "online": "1"}} if ac else {"status": "UNKNOWN"},
        "workload_control": "UNCONTROLLED",
        "competing_workload": "UNKNOWN",
    }


@pytest.fixture
def pair_harness(pair_root, stage_inputs, monkeypatch):
    owner = pair_root / "test-owner"
    monkeypatch.setattr(trace.runner, "_OWNER_ROOT", owner)
    monkeypatch.setattr(trace.runner, "_operational_context", context)
    monkeypatch.setattr(
        trace.runner,
        "check_headroom",
        lambda cap: trace.runner.HeadroomCheck(
            status="PASS",
            target_bytes=cap,
            required_bytes=3 * 1024**3,
            available_bytes=4 * 1024**3,
            host_available_bytes=4 * 1024**3,
        ),
    )
    monkeypatch.setattr(trace.shutil, "disk_usage", lambda p: SimpleNamespace(free=1024**3))
    calls = []
    outcomes = []

    def supervise(argv, run_dir, limits):
        assert json.loads((owner / "active.json").read_text())["state"] == "RUNNING"
        assert limits.watchdog_seconds == 150 and limits.max_resident_bytes == 1024**3
        mode = "logging_off" if len(calls) == 0 else "logging_on"
        calls.append((argv, run_dir))
        run_dir.mkdir()
        result = trace.trace_feasibility(
            *stage_inputs, SolveOptions(), run_dir / "trace.log", logging_mode=mode
        )
        overrides = outcomes.pop(0) if outcomes else {}
        result.update(overrides.get("result", {}))
        (run_dir / "trace-result.json").write_text(json.dumps(result))
        return trace.runner.ExecutionRecord(
            argv=argv,
            run_dir=run_dir,
            stdout_path=run_dir / "stdout.json",
            stderr_path=run_dir / "stderr.txt",
            pid=123,
            raw_wait_status=0,
            exit_code=0,
            measurement_status="OK",
            measurement_reason=None,
            cpu_seconds=0.01,
            native_peak_rss_kib=100,
            peak_resident_bytes=102400,
        ).model_copy(update=overrides.get("execution", {}))

    monkeypatch.setattr(trace.runner, "supervise_linux", supervise)
    return pair_root, pair_approval(pair_root), calls, outcomes, owner


def test_ac_unknown_blocks_next_member_without_retry(pair_harness, monkeypatch):
    root, approval, calls, _, owner = pair_harness
    contexts = iter([context(), context(), context(False)])
    monkeypatch.setattr(trace.runner, "_operational_context", lambda: next(contexts))
    result = trace._run_pair_parent(root, approval)
    assert result["status"] == "PARTIAL" and len(calls) == 1
    assert result["members"][1]["status"] == "NOT_STARTED"
    assert "POWER" in result["reason"]
    assert json.loads((owner / "active.json").read_text())["state"] == "IDLE"
    with pytest.raises(ValueError, match="ALREADY_STARTED"):
        trace._run_pair_parent(root, approval)


@pytest.mark.parametrize("failure", [None, "crash", "mismatch", "capture", "infeasible", "reap"])
def test_unknown_continues_but_crash_or_mismatch_stops_pair(pair_harness, failure):
    root, approval, calls, outcomes, owner = pair_harness
    if failure == "crash":
        outcomes.append({"execution": {"signal": 9}})
    elif failure == "mismatch":
        outcomes.append({"result": {"correctness": "FAIL"}})
    elif failure == "capture":
        outcomes.append({"result": {"stage_complete": False}})
    elif failure == "infeasible":
        outcomes.append({"result": {"raw_solver_status": "INFEASIBLE", "correctness": "FAIL"}})
    elif failure == "reap":
        outcomes.append(
            {
                "execution": {
                    "measurement_status": "BLOCKED",
                    "measurement_reason": "REAP_UNCONFIRMED",
                }
            }
        )
    result = trace._run_pair_parent(root, approval)
    assert len(calls) == (1 if failure else 2)
    assert result["status"] == ("PARTIAL" if failure else "TERMINAL")
    assert result["members"][0]["raw_solver_status"] == (
        "INFEASIBLE" if failure == "infeasible" else "UNKNOWN"
    )
    assert result["members"][0]["score"] is None
    assert result["members"][1]["status"] == ("NOT_STARTED" if failure else "COMPLETE")
    state = json.loads((owner / "active.json").read_text())["state"]
    assert state == ("NEEDS_REVIEW" if failure == "reap" else "IDLE")
    assert (root / "manifest.json").exists()
    assert not (root / "runs/01-off/attempt/trace.log").exists()


def test_power_change_and_missing_metrics_keep_limitations(pair_harness, monkeypatch):
    root, approval, calls, _, _ = pair_harness
    contexts = iter([context(), context(False), context(), context()])
    monkeypatch.setattr(trace.runner, "_operational_context", lambda: next(contexts))
    result = trace._run_pair_parent(root, approval)
    assert len(calls) == 2 and result["comparability"] == "LIMITED"
    assert result["members"][0]["post_context"]["power"] == {"status": "UNKNOWN"}
    assert result["members"][0]["pre_context"]["load_average"] is None
    assert result["members"][0]["first_feasible_elapsed_seconds"] is None
    assert "ORDER_WORKLOAD_THERMAL_UNCONTROLLED_N1" in result["limitations"]


def test_prepare_pair_never_constructs_native_solver_or_approval(pair_root):
    assert cp_model.CpSolver.call_count == 0
    assert sorted(p.name for p in pair_root.iterdir()) == [
        "pair-candidate.json",
        "preparation-result.json",
    ]
    result = json.loads((pair_root / "preparation-result.json").read_text())
    assert result["search_executed"] is result["authorization_created"] is False
    assert result["candidate_sha256"] == trace.runner._sha(pair_root / "pair-candidate.json")
    with pytest.raises(FileExistsError):
        trace.prepare_pair(pair_root, "unit-pair")


def test_pair_direct_child_requires_lease_before_build(pair_root, monkeypatch):
    approval = pair_approval(pair_root)
    monkeypatch.setattr(trace, "_build_target", Mock(side_effect=AssertionError("BUILD_FORBIDDEN")))
    with pytest.raises((OSError, ValueError)):
        trace._pair_child(pair_root, approval, 0)
    assert cp_model.CpSolver.call_count == 0


def test_prepare_pair_cli_never_dispatches_solver(tmp_path, prepared_root, monkeypatch, capsys):
    root = tmp_path / "cli-pair"
    monkeypatch.setattr(
        trace.runner, "supervise_linux", Mock(side_effect=AssertionError("SPAWN_FORBIDDEN"))
    )
    assert trace.main(["prepare-pair", "--root", str(root), "--pair-id", "unit-pair"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "PREPARED_NOT_AUTHORIZED"
    assert not output["search_executed"] and not output["authorization_created"]
    assert cp_model.CpSolver.call_count == 0


def test_pair_child_profile_and_no_reentry(pair_root, stage_inputs, monkeypatch):
    approval = pair_approval(pair_root)
    owner = pair_root / "owner"
    owner.mkdir()
    monkeypatch.setattr(trace.runner, "_OWNER_ROOT", owner)
    monkeypatch.setattr(trace.os, "getppid", lambda: 321)
    monkeypatch.setattr(trace, "_build_target", lambda: stage_inputs)
    monkeypatch.setattr(trace.runner, "_operational_context", context)
    monkeypatch.setattr(trace.shutil, "disk_usage", lambda p: SimpleNamespace(free=1024**3))
    monkeypatch.setattr(
        trace.runner,
        "check_headroom",
        lambda cap: trace.runner.HeadroomCheck(
            status="PASS",
            target_bytes=cap,
            required_bytes=3 * 1024**3,
            available_bytes=4 * 1024**3,
            host_available_bytes=4 * 1024**3,
        ),
    )
    (owner / "active.json").write_text(
        json.dumps(
            {
                "state": "RUNNING",
                "pid": 321,
                "campaign_root": str(pair_root),
                "campaign_id": "unit-pair",
            }
        )
    )
    base = {
        "baseline_sha256": trace.runner._sha(pair_root / "pair-candidate.json"),
        "pair_id": "unit-pair",
        "parent_pid": 321,
    }
    (pair_root / "PAIR-START.json").write_text(json.dumps(base))
    member = pair_root / "runs/01-off"
    (member / "attempt").mkdir(parents=True)
    (member / "START.json").write_text(
        json.dumps(base | {"index": 0, "mode": "logging_off", "run_id": "unit-pair-off"})
    )
    result = trace._pair_child(pair_root, approval, 0)
    assert result["status"] == "CHILD_TERMINAL"
    saved = json.loads((member / "attempt/trace-result.json").read_text())
    assert saved["stage_complete"] and saved["logging_mode"] == "logging_off"
    assert saved["solve_calls"] == 1 and not (member / "attempt/trace.log").exists()
    assert (member / "attempt/independent-checks.json").exists()
    with pytest.raises(ValueError, match="STARTED"):
        trace._pair_child(pair_root, approval, 0)
    assert len(FakeSolver.instances) == 1


def test_off_missing_counters_are_null_with_reason(stage_inputs, tmp_path, monkeypatch):
    class MissingMetric(FakeSolver):
        def __init__(self):
            super().__init__()
            self.deterministic_time = None

    monkeypatch.setattr(cp_model, "CpSolver", MissingMetric)
    result = trace.trace_feasibility(
        *stage_inputs, SolveOptions(), tmp_path / "off.log", logging_mode="logging_off"
    )
    assert result["counters"]["deterministic_time"] is None
    assert result["counter_missing_reasons"]["deterministic_time"] == "FIELD_NOT_AVAILABLE"
    assert not (tmp_path / "off.log").exists()


def test_pair_headroom_blocks_without_starting_native_member(pair_harness, monkeypatch):
    root, approval, calls, _, _ = pair_harness
    monkeypatch.setattr(
        trace.runner,
        "check_headroom",
        lambda cap: trace.runner.HeadroomCheck(
            status="BLOCKED",
            target_bytes=cap,
            required_bytes=3 * 1024**3,
            available_bytes=0,
            host_available_bytes=0,
            reason="LOW_MEMORY",
        ),
    )
    result = trace._run_pair_parent(root, approval)
    assert result["status"] == "BLOCKED" and not calls
    assert all(row["status"] == "NOT_STARTED" for row in result["members"])
    assert not (root / "runs").exists()


def test_pair_terminal_and_manifest_bind_approved_candidate(pair_harness):
    root, approval, _, _, _ = pair_harness
    result = trace._run_pair_parent(root, approval)
    digest = trace.runner._sha(root / "pair-candidate.json")
    for index, subdir in enumerate(("01-off", "02-on")):
        terminal = json.loads((root / f"runs/{subdir}/terminal.json").read_text())
        assert terminal["baseline_sha256"] == digest
        assert terminal["pair_id"] == "unit-pair" and terminal["index"] == index
        assert terminal["parent_pid"] == trace.os.getpid()
        assert result["members"][index]["baseline_sha256"] == digest
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["baseline_sha256"] == digest and manifest["pair_id"] == "unit-pair"


def test_on_rejects_off_terminal_from_another_candidate(pair_root, monkeypatch):
    approval = pair_approval(pair_root)
    owner = pair_root / "owner"
    owner.mkdir()
    monkeypatch.setattr(trace.runner, "_OWNER_ROOT", owner)
    monkeypatch.setattr(trace.os, "getppid", lambda: 321)
    (owner / "active.json").write_text(
        json.dumps(
            {
                "state": "RUNNING",
                "pid": 321,
                "campaign_root": str(pair_root),
                "campaign_id": "unit-pair",
            }
        )
    )
    base = {
        "baseline_sha256": trace.runner._sha(pair_root / "pair-candidate.json"),
        "pair_id": "unit-pair",
        "parent_pid": 321,
    }
    (pair_root / "PAIR-START.json").write_text(json.dumps(base))
    off = pair_root / "runs/01-off"
    on = pair_root / "runs/02-on"
    off.mkdir(parents=True)
    on.mkdir()
    (on / "START.json").write_text(
        json.dumps(base | {"index": 1, "mode": "logging_on", "run_id": "unit-pair-on"})
    )
    (off / "terminal.json").write_text(
        json.dumps(
            base
            | {
                "status": "COMPLETE",
                "index": 0,
                "mode": "logging_off",
                "run_id": "unit-pair-off",
                "baseline_sha256": "0" * 64,
            }
        )
    )
    with pytest.raises(ValueError, match="PREVIOUS_MEMBER"):
        trace.check_pair_authorization(pair_root, approval, child=True, index=1)
    assert cp_model.CpSolver.call_count == 0


@pytest.mark.parametrize("mode", ["logging_off", "logging_on"])
def test_applied_callback_state_is_captured_and_drift_blocks(
    stage_inputs, tmp_path, monkeypatch, mode
):
    good = trace.trace_feasibility(
        *stage_inputs, SolveOptions(), tmp_path / "good.log", logging_mode=mode
    )
    assert good["callback_state"] == {
        "log_callback": None if mode == "logging_off" else "raw_utf8_flush",
        "best_bound_callback": False,
        "solution_callback": False,
    }

    class UnexpectedBound(FakeSolver):
        def __init__(self):
            super().__init__()
            self.best_bound_callback = lambda bound: None

    monkeypatch.setattr(cp_model, "CpSolver", UnexpectedBound)
    bad = trace.trace_feasibility(
        *stage_inputs, SolveOptions(), tmp_path / "bad.log", logging_mode=mode
    )
    assert "CALLBACK" in bad["error"] and not bad["stage_complete"]
    assert FakeSolver.instances[-1].calls == 0
    assert bad["callback_state"]["best_bound_callback"] is True


def test_unstarted_off_log_reason_is_not_logging_disabled(pair_harness, monkeypatch):
    root, approval, _, _, _ = pair_harness
    monkeypatch.setattr(trace.runner, "_operational_context", lambda: context(False))
    assert trace._run_pair_parent(root, approval)["status"] == "BLOCKED"
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["missing_logs"]["runs/01-off/attempt/trace.log"] == "NOT_STARTED"
