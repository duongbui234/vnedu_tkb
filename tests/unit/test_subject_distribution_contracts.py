"""Policy 0.3 contracts, versions, scope and overlap for S05/S06 (Phase 2C-1)."""

import copy
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

SPREAD = {
    "id": "spread",
    "code": "SUBJECT_COMPONENT_DAY_SPREAD",
    "parameters": {"requirement_ids": ["r"], "min_day_gap": 1},
}
SUBJECT_DAY = {
    "id": "subject-day",
    "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY",
    "parameters": {"limit": 2},
}


def _soft(rule: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {**rule, "priority": 1, "weight": 1, **extra}


def _error(data: dict[str, Any]) -> str:
    with pytest.raises(CoreError) as err:
        check_capabilities(ScheduleInput.model_validate(data))
    return err.value.diagnostics[0].code


def test_policy_03_roundtrip_and_unknown_version(dist_case: dict[str, Any]) -> None:
    dist_case["constraint_config"]["soft"] = [_soft(SPREAD)]
    dist_case["constraint_config"]["hard"] = [SUBJECT_DAY]
    p = ScheduleInput.model_validate(dist_case)
    assert ScheduleInput.model_validate_json(p.model_dump_json()) == p
    check_capabilities(p)
    dist_case["constraint_config"]["policy_version"] = "0.4"
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(dist_case)


@pytest.mark.parametrize("policy", ["0.1", "0.2"])
@pytest.mark.parametrize("mode", ["soft", "hard"])
def test_older_policies_treat_new_codes_as_unknown(
    dist_case: dict[str, Any], policy: str, mode: str
) -> None:
    dist_case["constraint_config"]["policy_version"] = policy
    rule = _soft(SPREAD) if mode == "soft" else SPREAD
    dist_case["constraint_config"][mode] = [rule]
    expected = "UNKNOWN_RULE" if (mode == "soft" or policy == "0.2") else "CUSTOM_HARD_RULE"
    assert _error(dist_case) == expected


def test_older_policies_keep_disabled_new_code_payload_raw(quality_case: dict[str, Any]) -> None:
    # Before 2C-1 the code was unknown: arbitrary disabled params were kept unparsed.
    rule = _soft(SPREAD, enabled=False, parameters={"anything": [3, 1, 2]})
    quality_case["constraint_config"]["soft"] = [rule]
    a = ScheduleInput.model_validate(quality_case).fingerprint()
    rule["parameters"]["anything"].reverse()
    assert ScheduleInput.model_validate(quality_case).fingerprint() != a


def test_mode_support_matrix() -> None:
    for code in ("SUBJECT_COMPONENT_DAY_SPREAD", "CLASS_SUBJECT_MAX_PERIODS_PER_DAY"):
        for mode in ("soft", "hard"):
            assert supports_mode(code, mode, "0.3")
            assert not supports_mode(code, mode, "0.2")
            assert not supports_mode(code, mode, "0.1")
    assert supports_mode("TEACHER_AVOID_SLOTS", "hard", "0.3")
    assert supports_mode("TEACHER_AVOID_SLOTS", "soft", "0.3")


@pytest.mark.parametrize(
    "rule",
    [
        {**SPREAD, "parameters": {"requirement_ids": ["r"], "min_day_gap": 0}},
        {**SPREAD, "parameters": {"requirement_ids": [], "min_day_gap": 1}},
        {**SPREAD, "parameters": {"requirement_ids": ["r", "r"], "min_day_gap": 1}},
        {**SPREAD, "parameters": {"requirement_ids": ["unknown"], "min_day_gap": 1}},
        {**SPREAD, "parameters": {"requirement_ids": ["r"], "min_day_gap": True}},
        {**SUBJECT_DAY, "parameters": {"limit": -1}},
        {**SUBJECT_DAY, "parameters": {"limit": 2, "extra": 1}},
    ],
)
def test_parameter_contracts(dist_case: dict[str, Any], rule: dict[str, Any]) -> None:
    dist_case["constraint_config"]["hard"] = [{**rule, "enabled": False}]
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(dist_case)


@pytest.mark.parametrize(
    "rule",
    [
        {**SPREAD, "scope": {"class_ids": ["c"]}},
        {**SPREAD, "scope": {"teacher_ids": ["t"]}},
        {**SUBJECT_DAY, "scope": {"teacher_ids": ["t"]}},
        {**SUBJECT_DAY, "scope": {"room_ids": []} | {"teacher_ids": ["t"]}},
    ],
)
def test_family_scopes(dist_case: dict[str, Any], rule: dict[str, Any]) -> None:
    dist_case["constraint_config"]["hard"] = [rule]
    assert _error(dist_case) == "RULE_SCOPE"


def test_subject_day_class_and_subject_scope_allowed(dist_case: dict[str, Any]) -> None:
    rule = {**SUBJECT_DAY, "scope": {"class_ids": ["c"], "subject_ids": ["sub"]}}
    dist_case["constraint_config"]["hard"] = [rule]
    check_capabilities(ScheduleInput.model_validate(dist_case))
    # S01-S04 still accept only teacher scope under policy 0.3.
    dist_case["constraint_config"]["hard"] = [
        {
            "id": "x",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 1},
            "scope": {"class_ids": ["c"]},
        }
    ]
    assert _error(dist_case) == "RULE_SCOPE"


