"""Phase 2 Linux performance controller v2 (policy 0.4), outside Scheduling Core.

Child supervision, native accounting, headroom, journaling helpers and the owner lock are
imported unchanged from the frozen v1 controller; only output verification, H/Q/P/zero
verdicts, plan membership and stop gates are new. Run as ``python -m benchmarks.run_phase2``.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

from pydantic import Field, JsonValue, StrictBool, StrictStr, model_validator

from benchmarks import generate_phase2 as g2
from benchmarks import run_benchmarks as v1
from benchmarks.run_benchmarks import (
    OutputVerification,
    RunLimits,
    RunRecord,
)
from tkb_core.contracts.score import ScoreReport
from tkb_core.domain.models import DomainModel, NonNegativeInt
from tkb_core.solver.options import SolveOptions

PROTOCOL = "phase2-linux-v2"
ROOT = Path(__file__).resolve().parents[1]
SHA = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
CampaignId = v1.CampaignId
Phase = Literal["warmup", "pilot", "primary"]
# Acceptance v2 §4: unchanged solver budget, watchdog and peak-RSS target per size.
BUDGETS: dict[int, tuple[float, float, int]] = {
    10: (60.0, 150.0, 1024**3),
    20: (120.0, 210.0, 2 * 1024**3),
    40: (180.0, 270.0, 4 * 1024**3),
}
WARMUP_BUDGET = (10.0, 15.0, 256 * 1024**2)
# Input policy -> (ScheduleResult version, ScoreReport version) the installed Core must emit.
VERSION_TABLE = {
    "0.1": ("1.2", "1.0"),
    "0.2": ("1.3", "1.0"),
    "0.3": ("1.4", "1.1"),
    "0.4": ("1.5", "1.2"),
}
PRIMARY_COUNT = 216
VARIANTS = ("SOFT", "HARD")
PILOT_IDS = tuple(g2.dataset_id(10, "BASE", 101, v) for v in VARIANTS)


def check_version_table() -> None:
    """Fail fast when the imported Core pairs versions differently from this protocol."""
    from tkb_core.contracts.output import QUALITY_POLICY, SCORE_VERSION

    installed = {policy: (out, SCORE_VERSION[out]) for out, policy in QUALITY_POLICY.items()}
    if installed != VERSION_TABLE:
        raise ValueError("VERSION_TABLE_DRIFT")


def expected_versions(problem: Any) -> tuple[str, str]:
    from tkb_core.domain.models import ConstraintConfigV11

    config = problem.constraint_config
    if problem.schema_version != "1.1" or not isinstance(config, ConstraintConfigV11):
        raise ValueError("INPUT_VERSION_UNSUPPORTED")
    return VERSION_TABLE[config.policy_version]


def verify_output_v2(
    input_path: Path, result_path: Path, execution: v1.ExecutionRecord
) -> OutputVerification:
    """Public CLI checks with the output/score version pair derived from the input."""
    import contextlib
    import io

    from tkb_core.cli import main
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.contracts.output import ScheduleResult, SolverRunMetadata

    try:
        problem = ScheduleInput.model_validate(
            v1._json_object(input_path.read_text(encoding="utf-8"))
        )
        output_version, score_version = expected_versions(problem)
        raw = v1._json_object(execution.stdout_path.read_text(encoding="utf-8"))
        if result_path.exists() and v1._json_object(result_path.read_text(encoding="utf-8")) != raw:
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
        if result.schema_version != output_version or execution.exit_code != pairs.get(
            result.status
        ):
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
            parsed = v1._json_object(output.getvalue())
            if code != 0 or parsed.get("status") != expected:
                raise ValueError("Independent verification failed")
            checked.append(parsed)
        if checked[0].get("schema_version") != output_version:
            raise ValueError("Validation version mismatch")
        score = ScoreReport.model_validate(checked[1])
        if score.schema_version != score_version:
            raise ValueError("Score version mismatch")
        return OutputVerification(
            status="VALID_SCHEDULE", valid_schedule=True, solver_status=result.status, score=score
        )
    except (OSError, ValueError, TypeError, AttributeError, KeyError, RecursionError) as exc:
        return OutputVerification(status="INVALID", diagnostics=(type(exc).__name__,))


class CaseVerdict(DomainModel):
    """Acceptance v2 axes, judged independently; zero is never a P gate."""

    schema_version: Literal["2.0"] = "2.0"
    hard: Literal["PASS", "FAIL", "NOT_APPLICABLE", "NOT_ASSESSED"] = "NOT_ASSESSED"
    quality: Literal["REVIEW_REQUIRED", "NO_SCHEDULE", "NOT_APPLICABLE"] = "NO_SCHEDULE"
    witness_comparison: Literal["BETTER", "EQUAL", "WORSE"] | None = None
    performance: Literal["MET", "NOT_MET", "INCOMPLETE", "NOT_APPLICABLE"] = "INCOMPLETE"
    zero: Literal["MET", "NOT_MET", "NOT_APPLICABLE"] = "NOT_APPLICABLE"
    reasons: tuple[StrictStr, ...] = ()
    run_sha256: SHA
    dataset_manifest_sha256: SHA | None = None


def _within_limits(run: RunRecord, size: int) -> bool:
    assert run.execution.peak_resident_bytes is not None
    assert run.execution.launch_to_exit_seconds is not None
    _, watchdog, rss = BUDGETS[size]
    return (
        run.execution.peak_resident_bytes <= rss
        and run.execution.launch_to_exit_seconds <= watchdog
    )


def judge_case(run_dir: Path, dataset_manifest: Path) -> CaseVerdict:
    """Judge one outcome against frozen truth and fixed limits, without aggregation."""
    from tkb_core.contracts.output import ScheduleResult

    run = RunRecord.model_validate(v1._json_object((run_dir / "run.json").read_text()))
    meta = g2.DatasetManifest.model_validate(v1._json_object(dataset_manifest.read_text()))
    verdict = CaseVerdict(
        run_sha256=v1._sha(run_dir / "run.json"),
        dataset_manifest_sha256=v1._sha(dataset_manifest),
    )
    unsat = meta.profile == "UNSAT_CAPACITY"
    zero_applies = meta.known_optimum is not None
    if unsat:
        verdict.quality = "NOT_APPLICABLE"
        verdict.performance = "NOT_APPLICABLE"
    if run.execution.pid is None and run.execution.measurement_status == "NOT_STARTED":
        if run.identity.get("expected_input_sha256") != meta.files["input.json"]:
            raise ValueError("Expected input identity mismatch")
        verdict.reasons = ("EXECUTION_NOT_STARTED",)
        return verdict
    if (
        run.identity.get("input_sha256") != meta.files["input.json"]
        or run.identity.get("input_fingerprint") != meta.input_fingerprint
    ):
        raise ValueError("Outcome/input identity mismatch")
    status = run.output.solver_status
    if run.harness_status == "OUTPUT_INVALID":
        # Review F1: an output that fails independent verification is a Core technical error
        # (acceptance v2 H4), unlike crashes or measurement/environment failures.
        verdict.hard = "FAIL"
        verdict.reasons = ("OUTPUT_INVALID:" + ",".join(run.output.diagnostics),)
        return verdict
    if unsat:
        if run.harness_status != "COMPLETE":
            verdict.reasons = ("UNSAT_EXECUTION_INCOMPLETE:" + run.harness_status,)
            return verdict
        raw = ScheduleResult.model_validate(v1._json_object((run_dir / "result.json").read_text()))
        expected = (
            status == "INFEASIBLE"
            and raw.status == "INFEASIBLE"
            and not raw.valid_schedule
            and not raw.assignments
            and raw.quality is not None
            and raw.quality.score is None
            and getattr(raw.metadata, "solver_executed", None) is False
        )
        verdict.hard = "PASS" if expected else "FAIL"
        verdict.reasons = () if expected else ("CAPACITY_EXPECTATION_FAILED",)
        return verdict
    good_measurement = (
        run.execution.measurement_status == "OK"
        and run.execution.peak_resident_bytes is not None
        and run.execution.launch_to_exit_seconds is not None
    )
    if zero_applies:
        verdict.zero = "NOT_MET"
    if run.harness_status == "COMPLETE" and status in (
        "INFEASIBLE",
        "INPUT_INVALID",
        "UNSUPPORTED_FEATURE",
        "MODEL_INVALID",
    ):
        verdict.hard = "FAIL"
        verdict.reasons = ("UNEXPECTED_CORE_ERROR:" + str(status),)
        return verdict
    if not run.valid_schedule:
        verdict.hard = "NOT_APPLICABLE"
        if good_measurement and (
            run.harness_status in ("WATCHDOG_TIMEOUT", "RESOURCE_STOP")
            or (run.harness_status == "COMPLETE" and status == "UNKNOWN")
        ):
            verdict.performance = "NOT_MET"
        verdict.reasons = (run.harness_status + ":" + str(status),)
        return verdict
    if run.output.score is None or run.output.score.tiers is None or meta.baseline_score is None:
        verdict.hard = "FAIL"
        verdict.reasons = ("MISSING_SCORE",)
        return verdict
    score = run.output.score
    baseline = meta.baseline_score
    if (
        score.input_fingerprint != meta.input_fingerprint
        or baseline.input_fingerprint != score.input_fingerprint
    ):
        raise ValueError("Score/input mismatch")
    assert baseline.tiers is not None and score.tiers is not None
    vector, witness = score.tiers, baseline.tiers
    raw = ScheduleResult.model_validate(v1._json_object((run_dir / "result.json").read_text()))
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
        if vector[:i] == witness[:i] and vector[i] > witness[i]:
            reasons.append("PROVED_PREFIX_WORSE_THAN_WITNESS")
    if raw.quality.status == "LEXICOGRAPHIC_OPTIMAL" and vector > witness:
        reasons.append("OPTIMUM_WORSE_THAN_WITNESS")
    if meta.p2_lower_bound is not None and vector[0] == 0 and vector[1] < meta.p2_lower_bound:
        reasons.append("BELOW_DECLARED_LOWER_BOUND")
    if reasons:
        verdict.hard = "FAIL"
        verdict.reasons = tuple(reasons)
        return verdict
    verdict.hard = "PASS"
    verdict.quality = "REVIEW_REQUIRED"
    verdict.witness_comparison = (
        "BETTER" if vector < witness else ("EQUAL" if vector == witness else "WORSE")
    )
    if zero_applies:
        verdict.zero = "MET" if vector == (0, 0, 0) else "NOT_MET"
    if not good_measurement:
        verdict.reasons = ("MISSING_MEASUREMENT",)
        return verdict
    met = _within_limits(run, meta.class_count)
    verdict.performance = "MET" if met else "NOT_MET"
    verdict.reasons = () if met else ("TIME_OR_RAM_NOT_MET",)
    return verdict


class PlannedCase(DomainModel):
    run_id: StrictStr
    dataset_id: StrictStr
    phase: Phase
    repeat: Annotated[NonNegativeInt, Field(le=3)]
    class_count: Literal[10, 20, 40] | None
    profile: Literal["BASE", "MIXED", "TIGHT", "UNSAT_CAPACITY", "WARMUP"]
    variant: Literal["SOFT", "HARD"] | None
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
            if (
                self.class_count is not None
                or self.variant is not None
                or self.profile != "WARMUP"
                or self.repeat != 0
            ):
                raise ValueError("Invalid warmup membership")
            budget = WARMUP_BUDGET
        else:
            if self.class_count is None or self.profile == "WARMUP" or self.variant is None:
                raise ValueError("Invalid dataset reference")
            budget = BUDGETS[self.class_count]
            expected = g2.dataset_id(
                self.class_count, self.profile, self.generator_seed, self.variant
            )
            if self.dataset_id != expected or self.generator_seed not in (101, 102, 103):
                raise ValueError("Unknown dataset")
            if self.dataset_manifest is None or self.manifest_sha256 is None:
                raise ValueError("Missing dataset manifest")
            if self.phase == "pilot" and (self.dataset_id not in PILOT_IDS or self.repeat != 0):
                raise ValueError("Pilot policy differs")
            if self.phase == "primary" and self.repeat not in (1, 2, 3):
                raise ValueError("Invalid repeat")
        if (
            self.options.time_limit_seconds,
            self.limits.watchdog_seconds,
            self.limits.max_resident_bytes,
        ) != budget:
            raise ValueError("Fixed budget changed")
        if self.options != SolveOptions(time_limit_seconds=budget[0]):
            raise ValueError("Fixed solver options changed")
        if self.ground_truth != ("INFEASIBLE" if self.profile == "UNSAT_CAPACITY" else "FEASIBLE"):
            raise ValueError("Ground truth/profile mismatch")
        if (
            self.run_id
            != f"{self.phase}-{self.dataset_id}-{self.input_sha256}-w1-s42-r{self.repeat}"
        ):
            raise ValueError("Run identity mismatch")
        return self


def primary_order(ids: set[str]) -> list[tuple[str, int]]:
    import random

    rng = random.Random(2026)
    order: list[tuple[str, int]] = []
    for repeat in (1, 2, 3):
        shuffled = sorted(ids)
        rng.shuffle(shuffled)
        order.extend((d, repeat) for d in shuffled)
    return order


class CampaignPlan(DomainModel):
    """Frozen v2 membership: warmup, two pilots, 216 primary rows."""

    schema_version: Literal["2.0"] = "2.0"
    policy: Literal["phase2-linux-v2"] = "phase2-linux-v2"
    campaign_id: CampaignId
    machine_id: CampaignId
    bundle_dir: Path
    bundle_sha256: SHA
    source_ids: dict[str, SHA]
    dataset_sources: dict[str, SHA]
    order_seed: Literal[2026] = 2026
    primary: tuple[PlannedCase, ...]
    pilots: tuple[PlannedCase, PlannedCase]
    warmup: PlannedCase | None = None
    sealed: StrictBool = False
    preflight_dir: Path | None = None
    preflight_sha256: SHA | None = None
    runtime_identity: dict[str, JsonValue] = Field(default_factory=dict)
    environment: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def membership(self) -> Self:
        expected = g2.expected_dataset_ids()
        if len({c.run_id for c in self.primary}) != len(self.primary) or len(self.primary) != (
            3 * len(expected)
        ):
            raise ValueError("Primary must contain every dataset three times")
        if any(c.phase != "primary" for c in self.primary):
            raise ValueError("Phase membership changed")
        if [(c.dataset_id, c.repeat) for c in self.primary] != primary_order(expected):
            raise ValueError("Frozen order differs from policy")
        if tuple(c.dataset_id for c in self.pilots) != PILOT_IDS or any(
            c.phase != "pilot" for c in self.pilots
        ):
            raise ValueError("Pilot membership changed")
        if {c.run_id for c in self.pilots} & {c.run_id for c in self.primary}:
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


class CampaignState(DomainModel):
    schema_version: Literal["2.0"] = "2.0"
    plan_sha256: SHA
    phase: Phase
    status: Literal["COMPLETE", "BLOCKED", "STOPPED", "NEEDS_REVIEW", "CANCELLED"]
    rows: dict[str, Literal["NOT_STARTED", "NOT_STARTED_GATE_BLOCKED", "TERMINAL", "PARTIAL"]]
    attempted: NonNegativeInt = 0
    completed: NonNegativeInt = 0
    failed: NonNegativeInt = 0
    pending: NonNegativeInt = 0
    reason: StrictStr | None = None


def source_ids() -> dict[str, str]:
    """Every tooling source a v2 outcome depends on, including imported v1 modules."""
    names = {
        "controller": "benchmarks/run_phase2.py",
        "generator": "benchmarks/generate_phase2.py",
        "aggregator": "benchmarks/aggregate_phase2.py",
        "controller_v1": "benchmarks/run_benchmarks.py",
        "generator_v1": "benchmarks/generate_synthetic.py",
        "preflight_v1": "benchmarks/phase2a_preflight.py",
        "native_trace": "benchmarks/native_trace.py",
        "windows_runtime": "benchmarks/windows_runtime.py",
        "lock": "uv.lock",
    }
    return {key: v1._sha(ROOT / path) for key, path in names.items()}


def build_campaign_plan(bundle_dir: Path, campaign_id: str, machine_id: str) -> CampaignPlan:
    """Read frozen v2 bundle metadata into deterministic rows; never solves."""
    root = bundle_dir.absolute()
    bundle = g2.BundleManifest.model_validate(
        v1._json_object((root / "manifest.json").read_text(encoding="utf-8"))
    )
    expected = g2.expected_dataset_ids()
    ids = [e.dataset_id for e in bundle.datasets]
    if len(ids) != len(expected) or set(ids) != expected:
        raise ValueError("Dataset membership drift")
    cases: dict[str, dict[str, Any]] = {}
    sources: dict[str, str] | None = None
    for entry in bundle.datasets:
        base = v1._safe_file(root, entry.dataset_id)
        path = base / "manifest.json"
        if v1._sha(path) != entry.manifest_sha256:
            raise ValueError("Dataset manifest checksum drift")
        data = g2.DatasetManifest.model_validate(v1._json_object(path.read_text(encoding="utf-8")))
        if data.dataset_id != entry.dataset_id:
            raise ValueError("Dataset envelope drift")
        if sources is None:
            sources = data.sources
        if sources != data.sources:
            raise ValueError("Dataset source identities differ")
        names = (
            {"input.json", "provenance-input.json", "provenance-witness.json"}
            if data.profile == "UNSAT_CAPACITY"
            else {"input.json", "witness.json"}
        )
        if set(data.files) != names:
            raise ValueError("Artifact membership drift")
        for name, digest in data.files.items():
            if v1._sha(v1._safe_file(base, name)) != digest:
                raise ValueError("Input/witness checksum drift")
        budget = BUDGETS[data.class_count]
        cases[data.dataset_id] = dict(
            dataset_id=data.dataset_id,
            class_count=data.class_count,
            profile=data.profile,
            variant=data.variant,
            generator_seed=data.seed,
            input_path=base / "input.json",
            dataset_manifest=path,
            manifest_sha256=entry.manifest_sha256,
            input_sha256=data.files["input.json"],
            input_fingerprint=data.input_fingerprint,
            ground_truth=data.ground_truth,
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

    return CampaignPlan(
        campaign_id=campaign_id,
        machine_id=machine_id,
        bundle_dir=root,
        bundle_sha256=v1._sha(root / "manifest.json"),
        source_ids=source_ids(),
        dataset_sources=sources or {},
        primary=tuple(row(i, "primary", r) for i, r in primary_order(expected)),
        pilots=(row(PILOT_IDS[0], "pilot", 0), row(PILOT_IDS[1], "pilot", 0)),
    )


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
    """Supervise one solve exactly like v1, with v2 output verification."""
    from tkb_core.contracts.input import ScheduleInput

    python, input_path, run_dir = python.absolute(), input_path.absolute(), run_dir.absolute()
    if run_dir.exists() or run_dir.is_symlink():
        raise FileExistsError(run_dir)
    identity: dict[str, JsonValue] = {"expected_input_sha256": input_sha256}
    argv: tuple[str, ...] = (
        str(python),
        "-I",
        str(ROOT / "benchmarks/native_trace.py"),
        "--trace",
        str(run_dir / "native-calls.jsonl"),
        "solve",
        str(input_path),
        "--output",
        str(run_dir / "result.json"),
    )
    try:
        limits = RunLimits.model_validate(limits.model_dump())
        options = SolveOptions.model_validate(options.model_dump())
        if v1._sha(input_path) != input_sha256:
            raise ValueError("INPUT_HASH_MISMATCH")
        identity.update(
            v1._runtime_identity(python=python, preflight_dir=preflight_dir, lock_path=lock_path)
        )
        identity["v2_tooling_source_sha256"] = v1._sha(Path(__file__))
        import hashlib

        captured = input_path.read_bytes()
        captured_sha = hashlib.sha256(captured).hexdigest()
        if captured_sha != input_sha256:
            raise ValueError("INPUT_CHANGED_BEFORE_SPAWN")
        problem = ScheduleInput.model_validate(v1._json_object(captured.decode("utf-8")))
        expected_versions(problem)
        identity.update(
            {
                "input_sha256": captured_sha,
                "input_fingerprint": problem.fingerprint(),
                "options": options.model_dump(mode="json"),
                "limits": limits.model_dump(mode="json"),
            }
        )
        # Review F4: v1's last check immediately before spawn.
        if v1._sha(input_path) != input_sha256:
            raise ValueError("INPUT_CHANGED_BEFORE_SPAWN")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        run_dir.mkdir()
        execution = v1.ExecutionRecord(
            argv=argv,
            run_dir=run_dir,
            stdout_path=run_dir / "stdout.json",
            stderr_path=run_dir / "stderr.txt",
            error_type=type(exc).__name__,
        )
        record = RunRecord(
            harness_status="ENVIRONMENT_BLOCKED",
            execution=execution,
            output=OutputVerification(diagnostics=(str(exc),)),
            identity=identity,
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
        execution = v1.supervise(argv, run_dir, limits)
        started = time.monotonic()
        try:
            if v1._sha(input_path) != input_sha256:
                raise ValueError("INPUT_CHANGED")
            output = verify_output_v2(input_path, run_dir / "result.json", execution)
            if v1._sha(input_path) != input_sha256:
                raise ValueError("INPUT_CHANGED")
        except (OSError, ValueError) as exc:
            output = OutputVerification(
                status="INVALID", diagnostics=("INPUT_CHANGED", type(exc).__name__)
            )
        status = v1.classify_run(execution, output)
        record = RunRecord(
            harness_status=status,
            execution=execution,
            output=output,
            identity=identity,
            valid_schedule=status == "COMPLETE" and output.valid_schedule,
            parent_verification_seconds=time.monotonic() - started,
        )
    with (run_dir / "run.json").open("x", encoding="utf-8") as handle:
        handle.write(record.model_dump_json(indent=2) + "\n")
    return record


def qualified(record: RunRecord, verdict: CaseVerdict, case: PlannedCase) -> bool:
    """D2: a pilot needs H PASS, a schedule and P MET; zero and Q never gate it."""
    if record.harness_status != "COMPLETE":
        return False
    if case.phase == "warmup":
        return record.valid_schedule
    if case.profile == "UNSAT_CAPACITY":
        return verdict.hard == "PASS"
    return verdict.hard == "PASS" and record.valid_schedule and verdict.performance == "MET"


def stop_status(record: RunRecord, verdict: CaseVerdict, case: PlannedCase) -> str | None:
    """Plan §6 gates: safety/correctness stop the campaign; P NOT_MET does not."""
    execution = record.execution
    if execution.pid is not None and (
        execution.exit_code is None
        or (execution.measurement_method == "linux_wait4" and execution.raw_wait_status is None)
    ):
        return "NEEDS_REVIEW"
    if execution.measurement_reason == "REAP_UNCONFIRMED":
        return "NEEDS_REVIEW"
    if record.harness_status == "CANCELLED":
        return "CANCELLED"
    if execution.measurement_status != "OK":
        return "STOPPED"
    if record.harness_status in (
        "CRASH",
        "OUTPUT_INVALID",
        "MEASUREMENT_BLOCKED",
        "ENVIRONMENT_BLOCKED",
    ):
        return "STOPPED"
    if verdict.hard == "FAIL":
        return "STOPPED"
    if case.phase != "primary" and not qualified(record, verdict, case):
        return "STOPPED"
    return None


def phase_cases(plan: CampaignPlan, phase: Phase) -> tuple[PlannedCase, ...]:
    if phase == "primary":
        return plan.primary
    if phase == "pilot":
        return plan.pilots
    assert plan.warmup is not None
    return (plan.warmup,)


BUNDLE_WATCHDOG_SECONDS = 1800.0
BUNDLE_MAX_RESIDENT_BYTES = 2 * 1024**3


def bundle_verification_argv(python: Path, bundle: Path) -> tuple[str, ...]:
    """Verify a bundle with the given (installed) interpreter under v1's search-import guard."""
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from benchmarks.windows_preflight import import_guard\n"
        "with import_guard(scoring=False):\n"
        "    from benchmarks.generate_phase2 import verify_bundle\n"
        "    verify_bundle(Path(sys.argv[2]))\n"
        'print("BUNDLE_VERIFIED")\n'
    )
    return (str(python), "-I", "-c", script, str(ROOT), str(bundle))


