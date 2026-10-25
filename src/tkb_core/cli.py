"""Standalone contract, solve and independent schedule-validation CLI."""

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from pydantic import BaseModel, ValidationError

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult
from tkb_core.domain.errors import CoreError
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule


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


def _read_model[ModelT: BaseModel](path: Path, model: type[ModelT]) -> ModelT:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoreError("INPUT_INVALID", "INPUT_READ_ERROR", "Cannot read the input file") from exc
    except UnicodeError as exc:
        raise CoreError("INPUT_INVALID", "INVALID_JSON", "Input must be UTF-8 JSON") from exc
    try:
        data = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        return model.model_validate(data)
    except ValidationError as exc:
        raise CoreError(
            "INPUT_INVALID", "SCHEMA_VALIDATION_FAILED", "File violates its versioned contract"
        ) from exc
    except (ValueError, RecursionError) as exc:
        raise CoreError(
            "INPUT_INVALID", "INVALID_JSON", "Input must be finite JSON with unique keys"
        ) from exc


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
    if (
        args
        and not args[0].startswith("-")
        and args[0] not in {"validate-input", "solve", "validate-schedule"}
    ):
        return _error(
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
    try:
        namespace = parser.parse_args(args)
    except _ArgumentError:
        return _error("INPUT_INVALID", "INVALID_ARGUMENTS", "Invalid command arguments; see --help")
    try:
        problem = _read_model(namespace.path, ScheduleInput)
        fingerprint = problem.fingerprint()
        if namespace.command == "validate-schedule":
            previous = _read_model(namespace.result, ScheduleResult)
            if previous.input_fingerprint != fingerprint:
                return _error(
                    "INPUT_INVALID", "STALE_RESULT", "Result does not match the current input"
                )
            report = validate_schedule(problem, previous.assignments)
            print(
                json.dumps(
                    {
                        "schema_version": "1.1",
                        "status": "SCHEDULE_VALID" if report.valid else "SCHEDULE_INVALID",
                        "valid_schedule": report.valid,
                        "input_fingerprint": fingerprint,
                        "diagnostics": [v.model_dump(mode="json") for v in report.violations],
                    }
                )
            )
            return 0 if report.valid else 2
        if namespace.command == "solve":
            if namespace.output is not None:
                _check_output(namespace.path, namespace.output)
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
            result = solve(problem, options)
            serialized = result.model_dump_json()
            if namespace.output is not None:
                try:
                    _write_atomic(namespace.output, serialized)
                except OSError:
                    return _error(
                        "INPUT_INVALID",
                        "OUTPUT_WRITE_ERROR",
                        "Could not atomically write the result file",
                    )
            print(serialized)
            return {"INFEASIBLE": 3, "UNKNOWN": 4, "MODEL_INVALID": 5}.get(
                result.status, 0 if result.valid_schedule else 2
            )
    except CoreError as exc:
        diagnostic = exc.diagnostics[0]
        return _error(exc.status.value, diagnostic.code, diagnostic.message)
    except ValidationError:
        return _error("INPUT_INVALID", "OPTIONS_INVALID", "Solver options violate their contract")
    except (OSError, ValueError, RecursionError):
        return _error(
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
