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


@pytest.fixture
def cpu_clocks(monkeypatch):
    import resource

    wall = Mock(side_effect=[10_000_000_000, 12_000_000_000])
    usage = Mock(
        side_effect=[
            SimpleNamespace(ru_utime=10.0, ru_stime=2.0),
            SimpleNamespace(ru_utime=13.0, ru_stime=3.0),
        ]
    )
    monkeypatch.setattr(trace.time, "monotonic_ns", wall)
    monkeypatch.setattr(resource, "getrusage", usage)
    return wall, usage


def test_native_cpu_user_system_delta_and_units(cpu_clocks):
    import resource

    sample = {}
    raw = trace.measure_native_call(lambda: cp_model.UNKNOWN, sample)
    assert raw is cp_model.UNKNOWN
    assert sample["measurement_status"] == "OK" and sample["reason"] is None
    assert sample["user_seconds"] == 3.0 and sample["system_seconds"] == 1.0
    assert sample["cpu_seconds"] == 4.0 and sample["wall_elapsed_seconds"] == 2.0
    assert sample["cpu_wall_ratio"] == 2.0 and sample["ratio_reason"] is None
    assert sample["call_entered"] is sample["call_returned"] is True
    assert sample["native_return_code"] == 0 and sample["native_exception"] is None
    assert sample["cpu_start"] == {"user_seconds": 10.0, "system_seconds": 2.0}
    assert all(call.args == (resource.RUSAGE_SELF,) for call in cpu_clocks[1].call_args_list)


@pytest.mark.parametrize(
    "end_cpu,wall_end,expected",
    [
        ((10.0, 2.0), 12_000_000_000, "OK"),
        ((9.0, 3.0), 12_000_000_000, "BLOCKED"),
        ((float("nan"), 3.0), 12_000_000_000, "BLOCKED"),
        ((float("inf"), 3.0), 12_000_000_000, "BLOCKED"),
        ((None, 3.0), 12_000_000_000, "BLOCKED"),
        ((13.0, 3.0), 10_000_000_000, "BLOCKED"),
    ],
)
def test_cpu_zero_missing_negative_nonfinite_and_wall_zero(cpu_clocks, end_cpu, wall_end, expected):
    wall, usage = cpu_clocks
    wall.side_effect = [10_000_000_000, wall_end]
    usage.side_effect = [
        SimpleNamespace(ru_utime=10.0, ru_stime=2.0),
        SimpleNamespace(ru_utime=end_cpu[0], ru_stime=end_cpu[1]),
    ]
    sample = {}
    assert trace.measure_native_call(lambda: cp_model.UNKNOWN, sample) is cp_model.UNKNOWN
    assert sample["measurement_status"] == expected
    if expected == "OK":
        assert sample["cpu_seconds"] == 0 and sample["cpu_wall_ratio"] == 0
    else:
        assert sample["cpu_seconds"] is sample["cpu_wall_ratio"] is None
        assert sample["reason"] and sample["ratio_reason"]
    json.dumps(sample, allow_nan=False)


@pytest.mark.parametrize("clock", ["wall", "cpu"])
def test_cpu_pre_clock_failure_never_enters_native(cpu_clocks, clock):
    cpu_clocks[0 if clock == "wall" else 1].side_effect = OSError("PRE_CLOCK")
    call = Mock(side_effect=AssertionError("NATIVE_MUST_NOT_ENTER"))
    sample = {}
    with pytest.raises(RuntimeError, match="CPU_CLOCK_PRE"):
        trace.measure_native_call(call, sample)
    assert not sample["call_entered"] and sample["native_return_code"] is None
    assert sample["measurement_status"] == "BLOCKED" and sample["cpu_seconds"] is None
    assert call.call_count == 0


@pytest.mark.parametrize("clock", ["wall", "cpu"])
def test_cpu_post_clock_failure_keeps_raw_return_and_response(
    stage_inputs, tmp_path, monkeypatch, cpu_clocks, clock
):
    monkeypatch.setattr(FakeSolver, "status_code", 4)
    target = cpu_clocks[0 if clock == "wall" else 1]
    first = 10_000_000_000 if clock == "wall" else SimpleNamespace(ru_utime=10.0, ru_stime=2.0)
    target.side_effect = [first, OSError("POST_CLOCK")]
    result = trace.trace_feasibility(
        *stage_inputs,
        SolveOptions(),
        tmp_path / "unused.log",
        logging_mode="logging_off",
        measure_cpu=True,
    )
    sample = result["native_solve_measurement"]
    assert sample["measurement_status"] == "BLOCKED" and sample["call_returned"]
    assert sample["native_return_code"] == 4 and result["raw_solver_status"] == "OPTIMAL"
    assert result["response"] and result["stage_complete"] and result["native_call_count"] == 1
    assert result["valid_schedule"] and result["correctness"] == "PASS"
    assert FakeSolver.instances[-1].calls == 1


