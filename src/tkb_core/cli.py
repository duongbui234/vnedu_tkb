"""Phase 0 CLI: validate the domain contract without solving or accessing services."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from pydantic import ValidationError

from tkb_core.contracts.input import ScheduleInput


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


def main(argv: Sequence[str] | None = None) -> int:
    """Return 0 for a valid contract, 2 for input/usage/unsupported errors."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and not args[0].startswith("-") and args[0] != "validate-input":
        return _error(
            "UNSUPPORTED_FEATURE",
            "COMMAND_NOT_IMPLEMENTED",
            "Only validate-input is implemented in Phase 0",
        )
    parser = _Parser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser(
        "validate-input", help="Check schema and references, not feasibility"
    )
    validate.add_argument("path", type=Path)
    try:
        namespace = parser.parse_args(args)
    except _ArgumentError:
        return _error("INPUT_INVALID", "INVALID_ARGUMENTS", "Use validate-input PATH; see --help")
    try:
        raw = namespace.path.read_text(encoding="utf-8")
    except OSError:
        return _error("INPUT_INVALID", "INPUT_READ_ERROR", "Cannot read the input file")
    except UnicodeError:
        return _error("INPUT_INVALID", "INVALID_JSON", "Input must be UTF-8 JSON")
    try:
        data = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        problem = ScheduleInput.model_validate(data)
        fingerprint = problem.fingerprint()
    except ValidationError as error:
        # Avoid str(error), which includes full input values in Pydantic reports.
        return _error(
            "INPUT_INVALID",
            "SCHEMA_VALIDATION_FAILED",
            f"Input violates contract v1 ({error.error_count()} validation errors)",
        )
    except (ValueError, RecursionError):
        return _error(
            "INPUT_INVALID", "INVALID_JSON", "Input must be finite JSON with unique object keys"
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