def bundle_verification_passed(execution: v1.ExecutionRecord) -> bool:
    """Exit 0, measured, within the tooling RSS bound, and an explicit success marker."""
    try:
        marker = execution.stdout_path.read_text().strip()
    except OSError:
        return False
    return (
        execution.measurement_status == "OK"
        and execution.exit_code == 0
        and execution.stop_reason is None
        and execution.peak_resident_bytes is not None
        and execution.peak_resident_bytes <= BUNDLE_MAX_RESIDENT_BYTES
        and marker == "BUNDLE_VERIFIED"
    )


def _verify_bundle_isolated(bundle: Path, output: Path) -> None:
    """Supervised child verifies every dataset by deterministic regeneration (no search)."""
    execution = v1.supervise(
        bundle_verification_argv(Path(sys.executable), bundle),
        output,
        # Regenerating 72 datasets is slower than v1's 36; this bounds tooling, not a solve.
        RunLimits(
            watchdog_seconds=BUNDLE_WATCHDOG_SECONDS, max_resident_bytes=BUNDLE_MAX_RESIDENT_BYTES
        ),
    )
    v1._write_json(output / "execution.json", execution, exclusive=True)
    if not bundle_verification_passed(execution):
        raise ValueError("BUNDLE_VERIFICATION_BLOCKED")