def test_native_exception_preserves_original_and_end_attempt(cpu_clocks):
    original = ValueError("ORIGINAL_NATIVE_ERROR")
    cpu_clocks[1].side_effect = [
        SimpleNamespace(ru_utime=10.0, ru_stime=2.0),
        OSError("POST_ERROR"),
    ]
    sample = {}
    with pytest.raises(ValueError) as caught:
        trace.measure_native_call(Mock(side_effect=original), sample)
    assert caught.value is original and sample["call_entered"] and not sample["call_returned"]
    assert sample["native_exception"] == "ValueError:ORIGINAL_NATIVE_ERROR"
    assert sample["measurement_status"] == "BLOCKED" and sample["wall_end_ns"] == 12_000_000_000


def test_native_cpu_boundary_excludes_setup_decode_validation(stage_inputs, tmp_path, monkeypatch):
    import resource

    from tkb_core.validation import independent_validator, score_evaluator

    events = []
    original_validate = independent_validator.validate_schedule
    original_score = score_evaluator.evaluate_score

    def validate(*a):
        events.append("validate")
        return original_validate(*a)

    def score(*a):
        events.append("score")
        return original_score(*a)

    def wall():
        events.append("wall")
        return 1_000_000_000 if events.count("wall") == 1 else 3_000_000_000

    def cpu(who):
        events.append("cpu")
        return SimpleNamespace(ru_utime=float(events.count("cpu")), ru_stime=0.0)

    class Ordered(FakeSolver):
        status_code = 4

        def __init__(self):
            events.append("constructor")
            super().__init__()

        def solve(self, model):
            events.append("native")
            return super().solve(model)

    monkeypatch.setattr(cp_model, "CpSolver", Ordered)
    monkeypatch.setattr(
        trace, "model_hash", lambda built: events.append("guard") or trace.MODEL_SHA
    )
    monkeypatch.setattr(trace.time, "monotonic_ns", wall)
    monkeypatch.setattr(resource, "getrusage", cpu)
    monkeypatch.setattr(independent_validator, "validate_schedule", validate)
    monkeypatch.setattr(score_evaluator, "evaluate_score", score)
    result = trace.trace_feasibility(
        *stage_inputs,
        SolveOptions(),
        tmp_path / "off.log",
        logging_mode="logging_off",
        measure_cpu=True,
    )
    assert result["native_solve_measurement"]["measurement_status"] == "OK"
    start = events.index("wall")
    assert events[start:] == ["wall", "cpu", "native", "cpu", "wall", "validate", "score"]
    assert "constructor" in events[:start] and events[start - 1] == "guard"


def test_native_one_call_even_if_stage_requests_second(
    stage_inputs, tmp_path, monkeypatch, cpu_clocks
):
    from tkb_core.solver import objectives

    def twice(prepared, built, compiled, options, priority, budget):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = budget
        solver.parameters.num_search_workers = options.num_workers
        solver.parameters.random_seed = options.seed
        solver.parameters.relative_gap_limit = solver.parameters.absolute_gap_limit = 0.0
        solver.solve(built.model)
        solver.solve(built.model)

    monkeypatch.setattr(objectives, "_run_stage", twice)
    result = trace.trace_feasibility(
        *stage_inputs,
        SolveOptions(),
        tmp_path / "off.log",
        logging_mode="logging_off",
        measure_cpu=True,
    )
    assert FakeSolver.instances[-1].calls == 1 and result["native_call_count"] == 1
    assert "PARAMETER_OR_MODEL_DRIFT" in result["error"]


def test_cpu_unknown_keeps_final_counters_without_schedule(stage_inputs, tmp_path, cpu_clocks):
    result = trace.trace_feasibility(
        *stage_inputs,
        SolveOptions(),
        tmp_path / "off.log",
        logging_mode="logging_off",
        measure_cpu=True,
    )
    assert result["raw_solver_status"] == "UNKNOWN" and result["stage_complete"]
    assert result["native_solve_measurement"]["measurement_status"] == "OK"
    assert result["counters"]["num_branches"] == 3 and result["score"] is None
    assert (
        result["termination_cause"] is None and result["termination_cause_reason"] == "NOT_EXPOSED"
    )
    assert result["configured_wall_budget_seconds"] == 60.0


