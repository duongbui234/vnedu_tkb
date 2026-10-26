"""Bounded Linux supervisor tests, never school-scale benchmark runs."""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from benchmarks import run_benchmarks as runner

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="Native Linux only; Windows BLOCKED"
)


@pytest.fixture
def empty_execution(tmp_path: Path) -> Any:
    root = tmp_path / "run"
    return runner.ExecutionRecord(
        argv=(sys.executable, "-I", "-c", "pass"),
        run_dir=root,
        stdout_path=root / "stdout.json",
        stderr_path=root / "stderr.txt",
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("watchdog_seconds", True),
        ("watchdog_seconds", "1"),
        ("watchdog_seconds", float("nan")),
        ("watchdog_seconds", float("inf")),
        ("watchdog_seconds", 0),
        ("max_resident_bytes", False),
        ("max_resident_bytes", 0),
        ("extra", 1),
    ],
)
def test_strict_tooling_contracts(field: str, value: Any) -> None:
    data = {"watchdog_seconds": 4.0, "max_resident_bytes": 256 * 1024**2, field: value}
    with pytest.raises(ValidationError):
        runner.RunLimits.model_validate(data)


def test_missing_measurements_are_null(empty_execution: Any) -> None:
    assert empty_execution.measurement_status == "NOT_STARTED"
    assert empty_execution.peak_resident_bytes is None
    with pytest.raises(ValidationError):
        runner.ExecutionRecord.model_validate(
            {**empty_execution.model_dump(), "peak_resident_bytes": 0}
        )
    with pytest.raises(ValidationError):
        runner.ExecutionRecord.model_validate(
            {**empty_execution.model_dump(), "schema_version": "2.0"}
        )


def test_kib_units() -> None:
    assert runner.kib_to_bytes(1024) == 1048576
    for value in (True, -1, "1024", 1.5):
        with pytest.raises(ValueError):
            runner.kib_to_bytes(value)


def test_import_does_not_load_solver() -> None:
    code = """
import builtins
original=builtins.__import__
def guard(name,*a,**kw):
    if name.startswith(('ortools','tkb_core.solver.cp_sat','tkb_core.solver.model_builder')):
        raise ImportError(name)
    return original(name,*a,**kw)
builtins.__import__=guard
from benchmarks import run_benchmarks
"""
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert p.returncode == 0, p.stderr


def child_argv(body: str) -> tuple[str, ...]:
    return (sys.executable, "-I", "-c", body)


def limits(seconds: float = 4.0, cap: int = 256 * 1024**2) -> Any:
    return runner.RunLimits(watchdog_seconds=seconds, max_resident_bytes=cap)


def test_fast_child_has_kernel_peak(tmp_path: Path) -> None:
    r = runner.supervise_linux(child_argv("pass"), tmp_path / "run", limits())
    assert r.exit_code == 0 and r.measurement_status == "OK"
    assert r.peak_resident_bytes > 0
    assert r.peak_resident_bytes == r.native_peak_rss_kib * 1024
    assert r.cpu_seconds >= 0
    with pytest.raises(ChildProcessError):
        os.waitpid(r.pid, os.WNOHANG)


SPIKE = 'import mmap; m=mmap.mmap(-1,64*1024**2); m[:]=b"x"*(64*1024**2); m.close()'


def test_native_memory_spike(tmp_path: Path) -> None:
    r = runner.supervise_linux(child_argv(SPIKE), tmp_path / "run", limits())
    assert r.measurement_status == "OK" and r.peak_resident_bytes >= 64 * 1024**2


