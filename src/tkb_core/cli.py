"""Standalone contract, solve and independent schedule-validation CLI."""

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, NoReturn

from pydantic import BaseModel, ValidationError

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult
from tkb_core.contracts.repair import PreviousSchedule, RepairRequest, RepairResult
from tkb_core.contracts.score import ScoreReport
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ConstraintConfigV11, Diagnostic
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.repair_evaluator import check_report, evaluate_repair
from tkb_core.validation.score_evaluator import evaluate_score, score_version


class _ArgumentError(ValueError):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _ArgumentError(message)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    raise ValueError("Non-finite constants are not valid JSON")


def _error(status: str, code: str, message: str) -> int:
    print(
        json.dumps(
            {
                "schema_version": "1.0",
                "status": status,
                "diagnostics": [{"code": code, "message": message}],
            }
        )
    )
    return 2


def _load_json(path: Path) -> Any:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoreError("INPUT_INVALID", "INPUT_READ_ERROR", "Cannot read the input file") from exc
    except UnicodeError as exc:
        raise CoreError("INPUT_INVALID", "INVALID_JSON", "Input must be UTF-8 JSON") from exc
    try:
        return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise CoreError(
            "INPUT_INVALID", "INVALID_JSON", "Input must be finite JSON with unique keys"
        ) from exc


def _read_model[ModelT: BaseModel](
    path: Path, model: type[ModelT], code: str = "SCHEMA_VALIDATION_FAILED"
) -> ModelT:
    data = _load_json(path)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise CoreError("INPUT_INVALID", code, "File violates its versioned contract") from exc
    except (ValueError, RecursionError) as exc:
        raise CoreError(
            "INPUT_INVALID", "INVALID_JSON", "Input must be finite JSON with unique keys"
        ) from exc


def _read_previous(path: Path) -> PreviousSchedule:
    """A PreviousSchedule 1.0, or a valid ScheduleResult 1.1-1.5 converted to one."""
    data = _load_json(path)
    try:
        if isinstance(data, dict) and "status" in data:
            return PreviousSchedule.from_result(ScheduleResult.model_validate(data))
        return PreviousSchedule.model_validate(data)
    except (ValueError, RecursionError) as exc:
        raise CoreError(
            "INPUT_INVALID", "PREVIOUS_SCHEDULE_INVALID", "Previous schedule is invalid"
        ) from exc


def _exit_code(result: ScheduleResult) -> int:
    return {"INFEASIBLE": 3, "UNKNOWN": 4, "MODEL_INVALID": 5}.get(
        result.status, 0 if result.valid_schedule else 2
    )


def _expected_output(problem: ScheduleInput) -> str:
    if isinstance(problem.constraint_config, ConstraintConfigV11):
        return {"0.2": "1.3", "0.3": "1.4", "0.4": "1.5"}.get(
            problem.constraint_config.policy_version, "1.2"
        )
    return "1.1"


def _evaluate_repair(problem: ScheduleInput, previous_path: Path, result_path: Path) -> int:
    """Recompute hard validity, score and every repair count of a RepairResult file."""
    fingerprint = problem.fingerprint()
    previous = _read_previous(previous_path)
    envelope = _read_model(result_path, RepairResult)
    if (
        envelope.result.input_fingerprint != fingerprint
        or envelope.previous_fingerprint != previous.fingerprint()
    ):
        return _error("INPUT_INVALID", "STALE_RESULT", "Result does not match input/previous")
    if problem.schema_version != "1.1" or envelope.result.schema_version != _expected_output(
        problem
    ):
        return _error("INPUT_INVALID", "RESULT_VERSION", "Result version does not match input")
    if envelope.repair is None or envelope.request is None:
        return _error("INPUT_INVALID", "RESULT_NOT_REPAIRED", "Result carries no repaired schedule")
    assignments = envelope.result.assignments
    if not validate_schedule(problem, assignments).valid:
        return _error("INPUT_INVALID", "SCHEDULE_INVALID", "Schedule violates hard constraints")
    score = evaluate_score(problem, assignments)
    declared = envelope.result.quality.score if envelope.result.quality else None
    if declared is not None:
        actual = declared.model_dump(mode="json")
        actual["rules"].sort(key=lambda r: r["rule_id"])
        if actual != score.model_dump(mode="json"):
            return _error(
                "INPUT_INVALID",
                "RESULT_SCORE_MISMATCH",
                "Declared score differs from recomputation",
            )
    evaluation = evaluate_repair(problem, previous, envelope.request, assignments)
    problems = check_report(evaluation, envelope.repair)
    if problems:
        return _error(
            "INPUT_INVALID",
            "RESULT_REPAIR_MISMATCH",
            "Declared repair report differs from recomputation: " + ",".join(problems),
        )
    print(
        json.dumps(
            {
                "schema_version": "1.0",
                "status": "OK",
                "input_fingerprint": fingerprint,
                "previous_fingerprint": envelope.previous_fingerprint,
                "matched": evaluation.matched,
                "new": evaluation.new,
                "dropped": evaluation.dropped,
                "changed": evaluation.changed,
                "slot_changes": evaluation.slot_changes,
                "room_only_changes": evaluation.room_only_changes,
                "frozen": evaluation.frozen,
                # A solver claim; only the counts above are recomputed independently.
                "declared_min_changes_proved": envelope.repair.min_changes_proved,
            }
        )
    )
    return 0


