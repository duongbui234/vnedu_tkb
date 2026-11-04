"""Aggregate hard variants (S02/S03) as exact CP-SAT load limits (Phase 2B)."""

from typing import Any

import pytest
from ortools.sat.python import cp_model

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.errors import CoreError
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver.model_builder import build_model


def _session(limit: int, sessions: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": "h2",
        "code": "TEACHER_MAX_PERIODS_PER_SESSION",
        "parameters": {"limit": limit, "session_ids": sessions or ["AM"]},
    }


def _day(limit: int) -> dict[str, Any]:
    return {"id": "h3", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": limit}}


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
    return solver.status_name(solver.solve(built.model))


def test_session_limit_counts_double_and_allows_equality(hard_case: dict[str, Any]) -> None:
    forced = {"r::1": "1-AM-1", "r::2": "1-AM-3"}
    assert _status(hard_case, _session(2), forced) == "INFEASIBLE"
    assert _status(hard_case, _session(3), forced) in ("OPTIMAL", "FEASIBLE")
    assert _status(hard_case, _session(2, ["PM"]), forced) in ("OPTIMAL", "FEASIBLE")


def test_day_limit_sums_sessions(hard_case: dict[str, Any]) -> None:
    forced = {"r::1": "1-AM-1", "r::2": "1-PM-1"}
    assert _status(hard_case, _day(2), forced) == "INFEASIBLE"
    assert _status(hard_case, _day(3), forced) in ("OPTIMAL", "FEASIBLE")
    # Two days with limit 1 cannot hold four periods, and limit 0 forbids teaching.
    assert _status(hard_case, _day(1), {}) == "INFEASIBLE"
    assert _status(hard_case, _day(0), {}) == "INFEASIBLE"
    assert _status(hard_case, _day(2), {}) in ("OPTIMAL", "FEASIBLE")


def test_limit_range_guard(hard_case: dict[str, Any]) -> None:
    hard_case["constraint_config"]["hard"] = [_day(2**63)]
    prepared = prepare(ScheduleInput.model_validate(hard_case))
    with pytest.raises(CoreError) as err:
        build_model(prepared)
    assert err.value.diagnostics[0].code == "HARD_RULE_RANGE"


def test_policy_01_model_unchanged(quality_case: dict[str, Any]) -> None:
    prepared = prepare(ScheduleInput.model_validate(quality_case))
    before = str(build_model(prepared).model.proto)
    quality_case["constraint_config"]["policy_version"] = "0.2"
    quality_case["constraint_config"]["hard"] = [{**_day(1), "enabled": False}]
    after = str(build_model(prepare(ScheduleInput.model_validate(quality_case))).model.proto)
    assert before == after
