"""Single-worker tier stages: sequential slice, interleaved remainder, sticky interleaving."""

import itertools
from typing import Any

import pytest

from tkb_core.constraints.soft import compile_soft
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.feasibility import PreparedProblem, prepare
from tkb_core.solver.model_builder import build_model
from tkb_core.solver.objectives import QualityOutcome, StageOutcome, run_quality
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.score_evaluator import _evaluate_validated

RULES = [
    {
        "id": "avoid",
        "code": "TEACHER_AVOID_SLOTS",
        "parameters": {"slot_ids": ["1-AM-1"]},
        "weight": 1,
        "priority": 1,
    },
    {
        "id": "load",
        "code": "TEACHER_MAX_PERIODS_PER_DAY",
        "parameters": {"limit": 3},
        "weight": 1,
        "priority": 2,
    },
    {
        "id": "window",
        "code": "TEACHER_PREFERRED_PERIOD_WINDOW",
        "parameters": {"first_period": 1, "last_period": 4, "session_ids": ["AM", "PM"]},
        "weight": 1,
        "priority": 3,
    },
]


def _schedule(session: str) -> tuple[ScheduleAssignment, ...]:
    return tuple(
        ScheduleAssignment(
            occurrence_id=f"r::{i}",
            slot_id=f"1-{session}-{start}",
            class_ids=("c",),
            teacher_ids=("t",),
        )
        for i, start in enumerate((1, 3, 4), 1)
    )


def _outcome(p: PreparedProblem, status: str, session: str) -> StageOutcome:
    aa = _schedule(session)
    score = _evaluate_validated(p.normalized.problem, aa)
    assert score.tiers is not None
    ok = status in ("OPTIMAL", "FEASIBLE")
    return StageOutcome(
        SolveStatus(status),
        aa if ok else (),
        {r.rule_id: (r.raw_penalty, r.weighted_penalty) for r in score.rules},
        {k: score.tiers[k - 1] for k in (1, 2, 3)},
        1.0,
        0.0,
    )


def _placements(p: PreparedProblem, built: Any, session: str) -> list[tuple[int, int]]:
    chosen = {a.occurrence_id: (a.slot_id, a.room_id) for a in _schedule(session)}
    return sorted(
        (v.index, int((pl.start_slot_id, pl.room_id) == chosen[o.id]))
        for o in p.normalized.occurrences
        for pl, v in zip(p.domains[o.id], built.variables[o.id], strict=True)
    )


def _run(
    quality_case: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    script: dict[tuple[int, str], tuple[str, str]],
    *,
    limit: float = 10.0,
    workers: int = 1,
) -> tuple[QualityOutcome, list[dict[str, Any]], PreparedProblem, Any]:
    """Run quality with scripted (priority, search) stage results on a 1.0s-per-tick clock.

    Feasibility and verification return the AM schedule; unscripted tiers prove PM.
    """
    quality_case["constraint_config"]["soft"] = RULES
    p = prepare(ScheduleInput.model_validate(quality_case))
    built = build_model(p)
    hard = built.model.clone()
    compiled = compile_soft(p, built)
    calls: list[dict[str, Any]] = []

    def fake(
        prepared: Any,
        built: Any,
        compiled: Any,
        options: Any,
        priority: Any,
        budget: float,
        *,
        model: Any = None,
        fix_hint: bool = False,
        search: str = "default",
    ) -> StageOutcome:
        hint = built.model.proto.solution_hint
        calls.append(
            {
                "priority": priority,
                "budget": budget,
                "search": search,
                "hint": sorted(zip(list(hint.vars), list(hint.values), strict=True)),
            }
        )
        if priority is None:
            return _outcome(p, "OPTIMAL", "AM")
        status, session = script.get((priority, search), ("OPTIMAL", "PM"))
        return _outcome(p, status, session)

    clock = itertools.count(0.0, 1.0)
    monkeypatch.setattr("tkb_core.solver.objectives.perf_counter", lambda: next(clock))
    monkeypatch.setattr("tkb_core.solver.objectives._run_stage", fake)
    options = SolveOptions(time_limit_seconds=limit, num_workers=workers)
    return run_quality(p, built, compiled, options, hard), calls, p, built


def _tier_calls(calls: list[dict[str, Any]]) -> list[tuple[int, str]]:
    return [(c["priority"], c["search"]) for c in calls if c["priority"] is not None]


