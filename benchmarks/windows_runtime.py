"""Native Windows process accounting; no Core or solver dependency at import time."""

from __future__ import annotations

import ctypes
import platform
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import JsonValue

    from benchmarks.run_benchmarks import ExecutionRecord, RunLimits


class ProcessMemory(ctypes.Structure):
    """PROCESS_MEMORY_COUNTERS: SIZE_T counters are bytes, including the peak."""

    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t)
        for name in (
            "PeakWorkingSetSize",
            "WorkingSetSize",
            "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage",
            "QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage",
            "PagefileUsage",
            "PeakPagefileUsage",
        )
    ]


class MemoryStatus(ctypes.Structure):
    """MEMORYSTATUSEX: native physical/commit availability in bytes."""

    _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong)
        for name in (
            "ullTotalPhys",
            "ullAvailPhys",
            "ullTotalPageFile",
            "ullAvailPageFile",
            "ullTotalVirtual",
            "ullAvailVirtual",
            "ullAvailExtendedVirtual",
        )
    ]


class JobBasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JobLimits(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", JobBasicLimits), ("IoInfo", ctypes.c_ulonglong * 6)] + [
        (name, ctypes.c_size_t)
        for name in (
            "ProcessMemoryLimit",
            "JobMemoryLimit",
            "PeakProcessMemoryUsed",
            "PeakJobMemoryUsed",
        )
    ]


def native_api() -> Any:
    """Bind pointer-sized signatures only on native x64 CPython 3.12 Windows."""
    if (
        sys.platform != "win32"
        or platform.machine().lower() not in ("amd64", "x86_64")
        or ctypes.sizeof(ctypes.c_void_p) != 8
        or sys.version_info[:2] != (3, 12)
        or platform.python_implementation() != "CPython"
    ):
        raise OSError("WINDOWS_NATIVE_REQUIRED")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "K32GetProcessMemoryInfo": [wintypes.HANDLE, ctypes.POINTER(ProcessMemory), wintypes.DWORD],
        "GetProcessTimes": [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)],
        "GlobalMemoryStatusEx": [ctypes.POINTER(MemoryStatus)],
        "IsProcessInJob": [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)],
        "SetInformationJobObject": [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD],
        "AssignProcessToJobObject": [wintypes.HANDLE, wintypes.HANDLE],
        "TerminateJobObject": [wintypes.HANDLE, wintypes.UINT],
        "CloseHandle": [wintypes.HANDLE],
    }
    for name, args in signatures.items():
        function = getattr(kernel, name)
        function.argtypes = args
        function.restype = wintypes.BOOL
    kernel.GetCurrentProcess.argtypes = []
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    return kernel


def _checked(ok: int) -> None:
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())


@contextmanager
def _defer_interrupt() -> Iterator[list[bool]]:
    """Keep ownership bookkeeping atomic with respect to console interruption."""
    interrupted = [False]
    previous = signal.getsignal(signal.SIGINT)

    def deferred(signum: int, frame: Any) -> None:
        interrupted[0] = True

    signal.signal(signal.SIGINT, deferred)
    try:
        yield interrupted
    finally:
        signal.signal(signal.SIGINT, previous)


def memory_status() -> dict[str, int]:
    """Fail closed when inherited job limits have not been accounted for."""
    kernel = native_api()
    in_job = wintypes.BOOL()
    _checked(kernel.IsProcessInJob(kernel.GetCurrentProcess(), None, ctypes.byref(in_job)))
    if in_job.value:
        raise OSError("JOB_MEMORY_ACCOUNTING_UNVERIFIED")
    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    _checked(kernel.GlobalMemoryStatusEx(ctypes.byref(status)))
    return {name: int(getattr(status, name)) for name, _ in MemoryStatus._fields_[2:]}


@contextmanager
def setup_process(argv: list[str], out: Any, err: Any) -> Iterator[Any]:
    """Assign a blocked trampoline to a kill-on-close job before it can spawn work."""
    kernel = native_api()
    job = kernel.CreateJobObjectW(None, None)
    _checked(bool(job))
    child: Any = None
    try:
        limits = JobLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        _checked(
            kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
        )
        trampoline = (
            "import subprocess,sys;"
            "token=sys.stdin.buffer.read(1);"
            "sys.stdin.close();"
            "sys.exit(subprocess.call(sys.argv[1:],stdin=subprocess.DEVNULL) "
            "if token==b'1' else 125)"
        )
        with _defer_interrupt() as interrupted:
            child = subprocess.Popen(
                [sys.executable, "-I", "-c", trampoline, *argv],
                cwd=Path(__file__).resolve().parents[1],
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            _checked(kernel.AssignProcessToJobObject(job, int(child._handle)))
            child.stdin.write(b"1")
            child.stdin.flush()
            child.stdin.close()
        if interrupted[0]:
            raise KeyboardInterrupt
        yield child
    finally:
        with _defer_interrupt():
            try:
                if child is not None:
                    try:
                        _checked(kernel.TerminateJobObject(job, 1))
                    finally:
                        if child.poll() is None:
                            child.kill()
                        child.wait(timeout=5)
                        child._handle.Close()
            finally:
                _checked(kernel.CloseHandle(job))


def machine_identity() -> dict[str, JsonValue]:
    """Stable native host identity; mutable availability is admission evidence only."""
    import hashlib
    import os
    import winreg

    native_api()
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
        machine_id = winreg.QueryValueEx(key, "MachineGuid")[0]
    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
    ) as key:
        cpu = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    return {
        "platform": sys.platform,
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "cpu_count": os.cpu_count(),
        "cpu_models": [cpu],
        "total_physical_bytes": memory_status()["ullTotalPhys"],
        "machine_id_sha256": hashlib.sha256(machine_id.encode()).hexdigest(),
        "python": sys.executable,
        "prefix": sys.prefix,
        "python_version": platform.python_version(),
        "runtime_env": {
            key: os.environ.get(key)
            for key in (
                "PYTHONHASHSEED",
                "OMP_NUM_THREADS",
                "MKL_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
            )
        },
    }


