"""One-run Linux supervision primitives; no campaign CLI or school benchmarks."""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, Self

from pydantic import (
    Field,
    JsonValue,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

if TYPE_CHECKING:
    from tkb_core.solver.options import SolveOptions

from tkb_core.contracts.score import ScoreReport
from tkb_core.domain.models import DomainModel, NonNegativeInt, PositiveInt

SAMPLE_INTERVAL = 0.05
TERM_GRACE = 1.0
NonNegativeFloat = Annotated[StrictFloat, Field(ge=0)]
HarnessStatus = Literal[
    "COMPLETE",
    "WATCHDOG_TIMEOUT",
    "RESOURCE_STOP",
    "ENVIRONMENT_BLOCKED",
    "MEASUREMENT_BLOCKED",
    "OUTPUT_INVALID",
    "CRASH",
    "CANCELLED",
]


class RunLimits(DomainModel):
    """Explicit test/run limits, never a default school performance budget."""

    watchdog_seconds: Annotated[StrictFloat, Field(gt=0)]
    max_resident_bytes: PositiveInt


class ExecutionRecord(DomainModel):
    """Owned child evidence; unavailable measurements stay null."""

    schema_version: Literal["1.0"] = "1.0"
    argv: Annotated[tuple[StrictStr, ...], Field(min_length=1)]
    run_dir: Path
    stdout_path: Path
    stderr_path: Path
    pid: PositiveInt | None = None
    raw_wait_status: StrictInt | None = None
    exit_code: StrictInt | None = None
    signal: PositiveInt | None = None
    stop_reason: (
        Literal["WATCHDOG", "RESOURCE_LIMIT", "PROBE_ERROR", "PARENT_INTERRUPTED"] | None
    ) = None
    error_type: StrictStr | None = None
    launch_to_exit_seconds: NonNegativeFloat | None = None
    cpu_seconds: NonNegativeFloat | None = None
    native_peak_rss_kib: NonNegativeInt | None = None
    peak_resident_bytes: NonNegativeInt | None = None
    sampled_peak_bytes: NonNegativeInt | None = None
    sample_count: NonNegativeInt = 0
    measurement_status: Literal["OK", "BLOCKED", "NOT_STARTED"] = "NOT_STARTED"
    measurement_reason: StrictStr | None = "NOT_SPAWNED"
    native_field: Literal["ru_maxrss"] = "ru_maxrss"
    native_unit: Literal["KiB"] = "KiB"
    measurement_method: Literal["linux_wait4"] = "linux_wait4"

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.sample_count == 0 and self.sampled_peak_bytes is not None:
            raise ValueError("No RSS samples were collected")
        if self.sample_count > 0 and self.sampled_peak_bytes is None:
            raise ValueError("RSS sample count requires sampled peak")
        if self.measurement_status == "NOT_STARTED" and any(
            v is not None
            for v in (
                self.pid,
                self.cpu_seconds,
                self.peak_resident_bytes,
                self.native_peak_rss_kib,
            )
        ):
            raise ValueError("Unstarted execution cannot carry child measurements")
        if self.measurement_status == "OK":
            if any(
                v is None
                for v in (
                    self.pid,
                    self.raw_wait_status,
                    self.exit_code,
                    self.cpu_seconds,
                    self.native_peak_rss_kib,
                    self.peak_resident_bytes,
                )
            ):
                raise ValueError("Successful measurement requires kernel evidence")
            if self.measurement_reason is not None:
                raise ValueError("Successful measurement cannot have failure reason")
        elif not self.measurement_reason:
            raise ValueError("Unavailable measurement requires reason")
        if self.native_peak_rss_kib is not None and self.peak_resident_bytes != kib_to_bytes(
            self.native_peak_rss_kib
        ):
            raise ValueError("Inconsistent peak units")
        if self.signal is not None and self.exit_code != -self.signal:
            raise ValueError("Signal/exit mismatch")
        return self


class OutputVerification(DomainModel):
    """Independent output result, separate from process/measurement success."""

    status: Literal["SKIPPED", "VALID_SCHEDULE", "VALID_CORE_ERROR", "INVALID"] = "SKIPPED"
    solver_status: StrictStr | None = None
    valid_schedule: StrictBool = False
    score: ScoreReport | None = None
    diagnostics: tuple[StrictStr, ...] = ()

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.valid_schedule != (self.status == "VALID_SCHEDULE"):
            raise ValueError("Only verified schedules can claim validity")
        return self


class RunRecord(DomainModel):
    """Tooling outcome; never a replacement for ScheduleResult."""

    schema_version: Literal["1.0"] = "1.0"
    harness_status: HarnessStatus
    execution: ExecutionRecord
    output: OutputVerification
    identity: dict[str, JsonValue]
    parent_verification_seconds: NonNegativeFloat = 0.0
    valid_schedule: StrictBool = False
    first_feasible_elapsed_seconds: None = None
    first_feasible_reason: Literal["NOT_INSTRUMENTED"] = "NOT_INSTRUMENTED"

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.valid_schedule != (
            self.harness_status == "COMPLETE" and self.output.valid_schedule
        ):
            raise ValueError("Only complete verified runs can publish schedules")
        return self


def kib_to_bytes(value: int) -> int:
    """Convert Linux kernel KiB; reject bool/coercion and negative values."""
    if type(value) is not int or value < 0:
        raise ValueError("Invalid KiB measurement")
    return value * 1024


def _read_rss(pid: int) -> int:
    pages = int(Path(f"/proc/{pid}/statm").read_text().split()[1])
    if pages < 0:
        raise ValueError("Invalid resident pages")
    return pages * os.sysconf("SC_PAGE_SIZE")


def _linux_available() -> bool:
    return (
        sys.platform == "linux"
        and all(
            hasattr(os, n)
            for n in (
                "posix_spawn",
                "POSIX_SPAWN_OPEN",
                "wait4",
                "WNOHANG",
                "waitid",
                "P_PID",
                "WNOWAIT",
                "WEXITED",
                "waitstatus_to_exitcode",
                "kill",
            )
        )
        and hasattr(signal, "pthread_sigmask")
    )


def supervise_linux(argv: tuple[str, ...], run_dir: Path, limits: RunLimits) -> ExecutionRecord:
    """Own one child through spawn, stop and wait4; never reap another PID."""
    import math

    limits = RunLimits.model_validate(limits.model_dump())
    run_dir = run_dir.absolute()
    r = ExecutionRecord(
        argv=argv,
        run_dir=run_dir,
        stdout_path=run_dir / "stdout.json",
        stderr_path=run_dir / "stderr.txt",
    )
    run_dir.parent.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir()
    if not _linux_available():
        r.error_type = "UnsupportedPlatform"
        return r
    pid: int | None = None
    owned = False
    probe_failed = False
    started = time.monotonic()
    term_at: float | None = None
    killed = False

    def poll() -> bool:
        nonlocal owned
        assert pid is not None
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
        try:
            try:
                waited, status, usage = os.wait4(pid, os.WNOHANG)
            except InterruptedError:
                return True
            except OSError as exc:
                owned = False
                r.error_type = type(exc).__name__
                r.measurement_reason = "OWNERSHIP_OR_WAIT4_LOST"
                r.stop_reason = r.stop_reason or "PROBE_ERROR"
                return False
            if waited == 0:
                return True
            owned = False
            if waited != pid:
                r.measurement_reason = "PID_MISMATCH"
                r.stop_reason = r.stop_reason or "PROBE_ERROR"
                return False
            r.raw_wait_status = status
            r.exit_code = os.waitstatus_to_exitcode(status)
            r.signal = -r.exit_code if r.exit_code < 0 else None
            r.launch_to_exit_seconds = time.monotonic() - started
            try:
                cpu = usage.ru_utime + usage.ru_stime
                peak = kib_to_bytes(usage.ru_maxrss)
                if not math.isfinite(cpu) or cpu < 0:
                    raise ValueError("Invalid CPU measurement")
                r.cpu_seconds = cpu
                r.native_peak_rss_kib = usage.ru_maxrss
                r.peak_resident_bytes = peak
                if not probe_failed:
                    r.measurement_status = "OK"
                    r.measurement_reason = None
            except (ValueError, TypeError, AttributeError) as exc:
                r.error_type = type(exc).__name__
                r.measurement_reason = "INVALID_RUSAGE"
            return False
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)

    def send_stop(sig: int) -> None:
        nonlocal owned
        assert pid is not None
        try:
            # WNOWAIT checks ownership without competing with wait4's reap.
            os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except OSError as exc:
            owned = False
            r.measurement_status = "BLOCKED"
            r.measurement_reason = "OWNERSHIP_NOT_CONFIRMED"
            r.error_type = type(exc).__name__
            return
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass

    try:
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            pid = os.posix_spawn(
                argv[0],
                argv,
                dict(os.environ),
                setsigmask=mask,
                file_actions=[
                    (os.POSIX_SPAWN_OPEN, 0, "/dev/null", os.O_RDONLY, 0),
                    (os.POSIX_SPAWN_OPEN, 1, str(r.stdout_path), flags, 0o600),
                    (os.POSIX_SPAWN_OPEN, 2, str(r.stderr_path), flags, 0o600),
                ],
            )
            owned = True
            r.pid = pid
            r.measurement_status = "BLOCKED"
            r.measurement_reason = "NOT_REAPED"
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        while owned:
            if not poll():
                break
            if time.monotonic() - started >= limits.watchdog_seconds:
                r.stop_reason = "WATCHDOG"
                break
            try:
                rss = _read_rss(pid)
            except (OSError, ValueError, IndexError) as exc:
                if isinstance(exc, (FileNotFoundError, ProcessLookupError)) and not poll():
                    break
                probe_failed = True
                r.stop_reason = "PROBE_ERROR"
                r.error_type = type(exc).__name__
                r.measurement_reason = "RSS_PROBE_FAILED"
                break
            r.sample_count += 1
            r.sampled_peak_bytes = max(rss, r.sampled_peak_bytes or 0)
            if rss > limits.max_resident_bytes:
                r.stop_reason = "RESOURCE_LIMIT"
                break
            time.sleep(SAMPLE_INTERVAL)
    except BaseException as exc:
        r.error_type = type(exc).__name__
        if pid is not None:
            r.pid = pid
            r.stop_reason = "PARENT_INTERRUPTED"
            r.measurement_status = "BLOCKED"
            r.measurement_reason = "PARENT_INTERRUPTED"
        elif not isinstance(exc, OSError):
            r.stop_reason = "PARENT_INTERRUPTED"
    finally:
        # Stop first: unexpected polling exceptions must not bypass signal delivery.
        while owned:
            try:
                if term_at is None:
                    term_at = time.monotonic()
                    send_stop(signal.SIGTERM)
                elif not killed and time.monotonic() - term_at >= TERM_GRACE:
                    killed = True
                    send_stop(signal.SIGKILL)
                if not owned or not poll():
                    break
            except BaseException as exc:
                r.error_type = type(exc).__name__
                r.measurement_status = "BLOCKED"
                r.measurement_reason = "WAIT4_CLEANUP_FAILED"
                if killed:
                    # No wait backend: fail closed, never invent a reap or spin forever.
                    owned = False
                    r.measurement_reason = "REAP_UNCONFIRMED"
                    break
            time.sleep(SAMPLE_INTERVAL)
    return ExecutionRecord.model_validate(r.model_dump())


