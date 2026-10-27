"""Single-target trace preparation and instrumentation, outside Scheduling Core."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from contextlib import ExitStack, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self
from unittest.mock import patch

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import JsonValue, model_validator

from benchmarks import run_benchmarks as runner
from tkb_core.domain.models import DomainModel
from tkb_core.solver.options import SolveOptions

if TYPE_CHECKING:
    from tkb_core.constraints.soft import CompiledSoft
    from tkb_core.preprocessing.feasibility import PreparedProblem
    from tkb_core.solver.model_builder import BuiltModel

ROOT = Path(__file__).resolve().parents[1]
LEGACY = runner._OWNER_ROOT.parent.parent / "benchmarks/artifacts/phase2a/pilot-linux-20261027-v1"
PLAN_SHA = "6b8a324560b1857555f686a955f5af79468e5f80a00d830466b9253e648a9e61"
INPUT_SHA = "7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735"
WITNESS_SHA = "f9b5274529c9d1bd4d4c301b2626336bd0128b38b57901b90627ca4be1121a57"
MODEL_SHA = "f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083"
FINGERPRINT = "126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee"
LOGGING = {
    "log_search_progress": True,
    "log_to_stdout": False,
    "log_to_response": False,
    "callback": "raw_utf8_flush",
    "first_feasible_reason": "NOT_INSTRUMENTED",
}
LIMITS = runner.RunLimits(watchdog_seconds=150.0, max_resident_bytes=1024**3)


class Identity(DomainModel):
    """Exact diagnostic snapshot; numerical run policy cannot be changed."""

    schema_version: Literal["1.0"] = "1.0"
    dataset_id: Literal["c10-tight-s101"] = "c10-tight-s101"
    input_sha256: runner.SHA
    witness_sha256: runner.SHA
    model_sha256: runner.SHA
    runtime: dict[str, JsonValue]
    machine: dict[str, JsonValue]
    source_ids: dict[str, JsonValue]
    driver_sha256: runner.SHA
    options: SolveOptions
    limits: runner.RunLimits
    logging: dict[str, JsonValue]

    @model_validator(mode="after")
    def fixed(self) -> Self:
        if (
            (self.input_sha256, self.witness_sha256, self.model_sha256)
            != (
                INPUT_SHA,
                WITNESS_SHA,
                MODEL_SHA,
            )
            or self.options != SolveOptions()
            or self.limits != LIMITS
        ):
            raise ValueError("TARGET_OR_POLICY_DRIFT")
        if compare_identity(LOGGING, self.logging):
            raise ValueError("LOGGING_POLICY_DRIFT")
        return self


class Candidate(DomainModel):
    """Prepared snapshot, explicitly without execution authorization."""

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["PREPARED_NOT_AUTHORIZED"] = "PREPARED_NOT_AUTHORIZED"
    run_id: runner.CampaignId
    output_root: Path
    legacy_plan_sha256: runner.SHA
    identity: Identity
    legacy_gate: Literal["PASS", "BLOCKED_MACHINE_DRIFT"]
    legacy_differences: dict[str, dict[str, JsonValue]]

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if not self.output_root.is_absolute() or self.legacy_plan_sha256 != PLAN_SHA:
            raise ValueError("BASELINE_IDENTITY_INVALID")
        if (self.legacy_gate == "PASS") != (not self.legacy_differences):
            raise ValueError("LEGACY_GATE_INCONSISTENT")
        return self


class Authorization(DomainModel):
    """An externally supplied approval record bound to one prepared root/run."""

    schema_version: Literal["1.0"] = "1.0"
    approved: Literal[True]
    action: Literal["RUN_ONE_FEASIBILITY_TRACE"]
    baseline_sha256: runner.SHA
    run_id: runner.CampaignId
    output_root: Path


def compare_identity(expected: dict[str, Any], actual: dict[str, Any]) -> tuple[str, ...]:
    """Return exact differing field paths, distinguishing missing/null and JSON types."""
    differences = []
    for key in sorted(expected.keys() | actual.keys()):
        if key not in expected or key not in actual or type(expected[key]) is not type(actual[key]):
            differences.append(key)
        elif isinstance(expected[key], dict):
            differences.extend(key + "." + p for p in compare_identity(expected[key], actual[key]))
        elif expected[key] != actual[key]:
            differences.append(key)
    return tuple(differences)


def _target() -> tuple[runner.CampaignPlan, runner.PlannedCase]:
    if runner._sha(LEGACY / "plan.json") != PLAN_SHA:
        raise ValueError("LEGACY_PLAN_DRIFT")
    plan = runner.CampaignPlan.model_validate_json((LEGACY / "plan.json").read_text())
    return plan, next(c for c in plan.primary if c.dataset_id == "c10-tight-s101")


def model_hash(built: BuiltModel) -> str:
    """Hash the exact UTF8 proto representation used by the static witness audit."""
    import hashlib

    return hashlib.sha256(str(built.model.proto).encode()).hexdigest()


def _build_target() -> tuple[Any, Any, Any]:
    from benchmarks.generate_synthetic import WitnessArtifact, _sources
    from tkb_core.constraints.soft import compile_soft
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.preprocessing.feasibility import prepare
    from tkb_core.solver.model_builder import build_model
    from tkb_core.validation.independent_validator import validate_schedule
    from tkb_core.validation.score_evaluator import evaluate_score

    _, case = _target()
    meta = runner._json_object(case.dataset_manifest.read_text())
    if runner._sha(case.dataset_manifest) != case.manifest_sha256 or _sources() != meta["sources"]:
        raise ValueError("DATASET_SOURCE_DRIFT")
    for name, digest in meta["files"].items():
        if runner._sha(case.input_path.parent / name) != digest:
            raise ValueError("INPUT_OR_WITNESS_DRIFT")
    if (runner._sha(case.input_path), runner._sha(case.input_path.parent / "witness.json")) != (
        INPUT_SHA,
        WITNESS_SHA,
    ):
        raise ValueError("TARGET_BYTES_DRIFT")
    problem = ScheduleInput.model_validate_json(case.input_path.read_text())
    witness = WitnessArtifact.model_validate_json(
        (case.input_path.parent / "witness.json").read_text()
    )
    if problem.fingerprint() != FINGERPRINT or witness.input_fingerprint != FINGERPRINT:
        raise ValueError("FINGERPRINT_DRIFT")
    score = evaluate_score(problem, witness.assignments)
    if not validate_schedule(problem, witness.assignments).valid or score.tiers != (0, 78, 0):
        raise ValueError("WITNESS_INVALID")
    prepared = prepare(problem, SolveOptions())
    built = build_model(prepared)
    compiled = compile_soft(prepared, built)
    built.model.clear_objective()
    if built.model.validate() or built.model.has_objective() or model_hash(built) != MODEL_SHA:
        raise ValueError("MODEL_DRIFT")
    return prepared, built, compiled


def capture_identity() -> dict[str, JsonValue]:
    """Capture installed runtime and build-only identity with native solver blocked."""
    from ortools.sat.python import cp_model

    with patch.object(
        cp_model, "CpSolver", side_effect=AssertionError("SEARCH_FORBIDDEN")
    ) as guard:
        plan, _ = _target()
        runtime = runner._runtime_identity(
            python=Path(sys.executable),
            preflight_dir=plan.preflight_dir,
            lock_path=ROOT / "uv.lock",
        )
        if runtime != plan.runtime_identity or runner._source_ids() != plan.source_ids:
            raise ValueError("FROZEN_RUNTIME_OR_SOURCE_DRIFT")
        _build_target()
        guard.assert_not_called()
        identity = Identity(
            input_sha256=INPUT_SHA,
            witness_sha256=WITNESS_SHA,
            model_sha256=MODEL_SHA,
            runtime=runtime,
            machine=runner._machine_identity(),
            source_ids=runner._source_ids(),
            driver_sha256=runner._sha(Path(__file__)),
            options=SolveOptions(),
            limits=LIMITS,
            logging=LOGGING,
        )
        return identity.model_dump(mode="json")


def legacy_comparison(
    identity: dict[str, JsonValue],
) -> tuple[str, dict[str, dict[str, JsonValue]]]:
    """Run the unmodified historical gate, accepting only machine drift as a candidate."""
    plan, _ = _target()
    differences = {}
    frozen = plan.environment["machine"]
    current = identity["machine"]
    for name in compare_identity(frozen, current):
        if "." in name:
            # Keep nested values intact instead of inventing normalized machine fields.
            key = name.split(".")[0]
        else:
            key = name
        differences["machine." + key] = {"frozen": frozen.get(key), "current": current.get(key)}
    try:
        runner._check_campaign_identity(plan, LEGACY / "plan.json", plan.preflight_dir)
        gate = "PASS"
    except ValueError as exc:
        if str(exc) != "MACHINE_DRIFT":
            raise
        gate = "BLOCKED_MACHINE_DRIFT"
    if runner._machine_identity() != current:
        raise ValueError("PREPARE_MACHINE_CHANGED")
    return gate, differences


def prepare_trace(root: Path, run_id: str) -> dict[str, JsonValue]:
    """Write a new candidate or blocked report; never grant approval or spawn search."""
    if root.exists() or root.is_symlink():
        raise FileExistsError(root)
    root = root.resolve()
    plan, _ = _target()
    protected = (
        LEGACY,
        plan.bundle_dir,
        plan.preflight_dir,
        ROOT / "benchmarks/artifacts/phase2a/tight10-static-v1",
        ROOT / "benchmarks/artifacts/phase2a/tight10-auxiliary-v1",
    )
    if any(root.is_relative_to(p.resolve()) for p in protected):
        raise ValueError("OUTPUT_INSIDE_FROZEN_EVIDENCE")
    root.mkdir(parents=True)
    try:
        from ortools.sat.python import cp_model

        with patch.object(cp_model, "CpSolver", side_effect=AssertionError("SEARCH_FORBIDDEN")):
            identity = Identity.model_validate(capture_identity())
            gate, differences = legacy_comparison(identity.model_dump(mode="json"))
        candidate = Candidate(
            run_id=run_id,
            output_root=root,
            legacy_plan_sha256=PLAN_SHA,
            identity=identity,
            legacy_gate=gate,
            legacy_differences=differences,
        )
        runner._write_json(root / "candidate-baseline.json", candidate, exclusive=True)
        result = {
            "schema_version": "1.0",
            "status": candidate.status,
            "candidate_sha256": runner._sha(root / "candidate-baseline.json"),
            "legacy_gate": gate,
            "legacy_differences": differences,
            "search_executed": False,
            "authorization_created": False,
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {
            "schema_version": "1.0",
            "status": "BLOCKED",
            "reason": str(exc),
            "search_executed": False,
            "authorization_created": False,
        }
    runner._write_json(root / "preparation-result.json", result, exclusive=True)
    return result


def check_authorization(root: Path, authorization: Path, *, child: bool = False) -> Candidate:
    """Check approval/root, exact current snapshot and, in child, the parent's lease."""
    root = root.resolve()
    candidate = Candidate.model_validate_json((root / "candidate-baseline.json").read_text())
    approval = Authorization.model_validate_json(authorization.read_text())
    if (
        approval.baseline_sha256 != runner._sha(root / "candidate-baseline.json")
        or approval.run_id != candidate.run_id
        or approval.output_root != root
        or candidate.output_root != root
    ):
        raise ValueError("AUTHORIZATION_SCOPE_MISMATCH")
    if child:
        lease = runner._json_object((runner._OWNER_ROOT / "active.json").read_text())
        start = runner._json_object((root / "START.json").read_text())
        if (
            lease.get("state") != "RUNNING"
            or lease.get("pid") != os.getppid()
            or lease.get("campaign_root") != str(root)
            or lease.get("campaign_id") != candidate.run_id
            or start
            != {
                "baseline_sha256": approval.baseline_sha256,
                "parent_pid": os.getppid(),
                "run_id": candidate.run_id,
            }
        ):
            raise ValueError("PARENT_LEASE_MISMATCH")
    elif (root / "START.json").exists() or (root / "attempt").exists():
        raise ValueError("ALREADY_STARTED")
    current = Identity.model_validate(capture_identity()).model_dump(mode="json")
    changed = compare_identity(candidate.identity.model_dump(mode="json"), current)
    if changed:
        raise ValueError("IDENTITY_DRIFT:" + ",".join(changed))
    return candidate


