"""Hard-feasibility solve pipeline; export is gated by independent validation."""

from importlib.metadata import version
from time import perf_counter

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import (
    ScheduleResult,
    SolverRunMetadata,
    SolverRunMetadataV12,
    ValidationReport,
)
from tkb_core.contracts.score import QualityReport, StageRun
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ConstraintConfigV11, Diagnostic, ScheduleAssignment
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score


def map_status(status: int) -> SolveStatus:
    """Map CP-SAT wire enum values explicitly; never confuse UNKNOWN with infeasible."""
    return {
        0: SolveStatus.UNKNOWN,
        1: SolveStatus.MODEL_INVALID,
        2: SolveStatus.FEASIBLE,
        3: SolveStatus.INFEASIBLE,
        4: SolveStatus.OPTIMAL,
    }.get(status, SolveStatus.MODEL_INVALID)


def solve(problem: ScheduleInput, options: SolveOptions | None = None) -> ScheduleResult:
    """Solve supported hard constraints; no objective, network, storage or repair."""
    started = perf_counter()
    fingerprint: str | None = None
    applied: SolveOptions | None = None
    solver_version: str | None = None
    solver_wall: float | None = None
    executed = False
    quality_input = isinstance(problem, ScheduleInput) and problem.schema_version == "1.1"
    quality = QualityReport(status="NOT_EVALUATED")
    feasibility_run = StageRun()
    active_priorities: tuple[int, ...] = ()

    def finish(
        status: SolveStatus | str,
        assignments: tuple[ScheduleAssignment, ...] = (),
        diagnostics: tuple[Diagnostic, ...] = (),
        validation: ValidationReport | None = None,
    ) -> ScheduleResult:
        selected_quality = quality
        if quality_input and validation is not None and validation.valid and not active_priorities:
            checked_score = evaluate_score(problem, assignments)
            if checked_score.status != "OK":
                return finish(
                    "MODEL_INVALID",
                    diagnostics=(
                        Diagnostic(
                            code="INTERNAL_SCORE_ERROR", message="Score verification failed"
                        ),
                    ),
                )
            selected_quality = QualityReport(status="NOT_REQUESTED", score=checked_score)
        metadata_type = SolverRunMetadataV12 if quality_input else SolverRunMetadata
        extra = {"feasibility_run": feasibility_run} if quality_input else {}
        result_extra = {"quality": selected_quality} if quality_input else {}
        return ScheduleResult(
            schema_version="1.2" if quality_input else "1.1",
            status=SolveStatus(status),
            input_fingerprint=fingerprint,
            valid_schedule=bool(validation and validation.valid),
            assignments=assignments,
            diagnostics=diagnostics,
            validation=validation,
            metadata=metadata_type(
                **extra,
                solver_executed=executed,
                solver_version=solver_version,
                wall_time=perf_counter() - started,
                solver_wall_time=solver_wall,
                seed=applied.seed if applied else None,
                num_workers=applied.num_workers if applied else None,
                time_limit_seconds=applied.time_limit_seconds if applied else None,
            ),
            **result_extra,
        )

    try:
        applied = (
            SolveOptions()
            if options is None
            else SolveOptions.model_validate(options.model_dump(warnings="error"))
        )
        problem = ScheduleInput.model_validate(problem.model_dump(warnings="error"))
        fingerprint = problem.fingerprint()
        quality_input = problem.schema_version == "1.1"
        if isinstance(problem.constraint_config, ConstraintConfigV11):
            active_priorities = tuple(
                sorted({r.priority for r in problem.constraint_config.soft if r.enabled})
            )
    except (ValueError, TypeError, AttributeError):
        return finish(
            "INPUT_INVALID",
            diagnostics=(
                Diagnostic(code="CONTRACT_INVALID", message="Input/options failed revalidation"),
            ),
        )
    try:
        prepared = prepare(problem, applied)
    except CoreError as exc:
        return finish(exc.status, diagnostics=exc.diagnostics)
    if not prepared.normalized.occurrences:
        report = validate_schedule(problem, ())
        if not report.valid:
            return finish(
                "MODEL_INVALID",
                validation=report,
                diagnostics=(
                    Diagnostic(
                        code="INTERNAL_VALIDATION_FAILED",
                        message="Independent validation rejected the empty result",
                    ),
                ),
            )
        if quality_input and active_priorities:
            quality = QualityReport(
                status="SCORED_FEASIBLE",
                score=evaluate_score(problem, ()),
                tier_runs=tuple(StageRun(priority=p) for p in active_priorities),
            )
        return finish(
            "FEASIBLE",
            validation=report,
            diagnostics=(
                Diagnostic(
                    code="EMPTY_PROBLEM", message="Empty synthetic demand; no solver was executed"
                ),
            ),
        )
    try:
        from ortools.sat.python import cp_model

        from tkb_core.solver.model_builder import build_model
    except ImportError:
        return finish(
            "UNSUPPORTED_FEATURE",
            diagnostics=(
                Diagnostic(
                    code="SOLVER_NOT_INSTALLED",
                    message="Install the solver extra to execute CP-SAT",
                ),
            ),
        )
    try:
        solver_version = version("ortools")
        built = build_model(prepared)
        if quality_input and active_priorities:
            from tkb_core.constraints.soft import compile_soft
            from tkb_core.solver.objectives import run_quality

            compiled = compile_soft(prepared, built)
            outcome = run_quality(prepared, built, compiled, applied)
            executed = outcome.solver_executed
            solver_wall = outcome.solver_wall_time
            quality = outcome.quality
            feasibility_run = outcome.feasibility_run
            return finish(
                outcome.status, outcome.assignments, outcome.diagnostics, outcome.validation
            )
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = applied.time_limit_seconds
        solver.parameters.num_search_workers = applied.num_workers
        solver.parameters.random_seed = applied.seed
        executed = True
        raw_status = solver.solve(built.model)
        solver_wall = solver.wall_time
        status = map_status(int(raw_status))
        feasibility_run = StageRun(raw_status=status, wall_time=solver_wall)
        if status not in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
            return finish(
                status,
                diagnostics=(
                    Diagnostic(
                        code=status.value,
                        message="No validated schedule was produced; solver status is recorded",
                    ),
                ),
            )
        requirements = {r.id: r for r in problem.teaching_requirements}
        result: list[ScheduleAssignment] = []
        for occurrence in prepared.normalized.occurrences:
            req = requirements[occurrence.requirement_id]
            for placement, variable in zip(
                prepared.domains[occurrence.id], built.variables[occurrence.id], strict=True
            ):
                if solver.boolean_value(variable):
                    result.append(
                        ScheduleAssignment(
                            occurrence_id=occurrence.id,
                            slot_id=placement.start_slot_id,
                            room_id=placement.room_id,
                            class_ids=req.class_ids,
                            teacher_ids=req.teacher_ids,
                        )
                    )
        assignments = tuple(result)
        report = validate_schedule(problem, assignments)
        if not report.valid:
            return finish(
                "MODEL_INVALID",
                validation=report,
                diagnostics=(
                    Diagnostic(
                        code="INTERNAL_VALIDATION_FAILED",
                        message="Independent validation rejected the solver result",
                    ),
                ),
            )
        return finish(status, assignments=assignments, validation=report)
    except CoreError as exc:
        return finish(exc.status, diagnostics=exc.diagnostics)
    except (ValueError, TypeError, RuntimeError, OverflowError):
        return finish(
            "MODEL_INVALID",
            diagnostics=(
                Diagnostic(
                    code="SOLVER_ERROR", message="Model construction or solver execution failed"
                ),
            ),
        )
