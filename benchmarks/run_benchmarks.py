"""Explicit Linux campaign controls and one-child supervision, outside Scheduling Core."""

from __future__ import annotations

import os
import signal
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

from pydantic import (
    Field,
    JsonValue,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from tkb_core.contracts.score import ScoreReport
from tkb_core.domain.models import DomainModel, NonNegativeInt, PositiveInt
from tkb_core.solver.options import SolveOptions

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


# Campaign metadata stays outside Core and never imports the generator into this controller.
SHA = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
CampaignId = Annotated[StrictStr, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")]
Phase = Literal["warmup", "pilot", "primary"]
ROOT = Path(__file__).resolve().parents[1]


def _repository_owner_root(root: Path) -> Path:
    """Linked worktrees share one owner marker in their common Git directory."""
    marker = root / ".git"
    if marker.is_file():
        prefix, sep, location = marker.read_text().strip().partition(": ")
        if prefix != "gitdir" or not sep:
            raise ValueError("Unknown Git worktree marker")
        gitdir = (root / location).resolve()
    else:
        gitdir = marker.resolve()
    shared = gitdir / "commondir"
    common = (gitdir / shared.read_text().strip()).resolve() if shared.is_file() else gitdir
    if not common.is_dir():
        raise ValueError("Repository owner scope unknown")
    return common / "tkb-campaign-owner"


_OWNER_ROOT = _repository_owner_root(ROOT)
_BUDGETS = {
    10: (60.0, 150.0, 1024**3),
    20: (120.0, 210.0, 2 * 1024**3),
    40: (180.0, 270.0, 4 * 1024**3),
}
_PROFILES = ("BASE", "MIXED", "TIGHT", "UNSAT_CAPACITY")
_META_KEYS = {
    "benchmark_schema_version",
    "dataset_id",
    "class_count",
    "profile",
    "seed",
    "input_fingerprint",
    "ground_truth",
    "known_optimum",
    "baseline_score",
    "p2_lower_bound",
    "capacity_proof",
    "dimensions",
    "sources",
    "files",
}


class PlannedCase(DomainModel):
    """An immutable-policy reference to input bytes, not a generated school input."""

    run_id: StrictStr
    dataset_id: StrictStr
    phase: Phase
    repeat: Annotated[NonNegativeInt, Field(le=3)]
    class_count: Literal[10, 20, 40] | None
    profile: Literal["BASE", "MIXED", "TIGHT", "UNSAT_CAPACITY", "WARMUP"]
    generator_seed: NonNegativeInt
    input_path: Path
    dataset_manifest: Path | None
    manifest_sha256: SHA | None
    input_sha256: SHA
    input_fingerprint: SHA
    ground_truth: Literal["FEASIBLE", "INFEASIBLE"]
    options: SolveOptions
    limits: RunLimits

    @model_validator(mode="after")
    def fixed_policy(self) -> Self:
        if self.phase == "warmup":
            if self.class_count is not None or self.profile != "WARMUP" or self.repeat != 0:
                raise ValueError("Invalid warmup membership")
            budget = (10.0, 15.0, 256 * 1024**2)
        else:
            if self.class_count is None or self.profile == "WARMUP":
                raise ValueError("Invalid dataset reference")
            budget = _BUDGETS[self.class_count]
            expected = f"c{self.class_count}-{self.profile.lower()}-s{self.generator_seed}"
            if self.dataset_id != expected or self.generator_seed not in (101, 102, 103):
                raise ValueError("Unknown dataset")
            if self.dataset_manifest is None or self.manifest_sha256 is None:
                raise ValueError("Missing dataset manifest")
            if self.phase == "pilot" and (self.dataset_id != "c10-base-s101" or self.repeat != 0):
                raise ValueError("Pilot policy differs")
            if self.phase == "primary" and self.repeat not in (1, 2, 3):
                raise ValueError("Invalid repeat")
        if (
            self.options.time_limit_seconds,
            self.limits.watchdog_seconds,
            self.limits.max_resident_bytes,
        ) != budget:
            raise ValueError("Fixed budget changed")
        expected_options = SolveOptions(time_limit_seconds=budget[0])
        if self.options != expected_options:
            raise ValueError("Fixed solver options changed")
        if self.ground_truth != ("INFEASIBLE" if self.profile == "UNSAT_CAPACITY" else "FEASIBLE"):
            raise ValueError("Ground truth/profile mismatch")
        expected_id = f"{self.phase}-{self.dataset_id}-{self.input_sha256}-w1-s42-r{self.repeat}"
        if self.run_id != expected_id:
            raise ValueError("Run identity mismatch")
        return self


class CampaignPlan(DomainModel):
    """Frozen primary order and separate pilot/warmup membership."""

    schema_version: Literal["1.0"] = "1.0"
    policy: Literal["phase2a-linux-primary-v1"] = "phase2a-linux-primary-v1"
    campaign_id: CampaignId
    machine_id: CampaignId
    bundle_dir: Path
    bundle_sha256: SHA
    source_ids: dict[str, SHA]
    dataset_sources: dict[str, SHA]
    order_seed: Literal[2026] = 2026
    primary: tuple[PlannedCase, ...]
    pilot: PlannedCase
    warmup: PlannedCase | None = None
    sealed: StrictBool = False
    preflight_dir: Path | None = None
    preflight_sha256: SHA | None = None
    runtime_identity: dict[str, JsonValue] = Field(default_factory=dict)
    environment: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def membership(self) -> Self:
        import random

        expected = {
            f"c{size}-{profile.lower()}-s{seed}"
            for size in _BUDGETS
            for profile in _PROFILES
            for seed in (101, 102, 103)
        }
        if len(self.primary) != 108 or len({c.run_id for c in self.primary}) != 108:
            raise ValueError("Primary must contain108 unique rows")
        keys = {(c.dataset_id, c.repeat) for c in self.primary if c.phase == "primary"}
        if keys != {(d, r) for d in expected for r in (1, 2, 3)} or self.pilot.phase != "pilot":
            raise ValueError("Phase membership changed")
        rng = random.Random(2026)
        order: list[tuple[str, int]] = []
        for repeat in (1, 2, 3):
            ids = sorted(expected)
            rng.shuffle(ids)
            order.extend((d, repeat) for d in ids)
        if [(c.dataset_id, c.repeat) for c in self.primary] != order:
            raise ValueError("Frozen order differs from policy")
        if self.pilot.run_id in {c.run_id for c in self.primary}:
            raise ValueError("Pilot counted twice")
        if self.sealed and (
            self.warmup is None
            or self.preflight_dir is None
            or self.preflight_sha256 is None
            or not self.runtime_identity
            or not self.environment
        ):
            raise ValueError("Sealed plan lacks preflight identity")
        return self


class HeadroomCheck(DomainModel):
    status: Literal["PASS", "BLOCKED"]
    target_bytes: PositiveInt
    required_bytes: PositiveInt
    available_bytes: NonNegativeInt | None = None
    host_available_bytes: NonNegativeInt | None = None
    scopes: tuple[dict[str, JsonValue], ...] = ()
    reason: StrictStr | None = None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.required_bytes != self.target_bytes + 2 * 1024**3:
            raise ValueError("Headroom must include2GiB reserve")
        if self.status == "PASS" and (
            self.available_bytes is None
            or self.host_available_bytes is None
            or self.available_bytes < self.required_bytes
            or self.available_bytes > self.host_available_bytes
            or self.reason is not None
        ):
            raise ValueError("Headroom PASS lacks verified availability")
        if self.status == "BLOCKED" and not self.reason:
            raise ValueError("Blocked headroom needs reason")
        return self


class CaseVerdict(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    correctness: Literal["PASS", "FAIL", "NOT_ASSESSED"] = "NOT_ASSESSED"
    performance: Literal["MET", "NOT_MET", "NOT_ASSESSED", "NOT_APPLICABLE"] = "NOT_ASSESSED"
    quality: Literal["BETTER", "EQUAL", "WORSE", "NO_SCHEDULE", "NOT_APPLICABLE"] = "NO_SCHEDULE"
    reasons: tuple[StrictStr, ...] = ()
    run_sha256: SHA
    dataset_manifest_sha256: SHA | None = None


class CampaignState(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    plan_sha256: SHA
    phase: Phase
    status: Literal["COMPLETE", "BLOCKED", "STOPPED", "NEEDS_REVIEW", "CANCELLED"]
    rows: dict[str, Literal["NOT_STARTED", "NOT_STARTED_GATE_BLOCKED", "TERMINAL", "PARTIAL"]]
    attempted: NonNegativeInt = 0
    completed: NonNegativeInt = 0
    failed: NonNegativeInt = 0
    pending: NonNegativeInt = 0
    reason: StrictStr | None = None


def _source_ids() -> dict[str, str]:
    return {
        "controller": _sha(Path(__file__)),
        "generator": _sha(ROOT / "benchmarks/generate_synthetic.py"),
        "lock": _sha(ROOT / "uv.lock"),
    }


def _json_bytes(model: DomainModel) -> bytes:
    import json

    return (
        json.dumps(model.model_dump(mode="json"), sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()


def _safe_file(base: Path, name: str) -> Path:
    path = base / name
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError("Artifact escapes bundle")
    return path


def build_campaign_plan(bundle_dir: Path, campaign_id: str, machine_id: str) -> CampaignPlan:
    """Read frozen metadata and create deterministic108 rows; never solve or prepare."""
    import random

    root = bundle_dir.absolute()
    bundle = _json_object((root / "manifest.json").read_text(encoding="utf-8"))
    if (
        set(bundle) != {"benchmark_schema_version", "protocol", "revision", "datasets"}
        or bundle["benchmark_schema_version"] != "1.0"
        or bundle["protocol"] != "phase2a-operational-v1"
    ):
        raise ValueError("Unknown bundle envelope")
    expected = {
        f"c{size}-{profile.lower()}-s{seed}"
        for size in _BUDGETS
        for profile in _PROFILES
        for seed in (101, 102, 103)
    }
    entries = bundle["datasets"]
    if (
        not isinstance(entries, list)
        or len(entries) != 36
        or {e["dataset_id"] for e in entries} != expected
    ):
        raise ValueError("Dataset membership drift")
    cases = {}
    sources = None
    for entry in entries:
        if set(entry) != {"dataset_id", "manifest_sha256"}:
            raise ValueError("Unknown bundle entry")
        base = _safe_file(root, entry["dataset_id"])
        path = base / "manifest.json"
        if _sha(path) != entry["manifest_sha256"]:
            raise ValueError("Dataset manifest checksum drift")
        data = _json_object(path.read_text(encoding="utf-8"))
        if (
            set(data) != _META_KEYS
            or data["benchmark_schema_version"] != "1.0"
            or data["dataset_id"] != entry["dataset_id"]
        ):
            raise ValueError("Dataset envelope drift")
        if sources is None:
            sources = data["sources"]
        if sources != data["sources"]:
            raise ValueError("Dataset source identities differ")
        names = (
            {"input.json", "provenance-input.json", "provenance-witness.json"}
            if data["profile"] == "UNSAT_CAPACITY"
            else {"input.json", "witness.json"}
        )
        if set(data["files"]) != names:
            raise ValueError("Artifact membership drift")
        for name, digest in data["files"].items():
            if _sha(_safe_file(base, name)) != digest:
                raise ValueError("Input/witness checksum drift")
        budget = _BUDGETS.get(data["class_count"])
        if budget is None:
            raise ValueError("Unsupported size")
        cases[data["dataset_id"]] = dict(
            dataset_id=data["dataset_id"],
            class_count=data["class_count"],
            profile=data["profile"],
            generator_seed=data["seed"],
            input_path=base / "input.json",
            dataset_manifest=path,
            manifest_sha256=entry["manifest_sha256"],
            input_sha256=data["files"]["input.json"],
            input_fingerprint=data["input_fingerprint"],
            ground_truth=data["ground_truth"],
            options=SolveOptions(time_limit_seconds=budget[0]),
            limits=RunLimits(watchdog_seconds=budget[1], max_resident_bytes=budget[2]),
        )

    def row(ident: str, phase: Phase, repeat: int) -> PlannedCase:
        data = cases[ident]
        return PlannedCase(
            **data,
            phase=phase,
            repeat=repeat,
            run_id=f"{phase}-{ident}-{data['input_sha256']}-w1-s42-r{repeat}",
        )

    rng = random.Random(2026)
    primary: list[PlannedCase] = []
    for repeat in (1, 2, 3):
        ids = sorted(cases)
        rng.shuffle(ids)
        primary.extend(row(i, "primary", repeat) for i in ids)
    return CampaignPlan(
        campaign_id=campaign_id,
        machine_id=machine_id,
        bundle_dir=root,
        bundle_sha256=_sha(root / "manifest.json"),
        source_ids=_source_ids(),
        dataset_sources=sources or {},
        primary=tuple(primary),
        pilot=row("c10-base-s101", "pilot", 0),
    )


_PROC_ROOT = Path("/proc")
_CGROUP_ROOT = Path("/sys/fs/cgroup")


def check_headroom(memory_target_bytes: int) -> HeadroomCheck:
    """Conservative admission estimate across the verified visible cgroup2 hierarchy."""
    import re

    if type(memory_target_bytes) is not int or memory_target_bytes <= 0:
        raise ValueError("Positive byte target required")
    required = memory_target_bytes + 2 * 1024**3
    host = None
    scopes: list[dict[str, JsonValue]] = []
    try:
        if sys.platform != "linux":
            raise ValueError("Linux required")
        mem = next(
            line
            for line in (_PROC_ROOT / "meminfo").read_text().splitlines()
            if line.startswith("MemAvailable:")
        )
        _, amount, unit = mem.split()
        if unit != "kB" or not amount.isdigit():
            raise ValueError("Unknown MemAvailable unit")
        host = int(amount) * 1024
        mounts = []

        def decode(value: str) -> str:
            return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), value)

        for line in (_PROC_ROOT / "self/mountinfo").read_text().splitlines():
            left, sep, right = line.partition(" - ")
            fields = left.split()
            if sep and right.split()[0] == "cgroup2" and decode(fields[4]) == str(_CGROUP_ROOT):
                mounts.append(decode(fields[3]))
        if (
            mounts != ["/"]
            or "memory" not in (_CGROUP_ROOT / "cgroup.controllers").read_text().split()
        ):
            raise ValueError("Unverified cgroup2 mount/controller")
        entries = [
            line[3:]
            for line in (_PROC_ROOT / "self/cgroup").read_text().splitlines()
            if line.startswith("0::")
        ]
        if len(entries) != 1 or not entries[0].startswith("/") or entries[0] == "/":
            raise ValueError("Unverified root/namespace")
        base = _CGROUP_ROOT.resolve()
        current = (base / entries[0].lstrip("/")).resolve()
        if not current.is_relative_to(base):
            raise ValueError("Scope escapes hierarchy")
        available = host
        for scope in [current, *current.parents]:
            if not scope.is_relative_to(base):
                break
            if scope == base:
                if (scope / "memory.max").exists() or (scope / "memory.current").exists():
                    raise ValueError("Mount root is not verified host root")
                continue
            maximum = (scope / "memory.max").read_text().strip()
            used = (scope / "memory.current").read_text().strip()
            if not used.isdigit() or (maximum != "max" and not maximum.isdigit()):
                raise ValueError("Malformed memory accounting")
            remaining = max(0, int(maximum) - int(used)) if maximum != "max" else None
            scopes.append(
                {
                    "path": str(scope),
                    "memory_max": maximum,
                    "memory_current": int(used),
                    "remaining_bytes": remaining,
                }
            )
            if remaining is not None:
                available = min(available, remaining)
        return HeadroomCheck(
            status="PASS" if available >= required else "BLOCKED",
            target_bytes=memory_target_bytes,
            required_bytes=required,
            available_bytes=available,
            host_available_bytes=host,
            scopes=tuple(scopes),
            reason=None if available >= required else "INSUFFICIENT_HEADROOM",
        )
    except (OSError, ValueError, IndexError, StopIteration) as exc:
        return HeadroomCheck(
            status="BLOCKED",
            target_bytes=memory_target_bytes,
            required_bytes=required,
            host_available_bytes=host,
            scopes=tuple(scopes),
            reason="HEADROOM_UNKNOWN:" + type(exc).__name__,
        )


def _write_json(
    path: Path, value: DomainModel | dict[str, JsonValue], *, exclusive: bool = False
) -> None:
    import json
    import tempfile

    content = (
        _json_bytes(value)
        if isinstance(value, DomainModel)
        else (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    )
    if exclusive:
        with path.open("xb") as out:
            out.write(content)
        return
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".campaign-", delete=False) as out:
            temporary = Path(out.name)
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def _campaign_owner(
    owner_root: Path, campaign_root: Path, campaign_id: str
) -> Iterator[dict[str, JsonValue]]:
    import fcntl

    owner_root.mkdir(parents=True, exist_ok=True)
    marker = owner_root / "active.json"
    with (owner_root / "campaign.lock").open("a+b") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("CAMPAIGN_ALREADY_ACTIVE") from exc
        try:
            if marker.exists():
                previous = _json_object(marker.read_text())
                if (
                    set(previous)
                    != {"schema_version", "state", "campaign_root", "campaign_id", "pid"}
                    or previous["schema_version"] != "1.0"
                    or previous["state"] != "IDLE"
                ):
                    raise ValueError("STALE_ACTIVE_MARKER_NEEDS_REVIEW")
            lease: dict[str, JsonValue] = {
                "schema_version": "1.0",
                "state": "RUNNING",
                "campaign_root": str(campaign_root.absolute()),
                "campaign_id": campaign_id,
                "pid": os.getpid(),
            }
            _write_json(marker, lease)
            try:
                yield lease
            except BaseException:
                lease["state"] = "NEEDS_REVIEW"
                raise
            else:
                if lease["state"] == "RUNNING":
                    lease["state"] = "IDLE"
            finally:
                _write_json(marker, lease)
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def check_case(run_dir: Path, dataset_manifest: Path) -> CaseVerdict:
    """Judge one outcome against frozen truth/targets, without aggregating samples."""
    from tkb_core.contracts.output import ScheduleResult

    run = RunRecord.model_validate(_json_object((run_dir / "run.json").read_text()))
    meta = _json_object(dataset_manifest.read_text())
    if set(meta) != _META_KEYS or meta["benchmark_schema_version"] != "1.0":
        raise ValueError("Unknown dataset manifest")
    verdict = CaseVerdict(
        run_sha256=_sha(run_dir / "run.json"), dataset_manifest_sha256=_sha(dataset_manifest)
    )
    unsat = meta["profile"] == "UNSAT_CAPACITY"
    if run.execution.pid is None and run.execution.measurement_status == "NOT_STARTED":
        if run.identity.get("expected_input_sha256") != meta["files"]["input.json"]:
            raise ValueError("Expected input identity mismatch")
        verdict.reasons = ("EXECUTION_NOT_STARTED",)
        if unsat:
            verdict.performance = "NOT_APPLICABLE"
            verdict.quality = "NOT_APPLICABLE"
        return verdict
    if (
        run.identity.get("input_sha256") != meta["files"]["input.json"]
        or run.identity.get("input_fingerprint") != meta["input_fingerprint"]
    ):
        raise ValueError("Outcome/input identity mismatch")
    if unsat and run.harness_status != "COMPLETE":
        verdict.performance = "NOT_APPLICABLE"
        verdict.quality = "NOT_APPLICABLE"
        verdict.reasons = ("UNSAT_EXECUTION_INCOMPLETE:" + run.harness_status,)
        return verdict
    good_measurement = (
        run.execution.measurement_status == "OK"
        and run.execution.peak_resident_bytes is not None
        and run.execution.launch_to_exit_seconds is not None
    )
    status = run.output.solver_status
    if meta["profile"] == "UNSAT_CAPACITY":
        raw = ScheduleResult.model_validate(_json_object((run_dir / "result.json").read_text()))
        expected = (
            run.harness_status == "COMPLETE"
            and status == "INFEASIBLE"
            and raw.status == "INFEASIBLE"
            and not raw.valid_schedule
            and not raw.assignments
            and raw.quality is not None
            and raw.quality.score is None
            and getattr(raw.metadata, "solver_executed", None) is False
        )
        return CaseVerdict(
            correctness="PASS" if expected else "FAIL",
            performance="NOT_APPLICABLE",
            quality="NOT_APPLICABLE",
            reasons=() if expected else ("CAPACITY_EXPECTATION_FAILED",),
            run_sha256=verdict.run_sha256,
            dataset_manifest_sha256=verdict.dataset_manifest_sha256,
        )
    if run.harness_status == "COMPLETE" and status in (
        "INFEASIBLE",
        "INPUT_INVALID",
        "UNSUPPORTED_FEATURE",
        "MODEL_INVALID",
    ):
        return verdict.model_copy(
            update={"correctness": "FAIL", "reasons": ("UNEXPECTED_CORE_ERROR",)}
        )
    if not run.valid_schedule:
        if good_measurement and (
            run.harness_status in ("WATCHDOG_TIMEOUT", "RESOURCE_STOP")
            or (run.harness_status == "COMPLETE" and status == "UNKNOWN")
        ):
            verdict.performance = "NOT_MET"
        verdict.reasons = (run.harness_status + ":" + str(status),)
        return verdict
    if run.output.score is None or run.output.score.tiers is None:
        return verdict.model_copy(update={"correctness": "FAIL", "reasons": ("MISSING_SCORE",)})
    score = run.output.score
    baseline = ScoreReport.model_validate(meta["baseline_score"])
    if (
        score.input_fingerprint != meta["input_fingerprint"]
        or baseline.input_fingerprint != score.input_fingerprint
    ):
        raise ValueError("Score/input mismatch")
    assert baseline.tiers is not None
    vector = score.tiers
    assert vector is not None
    verdict.correctness = "PASS"
    verdict.quality = (
        "BETTER" if vector < baseline.tiers else ("EQUAL" if vector == baseline.tiers else "WORSE")
    )
    raw = ScheduleResult.model_validate(_json_object((run_dir / "result.json").read_text()))
    if (
        raw.input_fingerprint != score.input_fingerprint
        or raw.status != status
        or raw.quality is None
        or raw.quality.score != score
    ):
        raise ValueError("Raw result and verified outcome differ")
    reasons = []
    for priority in raw.quality.optimal_prefix:
        i = priority - 1
        if vector[:i] == baseline.tiers[:i] and vector[i] > baseline.tiers[i]:
            reasons.append("PROVED_PREFIX_WORSE_THAN_WITNESS")
    if raw.quality.status == "LEXICOGRAPHIC_OPTIMAL" and vector > baseline.tiers:
        reasons.append("OPTIMUM_WORSE_THAN_WITNESS")
    if meta["profile"] == "TIGHT" and vector[0] == 0 and vector[1] < meta["p2_lower_bound"]:
        reasons.append("BELOW_DECLARED_LOWER_BOUND")
    if reasons:
        verdict.correctness = "FAIL"
        verdict.reasons = tuple(reasons)
        return verdict
    if not good_measurement:
        verdict.reasons = ("MISSING_MEASUREMENT",)
        return verdict
    budget = _BUDGETS[meta["class_count"]]
    assert run.execution.peak_resident_bytes is not None
    assert run.execution.launch_to_exit_seconds is not None
    met = (
        run.execution.peak_resident_bytes <= budget[2]
        and run.execution.launch_to_exit_seconds <= budget[1]
    )
    if meta["profile"] in ("BASE", "MIXED") and vector != (0, 0, 0):
        met = False
    verdict.performance = "MET" if met else "NOT_MET"
    verdict.reasons = () if met else ("TIME_RAM_OR_ZERO_TARGET_NOT_MET",)
    return verdict


def _machine_identity() -> dict[str, JsonValue]:
    import platform

    return {
        "platform": sys.platform,
        "release": platform.release(),
        "machine": platform.machine(),
        "hostname": platform.node(),
        "cpu_count": os.cpu_count(),
        "os_release_sha256": _sha(Path("/etc/os-release")),
        "mem_total": next(
            line
            for line in Path("/proc/meminfo").read_text().splitlines()
            if line.startswith("MemTotal:")
        ),
        "cpu_models": cast(
            list[JsonValue],
            sorted(
                {
                    line.split(":", 1)[1].strip()
                    for line in Path("/proc/cpuinfo").read_text().splitlines()
                    if line.startswith("model name")
                }
            ),
        ),
        "machine_id_sha256": _sha(Path("/etc/machine-id")),
        "python": sys.executable,
        "python_version": platform.python_version(),
        "prefix": sys.prefix,
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


def _verify_frozen_bundle(bundle: Path, output: Path) -> None:
    """Bounded installed worker validates all witnesses/proofs, without search in parent."""
    script = (
        "import importlib.util,sys;from pathlib import Path;"
        's=importlib.util.spec_from_file_location("frozen_generator",sys.argv[1]);'
        "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;"
        's.loader.exec_module(m);m.verify_bundle(Path(sys.argv[2]));print("BUNDLE_VERIFIED")'
    )
    execution = supervise_linux(
        (
            sys.executable,
            "-I",
            "-c",
            script,
            str(ROOT / "benchmarks/generate_synthetic.py"),
            str(bundle),
        ),
        output,
        RunLimits(watchdog_seconds=150.0, max_resident_bytes=1024**3),
    )
    _write_json(output / "execution.json", execution, exclusive=True)
    if (
        execution.measurement_status != "OK"
        or execution.exit_code != 0
        or execution.stop_reason is not None
        or execution.peak_resident_bytes is None
        or execution.peak_resident_bytes > 1024**3
        or execution.stdout_path.read_text().strip() != "BUNDLE_VERIFIED"
    ):
        raise ValueError("BUNDLE_VERIFICATION_BLOCKED")


def _prepare_campaign(
    bundle: Path, preflight: Path, output: Path, campaign_id: str, machine_id: str
) -> CampaignPlan:
    """Seal a new campaign only; never warm up or start a scheduling run."""
    import subprocess

    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.contracts.output import ScheduleResult

    plan = build_campaign_plan(bundle, campaign_id, machine_id)
    runtime = _runtime_identity(
        python=Path(sys.executable), preflight_dir=preflight, lock_path=ROOT / "uv.lock"
    )
    machine = _machine_identity()
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    with _campaign_owner(_OWNER_ROOT, output, campaign_id):
        output.mkdir(parents=True)
        headroom = check_headroom(1024**3)
        _write_json(output / "prepare-headroom.json", headroom, exclusive=True)
        if headroom.status != "PASS":
            raise ValueError("PREPARE_HEADROOM_BLOCKED")
        _verify_frozen_bundle(plan.bundle_dir, output / "bundle-verification")
        tiny = preflight / "smoke/input.json"
        manifest = _json_object((preflight / "preflight-manifest.json").read_text())
        for name in ("smoke/input.json", "smoke/result.json"):
            if _sha(preflight / name) != manifest["files"][name]:
                raise ValueError("WARMUP_SOURCE_DRIFT")
        problem = ScheduleInput.model_validate(_json_object(tiny.read_text()))
        expected = ScheduleResult.model_validate(
            _json_object((preflight / "smoke/result.json").read_text())
        )
        if not expected.valid_schedule or expected.input_fingerprint != problem.fingerprint():
            raise ValueError("WARMUP_FIXTURE_INVALID")
        digest = _sha(tiny)
        warm = PlannedCase(
            run_id=f"warmup-tiny-{digest}-w1-s42-r0",
            dataset_id="tiny",
            phase="warmup",
            repeat=0,
            class_count=None,
            profile="WARMUP",
            generator_seed=0,
            input_path=tiny.absolute(),
            dataset_manifest=None,
            manifest_sha256=None,
            input_sha256=digest,
            input_fingerprint=problem.fingerprint(),
            ground_truth="FEASIBLE",
            options=SolveOptions(time_limit_seconds=10.0),
            limits=RunLimits(watchdog_seconds=15.0, max_resident_bytes=256 * 1024**2),
        )

        def git(*args: str) -> str:
            return subprocess.check_output(("git", "-C", str(ROOT), *args), text=True).strip()

        environment: dict[str, JsonValue] = {
            "machine": machine,
            "git_head": git("rev-parse", "HEAD"),
            "git_status": git("status", "--porcelain"),
            "windows_status": "BLOCKED",
            "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
            "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
            "mkl_num_threads": os.environ.get("MKL_NUM_THREADS"),
        }
        sealed = CampaignPlan.model_validate(
            plan.model_dump()
            | dict(
                sealed=True,
                warmup=warm,
                preflight_dir=preflight.absolute(),
                preflight_sha256=_sha(preflight / "preflight-manifest.json"),
                runtime_identity=runtime,
                environment=environment,
            )
        )
        _write_json(output / "plan.json", sealed, exclusive=True)
        _write_json(output / "environment.json", environment, exclusive=True)
        _write_json(
            output / "seal.json",
            {
                "schema_version": "1.0",
                "plan_sha256": _sha(output / "plan.json"),
                "environment_sha256": _sha(output / "environment.json"),
            },
            exclusive=True,
        )
        return sealed


def _check_campaign_identity(plan: CampaignPlan, path: Path, preflight: Path) -> str:
    seal = _json_object((path.parent / "seal.json").read_text())
    digest = _sha(path)
    if (
        set(seal) != {"schema_version", "plan_sha256", "environment_sha256"}
        or seal["schema_version"] != "1.0"
        or seal["plan_sha256"] != digest
        or seal["environment_sha256"] != _sha(path.parent / "environment.json")
        or _json_object((path.parent / "environment.json").read_text()) != plan.environment
    ):
        raise ValueError("SEALED_IDENTITY_DRIFT")
    if not plan.sealed or plan.preflight_dir != preflight.absolute():
        raise ValueError("UNSEALED_PLAN")
    current = build_campaign_plan(plan.bundle_dir, plan.campaign_id, plan.machine_id)
    for key in ("bundle_sha256", "source_ids", "dataset_sources", "primary", "pilot"):
        if getattr(current, key) != getattr(plan, key):
            raise ValueError("SOURCE_OR_DATASET_DRIFT")
    if _sha(preflight / "preflight-manifest.json") != plan.preflight_sha256:
        raise ValueError("PREFLIGHT_DRIFT")
    runtime = _runtime_identity(
        python=Path(sys.executable), preflight_dir=preflight, lock_path=ROOT / "uv.lock"
    )
    if runtime != plan.runtime_identity:
        raise ValueError("RUNTIME_DRIFT")
    if _machine_identity() != plan.environment.get("machine", plan.environment):
        raise ValueError("MACHINE_DRIFT")
    assert plan.warmup is not None
    if _sha(plan.warmup.input_path) != plan.warmup.input_sha256:
        raise ValueError("WARMUP_DRIFT")
    return digest


def _operational_context() -> dict[str, JsonValue]:
    from datetime import UTC, datetime

    try:
        load: JsonValue = list(os.getloadavg())
    except OSError:
        load = None
    power: dict[str, JsonValue] = {}
    try:
        for device in Path("/sys/class/power_supply").iterdir():
            power[device.name] = {
                name: (device / name).read_text().strip()
                for name in ("type", "online", "status", "capacity")
                if (device / name).is_file()
            }
    except OSError:
        power = {"status": "UNKNOWN"}
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "load_average": load,
        "load_status": "OBSERVED" if load is not None else "UNKNOWN",
        "power": power or {"status": "UNKNOWN"},
        "workload_control": "UNCONTROLLED",
        "competing_workload": "UNKNOWN",
    }


def _journal(path: Path, event: dict[str, JsonValue]) -> None:
    import json
    from datetime import UTC, datetime

    event = event | {"timestamp_utc": datetime.now(UTC).isoformat()}
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
        out.flush()
        os.fsync(out.fileno())


def _events(root: Path, digest: str) -> list[dict[str, Any]]:
    path = root / "journal.jsonl"
    if not path.exists():
        return []
    result = []
    for line in path.read_text().splitlines():
        event = _json_object(line)
        if (
            set(event)
            != {
                "schema_version",
                "plan_sha256",
                "phase",
                "event",
                "run_id",
                "detail",
                "timestamp_utc",
            }
            or event["schema_version"] != "1.0"
            or event["plan_sha256"] != digest
            or event["phase"] not in ("warmup", "pilot", "primary")
            or event["event"] not in ("GATE_BLOCKED", "START", "TERMINAL")
        ):
            raise ValueError("JOURNAL_INVALID")
        result.append(event)
    return result


def _receipt(root: Path, case: PlannedCase, digest: str) -> tuple[RunRecord, CaseVerdict]:
    base = root / case.phase / case.run_id
    receipt = _json_object((base / "terminal.json").read_text())
    if (
        set(receipt) != {"schema_version", "plan_sha256", "run_id", "files"}
        or receipt["schema_version"] != "1.0"
        or receipt["plan_sha256"] != digest
        or receipt["run_id"] != case.run_id
    ):
        raise ValueError("TERMINAL_INVALID")
    files = receipt["files"]
    required = {"run.json", "case-verdict.json"}
    if (
        not isinstance(files, dict)
        or not required <= set(files)
        or set(files) - required - {"result.json", "stdout.json", "stderr.txt"}
    ):
        raise ValueError("TERMINAL_MEMBERSHIP")
    for name, sha in files.items():
        if _sha(base / name) != sha:
            raise ValueError("TERMINAL_EVIDENCE_DRIFT")
    record = RunRecord.model_validate(_json_object((base / "run.json").read_text()))
    verdict = CaseVerdict.model_validate(_json_object((base / "case-verdict.json").read_text()))
    not_started = (
        record.execution.pid is None
        and record.execution.measurement_status == "NOT_STARTED"
        and record.identity.get("expected_input_sha256") == case.input_sha256
    )
    actual_matches = (
        record.identity.get("input_sha256") == case.input_sha256
        and record.identity.get("input_fingerprint") == case.input_fingerprint
    )
    if verdict.run_sha256 != files["run.json"] or not (not_started or actual_matches):
        raise ValueError("TERMINAL_INPUT_IDENTITY")
    return record, verdict


def _qualified(record: RunRecord, verdict: CaseVerdict, case: PlannedCase) -> bool:
    performance = (
        verdict.performance == "NOT_APPLICABLE"
        if case.profile == "UNSAT_CAPACITY"
        else record.valid_schedule
        if case.phase == "warmup"
        else verdict.performance == "MET"
    )
    return record.harness_status == "COMPLETE" and verdict.correctness == "PASS" and performance


def _stop_status(record: RunRecord, verdict: CaseVerdict, case: PlannedCase) -> str | None:
    if record.execution.pid is not None and record.execution.raw_wait_status is None:
        return "NEEDS_REVIEW"
    if record.execution.measurement_reason == "REAP_UNCONFIRMED":
        return "NEEDS_REVIEW"
    if record.harness_status == "CANCELLED":
        return "CANCELLED"
    if record.execution.measurement_status != "OK":
        return "STOPPED"
    if record.harness_status in (
        "CRASH",
        "OUTPUT_INVALID",
        "MEASUREMENT_BLOCKED",
        "ENVIRONMENT_BLOCKED",
    ):
        return "STOPPED"
    if verdict.correctness == "FAIL":
        return "STOPPED"
    if case.phase != "primary" and not _qualified(record, verdict, case):
        return "STOPPED"
    return None


def _phase_cases(plan: CampaignPlan, phase: Phase) -> tuple[PlannedCase, ...]:
    if phase == "primary":
        return plan.primary
    if phase == "pilot":
        return (plan.pilot,)
    assert plan.warmup is not None
    return (plan.warmup,)


def _read_terminals(
    root: Path, plan: CampaignPlan, digest: str, events: list[dict[str, Any]]
) -> dict[str, tuple[RunRecord, CaseVerdict]]:
    cases = {c.run_id: c for p in ("warmup", "pilot", "primary") for c in _phase_cases(plan, p)}
    started: set[str] = set()
    indices: dict[str, int] = {"warmup": 0, "pilot": 0, "primary": 0}
    terminal: dict[str, tuple[RunRecord, CaseVerdict]] = {}
    for event in events:
        ident = event["run_id"]
        if ident not in cases or cases[ident].phase != event["phase"]:
            raise ValueError("UNKNOWN_RUN")
        if event["event"] == "GATE_BLOCKED":
            if ident in started:
                raise ValueError("GATE_AFTER_START")
        elif event["event"] == "START":
            if ident in started:
                raise ValueError("DUPLICATE_START")
            ordered = _phase_cases(plan, cast(Phase, event["phase"]))
            index = indices[event["phase"]]
            if index >= len(ordered) or ordered[index].run_id != ident:
                raise ValueError("JOURNAL_ORDER_DRIFT")
            indices[event["phase"]] += 1
            started.add(ident)
        else:
            if ident not in started or ident in terminal:
                raise ValueError("TERMINAL_WITHOUT_START")
            if event["detail"] != {
                "terminal_sha256": _sha(root / cases[ident].phase / ident / "terminal.json")
            }:
                raise ValueError("TERMINAL_RECEIPT_DRIFT")
            terminal[ident] = _receipt(root, cases[ident], digest)
    if started - set(terminal):
        raise ValueError("UNFINISHED_START")
    for c in cases.values():
        if (root / c.phase / c.run_id).exists() and c.run_id not in terminal:
            raise ValueError("PARTIAL_RUN_DIRECTORY")
    return terminal


def execute_campaign(
    plan_path: Path, preflight_dir: Path, *, phase: str, resume: bool = False
) -> CampaignState:
    """Run one explicitly selected phase, retaining every terminal outcome on resume."""
    if phase not in ("warmup", "pilot", "primary"):
        raise ValueError("Explicit execution phase required")
    selected = cast(Phase, phase)
    plan = CampaignPlan.model_validate(_json_object(plan_path.read_text()))
    cases = _phase_cases(plan, selected)
    root = plan_path.absolute().parent
    state = CampaignState(
        plan_sha256=_sha(plan_path),
        phase=selected,
        status="BLOCKED",
        rows={c.run_id: "NOT_STARTED" for c in cases},
        pending=len(cases),
    )
    try:
        digest = _check_campaign_identity(plan, plan_path, preflight_dir)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        state.reason = "IDENTITY_BLOCKED:" + str(exc)
        return state
    with _campaign_owner(_OWNER_ROOT, root, plan.campaign_id) as lease:

        def finish(status: Any, reason: str | None = None) -> CampaignState:
            state.status = status
            state.reason = reason
            state.attempted = sum(v in ("TERMINAL", "PARTIAL") for v in state.rows.values())
            state.completed = sum(v == "TERMINAL" for v in state.rows.values())
            state.pending = len(cases) - state.completed
            if status == "NEEDS_REVIEW":
                lease["state"] = "NEEDS_REVIEW"
            _write_json(root / "campaign-state.json", state)
            return state

        try:
            events = _events(root, digest)
            terminal = _read_terminals(root, plan, digest, events)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            for c in cases:
                if (root / selected / c.run_id).exists():
                    state.rows[c.run_id] = "PARTIAL"
            return finish("NEEDS_REVIEW", str(exc))
        for c in cases:
            if c.run_id in terminal:
                state.rows[c.run_id] = "TERMINAL"
                record, verdict = terminal[c.run_id]
                state.failed += int(not _qualified(record, verdict, c))
        if any(e["phase"] == selected for e in events) and not resume:
            return finish("BLOCKED", "EXPLICIT_RESUME_REQUIRED")
        prerequisites = (
            ()
            if selected == "warmup"
            else ("warmup",)
            if selected == "pilot"
            else ("warmup", "pilot")
        )
        for required in prerequisites:
            c = _phase_cases(plan, cast(Phase, required))[0]
            if c.run_id not in terminal or not _qualified(*terminal[c.run_id], c):
                return finish("BLOCKED", "PREREQUISITE_NOT_PASSED:" + required)

        def event(kind: str, c: PlannedCase, detail: JsonValue = None) -> None:
            _journal(
                root / "journal.jsonl",
                {
                    "schema_version": "1.0",
                    "plan_sha256": digest,
                    "phase": selected,
                    "event": kind,
                    "run_id": c.run_id,
                    "detail": detail,
                },
            )

        for c in cases:
            if c.run_id in terminal:
                stop = _stop_status(*terminal[c.run_id], c)
                if stop:
                    return finish(stop, "TERMINAL_STOP_RETAINED")
                continue
            try:
                _check_campaign_identity(plan, plan_path, preflight_dir)
                headroom = check_headroom(c.limits.max_resident_bytes)
                import shutil

                disk = shutil.disk_usage(root)
                if headroom.status != "PASS" or disk.free < 256 * 1024**2:
                    state.rows[c.run_id] = "NOT_STARTED_GATE_BLOCKED"
                    event(
                        "GATE_BLOCKED",
                        c,
                        {
                            "headroom": headroom.model_dump(mode="json"),
                            "disk_free_bytes": disk.free,
                        },
                    )
                    return finish("BLOCKED", "ADMISSION_GATE_BLOCKED")
            except (OSError, ValueError, TypeError, KeyError) as exc:
                event("GATE_BLOCKED", c, {"reason": str(exc)})
                state.rows[c.run_id] = "NOT_STARTED_GATE_BLOCKED"
                return finish("BLOCKED", "ADMISSION_IDENTITY_BLOCKED")
            event(
                "START",
                c,
                {
                    "headroom": headroom.model_dump(mode="json"),
                    "disk_free_bytes": disk.free,
                    "operational_context": _operational_context(),
                },
            )
            state.rows[c.run_id] = "PARTIAL"
            base = root / selected / c.run_id
            record = run_cli_once(
                python=Path(sys.executable),
                input_path=c.input_path,
                run_dir=base,
                preflight_dir=preflight_dir,
                lock_path=ROOT / "uv.lock",
                input_sha256=c.input_sha256,
                options=c.options,
                limits=c.limits,
            )
            if c.phase == "warmup":
                verdict = CaseVerdict(
                    correctness="PASS" if record.valid_schedule else "NOT_ASSESSED",
                    performance="NOT_APPLICABLE",
                    quality="NOT_APPLICABLE",
                    run_sha256=_sha(base / "run.json"),
                )
            else:
                assert c.dataset_manifest is not None
                try:
                    verdict = check_case(base, c.dataset_manifest)
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    verdict = CaseVerdict(
                        correctness="FAIL",
                        reasons=("VERDICT_INVALID:" + type(exc).__name__,),
                        run_sha256=_sha(base / "run.json"),
                    )
            _write_json(base / "case-verdict.json", verdict, exclusive=True)
            names = ("run.json", "case-verdict.json", "stdout.json", "stderr.txt", "result.json")
            files: dict[str, JsonValue] = {
                name: _sha(base / name) for name in names if (base / name).is_file()
            }
            _write_json(
                base / "terminal.json",
                {
                    "schema_version": "1.0",
                    "plan_sha256": digest,
                    "run_id": c.run_id,
                    "files": files,
                },
                exclusive=True,
            )
            event("TERMINAL", c, {"terminal_sha256": _sha(base / "terminal.json")})
            state.rows[c.run_id] = "TERMINAL"
            state.failed += int(not _qualified(record, verdict, c))
            stop = _stop_status(record, verdict, c)
            if stop:
                return finish(stop, "RUN_STOP_POLICY")
            finish("BLOCKED", "IN_PROGRESS")
        return finish("COMPLETE")


def main(argv: list[str] | None = None) -> int:
    """Explicit phase CLI; prepare never silently starts any solve."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("prepare", "warmup", "pilot", "primary"))
    for flag in ("bundle", "preflight-dir", "output", "plan"):
        parser.add_argument("--" + flag, type=Path)
    parser.add_argument("--campaign-id")
    parser.add_argument("--machine-id")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if args.preflight_dir is None:
        parser.error("--preflight-dir required")
    if args.phase == "prepare":
        if (
            args.resume
            or args.plan is not None
            or not all((args.bundle, args.output, args.campaign_id, args.machine_id))
        ):
            parser.error("prepare requires bundle/output/campaign-id/machine-id, no plan/resume")
    elif args.plan is None or any((args.bundle, args.output, args.campaign_id, args.machine_id)):
        parser.error("execution requires plan only, no prepare arguments")
    try:
        if args.phase == "prepare":
            _prepare_campaign(
                args.bundle, args.preflight_dir, args.output, args.campaign_id, args.machine_id
            )
            print(
                json.dumps(
                    {"status": "PREPARED", "windows_status": "BLOCKED", "primary_planned": 108}
                )
            )
            return 0
        assert args.plan is not None
        state = execute_campaign(
            args.plan, args.preflight_dir, phase=args.phase, resume=args.resume
        )
        print(state.model_dump_json())
        return 0 if state.status == "COMPLETE" else 2
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(
            json.dumps({"status": "BLOCKED", "error_type": type(exc).__name__, "reason": str(exc)})
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
