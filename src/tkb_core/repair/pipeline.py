"""Repair pipeline (Phase 3A, spec §2.3-§2.5): stay close to a previous schedule.

``solve()`` is not modified. Repair reuses preprocessing, the hard model, the soft compiler
and the lexicographic quality runner, and adds one change-count stage before
(``BEFORE_QUALITY``) or after (``AFTER_QUALITY``) the P1-P3 tiers. Every returned
schedule passes the independent validator, the score evaluator and the repair evaluator.
"""

from dataclasses import dataclass, field
from importlib.metadata import version
from time import perf_counter
from typing import Any

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult, SolverRunMetadata, SolverRunMetadataV12
from tkb_core.contracts.repair import (
    ChangeStage,
    PreviousSchedule,
    RepairChange,
    RepairReport,
    RepairRequest,
    RepairResult,
)
from tkb_core.contracts.score import QualityReport, ScoreReport, StageRun
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ConstraintConfigV11, Diagnostic, ScheduleAssignment
from tkb_core.preprocessing.feasibility import PreparedProblem, prepare
from tkb_core.repair.matching import RepairMatching, match
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.repair_evaluator import check_report, evaluate_repair
from tkb_core.validation.score_evaluator import evaluate_score

_OUTPUT = {"0.1": "1.2", "0.2": "1.3", "0.3": "1.4", "0.4": "1.5"}
_SOLVED = (SolveStatus.FEASIBLE, SolveStatus.OPTIMAL)


def add_repair_terms(*args: Any, **kwargs: Any) -> Any:
    """Indirection kept patchable in tests; imports the CP-SAT compiler lazily."""
    from tkb_core.repair.compiler import add_repair_terms as compile_terms

    return compile_terms(*args, **kwargs)