def classify_trace(text: str, branches: int | None, complete: bool) -> str:
    """Recognize positive search evidence; missing/zero/truncated data stays undetermined."""
    if not complete:
        return "UNDETERMINED"
    if branches is not None and branches > 0:
        return "SEARCH_ENTERED"
    search = re.search(r"Starting (?:main |sequential )?search at \d", text)
    presolve = text.find("Starting presolve")
    if search and (presolve < 0 or presolve < search.start()):
        return "SEARCH_ENTERED"
    return "UNDETERMINED"


def write_log_chunk(handle: Any, chunk: str) -> None:
    """Preserve native chunks without parsing or changing their contents."""
    handle.write(chunk)
    handle.flush()


def trace_feasibility(
    prepared: PreparedProblem,
    built: BuiltModel,
    compiled: CompiledSoft,
    options: SolveOptions,
    log_path: Path,
    *,
    logging_mode: Literal["logging_off", "logging_on"] = "logging_on",
) -> dict[str, JsonValue]:
    """Instrument one stage; the run/child entry points must authorize before calling."""
    from ortools.sat.python import cp_model
    from ortools.sat.python.cp_model_helper import SatParameters

    from tkb_core.solver.objectives import _run_stage
    from tkb_core.validation.independent_validator import validate_schedule
    from tkb_core.validation.score_evaluator import evaluate_score

    if (
        SolveOptions.model_validate(options.model_dump()) != SolveOptions()
        or model_hash(built) != MODEL_SHA
    ):
        raise ValueError("TRACE_POLICY_OR_MODEL_DRIFT")
    if logging_mode not in ("logging_off", "logging_on"):
        raise ValueError("LOGGING_POLICY_DRIFT")
    logging_on = logging_mode == "logging_on"
    constructor, calls, solves, captured = cp_model.CpSolver, 0, 0, None
    log_errors = []
    outcome = None
    error = None
    parameters = None
    callback_state = None
    start = time.monotonic()
    try:
        log_file = log_path.open("x", encoding="utf-8") if logging_on else nullcontext(None)
        with log_file as handle, ExitStack() as stack:

            def factory():
                nonlocal calls, solves, captured, parameters
                calls += 1
                if calls != 1:
                    raise ValueError("MULTIPLE_SOLVER_CONSTRUCTORS")
                solver = constructor()
                captured = solver
                solver.parameters.log_search_progress = logging_on
                solver.parameters.log_to_stdout = False
                solver.parameters.log_to_response = False

                def log(chunk):
                    try:
                        write_log_chunk(handle, chunk)
                    except OSError as exc:
                        log_errors.append(type(exc).__name__)
                        raise

                solver.log_callback = log if logging_on else None
                native_solve = solver.solve

                def checked_solve(model, solution_callback=None):
                    nonlocal solves, parameters, callback_state
                    solves += 1
                    expected = SatParameters()
                    for key, value in {
                        "max_time_in_seconds": 60.0,
                        "num_search_workers": 1,
                        "random_seed": 42,
                        "relative_gap_limit": 0.0,
                        "absolute_gap_limit": 0.0,
                        "log_search_progress": logging_on,
                        "log_to_stdout": False,
                        "log_to_response": False,
                    }.items():
                        setattr(expected, key, value)
                    parameters = str(solver.parameters)
                    if solves != 1 or parameters != str(expected) or model_hash(built) != MODEL_SHA:
                        raise ValueError("SOLVE_PARAMETER_OR_MODEL_DRIFT")
                    callback_state = {
                        "log_callback": (
                            "raw_utf8_flush"
                            if solver.log_callback is log
                            else None
                            if solver.log_callback is None
                            else "UNEXPECTED"
                        ),
                        "best_bound_callback": getattr(solver, "best_bound_callback", None)
                        is not None,
                        "solution_callback": solution_callback is not None,
                    }
                    if (
                        solver.log_callback is not (log if logging_on else None)
                        or callback_state["best_bound_callback"]
                        or callback_state["solution_callback"]
                    ):
                        raise ValueError("SOLVE_CALLBACK_DRIFT")
                    return native_solve(model)

                stack.enter_context(patch.object(solver, "solve", side_effect=checked_solve))
                return solver

            stack.enter_context(patch.object(cp_model, "CpSolver", side_effect=factory))
            try:
                outcome = _run_stage(prepared, built, compiled, options, None, 60.0)
            except (OSError, ValueError, RuntimeError) as exc:
                error = type(exc).__name__ + ":" + str(exc)
    except FileExistsError:
        raise
    except OSError as exc:
        error = (error + ";" if error else "") + type(exc).__name__ + ":" + str(exc)
        log_errors.append("LOG_CLOSE_OR_OPEN_ERROR")
    end = time.monotonic()
    try:
        text = log_path.read_text() if logging_on else ""
    except OSError as exc:
        text = ""
        error = (error + ";" if error else "") + type(exc).__name__ + ":" + str(exc)
        log_errors.append("LOG_READ_ERROR")
    counters = {
        name: None
        for name in (
            "wall_time",
            "user_time",
            "deterministic_time",
            "num_branches",
            "num_conflicts",
            "num_booleans",
            "num_binary_propagations",
            "num_integer_propagations",
            "num_restarts",
            "num_lp_iterations",
        )
    }
    response_reason = "NO_RESPONSE"
    response_text = response_stats = None
    if captured is not None:
        try:
            response = captured.response_proto
            response_text, response_stats = str(response), captured.response_stats()
            response_reason = None
            for name in (
                "wall_time",
                "user_time",
                "deterministic_time",
                "num_branches",
                "num_conflicts",
                "num_booleans",
                "num_binary_propagations",
                "num_integer_propagations",
            ):
                counters[name] = getattr(captured, name, None)
            counters["num_restarts"] = getattr(response, "num_restarts", None)
            counters["num_lp_iterations"] = getattr(response, "num_lp_iterations", None)
        except RuntimeError:
            pass
    stage_complete = outcome is not None and calls == solves == 1
    capture_complete = not error and not log_errors and bool(text)
    complete = stage_complete and not error and (capture_complete or not logging_on)
    result = {
        "schema_version": "1.0",
        "logging_mode": logging_mode,
        "stage_complete": stage_complete,
        "trace_complete": bool(complete) if logging_on else None,
        "trace_capture_status": ("COMPLETE" if complete else "FAILED")
        if logging_on
        else "DISABLED",
        "missing_log_reason": None if logging_on else "LOGGING_DISABLED",
        "elapsed_to_search_marker_seconds": None,
        "search_marker_reason": "NOT_PARSED" if logging_on else "LOGGING_DISABLED",
        "error": error,
        "log_errors": log_errors,
        "raw_solver_status": outcome.status.value if outcome else None,
        "constructor_calls": calls,
        "solve_calls": solves,
        "stage_start_monotonic": start,
        "stage_end_monotonic": end,
        "stage_elapsed_seconds": end - start,
        "parameters": parameters,
        "callback_state": callback_state,
        "callback_state_reason": None if callback_state is not None else "NOT_REACHED_SOLVE",
        "response": response_text,
        "response_stats": response_stats,
        "counters": counters,
        "response_reason": response_reason,
        "counter_missing_reasons": {
            key: response_reason or "FIELD_NOT_AVAILABLE"
            for key, value in counters.items()
            if value is None
        },
        "phase": classify_trace(text, counters.get("num_branches"), bool(complete)),
        "correctness": "NOT_ASSESSED",
        "valid_schedule": False,
        "assignments": [],
        "score": None,
        "quality_proved": False,
        "optimal_prefix": [],
        "first_feasible_elapsed_seconds": None,
        "first_feasible_reason": "NOT_INSTRUMENTED",
    }
    if complete and outcome.status.value in ("FEASIBLE", "OPTIMAL"):
        hard = validate_schedule(prepared.normalized.problem, outcome.assignments)
        score = evaluate_score(prepared.normalized.problem, outcome.assignments)
        rules = {r.rule_id: (r.raw_penalty, r.weighted_penalty) for r in score.rules}
        tiers = {p: score.tiers[p - 1] for p in compiled.tiers} if score.tiers is not None else None
        good = (
            hard.valid
            and score.status == "OK"
            and rules == outcome.rule_values
            and tiers == outcome.tier_values
        )
        result["correctness"] = "PASS" if good else "FAIL"
        if good:
            result.update(
                valid_schedule=True,
                assignments=[a.model_dump(mode="json") for a in outcome.assignments],
                score=score.model_dump(mode="json"),
            )
    elif outcome is not None and outcome.status.value in ("INFEASIBLE", "MODEL_INVALID"):
        result["correctness"] = "FAIL"
    return result