def test_proved_slice_is_the_only_tier_solve(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    out, calls, _, _ = _run(quality_case, monkeypatch, {})
    assert out.status == "OPTIMAL" and out.quality.optimal_prefix == (1, 2, 3)
    assert [c["search"] for c in calls[:2]] == ["default", "default"]
    assert _tier_calls(calls) == [(1, "slice"), (2, "slice"), (3, "slice")]


def test_unproved_slice_continues_interleaved_from_its_incumbent(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    out, calls, p, built = _run(quality_case, monkeypatch, {(1, "slice"): ("FEASIBLE", "PM")})
    # Clock ticks: feasibility 0-1, verification 2-3, tier 1 measure 4-7 (slice 5-6),
    # tier 2 measure 8-9; tier 1 interleaves on what the slice left of its budget.
    assert [(c["priority"], c["search"], c["budget"]) for c in calls] == [
        (None, "default", 10.0),
        (None, "default", 9.0),
        (1, "slice", 8.0),
        (1, "interleave", 7.0),
        (2, "interleave", 5.0),
        (3, "interleave", 4.0),
    ]
    assert calls[2]["hint"] == _placements(p, built, "AM")
    assert calls[3]["hint"] == _placements(p, built, "PM")
    first = out.quality.tier_runs[0]
    assert first.raw_status == "OPTIMAL" and first.proved_optimal and first.wall_time == 2.0
    assert out.status == "OPTIMAL" and out.assignments == _schedule("PM")


def test_unknown_slice_interleaves_from_verified_incumbent(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    out, calls, p, built = _run(quality_case, monkeypatch, {(1, "slice"): ("UNKNOWN", "PM")})
    assert _tier_calls(calls)[:2] == [(1, "slice"), (1, "interleave")]
    assert calls[3]["hint"] == _placements(p, built, "AM")
    assert out.status == "OPTIMAL"


@pytest.mark.parametrize("status", ["INFEASIBLE", "MODEL_INVALID"])
def test_slice_errors_never_interleave(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    out, calls, _, _ = _run(quality_case, monkeypatch, {(1, "slice"): (status, "PM")})
    assert _tier_calls(calls) == [(1, "slice")]
    assert out.status == "MODEL_INVALID"


def test_exhausted_budget_after_slice_stops_unproved(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    out, calls, _, _ = _run(
        quality_case, monkeypatch, {(1, "slice"): ("FEASIBLE", "PM")}, limit=3.0
    )
    assert _tier_calls(calls) == [(1, "slice")]
    assert out.status == "FEASIBLE" and out.quality.tier_runs[0].raw_status == "FEASIBLE"
    assert out.assignments == _schedule("PM")


def test_failed_interleave_keeps_slice_incumbent(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    script = {(1, "slice"): ("FEASIBLE", "PM"), (1, "interleave"): ("UNKNOWN", "PM")}
    out, calls, _, _ = _run(quality_case, monkeypatch, script)
    assert _tier_calls(calls) == [(1, "slice"), (1, "interleave")]
    first = out.quality.tier_runs[0]
    assert first.raw_status == "FEASIBLE" and first.wall_time == 2.0
    assert out.status == "FEASIBLE" and out.assignments == _schedule("PM")


def test_worse_interleave_result_keeps_slice_incumbent(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    script = {(1, "slice"): ("FEASIBLE", "PM"), (1, "interleave"): ("FEASIBLE", "AM")}
    out, _, p, _ = _run(quality_case, monkeypatch, script)
    assert (
        _outcome(p, "FEASIBLE", "AM").tier_values[1] > _outcome(p, "FEASIBLE", "PM").tier_values[1]
    )
    assert out.status == "FEASIBLE" and out.assignments == _schedule("PM")


def test_interleaving_is_sticky_only_after_it_was_needed(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    out, calls, _, _ = _run(quality_case, monkeypatch, {(2, "slice"): ("FEASIBLE", "PM")})
    assert _tier_calls(calls) == [(1, "slice"), (2, "slice"), (2, "interleave"), (3, "interleave")]
    assert out.status == "OPTIMAL"


def test_multiple_workers_keep_one_default_solve_per_tier(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    out, calls, _, _ = _run(
        quality_case, monkeypatch, {(1, "default"): ("FEASIBLE", "PM")}, workers=2
    )
    assert [c["search"] for c in calls] == ["default", "default", "default"]
    assert out.status == "FEASIBLE"