def test_small_run_does_not_inherit_previous_peak(tmp_path: Path) -> None:
    # A heavy parent's lifetime RSS can floor child peaks; compare in one light parent.
    code = f"""
import sys
from pathlib import Path
from benchmarks import run_benchmarks as r
root=Path(sys.argv[1]);lim=r.RunLimits(watchdog_seconds=4.0,max_resident_bytes=256*1024**2)
a=r.supervise_linux((sys.executable,'-I','-c',{SPIKE!r}),root/'large',lim)
b=r.supervise_linux((sys.executable,'-I','-c','pass'),root/'small',lim)
assert a.peak_resident_bytes > b.peak_resident_bytes+32*1024**2
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr


def test_unrelated_child_is_not_reaped(tmp_path: Path) -> None:
    other = os.posix_spawn(sys.executable, child_argv("import time;time.sleep(.3)"), os.environ)
    try:
        r = runner.supervise_linux(child_argv("pass"), tmp_path / "run", limits())
        assert r.pid != other
    finally:
        assert os.waitpid(other, 0)[0] == other


def test_existing_root_is_preserved(tmp_path: Path) -> None:
    root = tmp_path / "run"
    root.mkdir()
    (root / "sentinel").write_text("keep")
    with pytest.raises(FileExistsError):
        runner.supervise_linux(child_argv("pass"), root, limits())
    assert (root / "sentinel").read_text() == "keep"


def test_large_stdout_stderr_do_not_block(tmp_path: Path) -> None:
    r = runner.supervise_linux(
        child_argv('import os;os.write(1,b"a"*(2*1024**2));os.write(2,b"b"*(2*1024**2))'),
        tmp_path / "run",
        limits(),
    )
    assert r.exit_code == 0
    assert r.stdout_path.stat().st_size == r.stderr_path.stat().st_size == 2 * 1024**2


def assert_reaped(r: Any) -> None:
    with pytest.raises(ChildProcessError):
        os.waitpid(r.pid, os.WNOHANG)


def test_watchdog_stops_sleeping_child(tmp_path: Path) -> None:
    r = runner.supervise_linux(
        child_argv("import time;time.sleep(8)"), tmp_path / "run", limits(0.1)
    )
    assert r.stop_reason == "WATCHDOG" and r.signal == 15
    assert r.launch_to_exit_seconds < 5
    assert_reaped(r)


def test_ignored_term_is_followed_by_kill(tmp_path: Path) -> None:
    marker = tmp_path / "ready"
    body = (
        "import signal,time;from pathlib import Path;"
        "signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        f"Path({str(marker)!r}).touch();time.sleep(8)"
    )
    r = runner.supervise_linux(child_argv(body), tmp_path / "run", limits(2.0))
    assert marker.exists() and r.stop_reason == "WATCHDOG" and r.signal == 9
    assert r.launch_to_exit_seconds >= 3.0
    assert_reaped(r)


def test_sampled_limit_requests_resource_stop(tmp_path: Path) -> None:
    r = runner.supervise_linux(
        child_argv(SPIKE.replace("m.close()", "import time;time.sleep(.5);m.close()")),
        tmp_path / "run",
        limits(cap=32 * 1024**2),
    )
    assert r.stop_reason == "RESOURCE_LIMIT"
    assert r.sample_count > 0 and r.sampled_peak_bytes > 32 * 1024**2
    assert r.native_peak_rss_kib * 1024 == r.peak_resident_bytes
    assert_reaped(r)


def test_proc_disappears_on_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = os.wait4

    def sample(pid: int) -> int:
        # Simulate exit between first nonblocking wait and proc read, without reaping it.
        import time

        time.sleep(0.15)
        raise FileNotFoundError("exit race")

    monkeypatch.setattr(runner, "_read_rss", sample, raising=False)
    r = runner.supervise_linux(child_argv("pass"), tmp_path / "run", limits())
    assert r.measurement_status == "OK" and r.exit_code == 0
    assert os.wait4 is original


def test_live_proc_permission_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(pid: int) -> int:
        raise PermissionError("test")

    monkeypatch.setattr(runner, "_read_rss", fail, raising=False)
    r = runner.supervise_linux(child_argv("import time;time.sleep(8)"), tmp_path / "run", limits())
    assert r.measurement_status == "BLOCKED" and r.stop_reason == "PROBE_ERROR"
    assert r.sampled_peak_bytes is None and r.measurement_reason
    assert_reaped(r)


def test_wait4_eintr_is_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = os.wait4
    count = 0

    def interrupted(pid: int, flags: int) -> Any:
        nonlocal count
        count += 1
        if count == 1:
            raise InterruptedError()
        return original(pid, flags)

    monkeypatch.setattr(os, "wait4", interrupted)
    r = runner.supervise_linux(child_argv("pass"), tmp_path / "run", limits())
    assert count >= 2 and r.measurement_status == "OK"
    assert_reaped(r)


@pytest.mark.parametrize("lost", ["echild", "mismatch"])
def test_lost_ownership_never_signals_pid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lost: str
) -> None:
    signals = []
    monkeypatch.setattr(os, "posix_spawn", lambda *a, **k: 999999)

    def wait(*args: Any) -> Any:
        if lost == "echild":
            raise ChildProcessError()
        return (999998, 0, None)

    monkeypatch.setattr(os, "wait4", wait)
    monkeypatch.setattr(os, "kill", lambda *args: signals.append(args))
    r = runner.supervise_linux(child_argv("pass"), tmp_path / "run", limits())
    assert r.measurement_status == "BLOCKED" and r.peak_resident_bytes is None
    assert not signals


@pytest.mark.parametrize("error", [KeyboardInterrupt, RuntimeError])
def test_parent_interrupt_and_exception_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Any
) -> None:
    def fail(pid: int) -> int:
        raise error("injected")

    monkeypatch.setattr(runner, "_read_rss", fail, raising=False)
    r = runner.supervise_linux(child_argv("import time;time.sleep(8)"), tmp_path / "run", limits())
    assert r.stop_reason == "PARENT_INTERRUPTED" and r.error_type == error.__name__
    assert_reaped(r)


def test_spawn_failure_has_no_child_metrics(tmp_path: Path) -> None:
    r = runner.supervise_linux(("/missing/python",), tmp_path / "run", limits())
    assert r.pid is None and r.peak_resident_bytes is None and r.cpu_seconds is None
    assert r.measurement_status == "NOT_STARTED" and r.error_type


@pytest.fixture
def tiny_case() -> tuple[Any, Any]:
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.solver.cp_sat import solve
    from tkb_core.solver.options import SolveOptions

    p = ScheduleInput.model_validate_json(
        (Path(__file__).parents[2] / "tests/fixtures/quality/teacher_preferences.json").read_text()
    )
    r = solve(p, SolveOptions(time_limit_seconds=10.0, num_workers=1, seed=42))
    assert r.valid_schedule
    return p, r


def output_files(tmp_path: Path, p: Any, result: Any, code: int) -> tuple[Path, Path, Any]:
    inp = tmp_path / "input.json"
    inp.write_text(p.model_dump_json())
    dest = tmp_path / "result.json"
    payload = result.model_dump_json() if hasattr(result, "model_dump_json") else json.dumps(result)
    dest.write_text(payload)
    stdout = tmp_path / "stdout.json"
    stdout.write_text(payload)
    e = runner.ExecutionRecord(
        argv=child_argv("pass"),
        run_dir=tmp_path,
        stdout_path=stdout,
        stderr_path=tmp_path / "stderr.txt",
        pid=123,
        raw_wait_status=code << 8,
        exit_code=code,
        cpu_seconds=0.0,
        native_peak_rss_kib=1024,
        peak_resident_bytes=1048576,
        measurement_status="OK",
        measurement_reason=None,
    )
    return inp, dest, e


@pytest.mark.parametrize(
    "status,code",
    [
        ("OPTIMAL", 0),
        ("FEASIBLE", 0),
        ("INFEASIBLE", 3),
        ("UNKNOWN", 4),
        ("INPUT_INVALID", 2),
        ("UNSUPPORTED_FEATURE", 2),
        ("MODEL_INVALID", 5),
    ],
)
def test_cli_exit_status_pairs(tmp_path: Path, tiny_case: Any, status: str, code: int) -> None:
    from tkb_core.contracts.output import ScheduleResult, SolverRunMetadataV12
    from tkb_core.contracts.score import QualityReport, StageRun

    p, positive = tiny_case
    if code == 0:
        result = positive
        if status == "FEASIBLE":
            data = result.model_dump(mode="json")
            data["status"] = "FEASIBLE"
            data["quality"]["status"] = "SCORED_FEASIBLE"
            data["quality"]["optimal_prefix"] = []
            data["quality"]["tier_runs"] = [StageRun(priority=1).model_dump(mode="json")]
            result = ScheduleResult.model_validate(data)
    else:
        result = ScheduleResult(
            schema_version="1.2",
            status=status,
            input_fingerprint=p.fingerprint(),
            metadata=SolverRunMetadataV12(solver_executed=False),
            quality=QualityReport(status="NOT_EVALUATED"),
        )
    inp, dest, e = output_files(tmp_path, p, result, code)
    verified = runner.verify_cli_output(inp, dest, e)
    assert verified.solver_status == status
    assert verified.valid_schedule == (code == 0)
    assert runner.classify_run(e, verified) == "COMPLETE"
    if code == 0:
        assert verified.score == positive.quality.score


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "utf8",
        "json",
        "duplicate",
        "nan",
        "version",
        "stale",
        "hard",
        "score",
        "proof",
        "stdout",
        "exit_mismatch",
    ],
)
def test_malformed_stale_and_forged_outputs(tmp_path: Path, tiny_case: Any, mutation: str) -> None:
    p, r = tiny_case
    inp, dest, e = output_files(tmp_path, p, r, 0)
    data = json.loads(dest.read_text())
    if mutation == "missing":
        dest.unlink()
    elif mutation == "utf8":
        dest.write_bytes(b"\xff")
    elif mutation == "json":
        dest.write_text("{")
    elif mutation == "duplicate":
        dest.write_text('{"x":1,"x":2}')
    elif mutation == "nan":
        dest.write_text('{"x":NaN}')
    elif mutation == "stdout":
        e.stdout_path.write_text("{}")
    elif mutation == "exit_mismatch":
        e = e.model_copy(update={"exit_code": 3})
    else:
        if mutation == "version":
            data["schema_version"] = "1.1"
        if mutation == "stale":
            data["input_fingerprint"] = "0" * 64
            data["quality"]["score"]["input_fingerprint"] = "0" * 64
        if mutation == "hard":
            data["assignments"][0]["slot_id"] = "bad"
        if mutation == "score":
            data["quality"]["score"]["rules"][0]["raw_penalty"] += 1
        if mutation == "proof":
            data["quality"]["tier_runs"][0]["incumbent_value"] = 999
        dest.write_text(json.dumps(data))
        e.stdout_path.write_text(json.dumps(data))
    verified = runner.verify_cli_output(inp, dest, e)
    assert verified.status == "INVALID" and not verified.valid_schedule
    assert runner.classify_run(e, verified) == "OUTPUT_INVALID"


@pytest.mark.parametrize("extra", [False, True])
def test_valid_error_envelope_is_not_schedule(tmp_path: Path, tiny_case: Any, extra: bool) -> None:
    p, _ = tiny_case
    data = {
        "schema_version": "1.0",
        "status": "INPUT_INVALID",
        "diagnostics": [{"code": "INVALID_INPUT", "message": "test"}],
    }
    if extra:
        data["valid_schedule"] = True
    inp, dest, e = output_files(tmp_path, p, data, 2)
    dest.unlink()
    v = runner.verify_cli_output(inp, dest, e)
    assert v.status == ("INVALID" if extra else "VALID_CORE_ERROR")
    assert not v.valid_schedule


@pytest.mark.parametrize(
    "stop,code,measurement,output,expected",
    [
        ("WATCHDOG", -15, "BLOCKED", "VALID_SCHEDULE", "WATCHDOG_TIMEOUT"),
        ("RESOURCE_LIMIT", 0, "OK", "VALID_SCHEDULE", "RESOURCE_STOP"),
        ("PARENT_INTERRUPTED", -9, "OK", "SKIPPED", "CANCELLED"),
        ("PROBE_ERROR", -15, "BLOCKED", "INVALID", "MEASUREMENT_BLOCKED"),
        (None, -11, "BLOCKED", "INVALID", "CRASH"),
        (None, 42, "OK", "INVALID", "CRASH"),
        (None, 0, "BLOCKED", "INVALID", "MEASUREMENT_BLOCKED"),
        (None, 0, "OK", "SKIPPED", "OUTPUT_INVALID"),
    ],
)
def test_compound_outcomes(
    empty_execution: Any, stop: str | None, code: int, measurement: str, output: str, expected: str
) -> None:
    e = empty_execution.model_copy(
        update={
            "pid": 123,
            "exit_code": code,
            "signal": -code if code < 0 else None,
            "stop_reason": stop,
            "measurement_status": measurement,
        }
    )
    v = runner.OutputVerification(status=output, valid_schedule=output == "VALID_SCHEDULE")
    assert runner.classify_run(e, v) == expected


@pytest.fixture
def frozen_unit(tmp_path: Path) -> Path:
    """Synthetic identity fixture, not an installed or released wheel."""
    import hashlib
    import importlib.metadata as md
    import zipfile

    root = tmp_path / "preflight"
    (root / "distribution").mkdir(parents=True)
    wheel = root / "distribution/core.whl"
    source = Path(__file__).parents[2] / "src"
    with zipfile.ZipFile(wheel, "w") as z:
        for p in (source / "tkb_core").rglob("*.py"):
            z.write(p, str(p.relative_to(source)))
    env = {
        "installed_versions": {n: md.version(n) for n in ("vnedu-tkb-core", "pydantic", "ortools")},
        "core_tree": "synthetic-tree",
        "git_commit": "synthetic-commit",
    }
    (root / "environment-solver.json").write_text(json.dumps(env))
    manifest = {
        "preflight_schema_version": "1.0",
        "linux_status": "PASS",
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "uv_lock_sha256": hashlib.sha256((source.parent / "uv.lock").read_bytes()).hexdigest(),
        "files": {
            "environment-solver.json": hashlib.sha256(
                (root / "environment-solver.json").read_bytes()
            ).hexdigest()
        },
    }
    (root / "preflight-manifest.json").write_text(json.dumps(manifest))
    return root


def run_kwargs(tmp_path: Path, tiny_case: Any, frozen_unit: Path) -> dict[str, Any]:
    import hashlib

    from tkb_core.solver.options import SolveOptions

    inp = tmp_path / "input.json"
    inp.write_text(tiny_case[0].model_dump_json())
    return dict(
        python=Path(sys.executable),
        input_path=inp,
        run_dir=tmp_path / "run",
        preflight_dir=frozen_unit,
        lock_path=Path(__file__).parents[2] / "uv.lock",
        input_sha256=hashlib.sha256(inp.read_bytes()).hexdigest(),
        limits=limits(),
        options=SolveOptions(time_limit_seconds=1.0, num_workers=1, seed=42),
    )


@pytest.mark.parametrize(
    "mismatch",
    ["wheel", "lock", "version", "version_missing", "editable", "input", "platform", "api"],
)
def test_runtime_identity_mismatch_blocks_before_spawn(
    tmp_path: Path,
    tiny_case: Any,
    frozen_unit: Path,
    monkeypatch: pytest.MonkeyPatch,
    mismatch: str,
) -> None:
    import hashlib

    k = run_kwargs(tmp_path, tiny_case, frozen_unit)
    if mismatch == "wheel":
        (frozen_unit / "distribution/core.whl").write_bytes(b"changed")
    if mismatch == "lock":
        k["lock_path"] = tmp_path / "wrong.lock"
        k["lock_path"].write_text("wrong")
    if mismatch == "input":
        k["input_sha256"] = "0" * 64
    if mismatch == "version":
        env = frozen_unit / "environment-solver.json"
        data = json.loads(env.read_text())
        data["installed_versions"]["pydantic"] = "0"
        env.write_text(json.dumps(data))
        path = frozen_unit / "preflight-manifest.json"
        m = json.loads(path.read_text())
        m["files"]["environment-solver.json"] = hashlib.sha256(env.read_bytes()).hexdigest()
        path.write_text(json.dumps(m))
    if mismatch == "version_missing":
        import importlib.metadata as md

        original = md.version

        def missing(name: str) -> str:
            if name == "ortools":
                raise md.PackageNotFoundError(name)
            return original(name)

        monkeypatch.setattr(md, "version", missing)
    if mismatch == "platform":
        monkeypatch.setattr(sys, "platform", "not-linux")
    if mismatch == "api":
        monkeypatch.delattr(os, "wait4")
    r = runner.run_cli_once(**k)
    assert r.harness_status == "ENVIRONMENT_BLOCKED" and r.execution.pid is None
    assert r.execution.peak_resident_bytes is None and not r.valid_schedule
    assert mismatch.upper() in " ".join(r.output.diagnostics)
    assert runner.RunRecord.model_validate_json((k["run_dir"] / "run.json").read_text()) == r


def test_input_changes_during_run(
    tmp_path: Path, tiny_case: Any, frozen_unit: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    k = run_kwargs(tmp_path, tiny_case, frozen_unit)
    monkeypatch.setattr(
        runner, "_runtime_identity", lambda **kw: {"unit_test": True}, raising=False
    )
    original = runner.supervise_linux

    def mutate(*args: Any, **kw: Any) -> Any:
        r = original(*args, **kw)
        k["input_path"].write_text("{}")
        return r

    monkeypatch.setattr(runner, "supervise_linux", mutate)
    r = runner.run_cli_once(**k)
    assert r.harness_status == "OUTPUT_INVALID" and not r.valid_schedule
    assert "INPUT_CHANGED" in r.output.diagnostics


def test_stopped_run_never_publishes_schedule(
    tmp_path: Path, tiny_case: Any, frozen_unit: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    k = run_kwargs(tmp_path, tiny_case, frozen_unit)
    monkeypatch.setattr(
        runner, "_runtime_identity", lambda **kw: {"unit_test": True}, raising=False
    )
    original = runner.supervise_linux

    def stopped(*args: Any, **kw: Any) -> Any:
        r = original(*args, **kw)
        return r.model_copy(update={"stop_reason": "WATCHDOG"})

    monkeypatch.setattr(runner, "supervise_linux", stopped)
    r = runner.run_cli_once(**k)
    assert (
        r.output.valid_schedule and r.harness_status == "WATCHDOG_TIMEOUT" and not r.valid_schedule
    )


def test_record_json_roundtrip(tmp_path: Path, tiny_case: Any, frozen_unit: Path) -> None:
    k = run_kwargs(tmp_path, tiny_case, frozen_unit)
    k["run_dir"].mkdir()
    (k["run_dir"] / "sentinel").write_text("keep")
    with pytest.raises(FileExistsError):
        runner.run_cli_once(**k)
    assert (k["run_dir"] / "sentinel").read_text() == "keep"


def test_installed_wheel_tiny_cli_roundtrip(tmp_path: Path) -> None:
    preflight = os.environ.get("TKB_PREFLIGHT_DIR")
    if not preflight:
        pytest.skip("requires frozen Task2 installed wheel via TKB_PREFLIGHT_DIR")
    preflight = Path(preflight).absolute()
    python = preflight / "venv-solver/bin/python"
    assert python.is_file(), "Explicit preflight supplied but installed Python missing"
    root = Path(__file__).parents[2]
    data = json.loads((root / "tests/fixtures/quality/teacher_preferences.json").read_text())
    data["constraint_config"]["soft"] += [
        {
            "id": "session",
            "code": "TEACHER_MAX_PERIODS_PER_SESSION",
            "parameters": {"limit": 1, "session_ids": ["AM", "PM"]},
            "weight": 1,
            "priority": 1,
        },
        {
            "id": "day",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 1},
            "weight": 1,
            "priority": 2,
        },
        {
            "id": "window",
            "code": "TEACHER_PREFERRED_PERIOD_WINDOW",
            "parameters": {"first_period": 2, "last_period": 2, "session_ids": ["AM", "PM"]},
            "weight": 1,
            "priority": 3,
        },
    ]
    inp = tmp_path / "input.json"
    inp.write_text(json.dumps(data))
    driver = """