def _run_parent(root: Path, authorization: Path) -> dict[str, JsonValue]:
    candidate = check_authorization(root, authorization)
    with runner._campaign_owner(runner._OWNER_ROOT, root, candidate.run_id) as lease:
        try:
            check_authorization(root, authorization)
            headroom = runner.check_headroom(1024**3)
            if headroom.status != "PASS" or shutil.disk_usage(root).free < 256 * 1024**2:
                raise ValueError("ADMISSION_BLOCKED")
        except (OSError, ValueError) as exc:
            return {"status": "BLOCKED", "reason": str(exc)}
        runner._write_json(
            root / "identity-before-run.json",
            {
                "headroom": headroom.model_dump(mode="json"),
                "context": runner._operational_context(),
                "identity": candidate.identity.model_dump(mode="json"),
            },
            exclusive=True,
        )
        frozen_approval = root / "authorization.json"
        if authorization.resolve() != frozen_approval:
            with frozen_approval.open("xb") as handle:
                handle.write(authorization.read_bytes())
        check_authorization(root, frozen_approval)
        runner._write_json(
            root / "START.json",
            {
                "baseline_sha256": runner._sha(root / "candidate-baseline.json"),
                "parent_pid": os.getpid(),
                "run_id": candidate.run_id,
            },
            exclusive=True,
        )
        execution = runner.supervise_linux(
            (
                str(Path(sys.executable).absolute()),
                "-I",
                str(Path(__file__).resolve()),
                "_child",
                "--root",
                str(root),
                "--authorization",
                str(frozen_approval),
            ),
            root / "attempt",
            candidate.identity.limits,
        )
        if (
            execution.pid is not None and execution.raw_wait_status is None
        ) or execution.measurement_reason == "REAP_UNCONFIRMED":
            lease["state"] = "NEEDS_REVIEW"
        runner._write_json(root / "execution.json", execution, exclusive=True)
        files = {str(p.relative_to(root)): runner._sha(p) for p in root.rglob("*") if p.is_file()}
        runner._write_json(
            root / "manifest.json", {"schema_version": "1.0", "files": files}, exclusive=True
        )
        harness = (
            "MEASUREMENT_BLOCKED"
            if execution.measurement_status != "OK"
            else "WATCHDOG_TIMEOUT"
            if execution.stop_reason == "WATCHDOG"
            else "RESOURCE_STOP"
            if execution.stop_reason == "RESOURCE_LIMIT"
            else "CRASH"
            if execution.signal is not None
            else "CHILD_ERROR"
            if execution.exit_code != 0
            else "COMPLETE"
        )
        return {
            "status": "TERMINAL",
            "harness_status": harness,
            "measurement_status": execution.measurement_status,
            "exit_code": execution.exit_code,
        }


