"""Historical aggregation uses saved evidence; these tests never search a schedule."""

import copy
from pathlib import Path

import pytest

from benchmarks import aggregate_linux as aggregate


def row(ident: str = "r1", fp: str = "a", **changes: object) -> dict:
    value = {
        "run_id": ident,
        "dataset_id": "dataset-" + fp,
        "input_fingerprint": fp,
        "class_count": 10,
        "profile": "BASE",
        "harness_status": "COMPLETE",
        "solver_status": "FEASIBLE",
        "valid_schedule": True,
        "correctness": "PASS",
        "performance": "MET",
        "quality": "EQUAL",
        "qualified": True,
        "failure_causes": [],
        "score": [0, 0, 0],
        "baseline_score": [0, 0, 0],
        "optimal_prefix": [],
        "quality_status": "SCORED_FEASIBLE",
        "metrics": {"launch_to_exit_seconds": 2.0, "peak_resident_bytes": 1024},
    }
    value.update(changes)
    return value


def test_mixed_outcomes_keep_denominator_nulls_and_no_invalid_vectors() -> None:
    rows = [row()]
    for ident, harness, solver in (
        ("unknown", "COMPLETE", "UNKNOWN"),
        ("crash", "CRASH", None),
        ("measurement", "MEASUREMENT_BLOCKED", None),
    ):
        rows.append(
            row(
                ident,
                harness_status=harness,
                solver_status=solver,
                valid_schedule=False,
                correctness="NOT_ASSESSED",
                performance="NOT_ASSESSED",
                quality="NO_SCHEDULE",
                qualified=False,
                failure_causes=[harness],
                score=None,
                metrics={"launch_to_exit_seconds": None, "peak_resident_bytes": None},
            )
        )
    before = copy.deepcopy(rows)
    summary = aggregate.summarize(rows)
    assert rows == before
    assert summary["total"] == 4 and summary["not_qualified"] == 3
    assert summary["valid_schedules"] == 1
    assert summary["solver_status"] == {"FEASIBLE": 1, "UNKNOWN": 1, "UNAVAILABLE": 2}
    stats = summary["datasets"][0]["metrics"]["launch_to_exit_seconds"]
    assert stats == {"n": 1, "missing": 3, "min": 2.0, "median": 2.0, "max": 2.0}
    assert summary["performance_verdict"] == "NOT_ASSESSED"
    assert summary["correctness_verdict"] == "INCOMPLETE"


def test_distinct_fingerprints_never_share_metric_or_score_statistics() -> None:
    result = aggregate.summarize(
        [
            row(),
            row("r2", metrics={"launch_to_exit_seconds": 4.0}),
            row("r3", "b", metrics={"launch_to_exit_seconds": 1000.0}),
        ]
    )
    assert "metrics" not in result
    assert "metrics" not in result["profiles"][0]
    assert len(result["datasets"]) == 2
    assert result["datasets"][0]["metrics"]["launch_to_exit_seconds"]["median"] == 3.0
    assert result["datasets"][1]["metrics"]["launch_to_exit_seconds"]["median"] == 1000.0
    assert "score_mean" not in str(result)


def test_fail_blocks_correctness_and_unknown_is_not_infeasible() -> None:
    result = aggregate.summarize(
        [
            row(correctness="FAIL", qualified=False),
            row(
                "unknown",
                solver_status="UNKNOWN",
                valid_schedule=False,
                score=None,
                correctness="NOT_ASSESSED",
                performance="NOT_MET",
                qualified=False,
                quality="NO_SCHEDULE",
            ),
        ]
    )
    assert result["correctness_verdict"] == "FAIL"
    assert result["performance_verdict"] == "NOT_MET"
    assert result["solver_status"].get("INFEASIBLE", 0) == 0


def test_unsat_excluded_from_feasible_gate_and_all_missing_stays_null() -> None:
    r = row(
        profile="UNSAT_CAPACITY",
        solver_status="INFEASIBLE",
        valid_schedule=False,
        score=None,
        baseline_score=None,
        quality="NOT_APPLICABLE",
        performance="NOT_APPLICABLE",
        metrics={"launch_to_exit_seconds": None},
    )
    result = aggregate.summarize([r])
    assert result["known_feasible"] == 0
    assert result["performance_verdict"] == "NOT_APPLICABLE"
    assert result["datasets"][0]["metrics"]["launch_to_exit_seconds"] == {
        "n": 0,
        "missing": 1,
        "min": None,
        "median": None,
        "max": None,
    }


def test_failure_causes_are_nonexclusive_counts_not_fake_failures() -> None:
    result = aggregate.summarize(
        [
            row(
                qualified=False,
                performance="NOT_MET",
                quality="WORSE",
                failure_causes=["ZERO_TARGET_NOT_MET", "MEMORY_TARGET_EXCEEDED"],
            ),
            row(
                "r2",
                valid_schedule=False,
                score=None,
                qualified=False,
                performance="NOT_MET",
                quality="NO_SCHEDULE",
                correctness="NOT_ASSESSED",
                failure_causes=["NO_SCHEDULE"],
            ),
        ]
    )
    assert result["not_qualified"] == 2
    assert result["failure_causes"] == {
        "ZERO_TARGET_NOT_MET": 1,
        "MEMORY_TARGET_EXCEEDED": 1,
        "NO_SCHEDULE": 1,
    }


def test_duplicate_rows_or_unverified_score_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate.summarize([row(), row()])
    with pytest.raises(ValueError, match="score"):
        aggregate.summarize([row(valid_schedule=False)])


