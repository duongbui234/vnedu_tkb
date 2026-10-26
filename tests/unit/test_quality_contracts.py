"""Version migration and explicit preference semantics."""

import copy
from typing import Any

import pytest
from pydantic import ValidationError

from tkb_core.contracts.input import ScheduleInput


def test_v10_hash_and_payload_unchanged(problem_data: dict[str, Any]) -> None:
    p = ScheduleInput.model_validate(problem_data)
    assert p.fingerprint() == "77851bfa1fa34e4155969ee7749117415de0fd90e6de743fd7267f5ec194eee1"
    assert "policy_version" not in p.model_dump()["constraint_config"]


def test_v11_config_roundtrip(quality_data: dict[str, Any]) -> None:
    p = ScheduleInput.model_validate(quality_data)
    assert p.constraint_config.policy_version == "0.1"
    assert p.constraint_config.soft[0].priority == 1
    assert ScheduleInput.model_validate_json(p.model_dump_json()) == p


@pytest.mark.parametrize(
    "field,value",
    [
        ("priority", True),
        ("priority", 0),
        ("priority", 4),
        ("weight", 1.5),
        ("weight", "2"),
        ("weight", False),
    ],
)
def test_strict_envelope(quality_data: dict[str, Any], field: str, value: Any) -> None:
    quality_data["constraint_config"]["soft"][0][field] = value
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(quality_data)


def test_known_disabled_bad_parameters(quality_data: dict[str, Any]) -> None:
    r = quality_data["constraint_config"]["soft"][0]
    r["enabled"] = False
    r["parameters"]["typo"] = 1
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(quality_data)


def test_duplicate_id_and_references(quality_data: dict[str, Any]) -> None:
    rules = quality_data["constraint_config"]["soft"]
    rules.append(copy.deepcopy(rules[0]))
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(quality_data)
    rules.pop()
    rules[0]["parameters"]["slot_ids"] = ["unknown"]
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(quality_data)


def test_v11_hash_sets_and_unknown_arrays(quality_data: dict[str, Any]) -> None:
    r = quality_data["constraint_config"]["soft"][0]
    r["parameters"]["slot_ids"] = [s["id"] for s in quality_data["time_slots"]]
    a = ScheduleInput.model_validate(quality_data).fingerprint()
    r["parameters"]["slot_ids"].reverse()
    assert ScheduleInput.model_validate(quality_data).fingerprint() == a
    r.update(code="UNKNOWN", enabled=False, parameters={"ordered": [1, 2]})
    b = ScheduleInput.model_validate(quality_data).fingerprint()
    r["parameters"]["ordered"].reverse()
    assert ScheduleInput.model_validate(quality_data).fingerprint() != b


def test_no_implicit_config_or_legacy_priority(
    quality_data: dict[str, Any], problem_data: dict[str, Any]
) -> None:
    del quality_data["constraint_config"]
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(quality_data)
    problem_data["constraint_config"] = {"soft": [{"code": "x", "weight": 1, "priority": 1}]}
    with pytest.raises(ValidationError):
        ScheduleInput.model_validate(problem_data)


def test_effective_scopes_and_unsupported(quality_data: dict[str, Any]) -> None:
    from tkb_core.constraints.registry import validate_rule_config
    from tkb_core.domain.errors import CoreError

    r = quality_data["constraint_config"]["soft"][0]
    other = copy.deepcopy(r)
    other["id"] = "second"
    other["scope"] = {}
    quality_data["constraint_config"]["soft"].append(other)
    with pytest.raises(CoreError) as err:
        validate_rule_config(ScheduleInput.model_validate(quality_data))
    assert err.value.diagnostics[0].code == "OVERLAPPING_RULES"
    other["enabled"] = False
    validate_rule_config(ScheduleInput.model_validate(quality_data))
    r["scope"]["class_ids"] = [quality_data["classes"][0]["id"]]
    with pytest.raises(CoreError) as err:
        validate_rule_config(ScheduleInput.model_validate(quality_data))
    assert err.value.diagnostics[0].code == "RULE_SCOPE"