def _child(root: Path, authorization: Path) -> dict[str, JsonValue]:
    from ortools.sat.python import cp_model

    candidate = check_authorization(root, authorization, child=True)
    with patch.object(cp_model, "CpSolver", side_effect=AssertionError("SEARCH_FORBIDDEN")):
        prepared, built, compiled = _build_target()
    check_authorization(root, authorization, child=True)
    runner._write_json(root / "attempt/child-identity.json", candidate.identity, exclusive=True)
    result = trace_feasibility(
        prepared, built, compiled, candidate.identity.options, root / "attempt/trace.log"
    )
    runner._write_json(root / "attempt/trace-result.json", result, exclusive=True)
    for name, key in (
        ("parameters.txt", "parameters"),
        ("response.txt", "response"),
        ("response-stats.txt", "response_stats"),
    ):
        if result[key] is not None:
            (root / "attempt" / name).write_text(result[key], encoding="utf-8")
    runner._write_json(
        root / "attempt/independent-checks.json",
        {
            "correctness": result["correctness"],
            "valid_schedule": result["valid_schedule"],
            "score": result["score"],
            "quality_proved": False,
        },
        exclusive=True,
    )
    if result["valid_schedule"]:
        runner._write_json(
            root / "attempt/assignments.json",
            {
                "assignments": result["assignments"],
            },
            exclusive=True,
        )
    return {
        "status": "CORRECTNESS_FAIL"
        if result["correctness"] == "FAIL"
        else "TRACE_COMPLETE"
        if result["trace_complete"]
        else "TRACE_INCOMPLETE"
    }


