"""Let Core schedule the same converted input and compare it with the real schedule (plan §6).

Core runs through its public CLI in a fresh process (seed 42; 1 worker and a budget by school size
as in the benchmarks unless ``--workers``/``--time-limit`` are given). ``--warm-start`` starts Core
from the real schedule through ``warm_start.py`` (diagnostic). Core's schedule is then re-checked
with the independent checker and evaluator, exactly like the real one. Run once per school (n = 1).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tkb_core.contracts.output import ScheduleResult
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score
from tools.real_data import score_real

BUDGETS = ((10, 60.0), (20, 120.0))
LARGEST = 180.0


def budget_for(classes: int) -> float:
    return next((seconds for limit, seconds in BUDGETS if classes <= limit), LARGEST)


def run_core(
    input_path: Path,
    result_path: Path,
    seconds: float,
    workers: int = 1,
    warm_start: Path | None = None,
) -> dict[str, Any]:
    entry = ["tools.real_data.warm_start", str(warm_start)] if warm_start else ["tkb_core.cli"]
    argv = [
        sys.executable,
        "-m",
        *entry,
        "solve",
        str(input_path),
        "--output",
        str(result_path),
        "--time-limit",
        str(seconds),
        "--workers",
        str(workers),
        "--seed",
        "42",
    ]
    started = time.monotonic()
    proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    _, status, usage = os.wait4(proc.pid, 0)
    assert proc.stderr is not None
    return {
        "exit": os.waitstatus_to_exitcode(status),
        "wall_seconds": round(time.monotonic() - started, 2),
        "peak_rss_mib": round(usage.ru_maxrss / 1024, 1),
        "time_limit": seconds,
        "workers": workers,
        "warm_start": warm_start is not None,
        "stderr": proc.stderr.read().decode(errors="replace")[-2000:],
    }


def _better(real: int, core: int) -> str:
    return "EQUAL" if real == core else ("CORE" if core < real else "REAL")


def compare(
    converted: Path,
    output: Path,
    seconds: float | None,
    workers: int = 1,
    warm_start: bool = False,
) -> dict[str, Any]:
    input_path = converted / "input.json"
    problem, real_assignments = score_real.load(input_path, converted / "real-assignments.json")
    real = score_real.score_files(input_path, converted / "real-assignments.json")
    seconds = seconds if seconds is not None else budget_for(len(problem.classes))
    warm = converted / "real-assignments.json" if warm_start else None
    run = run_core(input_path, output / "core-result.json", seconds, workers, warm)
    core: dict[str, Any] = {"run": run, "status": None, "hard_valid": None, "tiers": None}
    if (output / "core-result.json").exists():
        result = ScheduleResult.model_validate_json((output / "core-result.json").read_text())
        core["status"] = str(result.status)
        if result.assignments:
            hard = validate_schedule(problem, result.assignments)
            score = evaluate_score(problem, result.assignments) if hard.valid else None
            core |= score_real.summarize(problem, hard, score)
            core["status"] = str(result.status)
            claimed = (
                result.quality.score.tiers if result.quality and result.quality.score else None
            )
            core["independent_score_matches"] = (
                score is not None and score.tiers is not None and claimed == score.tiers
            )
            core["optimal_prefix"] = list(result.quality.optimal_prefix) if result.quality else []
            core["tier_runs"] = (
                [t.model_dump(mode="json") for t in result.quality.tier_runs]
                if result.quality
                else []
            )
    codes = sorted(set(real["rules"]) | set(core.get("rules") or {}))
    by_rule = []
    for code in codes:
        r = real["rules"].get(code, {}).get("raw_penalty")
        c = (core.get("rules") or {}).get(code, {}).get("raw_penalty")
        by_rule.append(
            {
                "code": code,
                "real": r,
                "core": c,
                "better": None if r is None or c is None else _better(r, c),
            }
        )
    lexicographic = None
    if real["tiers"] is not None and core.get("tiers") is not None:
        rt, ct = tuple(real["tiers"]), tuple(core["tiers"])
        lexicographic = "EQUAL" if rt == ct else ("CORE_BETTER" if ct < rt else "REAL_BETTER")
    return {
        "school": problem.school.school_id,
        "real": real,
        "core": core,
        "by_rule": by_rule,
        "lexicographic": lexicographic,
        "note": "n = 1; measurement scale of plan §5, not a quality profile",
    }


def render(report: dict[str, Any]) -> str:
    real, core = report["real"], report["core"]
    lines = [
        f"# So sánh lịch thật và lịch Core — {report['school']}",
        "",
        f"- Quy mô: {real['counts']['classes']} lớp, {real['counts']['teachers']} GV, "
        f"{real['counts']['periods']} tiết.",
        f"- Lịch thật: hard hợp lệ = {real['hard_valid']}, vector {real['tiers']}.",
        f"- Lịch Core: status {core['status']}, hard hợp lệ = {core['hard_valid']}, vector "
        f"{core['tiers']}, {core['run']['wall_seconds']} s, RSS {core['run']['peak_rss_mib']} MiB, "
        f"{core['run']['workers']} worker"
        f"{', warm start' if core['run']['warm_start'] else ''}.",
        f"- So theo thứ tự từ điển: {report['lexicographic']}.",
        "",
        "| Rule | Lịch thật | Lịch Core | Tốt hơn |",
        "|---|---:|---:|---|",
    ]
    lines += [
        f"| {r['code']} | {r['real']} | {r['core']} | {r['better']} |" for r in report["by_rule"]
    ]
    lines += ["", f"_{report['note']}._", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("converted", type=Path, help="directory written by convert_real.py")
    parser.add_argument("--output", type=Path, required=True, help="new directory for the results")
    parser.add_argument("--time-limit", type=float, help="seconds; default by school size")
    parser.add_argument("--workers", type=int, default=1, help="CP-SAT workers (default 1)")
    parser.add_argument(
        "--warm-start", action="store_true", help="start Core from the real schedule"
    )
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output {args.output} already exists; nothing is overwritten")
    args.output.mkdir(parents=True)
    report = compare(args.converted, args.output, args.time_limit, args.workers, args.warm_start)
    with (args.output / "comparison.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)
    (args.output / "comparison.md").write_text(render(report), encoding="utf-8")
    print(render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
