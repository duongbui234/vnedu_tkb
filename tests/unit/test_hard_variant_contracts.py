"""Policy 0.2 contracts, capability matrix and cross-mode overlap (Phase 2B)."""

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from tkb_core.constraints.registry import DEFINITIONS, supports_mode, validate_rule_config
from tkb_core.contracts.capabilities import check_capabilities
from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult, SolverRunMetadataV12, ValidationReport
from tkb_core.contracts.score import QualityReport, ScoreReport
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.errors import CoreError

DAY = {"id": "h-day", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 3}}
SOFT_DAY = {**DAY, "id": "s-day", "priority": 1, "weight": 1}


def _code(data: dict[str, Any]) -> str:
    with pytest.raises(CoreError) as err:
        check_capabilities(ScheduleInput.model_validate(data))
    return err.value.diagnostics[0].code


def test_policy_versions_dispatch(hard_case: dict[str, Any]) -> None:
    p = ScheduleInput.model_validate(hard_case)
    assert p.constraint_config.policy_version == "0.2"
    assert ScheduleInput.model_validate_json(p.model_dump_json()) == p
    hard_case["constraint_config"]["policy_version"] = "0.9"
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(hard_case)


@pytest.mark.parametrize("field,value", [("priority", 1), ("weight", 1)])
def test_hard_envelope_rejects_soft_fields(
    hard_case: dict[str, Any], field: str, value: int
) -> None:
    hard_case["constraint_config"]["hard"] = [{**DAY, field: value}]
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(hard_case)


def test_hard_bad_parameters_even_disabled(hard_case: dict[str, Any]) -> None:
    hard_case["constraint_config"]["hard"] = [{**DAY, "enabled": False, "parameters": {}}]
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(hard_case)


def test_capability_matrix(quality_case: dict[str, Any]) -> None:
    quality_case["constraint_config"]["hard"] = [DAY]
    assert _code(quality_case) == "CUSTOM_HARD_RULE"
    quality_case["constraint_config"]["policy_version"] = "0.2"
    check_capabilities(ScheduleInput.model_validate(quality_case))
    quality_case["constraint_config"]["hard"] = [{"id": "x", "code": "NEW_RULE"}]
    assert _code(quality_case) == "UNKNOWN_RULE"
    quality_case["constraint_config"]["hard"] = [{**DAY, "scope": {"class_ids": ["c"]}}]
    assert _code(quality_case) == "RULE_SCOPE"
    quality_case["constraint_config"]["hard"] = [{"id": "x", "code": "NEW_RULE", "enabled": False}]
    check_capabilities(ScheduleInput.model_validate(quality_case))


def test_mode_support_by_policy() -> None:
    for code in [c for c, d in DEFINITIONS.items() if d.policy_id in ("S01", "S02", "S03", "S04")]:
        assert supports_mode(code, "soft", "0.1") and supports_mode(code, "soft", "0.2")
        assert not supports_mode(code, "hard", "0.1")
        assert supports_mode(code, "hard", "0.2")
    assert not supports_mode("NEW_RULE", "hard", "0.2")


def test_overlap_any_mode(hard_case: dict[str, Any]) -> None:
    config = hard_case["constraint_config"]
    config["hard"], config["soft"] = [DAY], [SOFT_DAY]
    with pytest.raises(CoreError) as err:
        validate_rule_config(ScheduleInput.model_validate(hard_case))
    assert err.value.diagnostics[0].code == "OVERLAPPING_RULES"
    config["soft"] = []
    config["hard"] = [DAY, {**DAY, "id": "h-day-2", "parameters": {"limit": 1}}]
    with pytest.raises(CoreError):
        validate_rule_config(ScheduleInput.model_validate(hard_case))
    config["hard"][1]["enabled"] = False
    validate_rule_config(ScheduleInput.model_validate(hard_case))
    # Different families combine; session sets that do not intersect do not overlap.
    config["hard"] = [
        DAY,
        {
            "id": "h-am",
            "code": "TEACHER_MAX_PERIODS_PER_SESSION",
            "parameters": {"limit": 2, "session_ids": ["AM"]},
        },
    ]
    config["soft"] = [
        {
            "id": "s-pm",
            "code": "TEACHER_MAX_PERIODS_PER_SESSION",
            "parameters": {"limit": 2, "session_ids": ["PM"]},
            "priority": 1,
            "weight": 1,
        }
    ]
    validate_rule_config(ScheduleInput.model_validate(hard_case))
    config["soft"][0]["parameters"]["session_ids"] = ["PM", "AM"]
    with pytest.raises(CoreError):
        validate_rule_config(ScheduleInput.model_validate(hard_case))


def test_policy_01_hard_overlap_keeps_legacy_capability_error(
    quality_case: dict[str, Any],
) -> None:
    quality_case["constraint_config"]["hard"] = [DAY]
    quality_case["constraint_config"]["soft"] = [SOFT_DAY]
    assert _code(quality_case) == "CUSTOM_HARD_RULE"


def test_fingerprint_mode_and_policy(hard_case: dict[str, Any]) -> None:
    config = hard_case["constraint_config"]
    config["hard"] = [
        DAY,
        {
            "id": "h-avoid",
            "code": "TEACHER_AVOID_SLOTS",
            "parameters": {"slot_ids": ["1-AM-1", "1-AM-2"]},
        },
    ]
    a = ScheduleInput.model_validate(hard_case).fingerprint()
    config["hard"] = [copy.deepcopy(config["hard"][1]), DAY]
    config["hard"][0]["parameters"]["slot_ids"].reverse()
    assert ScheduleInput.model_validate(hard_case).fingerprint() == a
    config["hard"][1] = {**DAY, "enabled": False}
    assert ScheduleInput.model_validate(hard_case).fingerprint() != a
    config["hard"] = [config["hard"][0]]
    config["soft"] = [SOFT_DAY | {"id": "h-day"}]
    b = ScheduleInput.model_validate(hard_case).fingerprint()
    assert b != a
    config["policy_version"] = "0.1"
    assert ScheduleInput.model_validate(hard_case).fingerprint() != b


def _result(version: str, policy: str) -> dict[str, Any]:
    score = ScoreReport(status="OK", input_fingerprint="a" * 64, rules=(), tiers=(0, 0, 0))
    return ScheduleResult.model_construct(
        schema_version=version,
        status=SolveStatus.FEASIBLE,
        input_fingerprint="a" * 64,
        valid_schedule=True,
        validation=ValidationReport(valid=True),
        metadata=SolverRunMetadataV12(solver_executed=True),
        quality=QualityReport(policy_version=policy, status="NOT_REQUESTED", score=score),
    ).model_dump(mode="json")


def test_output_13_pairs_with_policy_02() -> None:
    r = ScheduleResult.model_validate(_result("1.3", "0.2"))
    assert ScheduleResult.model_validate_json(r.model_dump_json()) == r
    assert r.model_dump()["quality"]["policy_version"] == "0.2"
    ScheduleResult.model_validate(_result("1.2", "0.1"))
    for version, policy in (("1.2", "0.2"), ("1.3", "0.1")):
        with pytest.raises(ValidationError):
            ScheduleResult.model_validate(_result(version, policy))
    data = _result("1.3", "0.2")
    data["metadata"].pop("feasibility_run")
    ScheduleResult.model_validate(data)
    del data["quality"]
    with pytest.raises(ValidationError):
        ScheduleResult.model_validate(data)