def _json_object(raw: str) -> dict[str, Any]:
    import json

    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError("Duplicate JSON key")
        return result

    def invalid(value: str) -> None:
        raise ValueError("Non-finite JSON")

    result = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    if not isinstance(result, dict):
        raise ValueError("Expected object")
    return result


def verify_cli_output(
    input_path: Path, result_path: Path, execution: ExecutionRecord
) -> OutputVerification:
    """Reuse public CLI checks for hard, score and proof-metadata consistency."""
    import contextlib
    import io

    from tkb_core.cli import main
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.contracts.output import ScheduleResult, SolverRunMetadata

    try:
        problem = ScheduleInput.model_validate(_json_object(input_path.read_text(encoding="utf-8")))
        if problem.schema_version != "1.1":
            raise ValueError("Expected input1.1")
        raw = _json_object(execution.stdout_path.read_text(encoding="utf-8"))
        if result_path.exists() and _json_object(result_path.read_text(encoding="utf-8")) != raw:
            raise ValueError("Stdout/result mismatch")
        if execution.exit_code == 2 and raw.get("schema_version") == "1.0":
            if set(raw) != {"schema_version", "status", "diagnostics"} or raw["status"] not in (
                "INPUT_INVALID",
                "UNSUPPORTED_FEATURE",
            ):
                raise ValueError("Invalid error envelope")
            diagnostics = raw["diagnostics"]
            if (
                not isinstance(diagnostics, list)
                or not diagnostics
                or any(
                    not isinstance(d, dict)
                    or set(d) != {"code", "message"}
                    or any(not isinstance(d[k], str) or not d[k] for k in ("code", "message"))
                    for d in diagnostics
                )
            ):
                raise ValueError("Invalid diagnostic envelope")
            return OutputVerification(
                status="VALID_CORE_ERROR",
                solver_status=str(raw["status"]),
                diagnostics=tuple(d["code"] for d in diagnostics),
            )
        if not result_path.is_file():
            raise ValueError("Missing result")
        result = ScheduleResult.model_validate(raw)
        pairs = {
            "FEASIBLE": 0,
            "OPTIMAL": 0,
            "INFEASIBLE": 3,
            "UNKNOWN": 4,
            "INPUT_INVALID": 2,
            "UNSUPPORTED_FEATURE": 2,
            "MODEL_INVALID": 5,
        }
        if result.schema_version != "1.2" or execution.exit_code != pairs.get(result.status):
            raise ValueError("Exit/version/status mismatch")
        if result.input_fingerprint != problem.fingerprint() and not (
            result.status == "INPUT_INVALID"
            and result.input_fingerprint is None
            and isinstance(result.metadata, SolverRunMetadata)
            and not result.metadata.solver_executed
        ):
            raise ValueError("Stale result")
        if execution.exit_code != 0:
            if (
                result.valid_schedule
                or result.assignments
                or (result.quality and result.quality.score is not None)
            ):
                raise ValueError("Error cannot expose a schedule")
            return OutputVerification(
                status="VALID_CORE_ERROR",
                solver_status=result.status,
                diagnostics=tuple(d.code for d in result.diagnostics),
            )
        if not result.valid_schedule:
            raise ValueError("No valid schedule")
        checked = []
        for command, expected in (
            ("validate-schedule", "SCHEDULE_VALID"),
            ("evaluate-score", "OK"),
        ):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main([command, str(input_path), str(result_path)])
            parsed = _json_object(output.getvalue())
            if code != 0 or parsed.get("status") != expected:
                raise ValueError("Independent verification failed")
            checked.append(parsed)
        score = ScoreReport.model_validate(checked[1])
        return OutputVerification(
            status="VALID_SCHEDULE", valid_schedule=True, solver_status=result.status, score=score
        )
    except (OSError, ValueError, TypeError, AttributeError, RecursionError) as exc:
        return OutputVerification(status="INVALID", diagnostics=(type(exc).__name__,))