def _check_preflight(preflight: Path) -> dict[str, Any]:
    manifest = v1._json_object((preflight / "preflight-manifest.json").read_text())
    if manifest.get("protocol") != PROTOCOL or manifest.get("policy04_smoke") != "PASS":
        raise ValueError("PREFLIGHT_NOT_V2")
    return manifest


def prepare_campaign(
    bundle: Path, preflight: Path, output: Path, campaign_id: str, machine_id: str
) -> CampaignPlan:
    """Seal a new campaign only; never warms up or starts a scheduling run."""
    import subprocess

    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.contracts.output import ScheduleResult

    check_version_table()
    manifest = _check_preflight(preflight)
    plan = build_campaign_plan(bundle, campaign_id, machine_id)
    runtime = v1._runtime_identity(
        python=Path(sys.executable), preflight_dir=preflight, lock_path=ROOT / "uv.lock"
    )
    machine = v1._machine_identity()
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    with v1._campaign_owner(v1._OWNER_ROOT, output, campaign_id):
        output.mkdir(parents=True)
        headroom = v1.check_headroom(2 * 1024**3)
        v1._write_json(output / "prepare-headroom.json", headroom, exclusive=True)
        if headroom.status != "PASS":
            raise ValueError("PREPARE_HEADROOM_BLOCKED")
        _verify_bundle_isolated(plan.bundle_dir, output / "bundle-verification")
        tiny = preflight / "smoke/input.json"
        for name in ("smoke/input.json", "smoke/result.json"):
            if v1._sha(preflight / name) != manifest["files"][name]:
                raise ValueError("WARMUP_SOURCE_DRIFT")
        problem = ScheduleInput.model_validate(v1._json_object(tiny.read_text()))
        expected = ScheduleResult.model_validate(
            v1._json_object((preflight / "smoke/result.json").read_text())
        )
        if not expected.valid_schedule or expected.input_fingerprint != problem.fingerprint():
            raise ValueError("WARMUP_FIXTURE_INVALID")
        digest = v1._sha(tiny)
        warm = PlannedCase(
            run_id=f"warmup-tiny-{digest}-w1-s42-r0",
            dataset_id="tiny",
            phase="warmup",
            repeat=0,
            class_count=None,
            profile="WARMUP",
            variant=None,
            generator_seed=0,
            input_path=tiny.absolute(),
            dataset_manifest=None,
            manifest_sha256=None,
            input_sha256=digest,
            input_fingerprint=problem.fingerprint(),
            ground_truth="FEASIBLE",
            options=SolveOptions(time_limit_seconds=WARMUP_BUDGET[0]),
            limits=RunLimits(
                watchdog_seconds=WARMUP_BUDGET[1], max_resident_bytes=WARMUP_BUDGET[2]
            ),
        )

        def git(*args: str) -> str:
            return subprocess.check_output(("git", "-C", str(ROOT), *args), text=True).strip()

        environment: dict[str, JsonValue] = {
            "machine": machine,
            "git_head": git("rev-parse", "HEAD"),
            "git_status": git("status", "--porcelain"),
            "windows_status": "NOT_RUN",
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
                preflight_sha256=v1._sha(preflight / "preflight-manifest.json"),
                runtime_identity=runtime,
                environment=environment,
            )
        )
        v1._write_json(output / "plan.json", sealed, exclusive=True)
        v1._write_json(output / "environment.json", environment, exclusive=True)
        v1._write_json(
            output / "seal.json",
            {
                "schema_version": "2.0",
                "plan_sha256": v1._sha(output / "plan.json"),
                "environment_sha256": v1._sha(output / "environment.json"),
            },
            exclusive=True,
        )
        return sealed