def _overlap(data: dict[str, Any]) -> bool:
    try:
        validate_rule_config(ScheduleInput.model_validate(data))
    except CoreError as exc:
        assert exc.diagnostics[0].code == "OVERLAPPING_RULES"
        return True
    return False


def test_spread_overlap_by_shared_requirement(dist_case: dict[str, Any]) -> None:
    dist_case["teaching_requirements"].append(
        {**dist_case["teaching_requirements"][0], "id": "r2", "block_durations": [1, 1, 1, 1]}
    )
    config = dist_case["constraint_config"]
    config["hard"] = [SPREAD]
    config["soft"] = [
        _soft(SPREAD, id="s2", parameters={"requirement_ids": ["r2", "r"], "min_day_gap": 2})
    ]
    assert _overlap(dist_case)
    config["soft"][0]["parameters"]["requirement_ids"] = ["r2"]
    assert not _overlap(dist_case)
    config["hard"].append(
        {**SPREAD, "id": "h2", "parameters": {"requirement_ids": ["r"], "min_day_gap": 1}}
    )
    assert _overlap(dist_case)


def test_subject_day_overlap_by_class_subject(dist_case: dict[str, Any]) -> None:
    dist_case["classes"].append({"id": "c2"})
    dist_case["subjects"].append({"id": "sub2"})
    config = dist_case["constraint_config"]
    config["hard"] = [{**SUBJECT_DAY, "scope": {"class_ids": ["c"]}}]
    config["soft"] = [_soft(SUBJECT_DAY, id="s", scope={"class_ids": ["c2"]})]
    assert not _overlap(dist_case)
    config["soft"][0]["scope"] = {"subject_ids": ["sub2"]}
    assert _overlap(dist_case)  # (c, sub2) is in both
    config["hard"][0]["scope"] = {"class_ids": ["c"], "subject_ids": ["sub"]}
    assert not _overlap(dist_case)
    # Different families combine freely.
    config["soft"] = [_soft(SPREAD)]
    config["hard"].append(
        {"id": "t", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 3}}
    )
    assert not _overlap(dist_case)


def test_fingerprint_sorts_requirement_ids(dist_case: dict[str, Any]) -> None:
    dist_case["teaching_requirements"].append({**dist_case["teaching_requirements"][0], "id": "r2"})
    rule = copy.deepcopy(SPREAD)
    rule["parameters"]["requirement_ids"] = ["r", "r2"]
    dist_case["constraint_config"]["hard"] = [rule]
    a = ScheduleInput.model_validate(dist_case).fingerprint()
    rule["parameters"]["requirement_ids"].reverse()
    assert ScheduleInput.model_validate(dist_case).fingerprint() == a
    rule["parameters"]["min_day_gap"] = 2
    assert ScheduleInput.model_validate(dist_case).fingerprint() != a


def _row(unit: str) -> RuleScore:
    return RuleScore(
        rule_id="x", code="c", priority=1, weight=1, unit=unit, raw_penalty=1, weighted_penalty=1
    )


def test_score_report_units_by_version() -> None:
    ok = {"status": "OK", "input_fingerprint": "a" * 64, "tiers": (1, 0, 0)}
    ScoreReport(schema_version="1.1", rules=(_row("day_gap_shortfall"),), **ok)
    ScoreReport(schema_version="1.0", rules=(_row("teaching_periods"),), **ok)
    with pytest.raises(ValidationError):
        ScoreReport(schema_version="1.0", rules=(_row("day_gap_shortfall"),), **ok)
    with pytest.raises(ValidationError):
        _row("days")


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


def test_output_14_pairs_policy_03_and_score_11() -> None:
    r = ScheduleResult.model_validate(_result("1.4", "0.3", "1.1"))
    assert ScheduleResult.model_validate_json(r.model_dump_json()) == r
    ScheduleResult.model_validate(_result("1.3", "0.2", "1.0"))
    for bad in (
        ("1.4", "0.3", "1.0"),
        ("1.3", "0.2", "1.1"),
        ("1.4", "0.2", "1.1"),
        ("1.3", "0.3", "1.1"),
        ("1.2", "0.1", "1.1"),
    ):
        with pytest.raises(ValidationError):
            ScheduleResult.model_validate(_result(*bad))
