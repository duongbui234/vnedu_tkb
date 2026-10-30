"""Installed Windows Task2 probes; native execution requires separate user approval."""

from __future__ import annotations

import argparse
import builtins
import copy
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import platform
import subprocess
import sys
import tomllib
import zipfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def isolated() -> bool:
    """Whether Python was launched with isolation (-I)."""
    return bool(sys.flags.isolated)


def native_gate(approval_reference: str) -> None:
    """Fail closed before importing Core; reference records consent, never grants it."""
    if sys.platform != "win32" or platform.machine().lower() not in ("amd64", "x86_64"):
        raise ValueError("WINDOWS_NATIVE_REQUIRED")
    if not approval_reference.strip():
        raise ValueError("APPROVAL_REFERENCE_REQUIRED")
    if not isolated():
        raise ValueError("ISOLATED_INTERPRETER_REQUIRED")
    if sys.version_info[:2] != (3, 12):
        raise ValueError("PYTHON_3_12_REQUIRED")


@contextmanager
def import_guard(*, scoring: bool) -> Iterator[list[str]]:
    """Block native search imports; scorer additionally cannot preprocess/compile."""
    forbidden = (
        "ortools",
        "tkb_core.solver.cp_sat",
        "tkb_core.solver.objectives",
        "tkb_core.solver.model_builder",
        "tkb_core.constraints.soft",
    )
    if scoring:
        forbidden += ("tkb_core.preprocessing",)
    original = builtins.__import__
    denied = []

    def guarded(name, *args, **kwargs):
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden):
            denied.append(name)
            raise ImportError("FORBIDDEN_IMPORT: " + name)
        return original(name, *args, **kwargs)

    builtins.__import__ = guarded
    try:
        yield denied
    finally:
        builtins.__import__ = original


def check_output_location(output: Path, payload: Path) -> None:
    """Reject resolved aliases and either direction of output/payload containment."""
    output, payload = output.resolve(), payload.resolve()
    if output.is_relative_to(payload) or payload.is_relative_to(output):
        raise ValueError("OUTPUT_PAYLOAD_OVERLAP")


def check_versions(installed: dict, locked: dict, environment: str) -> None:
    """Reject version drift, unrecorded distributions and solver in no-solver venv."""
    if any(locked.get(name) != version for name, version in installed.items()):
        raise ValueError("PACKAGE_VERSION_DRIFT")
    required = {"vnedu-tkb-core": "0.2.0", "pydantic": "2.14.1"}
    if environment == "solver":
        required["ortools"] = "9.15.6755"
    elif "ortools" in installed:
        raise ValueError("NO_SOLVER_CONTAINS_ORTOOLS")
    if any(installed.get(name) != version for name, version in required.items()):
        raise ValueError("MISSING_REQUIRED_PACKAGE")


