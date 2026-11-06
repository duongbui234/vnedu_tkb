"""explain_infeasibility(): hand-computed conflicts, budget, feasibility and invariants (3B)."""

import json
from pathlib import Path
from typing import Any

import pytest

from tkb_core.contracts.diagnostics import ExplainOptions, InfeasibilityReport
from tkb_core.contracts.input import ScheduleInput
from tkb_core.diagnostics import model as diagnostic_model
from tkb_core.diagnostics.domains import build_domains
from tkb_core.diagnostics.groups import enumerate_groups
from tkb_core.diagnostics.model import SubsetOutcome, build_diagnostic_model, solve_subset
from tkb_core.diagnostics.pipeline import explain_infeasibility
from tkb_core.domain.errors import CoreError
from tkb_core.preprocessing.normalize import normalize
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.precheck_verifier import check_explanation

FIXTURES = Path(__file__).parents[1] / "fixtures"


def explain(
    data: dict[str, Any], granularity: str = "MODEL", seconds: float = 10.0
) -> InfeasibilityReport:
    options = ExplainOptions.model_validate(
        {"time_limit_seconds": seconds, "seed": 42, "granularity": granularity}
    )
    return explain_infeasibility(ScheduleInput.model_validate(data), options)


def subset(report: InfeasibilityReport) -> list[tuple[str, str]]:
    return [(g.kind, g.id) for g in report.subset]


TRIANGLE = [
    ("CLASS_OCCUPANCY", "c1"),
    ("DEMAND", "r1"),
    ("DEMAND", "r2"),
    ("DEMAND", "r3"),
    ("ROOM_OCCUPANCY", "lab"),
    ("TEACHER_OCCUPANCY", "t1"),
]


@pytest.mark.parametrize("granularity", ["MODEL", "FULL"])
def test_triangle_conflict_is_a_proved_minimal_subset(
    triangle_case: dict[str, Any], granularity: str
) -> None:
    report = explain(triangle_case, granularity)
    assert report.status == "CORE_SUBSET" and report.minimal_proved
    assert subset(report) == TRIANGLE
    assert report.evidence is not None and report.evidence.infeasibility == "SOLVER"
    assert all(w.validator_valid for w in report.evidence.minimality_witnesses)
    assert report.metadata.num_workers == 1 and report.metadata.solver_calls >= 2
    # solve() agrees that the input is infeasible.
    assert solve(ScheduleInput.model_validate(triangle_case), SolveOptions()).status == "INFEASIBLE"


def test_spread_conflict_model_versus_full(spread_case: dict[str, Any]) -> None:
    model = explain(spread_case, "MODEL")
    assert model.status == "CORE_SUBSET" and model.minimal_proved
    assert subset(model) == [
        ("DEMAND", "r"),
        ("DEMAND", "r3"),
        ("HARD_RULE", "spread"),
        ("TEACHER_OCCUPANCY", "t1"),
    ]
    full = explain(spread_case, "FULL")
    assert full.status == "CORE_SUBSET" and full.minimal_proved
    assert subset(full) == [
        ("DEMAND", "r"),
        ("DEMAND", "r3"),
        ("HARD_RULE", "spread"),
        ("LOCK", "r3::1"),
        ("TEACHER_OCCUPANCY", "t1"),
    ]


def test_counting_conflict_stops_at_prechecks_without_solver(triangle_case: dict[str, Any]) -> None:
    triangle_case["teaching_requirements"][0]["periods_per_cycle"] = 3
    report = explain(triangle_case)
    assert report.status == "PRECHECK_PROOF"
    assert report.metadata.solver_calls == 0 and report.metadata.solver_version is None
    assert {p.code for p in report.precheck_proofs} == {"PC_RESOURCE_CAPACITY"}


def test_feasible_input_is_not_infeasible_and_carries_no_schedule(
    triangle_case: dict[str, Any],
) -> None:
    triangle_case["time_slots"].append({"id": "d1p3", "day": 1, "session": "AM", "period": 3})
    report = explain(triangle_case, "FULL")
    assert report.status == "NOT_INFEASIBLE"
    assert report.subset == () and report.evidence is None
    assert "assignments" not in report.model_dump()


def test_input_errors_are_raised_unchanged(triangle_case: dict[str, Any]) -> None:
    triangle_case["teaching_requirements"][0].update(periods_per_cycle=3, block_durations=[3])
    with pytest.raises(CoreError) as error:
        explain(triangle_case)
    assert error.value.status == "UNSUPPORTED_FEATURE"


def test_resource_limit_is_reported(triangle_case: dict[str, Any]) -> None:
    options = ExplainOptions(time_limit_seconds=5.0, seed=1, granularity="FULL", max_placements=1)
    report = explain_infeasibility(ScheduleInput.model_validate(triangle_case), options)
    assert report.status == "RESOURCE_LIMIT" and report.evidence is None


