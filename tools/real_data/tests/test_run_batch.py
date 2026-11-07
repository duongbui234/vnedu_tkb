"""Packing of parallel compare jobs into the thread budget (no solver)."""

import json
from pathlib import Path

from tools.real_data import run_batch as rb


def _jobs() -> list[rb.Job]:
    return rb.order(
        [
            rb.Job("s1", 2, 10),
            rb.Job("s2", 8, 30),
            rb.Job("s3", 8, 50),
            rb.Job("s1", 4, 10),
            rb.Job("s1", 8, 10),
        ]
    )


def test_order_largest_workers_then_size() -> None:
    assert [(j.school, j.workers) for j in _jobs()] == [
        ("s3", 8),
        ("s2", 8),
        ("s1", 8),
        ("s1", 4),
        ("s1", 2),
    ]


def test_next_jobs_fill_budget_and_skip_ahead() -> None:
    jobs = _jobs()
    first = rb.next_jobs(jobs, 0, 20)
    assert [(j.school, j.workers) for j in first] == [("s3", 8), ("s2", 8), ("s1", 4)]
    # With 16 threads busy, only jobs of at most 4 workers fit.
    assert [(j.school, j.workers) for j in rb.next_jobs(jobs, 16, 20)] == [("s1", 4)]
    assert rb.next_jobs(jobs, 20, 20) == []


def test_oversized_job_runs_alone() -> None:
    big = [rb.Job("x", 32, 1)]
    assert rb.next_jobs(big, 0, 20) == big
    assert rb.next_jobs(big, 2, 20) == []


def test_discover_skips_done_outputs(tmp_path: Path) -> None:
    for school, classes in (("a", 12), ("b", 40)):
        conv = tmp_path / school / "conv"
        conv.mkdir(parents=True)
        report = {"counts": {"classes": classes}}
        (conv / "conversion-report.json").write_text(json.dumps(report))
    (tmp_path / "a" / "cmp-w2").mkdir()
    jobs = rb.discover([tmp_path], [2, 4])
    assert [(j.school, j.workers) for j in jobs] == [("b", 4), ("a", 4), ("b", 2)]
    other = tmp_path / "second"
    (other / "c" / "conv").mkdir(parents=True)
    (other / "c" / "conv" / "conversion-report.json").write_text(
        json.dumps({"counts": {"classes": 20}})
    )
    both = rb.discover([tmp_path, other], [2])
    # Larger school first across roots: b (40 classes) before c (20).
    assert [(j.root, j.school) for j in both] == [(tmp_path, "b"), (other, "c")]
