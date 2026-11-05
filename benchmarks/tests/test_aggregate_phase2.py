"""v2 aggregation: full denominators, null-safe statistics, separate H/P/Q/zero."""

from pathlib import Path
from typing import Any

import pytest

from benchmarks import aggregate_phase2 as agg
from benchmarks import generate_phase2 as g2
from benchmarks import run_benchmarks as v1
from benchmarks import run_phase2 as r2


def _case(profile: str = "BASE", seed: int = 101, repeat: int = 1, variant: str = "SOFT"):
    budget = r2.BUDGETS[10]
    ident = g2.dataset_id(10, profile, seed, variant)
    sha = f"{seed:02x}".ljust(64, "a")
    return r2.PlannedCase(
        run_id=f"primary-{ident}-{sha}-w1-s42-r{repeat}",
        dataset_id=ident,
        phase="primary",
        repeat=repeat,
        class_count=10,
        profile=profile,
        variant=variant,
        generator_seed=seed,
        input_path=Path("/x/input.json"),
        dataset_manifest=Path("/x/manifest.json"),
        manifest_sha256=sha,
        input_sha256=sha,
        input_fingerprint=sha,
        ground_truth="INFEASIBLE" if profile == "UNSAT_CAPACITY" else "FEASIBLE",
        options=r2.SolveOptions(time_limit_seconds=budget[0]),
        limits=v1.RunLimits(watchdog_seconds=budget[1], max_resident_bytes=budget[2]),
    )


def _record(
    *,
    seconds: float | None = 10.0,
    rss: int = 1000,
    schedule: bool = True,
    status: str = "COMPLETE",
) -> v1.RunRecord:
    fields: dict[str, Any] = dict(
        argv=("python",),
        run_dir=Path("/x"),
        stdout_path=Path("/x/stdout.json"),
        stderr_path=Path("/x/stderr.txt"),
        pid=1,
        exit_code=0,
    )
    if seconds is None:
        fields.update(measurement_status="BLOCKED", measurement_reason="PROBE")
    else:
        fields.update(
            raw_wait_status=0,
            cpu_seconds=1.0,
            native_peak_rss_kib=rss,
            peak_resident_bytes=rss * 1024,
            launch_to_exit_seconds=seconds,
            measurement_status="OK",
            measurement_reason=None,
        )
    output = (
        v1.OutputVerification(
            status="VALID_SCHEDULE", valid_schedule=True, solver_status="FEASIBLE"
        )
        if schedule
        else v1.OutputVerification(status="VALID_CORE_ERROR", solver_status="UNKNOWN")
    )
    return v1.RunRecord(
        harness_status=status,
        execution=v1.ExecutionRecord(**fields),
        output=output,
        identity={},
        valid_schedule=schedule and status == "COMPLETE",
    )


def _verdict(**update: Any) -> r2.CaseVerdict:
    base: dict[str, Any] = dict(
        hard="PASS",
        quality="REVIEW_REQUIRED",
        witness_comparison="WORSE",
        performance="MET",
        run_sha256="c" * 64,
    )
    return r2.CaseVerdict(**(base | update))


def _unsat_verdict() -> r2.CaseVerdict:
    return r2.CaseVerdict(
        hard="PASS", quality="NOT_APPLICABLE", performance="NOT_APPLICABLE", run_sha256="c" * 64
    )


def _met_rows() -> list[agg.Row]:
    return [
        agg.Row(_case(repeat=1), _record(seconds=10.0), _verdict()),
        agg.Row(_case(repeat=2), _record(seconds=30.0), _verdict()),
        agg.Row(_case(repeat=3), _record(seconds=20.0), _verdict()),
        agg.Row(_case("UNSAT_CAPACITY"), _record(schedule=False, seconds=1.0), _unsat_verdict()),
    ]