LoggingMode = Literal["logging_off", "logging_on"]
PAIR_ORDER = ("logging_off", "logging_on")
PAIR_PATHS = ("runs/01-off", "runs/02-on")
PAIR_PROFILES = {
    "logging_off": LOGGING | {"log_search_progress": False, "callback": None},
    "logging_on": LOGGING,
}
PAIR_POLICY = {
    "power_precondition": "AC_ON",
    "workload_control": "UNCONTROLLED",
    "competing_workload": "UNKNOWN",
    "cooldown": "NONE",
}


class PairCandidate(DomainModel):
    """Exactly two fresh runs sharing one approved snapshot, with fixed treatments."""

    schema_version: Literal["1.0"] = "1.0"
    kind: Literal["tight10_logging_pair"] = "tight10_logging_pair"
    status: Literal["PREPARED_NOT_AUTHORIZED"] = "PREPARED_NOT_AUTHORIZED"
    pair_id: runner.CampaignId
    output_root: Path
    run_ids: tuple[runner.CampaignId, runner.CampaignId]
    order: tuple[Literal["logging_off"], Literal["logging_on"]] = PAIR_ORDER
    run_paths: tuple[Literal["runs/01-off"], Literal["runs/02-on"]] = PAIR_PATHS
    common_identity: dict[str, JsonValue]
    profiles: dict[str, JsonValue]
    operational_policy: dict[str, JsonValue]
    legacy_plan_sha256: runner.SHA = PLAN_SHA
    legacy_gate: Literal["PASS", "BLOCKED_MACHINE_DRIFT"]
    legacy_differences: dict[str, dict[str, JsonValue]]

    @model_validator(mode="after")
    def fixed(self) -> Self:
        if (
            len(self.pair_id) > 60
            or self.run_ids != (self.pair_id + "-off", self.pair_id + "-on")
            or not self.output_root.is_absolute()
            or self.output_root != self.output_root.resolve()
            or self.legacy_plan_sha256 != PLAN_SHA
            or (self.legacy_gate == "PASS") != (not self.legacy_differences)
            or "logging" in self.common_identity
            or compare_identity(PAIR_PROFILES, self.profiles)
            or compare_identity(PAIR_POLICY, self.operational_policy)
        ):
            raise ValueError("PAIR_SCOPE_OR_POLICY_DRIFT")
        full = Identity.model_validate(self.common_identity | {"logging": LOGGING})
        if compare_identity(
            full.model_dump(mode="json", exclude={"logging"}), self.common_identity
        ):
            raise ValueError("COMMON_IDENTITY_INCOMPLETE")
        return self