def test_cli_writes_nothing_on_integrity_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    output = tmp_path / "summary.json"
    assert aggregate.main([str(tmp_path / "missing"), "--output", str(output)]) == 2
    assert not output.exists()
    assert capsys.readouterr().err


# Reuse typed metadata/execution boundaries; no real solver or supervisor is invoked.
from benchmarks.tests.test_campaign_linux import (  # noqa: E402
    campaign,  # noqa: F401,F811
    ready,
    run_phase,
    unit_bundle,  # noqa: F401
)


@pytest.fixture
def completed_campaign(campaign, monkeypatch: pytest.MonkeyPatch):  # noqa: F811
    path, _, plan, _, _ = campaign
    fake_run = aggregate.runner.run_cli_once

    def recorded(**kwargs):
        record = fake_run(**kwargs)
        record.identity.update(plan.runtime_identity)
        record.identity["options"] = kwargs["options"].model_dump(mode="json")
        record.identity["limits"] = kwargs["limits"].model_dump(mode="json")
        (kwargs["run_dir"] / "run.json").write_text(record.model_dump_json())
        return record

    monkeypatch.setattr(aggregate.runner, "run_cli_once", recorded)
    ready(campaign)
    assert run_phase(campaign, "primary").status == "COMPLETE"

    def saved_output(input_path, result_path, execution):
        return aggregate.runner.RunRecord.model_validate_json(
            (result_path.parent / "run.json").read_text()
        ).output

    monkeypatch.setattr(aggregate.runner, "verify_cli_output", saved_output)
    # Any accidental scheduling during aggregation is a test failure.
    monkeypatch.setattr(aggregate.runner, "run_cli_once", lambda **kw: pytest.fail("search"))
    monkeypatch.setattr(aggregate.runner, "_machine_identity", lambda: pytest.fail("live gate"))
    return path.parent, plan


def test_full_saved_campaign_integrity_and_setup_exclusion(completed_campaign) -> None:
    root, _ = completed_campaign
    before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = aggregate.aggregate_campaign(root)
    assert result["receipts_verified"] == 110
    assert result["summary"]["total"] == 108
    assert result["summary"]["known_feasible"] == 81
    assert result["summary"]["performance_verdict"] == "MET"
    assert len(result["summary"]["datasets"]) == 36
    assert len(result["summary"]["profiles"]) == 12
    assert all(d["total"] == 3 for d in result["summary"]["datasets"])
    assert all(r["repeat"] in (1, 2, 3) for r in result["rows"])
    assert before == {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert result["windows_status"] == "BLOCKED"


@pytest.mark.parametrize(
    "target",
    [
        "plan.json",
        "environment.json",
        "preflight",
        "input",
        "witness",
        "manifest",
        "run.json",
        "result.json",
        "terminal.json",
        "journal.jsonl",
        "state",
        "missing",
    ],
)
def test_corruption_or_missing_rows_blocks_report(completed_campaign, target) -> None:
    import json

    root, plan = completed_campaign
    case = plan.primary[0]
    if target == "preflight":
        path = plan.preflight_dir / "preflight-manifest.json"
    elif target in ("input", "witness", "manifest"):
        path = (
            case.input_path.parent
            / {"input": "input.json", "witness": "witness.json", "manifest": "manifest.json"}[
                target
            ]
        )
    elif target in ("run.json", "result.json", "terminal.json", "missing"):
        path = root / "primary" / case.run_id / ("run.json" if target == "missing" else target)
    elif target == "state":
        path = root / "campaign-state.json"
    else:
        path = root / target
    if target == "missing":
        path.unlink()
    elif target == "state":
        data = json.loads(path.read_text())
        data["failed"] += 1
        path.write_text(json.dumps(data))
    else:
        path.write_text("{}")
    with pytest.raises((OSError, ValueError, KeyError)):
        aggregate.aggregate_campaign(root)


def test_independent_recheck_mismatch_is_not_accepted(completed_campaign, monkeypatch) -> None:
    root, _ = completed_campaign
    monkeypatch.setattr(
        aggregate.runner,
        "verify_cli_output",
        lambda *a: aggregate.runner.OutputVerification(status="INVALID"),
    )
    with pytest.raises(ValueError, match="INDEPENDENT_OUTPUT_MISMATCH"):
        aggregate.aggregate_campaign(root)


def test_cli_output_is_exclusive_and_outside_frozen_paths(completed_campaign, tmp_path) -> None:
    root, plan = completed_campaign
    for directory in (root, plan.bundle_dir, plan.preflight_dir):
        assert aggregate.main([str(root), "--output", str(directory / "new.json")]) == 2
        assert not (directory / "new.json").exists()
    output = tmp_path / "summary.json"
    assert aggregate.main([str(root), "--output", str(output)]) == 0
    raw = output.read_bytes()
    assert aggregate.main([str(root), "--output", str(output)]) == 2
    assert output.read_bytes() == raw


def test_interrupted_record_without_result_keeps_null_score(completed_campaign):
    root, plan = completed_campaign
    case = next(c for c in plan.primary if c.profile == "BASE")
    base = root / "primary" / case.run_id
    record = aggregate.runner.RunRecord.model_validate_json((base / "run.json").read_text())
    record = record.model_copy(
        update={
            "harness_status": "CRASH",
            "valid_schedule": False,
            "output": aggregate.runner.OutputVerification(),
        }
    )
    verdict = aggregate.runner.CaseVerdict(run_sha256="0" * 64)
    result = aggregate._row(case, record, verdict, None)
    assert result["score"] is None and result["quality_status"] is None
    assert result["metrics"]["core_wall_seconds"] is None
    assert result["tier_runs"] == []