import hashlib,importlib.util,json,sys
from pathlib import Path
root,preflight,inp,run=map(Path,sys.argv[1:])
spec=importlib.util.spec_from_file_location('supervisor',root/'benchmarks/run_benchmarks.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
from tkb_core.solver.options import SolveOptions
r=m.run_cli_once(python=Path(sys.executable),input_path=inp,run_dir=run,preflight_dir=preflight,lock_path=root/'uv.lock',input_sha256=hashlib.sha256(inp.read_bytes()).hexdigest(),limits=m.RunLimits(watchdog_seconds=15.0,max_resident_bytes=256*1024**2),options=SolveOptions(time_limit_seconds=10.0,num_workers=1,seed=42))
assert r.harness_status=='COMPLETE',r.model_dump_json()
assert r.valid_schedule and r.output.score.tiers==(1,1,2)
assert r.execution.measurement_status=='OK' and r.execution.peak_resident_bytes>0
assert len(r.output.score.rules)==4
print(r.model_dump_json())
"""
    p = subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            driver,
            str(root),
            str(preflight),
            str(inp),
            str(tmp_path / "run"),
        ],
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert p.returncode == 0, p.stderr + p.stdout
    r = runner.RunRecord.model_validate_json(p.stdout)
    assert r.valid_schedule


def test_closed_parent_standard_fds_do_not_cross_streams(tmp_path: Path) -> None:
    code = """
import os,sys
from pathlib import Path
from benchmarks import run_benchmarks as r
os.close(0);os.close(1)
argv=(sys.executable,'-I','-c',"import os;os.write(1,b'out');os.write(2,b'err')")
a=r.supervise_linux(argv,Path(sys.argv[1]),
    r.RunLimits(watchdog_seconds=3.0,max_resident_bytes=256*1024**2))
assert a.stdout_path.read_bytes()==b'out'
assert a.stderr_path.read_bytes()==b'err'
"""
    p = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "run")],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert p.returncode == 0, p.stderr


def test_error_with_score_is_not_accepted(tmp_path: Path, tiny_case: Any) -> None:
    p, positive = tiny_case
    data = positive.model_dump(mode="json")
    data.update(status="UNKNOWN", valid_schedule=False, assignments=[], validation=None)
    data["quality"].update(status="NOT_REQUESTED", optimal_prefix=[], tier_runs=[])
    inp, dest, e = output_files(tmp_path, p, data, 4)
    assert runner.verify_cli_output(inp, dest, e).status == "INVALID"


@pytest.mark.parametrize("field,value", [("raw_wait_status", True), ("exit_code", "0")])
def test_execution_rejects_coerced_process_status(
    empty_execution: Any, field: str, value: Any
) -> None:
    with pytest.raises(ValidationError):
        runner.ExecutionRecord.model_validate({**empty_execution.model_dump(), field: value})


def test_interrupt_during_post_spawn_initialization_reaps_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = runner.ExecutionRecord.__setattr__
    original_spawn = os.posix_spawn
    pids = []
    fired = False

    def spawn(*a: Any, **kw: Any) -> int:
        pid = original_spawn(*a, **kw)
        pids.append(pid)
        return pid

    def interrupt(self: Any, name: str, value: Any) -> None:
        nonlocal fired
        if name == "measurement_status" and self.pid and not fired:
            fired = True
            raise KeyboardInterrupt("post-spawn")
        original(self, name, value)

    monkeypatch.setattr(os, "posix_spawn", spawn)
    monkeypatch.setattr(runner.ExecutionRecord, "__setattr__", interrupt)
    r = None
    try:
        try:
            r = runner.supervise_linux(
                child_argv("import time;time.sleep(2)"), tmp_path / "run", limits()
            )
        except KeyboardInterrupt:
            pass
        assert r is not None and r.stop_reason == "PARENT_INTERRUPTED"
        assert_reaped(r)
    finally:
        for pid in pids:
            try:
                if os.waitpid(pid, os.WNOHANG)[0] == 0:
                    os.kill(pid, 9)
                    os.waitpid(pid, 0)
            except ChildProcessError:
                pass


def test_repeated_poll_exception_enters_bounded_cleanup(tmp_path: Path) -> None:
    code = """
import os,sys
from pathlib import Path
from benchmarks import run_benchmarks as r
native=os.wait4
def fail(*a):raise RuntimeError('permanent injected wait4 failure')
os.wait4=fail
try:
    argv=(sys.executable,'-I','-c','import time;time.sleep(2)')
    v=r.supervise_linux(argv,Path(sys.argv[1]),
        r.RunLimits(watchdog_seconds=3.0,max_resident_bytes=256*1024**2))
finally:os.wait4=native
assert v.stop_reason=='PARENT_INTERRUPTED'
assert v.measurement_status=='BLOCKED' and v.measurement_reason=='REAP_UNCONFIRMED'
# Broken wait4 cannot certify reaping: the test owner explicitly recovers after restoring it.
assert native(v.pid,0)[0]==v.pid
"""
    p = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "run")],
        capture_output=True,
        text=True,
        timeout=7,
    )
    assert p.returncode == 0, p.stderr


def test_input_identity_uses_one_checked_snapshot(
    tmp_path: Path, tiny_case: Any, frozen_unit: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    k = run_kwargs(tmp_path, tiny_case, frozen_unit)
    before = k["input_path"].read_bytes()

    def replace(**kw: Any) -> dict[str, Any]:
        other = json.loads(before)
        other["school"]["term"] = "changed-during-preflight"
        k["input_path"].write_text(json.dumps(other))
        return {"unit_test": True}

    original = runner.supervise_linux

    def restore(*a: Any, **kw: Any) -> Any:
        k["input_path"].write_bytes(before)
        return original(*a, **kw)

    monkeypatch.setattr(runner, "_runtime_identity", replace)
    monkeypatch.setattr(runner, "supervise_linux", restore)
    r = runner.run_cli_once(**k)
    assert r.harness_status == "ENVIRONMENT_BLOCKED" and r.execution.pid is None
    assert "INPUT_CHANGED_BEFORE_SPAWN" in r.output.diagnostics


@pytest.mark.parametrize("proof", [False, True])
def test_schema_valid_forged_score_and_proof_rejected(
    tmp_path: Path, tiny_case: Any, proof: bool
) -> None:
    from tkb_core.contracts.output import ScheduleResult
    from tkb_core.contracts.score import StageRun

    p, r = tiny_case
    data = r.model_dump(mode="json")
    data["quality"]["score"]["rules"][0]["raw_penalty"] += 1
    data["quality"]["score"]["rules"][0]["weighted_penalty"] += 1
    data["quality"]["score"]["tiers"][0] += 1
    if proof:
        data["quality"]["tier_runs"][0]["incumbent_value"] += 1
        data["quality"]["tier_runs"][0]["best_bound"] += 1
    else:
        data["status"] = "FEASIBLE"
        data["quality"]["status"] = "SCORED_FEASIBLE"
        data["quality"]["optimal_prefix"] = []
        data["quality"]["tier_runs"] = [StageRun(priority=1).model_dump(mode="json")]
    coherent = ScheduleResult.model_validate(data)
    inp, dest, e = output_files(tmp_path, p, coherent, 0)
    assert runner.verify_cli_output(inp, dest, e).status == "INVALID"


def test_real_sigint_restores_mask_and_reaps(tmp_path: Path) -> None:
    # Isolate Python SIGINT handling from native solver handlers loaded by other Core tests.
    code = """
import os,sys,signal
from pathlib import Path
from benchmarks import run_benchmarks as r
original=r._read_rss
before=signal.pthread_sigmask(signal.SIG_BLOCK,set())
fired=False
def interrupt(pid):
    global fired
    if not fired:
        fired=True;os.kill(os.getpid(),signal.SIGINT)
    return original(pid)
r._read_rss=interrupt
argv=(sys.executable,'-I','-c','import time;time.sleep(2)')
v=r.supervise_linux(argv,Path(sys.argv[1]),
    r.RunLimits(watchdog_seconds=4.0,max_resident_bytes=256*1024**2))
assert v.stop_reason=='PARENT_INTERRUPTED'
assert signal.pthread_sigmask(signal.SIG_BLOCK,set())==before
try:os.waitpid(v.pid,os.WNOHANG)
except ChildProcessError:pass
else:raise AssertionError('not reaped')
"""
    p = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path / "run")],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert p.returncode == 0, p.stderr


def test_native_signal_crash_is_not_infeasible(tmp_path: Path) -> None:
    r = runner.supervise_linux(
        child_argv("import os,signal;os.kill(os.getpid(),signal.SIGKILL)"),
        tmp_path / "run",
        limits(),
    )
    assert r.signal == 9 and r.stop_reason is None and r.measurement_status == "OK"
    assert runner.classify_run(r, runner.OutputVerification()) == "CRASH"
    assert_reaped(r)


@pytest.mark.parametrize("status,code", [("INFEASIBLE", 3), ("UNKNOWN", 4)])
def test_native_nonzero_exit_with_valid_core_payload(
    tmp_path: Path, tiny_case: Any, status: str, code: int
) -> None:
    from tkb_core.contracts.output import ScheduleResult, SolverRunMetadataV12
    from tkb_core.contracts.score import QualityReport

    p, _ = tiny_case
    inp = tmp_path / "input.json"
    inp.write_text(p.model_dump_json())
    dest = tmp_path / "run/result.json"
    payload = ScheduleResult(
        schema_version="1.2",
        status=status,
        input_fingerprint=p.fingerprint(),
        metadata=SolverRunMetadataV12(solver_executed=False),
        quality=QualityReport(status="NOT_EVALUATED"),
    ).model_dump_json()
    body = (
        f"import os;from pathlib import Path;p={payload!r};"
        f"Path({str(dest)!r}).write_text(p);os.write(1,p.encode());os._exit({code})"
    )
    r = runner.supervise_linux(child_argv(body), tmp_path / "run", limits())
    v = runner.verify_cli_output(inp, dest, r)
    assert r.exit_code == code and r.stop_reason is None
    assert v.solver_status == status and not v.valid_schedule
    assert runner.classify_run(r, v) == "COMPLETE"
    assert_reaped(r)