def classify_run(execution: ExecutionRecord, output: OutputVerification) -> HarnessStatus:
    """Apply harness precedence without losing either underlying evidence record."""
    if execution.stop_reason == "PARENT_INTERRUPTED":
        return "CANCELLED"
    if execution.stop_reason == "WATCHDOG":
        return "WATCHDOG_TIMEOUT"
    if execution.stop_reason == "RESOURCE_LIMIT":
        return "RESOURCE_STOP"
    if execution.pid is None:
        return "ENVIRONMENT_BLOCKED"
    if (
        execution.stop_reason is None
        and execution.exit_code is not None
        and (execution.signal is not None or execution.exit_code not in (0, 2, 3, 4, 5))
    ):
        return "CRASH"
    if execution.stop_reason == "PROBE_ERROR" or execution.measurement_status != "OK":
        return "MEASUREMENT_BLOCKED"
    if output.status not in ("VALID_SCHEDULE", "VALID_CORE_ERROR"):
        return "OUTPUT_INVALID"
    return "COMPLETE"


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runtime_identity(
    *, python: Path, preflight_dir: Path, lock_path: Path
) -> dict[str, JsonValue]:
    import importlib.metadata as md
    import zipfile

    import tkb_core

    if sys.platform != "linux":
        raise ValueError("PLATFORM_UNSUPPORTED")
    if not _linux_available():
        raise ValueError("API_MISSING")
    manifest = _json_object((preflight_dir / "preflight-manifest.json").read_text())
    if manifest["preflight_schema_version"] != "1.0" or manifest["linux_status"] != "PASS":
        raise ValueError("PREFLIGHT_INVALID")
    env_path = preflight_dir / "environment-solver.json"
    if _sha(env_path) != manifest["files"]["environment-solver.json"]:
        raise ValueError("ENVIRONMENT_HASH_MISMATCH")
    env = _json_object(env_path.read_text())
    wheels = list((preflight_dir / "distribution").glob("*.whl"))
    if len(wheels) != 1 or _sha(wheels[0]) != manifest["wheel_sha256"]:
        raise ValueError("WHEEL_HASH_MISMATCH")
    if _sha(lock_path) != manifest["uv_lock_sha256"]:
        raise ValueError("LOCK_HASH_MISMATCH")
    expected = env["installed_versions"]
    if (
        not isinstance(expected, dict)
        or not {"vnedu-tkb-core", "pydantic", "ortools"} <= expected.keys()
    ):
        raise ValueError("VERSION_MANIFEST_INVALID")
    try:
        actual: dict[str, JsonValue] = {name: md.version(name) for name in expected}
    except md.PackageNotFoundError as exc:
        raise ValueError("VERSION_MISSING") from exc
    if actual != expected:
        raise ValueError("VERSION_MISMATCH")
    if python.absolute() != Path(sys.executable).absolute() or not python.is_file():
        raise ValueError("PYTHON_IDENTITY_MISMATCH")
    if tkb_core.__file__ is None:
        raise ValueError("EDITABLE_OR_UNKNOWN_PACKAGE")
    package = Path(tkb_core.__file__).resolve().parent
    if not package.is_relative_to(Path(sys.prefix).resolve()) or "site-packages" not in str(
        package
    ):
        raise ValueError("EDITABLE_PACKAGE_NOT_ALLOWED")
    direct = md.distribution("vnedu-tkb-core").read_text("direct_url.json")
    if direct and _json_object(direct).get("dir_info", {}).get("editable", False):
        raise ValueError("EDITABLE_PACKAGE_NOT_ALLOWED")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = [n for n in archive.namelist() if n.startswith("tkb_core/") and n.endswith(".py")]
        installed = {
            str(p.relative_to(package.parent)).replace("\\", "/") for p in package.rglob("*.py")
        }
        if not names or len(names) != len(set(names)) or set(names) != installed:
            raise ValueError("WHEEL_SOURCE_MEMBERSHIP")
        for name in names:
            if ".." in Path(name).parts or (package.parent / name).read_bytes() != archive.read(
                name
            ):
                raise ValueError("WHEEL_SOURCE_MISMATCH")
    return {
        "wheel_sha256": str(manifest["wheel_sha256"]),
        "uv_lock_sha256": str(manifest["uv_lock_sha256"]),
        "core_tree": str(env["core_tree"]),
        "core_commit": str(env["git_commit"]),
        "installed_versions": actual,
        "tkb_core_file": str(package / "__init__.py"),
        "tooling_source_sha256": _sha(Path(__file__)),
    }


