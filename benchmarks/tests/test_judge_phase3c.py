"""Phase 3C verdicts H/P/C/Q/X and stop gates (Task 3)."""

import json
from pathlib import Path
from typing import Any

import pytest

from benchmarks import judge_phase3c as j3
from benchmarks import run_benchmarks as v1
from tkb_core.contracts.diagnostics import ExplainOptions
from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.repair import PreviousSchedule, RepairRequest
from tkb_core.diagnostics.pipeline import explain_infeasibility
from tkb_core.repair.pipeline import repair
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions

LIMITS = v1.RunLimits(watchdog_seconds=150.0, max_resident_bytes=1024**3)


def _execution(base: Path, *, code: int = 0, seconds: float = 1.0, stop: str | None = None) -> Any:
    return v1.ExecutionRecord(
        argv=("python",),
        run_dir=base,
        stdout_path=base / "stdout.json",
        stderr_path=base / "stderr.txt",
        exit_code=code,
        stop_reason=stop,
        pid=4242,
        raw_wait_status=0,
        cpu_seconds=0.5,
        native_peak_rss_kib=1000,
        peak_resident_bytes=1000 * 1024,
        launch_to_exit_seconds=seconds,
        measurement_status="OK",
        measurement_reason=None,
    )


def _record(base: Path, output: v1.OutputVerification, **kwargs: Any) -> v1.RunRecord:
    execution = _execution(base, **kwargs)
    status = v1.classify_run(execution, output)
    return v1.RunRecord(
        harness_status=status,
        execution=execution,
        output=output,
        identity={},
        valid_schedule=status == "COMPLETE" and output.valid_schedule,
    )


def _case() -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "school": {"school_id": "s", "academic_year": "y", "term": "t"},
        "time_slots": [
            {"id": f"{d}-{s}-{p}", "day": d, "session": s, "period": p}
            for d in (1, 2)
            for s in ("AM", "PM")
            for p in range(1, 5)
        ],
        "classes": [{"id": "c"}],
        "teachers": [{"id": "t"}],
        "subjects": [{"id": "sub"}],
        "teaching_requirements": [
            {
                "id": "r",
                "class_ids": ["c"],
                "teacher_ids": ["t"],
                "subject_id": "sub",
                "periods_per_cycle": 4,
                "block_durations": [2, 1, 1],
            }
        ],
        "constraint_config": {"policy_version": "0.4", "hard": [], "soft": []},
    }


@pytest.fixture
def repaired(tmp_path: Path) -> Path:
    """The teacher loses the day of a previous lesson: at least one forced change."""
    data = _case()
    solved = solve(ScheduleInput.model_validate(data), SolveOptions(time_limit_seconds=5.0))
    previous = PreviousSchedule.from_result(solved)
    lost = int(previous.assignments[0].slot_id.split("-")[0])
    data["teachers"][0]["available_slot_ids"] = [
        s["id"] for s in data["time_slots"] if s["day"] != lost
    ]
    request = RepairRequest.model_validate(
        {
            "schema_version": "1.0",
            "change_order": "BEFORE_QUALITY",
            "max_changes": None,
            "change_scope": None,
            "use_previous_as_hint": True,
        }
    )
    result = repair(
        ScheduleInput.model_validate(data), previous, request, SolveOptions(time_limit_seconds=5.0)
    )
    base = tmp_path / "run"
    base.mkdir()
    (base / "result.json").write_text(result.model_dump_json())
    return base


def _valid() -> v1.OutputVerification:
    return v1.OutputVerification(
        status="VALID_SCHEDULE", solver_status="OPTIMAL", valid_schedule=True
    )


def test_repair_with_schedule_in_limits(repaired: Path) -> None:
    verdict = j3.judge_repair(_record(repaired, _valid()), repaired, "GROUND_TRUTH_UNKNOWN", LIMITS)
    assert (verdict.hard, verdict.performance, verdict.quality) == (
        "PASS",
        "MET",
        "REVIEW_REQUIRED",
    )
    assert verdict.changes is not None and verdict.changes["forced"] >= 1
    assert verdict.changes["changed"] >= verdict.changes["forced"]
    assert verdict.score is not None and len(verdict.score) == 3


def test_repair_over_watchdog_is_not_met(repaired: Path) -> None:
    record = _record(repaired, _valid(), seconds=151.0)
    verdict = j3.judge_repair(record, repaired, "GROUND_TRUTH_UNKNOWN", LIMITS)
    assert (verdict.hard, verdict.performance) == ("PASS", "NOT_MET")


def test_schedule_for_proved_infeasible_input_fails(repaired: Path) -> None:
    verdict = j3.judge_repair(_record(repaired, _valid()), repaired, "EXPECTED_INFEASIBLE", LIMITS)
    assert verdict.hard == "FAIL" and "SCHEDULE_FOR_PROVED_INFEASIBLE" in verdict.reasons
    assert j3.stop_status(_record(repaired, _valid()), verdict) == "STOPPED"


