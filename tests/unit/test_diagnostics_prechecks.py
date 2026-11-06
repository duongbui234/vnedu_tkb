"""Diagnostic prechecks and their independent verifier (Phase 3B spec §5, Task 3)."""

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tkb_core.contracts.diagnostics import LIMITATIONS, InfeasibilityReport, PrecheckProof
from tkb_core.contracts.input import ScheduleInput
from tkb_core.diagnostics.domains import build_domains
from tkb_core.diagnostics.prechecks import run_prechecks
from tkb_core.domain.errors import CoreError
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.preprocessing.normalize import normalize
from tkb_core.validation.precheck_verifier import check_explanation, recompute_precheck_proofs

FIXTURES = Path(__file__).parents[1] / "fixtures"


def base(**update: Any) -> dict[str, Any]:
    """Two days x AM x 3 periods; one class, one teacher, one requirement."""
    data: dict[str, Any] = {
        "schema_version": "1.1",
        "school": {"school_id": "s", "academic_year": "y", "term": "t"},
        "time_slots": [
            {"id": f"{d}-AM-{p}", "day": d, "session": "AM", "period": p}
            for d in (1, 2)
            for p in (1, 2, 3)
        ],
        "classes": [{"id": "c", "size": 10}],
        "teachers": [{"id": "t"}],
        "subjects": [{"id": "sub"}],
        "teaching_requirements": [
            {
                "id": "r",
                "class_ids": ["c"],
                "teacher_ids": ["t"],
                "subject_id": "sub",
                "periods_per_cycle": 4,
            }
        ],
        "constraint_config": {"policy_version": "0.3", "hard": [], "soft": []},
    }
    data.update(update)
    return data


def proofs(data: dict[str, Any]) -> list[tuple[str, str | None, tuple[str, ...], int, int]]:
    problem = ScheduleInput.model_validate(data)
    domains = build_domains(
        normalize(problem), expanded=False, max_placements=10**5, max_occupancy_terms=10**6
    )
    found = run_prechecks(domains)
    assert found == recompute_precheck_proofs(problem), "verifier disagrees"
    return [(p.code, p.rule_id, p.resource_ids, p.required, p.available) for p in found]


def test_clean_input_has_no_proof() -> None:
    assert proofs(base()) == []


def test_resource_capacity_lists_class_and_teacher_and_edge() -> None:
    data = base()
    data["teachers"][0]["available_slot_ids"] = ["1-AM-1", "1-AM-2", "1-AM-3"]
    # The class only has this teacher's lessons, so its usable slots shrink too.
    assert proofs(data) == [
        ("PC_RESOURCE_CAPACITY", None, ("c",), 4, 3),
        ("PC_RESOURCE_CAPACITY", None, ("t",), 4, 3),
    ]
    data["teaching_requirements"][0]["periods_per_cycle"] = 3
    assert proofs(data) == []  # exactly enough
    data = base()
    data["teaching_requirements"][0]["periods_per_cycle"] = 7
    assert proofs(data) == [
        ("PC_RESOURCE_CAPACITY", None, ("c",), 7, 6),
        ("PC_RESOURCE_CAPACITY", None, ("t",), 7, 6),
    ]


def test_empty_domain_from_lock_and_availability_and_all_listed() -> None:
    data = base()
    data["teachers"][0]["available_slot_ids"] = ["1-AM-1", "1-AM-2", "2-AM-1", "2-AM-2"]
    data["locked_assignments"] = [
        {"occurrence_id": "r::1", "slot_id": "1-AM-3"},
        {"occurrence_id": "r::2", "slot_id": "2-AM-3"},
    ]
    found = proofs(data)
    assert found[:2] == [
        ("PC_EMPTY_DOMAIN", None, (), 1, 0),
        ("PC_EMPTY_DOMAIN", None, (), 1, 0),
    ]
    problem = ScheduleInput.model_validate(data)
    with pytest.raises(CoreError) as solve_error:
        prepare(problem)  # solve() keeps its own first-failure precheck and error code
    assert solve_error.value.diagnostics[0].code == "LOCK_CONFLICT"


def test_lock_overlap_reports_class_and_teacher() -> None:
    data = base()
    data["locked_assignments"] = [
        {"occurrence_id": "r::1", "slot_id": "1-AM-1"},
        {"occurrence_id": "r::2", "slot_id": "1-AM-1"},
    ]
    found = [p for p in proofs(data) if p[0] == "PC_LOCK_OVERLAP"]
    assert found == [
        ("PC_LOCK_OVERLAP", None, ("c",), 2, 1),
        ("PC_LOCK_OVERLAP", None, ("t",), 2, 1),
    ]


def test_room_capacity_by_type() -> None:
    data = base(
        manage_rooms=True,
        rooms=[{"id": "lab", "room_type": "lab", "capacity": 30, "available_slot_ids": ["1-AM-1"]}],
    )
    data["teaching_requirements"][0].update(
        periods_per_cycle=2, room_required=True, required_room_type="lab"
    )
    found = proofs(data)
    assert ("PC_ROOM_CAPACITY", None, ("lab",), 2, 1) in found


