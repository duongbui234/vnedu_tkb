"""Summarize a sealed v2 campaign without re-running or rewriting any evidence.

Run as ``python -m benchmarks.aggregate_phase2 --campaign <root> --preflight-dir <dir>
--output <new dir>``. Statistics never turn null measurements into zero, never merge
datasets, and never estimate P95 or an SLA from three repeats.
"""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmarks import run_benchmarks as v1
from benchmarks import run_phase2 as r2


@dataclass(frozen=True)
class Row:
    case: r2.PlannedCase
    record: v1.RunRecord | None
    verdict: r2.CaseVerdict | None


def _stats(values: Sequence[float], *, conditional: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "n": len(values),
        "min": min(values) if values else None,
        "median": statistics.median(values) if values else None,
        "max": max(values) if values else None,
    }
    if conditional:
        result["conditional_on_success"] = True
    return result


def _group_key(case: r2.PlannedCase) -> str:
    return f"{case.variant}/c{case.class_count}/{case.profile}/{case.dataset_id}"


def summarize(rows: Sequence[Row]) -> dict[str, Any]:
    """Campaign verdicts over the full planned denominator plus per-dataset groups."""
    terminal = [r for r in rows if r.record is not None and r.verdict is not None]
    missing = len(rows) - len(terminal)
    verdicts = [r.verdict for r in terminal if r.verdict is not None]
    feasible = [r for r in terminal if r.case.ground_truth == "FEASIBLE"]
    unsat = [r for r in terminal if r.case.ground_truth == "INFEASIBLE"]
    if any(v.hard == "FAIL" for v in verdicts):
        hard = "FAIL"
    elif missing or any(v.hard == "NOT_ASSESSED" for v in verdicts):
        hard = "INCOMPLETE"
    else:
        hard = "PASS"
    perf = [r.verdict.performance for r in feasible if r.verdict is not None]
    unsat_hard = [r.verdict.hard for r in unsat if r.verdict is not None]
    if "NOT_MET" in perf or "FAIL" in unsat_hard:
        performance = "NOT_MET"
    elif missing or "INCOMPLETE" in perf or any(h != "PASS" for h in unsat_hard):
        performance = "INCOMPLETE"
    else:
        performance = "MET"
    zero = Counter(v.zero for v in verdicts)
    zero["MISSING"] = missing
    groups: dict[str, dict[str, Any]] = {}
    for key in sorted({_group_key(r.case) for r in rows}):
        members = [r for r in rows if _group_key(r.case) == key]
        done = [r for r in members if r.record is not None and r.verdict is not None]
        times = [
            r.record.execution.launch_to_exit_seconds
            for r in done
            if r.record is not None
            and r.record.valid_schedule
            and r.record.execution.measurement_status == "OK"
            and r.record.execution.launch_to_exit_seconds is not None
        ]
        rss = [
            float(r.record.execution.peak_resident_bytes)
            for r in done
            if r.record is not None
            and r.record.execution.measurement_status == "OK"
            and r.record.execution.peak_resident_bytes is not None
        ]
        case = members[0].case
        groups[key] = {
            "variant": case.variant,
            "class_count": case.class_count,
            "profile": case.profile,
            "dataset_id": case.dataset_id,
            "input_fingerprint": case.input_fingerprint,
            "planned": len(members),
            "terminal": len(done),
            "schedules": sum(r.record is not None and r.record.valid_schedule for r in done),
            "censored_without_schedule": sum(
                r.record is not None
                and not r.record.valid_schedule
                and r.case.ground_truth == "FEASIBLE"
                and r.record.execution.measurement_status == "OK"
                for r in done
            ),
            "measurement_missing": sum(
                r.record is not None and r.record.execution.measurement_status != "OK" for r in done
            ),
            "harness_status": dict(Counter(r.record.harness_status for r in done if r.record)),
            "hard": dict(Counter(r.verdict.hard for r in done if r.verdict)),
            "performance": dict(Counter(r.verdict.performance for r in done if r.verdict)),
            "zero": dict(Counter(r.verdict.zero for r in done if r.verdict)),
            "witness_comparison": {
                label: sum(
                    r.verdict is not None and r.verdict.witness_comparison == label for r in done
                )
                for label in ("BETTER", "EQUAL", "WORSE")
            },
            "score_vectors": [
                list(r.record.output.score.tiers)
                for r in done
                if r.record is not None
                and r.record.output.score is not None
                and r.record.output.score.tiers is not None
            ],
            "launch_to_exit_seconds": _stats(times, conditional=True),
            "peak_resident_bytes": _stats(rss, conditional=False),
        }
    return {
        "schema_version": "2.0",
        "protocol": r2.PROTOCOL,
        "campaign": {
            "planned": len(rows),
            "terminal": len(terminal),
            "missing": missing,
            "H": hard,
            "P": performance,
            "Q": "REVIEW_REQUIRED"
            if any(v.quality == "REVIEW_REQUIRED" for v in verdicts)
            else "NO_SCHEDULE",
            "zero": {
                label: zero.get(label, 0)
                for label in ("MET", "NOT_MET", "NOT_APPLICABLE", "MISSING")
            },
        },
        "groups": groups,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    c = summary["campaign"]
    lines = [
        f"# {summary['protocol']} summary",
        "",
        f"Planned {c['planned']}, terminal {c['terminal']}, missing {c['missing']}.",
        f"H: {c['H']}. P: {c['P']}. Q: {c['Q']} (no quality profile). Zero: {c['zero']}.",
        "",
        "Three repeats per dataset: no P95 and no SLA. Launch-to-exit statistics are "
        "conditional on success; runs without a schedule are counted as censored, never "
        "given the watchdog as a time. Missing measurements stay missing.",
        "",
        "| Group | Planned | Terminal | Schedules | Censored | P | Launch-to-exit s "
        "(min/median/max, conditional on success) | Peak RSS bytes (max) |",
        "|---|---:|---:|---:|---:|---|---|---:|",
    ]
    for key, g in summary["groups"].items():
        t = g["launch_to_exit_seconds"]
        span = "—" if not t["n"] else f"{t['min']:.3f} / {t['median']:.3f} / {t['max']:.3f}"
        rss = g["peak_resident_bytes"]["max"]
        lines.append(
            f"| {key} | {g['planned']} | {g['terminal']} | {g['schedules']} | "
            f"{g['censored_without_schedule']} | {g['performance']} | {span} | "
            f"{'—' if rss is None else int(rss)} |"
        )
    return "\n".join(lines) + "\n"


def _verify_frozen(root: Path, preflight: Path) -> tuple[r2.CampaignPlan, str]:
    plan_path = root / "plan.json"
    plan = r2.CampaignPlan.model_validate(v1._json_object(plan_path.read_text()))
    digest = v1._sha(plan_path)
    seal = v1._json_object((root / "seal.json").read_text())
    if (
        seal
        != {
            "schema_version": "2.0",
            "plan_sha256": digest,
            "environment_sha256": v1._sha(root / "environment.json"),
        }
        or v1._json_object((root / "environment.json").read_text()) != plan.environment
    ):
        raise ValueError("SEALED_IDENTITY_DRIFT")
    if not plan.sealed or plan.preflight_dir != preflight.absolute():
        raise ValueError("UNSEALED_PLAN")
    current = r2.build_campaign_plan(plan.bundle_dir, plan.campaign_id, plan.machine_id)
    for key in ("bundle_sha256", "source_ids", "dataset_sources", "primary", "pilots"):
        if getattr(current, key) != getattr(plan, key):
            raise ValueError("SOURCE_OR_DATASET_DRIFT")
    if v1._sha(preflight / "preflight-manifest.json") != plan.preflight_sha256:
        raise ValueError("PREFLIGHT_DRIFT")
    return plan, digest


def aggregate(campaign: Path, preflight: Path, output: Path) -> dict[str, Any]:
    """Read terminal receipts of a sealed campaign; write a new summary directory."""
    campaign, output = campaign.absolute(), output.absolute()
    if output.resolve().is_relative_to(campaign.resolve()):
        raise ValueError("OUTPUT_WOULD_MODIFY_FROZEN_EVIDENCE")
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    plan, digest = _verify_frozen(campaign, preflight)
    terminal = r2.read_terminals(campaign, plan, digest, r2.events(campaign, digest))
    rows = [Row(c, *terminal.get(c.run_id, (None, None))) for c in plan.primary]
    pilots = [Row(c, *terminal.get(c.run_id, (None, None))) for c in plan.pilots]
    summary = summarize(rows)
    summary["campaign_id"] = plan.campaign_id
    summary["plan_sha256"] = digest
    summary["pilots"] = {
        row.case.dataset_id: None if row.verdict is None else row.verdict.model_dump(mode="json")
        for row in pilots
    }
    output.mkdir(parents=True)
    import json

    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
    )
    (output / "summary.md").write_text(render_markdown(summary), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("campaign", "preflight-dir", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        summary = aggregate(args.campaign, args.preflight_dir, args.output)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(
            json.dumps({"status": "BLOCKED", "error_type": type(exc).__name__, "reason": str(exc)})
        )
        return 2
    print(json.dumps({"status": "SUMMARIZED", "campaign": summary["campaign"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