def test_infeasible_and_unknown_repairs(tmp_path: Path) -> None:
    data = _case()
    solved = solve(ScheduleInput.model_validate(data), SolveOptions(time_limit_seconds=5.0))
    previous = PreviousSchedule.from_result(solved)
    data["teachers"][0]["available_slot_ids"] = ["1-AM-1", "1-AM-2"]  # 2 slots, 4 periods
    request = RepairRequest.model_validate(
        {
            "schema_version": "1.0",
            "change_order": "BEFORE_QUALITY",
            "max_changes": None,
            "change_scope": None,
            "use_previous_as_hint": True,
        }
    )
    result = repair(
        ScheduleInput.model_validate(data), previous, request, SolveOptions(time_limit_seconds=5.0)
    )
    assert result.result.status == "INFEASIBLE"
    envelope = json.loads(result.model_dump_json())
    for status, code, performance in (
        ("INFEASIBLE", 3, "NOT_APPLICABLE"),
        ("UNKNOWN", 4, "NOT_MET"),
    ):
        envelope["result"]["status"] = status
        (tmp_path / "result.json").write_text(json.dumps(envelope))
        output = v1.OutputVerification(status="VALID_CORE_ERROR", solver_status=status)
        record = _record(tmp_path, output, code=code)
        verdict = j3.judge_repair(record, tmp_path, "GROUND_TRUTH_UNKNOWN", LIMITS)
        assert (verdict.hard, verdict.performance, verdict.quality) == (
            "NOT_APPLICABLE",
            performance,
            "NO_SCHEDULE",
        )
        assert verdict.status == status and j3.stop_status(record, verdict) is None


def test_watchdog_stop_is_not_met_and_continues(tmp_path: Path) -> None:
    record = _record(tmp_path, v1.OutputVerification(), stop="WATCHDOG", seconds=150.5)
    verdict = j3.judge_repair(record, tmp_path, "GROUND_TRUTH_UNKNOWN", LIMITS)
    assert record.harness_status == "WATCHDOG_TIMEOUT"
    assert (verdict.hard, verdict.performance) == ("NOT_APPLICABLE", "NOT_MET")
    assert j3.stop_status(record, verdict) is None


def test_invalid_output_stops(tmp_path: Path) -> None:
    record = _record(tmp_path, v1.OutputVerification(status="INVALID", diagnostics=("X",)))
    verdict = j3.judge_repair(record, tmp_path, "GROUND_TRUTH_UNKNOWN", LIMITS)
    assert record.harness_status == "OUTPUT_INVALID"
    assert j3.stop_status(record, verdict) == "STOPPED"


def _report(base: Path, data: dict[str, Any]) -> None:
    problem = ScheduleInput.model_validate(data)
    options = ExplainOptions(time_limit_seconds=5.0, seed=1, granularity="FULL")
    (base / "report.json").write_text(explain_infeasibility(problem, options).model_dump_json())


def test_explain_on_unsat_input(tmp_path: Path) -> None:
    fixtures = Path(__file__).parents[2] / "tests/fixtures"
    _report(tmp_path, json.loads((fixtures / "infeasible_teacher.json").read_text()))
    output = v1.OutputVerification(status="VALID_CORE_ERROR", solver_status="PRECHECK_PROOF")
    verdict = j3.judge_explain(_record(tmp_path, output), tmp_path, "UNSAT", LIMITS)
    assert (verdict.hard, verdict.performance) == ("PASS", "MET")
    assert verdict.explain is not None and verdict.explain["status"] == "PRECHECK_PROOF"
    _report(tmp_path, json.loads((fixtures / "feasible_small.json").read_text()))
    output = v1.OutputVerification(status="VALID_CORE_ERROR", solver_status="NOT_INFEASIBLE")
    verdict = j3.judge_explain(_record(tmp_path, output), tmp_path, "UNSAT", LIMITS)
    assert verdict.hard == "FAIL" and "UNSAT_REPORTED_FEASIBLE" in verdict.reasons


def test_input_rejected_by_core_is_not_a_hard_fail(repaired: Path) -> None:
    """Incident phase3c-linux-01: a core INPUT_INVALID is not a wrong schedule; it must not stop."""
    envelope = json.loads((repaired / "result.json").read_text())
    envelope["result"].update(
        status="INPUT_INVALID", valid_schedule=False, assignments=[], validation=None
    )
    envelope["result"]["quality"] = {
        "policy_version": "0.4",
        "status": "NOT_EVALUATED",
        "score": None,
        "optimal_prefix": [],
        "tier_runs": [],
    }
    envelope["result"]["diagnostics"] = [
        {"code": "LOCK_CONFLICT", "message": "m", "occurrence_ids": ["r::1"]}
    ]
    envelope["repair"] = None
    (repaired / "result.json").write_text(json.dumps(envelope))
    output = v1.OutputVerification(status="VALID_CORE_ERROR", solver_status="INPUT_INVALID")
    record = _record(repaired, output, code=2)
    verdict = j3.judge_repair(record, repaired, "EXPECTED_INFEASIBLE", LIMITS)
    assert (verdict.hard, verdict.performance, verdict.quality) == (
        "NOT_APPLICABLE",
        "NOT_APPLICABLE",
        "NO_SCHEDULE",
    )
    assert verdict.status == "INPUT_INVALID"
    assert verdict.reasons == ("CORE_REJECTED_INPUT", "LOCK_CONFLICT")
    assert j3.stop_status(record, verdict) is None