def check_campaign_identity(plan: CampaignPlan, path: Path, preflight: Path) -> str:
    """Any drift of seal, sources, bundle, preflight, runtime or machine blocks a run."""
    seal = v1._json_object((path.parent / "seal.json").read_text())
    digest = v1._sha(path)
    if (
        set(seal) != {"schema_version", "plan_sha256", "environment_sha256"}
        or seal["schema_version"] != "2.0"
        or seal["plan_sha256"] != digest
        or seal["environment_sha256"] != v1._sha(path.parent / "environment.json")
        or v1._json_object((path.parent / "environment.json").read_text()) != plan.environment
    ):
        raise ValueError("SEALED_IDENTITY_DRIFT")
    if not plan.sealed or plan.preflight_dir != preflight.absolute():
        raise ValueError("UNSEALED_PLAN")
    current = build_campaign_plan(plan.bundle_dir, plan.campaign_id, plan.machine_id)
    for key in ("bundle_sha256", "source_ids", "dataset_sources", "primary", "pilots"):
        if getattr(current, key) != getattr(plan, key):
            raise ValueError("SOURCE_OR_DATASET_DRIFT")
    if v1._sha(preflight / "preflight-manifest.json") != plan.preflight_sha256:
        raise ValueError("PREFLIGHT_DRIFT")
    runtime = v1._runtime_identity(
        python=Path(sys.executable), preflight_dir=preflight, lock_path=ROOT / "uv.lock"
    )
    if runtime != plan.runtime_identity:
        raise ValueError("RUNTIME_DRIFT")
    if v1._machine_identity() != plan.environment.get("machine", plan.environment):
        raise ValueError("MACHINE_DRIFT")
    assert plan.warmup is not None
    if v1._sha(plan.warmup.input_path) != plan.warmup.input_sha256:
        raise ValueError("WARMUP_DRIFT")
    return digest


