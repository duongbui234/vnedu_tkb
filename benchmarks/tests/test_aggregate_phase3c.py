"""Phase 3C aggregation: per-cell tables, paired hint/order comparisons, censoring (Task 4)."""

from typing import Any

from benchmarks import aggregate_phase3c as a3


def _row(**update: Any) -> a3.Row:
    data: dict[str, Any] = dict(
        run_id="R1-c10-base-s101-soft-N1-hint1",
        part="R1",
        dataset_id="c10-base-s101-soft",
        class_count=10,
        profile="BASE",
        variant="SOFT",
        noise="N1",
        order="BEFORE_QUALITY",
        hint=True,
        granularity=None,
        label="GROUND_TRUTH_UNKNOWN",
        harness_status="COMPLETE",
        launch_to_exit_seconds=61.0,
        peak_resident_bytes=400 * 1024**2,
        hard="PASS",
        performance="MET",
        status="FEASIBLE",
        score=[0, 3, 40],
        changes={"changed": 5, "forced": 3, "min_changes_proved": True},
        explain=None,
    )
    data.update(update)
    return a3.Row(**data)


def test_counts_and_censoring() -> None:
    rows = [
        _row(),
        _row(
            run_id="b",
            hint=False,
            performance="NOT_MET",
            harness_status="WATCHDOG_TIMEOUT",
            launch_to_exit_seconds=150.2,
            hard="NOT_APPLICABLE",
            status=None,
            changes=None,
        ),
        _row(
            run_id="c",
            noise="N2",
            status="INFEASIBLE",
            hard="NOT_APPLICABLE",
            performance="NOT_APPLICABLE",
            changes=None,
            launch_to_exit_seconds=None,
        ),
    ]
    summary = a3.summarize(rows)
    part = summary["parts"]["R1"]
    assert part["planned"] == part["terminal"] == 3
    assert part["H"] == {"PASS": 1, "NOT_APPLICABLE": 2}
    assert part["P"] == {"MET": 1, "NOT_MET": 1, "NOT_APPLICABLE": 1}
    cell = summary["cells"]["R1/10/BASE/SOFT/N1"]
    # Timing is conditional on success: the watchdog run is censored, never a time.
    assert cell["launch_to_exit_seconds"] == {"n": 1, "min": 61.0, "median": 61.0, "max": 61.0}
    assert cell["censored"] == 1 and cell["changed"] == [5] and cell["forced"] == [3]
    assert summary["cells"]["R1/10/BASE/SOFT/N2"]["status"] == {"INFEASIBLE": 1}


def test_paired_hint_and_order_comparisons() -> None:
    rows = [
        _row(),
        _row(
            run_id="R1-...-hint0",
            hint=False,
            changes={"changed": 7, "forced": 3, "min_changes_proved": False},
            launch_to_exit_seconds=62.0,
        ),
        _row(
            run_id="R2-...-hint1",
            part="R2",
            order="AFTER_QUALITY",
            changes={"changed": 9, "forced": 3, "min_changes_proved": False},
            score=[0, 1, 30],
        ),
    ]
    summary = a3.summarize(rows)
    assert summary["hint_pairs"] == [
        {
            "key": "R1/c10-base-s101-soft/N1",
            "changed_hint": 5,
            "changed_no_hint": 7,
            "seconds_hint": 61.0,
            "seconds_no_hint": 62.0,
            "status_hint": "FEASIBLE",
            "status_no_hint": "FEASIBLE",
        }
    ]
    assert summary["order_pairs"] == [
        {
            "key": "c10-base-s101-soft/N1/hint1",
            "changed_before": 5,
            "changed_after": 9,
            "score_before": [0, 3, 40],
            "score_after": [0, 1, 30],
        }
    ]


def test_markdown_states_limits() -> None:
    text = a3.render_markdown(a3.summarize([_row()]))
    assert "n = 1" in text and "P95" in text and "| R1/10/BASE/SOFT/N1 |" in text