class PairAuthorization(DomainModel):
    """External approval for one ordered pair; single-trace approval is insufficient."""

    schema_version: Literal["1.0"] = "1.0"
    approved: Literal[True]
    action: Literal["RUN_ONE_LOGGING_PAIR"]
    baseline_sha256: runner.SHA
    pair_id: runner.CampaignId
    output_root: Path
    run_ids: tuple[runner.CampaignId, runner.CampaignId]
    order: tuple[Literal["logging_off"], Literal["logging_on"]]


def prepare_pair(root: Path, pair_id: str) -> dict[str, JsonValue]:
    """Capture a new build-only pair snapshot; never acquire a lease or grant approval."""
    from ortools.sat.python import cp_model

    if root.exists() or root.is_symlink():
        raise FileExistsError(root)
    root = root.resolve()
    plan, _ = _target()
    protected = [LEGACY, plan.bundle_dir, plan.preflight_dir]
    protected.extend(p for p in (ROOT / "benchmarks/artifacts/phase2a").glob("*") if p.is_dir())
    if any(root.is_relative_to(p.resolve()) for p in protected):
        raise ValueError("OUTPUT_INSIDE_FROZEN_EVIDENCE")
    root.mkdir(parents=True)
    try:
        with patch.object(
            cp_model, "CpSolver", side_effect=AssertionError("SEARCH_FORBIDDEN")
        ) as guard:
            full = Identity.model_validate(capture_identity())
            gate, differences = legacy_comparison(full.model_dump(mode="json"))
            guard.assert_not_called()
        candidate = PairCandidate(
            pair_id=pair_id,
            output_root=root,
            run_ids=(pair_id + "-off", pair_id + "-on"),
            common_identity=full.model_dump(mode="json", exclude={"logging"}),
            profiles=PAIR_PROFILES,
            operational_policy=PAIR_POLICY,
            legacy_gate=gate,
            legacy_differences=differences,
        )
        runner._write_json(root / "pair-candidate.json", candidate, exclusive=True)
        result = {
            "schema_version": "1.0",
            "status": candidate.status,
            "candidate_sha256": runner._sha(root / "pair-candidate.json"),
            "legacy_gate": gate,
            "legacy_differences": differences,
            "search_executed": False,
            "authorization_created": False,
            "context": runner._operational_context(),
        }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result = {
            "schema_version": "1.0",
            "status": "BLOCKED",
            "reason": str(exc),
            "search_executed": False,
            "authorization_created": False,
        }
    runner._write_json(root / "preparation-result.json", result, exclusive=True)
    return result


def _pair_start(candidate: PairCandidate, digest: str, pid: int, index: int | None) -> dict:
    start = {"baseline_sha256": digest, "pair_id": candidate.pair_id, "parent_pid": pid}
    if index is not None:
        start.update(index=index, mode=candidate.order[index], run_id=candidate.run_ids[index])
    return start


def check_pair_authorization(
    root: Path,
    authorization: Path,
    *,
    child: bool = False,
    index: int | None = None,
    active: bool = False,
) -> PairCandidate:
    """Bind pair approval, fresh common identity, member scope and parent lease."""
    root = root.resolve()
    candidate = PairCandidate.model_validate_json((root / "pair-candidate.json").read_text())
    approval = PairAuthorization.model_validate_json(authorization.read_text())
    digest = runner._sha(root / "pair-candidate.json")
    if (
        approval.baseline_sha256 != digest
        or approval.pair_id != candidate.pair_id
        or approval.output_root != root
        or candidate.output_root != root
        or approval.run_ids != candidate.run_ids
        or approval.order != candidate.order
    ):
        raise ValueError("AUTHORIZATION_SCOPE_MISMATCH")
    if index is not None and (type(index) is not int or index not in (0, 1)):
        raise ValueError("PAIR_MEMBER_INVALID")
    if child or active:
        pid = os.getppid() if child else os.getpid()
        lease = runner._json_object((runner._OWNER_ROOT / "active.json").read_text())
        if (
            lease.get("state") != "RUNNING"
            or lease.get("pid") != pid
            or lease.get("campaign_root") != str(root)
            or lease.get("campaign_id") != candidate.pair_id
            or runner._json_object((root / "PAIR-START.json").read_text())
            != _pair_start(candidate, digest, pid, None)
        ):
            raise ValueError("PARENT_LEASE_MISMATCH")
        if child:
            if index is None:
                raise ValueError("PAIR_MEMBER_REQUIRED")
            member = root / candidate.run_paths[index]
            if (
                runner._json_object((member / "START.json").read_text())
                != _pair_start(candidate, digest, pid, index)
                or (member / "CHILD-START.json").exists()
            ):
                raise ValueError("MEMBER_STARTED_OR_SCOPE_MISMATCH")
            if index == 1:
                previous = runner._json_object((root / "runs/01-off/terminal.json").read_text())
                if previous.get("status") != "COMPLETE" or any(
                    previous.get(key) != value
                    for key, value in _pair_start(candidate, digest, pid, 0).items()
                ):
                    raise ValueError("PREVIOUS_MEMBER_INCOMPLETE")
    elif (root / "PAIR-START.json").exists() or any((root / p).exists() for p in PAIR_PATHS):
        raise ValueError("ALREADY_STARTED")
    current = Identity.model_validate(capture_identity()).model_dump(
        mode="json", exclude={"logging"}
    )
    changed = compare_identity(candidate.common_identity, current)
    if changed:
        raise ValueError("IDENTITY_DRIFT:" + ",".join(changed))
    return candidate


