"""Read-only Task 5 aggregation of sealed Linux campaign evidence; never runs a solver."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from benchmarks import run_benchmarks as runner
from tkb_core.contracts.output import ScheduleResult


def _counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(r[field] or "UNAVAILABLE") for r in rows).items()))


def _stats(values: list[float | int | None]) -> dict[str, Any]:
    present = [v for v in values if v is not None]
    return {
        "n": len(present),
        "missing": len(values) - len(present),
        "min": min(present) if present else None,
        "median": median(present) if present else None,
        "max": max(present) if present else None,
    }


def _counts_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    feasible = [r for r in rows if r["profile"] != "UNSAT_CAPACITY"]
    correctness = _counts(rows, "correctness")
    performance = _counts(feasible, "performance")
    return {
        "total": len(rows),
        "known_feasible": len(feasible),
        "valid_schedules": sum(r["valid_schedule"] for r in rows),
        "not_qualified": sum(not r["qualified"] for r in rows),
        **{
            field: _counts(rows, field)
            for field in (
                "harness_status",
                "solver_status",
                "correctness",
                "performance",
                "quality",
            )
        },
        "failure_causes": dict(
            sorted(
                Counter(
                    cause for r in rows if not r["qualified"] for cause in r["failure_causes"]
                ).items()
            )
        ),
        "correctness_verdict": (
            "FAIL"
            if correctness.get("FAIL")
            else "INCOMPLETE"
            if correctness.get("NOT_ASSESSED")
            else "PASS"
        ),
        "performance_verdict": (
            "NOT_APPLICABLE"
            if not feasible
            else "NOT_MET"
            if performance.get("NOT_MET")
            else "MET"
            if performance.get("MET") == len(feasible)
            else "NOT_ASSESSED"
        ),
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep all outcomes; summarize metrics only among repeats of the same dataset/input."""
    if len({r["run_id"] for r in rows}) != len(rows):
        raise ValueError("Duplicate run rows")
    for r in rows:
        if (r["score"] is not None) != r["valid_schedule"]:
            raise ValueError("Unverified or missing score")
    result = _counts_summary(rows)
    result["profiles"] = []
    for size, profile in sorted({(r["class_count"], r["profile"]) for r in rows}):
        selected = [r for r in rows if (r["class_count"], r["profile"]) == (size, profile)]
        result["profiles"].append(
            {"class_count": size, "profile": profile, **_counts_summary(selected)}
        )
    result["datasets"] = []
    for dataset, fp in sorted({(r["dataset_id"], r["input_fingerprint"]) for r in rows}):
        selected = [r for r in rows if (r["dataset_id"], r["input_fingerprint"]) == (dataset, fp)]
        metrics = sorted({key for r in selected for key in r["metrics"]})
        result["datasets"].append(
            {
                "dataset_id": dataset,
                "input_fingerprint": fp,
                **_counts_summary(selected),
                "metrics": {
                    key: _stats([r["metrics"].get(key) for r in selected]) for key in metrics
                },
                "run_ids": [r["run_id"] for r in selected],
            }
        )
    return result


def _verify_frozen(root: Path) -> tuple[runner.CampaignPlan, str]:
    plan_path = root / "plan.json"
    plan = runner.CampaignPlan.model_validate(runner._json_object(plan_path.read_text()))
    digest = runner._sha(plan_path)
    seal = runner._json_object((root / "seal.json").read_text())
    if (
        seal
        != {
            "schema_version": "1.0",
            "plan_sha256": digest,
            "environment_sha256": runner._sha(root / "environment.json"),
        }
        or runner._json_object((root / "environment.json").read_text()) != plan.environment
    ):
        raise ValueError("SEALED_IDENTITY_DRIFT")
    if not plan.sealed or plan.preflight_dir is None or plan.warmup is None:
        raise ValueError("UNSEALED_PLAN")
    current = runner.build_campaign_plan(plan.bundle_dir, plan.campaign_id, plan.machine_id)
    for key in ("bundle_sha256", "source_ids", "dataset_sources", "primary", "pilot"):
        if getattr(current, key) != getattr(plan, key):
            raise ValueError("SOURCE_OR_DATASET_DRIFT")
    if runner._sha(plan.preflight_dir / "preflight-manifest.json") != plan.preflight_sha256:
        raise ValueError("PREFLIGHT_DRIFT")
    if runner._sha(plan.warmup.input_path) != plan.warmup.input_sha256:
        raise ValueError("WARMUP_DRIFT")
    return plan, digest