def installed_environment(payload: Path, environment: str) -> dict:
    """Compare all installed Core .py bytes against frozen wheel and source."""
    import tkb_core

    package = Path(tkb_core.__file__).resolve().parent
    if (
        not package.is_relative_to(Path(sys.prefix).resolve())
        or "site-packages" not in package.parts
    ):
        raise ValueError("SOURCE_SHADOWING")
    distribution = metadata.distribution("vnedu-tkb-core")
    direct_url = json.loads(distribution.read_text("direct_url.json") or "{}")
    if direct_url.get("dir_info", {}).get("editable"):
        raise ValueError("EDITABLE_CORE")
    lock = payload / "source/uv.lock"
    locked = {p["name"]: p["version"] for p in tomllib.loads(lock.read_text())["package"]}
    installed = {
        d.metadata["Name"].lower().replace("_", "-"): d.version for d in metadata.distributions()
    }
    check_versions(installed, locked, environment)
    if environment == "no-solver" and importlib.util.find_spec("ortools") is not None:
        raise ValueError("ORTOOLS_IMPORTABLE")
    wheel = payload / "wheel/vnedu_tkb_core-0.2.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel) as archive:
        names = {n for n in archive.namelist() if n.startswith("tkb_core/") and n.endswith(".py")}
        actual = {"tkb_core/" + p.relative_to(package).as_posix() for p in package.rglob("*.py")}
        if names != actual or len(names) != 27:
            raise ValueError("CORE_FILE_MEMBERSHIP")
        for name in names:
            if not (
                archive.read(name)
                == (payload / "source/src" / name).read_bytes()
                == (package.parent / name).read_bytes()
            ):
                raise ValueError("INSTALLED_SOURCE_BYTES: " + name)
    return {
        "status": "PASS",
        "check": "INSTALLED_IDENTITY_ONLY",
        "environment": environment,
        "python_executable": sys.executable,
        "python_prefix": sys.prefix,
        "python_exact_version": platform.python_version(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "tkb_core_file": str(package / "__init__.py"),
        "installed_versions": installed,
        "source_files_compared": len(names),
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "lock_sha256": hashlib.sha256(lock.read_bytes()).hexdigest(),
        "performance": "NOT_MEASURED",
    }


def verify_installed_bundle(payload: Path) -> dict:
    """Re-use the frozen generator verifier under a native-search import guard."""
    with import_guard(scoring=False):
        path = payload / "source/benchmarks/generate_synthetic.py"
        spec = importlib.util.spec_from_file_location("windows_frozen_generator", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        root = payload / "source/benchmarks/artifacts/phase2a/task1-v1"
        manifest = module.verify_bundle(root)
        rows = []
        for entry in manifest.datasets:
            item = json.loads((root / entry.dataset_id / "manifest.json").read_bytes())
            rows.append(
                {
                    k: item[k]
                    for k in (
                        "dataset_id",
                        "input_fingerprint",
                        "ground_truth",
                        "baseline_score",
                        "known_optimum",
                        "p2_lower_bound",
                        "capacity_proof",
                        "dimensions",
                        "files",
                    )
                }
            )
    return {
        "status": "PASS",
        "search_executed": False,
        "datasets": rows,
        "dataset_count": len(rows),
        "performance": "NOT_MEASURED",
    }


def smoke_input() -> dict:
    """Tiny synthetic case with singles/doubles, four soft rules and three tiers."""
    return {
        "schema_version": "1.1",
        "school": {"school_id": "tiny-school", "academic_year": "2026-2027", "term": "demo"},
        "time_slots": [
            {"id": f"d{d}-p{p}", "day": d, "session": "AM", "period": p}
            for d in (1, 2)
            for p in (1, 2, 3)
        ],
        "classes": [{"id": "class-a"}, {"id": "class-b"}],
        "teachers": [{"id": "teacher-a"}, {"id": "teacher-b"}],
        "subjects": [{"id": "subject-a"}],
        "rooms": [],
        "teaching_requirements": [
            {
                "id": "req-a",
                "class_ids": ["class-a"],
                "teacher_ids": ["teacher-a"],
                "subject_id": "subject-a",
                "periods_per_cycle": 3,
                "block_durations": [1, 2],
            },
            {
                "id": "req-b",
                "class_ids": ["class-b"],
                "teacher_ids": ["teacher-b"],
                "subject_id": "subject-a",
                "periods_per_cycle": 1,
            },
        ],
        "locked_assignments": [{"occurrence_id": "req-a::1", "slot_id": "d1-p1"}],
        "constraint_config": {
            "policy_version": "0.1",
            "hard": [],
            "soft": [
                {
                    "id": "avoid",
                    "code": "TEACHER_AVOID_SLOTS",
                    "parameters": {"slot_ids": ["d1-p1"]},
                    "priority": 1,
                    "weight": 1,
                },
                {
                    "id": "session",
                    "code": "TEACHER_MAX_PERIODS_PER_SESSION",
                    "parameters": {"limit": 1, "session_ids": ["AM"]},
                    "priority": 1,
                    "weight": 1,
                },
                {
                    "id": "day",
                    "code": "TEACHER_MAX_PERIODS_PER_DAY",
                    "parameters": {"limit": 1},
                    "priority": 2,
                    "weight": 1,
                },
                {
                    "id": "window",
                    "code": "TEACHER_PREFERRED_PERIOD_WINDOW",
                    "parameters": {"first_period": 2, "last_period": 2, "session_ids": ["AM"]},
                    "priority": 3,
                    "weight": 1,
                },
            ],
        },
    }


def solve_arguments(input_path: Path, result_path: Path) -> list[str]:
    """Use unchanged Core defaults (60s/workers1/seed42 and guards)."""
    return ["solve", str(input_path), "--output", str(result_path)]


def write_json(path: Path, value: dict) -> None:
    """Exclusive output; no retry or evidence replacement."""
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def cli_case(
    root: Path,
    name: str,
    python: str | Path,
    args: Sequence[str | Path],
    expected_exit: int,
    field: str,
    expected: Any,
    *,
    runner: Callable[..., Any] | None = None,
) -> dict:
    """Capture exact argv/stdout/stderr/exit once, including failed expectations."""
    command = [str(python), "-I", "-B", "-X", "utf8", "-m", "tkb_core.cli", *map(str, args)]
    receipt_path = root / f"{name}.receipt.json"
    # Reserve the attempt before spawning; a partial receipt blocks reruns too.
    with receipt_path.open("x", encoding="utf-8") as receipt:
        record = {
            "argv": command,
            "cwd": str(root),
            "started_at_utc": datetime.now(UTC).isoformat(),
            "status": "STARTED",
            "exit_code": None,
            "reason": "CHILD_NOT_COMPLETED",
        }
        receipt.write(json.dumps(record) + "\n")
        receipt.flush()
        try:
            result = (runner or subprocess.run)(command, cwd=root, capture_output=True, check=False)
            (root / f"{name}.stdout.json").write_bytes(result.stdout)
            (root / f"{name}.stderr.txt").write_bytes(result.stderr)
            record["exit_code"] = result.returncode
            data = json.loads(result.stdout)
            record["expected_exit_code"] = expected_exit
            record["expected"] = {field: expected}
            good = result.returncode == expected_exit and data.get(field) == expected
            record.update(
                status="PASS" if good else "FAIL", reason=None if good else "CLI_EXPECTATION"
            )
        except Exception as exc:
            record.update(status="FAIL", reason=str(exc))
            raise
        finally:
            record["finished_at_utc"] = datetime.now(UTC).isoformat()
            receipt.seek(0)
            receipt.truncate()
            receipt.write(json.dumps(record, indent=2) + "\n")
    if not good:
        raise ValueError("CLI_EXPECTATION: " + name)
    return data


def smoke(root: Path) -> dict:
    """Run tiny CLI checks after native approval; never school-size search."""
    raw = smoke_input()
    input_path, result_path = root / "input.json", root / "result.json"
    write_json(input_path, raw)

    def cli(name, args, code, field, expected):
        return cli_case(root, name, sys.executable, args, code, field, expected)

    cli("validate-input", ["validate-input", input_path], 0, "status", "INPUT_VALID")
    result = cli("solve", solve_arguments(input_path, result_path), 0, "valid_schedule", True)
    if (
        result["schema_version"] != "1.2"
        or not result["metadata"]["solver_executed"]
        or [s["priority"] for s in result["quality"]["tier_runs"]] != [1, 2, 3]
    ):
        raise ValueError("SMOKE_QUALITY_OR_SCHEMA")
    validated = cli(
        "validate", ["validate-schedule", input_path, result_path], 0, "status", "SCHEDULE_VALID"
    )
    score = cli("score", ["evaluate-score", input_path, result_path], 0, "status", "OK")
    if (
        score != result["quality"]["score"]
        or score != validated["score"]
        or len(score["rules"]) != 4
    ):
        raise ValueError("SMOKE_SCORE_MISMATCH")
    stale = copy.deepcopy(result)
    stale["input_fingerprint"] = stale["quality"]["score"]["input_fingerprint"] = "0" * 64
    write_json(root / "stale.json", stale)
    (root / "malformed.json").write_text("{", encoding="utf-8")
    for cmd in ("evaluate-score", "validate-schedule"):
        row = cli(
            "stale-" + cmd, [cmd, input_path, root / "stale.json"], 2, "status", "INPUT_INVALID"
        )
        if row["diagnostics"][0]["code"] != "STALE_RESULT":
            raise ValueError("STALE_REASON")
        cli(
            "malformed-" + cmd,
            [cmd, input_path, root / "malformed.json"],
            2,
            "status",
            "INPUT_INVALID",
        )
    for name, hard in (
        ("invalid-locks", None),
        ("unknown-hard", "FUTURE_CUSTOM_HARD"),
        ("known-hard", "TEACHER_MAX_PERIODS_PER_DAY"),
    ):
        invalid = copy.deepcopy(raw)
        if hard is None:
            invalid["locked_assignments"].append({"occurrence_id": "req-a::2", "slot_id": "d1-p1"})
        else:
            invalid["constraint_config"]["hard"] = [
                {
                    "id": "hard",
                    "code": hard,
                    "parameters": {"limit": 1} if name == "known-hard" else {},
                }
            ]
        path = root / f"{name}.json"
        write_json(path, invalid)
        row = cli(
            name,
            ["solve", path],
            2,
            "status",
            "INPUT_INVALID" if hard is None else "UNSUPPORTED_FEATURE",
        )
        if row["assignments"] or row["metadata"]["solver_executed"]:
            raise ValueError("REJECTION_EXECUTED_SOLVER")
    return {"status": "PASS", "score_vector": score["tiers"], "performance": "NOT_MEASURED"}


def guard_score(input_path: Path, result_path: Path) -> dict:
    """No-solver validation/scoring must work with forbidden imports guarded."""
    if importlib.util.find_spec("ortools") is not None:
        raise ValueError("ORTOOLS_PRESENT")
    with import_guard(scoring=True):
        from tkb_core.contracts.input import ScheduleInput
        from tkb_core.contracts.output import ScheduleResult
        from tkb_core.validation.independent_validator import validate_schedule
        from tkb_core.validation.score_evaluator import evaluate_score

        problem = ScheduleInput.model_validate_json(input_path.read_bytes())
        result = ScheduleResult.model_validate_json(result_path.read_bytes())
        if result.input_fingerprint != problem.fingerprint():
            raise ValueError("STALE_RESULT")
        validation = validate_schedule(problem, result.assignments)
        score = evaluate_score(problem, result.assignments)
        if not validation.valid or score != result.quality.score:
            raise ValueError("NO_SOLVER_SCORE_OR_VALIDITY")
    return {"status": "PASS", "score_vector": score.tiers, "search_executed": False}


def registry(result_path: Path) -> dict:
    """Pending/disabled rules through installed APIs; pending must never search."""
    from tkb_core.constraints.registry import DEFINITIONS, RuleDefinition
    from tkb_core.contracts.capabilities import check_capabilities
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.contracts.output import ScheduleResult
    from tkb_core.domain.errors import CoreError
    from tkb_core.domain.rule_parameters import MaxDayParameters
    from tkb_core.solver.cp_sat import solve
    from tkb_core.validation.independent_validator import validate_schedule
    from tkb_core.validation.score_evaluator import evaluate_score

    if len(DEFINITIONS) != 4 or any(d.supported_modes != ("soft",) for d in DEFINITIONS.values()):
        raise ValueError("REGISTRY_READY_MISMATCH")
    check_capabilities(ScheduleInput.model_validate(smoke_input()))
    DEFINITIONS["PENDING_RULE"] = RuleDefinition("PENDING_RULE", "pending", MaxDayParameters)
    try:
        raw = smoke_input()
        raw["constraint_config"]["soft"] = [
            {
                "id": "pending",
                "code": "PENDING_RULE",
                "parameters": {"limit": 0},
                "priority": 1,
                "weight": 1,
            }
        ]
        problem = ScheduleInput.model_validate(raw)
        try:
            check_capabilities(problem)
        except CoreError as exc:
            if exc.status != "UNSUPPORTED_FEATURE":
                raise ValueError("PENDING_CAPABILITY_STATUS") from exc
        else:
            raise ValueError("PENDING_RULE_ACCEPTED")
        with import_guard(scoring=False) as denied:
            result = solve(problem)
        if denied:
            raise ValueError("PENDING_RULE_ATTEMPTED_NATIVE_IMPORT")
        score = evaluate_score(problem, ())
        validation = validate_schedule(problem, ())
        if (
            result.status != "UNSUPPORTED_FEATURE"
            or result.assignments
            or result.metadata.solver_executed
            or score.status != "UNSUPPORTED_FEATURE"
            or score.tiers is not None
            or validation.valid
        ):
            raise ValueError("PENDING_REJECTION_MISMATCH")
        raw["constraint_config"]["soft"][0]["enabled"] = False
        problem = ScheduleInput.model_validate(raw)
        assignments = ScheduleResult.model_validate_json(result_path.read_bytes()).assignments
        score = evaluate_score(problem, assignments)
        if not validate_schedule(problem, assignments).valid or score.tiers != (0, 0, 0):
            raise ValueError("DISABLED_RULE_APPLIED")
    finally:
        del DEFINITIONS["PENDING_RULE"]
    return {
        "status": "PASS",
        "ready_soft_families": 4,
        "pending": "UNSUPPORTED_FEATURE",
        "disabled_score": [0, 0, 0],
        "search_executed": False,
    }


def main() -> int:
    """Explicit Windows commands; a supplied reference is not automated approval."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("environment", "bundle", "smoke", "registry", "guard-score")
    )
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, required=True, help="New directory per check; never overwritten"
    )
    parser.add_argument("--approval-reference", required=True)
    parser.add_argument("--machine-id", required=True)
    parser.add_argument("--environment", choices=("solver", "no-solver"), default="solver")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    created_output = False
    try:
        native_gate(args.approval_reference)
        sys.dont_write_bytecode = True
        check_output_location(args.output, args.payload)
        if args.mode in ("guard-score", "registry") and args.result is None:
            raise ValueError("RESULT_REQUIRED")
        if args.mode == "guard-score" and (args.input is None or args.environment != "no-solver"):
            raise ValueError("NO_SOLVER_INPUT_REQUIRED")
        if args.environment == "no-solver" and args.mode == "smoke":
            raise ValueError("NO_SOLVER_CANNOT_SEARCH")
        args.output.mkdir(parents=True, exist_ok=False)
        created_output = True
        context = {
            "machine_id": args.machine_id,
            "approval_reference": args.approval_reference,
            "argv": sys.argv,
            "cwd": str(Path.cwd()),
            "utc": datetime.now(UTC).isoformat(),
            "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "windows_preflight_status": "NOT_ASSESSED",
        }
        write_json(args.output / "invocation.json", context)
        # Load only the handoff helper, never the Linux benchmark runner.
        spec = importlib.util.spec_from_file_location(
            "windows_payload_helper", Path(__file__).with_name("windows_payload.py")
        )
        helper = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(helper)
        inventory = json.loads(args.inventory.read_bytes())
        if (
            inventory["core_commit"] != helper.CORE_COMMIT
            or inventory["core_tree"] != helper.CORE_TREE
            or inventory["expected_wheel_sha256"] != helper.WHEEL_SHA
            or inventory["expected_lock_sha256"] != helper.LOCK_SHA
            or inventory["expected_bundle_manifest_sha256"] != helper.BUNDLE_SHA
        ):
            raise ValueError("FROZEN_IDENTITY_MISMATCH")
        checked = helper.verify_payload(args.payload, inventory)
        write_json(args.output / "payload-verification.json", checked)
        if (
            helper.sha((args.payload / "source/uv.lock").read_bytes()) != helper.LOCK_SHA
            or helper.sha(
                (args.payload / "wheel/vnedu_tkb_core-0.2.0-py3-none-any.whl").read_bytes()
            )
            != helper.WHEEL_SHA
            or helper.sha(
                (
                    args.payload / "source/benchmarks/artifacts/phase2a/task1-v1/manifest.json"
                ).read_bytes()
            )
            != helper.BUNDLE_SHA
        ):
            raise ValueError("FROZEN_BYTES_MISMATCH")
        environment = installed_environment(args.payload, args.environment)
        write_json(args.output / "installed-identity.json", environment)
        if args.mode == "environment":
            result = environment
        elif args.mode == "bundle":
            result = verify_installed_bundle(args.payload)
        elif args.mode == "smoke":
            result = smoke(args.output)
        elif args.mode == "registry":
            result = registry(args.result)
        else:
            result = guard_score(args.input, args.result)
        write_json(
            args.output / "result.json" if args.mode != "smoke" else args.output / "summary.json",
            result,
        )
    except Exception as exc:
        failure = {
            "status": "BLOCKED_OR_FAILED",
            "reason": str(exc),
            "windows_preflight_status": "NOT_ASSESSED",
        }
        if created_output:
            write_json(args.output / "failure.json", failure)
        print(json.dumps(failure))
        return 2
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
