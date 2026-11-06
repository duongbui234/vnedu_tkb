"""InfeasibilityReport 1.0: roundtrip, strictness and status/field consistency (Phase 3B)."""

from typing import Any

import pytest
from pydantic import ValidationError

from tkb_core.contracts.diagnostics import (
    LIMITATIONS,
    ExplainOptions,
    InfeasibilityReport,
)

FP = "a" * 64


def _meta() -> dict[str, Any]:
    return {
        "solver_version": "9.15.6755",
        "seed": 42,
        "num_workers": 1,
        "time_limit_seconds": 5.0,
        "wall_time": 0.5,
        "solver_calls": 3,
    }


def _proof() -> dict[str, Any]:
    return {
        "code": "PC_RESOURCE_CAPACITY",
        "rule_id": None,
        "resource_kind": "TEACHER",
        "resource_ids": ["t"],
        "occurrence_ids": [],
        "required": 4,
        "available": 3,
    }


def _core(**update: Any) -> dict[str, Any]:
    data = {
        "schema_version": "1.0",
        "status": "CORE_SUBSET",
        "input_fingerprint": FP,
        "granularity": "FULL",
        "subset": [{"kind": "DEMAND", "id": "r"}, {"kind": "TEACHER_AVAILABILITY", "id": "t"}],
        "minimal_proved": True,
        "unresolved": [],
        "evidence": {
            "infeasibility": "SOLVER",
            "minimality_witnesses": [
                {"group": {"kind": "DEMAND", "id": "r"}, "validator_valid": True},
                {"group": {"kind": "TEACHER_AVAILABILITY", "id": "t"}, "validator_valid": True},
            ],
        },
        "metadata": _meta(),
        "limitations": LIMITATIONS,
    }
    return data | update


def _proof_report(**update: Any) -> dict[str, Any]:
    data = {
        "schema_version": "1.0",
        "status": "PRECHECK_PROOF",
        "input_fingerprint": FP,
        "granularity": "MODEL",
        "precheck_proofs": [_proof()],
        "evidence": {"infeasibility": "ARITHMETIC", "minimality_witnesses": []},
        "metadata": _meta() | {"solver_calls": 0, "solver_version": None},
        "limitations": LIMITATIONS,
    }
    return data | update


def test_roundtrip_core_and_proof_reports() -> None:
    for data in (_core(), _proof_report()):
        report = InfeasibilityReport.model_validate(data)
        again = InfeasibilityReport.model_validate_json(report.model_dump_json())
        assert again == report


def test_no_assignments_field_and_unknown_fields_rejected() -> None:
    assert "assignments" not in InfeasibilityReport.model_fields
    with pytest.raises(ValidationError):
        InfeasibilityReport.model_validate(_core(assignments=[]))
    with pytest.raises(ValidationError):
        InfeasibilityReport.model_validate(_core(status="INFEASIBLE"))


@pytest.mark.parametrize(
    "update",
    [
        {"limitations": "Nguyên nhân duy nhất"},
        {"precheck_proofs": [_proof()]},
        {"subset": []},
        {"evidence": None},
        {"evidence": {"infeasibility": "ARITHMETIC", "minimality_witnesses": []}},
        {"unresolved": [{"kind": "DEMAND", "id": "other"}]},
        {"unresolved": [{"kind": "DEMAND", "id": "r"}]},  # minimal_proved yet unresolved
        {"evidence": {"infeasibility": "SOLVER", "minimality_witnesses": []}},
        {"subset": [{"kind": "DEMAND", "id": "r"}, {"kind": "DEMAND", "id": "r"}]},
        {"subset": [{"kind": "NOPE", "id": "r"}]},
    ],
)
def test_core_report_consistency(update: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        InfeasibilityReport.model_validate(_core(**update))


def test_unproved_core_may_have_unresolved_groups() -> None:
    report = InfeasibilityReport.model_validate(
        _core(
            minimal_proved=False,
            unresolved=[{"kind": "DEMAND", "id": "r"}],
            evidence={
                "infeasibility": "SOLVER",
                "minimality_witnesses": [
                    {"group": {"kind": "TEACHER_AVAILABILITY", "id": "t"}, "validator_valid": True}
                ],
            },
        )
    )
    assert not report.minimal_proved


@pytest.mark.parametrize(
    "update",
    [
        {"precheck_proofs": []},
        {"subset": [{"kind": "DEMAND", "id": "r"}]},
        {"minimal_proved": True},
        {"evidence": {"infeasibility": "SOLVER", "minimality_witnesses": []}},
        {"precheck_proofs": [_proof() | {"required": 3}]},
        {"precheck_proofs": [_proof() | {"code": "PC_NOPE"}]},
    ],
)
def test_proof_report_consistency(update: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        InfeasibilityReport.model_validate(_proof_report(**update))


@pytest.mark.parametrize("status", ["NOT_INFEASIBLE", "UNKNOWN", "RESOURCE_LIMIT"])
def test_non_infeasible_statuses_carry_no_claim(status: str) -> None:
    base = {
        "schema_version": "1.0",
        "status": status,
        "input_fingerprint": FP,
        "granularity": "MODEL",
        "metadata": _meta(),
        "limitations": LIMITATIONS,
    }
    assert InfeasibilityReport.model_validate(base).evidence is None
    for extra in (
        {"subset": [{"kind": "DEMAND", "id": "r"}]},
        {"precheck_proofs": [_proof()]},
        {"evidence": {"infeasibility": "SOLVER", "minimality_witnesses": []}},
    ):
        with pytest.raises(ValidationError):
            InfeasibilityReport.model_validate(base | extra)


def test_explain_options_require_every_decision() -> None:
    options = ExplainOptions(time_limit_seconds=2.0, seed=7, granularity="MODEL")
    assert options.max_placements == 100000
    for missing in ("time_limit_seconds", "seed", "granularity"):
        data: dict[str, Any] = {"time_limit_seconds": 2.0, "seed": 7, "granularity": "FULL"}
        del data[missing]
        with pytest.raises(ValidationError):
            ExplainOptions.model_validate(data)
    with pytest.raises(ValidationError):
        ExplainOptions(time_limit_seconds=0.0, seed=7, granularity="MODEL")
    with pytest.raises(ValidationError):
        ExplainOptions.model_validate({"time_limit_seconds": 1.0, "seed": 7, "granularity": "X"})