def test_all_met_keeps_q_review_and_zero_separate() -> None:
    summary = agg.summarize(_met_rows())
    assert summary["campaign"] == {
        "planned": 4,
        "terminal": 4,
        "missing": 0,
        "H": "PASS",
        "P": "MET",
        "Q": "REVIEW_REQUIRED",
        "zero": {"MET": 0, "NOT_MET": 0, "NOT_APPLICABLE": 4},
    }
    group = summary["groups"]["SOFT/c10/BASE/c10-base-s101-soft"]
    assert group["launch_to_exit_seconds"] == {
        "n": 3,
        "min": 10.0,
        "median": 20.0,
        "max": 30.0,
        "conditional_on_success": True,
    }
    assert group["witness_comparison"] == {"BETTER": 0, "EQUAL": 0, "WORSE": 3}


def test_missing_run_keeps_the_denominator() -> None:
    rows = _met_rows()
    rows[1] = agg.Row(rows[1].case, None, None)
    campaign = agg.summarize(rows)["campaign"]
    assert (campaign["planned"], campaign["terminal"], campaign["missing"]) == (4, 3, 1)
    assert campaign["P"] == "INCOMPLETE" and campaign["H"] == "INCOMPLETE"


def test_not_met_and_hard_fail() -> None:
    rows = _met_rows()
    rows[0] = agg.Row(rows[0].case, rows[0].record, _verdict(performance="NOT_MET"))
    assert agg.summarize(rows)["campaign"]["P"] == "NOT_MET"
    rows[2] = agg.Row(rows[2].case, rows[2].record, _verdict(hard="FAIL"))
    assert agg.summarize(rows)["campaign"]["H"] == "FAIL"


def test_unsat_hard_fail_blocks_p() -> None:
    rows = _met_rows()
    rows[3] = agg.Row(
        rows[3].case, rows[3].record, _unsat_verdict().model_copy(update={"hard": "FAIL"})
    )
    campaign = agg.summarize(rows)["campaign"]
    assert campaign["H"] == "FAIL" and campaign["P"] == "NOT_MET"


def test_null_measurements_and_censored_timeouts() -> None:
    rows = _met_rows()
    rows[0] = agg.Row(
        rows[0].case,
        _record(seconds=None, schedule=False, status="MEASUREMENT_BLOCKED"),
        _verdict(
            hard="NOT_APPLICABLE",
            quality="NO_SCHEDULE",
            witness_comparison=None,
            performance="INCOMPLETE",
        ),
    )
    rows[1] = agg.Row(
        rows[1].case,
        _record(seconds=150.5, schedule=False, status="WATCHDOG_TIMEOUT"),
        _verdict(
            hard="NOT_APPLICABLE",
            quality="NO_SCHEDULE",
            witness_comparison=None,
            performance="NOT_MET",
        ),
    )
    group = agg.summarize(rows)["groups"]["SOFT/c10/BASE/c10-base-s101-soft"]
    assert group["launch_to_exit_seconds"]["n"] == 1
    assert group["launch_to_exit_seconds"]["median"] == 20.0
    assert group["censored_without_schedule"] == 1
    assert group["measurement_missing"] == 1
    assert group["peak_resident_bytes"]["n"] == 2


def test_groups_never_mix_datasets() -> None:
    rows = [
        agg.Row(_case(seed=101), _record(), _verdict()),
        agg.Row(_case(seed=102), _record(), _verdict()),
        agg.Row(_case(seed=101, variant="HARD"), _record(), _verdict()),
    ]
    assert len(agg.summarize(rows)["groups"]) == 3


def test_markdown_states_limits() -> None:
    text = agg.render_markdown(agg.summarize(_met_rows()))
    assert "conditional on success" in text and "P95" in text
    assert "REVIEW_REQUIRED" in text


def test_aggregate_refuses_output_inside_campaign(tmp_path: Path) -> None:
    (tmp_path / "plan.json").write_text("{}")
    with pytest.raises(ValueError, match="OUTPUT_WOULD_MODIFY_FROZEN_EVIDENCE"):
        agg.aggregate(tmp_path, tmp_path / "preflight", tmp_path / "summary")
