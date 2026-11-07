"""Score a real schedule with the independent checker and evaluator (plan §6).

Calls ``validate_schedule`` and ``evaluate_score`` directly on the real assignments: these are the
Core's independent functions, with no solver involved, so no solver result is ever fabricated.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ValidationReport
from tkb_core.contracts.score import ScoreReport
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score


def load(
    input_path: Path, assignments_path: Path
) -> tuple[ScheduleInput, tuple[ScheduleAssignment, ...]]:
    problem = ScheduleInput.model_validate_json(input_path.read_text(encoding="utf-8"))
    data = json.loads(assignments_path.read_text(encoding="utf-8"))
    if data.get("source_input_fingerprint") != problem.fingerprint():
        raise ValueError("assignments were made for a different input")
    return problem, tuple(ScheduleAssignment.model_validate(a) for a in data["assignments"])


def summarize(
    problem: ScheduleInput,
    hard: ValidationReport,
    score: ScoreReport | None,
) -> dict[str, Any]:
    """Hard validity, tier vector and per-rule totals of one schedule on one input."""
    scope = {r.id: list(r.scope.teacher_ids) for r in problem.constraint_config.soft}  # type: ignore[union-attr]
    rules: dict[str, dict[str, int]] = {}
    teachers: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    tiers_of: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    tiers = None
    if score is not None and score.status == "OK" and score.tiers is not None:
        tiers = list(score.tiers)
        for r in score.rules:
            entry = rules.setdefault(
                r.code, {"raw_penalty": 0, "rows": 0, "rows_violating": 0, "priority": r.priority}
            )
            entry["raw_penalty"] += r.raw_penalty
            entry["rows"] += 1
            entry["rows_violating"] += r.raw_penalty > 0
            for t in scope.get(r.rule_id, []):
                teachers[t][r.code] += r.raw_penalty
                tiers_of[t][r.priority - 1] += r.weighted_penalty
    # Units differ between rules, so teachers are ranked by their own tier vector (P1, P2, P3),
    # the same lexicographic order Core optimises, never by a sum across units.
    ranked = sorted(teachers, key=lambda t: ([-v for v in tiers_of[t]], t))
    worst = [
        {"teacher": t, "tiers": tiers_of[t], "by_code": {k: v for k, v in teachers[t].items() if v}}
        for t in ranked
    ]
    return {
        "school": problem.school.school_id,
        "counts": {
            "classes": len(problem.classes),
            "teachers": len({t for r in problem.teaching_requirements for t in r.teacher_ids}),
            "requirements": len(problem.teaching_requirements),
            "periods": sum(r.periods_per_cycle for r in problem.teaching_requirements),
        },
        "hard_valid": hard.valid,
        "hard_violations": [v.model_dump(mode="json") for v in hard.violations],
        "tiers": tiers,
        "rules": rules,
        "worst_teachers": [w for w in worst if any(w["tiers"])][:10],
    }


def score_files(input_path: Path, assignments_path: Path) -> dict[str, Any]:
    problem, assignments = load(input_path, assignments_path)
    hard = validate_schedule(problem, assignments)
    score = evaluate_score(problem, assignments) if hard.valid else None
    return summarize(problem, hard, score)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("converted", type=Path, help="directory written by convert_real.py")
    args = parser.parse_args(argv)
    report = score_files(args.converted / "input.json", args.converted / "real-assignments.json")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["hard_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
