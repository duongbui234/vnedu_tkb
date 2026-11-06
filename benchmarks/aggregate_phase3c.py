"""Phase 3C aggregation (plan §4), outside Scheduling Core.

Reads a campaign only through verified journals and terminal receipts, then reports per cell
(part / size / profile / variant / noise) without merging cells, plus paired comparisons with the
same input: hint versus no hint, and BEFORE versus AFTER. n = 1 per cell: no P95 and no SLA.
Timing is conditional on success; runs stopped by the watchdog or a resource limit are censored,
and a missing measurement stays missing.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Row:
    run_id: str
    part: str
    dataset_id: str
    class_count: int
    profile: str
    variant: str
    noise: str | None
    order: str | None
    hint: bool | None
    granularity: str | None
    label: str
    harness_status: str
    launch_to_exit_seconds: float | None
    peak_resident_bytes: int | None
    hard: str
    performance: str
    status: str | None
    score: list[int] | None
    changes: dict[str, Any] | None
    explain: dict[str, Any] | None


def _stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "min": None, "median": None, "max": None}
    return {
        "n": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def _cell(row: Row) -> str:
    tail = row.noise or row.granularity or "-"
    return f"{row.part}/{row.class_count}/{row.profile}/{row.variant}/{tail}"


def summarize(rows: list[Row]) -> dict[str, Any]:
    parts: dict[str, dict[str, Any]] = {}
    for part in sorted({r.part for r in rows}):
        mine = [r for r in rows if r.part == part]
        parts[part] = {
            "planned": len(mine),
            "terminal": len(mine),
            "H": dict(Counter(r.hard for r in mine)),
            "P": dict(Counter(r.performance for r in mine)),
            "status": dict(Counter(r.status or "NONE" for r in mine)),
            "label": dict(Counter(r.label for r in mine)),
        }
    cells: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        grouped[_cell(row)].append(row)
    for key, mine in sorted(grouped.items()):
        met = [
            r.launch_to_exit_seconds
            for r in mine
            if r.performance == "MET" and r.launch_to_exit_seconds is not None
        ]
        cells[key] = {
            "runs": len(mine),
            "status": dict(Counter(r.status or r.harness_status for r in mine)),
            "H": dict(Counter(r.hard for r in mine)),
            "P": dict(Counter(r.performance for r in mine)),
            "launch_to_exit_seconds": _stats(met),
            "censored": sum(
                r.harness_status in ("WATCHDOG_TIMEOUT", "RESOURCE_STOP") for r in mine
            ),
            "peak_resident_bytes_max": max(
                (r.peak_resident_bytes for r in mine if r.peak_resident_bytes is not None),
                default=None,
            ),
            "changed": [r.changes["changed"] for r in mine if r.changes],
            "forced": [r.changes["forced"] for r in mine if r.changes],
            "min_changes_proved": sum(
                bool(r.changes and r.changes.get("min_changes_proved")) for r in mine
            ),
            "explain_status": dict(Counter(r.explain["status"] for r in mine if r.explain)),
        }
    by_key = {(r.part, r.dataset_id, r.noise, r.hint): r for r in rows if r.noise}
    hint_pairs = []
    for (part, dataset, noise, hint), row in sorted(by_key.items(), key=lambda kv: str(kv[0])):
        other = by_key.get((part, dataset, noise, False))
        if hint is not True or other is None:
            continue
        hint_pairs.append(
            {
                "key": f"{part}/{dataset}/{noise}",
                "changed_hint": row.changes["changed"] if row.changes else None,
                "changed_no_hint": other.changes["changed"] if other.changes else None,
                "seconds_hint": row.launch_to_exit_seconds,
                "seconds_no_hint": other.launch_to_exit_seconds,
                "status_hint": row.status,
                "status_no_hint": other.status,
            }
        )
    order_pairs = []
    for (part, dataset, noise, hint), row in sorted(by_key.items(), key=lambda kv: str(kv[0])):
        after = by_key.get(("R2", dataset, noise, hint))
        if part != "R1" or after is None:
            continue
        order_pairs.append(
            {
                "key": f"{dataset}/{noise}/hint{int(bool(hint))}",
                "changed_before": row.changes["changed"] if row.changes else None,
                "changed_after": after.changes["changed"] if after.changes else None,
                "score_before": row.score,
                "score_after": after.score,
            }
        )
    return {
        "schema_version": "3c-1.0",
        "parts": parts,
        "cells": cells,
        "hint_pairs": hint_pairs,
        "order_pairs": order_pairs,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Phase 3C repair benchmark summary",
        "",
        "n = 1 per cell: no P95, no SLA. Timing is conditional on success (P MET); watchdog and",
        "resource stops are censored. Q stays REVIEW_REQUIRED.",
        "",
        "| Part | Runs | H | P | Status |",
        "|---|---:|---|---|---|",
    ]
    for part, data in summary["parts"].items():
        lines.append(
            f"| {part} | {data['terminal']} | {data['H']} | {data['P']} | {data['status']} |"
        )
    lines += [
        "",
        "| Cell | Runs | Status | Seconds (min/median/max, MET only) | Censored | Changed "
        "| Forced | Min proved |",
        "|---|---:|---|---|---:|---|---|---:|",
    ]
    for key, cell in summary["cells"].items():
        t = cell["launch_to_exit_seconds"]
        seconds = "—" if not t["n"] else f"{t['min']:.1f} / {t['median']:.1f} / {t['max']:.1f}"
        lines.append(
            f"| {key} | {cell['runs']} | {cell['status']} | {seconds} | {cell['censored']} | "
            f"{cell['changed']} | {cell['forced']} | {cell['min_changes_proved']} |"
        )
    return "\n".join(lines) + "\n"


def collect(campaign: Path, preflight: Path) -> list[Row]:
    """Rows from verified receipts of every finished stage."""
    from benchmarks import run_benchmarks as v1
    from benchmarks import run_phase3c as r3

    plan_path = campaign.absolute() / "plan.json"
    plan = r3.Plan3C.model_validate(v1._json_object(plan_path.read_text()))
    digest = r3.check_identity(plan, plan_path, preflight)
    stages: list[tuple[str, tuple[Any, ...], str]] = [
        ("S", tuple(c for c in plan.cases if c.stage == "S"), digest),
        ("X", tuple(c for c in plan.cases if c.stage == "X"), digest),
    ]
    if (campaign / "derived.json").exists():
        derived, derived_digest = r3.check_derived(campaign.absolute(), digest)
        stages.append(("R", derived.cases, derived_digest))
    rows: list[Row] = []
    for stage, cases, stage_digest in stages:
        terminal = r3.read_terminals(campaign.absolute(), stage, stage_digest, cases)  # type: ignore[arg-type]
        for case in cases:
            if case.run_id not in terminal:
                continue
            record, verdict = terminal[case.run_id]
            rows.append(
                Row(
                    run_id=case.run_id,
                    part=case.part,
                    dataset_id=case.dataset_id,
                    class_count=case.class_count,
                    profile=case.profile,
                    variant=case.variant,
                    noise=case.noise,
                    order=case.order,
                    hint=case.hint,
                    granularity=case.granularity,
                    label=case.label,
                    harness_status=record.harness_status,
                    launch_to_exit_seconds=record.execution.launch_to_exit_seconds,
                    peak_resident_bytes=record.execution.peak_resident_bytes,
                    hard=verdict.hard,
                    performance=verdict.performance,
                    status=verdict.status,
                    score=list(verdict.score) if verdict.score is not None else None,
                    changes=verdict.changes,
                    explain=verdict.explain,
                )
            )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--preflight-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        summary = summarize(collect(args.campaign, args.preflight_dir))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 2
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (args.output / "summary.md").write_text(render_markdown(summary))
    print(
        json.dumps(
            {
                "status": "SUMMARIZED",
                "parts": {k: v["terminal"] for k, v in summary["parts"].items()},
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
