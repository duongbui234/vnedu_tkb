"""Run ``tkb_core.cli`` with a given schedule as the first incumbent (diagnostic tooling only).

    python -m tools.real_data.warm_start <assignments.json> solve <input.json> [solve options]

The hard-only feasibility stage of quality solving is replaced by the given assignments, put in
Core's occurrence order (``run_quality`` compares them element by element with the soft-model
check). Core then validates and scores them independently, checks them in the soft model and hints
every tier with them. Core code is unchanged: the patch lives in this process only and is removed
when the CLI returns.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.solver import objectives

APPLIED = "WARM_START_APPLIED"
NOT_APPLIED = "WARM_START_NOT_APPLIED"


def load(path: Path) -> tuple[ScheduleAssignment, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data["assignments"] if isinstance(data, dict) else data
    return tuple(ScheduleAssignment.model_validate(a) for a in items)


@contextmanager
def first_incumbent(assignments: tuple[ScheduleAssignment, ...]) -> Iterator[dict[str, bool]]:
    """Patch the first hard-only stage of ``run_quality`` to return ``assignments``."""
    original = objectives._run_stage
    state = {"applied": False}

    def patched(
        prepared: Any,
        built: Any,
        compiled: Any,
        options: Any,
        priority: Any,
        budget: float,
        **kw: Any,
    ) -> objectives.StageOutcome:
        if not state["applied"] and priority is None and kw.get("model") is not None:
            state["applied"] = True
            order = {o.id: i for i, o in enumerate(prepared.normalized.occurrences)}
            ordered = tuple(sorted(assignments, key=lambda a: order[a.occurrence_id]))
            return objectives.StageOutcome(SolveStatus.FEASIBLE, ordered, wall_time=0.0)
        return original(prepared, built, compiled, options, priority, budget, **kw)

    objectives._run_stage = patched
    try:
        yield state
    finally:
        objectives._run_stage = original


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    from tkb_core.cli import main as cli_main

    with first_incumbent(load(Path(args[0]))) as state:
        code = cli_main(args[1:])
    print(APPLIED if state["applied"] else NOT_APPLIED, file=sys.stderr)
    return code if state["applied"] else (code or 3)


if __name__ == "__main__":
    raise SystemExit(main())