def ac_online(context: dict[str, Any]) -> bool:
    """Require observed mains power; absent/unreadable state cannot pass admission."""
    power = context.get("power")
    return isinstance(power, dict) and any(
        isinstance(device, dict)
        and device.get("type") in ("Mains", "USB", "USB_C", "USB_PD")
        and device.get("online") == "1"
        for device in power.values()
    )


def _pair_admission(root: Path) -> dict[str, JsonValue]:
    headroom = runner.check_headroom(1024**3)
    context = runner._operational_context()
    admission = {
        "headroom": headroom.model_dump(mode="json"),
        "context": context,
        "disk_free_bytes": shutil.disk_usage(root).free,
    }
    return admission


def _check_pair_admission(admission: dict[str, Any]) -> None:
    if admission["headroom"]["status"] != "PASS" or admission["disk_free_bytes"] < 256 * 1024**2:
        raise ValueError("ADMISSION_BLOCKED")
    if not ac_online(admission["context"]):
        raise ValueError("POWER_AC_UNKNOWN_OR_OFFLINE")


def _pair_child(root: Path, authorization: Path, index: int) -> dict[str, JsonValue]:
    from ortools.sat.python import cp_model

    candidate = check_pair_authorization(root, authorization, child=True, index=index)
    member = root / candidate.run_paths[index]
    with patch.object(cp_model, "CpSolver", side_effect=AssertionError("SEARCH_FORBIDDEN")):
        prepared, built, compiled = _build_target()
    check_pair_authorization(root, authorization, child=True, index=index)
    current = candidate.common_identity
    admission = _pair_admission(root)
    runner._write_json(
        member / "attempt/child-identity.json",
        {
            "common_identity": current,
            "mode": candidate.order[index],
            "logging": candidate.profiles[candidate.order[index]],
            "admission": admission,
        },
        exclusive=True,
    )
    _check_pair_admission(admission)
    runner._write_json(member / "CHILD-START.json", {"pid": os.getpid()}, exclusive=True)
    result = trace_feasibility(
        prepared,
        built,
        compiled,
        SolveOptions(),
        member / "attempt/trace.log",
        logging_mode=candidate.order[index],
    )
    runner._write_json(member / "attempt/trace-result.json", result, exclusive=True)
    for name, key in (
        ("parameters.txt", "parameters"),
        ("response.txt", "response"),
        ("response-stats.txt", "response_stats"),
    ):
        if result[key] is not None:
            with (member / "attempt" / name).open("x", encoding="utf-8") as out:
                out.write(result[key])
    runner._write_json(
        member / "attempt/independent-checks.json",
        {key: result[key] for key in ("correctness", "valid_schedule", "score", "quality_proved")},
        exclusive=True,
    )
    if result["valid_schedule"]:
        runner._write_json(
            member / "attempt/assignments.json",
            {"assignments": result["assignments"]},
            exclusive=True,
        )
    return {"status": "CHILD_TERMINAL"}


