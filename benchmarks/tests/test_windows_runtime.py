"""Windows accounting contracts; native probes run only on actual Windows."""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from benchmarks import run_benchmarks as runner


def test_windows_kernel_evidence_uses_bytes_not_linux_wait_status(tmp_path: Path) -> None:
    record = runner.ExecutionRecord(
        argv=("python.exe",),
        run_dir=tmp_path,
        stdout_path=tmp_path / "out",
        stderr_path=tmp_path / "err",
        pid=123,
        exit_code=0,
        cpu_seconds=0.125,
        peak_resident_bytes=1048576,
        native_peak_working_set_bytes=1048576,
        native_field="PeakWorkingSetSize",
        native_unit="bytes",
        measurement_method="windows_process_handle",
        measurement_status="OK",
        measurement_reason=None,
    )
    assert record.raw_wait_status is None and record.native_peak_rss_kib is None
    assert record.peak_resident_bytes == 1048576
    for change in (
        {"native_peak_working_set_bytes": 1024},
        {"native_peak_rss_kib": 1024},
        {"native_unit": "KiB"},
        {"raw_wait_status": 0},
        {"native_peak_working_set_bytes": None},
    ):
        with pytest.raises(ValidationError):
            runner.ExecutionRecord.model_validate(record.model_dump() | change)
    from types import SimpleNamespace

    outcome = runner.RunRecord(
        harness_status="COMPLETE",
        execution=record,
        output=runner.OutputVerification(status="VALID_CORE_ERROR", solver_status="INFEASIBLE"),
        identity={},
    )
    verdict = runner.CaseVerdict(
        correctness="PASS",
        performance="NOT_APPLICABLE",
        quality="NOT_APPLICABLE",
        run_sha256="0" * 64,
    )
    assert runner._stop_status(outcome, verdict, SimpleNamespace(phase="primary")) is None


@pytest.mark.skipif(sys.platform == "win32", reason="Negative native-platform gate")
def test_windows_supervisor_refuses_linux_without_spawning(tmp_path: Path) -> None:
    from benchmarks.windows_runtime import supervise_windows

    record = supervise_windows(
        (sys.executable, "-c", "raise SystemExit(99)"),
        tmp_path / "run",
        runner.RunLimits(watchdog_seconds=2.0, max_resident_bytes=256 * 1024**2),
    )
    assert record.pid is None and record.measurement_status == "NOT_STARTED"
    assert record.error_type == "WINDOWS_NATIVE_REQUIRED"


def test_windows_headroom_reserves_two_gib(monkeypatch: pytest.MonkeyPatch) -> None:
    from benchmarks import windows_runtime

    monkeypatch.setattr(runner.sys, "platform", "win32")
    monkeypatch.setattr(
        windows_runtime,
        "memory_status",
        lambda: {
            "ullAvailPhys": 4 * 1024**3,
            "ullAvailPageFile": 3 * 1024**3,
        },
    )
    assert runner.check_headroom(1024**3).status == "PASS"
    denied = runner.check_headroom(2 * 1024**3)
    assert denied.status == "BLOCKED" and denied.available_bytes == 3 * 1024**3


def test_windows_probe_failure_blocks_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    from benchmarks import windows_runtime

    def failed():
        raise OSError("native probe failed")

    monkeypatch.setattr(runner.sys, "platform", "win32")
    monkeypatch.setattr(windows_runtime, "memory_status", failed)
    denied = runner.check_headroom(1024**3)
    assert denied.status == "BLOCKED" and denied.available_bytes is None


def test_interrupt_after_spawn_still_kills_and_waits_owned_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from benchmarks import windows_runtime

    calls = []

    class Handle:
        def Close(self):
            calls.append("close")

    class Child:
        _handle = Handle()
        interrupted = False

        @property
        def pid(self):
            if not self.interrupted:
                self.interrupted = True
                raise KeyboardInterrupt
            return 123

        def poll(self):
            return None

        def kill(self):
            calls.append("kill")

        def wait(self, timeout=None):
            calls.append("wait")
            return 1

    monkeypatch.setattr(windows_runtime, "native_api", lambda: object())
    monkeypatch.setattr(windows_runtime.subprocess, "Popen", lambda *a, **kw: Child())
    monkeypatch.setattr(windows_runtime.subprocess, "CREATE_NEW_PROCESS_GROUP", 512, raising=False)
    try:
        record = windows_runtime.supervise_windows(
            ("python",),
            tmp_path / "run",
            runner.RunLimits(watchdog_seconds=2.0, max_resident_bytes=256 * 1024**2),
        )
    except KeyboardInterrupt:
        record = None
    assert calls[:2] == ["kill", "wait"]
    assert record is not None and record.stop_reason == "PARENT_INTERRUPTED"
    assert record.exit_code == 1 and record.measurement_status != "OK"


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows accounting required")
@pytest.mark.parametrize("body", ["pass", "raise SystemExit(3)", "raise SystemExit(4)"])
def test_windows_fast_child_has_kernel_peak(tmp_path: Path, body: str) -> None:
    from benchmarks.windows_runtime import supervise_windows

    record = supervise_windows(
        (sys.executable, "-I", "-c", body),
        tmp_path / "run",
        runner.RunLimits(watchdog_seconds=4.0, max_resident_bytes=256 * 1024**2),
    )
    assert record.measurement_status == "OK"
    assert record.peak_resident_bytes > 0
    assert record.peak_resident_bytes == record.native_peak_working_set_bytes
    assert record.exit_code == (3 if "(3)" in body else 4 if "(4)" in body else 0)
    assert record.cpu_seconds >= 0


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows accounting required")
def test_windows_peak_survives_release_and_is_per_child(tmp_path: Path) -> None:
    from benchmarks.windows_runtime import supervise_windows

    limits = runner.RunLimits(watchdog_seconds=6.0, max_resident_bytes=256 * 1024**2)
    large = supervise_windows(
        (sys.executable, "-I", "-c", 'a=bytearray(64*1024**2);a[:]=b"x"*len(a);del a'),
        tmp_path / "large",
        limits,
    )
    small = supervise_windows((sys.executable, "-I", "-c", "pass"), tmp_path / "small", limits)
    assert large.measurement_status == small.measurement_status == "OK"
    assert large.peak_resident_bytes > small.peak_resident_bytes + 32 * 1024**2


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows accounting required")
def test_windows_watchdog_and_resource_stop_keep_owned_exit(tmp_path: Path) -> None:
    from benchmarks.windows_runtime import supervise_windows

    for name, body, cap, expected in (
        ("sleep", "import time;time.sleep(30)", 256 * 1024**2, "WATCHDOG"),
        (
            "memory",
            "a=bytearray(64*1024**2);import time;time.sleep(30)",
            32 * 1024**2,
            "RESOURCE_LIMIT",
        ),
    ):
        record = supervise_windows(
            (sys.executable, "-I", "-c", body),
            tmp_path / name,
            runner.RunLimits(watchdog_seconds=2.0, max_resident_bytes=cap),
        )
        assert record.stop_reason == expected and record.exit_code is not None
        assert record.measurement_status == "OK"


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows byte-range locking required")
def test_windows_campaign_lock_excludes_second_owner(tmp_path: Path) -> None:
    import json

    root = tmp_path / "owner"
    with runner._campaign_owner(root, tmp_path / "first", "first"):
        with pytest.raises(ValueError, match="CAMPAIGN_ALREADY_ACTIVE"):
            with runner._campaign_owner(root, tmp_path / "second", "second"):
                pytest.fail("Concurrent owner admitted")
    assert json.loads((root / "active.json").read_text())["state"] == "IDLE"
