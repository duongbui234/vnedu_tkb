"""Tiny native quality proofs and actual public-pipeline ordering/clone boundaries."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tkb_core.constraints.soft import compile_soft
from tkb_core.contracts.input import ScheduleInput
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver import model_builder, objectives
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.model_builder import build_model
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score


@pytest.mark.parametrize("room_lock", [False, True])
def test_tiny_quality_optimum_equal_with_and_without_ordering(
    ordering_case: dict[str, Any], room_lock: bool
) -> None:
    if room_lock:
        ordering_case["manage_rooms"] = True
        ordering_case["classes"][0]["size"] = 10
        ordering_case["rooms"] = [{"id": "opaque-room", "capacity": 20}]
        ordering_case["teaching_requirements"][0]["room_required"] = True
        ordering_case["locked_assignments"] = [{"occurrence_id": "r::2", "room_id": "opaque-room"}]
    problem = ScheduleInput.model_validate(ordering_case)
    prepared = prepare(problem)
    scores = []
    for ordered in (False, True):
        built = build_model(prepared, order_interchangeable=ordered)
        hard = built.model.clone()
        compiled = compile_soft(prepared, built)
        out = objectives.run_quality(
            prepared, built, compiled, SolveOptions(time_limit_seconds=5.0), hard
        )
        assert out.status == "OPTIMAL" and out.quality.optimal_prefix == (1, 2, 3)
        assert validate_schedule(problem, out.assignments).valid
        assert evaluate_score(problem, out.assignments) == out.score
        scores.append(out.score.tiers)
    assert scores == [(1, 1, 1), (1, 1, 1)]


def test_public_quality_orders_before_clone_and_keeps_stage_semantics(
    ordering_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    real_builder = model_builder.build_model
    real_stage = objectives._run_stage
    builds: list[tuple[bool, list[str], int]] = []
    calls: list[tuple[int | None, bool, bool]] = []

    def builder_spy(prepared: Any, *, order_interchangeable: bool = False) -> Any:
        built = real_builder(prepared, order_interchangeable=order_interchangeable)
        builds.append(
            (
                order_interchangeable,
                [str(c) for c in built.model.proto.constraints],
                len(built.model.proto.variables),
            )
        )
        return built

    def stage_spy(*args: Any, **kwargs: Any) -> Any:
        hard = kwargs.get("model")
        if hard is not None:
            assert [str(c) for c in hard.proto.constraints] == builds[0][1]
            assert len(hard.proto.variables) == builds[0][2]
            assert [str(c) for c in args[1].model.proto.constraints][: len(builds[0][1])] == builds[
                0
            ][1]
        calls.append((args[4], hard is not None, kwargs.get("fix_hint", False)))
        return real_stage(*args, **kwargs)

    monkeypatch.setattr(model_builder, "build_model", builder_spy)
    monkeypatch.setattr(objectives, "_run_stage", stage_spy)
    problem = ScheduleInput.model_validate(ordering_case)
    result = solve(problem, SolveOptions(time_limit_seconds=5.0))
    assert result.status == "OPTIMAL" and result.valid_schedule
    assert builds[0][0] and len(builds) == 1
    plain = real_builder(prepare(problem))
    assert len(builds[0][1]) == len(plain.model.proto.constraints) + 2
    assert calls == [
        (None, True, False),
        (None, False, True),
        (1, False, False),
        (2, False, False),
        (3, False, False),
    ]
    assert result.quality.optimal_prefix == (1, 2, 3)
    assert evaluate_score(problem, result.assignments) == result.quality.score


@pytest.mark.parametrize("legacy", [False, True])
def test_public_nonquality_paths_do_not_enable_ordering(
    ordering_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch, legacy: bool
) -> None:
    ordering_case["constraint_config"]["soft"] = []
    if legacy:
        ordering_case.update(schema_version="1.0", constraint_config={"hard": [], "soft": []})
    real = model_builder.build_model
    flags = []

    def spy(prepared: Any, *, order_interchangeable: bool = False) -> Any:
        flags.append(order_interchangeable)
        return real(prepared, order_interchangeable=order_interchangeable)

    monkeypatch.setattr(model_builder, "build_model", spy)
    result = solve(
        ScheduleInput.model_validate(ordering_case), SolveOptions(time_limit_seconds=5.0)
    )
    assert result.valid_schedule and flags == [False]


def test_ordering_does_not_execute_solver_before_range_error(
    ordering_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    ordering_case["constraint_config"]["soft"][0]["weight"] = 2**53

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Native stage must not run before OBJECTIVE_RANGE")

    monkeypatch.setattr(objectives, "_run_stage", forbidden)
    result = solve(ScheduleInput.model_validate(ordering_case))
    assert result.status == "INPUT_INVALID" and not result.metadata.solver_executed
    assert result.diagnostics[0].code == "OBJECTIVE_RANGE"


def test_validation_scoring_still_import_no_solver(
    ordering_case: dict[str, Any], tmp_path: Path
) -> None:
    # A deliberately reverse-ordinal hard-valid schedule must remain acceptable.
    fixture = tmp_path / "input.json"
    fixture.write_text(json.dumps(ordering_case), encoding="utf-8")
    script = """
import importlib.abc, json, sys
blocked = (
    'ortools', 'tkb_core.preprocessing', 'tkb_core.solver.model_builder',
    'tkb_core.solver.objectives', 'tkb_core.solver.cp_sat', 'tkb_core.constraints.soft',
)
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if any(name == x or name.startswith(x+'.') for x in blocked):
            raise AssertionError('Forbidden import: '+name)
sys.meta_path.insert(0, Guard())
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score
from pathlib import Path
p = ScheduleInput.model_validate_json(Path(sys.argv[1]).read_bytes())
aa = tuple(
    ScheduleAssignment(occurrence_id=f'r::{i}', slot_id=f'1-AM-{s}',
                       class_ids=('c',), teacher_ids=('t',))
    for i,s in enumerate((4,3,2),1)
)
assert validate_schedule(p, aa).valid
assert evaluate_score(p, aa).tiers == (1,1,1)
assert not any(n==x or n.startswith(x+'.') for n in sys.modules for x in blocked)
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(fixture)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
