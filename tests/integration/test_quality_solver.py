"""Public quality solve keeps hard semantics and legacy contracts."""

from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score


@pytest.mark.parametrize(
    "code,params",
    [
        ("TEACHER_AVOID_SLOTS", {"slot_ids": ["1-AM-1"]}),
        ("TEACHER_MAX_PERIODS_PER_SESSION", {"limit": 2, "session_ids": ["AM", "PM"]}),
        ("TEACHER_MAX_PERIODS_PER_DAY", {"limit": 2}),
        (
            "TEACHER_PREFERRED_PERIOD_WINDOW",
            {"first_period": 2, "last_period": 3, "session_ids": ["AM", "PM"]},
        ),
    ],
)
def test_v11_soft_solve_then_independent_score(
    quality_case: dict[str, Any], code: str, params: dict[str, Any]
) -> None:
    quality_case["constraint_config"]["soft"] = [
        {"id": "rule", "code": code, "parameters": params, "weight": 1, "priority": 1}
    ]
    p = ScheduleInput.model_validate(quality_case)
    r = solve(p, SolveOptions(time_limit_seconds=5.0))
    assert r.valid_schedule and r.schema_version == "1.2"
    assert r.status == "OPTIMAL" and r.quality.status == "LEXICOGRAPHIC_OPTIMAL"
    assert evaluate_score(p, r.assignments) == r.quality.score
    assert validate_schedule(p, r.assignments).valid
    assert ScheduleResult.model_validate_json(r.model_dump_json()) == r


def test_empty_and_no_soft(quality_case: dict[str, Any]) -> None:
    p = ScheduleInput.model_validate(quality_case)
    r = solve(p)
    assert r.valid_schedule and r.quality.status == "NOT_REQUESTED"
    quality_case["teaching_requirements"] = []
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 0},
            "weight": 1,
            "priority": 1,
        }
    ]
    r = solve(ScheduleInput.model_validate(quality_case))
    assert r.status == "FEASIBLE" and r.quality.score.tiers == (0, 0, 0)
    assert not r.metadata.solver_executed


def test_hard_modes_and_unknown_rejected(quality_case: dict[str, Any]) -> None:
    quality_case["constraint_config"]["hard"] = [
        {"id": "h", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 0}}
    ]
    assert solve(ScheduleInput.model_validate(quality_case)).status == "UNSUPPORTED_FEATURE"
    quality_case["constraint_config"]["hard"] = []
    quality_case["constraint_config"]["soft"] = [
        {"id": "x", "code": "x", "weight": 1, "priority": 1}
    ]
    p = ScheduleInput.model_validate(quality_case)
    assert solve(p).status == "UNSUPPORTED_FEATURE"
    assert evaluate_score(p, ()).status == "UNSUPPORTED_FEATURE"


def test_timed_alias_is_counted_once_and_room_choices_do_not_multiply(
    quality_case: dict[str, Any],
) -> None:
    quality_case["time_slots"] = [
        {"id": s, "day": 1, "session": s, "period": 1, "start_minute": 0, "end_minute": 45}
        for s in ("avoid", "alias", "other")
    ]
    quality_case["teachers"][0]["available_slot_ids"] = ["alias"]
    quality_case["teaching_requirements"][0].update(
        periods_per_cycle=1, block_durations=[1], room_required=True
    )
    quality_case["manage_rooms"] = True
    quality_case["classes"][0]["size"] = 20
    quality_case["rooms"] = [{"id": "room-a", "capacity": 30}, {"id": "room-b", "capacity": 30}]
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_AVOID_SLOTS",
            "parameters": {"slot_ids": ["avoid", "other"]},
            "weight": 1,
            "priority": 1,
        }
    ]
    p = ScheduleInput.model_validate(quality_case)
    r = solve(p)
    assert r.valid_schedule and r.assignments[0].slot_id == "alias"
    assert r.quality.score.tiers == (1, 0, 0)
    assert evaluate_score(p, r.assignments).tiers == (1, 0, 0)
    duplicate = {
        **quality_case["constraint_config"]["soft"][0],
        "id": "second",
        "parameters": {"slot_ids": ["alias"]},
    }
    quality_case["constraint_config"]["soft"].append(duplicate)
    assert solve(ScheduleInput.model_validate(quality_case)).status == "INPUT_INVALID"


def test_soft_limits_do_not_remove_locked_teaching(quality_case: dict[str, Any]) -> None:
    quality_case["locked_assignments"] = [
        {"occurrence_id": f"r::{i}", "slot_id": f"1-AM-{start}"}
        for i, start in enumerate((1, 3, 4), 1)
    ]
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "rule",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 0},
            "weight": 7,
            "priority": 2,
        }
    ]
    p = ScheduleInput.model_validate(quality_case)
    r = solve(p)
    assert r.valid_schedule and r.quality.optimal_prefix == (2,)
    assert r.quality.score.tiers == (0, 28, 0)
    p.teaching_requirements[0].block_durations = (1,)
    assert solve(p).status == "INPUT_INVALID"


@pytest.mark.parametrize("failure", ["options", "mutation", "constructed"])
def test_recognized_v11_validation_errors_still_emit_v12(
    quality_data: dict[str, Any], failure: str
) -> None:
    p = ScheduleInput.model_validate(quality_data)
    options = SolveOptions()
    if failure == "options":
        options.time_limit_seconds = -1.0
    elif failure == "mutation":
        p.constraint_config.soft[0].priority = 4
    else:
        p = ScheduleInput.model_construct(schema_version="1.1", school="invalid")
    r = solve(p, options)
    assert r.status == "INPUT_INVALID" and r.schema_version == "1.2"
    assert r.quality.status == "NOT_EVALUATED" and r.quality.score is None
    assert not r.assignments and not r.metadata.solver_executed
