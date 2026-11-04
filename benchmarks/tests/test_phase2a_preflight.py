"""Preflight failures preserve actual subprocess evidence and never grant PASS."""

import json
import os
import sys
import time
from pathlib import Path

import pytest


def test_preflight_child_failure_keeps_logs_and_blocks(tmp_path: Path) -> None:
    from benchmarks.phase2a_preflight import checked_run

    with pytest.raises(RuntimeError):
        checked_run(
            [sys.executable, "-c", 'print("actual failure");raise SystemExit(7)'],
            tmp_path / "probe",
            timeout=5,
        )
    assert "actual failure" in (tmp_path / "probe.stdout").read_text()
    assert json.loads((tmp_path / "probe.command.json").read_text())["exit_code"] == 7
    with pytest.raises(FileExistsError):
        checked_run([sys.executable, "-c", "pass"], tmp_path / "probe", timeout=5)


def test_preflight_watchdog_is_not_a_success(tmp_path: Path) -> None:
    from benchmarks.phase2a_preflight import checked_run

    with pytest.raises(TimeoutError):
        checked_run(
            [sys.executable, "-c", "import time;time.sleep(30)"],
            tmp_path / "slow",
            timeout=0.15,
        )
    record = json.loads((tmp_path / "slow.command.json").read_text())
    assert record["timed_out"] is True and record["exit_code"] != 0


@pytest.mark.skipif(sys.platform != "linux", reason="Linux descendant process accounting")
def test_preflight_timeout_stops_descendant_work(tmp_path: Path) -> None:
    from benchmarks.phase2a_preflight import checked_run

    pid_file = tmp_path / "descendant.pid"
    code = (
        "import subprocess,sys,time;from pathlib import Path;"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);"
        f"Path({str(pid_file)!r}).write_text(str(child.pid));time.sleep(30)"
    )
    pid = None
    try:
        with pytest.raises(TimeoutError):
            checked_run([sys.executable, "-c", code], tmp_path / "tree", timeout=0.5)
        pid = int(pid_file.read_text())
        for _ in range(20):
            status = Path(f"/proc/{pid}/stat")
            if not status.exists() or status.read_text().split()[2] == "Z":
                break
            time.sleep(0.02)
        else:
            pytest.fail("Descendant still executing after the preflight deadline")
    finally:
        if pid is None and pid_file.exists():
            pid = int(pid_file.read_text())
        if pid is not None:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass


@pytest.mark.skipif(sys.platform != "linux", reason="POSIX setup cleanup critical region")
def test_preflight_interrupt_after_spawn_still_cleans_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from benchmarks import phase2a_preflight

    calls = []

    def waited(pid, flags):
        calls.append("wait")
        return pid, 9

    def interrupted():
        raise KeyboardInterrupt

    monkeypatch.setattr(phase2a_preflight.os, "posix_spawn", lambda *a, **kw: 123)
    monkeypatch.setattr(phase2a_preflight.os, "waitpid", waited)
    monkeypatch.setattr(phase2a_preflight.time, "monotonic", interrupted)
    monkeypatch.setattr(phase2a_preflight.os, "killpg", lambda pid, sig: calls.append("stop-group"))
    with pytest.raises(KeyboardInterrupt):
        phase2a_preflight.checked_run(["python"], tmp_path / "interrupted", timeout=1)
    assert calls == ["stop-group", "wait"]


@pytest.mark.skipif(sys.platform != "linux", reason="POSIX signal mask inheritance")
def test_preflight_child_does_not_inherit_critical_region_signal_mask(tmp_path: Path) -> None:
    from benchmarks.phase2a_preflight import checked_run

    result = checked_run(
        [
            sys.executable,
            "-c",
            "import signal;print(signal.SIGINT in signal.pthread_sigmask(signal.SIG_BLOCK, []))",
        ],
        tmp_path / "mask",
        timeout=5,
    )
    assert result.strip() == "False"


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows Job Object required")
def test_windows_job_timeout_stops_descendant_heartbeat(tmp_path: Path) -> None:
    from benchmarks.phase2a_preflight import checked_run

    heartbeat = tmp_path / "heartbeat"
    worker = (
        "import time;from pathlib import Path;"
        f"p=Path({str(heartbeat)!r});"
        "exec('for i in range(1500):\\n p.write_text(str(i));time.sleep(.02)')"
    )
    parent = (
        "import subprocess,sys,time;"
        f"subprocess.Popen([sys.executable,'-c',{worker!r}]);time.sleep(30)"
    )
    with pytest.raises(TimeoutError):
        checked_run([sys.executable, "-c", parent], tmp_path / "job", timeout=2)
    assert heartbeat.exists()
    final = heartbeat.read_bytes()
    time.sleep(0.2)
    assert heartbeat.read_bytes() == final
