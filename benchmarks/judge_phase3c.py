"""Phase 3C verdicts (plan §4, C7) and stop gates (plan §5), outside Scheduling Core.

A verdict judges one terminal run against fixed limits; it never aggregates. Independent checks
(``validate-schedule``, ``evaluate-score``, ``evaluate-repair``, ``check-explanation``) run during
output verification in ``run_phase3c``; a run only reaches ``valid_schedule=True`` when all of
them passed. Solve runs (step S) reuse the frozen v2 verdict.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, JsonValue, StrictStr

from benchmarks import run_benchmarks as v1
from benchmarks import run_phase2 as r2
from benchmarks.run_benchmarks import RunLimits, RunRecord
from tkb_core.domain.models import DomainModel

SHA = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
Label = Literal["BASELINE", "UNSAT", "GROUND_TRUTH_UNKNOWN", "EXPECTED_INFEASIBLE"]
NOT_MET_HARNESS = ("WATCHDOG_TIMEOUT", "RESOURCE_STOP")


class Verdict3C(DomainModel):
    """Plan §4 axes for one run; ``changes``/``explain`` carry the C and X observations."""

    schema_version: Literal["3c-1.0"] = "3c-1.0"
    hard: Literal["PASS", "FAIL", "NOT_APPLICABLE", "NOT_ASSESSED"] = "NOT_ASSESSED"
    performance: Literal["MET", "NOT_MET", "INCOMPLETE", "NOT_APPLICABLE"] = "INCOMPLETE"
    quality: Literal["REVIEW_REQUIRED", "NO_SCHEDULE", "NOT_APPLICABLE"] = "NO_SCHEDULE"
    status: StrictStr | None = None
    score: tuple[int, ...] | None = None
    changes: dict[str, JsonValue] | None = None
    explain: dict[str, JsonValue] | None = None
    reasons: tuple[StrictStr, ...] = ()
    run_sha256: SHA


def within_limits(record: RunRecord, limits: RunLimits) -> bool:
    execution = record.execution
    return (
        execution.peak_resident_bytes is not None
        and execution.launch_to_exit_seconds is not None
        and execution.peak_resident_bytes <= limits.max_resident_bytes
        and execution.launch_to_exit_seconds <= limits.watchdog_seconds
    )


def _measured(record: RunRecord) -> bool:
    return record.execution.measurement_status == "OK"


def _sha(base: Path) -> str:
    path = base / "run.json"
    return v1._sha(path) if path.is_file() else "0" * 64


def _base_verdict(record: RunRecord, base: Path) -> Verdict3C | None:
    """Shared outcome for runs that never produced a judgeable output."""
    if record.harness_status in NOT_MET_HARNESS and _measured(record):
        return Verdict3C(
            hard="NOT_APPLICABLE",
            performance="NOT_MET",
            reasons=(record.harness_status,),
            run_sha256=_sha(base),
        )
    if record.harness_status != "COMPLETE":
        return Verdict3C(reasons=(record.harness_status,), run_sha256=_sha(base))
    return None


def judge_solve(record: RunRecord, base: Path, dataset_manifest: Path) -> Verdict3C:
    """Step S: the frozen v2 H/Q/P verdict, mapped onto the 3C model."""
    early = _base_verdict(record, base)
    if early is not None:
        return early
    from tkb_core.contracts.output import ScheduleResult

    v2 = r2.judge_case(base, dataset_manifest)
    result = ScheduleResult.model_validate(v1._json_object((base / "result.json").read_text()))
    score = result.quality.score if result.quality else None
    return Verdict3C(
        hard="NOT_ASSESSED" if v2.hard == "NOT_ASSESSED" else v2.hard,
        performance=v2.performance,
        quality=v2.quality,
        status=str(result.status),
        score=None if score is None else tuple(t for t in score.tiers),
        reasons=v2.reasons,
        run_sha256=_sha(base),
    )


def judge_repair(record: RunRecord, base: Path, label: Label, limits: RunLimits) -> Verdict3C:
    early = _base_verdict(record, base)
    if early is not None:
        return early
    from tkb_core.contracts.repair import RepairResult

    envelope = RepairResult.model_validate(v1._json_object((base / "result.json").read_text()))
    result = envelope.result
    status = str(result.status)
    if record.valid_schedule:
        reasons: list[str] = []
        hard: Literal["PASS", "FAIL"] = "PASS"
        if label == "EXPECTED_INFEASIBLE":
            hard, reasons = "FAIL", ["SCHEDULE_FOR_PROVED_INFEASIBLE"]
        report = envelope.repair
        assert report is not None
        score = result.quality.score if result.quality else None
        return Verdict3C(
            hard=hard,
            performance="MET" if within_limits(record, limits) else "NOT_MET",
            quality="REVIEW_REQUIRED",
            status=status,
            score=None if score is None else tuple(score.tiers),
            changes={
                "changed": report.changed,
                "forced": report.forced,
                "slot_changes": report.slot_changes,
                "room_only_changes": report.room_only_changes,
                "new": report.new,
                "dropped": report.dropped,
                "frozen": report.frozen,
                "min_changes_proved": report.min_changes_proved,
            },
            reasons=tuple(reasons),
            run_sha256=_sha(base),
        )
    if status == "INFEASIBLE":
        return Verdict3C(
            hard="NOT_APPLICABLE",
            performance="NOT_APPLICABLE",
            status=status,
            run_sha256=_sha(base),
        )
    if status == "UNKNOWN":
        return Verdict3C(
            hard="NOT_APPLICABLE", performance="NOT_MET", status=status, run_sha256=_sha(base)
        )
    return Verdict3C(
        hard="FAIL", status=status, reasons=("UNEXPECTED_STATUS",), run_sha256=_sha(base)
    )


def judge_explain(record: RunRecord, base: Path, label: Label, limits: RunLimits) -> Verdict3C:
    early = _base_verdict(record, base)
    if early is not None:
        return early
    from tkb_core.contracts.diagnostics import InfeasibilityReport

    report = InfeasibilityReport.model_validate(v1._json_object((base / "report.json").read_text()))
    observed: dict[str, JsonValue] = {
        "status": report.status,
        "granularity": report.granularity,
        "solver_calls": report.metadata.solver_calls,
        "wall_time": report.metadata.wall_time,
        "minimal_proved": report.minimal_proved,
        "subset_size": len(report.subset),
        "precheck_proofs": len(report.precheck_proofs),
    }
    conclusive = report.status in ("PRECHECK_PROOF", "CORE_SUBSET")
    if label in ("UNSAT", "EXPECTED_INFEASIBLE") and report.status == "NOT_INFEASIBLE":
        return Verdict3C(
            hard="FAIL",
            status=report.status,
            explain=observed,
            reasons=("UNSAT_REPORTED_FEASIBLE",),
            run_sha256=_sha(base),
        )
    if report.status in ("UNKNOWN", "RESOURCE_LIMIT"):
        performance: Literal["MET", "NOT_MET", "NOT_APPLICABLE"] = "NOT_MET"
    elif not conclusive:
        performance = "NOT_APPLICABLE"
    else:
        performance = "MET" if within_limits(record, limits) else "NOT_MET"
    return Verdict3C(
        hard="PASS" if conclusive else "NOT_APPLICABLE",
        performance=performance,
        quality="NOT_APPLICABLE",
        status=report.status,
        explain=observed,
        run_sha256=_sha(base),
    )


def stop_status(record: RunRecord, verdict: Verdict3C) -> str | None:
    """Plan §5: safety and correctness stop the campaign; P NOT_MET and INFEASIBLE do not."""
    execution = record.execution
    if execution.pid is not None and (
        execution.exit_code is None
        or (execution.measurement_method == "linux_wait4" and execution.raw_wait_status is None)
    ):
        if record.harness_status not in NOT_MET_HARNESS:
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
    return None