def supervise_windows(
    argv: tuple[str, ...],
    run_dir: Path,
    limits: RunLimits,
) -> ExecutionRecord:
    """Retain one Popen process handle through final peak/CPU queries and owned wait."""
    from benchmarks.run_benchmarks import SAMPLE_INTERVAL, ExecutionRecord, RunLimits

    limits = RunLimits.model_validate(limits.model_dump())
    run_dir = run_dir.absolute()
    run_dir.mkdir(parents=True, exist_ok=False)
    record = ExecutionRecord(
        argv=argv,
        run_dir=run_dir,
        stdout_path=run_dir / "stdout.json",
        stderr_path=run_dir / "stderr.txt",
        native_field="PeakWorkingSetSize",
        native_unit="bytes",
        measurement_method="windows_process_handle",
    )
    try:
        kernel = native_api()
    except OSError:
        record.error_type = "WINDOWS_NATIVE_REQUIRED"
        return record
    import threading

    if threading.current_thread() is not threading.main_thread():
        record.error_type = "MAIN_THREAD_REQUIRED"
        return record
    previous = signal.getsignal(signal.SIGINT)
    if previous not in (signal.default_int_handler, signal.SIG_DFL):
        record.error_type = "DEFAULT_SIGINT_HANDLER_REQUIRED"
        return record
    interrupted = False

    def defer_interrupt(signum: int, frame: Any) -> None:
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, defer_interrupt)
    started = time.monotonic()
    process: Any = None
    try:
        with record.stdout_path.open("xb") as out, record.stderr_path.open("xb") as err:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            record.pid = process.pid
            record.measurement_status = "BLOCKED"
            record.measurement_reason = "ACCOUNTING_INCOMPLETE"

            def sample() -> None:
                memory = ProcessMemory()
                memory.cb = ctypes.sizeof(memory)
                # CPython 3.12 owns this handle; querying by PID could race fast exit/PID reuse.
                _checked(
                    kernel.K32GetProcessMemoryInfo(
                        int(process._handle),
                        ctypes.byref(memory),
                        memory.cb,
                    )
                )
                peak = int(memory.PeakWorkingSetSize)
                if peak <= 0:
                    raise OSError("NATIVE_PEAK_UNAVAILABLE")
                record.native_peak_working_set_bytes = max(
                    peak,
                    record.native_peak_working_set_bytes or 0,
                )
                record.peak_resident_bytes = record.native_peak_working_set_bytes
                record.sample_count += 1
                record.sampled_peak_bytes = max(
                    int(memory.WorkingSetSize), record.sampled_peak_bytes or 0
                )

            try:
                while True:
                    sample()
                    if process.poll() is not None:
                        break
                    if interrupted:
                        record.stop_reason = "PARENT_INTERRUPTED"
                    elif time.monotonic() - started >= limits.watchdog_seconds:
                        record.stop_reason = "WATCHDOG"
                    elif record.peak_resident_bytes > limits.max_resident_bytes:
                        record.stop_reason = "RESOURCE_LIMIT"
                    if record.stop_reason is not None:
                        process.kill()
                        break
                    time.sleep(SAMPLE_INTERVAL)
            except KeyboardInterrupt:
                record.stop_reason = "PARENT_INTERRUPTED"
            except OSError as exc:
                record.stop_reason = "PROBE_ERROR"
                record.error_type = type(exc).__name__
            finally:
                if process.poll() is None:
                    process.kill()
                record.exit_code = process.wait(timeout=5)
            if record.stop_reason != "PROBE_ERROR":
                sample()
                times = [wintypes.FILETIME() for _ in range(4)]
                _checked(
                    kernel.GetProcessTimes(int(process._handle), *(ctypes.byref(t) for t in times))
                )
                record.cpu_seconds = (
                    sum((int(t.dwHighDateTime) << 32) | int(t.dwLowDateTime) for t in times[2:])
                    / 10_000_000
                )
                record.measurement_status = "OK"
                record.measurement_reason = None
    except KeyboardInterrupt:
        interrupted = True
        record.stop_reason = "PARENT_INTERRUPTED"
    except (OSError, subprocess.TimeoutExpired) as exc:
        record.error_type = type(exc).__name__
        record.measurement_status = "BLOCKED" if record.pid else "NOT_STARTED"
        record.measurement_reason = "CLEANUP_OR_ACCOUNTING_UNCONFIRMED"
    finally:
        try:
            if process is not None:
                if record.pid is None:
                    record.pid = process.pid
                    record.measurement_status = "BLOCKED"
                    record.measurement_reason = "ACCOUNTING_INCOMPLETE"
                if record.exit_code is None:
                    try:
                        process.kill()
                        record.exit_code = process.wait(timeout=5)
                    except (OSError, subprocess.TimeoutExpired) as exc:
                        record.error_type = type(exc).__name__
                        record.measurement_status = "BLOCKED"
                        record.measurement_reason = "REAP_UNCONFIRMED"
                process._handle.Close()
            if interrupted:
                record.stop_reason = "PARENT_INTERRUPTED"
            record.launch_to_exit_seconds = time.monotonic() - started
        finally:
            signal.signal(signal.SIGINT, previous)
    return ExecutionRecord.model_validate(record.model_dump())