def test_unknown_deletion_never_claims_minimality(
    triangle_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}
    real = solve_subset

    def flaky(*args: Any, **kwargs: Any) -> SubsetOutcome:
        calls["n"] += 1
        if calls["n"] <= 2:  # first full solve and the confirmation
            return real(*args, **kwargs)
        return SubsetOutcome("UNKNOWN", (), ())

    monkeypatch.setattr("tkb_core.diagnostics.pipeline.solve_subset", flaky)
    report = explain(triangle_case)
    assert report.status == "CORE_SUBSET" and not report.minimal_proved
    assert subset(report) == TRIANGLE
    assert [(g.kind, g.id) for g in report.unresolved] == TRIANGLE


def test_unknown_first_solve_is_unknown(
    triangle_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "tkb_core.diagnostics.pipeline.solve_subset",
        lambda *a, **k: SubsetOutcome("UNKNOWN", (), ()),
    )
    report = explain(triangle_case)
    assert report.status == "UNKNOWN" and report.subset == ()


def test_exhausted_budget_skips_the_solver(triangle_case: dict[str, Any]) -> None:
    """F5: once preparation used the whole budget, no solver call is made."""
    report = explain(triangle_case, seconds=1e-9)
    assert report.status == "UNKNOWN" and report.metadata.solver_calls == 0


def _busy_teacher() -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "school": {"school_id": "s", "academic_year": "y", "term": "t"},
        "time_slots": [
            {"id": f"s{i}", "day": 1, "session": "AM", "period": i} for i in range(1, 7)
        ],
        "classes": [{"id": "c"}],
        "teachers": [{"id": "t", "available_slot_ids": ["s1", "s2"]}],
        "subjects": [{"id": "x"}],
        "teaching_requirements": [
            {
                "id": "r",
                "class_ids": ["c"],
                "teacher_ids": ["t"],
                "subject_id": "x",
                "periods_per_cycle": 3,
            }
        ],
        "constraint_config": {"policy_version": "0.3", "hard": [], "soft": []},
    }


@pytest.mark.parametrize("granularity", ["MODEL", "FULL"])
def test_prechecks_run_before_the_expanded_domain_guard(granularity: str) -> None:
    """F1: the FULL domain may exceed the guard, but counting proofs come first."""
    options = ExplainOptions.model_validate(
        {"time_limit_seconds": 5.0, "seed": 1, "granularity": granularity, "max_placements": 10}
    )
    problem = ScheduleInput.model_validate(_busy_teacher())
    report = explain_infeasibility(problem, options)
    assert report.status == "PRECHECK_PROOF"
    assert check_explanation(problem, report) == ()


def test_resource_limit_report_passes_its_own_check(triangle_case: dict[str, Any]) -> None:
    """F1: when even the clean domain hits the guard, RESOURCE_LIMIT is a valid report."""
    triangle_case["teaching_requirements"][0]["periods_per_cycle"] = 3
    problem = ScheduleInput.model_validate(triangle_case)
    options = ExplainOptions(time_limit_seconds=5.0, seed=1, granularity="MODEL", max_placements=8)
    report = explain_infeasibility(problem, options)
    assert report.status == "RESOURCE_LIMIT"
    assert check_explanation(problem, report) == ()


def test_repeat_is_deterministic(spread_case: dict[str, Any]) -> None:
    first = explain(spread_case, "FULL").model_dump(exclude={"metadata"})
    second = explain(spread_case, "FULL").model_dump(exclude={"metadata"})
    assert first == second


def _full_model_status(data: dict[str, Any]) -> str:
    problem = ScheduleInput.model_validate(data)
    domains = build_domains(
        normalize(problem), expanded=False, max_placements=10**5, max_occupancy_terms=10**6
    )
    groups = enumerate_groups(problem, "MODEL")
    built = build_diagnostic_model(domains, groups)
    return solve_subset(built, {(g.kind, g.id) for g in groups}, 10.0, 42).status


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.glob("*.json")))
def test_all_on_model_matches_solve_status(name: str) -> None:
    """With every literal on, the MODEL diagnostic model agrees with solve() hard status."""
    data = json.loads((FIXTURES / name).read_text())
    try:
        problem = ScheduleInput.model_validate(data)
        normalize(problem)
    except (CoreError, ValueError):
        pytest.skip("input refused before diagnosis")
    result = solve(problem, SolveOptions(time_limit_seconds=10.0))
    try:
        status = _full_model_status(data)
    except CoreError:
        assert result.status in ("INFEASIBLE", "INPUT_INVALID")
        return
    expected = {"OPTIMAL": "FEASIBLE", "FEASIBLE": "FEASIBLE"}.get(result.status, result.status)
    assert status == expected


def test_diagnostic_model_does_not_touch_solve_modules() -> None:
    assert diagnostic_model.__name__ == "tkb_core.diagnostics.model"
    import tkb_core.solver.model_builder as builder

    assert not hasattr(builder, "build_diagnostic_model")
