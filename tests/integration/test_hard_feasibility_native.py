"""Native checks: hard schedules extend to the soft model; public solve uses hard feasibility."""

from typing import Any

import pytest

from tkb_core.constraints.soft import compile_soft
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver import objectives
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.model_builder import build_model
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.score_evaluator import evaluate_score

SCHEDULE = tuple(
    ScheduleAssignment(
        occurrence_id=f"r::{i}", slot_id=f"1-PM-{start}", class_ids=("c",), teacher_ids=("t",)
    )
    for i, start in enumerate((1, 3, 4), 1)
)


@pytest.mark.parametrize(
    "code,params",
    [
        ("TEACHER_AVOID_SLOTS", {"slot_ids": ["1-PM-3"]}),
        ("TEACHER_MAX_PERIODS_PER_SESSION", {"limit": 1, "session_ids": ["PM"]}),
        ("TEACHER_MAX_PERIODS_PER_DAY", {"limit": 1}),
        (
            "TEACHER_PREFERRED_PERIOD_WINDOW",
            {"first_period": 2, "last_period": 3, "session_ids": ["PM"]},
        ),
    ],
)
def test_hard_schedule_extends_to_soft_model(
    quality_case: dict[str, Any], code: str, params: dict[str, Any]
) -> None:
    quality_case["constraint_config"]["soft"] = [
        {"id": "rule", "code": code, "parameters": params, "weight": 3, "priority": 2}
    ]
    problem = ScheduleInput.model_validate(quality_case)
    p = prepare(problem)
    built = build_model(p)
    compiled = compile_soft(p, built)
    objectives._hint(p, built, SCHEDULE)
    out = objectives._run_stage(
        p, built, compiled, SolveOptions(time_limit_seconds=5.0), None, 5.0, fix_hint=True
    )
    assert out.status == SolveStatus.OPTIMAL and out.assignments == SCHEDULE
    score = evaluate_score(problem, SCHEDULE)
    assert score.status == "OK" and score.tiers is not None and score.tiers[1] > 0
    assert out.rule_values == {
        "rule": (score.rules[0].raw_penalty, score.rules[0].weighted_penalty)
    }
    assert out.tier_values == {2: score.tiers[1]}


def test_objective_range_still_rejected_before_any_solve(quality_case: dict[str, Any]) -> None:
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 0},
            "weight": 2**53,
            "priority": 1,
        }
    ]
    result = solve(ScheduleInput.model_validate(quality_case))
    assert result.status == "INPUT_INVALID" and not result.metadata.solver_executed
    assert result.diagnostics[0].code == "OBJECTIVE_RANGE"


def test_public_solve_runs_feasibility_on_hard_model(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 2},
            "weight": 1,
            "priority": 1,
        }
    ]
    real = objectives._run_stage
    seen: list[tuple[Any, Any, bool]] = []

    def spy(*args: Any, **kwargs: Any) -> objectives.StageOutcome:
        seen.append((args[4], kwargs.get("model"), kwargs.get("fix_hint", False)))
        return real(*args, **kwargs)

    monkeypatch.setattr(objectives, "_run_stage", spy)
    problem = ScheduleInput.model_validate(quality_case)
    result = solve(problem, SolveOptions(time_limit_seconds=5.0))
    assert result.status == "OPTIMAL" and result.valid_schedule
    assert [(pr, m is not None, f) for pr, m, f in seen] == [
        (None, True, False),
        (None, False, True),
        (1, False, False),
    ]
    assert not any(v.name.startswith(("excess_", "raw_")) for v in seen[0][1].proto.variables)
    assert evaluate_score(problem, result.assignments) == result.quality.score