def _hard(code: str, parameters: dict[str, Any], **scope: Any) -> dict[str, Any]:
    return {"id": code.lower(), "code": code, "parameters": parameters, "scope": scope}


def test_hard_day_and_session_load() -> None:
    data = base()
    data["constraint_config"]["hard"] = [_hard("TEACHER_MAX_PERIODS_PER_DAY", {"limit": 1})]
    assert proofs(data) == [("PC_HARD_DAY_LOAD", "teacher_max_periods_per_day", ("t",), 4, 2)]
    data["constraint_config"]["hard"] = [_hard("TEACHER_MAX_PERIODS_PER_DAY", {"limit": 2})]
    assert proofs(data) == []  # 2 + 2 = 4, exactly enough
    data["constraint_config"]["hard"] = [
        _hard("TEACHER_MAX_PERIODS_PER_SESSION", {"limit": 1, "session_ids": ["AM"]})
    ]
    assert proofs(data) == [
        ("PC_HARD_SESSION_LOAD", "teacher_max_periods_per_session", ("t",), 4, 2)
    ]


def test_hard_subject_day_and_day_spread() -> None:
    data = base()
    data["constraint_config"]["hard"] = [_hard("CLASS_SUBJECT_MAX_PERIODS_PER_DAY", {"limit": 1})]
    assert proofs(data) == [
        ("PC_HARD_SUBJECT_DAY", "class_subject_max_periods_per_day", ("c", "sub"), 4, 2)
    ]
    data = base()
    data["teaching_requirements"][0]["periods_per_cycle"] = 3
    data["constraint_config"]["hard"] = [
        _hard("SUBJECT_COMPONENT_DAY_SPREAD", {"requirement_ids": ["r"], "min_day_gap": 1})
    ]
    assert proofs(data) == [("PC_HARD_DAY_SPREAD", "subject_component_day_spread", ("r",), 3, 2)]


def test_hard_placement_rule_filters_usable_slots() -> None:
    data = base()
    data["constraint_config"]["hard"] = [
        _hard(
            "TEACHER_PREFERRED_PERIOD_WINDOW",
            {"first_period": 1, "last_period": 1, "session_ids": ["AM"]},
        )
    ]
    assert proofs(data) == [
        ("PC_RESOURCE_CAPACITY", None, ("c",), 4, 2),
        ("PC_RESOURCE_CAPACITY", None, ("t",), 4, 2),
    ]


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.glob("*.json")))
def test_verifier_agrees_on_every_fixture(name: str) -> None:
    data = json.loads((FIXTURES / name).read_text())
    try:
        problem = ScheduleInput.model_validate(data)
        normalized = normalize(problem)
        domains = build_domains(
            normalized, expanded=False, max_placements=10**5, max_occupancy_terms=10**6
        )
    except (CoreError, ValueError):
        pytest.skip("input refused before diagnosis")
    assert run_prechecks(domains) == recompute_precheck_proofs(problem)


def _report(data: dict[str, Any], found: tuple[PrecheckProof, ...]) -> InfeasibilityReport:
    return InfeasibilityReport(
        schema_version="1.0",
        status="PRECHECK_PROOF",
        input_fingerprint=ScheduleInput.model_validate(data).fingerprint(),
        granularity="MODEL",
        precheck_proofs=found,
        evidence={"infeasibility": "ARITHMETIC"},  # type: ignore[arg-type]
        metadata={  # type: ignore[arg-type]
            "solver_version": None,
            "seed": 1,
            "num_workers": 1,
            "time_limit_seconds": 1.0,
            "wall_time": 0.0,
            "solver_calls": 0,
        },
        limitations=LIMITATIONS,
    )


def test_check_explanation_rejects_forged_or_stale_reports() -> None:
    data = base()
    data["teaching_requirements"][0]["periods_per_cycle"] = 7
    problem = ScheduleInput.model_validate(data)
    genuine = recompute_precheck_proofs(problem)
    assert check_explanation(problem, _report(data, genuine)) == ()
    forged = (genuine[0].model_copy(update={"available": 5}),)
    assert check_explanation(problem, _report(data, forged)) == ("PRECHECK_MISMATCH",)
    other = copy.deepcopy(data)
    other["teaching_requirements"][0]["periods_per_cycle"] = 8
    assert check_explanation(ScheduleInput.model_validate(other), _report(data, genuine)) == (
        "STALE_REPORT",
    )


def test_verifier_never_imports_solver_preprocessing_or_diagnostics() -> None:
    script = """
import builtins
original = builtins.__import__
blocked = ('ortools', 'tkb_core.solver', 'tkb_core.constraints', 'tkb_core.preprocessing',
           'tkb_core.repair', 'tkb_core.diagnostics')
def guarded(name, *args, **kwargs):
    if name.startswith(blocked):
        raise ImportError('forbidden import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from tkb_core.validation.precheck_verifier import recompute_precheck_proofs, check_explanation
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