def _row(
    case: runner.PlannedCase,
    record: runner.RunRecord,
    verdict: runner.CaseVerdict,
    result: ScheduleResult | None,
) -> dict[str, Any]:
    assert case.dataset_manifest is not None
    meta = runner._json_object(case.dataset_manifest.read_text())
    execution = record.execution
    quality = result.quality if result else None
    metadata = result.metadata if result else None
    vector = record.output.score.tiers if record.valid_schedule and record.output.score else None
    causes = []
    if not runner._qualified(record, verdict, case):
        if verdict.correctness == "FAIL":
            causes.append("CORRECTNESS_FAIL")
        if case.profile != "UNSAT_CAPACITY":
            if not record.valid_schedule:
                causes.append("NO_SCHEDULE")
            if vector is not None and meta["known_optimum"] == [0, 0, 0] and vector != (0, 0, 0):
                causes.append("ZERO_TARGET_NOT_MET")
            if execution.peak_resident_bytes is not None and (
                execution.peak_resident_bytes > case.limits.max_resident_bytes
            ):
                causes.append("MEMORY_TARGET_EXCEEDED")
            if execution.launch_to_exit_seconds is not None and (
                execution.launch_to_exit_seconds > case.limits.watchdog_seconds
            ):
                causes.append("WATCHDOG_EXCEEDED")
        if execution.measurement_status != "OK":
            causes.append("MEASUREMENT_UNAVAILABLE")
        if record.harness_status != "COMPLETE":
            causes.append("HARNESS:" + record.harness_status)
        if not causes:
            causes.append("UNQUALIFIED_OTHER")
    feasibility = getattr(metadata, "feasibility_run", None)
    return {
        "run_id": case.run_id,
        "dataset_id": case.dataset_id,
        "repeat": case.repeat,
        "input_fingerprint": case.input_fingerprint,
        "input_sha256": case.input_sha256,
        "class_count": case.class_count,
        "profile": case.profile,
        "ground_truth": case.ground_truth,
        "known_optimum": meta["known_optimum"],
        "baseline_score": meta["baseline_score"]["tiers"] if meta["baseline_score"] else None,
        "p2_lower_bound": meta["p2_lower_bound"],
        "capacity_proof": meta["capacity_proof"],
        "dimensions": meta["dimensions"],
        "options": case.options.model_dump(mode="json"),
        "limits": case.limits.model_dump(mode="json"),
        "harness_status": record.harness_status,
        "solver_status": record.output.solver_status,
        "valid_schedule": record.valid_schedule,
        "correctness": verdict.correctness,
        "performance": verdict.performance,
        "quality": verdict.quality,
        "reasons": list(verdict.reasons),
        "qualified": runner._qualified(record, verdict, case),
        "failure_causes": causes,
        "score": list(vector) if vector is not None else None,
        "quality_status": quality.status if quality else None,
        "optimal_prefix": list(quality.optimal_prefix) if quality else [],
        "tier_runs": [r.model_dump(mode="json") for r in quality.tier_runs] if quality else [],
        "feasibility_run": feasibility.model_dump(mode="json") if feasibility else None,
        "solver_executed": getattr(metadata, "solver_executed", None),
        "diagnostics": [d.code for d in result.diagnostics] if result else [],
        "measurement_status": execution.measurement_status,
        "measurement_reason": execution.measurement_reason,
        "first_feasible_reason": record.first_feasible_reason,
        "metrics": {
            "launch_to_exit_seconds": execution.launch_to_exit_seconds,
            "core_wall_seconds": metadata.wall_time if metadata else None,
            "solver_wall_seconds": getattr(metadata, "solver_wall_time", None),
            "feasibility_solver_seconds": feasibility.wall_time if feasibility else None,
            "parent_verification_seconds": record.parent_verification_seconds,
            "cpu_seconds": execution.cpu_seconds,
            "peak_resident_bytes": execution.peak_resident_bytes,
            "first_feasible_elapsed_seconds": record.first_feasible_elapsed_seconds,
        },
    }