def test_cpu_early_solution_does_not_wait_for_deadline_and_validates_score(
    stage_inputs, tmp_path, monkeypatch, cpu_clocks
):
    monkeypatch.setattr(FakeSolver, "status_code", 4)
    result = trace.trace_feasibility(
        *stage_inputs,
        SolveOptions(),
        tmp_path / "off.log",
        logging_mode="logging_off",
        measure_cpu=True,
    )
    assert result["valid_schedule"] and result["score"]["tiers"] == [0, 0, 0]
    assert result["native_solve_measurement"]["wall_elapsed_seconds"] == 2.0
    assert result["counters"]["wall_time"] == 0.02 and not (tmp_path / "off.log").exists()


def test_cpu_missing_counter_and_no_response_reasons(
    stage_inputs, tmp_path, monkeypatch, cpu_clocks
):
    class NoResponse(FakeSolver):
        @property
        def response_proto(self):
            raise RuntimeError("NO_RESPONSE")

        @response_proto.setter
        def response_proto(self, value):
            pass

    monkeypatch.setattr(cp_model, "CpSolver", NoResponse)
    result = trace.trace_feasibility(
        *stage_inputs,
        SolveOptions(),
        tmp_path / "off.log",
        logging_mode="logging_off",
        measure_cpu=True,
    )
    assert result["response"] is None and result["response_reason"] == "NO_RESPONSE"
    assert result["counter_missing_reasons"]["num_branches"] == "NO_RESPONSE"
    assert result["counters"]["num_branches"] is None
    assert result["native_solve_measurement"]["measurement_status"] == "OK"


@pytest.fixture
def cpu_root(prepared_root, tmp_path):
    root = tmp_path / "cpu"
    result = trace.prepare_cpu(root, "unit-cpu")
    assert result["status"] == "PREPARED_NOT_AUTHORIZED"
    return root


def cpu_approval(root):
    path = root / "user-approval.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "approved": True,
                "action": "RUN_ONE_NATIVE_CPU_FEASIBILITY",
                "baseline_sha256": trace.runner._sha(root / "cpu-candidate.json"),
                "run_id": "unit-cpu",
                "output_root": str(root),
            }
        )
    )
    return path


@pytest.mark.parametrize(
    "field", ["model", "policy", "profile", "source", "options", "version", "unknown", "path"]
)
def test_cpu_policy_or_identity_drift_blocks(cpu_root, monkeypatch, field):
    approval = cpu_approval(cpu_root)
    if field == "source":
        changed = copy.deepcopy(identity())
        changed["driver_sha256"] = "c" * 64
        monkeypatch.setattr(trace, "capture_identity", lambda: changed)
        with pytest.raises(ValueError, match="DRIFT"):
            trace.check_cpu_authorization(cpu_root, approval)
        return
    path = cpu_root / "cpu-candidate.json"
    data = json.loads(path.read_text())
    if field == "model":
        data["common_identity"]["model_sha256"] = "0" * 64
    elif field == "policy":
        data["measurement_policy"]["max_native_calls"] = 2
    elif field == "profile":
        data["logging_profile"]["log_search_progress"] = True
    elif field == "options":
        data["common_identity"]["options"]["time_limit_seconds"] = 61.0
    elif field == "version":
        data["schema_version"] = "2.0"
    elif field == "unknown":
        data["extra"] = True
    elif field == "path":
        data["output_root"] = str(cpu_root / "../escape")
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        trace.check_cpu_authorization(cpu_root, approval)


def test_single_and_pair_approval_cannot_authorize_cpu(cpu_root, prepared_root, pair_root):
    for approval in (authorize(prepared_root), pair_approval(pair_root)):
        with pytest.raises(ValueError):
            trace.check_cpu_authorization(cpu_root, approval)