EVENT_KEYS = {
    "schema_version",
    "plan_sha256",
    "phase",
    "event",
    "run_id",
    "detail",
    "timestamp_utc",
}


def events(root: Path, digest: str) -> list[dict[str, Any]]:
    path = root / "journal.jsonl"
    if not path.exists():
        return []
    result = []
    for line in path.read_text().splitlines():
        event = v1._json_object(line)
        if (
            set(event) != EVENT_KEYS
            or event["schema_version"] != "2.0"
            or event["plan_sha256"] != digest
            or event["phase"] not in ("warmup", "pilot", "primary")
            or event["event"] not in ("GATE_BLOCKED", "START", "TERMINAL")
        ):
            raise ValueError("JOURNAL_INVALID")
        result.append(event)
    return result


def receipt(root: Path, case: PlannedCase, digest: str) -> tuple[RunRecord, CaseVerdict]:
    base = root / case.phase / case.run_id
    data = v1._json_object((base / "terminal.json").read_text())
    if (
        set(data) != {"schema_version", "plan_sha256", "run_id", "files"}
        or data["schema_version"] != "2.0"
        or data["plan_sha256"] != digest
        or data["run_id"] != case.run_id
    ):
        raise ValueError("TERMINAL_INVALID")
    files = data["files"]
    required = {"run.json", "case-verdict.json"}
    if (
        not isinstance(files, dict)
        or not required <= set(files)
        or set(files)
        - required
        - {"result.json", "stdout.json", "stderr.txt", "native-calls.jsonl"}
    ):
        raise ValueError("TERMINAL_MEMBERSHIP")
    for name, digest_value in files.items():
        if v1._sha(base / name) != digest_value:
            raise ValueError("TERMINAL_EVIDENCE_DRIFT")
    record = RunRecord.model_validate(v1._json_object((base / "run.json").read_text()))
    verdict = CaseVerdict.model_validate(v1._json_object((base / "case-verdict.json").read_text()))
    not_started = (
        record.execution.pid is None
        and record.execution.measurement_status == "NOT_STARTED"
        and record.identity.get("expected_input_sha256") == case.input_sha256
    )
    matches = (
        record.identity.get("input_sha256") == case.input_sha256
        and record.identity.get("input_fingerprint") == case.input_fingerprint
    )
    if verdict.run_sha256 != files["run.json"] or not (not_started or matches):
        raise ValueError("TERMINAL_INPUT_IDENTITY")
    return record, verdict


