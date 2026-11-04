"""Observe installed-wheel CLI native calls without changing search or product code."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any


@contextmanager
def trace_calls(path: Path) -> Iterator[None]:
    """Flush paired stage/native events, retain failures, and restore both methods."""
    from ortools.sat.python import cp_model

    from tkb_core.solver import objectives

    real_stage, real_solve = objectives._run_stage, cp_model.CpSolver.solve
    stage_count, call_count = 0, 0
    current: dict[str, Any] = {}
    with path.open("x", encoding="utf-8") as handle:

        def emit(event: str, **fields: Any) -> None:
            handle.write(json.dumps({"event": event, **fields}, allow_nan=False) + "\n")
            handle.flush()

        @wraps(real_stage)
        def stage(*args: Any, **kwargs: Any) -> Any:
            nonlocal stage_count, current
            stage_count += 1
            current = {
                "stage": stage_count,
                "priority": args[4],
                "mode": kwargs.get("search", "default"),
                "budget": args[5],
                "fix_hint": kwargs.get("fix_hint", False),
            }
            emit("stage_start", **current)
            try:
                outcome = real_stage(*args, **kwargs)
                emit(
                    "stage_end",
                    **current,
                    status=str(outcome.status),
                    tiers=outcome.tier_values,
                    bound=outcome.best_bound,
                    wall_time=outcome.wall_time,
                )
                return outcome
            except BaseException as exc:
                emit("stage_error", **current, error_type=type(exc).__name__)
                raise
            finally:
                current = {}

        @wraps(real_solve)
        def native(solver: Any, model: Any, *args: Any, **kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            call = call_count
            started = time.monotonic()
            emit(
                "native_start",
                **current,
                call=call,
                monotonic=started,
                clock=time.time(),
                parameters_before=str(solver.parameters),
                workers=solver.parameters.num_search_workers,
                seed=solver.parameters.random_seed,
                native_budget=solver.parameters.max_time_in_seconds
                if math.isfinite(solver.parameters.max_time_in_seconds)
                else None,
                variables=len(model.proto.variables),
                constraints=len(model.proto.constraints),
                hint_variables=len(model.proto.solution_hint.vars),
            )
            try:
                status = real_solve(solver, model, *args, **kwargs)
            except BaseException as exc:
                emit(
                    "native_error",
                    **current,
                    call=call,
                    monotonic=time.monotonic(),
                    clock=time.time(),
                    error_type=type(exc).__name__,
                )
                raise
            ended = time.monotonic()
            feasible = int(status) in (2, 4)
            emit(
                "native_end",
                **current,
                call=call,
                monotonic=ended,
                clock=time.time(),
                elapsed=ended - started,
                status=solver.status_name(status),
                incumbent=solver.objective_value if feasible else None,
                bound=solver.best_objective_bound if feasible else None,
                wall_time=solver.wall_time,
                deterministic_time=solver.response_proto.deterministic_time,
                response_stats=solver.response_stats(),
                parameters_after=str(solver.parameters),
            )
            return status

        objectives._run_stage, cp_model.CpSolver.solve = stage, native
        try:
            yield
        finally:
            objectives._run_stage, cp_model.CpSolver.solve = real_stage, real_solve


def main(argv: list[str] | None = None) -> int:
    """Pass CLI arguments through unchanged, adding only an exclusive trace path."""
    from tkb_core.cli import main as cli_main

    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--trace", type=Path, required=True)
    args, remaining = parser.parse_known_args(argv)
    with trace_calls(args.trace):
        return cli_main(remaining)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
