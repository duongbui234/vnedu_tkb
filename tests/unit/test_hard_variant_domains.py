"""Placement-local hard variants (S01/S04) filter candidate domains (Phase 2B)."""

import copy
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.errors import CoreError
from tkb_core.preprocessing.feasibility import prepare

AVOID = {"id": "h1", "code": "TEACHER_AVOID_SLOTS", "parameters": {"slot_ids": ["1-AM-2"]}}
WINDOW = {
    "id": "h4",
    "code": "TEACHER_PREFERRED_PERIOD_WINDOW",
    "parameters": {"first_period": 2, "last_period": 3, "session_ids": ["AM"]},
}


def _covered(data: dict[str, Any]) -> dict[str, set[tuple[str, ...]]]:
    prepared = prepare(ScheduleInput.model_validate(data))
    return {o: {p.slot_ids for p in d} for o, d in prepared.domains.items()}


def test_avoid_removes_every_placement_touching_slot(hard_case: dict[str, Any]) -> None:
    hard_case["constraint_config"]["hard"] = [AVOID]
    domains = _covered(hard_case)
    assert all("1-AM-2" not in c for cs in domains.values() for c in cs)
    assert ("1-AM-1", "1-AM-2") not in domains["r::1"]
    assert ("1-AM-3", "1-AM-4") in domains["r::1"]
    assert ("1-AM-1",) in domains["r::2"]


def test_window_checks_second_period_and_other_sessions(hard_case: dict[str, Any]) -> None:
    hard_case["constraint_config"]["hard"] = [WINDOW]
    domains = _covered(hard_case)
    assert domains["r::1"] & {("1-AM-2", "1-AM-3")}
    assert not domains["r::1"] & {("1-AM-3", "1-AM-4"), ("1-AM-1", "1-AM-2")}
    assert {("1-AM-2",), ("1-AM-3",), ("1-PM-1",), ("1-PM-4",)} <= domains["r::2"]
    assert ("1-AM-4",) not in domains["r::2"]


def test_aggregate_rules_do_not_prune(hard_case: dict[str, Any], quality_case: Any) -> None:
    base = _covered(copy.deepcopy(hard_case))
    hard_case["constraint_config"]["hard"] = [
        {"id": "h3", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 0}},
    ]
    assert _covered(hard_case) == base


def test_no_enabled_hard_keeps_domains_identical(hard_case: dict[str, Any]) -> None:
    legacy = copy.deepcopy(hard_case)
    legacy["constraint_config"]["policy_version"] = "0.1"
    hard_case["constraint_config"]["hard"] = [{**AVOID, "enabled": False}]
    a = prepare(ScheduleInput.model_validate(legacy)).domains
    b = prepare(ScheduleInput.model_validate(hard_case)).domains
    assert a == b


def test_scope_limits_filter(hard_case: dict[str, Any]) -> None:
    hard_case["teachers"].append({"id": "other"})
    hard_case["constraint_config"]["hard"] = [{**AVOID, "scope": {"teacher_ids": ["other"]}}]
    assert ("1-AM-1", "1-AM-2") in _covered(hard_case)["r::1"]


def test_empty_domain_is_infeasible(hard_case: dict[str, Any]) -> None:
    every = [s["id"] for s in hard_case["time_slots"]]
    hard_case["constraint_config"]["hard"] = [{**AVOID, "parameters": {"slot_ids": every}}]
    with pytest.raises(CoreError) as err:
        prepare(ScheduleInput.model_validate(hard_case))
    assert (err.value.status.value, err.value.diagnostics[0].code) == ("INFEASIBLE", "EMPTY_DOMAIN")


def test_lock_into_forbidden_slot_conflicts(hard_case: dict[str, Any]) -> None:
    hard_case["constraint_config"]["hard"] = [AVOID]
    hard_case["locked_assignments"] = [{"occurrence_id": "r::2", "slot_id": "1-AM-2"}]
    with pytest.raises(CoreError) as err:
        prepare(ScheduleInput.model_validate(hard_case))
    assert (err.value.status.value, err.value.diagnostics[0].code) == (
        "INPUT_INVALID",
        "LOCK_CONFLICT",
    )


def test_timed_alias_is_filtered(hard_case: dict[str, Any]) -> None:
    hard_case["time_slots"] = [
        {"id": "a1", "day": 1, "session": "A", "period": 1, "start_minute": 0, "end_minute": 45},
        {"id": "b1", "day": 1, "session": "B", "period": 1, "start_minute": 30, "end_minute": 75},
        {"id": "c1", "day": 1, "session": "C", "period": 1, "start_minute": 200, "end_minute": 245},
    ]
    hard_case["teaching_requirements"][0].update(periods_per_cycle=1, block_durations=[1])
    hard_case["constraint_config"]["hard"] = [{**AVOID, "parameters": {"slot_ids": ["b1"]}}]
    assert _covered(hard_case)["r::1"] == {("c1",)}