def read_terminals(
    root: Path, plan: CampaignPlan, digest: str, journal: list[dict[str, Any]]
) -> dict[str, tuple[RunRecord, CaseVerdict]]:
    cases = {c.run_id: c for p in ("warmup", "pilot", "primary") for c in phase_cases(plan, p)}
    started: set[str] = set()
    indices = {"warmup": 0, "pilot": 0, "primary": 0}
    terminal: dict[str, tuple[RunRecord, CaseVerdict]] = {}
    for event in journal:
        ident = event["run_id"]
        if ident not in cases or cases[ident].phase != event["phase"]:
            raise ValueError("UNKNOWN_RUN")
        if event["event"] == "GATE_BLOCKED":
            if ident in started:
                raise ValueError("GATE_AFTER_START")
        elif event["event"] == "START":
            if ident in started:
                raise ValueError("DUPLICATE_START")
            ordered = phase_cases(plan, cast(Phase, event["phase"]))
            index = indices[event["phase"]]
            if index >= len(ordered) or ordered[index].run_id != ident:
                raise ValueError("JOURNAL_ORDER_DRIFT")
            indices[event["phase"]] += 1
            started.add(ident)
        else:
            if ident not in started or ident in terminal:
                raise ValueError("TERMINAL_WITHOUT_START")
            if event["detail"] != {
                "terminal_sha256": v1._sha(root / cases[ident].phase / ident / "terminal.json")
            }:
                raise ValueError("TERMINAL_RECEIPT_DRIFT")
            terminal[ident] = receipt(root, cases[ident], digest)
    if started - set(terminal):
        raise ValueError("UNFINISHED_START")
    for c in cases.values():
        if (root / c.phase / c.run_id).exists() and c.run_id not in terminal:
            raise ValueError("PARTIAL_RUN_DIRECTORY")
    return terminal


def _verdict_for(case: PlannedCase, base: Path, record: RunRecord) -> CaseVerdict:
    if case.phase == "warmup":
        return CaseVerdict(
            hard="PASS" if record.valid_schedule else "NOT_ASSESSED",
            quality="NOT_APPLICABLE",
            performance="NOT_APPLICABLE",
            run_sha256=v1._sha(base / "run.json"),
        )
    assert case.dataset_manifest is not None
    try:
        return judge_case(base, case.dataset_manifest)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return CaseVerdict(
            hard="FAIL",
            reasons=("VERDICT_INVALID:" + type(exc).__name__,),
            run_sha256=v1._sha(base / "run.json"),
        )


def execute_campaign(
    plan_path: Path, preflight_dir: Path, *, phase: str, resume: bool = False
) -> CampaignState:
    """Run one explicitly selected phase; no retry, every terminal outcome retained."""
    if phase not in ("warmup", "pilot", "primary"):
        raise ValueError("Explicit execution phase required")
    selected = cast(Phase, phase)
    plan = CampaignPlan.model_validate(v1._json_object(plan_path.read_text()))
    cases = phase_cases(plan, selected)
    root = plan_path.absolute().parent
    state = CampaignState(
        plan_sha256=v1._sha(plan_path),
        phase=selected,
        status="BLOCKED",
        rows={c.run_id: "NOT_STARTED" for c in cases},
        pending=len(cases),
    )
    try:
        check_version_table()
        digest = check_campaign_identity(plan, plan_path, preflight_dir)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        state.reason = "IDENTITY_BLOCKED:" + str(exc)
        return state
    with v1._campaign_owner(v1._OWNER_ROOT, root, plan.campaign_id) as lease:

        def finish(status: Any, reason: str | None = None) -> CampaignState:
            state.status = status
            state.reason = reason
            state.attempted = sum(v in ("TERMINAL", "PARTIAL") for v in state.rows.values())
            state.completed = sum(v == "TERMINAL" for v in state.rows.values())
            state.pending = len(cases) - state.completed
            if status == "NEEDS_REVIEW":
                lease["state"] = "NEEDS_REVIEW"
            v1._write_json(root / "campaign-state.json", state)
            return state

        try:
            journal = events(root, digest)
            terminal = read_terminals(root, plan, digest, journal)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            for c in cases:
                if (root / selected / c.run_id).exists():
                    state.rows[c.run_id] = "PARTIAL"
            return finish("NEEDS_REVIEW", str(exc))
        for c in cases:
            if c.run_id in terminal:
                state.rows[c.run_id] = "TERMINAL"
                state.failed += int(not qualified(*terminal[c.run_id], c))
        if any(e["phase"] == selected for e in journal) and not resume:
            return finish("BLOCKED", "EXPLICIT_RESUME_REQUIRED")
        prerequisites: tuple[Phase, ...] = (
            ()
            if selected == "warmup"
            else ("warmup",)
            if selected == "pilot"
            else ("warmup", "pilot")
        )
        for required in prerequisites:
            for c in phase_cases(plan, required):
                if c.run_id not in terminal or not qualified(*terminal[c.run_id], c):
                    return finish("BLOCKED", "PREREQUISITE_NOT_PASSED:" + required)

        def event(kind: str, c: PlannedCase, detail: JsonValue = None) -> None:
            v1._journal(
                root / "journal.jsonl",
                {
                    "schema_version": "2.0",
                    "plan_sha256": digest,
                    "phase": selected,
                    "event": kind,
                    "run_id": c.run_id,
                    "detail": detail,
                },
            )

        for c in cases:
            if c.run_id in terminal:
                stop = stop_status(*terminal[c.run_id], c)
                if stop:
                    return finish(stop, "TERMINAL_STOP_RETAINED")
                continue
            try:
                import shutil

                check_campaign_identity(plan, plan_path, preflight_dir)
                headroom = v1.check_headroom(c.limits.max_resident_bytes)
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
                    "operational_context": v1._operational_context(),
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
            verdict = _verdict_for(c, base, record)
            v1._write_json(base / "case-verdict.json", verdict, exclusive=True)
            names = (
                "run.json",
                "case-verdict.json",
                "stdout.json",
                "stderr.txt",
                "result.json",
                "native-calls.jsonl",
            )
            files: dict[str, JsonValue] = {
                name: v1._sha(base / name) for name in names if (base / name).is_file()
            }
            v1._write_json(
                base / "terminal.json",
                {
                    "schema_version": "2.0",
                    "plan_sha256": digest,
                    "run_id": c.run_id,
                    "files": files,
                },
                exclusive=True,
            )
            event("TERMINAL", c, {"terminal_sha256": v1._sha(base / "terminal.json")})
            state.rows[c.run_id] = "TERMINAL"
            state.failed += int(not qualified(record, verdict, c))
            stop = stop_status(record, verdict, c)
            if stop:
                return finish(stop, "RUN_STOP_POLICY")
            finish("BLOCKED", "IN_PROGRESS")
        return finish("COMPLETE")


