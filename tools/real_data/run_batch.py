"""Run compare_real for many schools and worker counts in parallel, filling the CPU (AGENTS.md).

    python -m tools.real_data.run_batch <root> [<root> ...] --workers 2,4,8 --time-limit 180

Every ``<root>/<school>/conv`` directory of every root is compared once per worker count into
``<root>/<school>/cmp-w<N>``; one scheduler serves all roots. A job starts while the workers of
running jobs plus its own fit the thread budget (default ``os.cpu_count()``); larger jobs start
first. Each job has a watchdog (time limit + grace) and is never retried. ``layout.jsonl`` (in
the first root) records every start and end with the threads in use, so a report can state the
contention each run saw.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Job:
    school: str
    workers: int
    size: int  # classes; larger first within a worker count
    root: Path = Path(".")

    @property
    def name(self) -> str:
        return f"cmp-w{self.workers}"


def order(jobs: list[Job]) -> list[Job]:
    return sorted(jobs, key=lambda j: (-j.workers, -j.size, j.school, str(j.root)))


def next_jobs(pending: list[Job], running_threads: int, budget: int) -> list[Job]:
    """Jobs to start now, in order; a job larger than the budget runs alone."""
    chosen: list[Job] = []
    used = running_threads
    for job in pending:
        if used + job.workers <= budget or (used == 0 and not chosen):
            chosen.append(job)
            used += job.workers
    return chosen


def discover(roots: list[Path], worker_counts: list[int]) -> list[Job]:
    jobs = []
    for root in roots:
        for conv in sorted(root.glob("*/conv")):
            report = json.loads((conv / "conversion-report.json").read_text(encoding="utf-8"))
            for w in worker_counts:
                if not (conv.parent / f"cmp-w{w}").exists():
                    jobs.append(Job(conv.parent.name, w, int(report["counts"]["classes"]), root))
    return order(jobs)


def run(
    log_root: Path, jobs: list[Job], seconds: float, budget: int, grace: float
) -> list[dict[str, Any]]:
    layout = (log_root / "layout.jsonl").open("a", encoding="utf-8")

    def log(event: dict[str, Any]) -> None:
        layout.write(json.dumps(event, ensure_ascii=False) + "\n")
        layout.flush()

    pending = list(jobs)
    running: dict[Job, tuple[subprocess.Popen[bytes], float]] = {}
    results = []
    log(
        {
            "event": "batch",
            "jobs": len(jobs),
            "budget": budget,
            "cpu_count": os.cpu_count(),
            "time_limit": seconds,
            "time": time.time(),
        }
    )
    while pending or running:
        threads = sum(j.workers for j in running)
        for job in next_jobs(pending, threads, budget):
            pending.remove(job)
            folder = job.root / job.school
            argv = [
                sys.executable,
                "-m",
                "tools.real_data.compare_real",
                str(folder / "conv"),
                "--output",
                str(folder / job.name),
                "--time-limit",
                str(seconds),
                "--workers",
                str(job.workers),
            ]
            with (folder / f"{job.name}.log").open("w", encoding="utf-8") as out:
                proc = subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT)
            running[job] = (proc, time.time())
            threads += job.workers
            log(
                {
                    "event": "start",
                    "root": str(job.root),
                    "school": job.school,
                    "workers": job.workers,
                    "threads_in_use": threads,
                    "time": time.time(),
                }
            )
        time.sleep(1.0)
        for job, (proc, started) in list(running.items()):
            code = proc.poll()
            if code is None and time.time() - started > seconds + grace:
                proc.kill()
                code = proc.wait()
                log(
                    {
                        "event": "watchdog",
                        "root": str(job.root),
                        "school": job.school,
                        "workers": job.workers,
                    }
                )
            if code is not None:
                del running[job]
                elapsed = round(time.time() - started, 1)
                results.append(
                    {
                        "root": str(job.root),
                        "school": job.school,
                        "workers": job.workers,
                        "exit": code,
                        "elapsed": elapsed,
                    }
                )
                log(
                    {
                        "event": "end",
                        "root": str(job.root),
                        "school": job.school,
                        "workers": job.workers,
                        "exit": code,
                        "elapsed": elapsed,
                        "threads_in_use": sum(j.workers for j in running),
                        "time": time.time(),
                    }
                )
    layout.close()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("roots", type=Path, nargs="+", help="directories of <school>/conv")
    parser.add_argument("--workers", default="2,4,8", help="worker counts, e.g. 2,4,8")
    parser.add_argument("--time-limit", type=float, required=True)
    parser.add_argument("--budget", type=int, default=os.cpu_count() or 1, help="threads")
    parser.add_argument("--grace", type=float, default=300.0, help="watchdog grace seconds")
    args = parser.parse_args(argv)
    jobs = discover(args.roots, [int(w) for w in args.workers.split(",")])
    results = run(args.roots[0], jobs, args.time_limit, args.budget, args.grace)
    failed = [r for r in results if r["exit"] != 0]
    print(f"{len(results)} jobs, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