def aggregate_campaign(root: Path) -> dict[str, Any]:
    """Verify historical bytes/journal/policy and independently recheck outputs, without search."""
    root = root.resolve()
    plan, digest = _verify_frozen(root)
    events = runner._events(root, digest)
    terminals = runner._read_terminals(root, plan, digest, events)
    state = runner.CampaignState.model_validate(
        runner._json_object((root / "campaign-state.json").read_text())
    )
    if (
        state.plan_sha256 != digest
        or state.phase != "primary"
        or state.status != "COMPLETE"
        or state.attempted != 108
        or state.completed != 108
        or state.pending != 0
        or state.rows != {c.run_id: "TERMINAL" for c in plan.primary}
        or len(terminals) != 110
    ):
        raise ValueError("INCOMPLETE_OR_INCONSISTENT_CAMPAIGN")
    rows = []
    rechecked = 0
    evidence = {
        name: runner._sha(root / name)
        for name in (
            "plan.json",
            "seal.json",
            "environment.json",
            "journal.jsonl",
            "campaign-state.json",
        )
    }
    for case in (plan.warmup, plan.pilot, *plan.primary):
        assert case is not None
        record, verdict = terminals[case.run_id]
        base = root / case.phase / case.run_id
        e = record.execution
        if (
            e.run_dir.resolve() != base
            or e.stdout_path.resolve() != base / "stdout.json"
            or (e.stderr_path.resolve() != base / "stderr.txt")
        ):
            raise ValueError("EXECUTION_PATH_DRIFT")
        if any(record.identity.get(k) != v for k, v in plan.runtime_identity.items()) or (
            record.identity.get("options") != case.options.model_dump(mode="json")
            or record.identity.get("limits") != case.limits.model_dump(mode="json")
        ):
            raise ValueError("RUN_POLICY_OR_RUNTIME_DRIFT")
        if record.output.status != "SKIPPED":
            if runner.verify_cli_output(case.input_path, base / "result.json", e) != record.output:
                raise ValueError("INDEPENDENT_OUTPUT_MISMATCH")
            rechecked += 1
        if case.phase != "warmup":
            assert case.dataset_manifest is not None
            if runner.check_case(base, case.dataset_manifest) != verdict:
                raise ValueError("VERDICT_MISMATCH")
        if case.phase != "primary" and not runner._qualified(record, verdict, case):
            raise ValueError("PREREQUISITE_NOT_PASSED")
        evidence[str((base / "terminal.json").relative_to(root))] = runner._sha(
            base / "terminal.json"
        )
        if case.phase == "primary":
            result = (
                ScheduleResult.model_validate_json((base / "result.json").read_text())
                if record.output.status in ("VALID_SCHEDULE", "VALID_CORE_ERROR")
                else None
            )
            rows.append(_row(case, record, verdict, result))
    summary = summarize(rows)
    if summary["not_qualified"] != state.failed:
        raise ValueError("FAILED_COUNTER_MISMATCH")
    for event in events:
        if event["event"] == "START":
            admission = runner.HeadroomCheck.model_validate(event["detail"]["headroom"])
            case = next(
                c
                for c in (plan.warmup, plan.pilot, *plan.primary)
                if c is not None and c.run_id == event["run_id"]
            )
            if (
                admission.status != "PASS"
                or admission.target_bytes != case.limits.max_resident_bytes
            ):
                raise ValueError("ADMISSION_NOT_PASSED")
    return {
        "schema_version": "1.0",
        "scope": "Task5 Linux historical evidence only",
        "campaign_id": plan.campaign_id,
        "plan_sha256": digest,
        "windows_status": "BLOCKED",
        "cross_platform_verdict": "BLOCKED",
        "evidence_status": "PASS",
        "receipts_verified": len(terminals),
        "independent_outputs_rechecked": rechecked,
        "current_execution_gate": "NOT_ASSESSED_NO_EXECUTION",
        "historical_machine": plan.environment.get("machine"),
        "runtime_identity": plan.runtime_identity,
        "source_ids": plan.source_ids,
        "limitations": [
            "Three repeats per fingerprint; descriptive min/median/max only, no P95/SLA.",
            "No cross-fingerprint metrics or score pooling; profile summaries count outcomes.",
            "No time-to-first-feasible instrumentation; null is not zero.",
            "Independent hard/score/metadata checks do not re-prove optimality.",
            "Historical MemTotal drift (4KiB) remains; this audit does not authorize execution.",
        ],
        "evidence_sha256": evidence,
        "summary": summary,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    """Emit a verified JSON report to stdout or a new file, never overwrite campaign evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = aggregate_campaign(args.campaign)
        raw = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if args.output:
            plan, _ = _verify_frozen(args.campaign.resolve())
            if any(
                args.output.resolve().is_relative_to(p.resolve())
                for p in (
                    args.campaign,
                    plan.bundle_dir,
                    plan.preflight_dir,
                )
                if p is not None
            ):
                raise ValueError("OUTPUT_WOULD_MODIFY_FROZEN_EVIDENCE")
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(raw)
        else:
            print(raw, end="")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Task5 aggregation blocked: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