def test_cpu_prepare_cannot_construct_solver_or_authorize(cpu_root, monkeypatch, capsys, tmp_path):
    assert cp_model.CpSolver.call_count == 0
    assert sorted(p.name for p in cpu_root.iterdir()) == [
        "cpu-candidate.json",
        "preparation-result.json",
    ]
    result = json.loads((cpu_root / "preparation-result.json").read_text())
    assert result["candidate_sha256"] == trace.runner._sha(cpu_root / "cpu-candidate.json")
    assert not result["authorization_created"] and not result["search_executed"]
    with pytest.raises(FileExistsError):
        trace.prepare_cpu(cpu_root, "unit-cpu")
    assert (
        trace.main(["prepare-cpu", "--root", str(tmp_path / "cpu-cli"), "--run-id", "unit-cpu"])
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "PREPARED_NOT_AUTHORIZED"


@pytest.fixture
def cpu_harness(cpu_root, stage_inputs, cpu_clocks, monkeypatch):
    owner = cpu_root / "test-owner"
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
    controls = {}

    def supervise(argv, run_dir, limits):
        calls.append(argv)
        run_dir.mkdir()
        if not controls.get("kill"):
            result = trace.trace_feasibility(
                *stage_inputs,
                SolveOptions(),
                run_dir / "off.log",
                logging_mode="logging_off",
                measure_cpu=True,
            )
            result.update(controls.get("result", {}))
            (run_dir / "trace-result.json").write_text(json.dumps(result))
        record = trace.runner.ExecutionRecord(
            argv=argv,
            run_dir=run_dir,
            stdout_path=run_dir / "stdout.json",
            stderr_path=run_dir / "stderr.txt",
            pid=123,
            raw_wait_status=0,
            exit_code=0,
            cpu_seconds=4.5,
            native_peak_rss_kib=100,
            peak_resident_bytes=102400,
            measurement_status="OK",
            measurement_reason=None,
        )
        if controls.get("kill"):
            record = record.model_copy(
                update={
                    "signal": 9,
                    "exit_code": None,
                    "raw_wait_status": 9,
                    "stop_reason": "WATCHDOG",
                }
            )
        if controls.get("reap"):
            record = record.model_copy(
                update={"measurement_status": "BLOCKED", "measurement_reason": "REAP_UNCONFIRMED"}
            )
        return record

    monkeypatch.setattr(trace.runner, "supervise_linux", supervise)
    return cpu_root, cpu_approval(cpu_root), calls, controls, owner


def test_cpu_supervisor_kill_does_not_invent_native_cpu_or_count(cpu_harness):
    root, approval, calls, controls, owner = cpu_harness
    controls["kill"] = True
    result = trace._run_cpu_parent(root, approval)
    assert len(calls) == 1 and result["harness_status"] == "WATCHDOG_TIMEOUT"
    assert result["native_solve_measurement"] is None and result["native_call_count"] is None
    assert result["native_call_count_reason"] == "NOT_OBSERVABLE"
    assert result["native_capture_reason"] == "CHILD_TERMINATED_BEFORE_FINAL_CAPTURE"
    assert result["counters"]["num_branches"] is None
    assert (
        result["counter_missing_reasons"]["num_branches"] == "CHILD_TERMINATED_BEFORE_FINAL_CAPTURE"
    )
    assert result["response"] is None
    assert result["response_reason"] == "CHILD_TERMINATED_BEFORE_FINAL_CAPTURE"
    assert result["execution"]["cpu_seconds"] == 4.5
    assert json.loads((owner / "active.json").read_text())["state"] == "IDLE"


@pytest.mark.parametrize("block", ["none", "ac", "headroom", "owner", "reap", "timing"])
def test_cpu_owner_ac_headroom_reentry_and_reap(cpu_harness, monkeypatch, block):
    root, approval, calls, controls, owner = cpu_harness
    if block == "ac":
        monkeypatch.setattr(trace.runner, "_operational_context", lambda: context(False))
    elif block == "headroom":
        monkeypatch.setattr(trace.shutil, "disk_usage", lambda p: SimpleNamespace(free=0))
    elif block == "owner":
        owner.mkdir()
        (owner / "active.json").write_text(json.dumps({"state": "NEEDS_REVIEW"}))
    elif block == "reap":
        controls["reap"] = True
    elif block == "timing":
        controls["result"] = {
            "native_solve_measurement": {"measurement_status": "BLOCKED", "call_returned": True}
        }
    if block == "owner":
        with pytest.raises(ValueError, match="STALE"):
            trace._run_cpu_parent(root, approval)
        assert not calls
        return
    result = trace._run_cpu_parent(root, approval)
    assert len(calls) == (0 if block in ("ac", "headroom") else 1)
    if block == "none":
        assert result["status"] == "TERMINAL" and result["harness_status"] == "COMPLETE"
        assert result["raw_solver_status"] == "UNKNOWN" and result["score"] is None
        assert result["native_call_count"] == 1
    else:
        assert result["status"] == "BLOCKED"
    expected = "NEEDS_REVIEW" if block == "reap" else "IDLE"
    assert json.loads((owner / "active.json").read_text())["state"] == expected
    with pytest.raises(ValueError, match="ALREADY_STARTED"):
        trace._run_cpu_parent(root, approval)
    assert (root / "manifest.json").exists()


def test_cpu_direct_child_cannot_build_without_parent(cpu_root, monkeypatch):
    monkeypatch.setattr(
        trace, "_build_target", Mock(side_effect=AssertionError("UNAUTHORIZED_BUILD"))
    )
    with pytest.raises((OSError, ValueError)):
        trace._cpu_child(cpu_root, cpu_approval(cpu_root))
    assert cp_model.CpSolver.call_count == 0


@pytest.mark.parametrize("where", ["pre", "post"])
@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), None, -1])
def test_cpu_invalid_wall_snapshot_remains_json_serializable(cpu_clocks, where, invalid):
    cpu_clocks[0].side_effect = (
        [invalid, 12_000_000_000] if where == "pre" else [10_000_000_000, invalid]
    )
    sample = {}
    call = Mock(return_value=cp_model.UNKNOWN)
    if where == "pre":
        with pytest.raises(RuntimeError, match="CPU_CLOCK_PRE"):
            trace.measure_native_call(call, sample)
        assert call.call_count == 0
    else:
        assert trace.measure_native_call(call, sample) is cp_model.UNKNOWN
    assert sample["measurement_status"] == "BLOCKED"
    json.dumps(sample, allow_nan=False)


