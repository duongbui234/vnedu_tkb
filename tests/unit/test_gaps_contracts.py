"""Policy 0.4 contracts: versions, occupied work, scopes, overlap and timelines (2C-2)."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from tkb_core.constraints.registry import supports_mode, validate_rule_config
from tkb_core.contracts.capabilities import check_capabilities
from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult, SolverRunMetadataV12, ValidationReport
from tkb_core.contracts.score import QualityReport, RuleScore, ScoreReport
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.errors import CoreError

NEW_CODES = (
    "TEACHER_RESTRICTED_SLOTS",
    "TEACHER_TOTAL_GAPS",
    "TEACHER_MAX_GAP_RUN",
    "TEACHER_MIN_FREE_TIME",
    "TEACHER_SINGLE_PERIOD_SESSION",
)
GAPS = {"id": "gaps", "code": "TEACHER_TOTAL_GAPS", "parameters": {"session_ids": ["AM"]}}
AVAILABLE = [f"{d}-{s}-{p}" for d in (1, 2) for s in ("AM", "PM") for p in (1, 2, 3, 4)]


def _soft(rule: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {**copy.deepcopy(rule), "priority": 2, "weight": 1, **extra}


def _error(data: dict[str, Any]) -> str:
    with pytest.raises(CoreError) as err:
        check_capabilities(ScheduleInput.model_validate(data))
    return err.value.diagnostics[0].code


def test_policy_04_and_unknown_version(gap_case: dict[str, Any]) -> None:
    gap_case["constraint_config"]["soft"] = [_soft(GAPS)]
    p = ScheduleInput.model_validate(gap_case)
    assert ScheduleInput.model_validate_json(p.model_dump_json()) == p
    check_capabilities(p)
    gap_case["constraint_config"]["policy_version"] = "0.5"
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(gap_case)


@pytest.mark.parametrize("policy", ["0.1", "0.2", "0.3"])
def test_older_policies_treat_new_codes_as_unknown(gap_case: dict[str, Any], policy: str) -> None:
    gap_case["constraint_config"]["policy_version"] = policy
    gap_case["constraint_config"]["soft"] = [_soft(GAPS)]
    assert _error(gap_case) == "UNKNOWN_RULE"


def test_mode_matrix() -> None:
    for code in NEW_CODES:
        assert supports_mode(code, "soft", "0.4")
        assert not supports_mode(code, "hard", "0.4")  # D5: soft only
        assert not supports_mode(code, "soft", "0.3")
    for code in ("TEACHER_AVOID_SLOTS", "SUBJECT_COMPONENT_DAY_SPREAD"):
        assert supports_mode(code, "soft", "0.4") and supports_mode(code, "hard", "0.4")


def test_hard_mode_is_refused(gap_case: dict[str, Any]) -> None:
    gap_case["constraint_config"]["hard"] = [GAPS]
    assert _error(gap_case) == "CUSTOM_RULE"


@pytest.mark.parametrize(
    "rule",
    [
        {"id": "x", "code": "TEACHER_RESTRICTED_SLOTS", "parameters": {"slot_ids": []}},
        {"id": "x", "code": "TEACHER_TOTAL_GAPS", "parameters": {"session_ids": ["XX"]}},
        {
            "id": "x",
            "code": "TEACHER_MAX_GAP_RUN",
            "parameters": {"limit": -1, "session_ids": ["AM"]},
        },
        {"id": "x", "code": "TEACHER_MIN_FREE_TIME", "parameters": {"unit": "week", "target": 1}},
        {"id": "x", "code": "TEACHER_MIN_FREE_TIME", "parameters": {"unit": "day", "target": 0}},
        {
            "id": "x",
            "code": "TEACHER_SINGLE_PERIOD_SESSION",
            "parameters": {"session_ids": ["AM", "AM"]},
        },
    ],
)
def test_parameter_contracts(gap_case: dict[str, Any], rule: dict[str, Any]) -> None:
    gap_case["constraint_config"]["soft"] = [_soft(rule, enabled=False)]
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(gap_case)


def test_teacher_scope_only(gap_case: dict[str, Any]) -> None:
    gap_case["constraint_config"]["soft"] = [_soft(GAPS, scope={"class_ids": ["c"]})]
    assert _error(gap_case) == "RULE_SCOPE"


def _overlap(data: dict[str, Any]) -> bool:
    try:
        validate_rule_config(ScheduleInput.model_validate(data))
    except CoreError as exc:
        assert exc.diagnostics[0].code == "OVERLAPPING_RULES"
        return True
    return False


def test_s01_and_s07_may_not_count_the_same_slot(gap_case: dict[str, Any]) -> None:
    config = gap_case["constraint_config"]
    restricted = {
        "id": "r7",
        "code": "TEACHER_RESTRICTED_SLOTS",
        "parameters": {"slot_ids": ["1-AM-1"]},
    }
    avoid = {"id": "r1", "code": "TEACHER_AVOID_SLOTS", "parameters": {"slot_ids": ["1-AM-1"]}}
    config["soft"] = [_soft(restricted), _soft(avoid)]
    assert _overlap(gap_case)
    config["soft"][1]["parameters"]["slot_ids"] = ["1-AM-2"]
    assert not _overlap(gap_case)
    config["soft"] = [_soft(restricted)]
    config["hard"] = [avoid]
    assert _overlap(gap_case)


def test_session_and_free_time_overlap(gap_case: dict[str, Any]) -> None:
    config = gap_case["constraint_config"]
    config["soft"] = [_soft(GAPS), _soft(GAPS, id="g2", parameters={"session_ids": ["PM"]})]
    assert not _overlap(gap_case)
    config["soft"][1]["parameters"]["session_ids"] = ["PM", "AM"]
    assert _overlap(gap_case)
    free = {"id": "f", "code": "TEACHER_MIN_FREE_TIME", "parameters": {"unit": "day", "target": 1}}
    config["soft"] = [
        _soft(free),
        _soft(free, id="f2", parameters={"unit": "session", "target": 2}),
    ]
    assert _overlap(gap_case)
    # Different families combine freely.
    config["soft"] = [_soft(free), _soft(GAPS)]
    assert not _overlap(gap_case)


def _timed(data: dict[str, Any], cross_session_overlap: bool) -> None:
    b_start = 30 if cross_session_overlap else 100
    data["time_slots"] = [
        {"id": "a1", "day": 1, "session": "A", "period": 1, "start_minute": 0, "end_minute": 45},
        {"id": "a2", "day": 1, "session": "A", "period": 2, "start_minute": 45, "end_minute": 90},
        {
            "id": "b1",
            "day": 1,
            "session": "B",
            "period": 1,
            "start_minute": b_start,
            "end_minute": b_start + 45,
        },
    ]
    data["teaching_requirements"][0].update(periods_per_cycle=1, block_durations=[1])


def test_gap_rules_refuse_ambiguous_timelines(gap_case: dict[str, Any]) -> None:
    _timed(gap_case, cross_session_overlap=True)
    gap_case["constraint_config"]["soft"] = [_soft(GAPS, parameters={"session_ids": ["A"]})]
    assert _error(gap_case) == "GAP_TIMELINE"
    _timed(gap_case, cross_session_overlap=False)
    check_capabilities(ScheduleInput.model_validate(gap_case))
    _timed(gap_case, cross_session_overlap=True)
    gap_case["constraint_config"]["soft"] = [
        _soft({"id": "r7", "code": "TEACHER_RESTRICTED_SLOTS", "parameters": {"slot_ids": ["b1"]}})
    ]
    check_capabilities(ScheduleInput.model_validate(gap_case))  # S07 supports timed slots


def test_occupied_work_contract(gap_case: dict[str, Any]) -> None:
    gap_case["teachers"][0]["available_slot_ids"] = [s for s in AVAILABLE if s != "1-AM-3"]
    gap_case["constraint_config"]["occupied_work"] = [{"teacher_id": "t", "slot_ids": ["1-AM-3"]}]
    p = ScheduleInput.model_validate(gap_case)
    assert ScheduleInput.model_validate_json(p.model_dump_json()) == p
    for bad in (
        [{"teacher_id": "t", "slot_ids": ["1-AM-2"]}],  # inside availability
        [{"teacher_id": "t", "slot_ids": ["nope"]}],
        [{"teacher_id": "t", "slot_ids": ["1-AM-3", "1-AM-3"]}],
        [{"teacher_id": "t", "slot_ids": []}],
        [{"teacher_id": "x", "slot_ids": ["1-AM-3"]}],
        [{"teacher_id": "t", "slot_ids": ["1-AM-3"]}, {"teacher_id": "t", "slot_ids": ["2-PM-1"]}],
    ):
        data = copy.deepcopy(gap_case)
        data["constraint_config"]["occupied_work"] = bad
        with pytest.raises(ValidationError):
            ScheduleInput.model_validate(data)
    data = copy.deepcopy(gap_case)
    data["teachers"][0]["available_slot_ids"] = None  # every slot available
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(data)


@pytest.mark.parametrize("policy", ["0.1", "0.2", "0.3"])
def test_occupied_work_only_in_policy_04(gap_case: dict[str, Any], policy: str) -> None:
    gap_case["teachers"][0]["available_slot_ids"] = [s for s in AVAILABLE if s != "1-AM-3"]
    gap_case["constraint_config"]["policy_version"] = policy
    gap_case["constraint_config"]["occupied_work"] = [{"teacher_id": "t", "slot_ids": ["1-AM-3"]}]
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(gap_case)
    # Review F1: the key was unknown to these policies, so even an empty list is refused.
    gap_case["constraint_config"]["occupied_work"] = []
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(gap_case)
    del gap_case["constraint_config"]["occupied_work"]
    dumped = ScheduleInput.model_validate(gap_case).model_dump()
    assert "occupied_work" not in dumped["constraint_config"]


def test_policy_04_accepts_explicit_empty_occupied_work(gap_case: dict[str, Any]) -> None:
    gap_case["constraint_config"]["occupied_work"] = []
    p = ScheduleInput.model_validate(gap_case)
    assert "occupied_work" not in p.model_dump()["constraint_config"]
    del gap_case["constraint_config"]["occupied_work"]
    assert ScheduleInput.model_validate(gap_case).fingerprint() == p.fingerprint()


def test_older_fixture_hashes_unchanged() -> None:
    root = Path(__file__).parents[1] / "fixtures"
    expected = {
        "feasible_small.json": "77851bfa1fa34e4155969ee7749117415de0fd90e6de743fd7267f5ec194eee1",
    }
    for name, digest in expected.items():
        data = json.loads((root / name).read_text())
        assert ScheduleInput.model_validate(data).fingerprint() == digest


def test_occupied_work_fingerprint_is_order_free(gap_case: dict[str, Any]) -> None:
    gap_case["teachers"].append({"id": "u", "available_slot_ids": ["1-AM-1"]})
    gap_case["teachers"][0]["available_slot_ids"] = ["1-AM-1", "1-AM-2"]
    work = [
        {"teacher_id": "u", "slot_ids": ["2-PM-1", "1-PM-1"]},
        {"teacher_id": "t", "slot_ids": ["2-AM-1"]},
    ]
    gap_case["constraint_config"]["occupied_work"] = work
    gap_case["teaching_requirements"][0].update(periods_per_cycle=2, block_durations=[1, 1])
    a = ScheduleInput.model_validate(gap_case).fingerprint()
    work.reverse()
    work[1]["slot_ids"].reverse()
    assert ScheduleInput.model_validate(gap_case).fingerprint() == a


def _row(unit: str) -> RuleScore:
    return RuleScore(
        rule_id="x", code="c", priority=1, weight=1, unit=unit, raw_penalty=1, weighted_penalty=1
    )


@pytest.mark.parametrize(
    "unit", ["idle_periods", "free_days", "free_sessions", "single_period_sessions"]
)
def test_score_units_by_version(unit: str) -> None:
    ok = {"status": "OK", "input_fingerprint": "a" * 64, "tiers": (1, 0, 0)}
    ScoreReport(schema_version="1.2", rules=(_row(unit),), **ok)
    for old in ("1.0", "1.1"):
        with pytest.raises(ValidationError):
            ScoreReport(schema_version=old, rules=(_row(unit),), **ok)


def _result(version: str, policy: str, score_version: str) -> dict[str, Any]:
    score = ScoreReport(
        schema_version=score_version, status="OK", input_fingerprint="a" * 64, tiers=(0, 0, 0)
    )
    return ScheduleResult.model_construct(
        schema_version=version,
        status=SolveStatus.FEASIBLE,
        input_fingerprint="a" * 64,
        valid_schedule=True,
        validation=ValidationReport(valid=True),
        metadata=SolverRunMetadataV12(solver_executed=True),
        quality=QualityReport(policy_version=policy, status="NOT_REQUESTED", score=score),
    ).model_dump(mode="json")


def test_output_15_pairs() -> None:
    r = ScheduleResult.model_validate(_result("1.5", "0.4", "1.2"))
    assert ScheduleResult.model_validate_json(r.model_dump_json()) == r
    for bad in (
        ("1.5", "0.4", "1.1"),
        ("1.4", "0.4", "1.2"),
        ("1.5", "0.3", "1.2"),
        ("1.4", "0.3", "1.2"),
    ):
        with pytest.raises(ValidationError):
            ScheduleResult.model_validate(_result(*bad))