def policy04_smoke_input() -> dict[str, Any]:
    """Tiny policy 0.4 input exercising hard S02/S05 and soft S08/S10/S11 with occupied work."""
    slots = [
        {"id": f"d{d}-{s.lower()}-p{p}", "day": d, "session": s, "period": p}
        for d in (1, 2)
        for s in ("AM", "PM")
        for p in (1, 2, 3)
    ]
    return {
        "schema_version": "1.1",
        "school": {"school_id": "smoke", "academic_year": "smoke", "term": "smoke"},
        "time_slots": slots,
        "classes": [{"id": "C1"}],
        "teachers": [
            {"id": "T1", "available_slot_ids": [s["id"] for s in slots if s["id"] != "d2-pm-p3"]}
        ],
        "subjects": [{"id": "MATH"}, {"id": "LIT"}],
        "rooms": [],
        "teaching_requirements": [
            {
                "id": "R-MATH",
                "class_ids": ["C1"],
                "teacher_ids": ["T1"],
                "subject_id": "MATH",
                "periods_per_cycle": 3,
                "block_durations": [2, 1],
            },
            {
                "id": "R-LIT",
                "class_ids": ["C1"],
                "teacher_ids": ["T1"],
                "subject_id": "LIT",
                "periods_per_cycle": 2,
            },
        ],
        "constraint_config": {
            "policy_version": "0.4",
            "hard": [
                {
                    "id": "H-S02",
                    "code": "TEACHER_MAX_PERIODS_PER_SESSION",
                    "scope": {"teacher_ids": ["T1"]},
                    "parameters": {"limit": 2, "session_ids": ["AM", "PM"]},
                },
                {
                    "id": "H-S05",
                    "code": "SUBJECT_COMPONENT_DAY_SPREAD",
                    "parameters": {"requirement_ids": ["R-MATH"], "min_day_gap": 1},
                },
            ],
            "soft": [
                {
                    "id": "S08",
                    "code": "TEACHER_TOTAL_GAPS",
                    "priority": 1,
                    "weight": 1,
                    "scope": {"teacher_ids": ["T1"]},
                    "parameters": {"session_ids": ["AM", "PM"]},
                },
                {
                    "id": "S10",
                    "code": "TEACHER_MIN_FREE_TIME",
                    "priority": 2,
                    "weight": 1,
                    "scope": {"teacher_ids": ["T1"]},
                    "parameters": {"unit": "session", "target": 1},
                },
                {
                    "id": "S11",
                    "code": "TEACHER_SINGLE_PERIOD_SESSION",
                    "priority": 3,
                    "weight": 1,
                    "scope": {"teacher_ids": ["T1"]},
                    "parameters": {"session_ids": ["AM", "PM"]},
                },
            ],
            "occupied_work": [{"teacher_id": "T1", "slot_ids": ["d2-pm-p3"]}],
        },
    }


def run_policy04_smoke(smoke: Path, pythons: dict[str, str], run: Any) -> dict[str, JsonValue]:
    """Installed-wheel 0.4 solve, then validate/evaluate in both venvs (Score 1.2)."""
    import json

    from tkb_core.contracts.input import ScheduleInput

    smoke.mkdir(parents=True, exist_ok=False)
    source = smoke / "input.json"
    source.write_text(json.dumps(policy04_smoke_input(), indent=2) + "\n", encoding="utf-8")
    problem = ScheduleInput.model_validate(v1._json_object(source.read_text(encoding="utf-8")))
    output_version, score_version = expected_versions(problem)
    result = smoke / "result.json"
    run(
        "policy04-solve",
        [
            pythons["solver"],
            "-I",
            "-m",
            "tkb_core.cli",
            "solve",
            str(source),
            "--time-limit",
            "5",
            "--output",
            str(result),
        ],
        15,
    )
    solved = v1._json_object(result.read_text(encoding="utf-8"))
    if solved.get("schema_version") != output_version or solved.get("valid_schedule") is not True:
        raise ValueError("POLICY04_SMOKE_RESULT")
    for label in ("solver", "no-solver"):
        for command, status in (("validate-schedule", "SCHEDULE_VALID"), ("evaluate-score", "OK")):
            text = run(
                f"policy04-{label}-{command}",
                [pythons[label], "-I", "-m", "tkb_core.cli", command, str(source), str(result)],
                60,
            )
            parsed = v1._json_object(text)
            if parsed.get("status") != status:
                raise ValueError("POLICY04_SMOKE_" + command.upper())
            if command == "evaluate-score" and parsed.get("schema_version") != score_version:
                raise ValueError("POLICY04_SMOKE_SCORE_VERSION")
    return {
        "status": "PASS",
        "output_version": output_version,
        "score_version": score_version,
        "input_sha256": v1._sha(source),
        "result_sha256": v1._sha(result),
    }


