"""Hard S05 (day windows) and S06 (class-subject-day limits) as CP-SAT constraints."""

from typing import Any

import pytest
from ortools.sat.python import cp_model

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.errors import CoreError
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver.model_builder import build_model


def _spread(k: int) -> dict[str, Any]:
    return {
        "id": "spread",
        "code": "SUBJECT_COMPONENT_DAY_SPREAD",
        "parameters": {"requirement_ids": ["r"], "min_day_gap": k},
    }


def _subject_day(limit: int) -> dict[str, Any]:
    return {"id": "sd", "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY", "parameters": {"limit": limit}}


def _status(data: dict[str, Any], rule: dict[str, Any], forced: dict[str, str]) -> str:
    data["constraint_config"]["hard"] = [rule]
    prepared = prepare(ScheduleInput.model_validate(data))
    built = build_model(prepared)
    for occurrence, start in forced.items():
        for placement, var in zip(
            prepared.domains[occurrence], built.variables[occurrence], strict=True
        ):
            if placement.start_slot_id == start:
                built.model.add(var == 1)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    return str(solver.status_name(solver.solve(built.model)))


FEASIBLE = ("OPTIMAL", "FEASIBLE")


def test_spread_window_matches_pair_definition(dist_case: dict[str, Any]) -> None:
    dist_case["teaching_requirements"][0].update(periods_per_cycle=2, block_durations=[1, 1])
    assert _status(dist_case, _spread(2), {"r::1": "1-AM-1", "r::2": "2-AM-1"}) == "INFEASIBLE"
    assert _status(dist_case, _spread(2), {"r::1": "1-AM-1", "r::2": "3-AM-1"}) in FEASIBLE
    assert _status(dist_case, _spread(1), {"r::1": "1-AM-1", "r::2": "1-PM-1"}) == "INFEASIBLE"
    assert _status(dist_case, _spread(1), {"r::1": "1-AM-1", "r::2": "2-PM-1"}) in FEASIBLE


def test_spread_infeasible_beyond_cycle(dist_case: dict[str, Any]) -> None:
    # Three components need days at least 2 apart: 1, 3, 5 does not fit days 1..3.
    assert _status(dist_case, _spread(2), {}) == "INFEASIBLE"
    assert _status(dist_case, _spread(1), {}) in FEASIBLE


def test_subject_day_limit_counts_double(dist_case: dict[str, Any]) -> None:
    forced = {"r::1": "1-AM-1", "r::2": "1-PM-1"}
    assert _status(dist_case, _subject_day(2), forced) == "INFEASIBLE"
    assert _status(dist_case, _subject_day(3), forced) in FEASIBLE
    assert _status(dist_case, _subject_day(0), {}) == "INFEASIBLE"


def test_subject_day_range_guard(dist_case: dict[str, Any]) -> None:
    dist_case["constraint_config"]["hard"] = [_subject_day(2**63)]
    prepared = prepare(ScheduleInput.model_validate(dist_case))
    with pytest.raises(CoreError) as err:
        build_model(prepared)
    assert err.value.diagnostics[0].code == "HARD_RULE_RANGE"


@pytest.mark.parametrize("policy", ["0.1", "0.2"])
def test_older_policy_models_unchanged(quality_case: dict[str, Any], policy: str) -> None:
    quality_case["constraint_config"]["policy_version"] = policy
    before = str(build_model(prepare(ScheduleInput.model_validate(quality_case))).model.proto)
    quality_case["constraint_config"]["policy_version"] = "0.3"
    quality_case["constraint_config"]["hard"] = [{**_subject_day(0), "enabled": False}]
    after = str(build_model(prepare(ScheduleInput.model_validate(quality_case))).model.proto)
    assert before == after