def _check_output(source: Path, destination: Path) -> None:
    try:
        same_path = source.resolve() == destination.resolve()
    except RuntimeError as exc:
        raise CoreError(
            "INPUT_INVALID", "OUTPUT_PATH_ERROR", "Output path contains a symlink loop"
        ) from exc
    if same_path or (destination.exists() and source.samefile(destination)):
        raise CoreError(
            "INPUT_INVALID", "OUTPUT_CONFLICT", "Output must not replace the input file"
        )


def _write_atomic(destination: Path, content: str) -> None:
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, prefix=".tkb-", delete=False
        ) as handle:
            temporary = handle.name
            handle.write(content + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    """Exit 0 valid, 2 input/unsupported, 3 infeasible, 4 unknown, 5 model failure."""
    args = list(sys.argv[1:] if argv is None else argv)
    evaluation = bool(args and args[0] == "evaluate-score")
    # Error reports follow the input's ScoreReport version once the input has been parsed.
    report_version: list[Literal["1.0", "1.1", "1.2"]] = ["1.0"]

    def emit_error(status: str, code: str, message: str) -> int:
        if not evaluation:
            return _error(status, code, message)
        report = ScoreReport(
            schema_version=report_version[0],
            status="UNSUPPORTED_FEATURE" if status == "UNSUPPORTED_FEATURE" else "INPUT_INVALID",
            diagnostics=(Diagnostic(code=code, message=message),),
        )
        print(report.model_dump_json())
        return 2

    if (
        args
        and not args[0].startswith("-")
        and args[0]
        not in {
            "validate-input",
            "solve",
            "validate-schedule",
            "evaluate-score",
            "repair",
            "evaluate-repair",
        }
    ):
        return emit_error(
            "UNSUPPORTED_FEATURE",
            "COMMAND_NOT_IMPLEMENTED",
            "Command is not implemented in Phase 1",
        )
    parser = _Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser(
        "validate-input", help="Check schema and references, not feasibility"
    )
    validate.add_argument("path", type=Path)
    solving = commands.add_parser("solve", help="Solve supported hard constraints")
    solving.add_argument("path", type=Path)
    solving.add_argument("--time-limit", type=float, default=60.0)
    solving.add_argument("--workers", type=int, default=1)
    solving.add_argument("--seed", type=int, default=42)
    solving.add_argument("--output", type=Path)
    for limit in ("max-slots", "max-occurrences", "max-placements", "max-occupancy-terms"):
        solving.add_argument("--" + limit, type=int)
    checking = commands.add_parser(
        "validate-schedule", help="Recompute hard validity independently"
    )
    checking.add_argument("path", type=Path)
    checking.add_argument("result", type=Path)
    scoring = commands.add_parser(
        "evaluate-score", help="Independently recompute preference scores"
    )
    scoring.add_argument("path", type=Path)
    scoring.add_argument("result", type=Path)
    repairing = commands.add_parser("repair", help="Repair a previous schedule (Phase 3A)")
    repairing.add_argument("path", type=Path)
    repairing.add_argument("previous", type=Path)
    repairing.add_argument("--request", type=Path, required=True)
    repairing.add_argument("--time-limit", type=float, default=60.0)
    repairing.add_argument("--workers", type=int, default=1)
    repairing.add_argument("--seed", type=int, default=42)
    repairing.add_argument("--output", type=Path)
    for limit in ("max-slots", "max-occurrences", "max-placements", "max-occupancy-terms"):
        repairing.add_argument("--" + limit, type=int)
    rechecking = commands.add_parser(
        "evaluate-repair", help="Independently recompute a repair result"
    )
    rechecking.add_argument("path", type=Path)
    rechecking.add_argument("previous", type=Path)
    rechecking.add_argument("result", type=Path)
    try:
        namespace = parser.parse_args(args)
    except _ArgumentError:
        return emit_error(
            "INPUT_INVALID", "INVALID_ARGUMENTS", "Invalid command arguments; see --help"
        )
    try:
        problem = _read_model(namespace.path, ScheduleInput)
        fingerprint = problem.fingerprint()
        report_version[0] = score_version(problem)
        if namespace.command == "evaluate-repair":
            return _evaluate_repair(problem, namespace.previous, namespace.result)
        if namespace.command in ("validate-schedule", "evaluate-score"):
            previous = _read_model(namespace.result, ScheduleResult)
            if previous.input_fingerprint != fingerprint:
                return emit_error(
                    "INPUT_INVALID", "STALE_RESULT", "Result does not match the current input"
                )
            expected_version = "1.1"
            if isinstance(problem.constraint_config, ConstraintConfigV11):
                expected_version = {"0.2": "1.3", "0.3": "1.4", "0.4": "1.5"}.get(
                    problem.constraint_config.policy_version, "1.2"
                )
            # Input 1.0 may still be checked against legacy 1.0/1.1 results, never a quality
            # result; input 1.1 requires exactly the output version its policy produces.
            accepted = {"1.0", "1.1"} if expected_version == "1.1" else {expected_version}
            if previous.schema_version not in accepted:
                return emit_error(
                    "INPUT_INVALID", "RESULT_VERSION", "Result version does not match input"
                )
            score = None
            if namespace.command == "evaluate-score" or problem.schema_version == "1.1":
                score = evaluate_score(problem, previous.assignments)
                if score.status != "OK":
                    if namespace.command == "evaluate-score":
                        print(score.model_dump_json())
                        return 5 if score.status == "INTERNAL_ERROR" else 2
                    return emit_error(
                        "INPUT_INVALID", score.diagnostics[0].code, "Schedule could not be scored"
                    )
                if previous.quality is not None:
                    declared = previous.quality.score
                    if declared is not None:
                        expected = score.model_dump(mode="json")
                        actual = declared.model_dump(mode="json")
                        actual["rules"].sort(key=lambda r: r["rule_id"])
                        if actual != expected:
                            return emit_error(
                                "INPUT_INVALID",
                                "RESULT_SCORE_MISMATCH",
                                "Declared score differs from recomputation",
                            )
                    config = problem.constraint_config
                    if isinstance(config, ConstraintConfigV11):
                        active = sorted({r.priority for r in config.soft if r.enabled})
                        if active != [r.priority for r in previous.quality.tier_runs] or (
                            active and declared is None
                        ):
                            return emit_error(
                                "INPUT_INVALID",
                                "RESULT_SCORE_MISMATCH",
                                "Quality report does not cover active policy",
                            )
                if namespace.command == "evaluate-score":
                    print(score.model_dump_json())
                    return 0
            report = validate_schedule(problem, previous.assignments)
            print(
                json.dumps(
                    {
                        "schema_version": expected_version,
                        **({"score": score.model_dump(mode="json")} if score is not None else {}),
                        "status": "SCHEDULE_VALID" if report.valid else "SCHEDULE_INVALID",
                        "valid_schedule": report.valid,
                        "input_fingerprint": fingerprint,
                        "diagnostics": [v.model_dump(mode="json") for v in report.violations],
                    }
                )
            )
            return 0 if report.valid else 2
        if namespace.command in ("solve", "repair"):
            if namespace.output is not None:
                _check_output(namespace.path, namespace.output)
                if namespace.command == "repair":
                    _check_output(namespace.previous, namespace.output)
                    _check_output(namespace.request, namespace.output)
            values = {
                "time_limit_seconds": namespace.time_limit,
                "num_workers": namespace.workers,
                "seed": namespace.seed,
            }
            for limit in ("max_slots", "max_occurrences", "max_placements", "max_occupancy_terms"):
                value = getattr(namespace, limit)
                if value is not None:
                    values[limit] = value
            options = SolveOptions.model_validate(values)
            if namespace.command == "repair":
                from tkb_core.repair.pipeline import repair

                previous_schedule = _read_previous(namespace.previous)
                request = _read_model(namespace.request, RepairRequest, "REPAIR_REQUEST_INVALID")
                repaired = repair(problem, previous_schedule, request, options)
                result = repaired.result
                serialized = repaired.model_dump_json()
            else:
                from tkb_core.solver.cp_sat import solve

                result = solve(problem, options)
                serialized = result.model_dump_json()
            if namespace.output is not None:
                try:
                    _write_atomic(namespace.output, serialized)
                except OSError:
                    return emit_error(
                        "INPUT_INVALID",
                        "OUTPUT_WRITE_ERROR",
                        "Could not atomically write the result file",
                    )
            print(serialized)
            return _exit_code(result)
    except CoreError as exc:
        diagnostic = exc.diagnostics[0]
        return emit_error(exc.status.value, diagnostic.code, diagnostic.message)
    except ValidationError:
        return emit_error(
            "INPUT_INVALID", "OPTIONS_INVALID", "Solver options violate their contract"
        )
    except (OSError, ValueError, RecursionError):
        return emit_error(
            "INPUT_INVALID", "INVALID_INPUT", "Input or output path could not be processed"
        )
    print(
        json.dumps(
            {
                "schema_version": "1.0",
                "status": "INPUT_VALID",
                "checked": "contract",
                "solver_executed": False,
                "input_fingerprint": fingerprint,
                "counts": {
                    "classes": len(problem.classes),
                    "teachers": len(problem.teachers),
                    "requirements": len(problem.teaching_requirements),
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
