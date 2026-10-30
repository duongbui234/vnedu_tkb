"""Tiny native pairs: S03 bounds keep the exhaustive optimum and independent scores."""

import importlib.util
from itertools import product
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from ortools.sat.python import cp_model

from tkb_core.constraints.s03_bounds import S03BoundsDecision
from tkb_core.constraints.soft import compile_soft
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver.model_builder import build_model
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score

PAIRS = (
    "sym_sparse_days",
    "sym_multi_scope",
    "tim_overlap",
    "tim_locked_double",
    "tim_room_only",
    "sym_fixed_zero",
)


def _corpus() -> ModuleType:
    path = Path(__file__).parents[1] / "properties/test_s03_bounds_oracle.py"
    spec = importlib.util.spec_from_file_location("s03_bounds_corpus", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CORPUS = _corpus()


def _oracle_range(data: dict[str, Any]) -> tuple[int, int]:
    timed, occurrences = CORPUS.candidates(data)
    scope, limit = CORPUS._rule(data)
    raws = []
    for selection in product(*[[(o, r, c) for c in cs] for o, r, cs in occurrences]):
        if CORPUS.hard_valid(selection, timed):
            loads: dict[tuple[str, int], int] = {}
            for _, req, (_, _, covered) in selection:
                if req["teacher_ids"][0] in scope:
                    for slot in covered:
                        key = (req["teacher_ids"][0], slot["day"])
                        loads[key] = loads.get(key, 0) + 1
            raws.append(sum(max(0, n - limit) for n in loads.values()))
    return min(raws), max(raws)


def _solve_once(problem: ScheduleInput) -> dict[str, Any]:
    """One bounded CP-SAT call minimizing the tier that contains S03."""
    prepared = prepare(problem)
    built = build_model(prepared)
    compiled = compile_soft(prepared, built)
    built.model.minimize(compiled.tiers[1])
    assert not built.model.validate()
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 1.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    solver.parameters.relative_gap_limit = 0.0
    solver.parameters.absolute_gap_limit = 0.0
    status = solver.solve(built.model)
    assert status == cp_model.OPTIMAL
    reqs = {r.id: r for r in problem.teaching_requirements}
    assignments = tuple(
        ScheduleAssignment(
            occurrence_id=o.id,
            slot_id=p.start_slot_id,
            room_id=p.room_id,
            class_ids=reqs[o.requirement_id].class_ids,
            teacher_ids=reqs[o.requirement_id].teacher_ids,
        )
        for o in prepared.normalized.occurrences
        for p, v in zip(prepared.domains[o.id], built.variables[o.id], strict=True)
        if solver.boolean_value(v)
    )
    rule = compiled.rules[0]
    return {
        "assignments": assignments,
        "raw": int(solver.value(rule.raw_expression)),
        "weighted": int(solver.value(rule.weighted_expression)),
        "objective": int(solver.objective_value),
        "metadata": (rule.raw_upper_bound, rule.weighted_upper_bound, compiled.upper_bounds),
        "variables": len(built.model.proto.variables),
        "constraints": len(built.model.proto.constraints),
    }


@pytest.mark.parametrize("name", PAIRS)
def test_baseline_and_bounded_pair_match_oracle(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    data = CORPUS.CORPUS[name]()
    problem = ScheduleInput.model_validate(data)
    oracle_min, oracle_max = _oracle_range(data)
    bounded = _solve_once(problem)
    monkeypatch.setattr(
        "tkb_core.constraints.soft.derive_s03_bounds",
        lambda *a: S03BoundsDecision(None, "TEST_BASELINE"),
    )
    baseline = _solve_once(problem)
    for run in (baseline, bounded):
        assert run["raw"] == oracle_min
        assert run["weighted"] == run["objective"] == 3 * oracle_min
        assert validate_schedule(problem, run["assignments"]).valid
        score = evaluate_score(problem, run["assignments"])
        assert score.status == "OK"
        assert (score.rules[0].raw_penalty, score.rules[0].weighted_penalty) == (
            run["raw"],
            run["weighted"],
        )
    assert bounded["metadata"] == baseline["metadata"]
    assert bounded["metadata"][0] >= oracle_max
    assert bounded["variables"] == baseline["variables"]
    assert bounded["constraints"] >= baseline["constraints"]
