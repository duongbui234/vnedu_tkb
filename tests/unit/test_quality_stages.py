"""Deterministic stage statuses, saved incumbents and budget accounting."""

from typing import Any

import pytest

from tkb_core.constraints.soft import compile_soft
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver.model_builder import build_model
from tkb_core.solver.objectives import StageOutcome, run_quality
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.score_evaluator import _evaluate_validated


@pytest.mark.parametrize(
    "later,expected",
    [
        ("OPTIMAL", "OPTIMAL"),
        ("FEASIBLE", "FEASIBLE"),
        ("UNKNOWN", "FEASIBLE"),
        ("INFEASIBLE", "MODEL_INVALID"),
        ("MODEL_INVALID", "MODEL_INVALID"),
    ],
)
def test_stage_proof_and_fallback(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch, later: str, expected: str
) -> None:
    for module in (
        "preprocessing.normalize",
        "validation.independent_validator",
        "validation.score_evaluator",
    ):
        monkeypatch.setattr(f"tkb_core.{module}.check_capabilities", lambda p: None)
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_AVOID_SLOTS",
            "parameters": {"slot_ids": ["1-AM-1"]},
            "weight": 1,
            "priority": 1,
        }
    ]
    p = prepare(ScheduleInput.model_validate(quality_case))
    built = build_model(p)
    compiled = compile_soft(p, built)
    aa = tuple(
        ScheduleAssignment(
            occurrence_id=f"r::{i}", slot_id=f"1-PM-{start}", class_ids=("c",), teacher_ids=("t",)
        )
        for i, start in enumerate((1, 3, 4), 1)
    )
    calls = []

    def fake(
        prepared: Any, built: Any, compiled: Any, options: Any, priority: Any, budget: float
    ) -> StageOutcome:
        calls.append(budget)
        status = "OPTIMAL" if priority is None else later
        return StageOutcome(
            status=SolveStatus(status),
            assignments=aa if status in ("OPTIMAL", "FEASIBLE") else (),
            rule_values={"rule": (0, 0)},
            tier_values={1: 0},
            wall_time=1.0,
            best_bound=None if priority is None else 0.0,
        )

    ticks = iter((0.0, 3.0, 3.0, 5.0))
    monkeypatch.setattr("tkb_core.solver.objectives.perf_counter", lambda: next(ticks))
    monkeypatch.setattr("tkb_core.solver.objectives._run_stage", fake)
    out = run_quality(p, built, compiled, SolveOptions(time_limit_seconds=10.0))
    assert out.status == expected
    assert calls == [10.0, 7.0]
    if expected != "MODEL_INVALID":
        assert out.assignments == aa
        assert out.score == _evaluate_validated(p.normalized.problem, aa)
        assert out.quality.optimal_prefix == ((1,) if later == "OPTIMAL" else ())
    else:
        assert not out.assignments


@pytest.mark.parametrize(
    "scenario,expected,code",
    [
        ("mismatch", "MODEL_INVALID", "INTERNAL_SCORE_MISMATCH"),
        ("no_first", "UNKNOWN", None),
        ("budget", "FEASIBLE", None),
    ],
)
def test_mismatch_and_budget(
    quality_case: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
    expected: str,
    code: str | None,
) -> None:
    for module in (
        "preprocessing.normalize",
        "validation.independent_validator",
        "validation.score_evaluator",
    ):
        monkeypatch.setattr(f"tkb_core.{module}.check_capabilities", lambda p: None)
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_AVOID_SLOTS",
            "parameters": {"slot_ids": ["1-AM-1"]},
            "weight": 1,
            "priority": 1,
        }
    ]
    p = prepare(ScheduleInput.model_validate(quality_case))
    built = build_model(p)
    compiled = compile_soft(p, built)
    aa = tuple(
        ScheduleAssignment(
            occurrence_id=f"r::{i}", slot_id=f"1-PM-{start}", class_ids=("c",), teacher_ids=("t",)
        )
        for i, start in enumerate((1, 3, 4), 1)
    )
    calls = []

    def fake(*args: Any) -> StageOutcome:
        calls.append(args[-1])
        if scenario == "no_first":
            return StageOutcome(SolveStatus.UNKNOWN, wall_time=1.0)
        return StageOutcome(
            SolveStatus.OPTIMAL,
            aa,
            {"rule": (1, 1) if scenario == "mismatch" else (0, 0)},
            {1: 1 if scenario == "mismatch" else 0},
            wall_time=1.0,
        )

    ticks = iter((0.0, 3.0))
    monkeypatch.setattr("tkb_core.solver.objectives.perf_counter", lambda: next(ticks))
    monkeypatch.setattr("tkb_core.solver.objectives._run_stage", fake)
    out = run_quality(p, built, compiled, SolveOptions(time_limit_seconds=3.0))
    assert out.status == expected and len(calls) == 1
    assert out.diagnostics[0].code == code if code else not out.diagnostics
    if scenario == "budget":
        assert out.quality.tier_runs[0].raw_status == "NOT_RUN" and out.assignments