def run_cli_once(
    *,
    python: Path,
    input_path: Path,
    run_dir: Path,
    preflight_dir: Path,
    lock_path: Path,
    input_sha256: str,
    limits: RunLimits,
    options: SolveOptions,
) -> RunRecord:
    """Supervise one explicitly requested tiny/CLI run; no campaign entrypoint."""
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.solver.options import SolveOptions

    python, input_path, run_dir = python.absolute(), input_path.absolute(), run_dir.absolute()
    if run_dir.exists() or run_dir.is_symlink():
        raise FileExistsError(run_dir)
    identity: dict[str, JsonValue] = {"expected_input_sha256": input_sha256}
    argv: tuple[str, ...] = (
        str(python),
        "-I",
        "-m",
        "tkb_core.cli",
        "solve",
        str(input_path),
        "--output",
        str(run_dir / "result.json"),
    )
    try:
        limits = RunLimits.model_validate(limits.model_dump())
        options = SolveOptions.model_validate(options.model_dump())
        if _sha(input_path) != input_sha256:
            raise ValueError("INPUT_HASH_MISMATCH")
        identity.update(
            _runtime_identity(python=python, preflight_dir=preflight_dir, lock_path=lock_path)
        )
        import hashlib

        captured = input_path.read_bytes()
        captured_sha = hashlib.sha256(captured).hexdigest()
        if captured_sha != input_sha256:
            raise ValueError("INPUT_CHANGED_BEFORE_SPAWN")
        problem = ScheduleInput.model_validate(_json_object(captured.decode("utf-8")))
        if problem.schema_version != "1.1":
            raise ValueError("INPUT_VERSION_UNSUPPORTED")
        identity.update(
            {
                "input_sha256": captured_sha,
                "input_fingerprint": problem.fingerprint(),
                "options": options.model_dump(mode="json"),
                "limits": limits.model_dump(mode="json"),
            }
        )
        if _sha(input_path) != input_sha256:
            raise ValueError("INPUT_CHANGED_BEFORE_SPAWN")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        run_dir.mkdir()
        e = ExecutionRecord(
            argv=argv,
            run_dir=run_dir,
            stdout_path=run_dir / "stdout.json",
            stderr_path=run_dir / "stderr.txt",
            error_type=type(exc).__name__,
        )
        output = OutputVerification(diagnostics=(str(exc),))
        record = RunRecord(
            harness_status="ENVIRONMENT_BLOCKED", execution=e, output=output, identity=identity
        )
    else:
        argv += (
            "--time-limit",
            str(options.time_limit_seconds),
            "--workers",
            str(options.num_workers),
            "--seed",
            str(options.seed),
            "--max-slots",
            str(options.max_slots),
            "--max-occurrences",
            str(options.max_occurrences),
            "--max-placements",
            str(options.max_placements),
            "--max-occupancy-terms",
            str(options.max_occupancy_terms),
        )
        e = supervise_linux(argv, run_dir, limits)
        started = time.monotonic()
        try:
            if _sha(input_path) != input_sha256:
                raise ValueError("INPUT_CHANGED")
            output = verify_cli_output(input_path, run_dir / "result.json", e)
            if _sha(input_path) != input_sha256:
                raise ValueError("INPUT_CHANGED")
        except (OSError, ValueError) as exc:
            output = OutputVerification(
                status="INVALID", diagnostics=("INPUT_CHANGED", type(exc).__name__)
            )
        status = classify_run(e, output)
        record = RunRecord(
            harness_status=status,
            execution=e,
            output=output,
            identity=identity,
            valid_schedule=status == "COMPLETE" and output.valid_schedule,
            parent_verification_seconds=time.monotonic() - started,
        )
    with (run_dir / "run.json").open("x", encoding="utf-8") as handle:
        handle.write(record.model_dump_json(indent=2) + "\n")
    return record