def _run_pair_parent(root: Path, authorization: Path) -> dict[str, JsonValue]:
    """Sequential pair dispatch, callable only with separately approved pair identity."""
    root = root.resolve()
    candidate = check_pair_authorization(root, authorization)
    digest = runner._sha(root / "pair-candidate.json")
    result = {
        "schema_version": "1.0",
        "status": "BLOCKED",
        "reason": None,
        "comparability": "LIMITED",
        "inter_run_gap_seconds": None,
        "limitations": ["ORDER_WORKLOAD_THERMAL_UNCONTROLLED_N1", "POWER_SNAPSHOTS_ONLY"],
        "members": [
            _pair_start(candidate, digest, os.getpid(), i) | {"status": "NOT_STARTED"}
            for i in range(2)
        ],
    }
    with runner._campaign_owner(runner._OWNER_ROOT, root, candidate.pair_id) as lease:
        check_pair_authorization(root, authorization)
        frozen = root / "pair-authorization.json"
        if authorization.resolve() != frozen:
            with frozen.open("xb") as out:
                out.write(authorization.read_bytes())
        check_pair_authorization(root, frozen)
        digest = runner._sha(root / "pair-candidate.json")
        runner._write_json(
            root / "PAIR-START.json",
            _pair_start(candidate, digest, os.getpid(), None),
            exclusive=True,
        )
        previous_exit = None
        for index in range(2):
            row = result["members"][index]
            try:
                check_pair_authorization(root, frozen, active=True, index=index)
                admission = _pair_admission(root)
                row["admission"] = admission
                row["pre_context"] = admission["context"]
                _check_pair_admission(admission)
                member = root / candidate.run_paths[index]
                member.mkdir(parents=True)
                runner._write_json(
                    member / "identity-before-run.json",
                    {
                        "common_identity": candidate.common_identity,
                        "logging": candidate.profiles[candidate.order[index]],
                        "admission": admission,
                    },
                    exclusive=True,
                )
                runner._write_json(
                    member / "START.json",
                    _pair_start(candidate, digest, os.getpid(), index),
                    exclusive=True,
                )
                launch = time.monotonic()
                if previous_exit is not None:
                    result["inter_run_gap_seconds"] = launch - previous_exit
                row["status"] = "STARTED"
                # Any exception without an execution receipt leaves owner state for review.
                lease["state"] = "NEEDS_REVIEW"
                execution = runner.supervise_linux(
                    (
                        str(Path(sys.executable).absolute()),
                        "-I",
                        str(Path(__file__).resolve()),
                        "_pair-child",
                        "--root",
                        str(root),
                        "--authorization",
                        str(frozen),
                        "--member-index",
                        str(index),
                    ),
                    member / "attempt",
                    LIMITS,
                )
                previous_exit = time.monotonic()
                reaped = (
                    execution.raw_wait_status is not None
                    and execution.measurement_reason != "REAP_UNCONFIRMED"
                )
                runner._write_json(member / "execution.json", execution, exclusive=True)
                row["execution"] = execution.model_dump(mode="json")
                row["post_context"] = runner._operational_context()
                row["power_changed_or_unknown"] = (
                    not ac_online(row["post_context"])
                    or row["pre_context"]["power"] != row["post_context"]["power"]
                )
                stage_path = member / "attempt/trace-result.json"
                stage = runner._json_object(stage_path.read_text()) if stage_path.exists() else {}
                row.update(stage)
                row.update(_pair_start(candidate, digest, os.getpid(), index))
                good = (
                    reaped
                    and execution.measurement_status == "OK"
                    and execution.stop_reason is None
                    and execution.signal is None
                    and execution.exit_code == 0
                    and stage.get("stage_complete") is True
                    and stage.get("response_reason") is None
                    and stage.get("response") is not None
                    and stage.get("parameters") is not None
                    and stage.get("error") is None
                    and stage.get("constructor_calls") == stage.get("solve_calls") == 1
                    and stage.get("trace_capture_status")
                    == ("DISABLED" if index == 0 else "COMPLETE")
                    and stage.get("raw_solver_status") in ("UNKNOWN", "FEASIBLE", "OPTIMAL")
                    and (
                        stage.get("raw_solver_status") == "UNKNOWN"
                        or (
                            stage.get("correctness") == "PASS"
                            and stage.get("valid_schedule") is True
                        )
                    )
                    and stage.get("correctness") != "FAIL"
                )
                row["status"] = "COMPLETE" if good else "FAILED"
                runner._write_json(member / "terminal.json", row, exclusive=True)
                if reaped:
                    lease["state"] = "RUNNING"
                if not good:
                    result["reason"] = "MEMBER_FAILURE_NO_RETRY"
                    break
            except (OSError, ValueError, TypeError, KeyError) as exc:
                result["reason"] = str(exc)
                break
        completed = sum(row["status"] == "COMPLETE" for row in result["members"])
        started = any(row["status"] != "NOT_STARTED" for row in result["members"])
        result["status"] = "TERMINAL" if completed == 2 else "PARTIAL" if started else "BLOCKED"
        runner._write_json(root / "pair-result.json", result, exclusive=True)
        inventory = {
            str(p.relative_to(root)): runner._sha(p) for p in root.rglob("*") if p.is_file()
        }
        runner._write_json(
            root / "manifest.json",
            {
                "schema_version": "1.0",
                "files": inventory,
                "baseline_sha256": digest,
                "pair_id": candidate.pair_id,
                "parent_pid": os.getpid(),
                "missing_logs": {
                    "runs/01-off/attempt/trace.log": (
                        "NOT_STARTED"
                        if result["members"][0]["status"] == "NOT_STARTED"
                        else "LOGGING_DISABLED"
                    )
                },
            },
            exclusive=True,
        )
    return result


def main(argv: list[str] | None = None) -> int:
    """Explicit prepare/run modes; prepare cannot authorize or execute search."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase", choices=("prepare", "run", "_child", "prepare-pair", "run-pair", "_pair-child")
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--pair-id")
    parser.add_argument("--member-index", type=int, choices=(0, 1))
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args(argv)
    if args.phase == "prepare-pair":
        if args.pair_id is None or any(
            v is not None for v in (args.run_id, args.authorization, args.member_index)
        ):
            parser.error("prepare-pair requires only --pair-id and --root")
    elif args.phase in ("run-pair", "_pair-child"):
        if args.authorization is None or args.run_id is not None or args.pair_id is not None:
            parser.error("pair execution requires --authorization and forbids IDs")
        if (args.phase == "_pair-child") != (args.member_index is not None):
            parser.error("--member-index required only for _pair-child")
    elif args.pair_id is not None or args.member_index is not None:
        parser.error("single trace forbids pair arguments")
    elif args.phase == "prepare" and (args.run_id is None or args.authorization is not None):
        parser.error("prepare requires --run-id and forbids --authorization")
    elif args.phase != "prepare" and (args.authorization is None or args.run_id is not None):
        parser.error("run/_child require --authorization and forbid --run-id")
    try:
        if args.phase == "prepare-pair":
            result = prepare_pair(args.root, args.pair_id)
        elif args.phase == "run-pair":
            result = _run_pair_parent(args.root.resolve(), args.authorization)
        elif args.phase == "_pair-child":
            result = _pair_child(args.root.resolve(), args.authorization, args.member_index)
        elif args.phase == "prepare":
            result = prepare_trace(args.root, args.run_id)
        elif args.phase == "run":
            result = _run_parent(args.root.resolve(), args.authorization)
        else:
            result = _child(args.root.resolve(), args.authorization)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return (
            2
            if (
                result["status"] in ("BLOCKED", "PARTIAL", "TRACE_INCOMPLETE", "CORRECTNESS_FAIL")
                or result.get("harness_status", "COMPLETE") != "COMPLETE"
            )
            else 0
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