def test_cpu_ratio_overflow_is_blocked_without_losing_native_return(cpu_clocks):
    cpu_clocks[0].side_effect = [1, 2]
    cpu_clocks[1].side_effect = [
        SimpleNamespace(ru_utime=0.0, ru_stime=0.0),
        SimpleNamespace(ru_utime=1e308, ru_stime=0.0),
    ]
    sample = {}
    assert trace.measure_native_call(lambda: cp_model.UNKNOWN, sample) is cp_model.UNKNOWN
    assert sample["measurement_status"] == "BLOCKED" and sample["cpu_wall_ratio"] is None
    json.dumps(sample, allow_nan=False)


def test_cpu_child_success_and_reentry_are_guarded(cpu_root, stage_inputs, cpu_clocks, monkeypatch):
    approval = cpu_approval(cpu_root)
    owner = cpu_root / "owner"
    owner.mkdir()
    monkeypatch.setattr(trace.runner, "_OWNER_ROOT", owner)
    monkeypatch.setattr(trace.os, "getppid", lambda: 321)
    monkeypatch.setattr(trace, "_build_target", lambda: stage_inputs)
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
    (owner / "active.json").write_text(
        json.dumps(
            {
                "state": "RUNNING",
                "pid": 321,
                "campaign_root": str(cpu_root),
                "campaign_id": "unit-cpu",
            }
        )
    )
    start = {
        "baseline_sha256": trace.runner._sha(cpu_root / "cpu-candidate.json"),
        "run_id": "unit-cpu",
        "parent_pid": 321,
        "kind": "tight10_native_cpu",
        "logging_mode": "logging_off",
        "measurement_policy_version": "native_cpu_v1",
    }
    (cpu_root / "START.json").write_text(json.dumps(start))
    (cpu_root / "attempt").mkdir()
    assert trace._cpu_child(cpu_root, approval)["status"] == "CPU_CHILD_TERMINAL"
    receipt = json.loads((cpu_root / "CHILD-START.json").read_text())
    assert all(receipt[key] == value for key, value in start.items())
    assert receipt["pid"] == trace.os.getpid()
    result = json.loads((cpu_root / "attempt/trace-result.json").read_text())
    assert (
        result["native_solve_measurement"]["measurement_status"] == "OK"
        and result["native_call_count"] == 1
    )
    assert not (cpu_root / "attempt/trace.log").exists()
    assert (cpu_root / "attempt/independent-checks.json").exists()
    with pytest.raises(ValueError, match="REENTRY"):
        trace._cpu_child(cpu_root, approval)
    assert len(FakeSolver.instances) == 1
