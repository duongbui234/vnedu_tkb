"""Hard-only feasibility, expression verification and tier hints, with stubbed stages."""

from typing import Any

import pytest

from tkb_core.constraints.soft import CompiledSoft, compile_soft
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.feasibility import PreparedProblem, prepare
from tkb_core.solver.model_builder import BuiltModel, build_model
from tkb_core.solver.objectives import StageOutcome, run_quality
from tkb_core.solver.options import SolveOptions

RULE = {
    "id": "rule",
    "code": "TEACHER_AVOID_SLOTS",
    "parameters": {"slot_ids": ["1-AM-1"]},
    "weight": 1,
    "priority": 1,
}
SCHEDULE = tuple(
    ScheduleAssignment(
        occurrence_id=f"r::{i}", slot_id=f"1-PM-{start}", class_ids=("c",), teacher_ids=("t",)
    )
    for i, start in enumerate((1, 3, 4), 1)
)


def _setup(quality_case: dict[str, Any]) -> tuple[PreparedProblem, BuiltModel, Any, CompiledSoft]:
    quality_case["constraint_config"]["soft"] = [RULE]
    p = prepare(ScheduleInput.model_validate(quality_case))
    built = build_model(p)
    hard = built.model.clone()
    return p, built, hard, compile_soft(p, built)


def _stub(
    calls: list[dict[str, Any]],
    first: str = "OPTIMAL",
    verify: tuple[str, int] = ("OPTIMAL", 0),
    tier: str = "OPTIMAL",
) -> Any:
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
                "model": model,
                "fix_hint": fix_hint,
                "search": search,
                "hint": sorted(zip(list(hint.vars), list(hint.values), strict=True)),
            }
        )
        if priority is None and model is not None:
            ok = first in ("OPTIMAL", "FEASIBLE")
            return StageOutcome(SolveStatus(first), SCHEDULE if ok else (), wall_time=1.0)
        if priority is None:
            status, raw = verify
            ok = status in ("OPTIMAL", "FEASIBLE")
            return StageOutcome(
                SolveStatus(status),
                SCHEDULE if ok else (),
                {"rule": (raw, raw)},
                {1: raw},
                wall_time=1.0,
            )
        ok = tier in ("OPTIMAL", "FEASIBLE")
        return StageOutcome(
            SolveStatus(tier),
            SCHEDULE if ok else (),
            {"rule": (0, 0)},
            {1: 0},
            wall_time=1.0,
            best_bound=0.0,
        )

    return fake


def test_feasibility_uses_hard_clone_without_soft_auxiliaries(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    p, built, hard, compiled = _setup(quality_case)
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("tkb_core.solver.objectives._run_stage", _stub(calls))
    out = run_quality(p, built, compiled, SolveOptions(time_limit_seconds=10.0), hard)
    assert out.status == "OPTIMAL" and out.assignments == SCHEDULE
    assert [(c["priority"], c["model"] is hard, c["fix_hint"]) for c in calls] == [
        (None, True, False),
        (None, False, True),
        (1, False, False),
    ]
    assert [c["search"] for c in calls] == ["default", "default", "slice"]
    names = [v.name for v in hard.proto.variables]
    assert not any(n.startswith(("excess_", "raw_")) for n in names)
    assert len(names) == sum(len(v) for v in built.variables.values())
    assert names == [v.name for v in built.model.proto.variables][: len(names)]
    assert not hard.proto.has_objective() and list(hard.proto.solution_hint.vars) == []
    assert out.feasibility_run.raw_status == "OPTIMAL"


def test_tiers_are_hinted_with_verified_incumbent(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    p, built, hard, compiled = _setup(quality_case)
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("tkb_core.solver.objectives._run_stage", _stub(calls))
    run_quality(p, built, compiled, SolveOptions(time_limit_seconds=10.0), hard)
    chosen = {a.occurrence_id: (a.slot_id, a.room_id) for a in SCHEDULE}
    expected = sorted(
        (v.index, int((pl.start_slot_id, pl.room_id) == chosen[o.id]))
        for o in p.normalized.occurrences
        for pl, v in zip(p.domains[o.id], built.variables[o.id], strict=True)
    )
    assert calls[0]["hint"] == []
    assert calls[1]["hint"] == calls[2]["hint"] == expected


def test_verification_mismatch_is_internal_error(
    quality_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    p, built, hard, compiled = _setup(quality_case)
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "tkb_core.solver.objectives._run_stage", _stub(calls, verify=("OPTIMAL", 1))
    )
    out = run_quality(p, built, compiled, SolveOptions(time_limit_seconds=10.0), hard)
    assert out.status == "MODEL_INVALID" and not out.assignments
    assert out.diagnostics[0].code == "INTERNAL_SCORE_MISMATCH" and len(calls) == 2


@pytest.mark.parametrize(
    "status,expected,code",
    [
        ("INFEASIBLE", "MODEL_INVALID", "INTERNAL_STAGE_INCONSISTENCY"),
        ("MODEL_INVALID", "MODEL_INVALID", "MODEL_INVALID"),
        ("UNKNOWN", "FEASIBLE", None),
    ],
)
def test_verification_status_handling(
    quality_case: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    expected: str,
    code: str | None,
) -> None:
    p, built, hard, compiled = _setup(quality_case)
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("tkb_core.solver.objectives._run_stage", _stub(calls, verify=(status, 0)))
    out = run_quality(p, built, compiled, SolveOptions(time_limit_seconds=10.0), hard)
    assert out.status == expected and len(calls) == 2
    if code:
        assert out.diagnostics[0].code == code and not out.assignments
    else:
        assert out.assignments == SCHEDULE and not out.diagnostics
        assert out.quality.tier_runs[0].raw_status == "NOT_RUN"


@pytest.mark.parametrize(
    "first,expected,code",
    [("INFEASIBLE", "INFEASIBLE", "INFEASIBLE"), ("UNKNOWN", "UNKNOWN", None)],
)
def test_hard_infeasible_or_unknown_stops_before_soft(
    quality_case: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    first: str,
    expected: str,
    code: str | None,
) -> None:
    p, built, hard, compiled = _setup(quality_case)
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr("tkb_core.solver.objectives._run_stage", _stub(calls, first=first))
    out = run_quality(p, built, compiled, SolveOptions(time_limit_seconds=10.0), hard)
    assert out.status == expected and len(calls) == 1 and not out.assignments
    assert out.diagnostics[0].code == code if code else not out.diagnostics