def preflight(
    output: Path, bundle: Path, wheel: Path | None, wheel_sha256: str | None
) -> dict[str, Any]:
    """v1 installed-wheel preflight steps plus the 0.4 smoke and v2 bundle verification."""
    import json
    import shutil

    from benchmarks import phase2a_preflight as pf

    if sys.platform != "linux" or sys.version_info[:2] != (3, 12):
        raise ValueError("NATIVE_LINUX_PYTHON_3_12_REQUIRED")
    check_version_table()
    output, bundle = output.absolute(), bundle.absolute()
    if output.resolve().is_relative_to(bundle.resolve()) or bundle.resolve().is_relative_to(
        output.resolve()
    ):
        raise ValueError("PREFLIGHT_BUNDLE_OVERLAP")
    output.mkdir(parents=True, exist_ok=False)
    for name in ("distribution", "logs", "smoke"):
        (output / name).mkdir()

    def run(name: str, argv: list[str], timeout: float = 300) -> str:
        print("CHECK " + name, flush=True)
        return pf.checked_run(argv, output / "logs" / name, timeout=timeout)

    for name, argv in (
        ("core-tests", ["uv", "run", "--extra", "solver", "pytest"]),
        ("benchmark-tests", ["uv", "run", "--extra", "solver", "pytest", "benchmarks/tests"]),
        ("lint", ["uv", "run", "ruff", "check", "."]),
        ("format", ["uv", "run", "ruff", "format", "--check", "src", "tests", "benchmarks"]),
        ("types", ["uv", "run", "mypy"]),
    ):
        run(name, argv, 1800)
    if wheel is None:
        run("wheel", ["uv", "build", "--wheel", "--out-dir", str(output / "distribution")])
        wheel = next((output / "distribution").glob("*.whl"))
    else:
        if not wheel_sha256 or v1._sha(wheel) != wheel_sha256:
            raise ValueError("SHARED_WHEEL_HASH_REQUIRED_OR_MISMATCH")
        target = output / "distribution" / wheel.name
        shutil.copyfile(wheel, target)
        wheel = target
    pythons: dict[str, str] = {}
    for label in ("solver", "no-solver"):
        extra = ["--extra", "solver"] if label == "solver" else []
        requirements = run(
            "export-" + label,
            ["uv", "export", "--locked", "--no-dev", "--no-emit-project", *extra],
        )
        requirement_path = output / ("requirements-" + label + ".txt")
        requirement_path.write_text(requirements, encoding="utf-8")
        venv = output / ("venv-" + label)
        run("venv-" + label, ["uv", "venv", "--python", sys.executable, str(venv)])
        python = venv / "bin/python"
        pythons[label] = str(python)
        run(
            "dependencies-" + label,
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--require-hashes",
                "--only-binary",
                ":all:",
                "-r",
                str(requirement_path),
            ],
        )
        run(
            "install-" + label,
            ["uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel)],
        )
        run("pip-check-" + label, ["uv", "pip", "check", "--python", str(python)])
        env = json.loads(
            run(
                "identity-" + label,
                [
                    str(python),
                    "-I",
                    str(ROOT / "benchmarks/phase2a_preflight.py"),
                    "probe",
                    "--output",
                    str(output),
                    "--label",
                    label,
                ],
            )
        )
        (output / ("environment-" + label + ".json")).write_text(
            json.dumps(env, indent=2) + "\n", encoding="utf-8"
        )
    # Warmup source, as in v1: the 0.1 tiny fixture solved by the installed wheel.
    tiny = output / "smoke/input.json"
    shutil.copyfile(ROOT / "tests/fixtures/quality/priority_tradeoff.json", tiny)
    run(
        "tiny-solve",
        [
            pythons["solver"],
            "-I",
            "-m",
            "tkb_core.cli",
            "solve",
            str(tiny),
            "--time-limit",
            "5",
            "--output",
            str(output / "smoke/result.json"),
        ],
        15,
    )
    smoke = run_policy04_smoke(output / "smoke/policy04", pythons, run)
    run(
        "bundle-verification",
        list(bundle_verification_argv(Path(pythons["solver"]), bundle)),
        BUNDLE_WATCHDOG_SECONDS,
    )
    env = json.loads((output / "environment-solver.json").read_text())
    files = {
        path.relative_to(output).as_posix(): v1._sha(path)
        for directory in (output / "logs", output / "smoke", output / "distribution")
        for path in directory.rglob("*")
        if path.is_file()
    }
    for label in ("solver", "no-solver"):
        name = "environment-" + label + ".json"
        files[name] = v1._sha(output / name)
    manifest = {
        "preflight_schema_version": "1.0",
        "protocol": PROTOCOL,
        "linux_status": "PASS",
        "windows_status": "NOT_RUN",
        "policy04_smoke": smoke["status"],
        "policy04_smoke_detail": smoke,
        "wheel_sha256": v1._sha(wheel),
        "uv_lock_sha256": v1._sha(ROOT / "uv.lock"),
        "git_commit": env["git_commit"],
        "core_tree": env["core_tree"],
        "bundle_manifest_sha256": v1._sha(bundle / "manifest.json"),
        "files": files,
    }
    (output / "preflight-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    """Explicit phase CLI; preflight/prepare never start a measured scheduling run."""
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", required=True, choices=("preflight", "prepare", "warmup", "pilot", "primary")
    )
    for flag in ("bundle", "preflight-dir", "output", "plan", "wheel"):
        parser.add_argument("--" + flag, type=Path)
    parser.add_argument("--wheel-sha256")
    parser.add_argument("--campaign-id")
    parser.add_argument("--machine-id")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.phase == "preflight":
            if args.output is None or args.bundle is None:
                parser.error("preflight requires --output and --bundle")
            result = preflight(args.output, args.bundle, args.wheel, args.wheel_sha256)
            print(json.dumps({"status": "PREFLIGHT_PASS", "protocol": result["protocol"]}))
            return 0
        if args.preflight_dir is None:
            parser.error("--preflight-dir required")
        if args.phase == "prepare":
            if (
                args.resume
                or args.plan is not None
                or not all((args.bundle, args.output, args.campaign_id, args.machine_id))
            ):
                parser.error(
                    "prepare requires bundle/output/campaign-id/machine-id, no plan/resume"
                )
            prepare_campaign(
                args.bundle, args.preflight_dir, args.output, args.campaign_id, args.machine_id
            )
            print(json.dumps({"status": "PREPARED", "primary_planned": PRIMARY_COUNT, "pilots": 2}))
            return 0
        if args.plan is None or any((args.bundle, args.output, args.campaign_id, args.machine_id)):
            parser.error("execution requires plan only, no prepare arguments")
        state = execute_campaign(
            args.plan, args.preflight_dir, phase=args.phase, resume=args.resume
        )
        print(state.model_dump_json())
        return 0 if state.status == "COMPLETE" else 2
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(
            json.dumps({"status": "BLOCKED", "error_type": type(exc).__name__, "reason": str(exc)})
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