class _Mismatch(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class _Run:
    """Mutable bookkeeping shared by all exits of one repair call."""

    started: float = field(default_factory=perf_counter)
    applied: SolveOptions | None = None
    fingerprint: str | None = None
    policy: str = "0.1"
    quality_input: bool = True
    solver_version: str | None = None
    solver_wall: float = 0.0
    executed: bool = False
    feasibility: StageRun = field(default_factory=StageRun)


@dataclass(frozen=True)
class _ChangeOutcome:
    status: SolveStatus
    assignments: tuple[ScheduleAssignment, ...] = ()
    value: int | None = None
    best_bound: float | None = None
    wall_time: float | None = None


def _extract(prepared: PreparedProblem, built: Any, solver: Any) -> tuple[ScheduleAssignment, ...]:
    reqs = {r.id: r for r in prepared.normalized.problem.teaching_requirements}
    chosen = []
    for o in prepared.normalized.occurrences:
        req = reqs[o.requirement_id]
        for p, v in zip(prepared.domains[o.id], built.variables[o.id], strict=True):
            if solver.boolean_value(v):
                chosen.append(
                    ScheduleAssignment(
                        occurrence_id=o.id,
                        slot_id=p.start_slot_id,
                        room_id=p.room_id,
                        class_ids=req.class_ids,
                        teacher_ids=req.teacher_ids,
                    )
                )
    return tuple(chosen)


def _minimize_changes(
    prepared: PreparedProblem,
    built: Any,
    model: Any,
    expression: Any,
    options: SolveOptions,
    budget: float,
    run: _Run,
) -> _ChangeOutcome:
    """One native solve minimizing the change count on ``model`` (same variable indices)."""
    from ortools.sat.python import cp_model

    model.minimize(expression)
    if model.validate():
        return _ChangeOutcome(SolveStatus.MODEL_INVALID)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = budget
    solver.parameters.num_search_workers = options.num_workers
    solver.parameters.random_seed = options.seed
    solver.parameters.relative_gap_limit = 0.0
    solver.parameters.absolute_gap_limit = 0.0
    started = perf_counter()
    code = int(solver.solve(model))
    wall = perf_counter() - started
    run.executed = True
    run.solver_wall += wall
    status = {
        0: SolveStatus.UNKNOWN,
        1: SolveStatus.MODEL_INVALID,
        2: SolveStatus.FEASIBLE,
        3: SolveStatus.INFEASIBLE,
        4: SolveStatus.OPTIMAL,
    }[code]
    if status not in _SOLVED:
        return _ChangeOutcome(status, wall_time=wall)
    return _ChangeOutcome(
        status,
        _extract(prepared, built, solver),
        int(solver.value(expression)),
        float(solver.best_objective_bound),
        wall,
    )


def _verify(
    problem: ScheduleInput,
    previous: PreviousSchedule,
    request: RepairRequest,
    matching: RepairMatching,
    assignments: tuple[ScheduleAssignment, ...],
    expected_changes: int | None,
) -> tuple[Any, ScoreReport, Any]:
    """Independent hard, score and repair checks; any disagreement blocks the schedule."""
    validation = validate_schedule(problem, assignments)
    if not validation.valid:
        raise _Mismatch("INTERNAL_VALIDATION_FAILED")
    score = evaluate_score(problem, assignments)
    if score.status != "OK":
        raise _Mismatch("INTERNAL_SCORE_ERROR")
    evaluation = evaluate_repair(problem, previous, request, assignments)
    changed = {c[0] for c in evaluation.changes}
    if (
        evaluation.status != "OK"
        or evaluation.frozen_violations
        or not evaluation.max_changes_ok
        or not set(matching.forced) <= changed
        or evaluation.frozen != len(matching.frozen)
        or (expected_changes is not None and evaluation.changed != expected_changes)
    ):
        raise _Mismatch("REPAIR_REPORT_MISMATCH")
    return validation, score, evaluation


def _report(
    request: RepairRequest, matching: RepairMatching, evaluation: Any, stage: ChangeStage
) -> RepairReport:
    report = RepairReport(
        change_order=request.change_order,
        max_changes=request.max_changes,
        change_scope=request.change_scope,
        matched=evaluation.matched,
        new=evaluation.new,
        dropped=evaluation.dropped,
        changed=evaluation.changed,
        slot_changes=evaluation.slot_changes,
        room_only_changes=evaluation.room_only_changes,
        unchanged=evaluation.unchanged,
        frozen=evaluation.frozen,
        forced=len(matching.forced),
        changes=tuple(
            RepairChange(
                occurrence_id=o,
                previous_slot_id=ps,
                previous_room_id=pr,
                slot_id=s,
                room_id=r,
                forced=matching.forced.get(o),
            )
            for o, ps, pr, s, r in evaluation.changes
        ),
        new_occurrence_ids=evaluation.new_occurrence_ids,
        dropped_occurrence_ids=evaluation.dropped_occurrence_ids,
        change_stage=stage,
        min_changes_proved=stage.proved_optimal,
    )
    if check_report(evaluation, report):
        raise _Mismatch("REPAIR_REPORT_MISMATCH")
    return report


def _stage(outcome: _ChangeOutcome) -> ChangeStage:
    return ChangeStage(
        raw_status=outcome.status,
        incumbent_value=outcome.value,
        best_bound=outcome.best_bound,
        wall_time=outcome.wall_time,
        proved_optimal=outcome.status == SolveStatus.OPTIMAL,
    )


def repair(
    problem: ScheduleInput,
    previous: PreviousSchedule,
    request: RepairRequest,
    options: SolveOptions | None = None,
) -> RepairResult:
    """Repair a previous schedule for a changed input; never trust a solver value alone."""
    run = _Run()
    previous_fp: str | None = None
    source_fp: str | None = None
    count = 0
    checked_request: RepairRequest | None = None
    active: tuple[int, ...] = ()

    def finish(
        status: SolveStatus | str,
        assignments: tuple[ScheduleAssignment, ...] = (),
        diagnostics: tuple[Diagnostic, ...] = (),
        validation: Any = None,
        quality: QualityReport | None = None,
        report: RepairReport | None = None,
    ) -> RepairResult:
        valid = bool(validation is not None and validation.valid)
        if run.quality_input:
            if quality is None:
                quality = QualityReport(status="NOT_EVALUATED")
            quality = QualityReport.model_validate(
                {**quality.model_dump(), "policy_version": run.policy}
            )
            metadata: SolverRunMetadata = SolverRunMetadataV12(
                feasibility_run=run.feasibility,
                solver_executed=run.executed,
                solver_version=run.solver_version,
                wall_time=perf_counter() - run.started,
                solver_wall_time=run.solver_wall if run.executed else None,
                seed=run.applied.seed if run.applied else None,
                num_workers=run.applied.num_workers if run.applied else None,
                time_limit_seconds=run.applied.time_limit_seconds if run.applied else None,
            )
        else:
            metadata = SolverRunMetadata(
                solver_executed=False, wall_time=perf_counter() - run.started
            )
        result = ScheduleResult(
            schema_version=_OUTPUT[run.policy] if run.quality_input else "1.1",
            status=SolveStatus(status),
            input_fingerprint=run.fingerprint,
            valid_schedule=valid,
            assignments=assignments if valid else (),
            diagnostics=diagnostics,
            validation=validation,
            metadata=metadata,
            **({"quality": quality} if run.quality_input else {}),
        )
        return RepairResult(
            result=result,
            previous_fingerprint=previous_fp,
            previous_source_input_fingerprint=source_fp,
            previous_assignment_count=count,
            request=checked_request,
            repair=report if valid else None,
        )

    def fail(status: str, code: str, message: str) -> RepairResult:
        return finish(status, diagnostics=(Diagnostic(code=code, message=message),))

    def scored(
        assignments: tuple[ScheduleAssignment, ...], score: ScoreReport, tiers: tuple[int, ...]
    ) -> QualityReport:
        if not tiers:
            return QualityReport(status="NOT_REQUESTED", score=score)
        return QualityReport(
            status="SCORED_FEASIBLE",
            score=score,
            tier_runs=tuple(StageRun(priority=p) for p in tiers),
        )

    # -- contracts ---------------------------------------------------------------------------
    try:
        run.applied = (
            SolveOptions()
            if options is None
            else SolveOptions.model_validate(options.model_dump(warnings="error"))
        )
        problem = ScheduleInput.model_validate(problem.model_dump(warnings="error"))
        run.fingerprint = problem.fingerprint()
    except (ValueError, TypeError, AttributeError):
        run.quality_input = False
        return fail("INPUT_INVALID", "CONTRACT_INVALID", "Input/options failed revalidation")
    run.quality_input = problem.schema_version == "1.1"
    if isinstance(problem.constraint_config, ConstraintConfigV11):
        run.policy = problem.constraint_config.policy_version
        active = tuple(sorted({r.priority for r in problem.constraint_config.soft if r.enabled}))
    try:
        previous = PreviousSchedule.model_validate(previous.model_dump(warnings="error"))
        previous_fp = previous.fingerprint()
        source_fp = previous.source_input_fingerprint
        count = len(previous.assignments)
    except (ValueError, TypeError, AttributeError):
        return fail("INPUT_INVALID", "PREVIOUS_SCHEDULE_INVALID", "Previous schedule is invalid")
    try:
        checked_request = RepairRequest.model_validate(request.model_dump(warnings="error"))
        request = checked_request
    except (ValueError, TypeError, AttributeError):
        return fail("INPUT_INVALID", "REPAIR_REQUEST_INVALID", "Repair request is invalid")
    if not run.quality_input:
        return fail(
            "UNSUPPORTED_FEATURE", "REPAIR_INPUT_VERSION", "Repair requires input schema 1.1"
        )
    # -- preparation -------------------------------------------------------------------------
    try:
        prepared = prepare(problem, run.applied)
        matching = match(prepared, previous, request)
    except CoreError as exc:
        return finish(exc.status, diagnostics=exc.diagnostics)
    if request.max_changes is not None and len(matching.forced) > request.max_changes:
        # Review F2: a counted proof of infeasibility; no search is needed.
        return finish(
            "INFEASIBLE",
            diagnostics=(
                Diagnostic(
                    code="REPAIR_MAX_CHANGES_BELOW_FORCED",
                    message="Changes forced by the new input exceed max_changes",
                    occurrence_ids=tuple(sorted(matching.forced)),
                ),
            ),
        )
    applied = run.applied
    try:
        if not prepared.normalized.occurrences:
            validation, score, evaluation = _verify(problem, previous, request, matching, (), 0)
            return finish(
                "FEASIBLE",
                (),
                (Diagnostic(code="EMPTY_PROBLEM", message="Empty demand; no solver was executed"),),
                validation,
                scored((), score, active),
                _report(request, matching, evaluation, ChangeStage()),
            )
        try:
            from tkb_core.repair.compiler import add_previous_hint
            from tkb_core.solver.model_builder import build_model
            from tkb_core.solver.objectives import _hint, run_quality
        except ImportError:
            return fail(
                "UNSUPPORTED_FEATURE",
                "SOLVER_NOT_INSTALLED",
                "Install the solver extra to execute CP-SAT",
            )
        run.solver_version = version("ortools")
        # No interchangeable ordering: relabeling occurrences would count as changes.
        built = build_model(prepared)
        expression = add_repair_terms(built, matching, request)
        if request.use_previous_as_hint:
            add_previous_hint(built, matching)
        total = applied.time_limit_seconds

        def left() -> float:
            return total - (perf_counter() - run.started)

        def remaining_options(budget: float) -> SolveOptions:
            return SolveOptions.model_validate(
                {**applied.model_dump(), "time_limit_seconds": budget}
            )

        def unsolved(status: SolveStatus) -> RepairResult:
            if status == SolveStatus.MODEL_INVALID:
                return fail("MODEL_INVALID", "MODEL_INVALID", "Model construction failed")
            return fail(status, status.value, "No validated repair was produced")

        if not active or request.change_order == "BEFORE_QUALITY":
            budget = left()
            if budget <= 0:
                return fail("UNKNOWN", "UNKNOWN", "No time budget remained")
            target = built.model if not active else built.model.clone()
            first = _minimize_changes(prepared, built, target, expression, applied, budget, run)
            run.feasibility = StageRun(raw_status=first.status, wall_time=first.wall_time)
            if first.status not in _SOLVED:
                return unsolved(first.status)
            stage = _stage(first)
            validation, score, evaluation = _verify(
                problem, previous, request, matching, first.assignments, first.value
            )
            report = _report(request, matching, evaluation, stage)

            def fallback() -> RepairResult:
                # The verified change-stage schedule; quality tiers stay NOT_RUN.
                return finish(
                    first.status if not active else SolveStatus.FEASIBLE,
                    first.assignments,
                    validation=validation,
                    quality=scored(first.assignments, score, active),
                    report=report,
                )

            if not active or first.status != SolveStatus.OPTIMAL or left() <= 0:
                return fallback()
            from tkb_core.constraints.soft import compile_soft

            assert first.value is not None
            built.model.add(expression == first.value)
            _hint(prepared, built, first.assignments)
            hard_model = built.model.clone()
            compiled = compile_soft(prepared, built)
            outcome = run_quality(prepared, built, compiled, remaining_options(left()), hard_model)
            run.executed = True
            run.solver_wall += outcome.solver_wall_time or 0.0
            if outcome.status == SolveStatus.MODEL_INVALID or (
                outcome.status == SolveStatus.INFEASIBLE
            ):
                code = outcome.diagnostics[0].code if outcome.diagnostics else "MODEL_INVALID"
                return fail("MODEL_INVALID", code, "Quality stages contradict the change stage")
            if outcome.status not in _SOLVED:
                return fallback()
            validation, score, evaluation = _verify(
                problem, previous, request, matching, outcome.assignments, first.value
            )
            return finish(
                outcome.status,
                outcome.assignments,
                validation=validation,
                quality=outcome.quality,
                report=_report(request, matching, evaluation, stage),
            )
        # AFTER_QUALITY with active preferences: P1-P3 first, then fewest changes.
        from tkb_core.constraints.soft import compile_soft

        hard_model = built.model.clone()
        compiled = compile_soft(prepared, built)
        # Review F3: like BEFORE_QUALITY, preparation time counts against the time limit.
        budget = left()
        if budget <= 0:
            return fail("UNKNOWN", "UNKNOWN", "No time budget remained")
        outcome = run_quality(prepared, built, compiled, remaining_options(budget), hard_model)
        run.executed = outcome.solver_executed
        run.solver_wall += outcome.solver_wall_time or 0.0
        run.feasibility = outcome.feasibility_run
        if outcome.status not in _SOLVED:
            return finish(outcome.status, diagnostics=outcome.diagnostics, quality=outcome.quality)
        assignments = outcome.assignments
        validation, score, evaluation = _verify(
            problem, previous, request, matching, assignments, None
        )
        stage = ChangeStage()
        budget = left()
        if outcome.status == SolveStatus.OPTIMAL and budget > 0:
            _hint(prepared, built, assignments)
            change = _minimize_changes(
                prepared, built, built.model, expression, applied, budget, run
            )
            if change.status in (SolveStatus.INFEASIBLE, SolveStatus.MODEL_INVALID):
                return fail(
                    "MODEL_INVALID",
                    "INTERNAL_STAGE_INCONSISTENCY",
                    "Change stage contradicts proved quality tiers",
                )
            if change.status in _SOLVED:
                candidate = _verify(
                    problem, previous, request, matching, change.assignments, change.value
                )
                if candidate[1].tiers != score.tiers:
                    raise _Mismatch("INTERNAL_SCORE_MISMATCH")
                if candidate[2].changed <= evaluation.changed:
                    stage = _stage(change)
                    assignments = change.assignments
                    validation, score, evaluation = candidate
                elif change.status == SolveStatus.OPTIMAL:
                    # A proved minimum cannot exceed a feasible schedule's change count.
                    raise _Mismatch("REPAIR_REPORT_MISMATCH")
                else:
                    # Keep the better quality-stage schedule; claim no change incumbent.
                    stage = ChangeStage(raw_status=change.status, wall_time=change.wall_time)
            else:
                stage = ChangeStage(raw_status=change.status, wall_time=change.wall_time)
        quality = QualityReport.model_validate({**outcome.quality.model_dump(), "score": score})
        return finish(
            outcome.status,
            assignments,
            validation=validation,
            quality=quality,
            report=_report(request, matching, evaluation, stage),
        )
    except _Mismatch as exc:
        return fail("MODEL_INVALID", exc.code, "Independent repair verification failed")
    except CoreError as exc:
        return finish(exc.status, diagnostics=exc.diagnostics)
    except (ValueError, TypeError, RuntimeError, OverflowError):
        return fail("MODEL_INVALID", "SOLVER_ERROR", "Model construction or solver failed")
