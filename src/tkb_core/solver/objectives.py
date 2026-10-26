"""Budgeted lexicographic solves; each cached incumbent is independently verified."""

from dataclasses import dataclass, field
from time import perf_counter

from ortools.sat.python import cp_model

from tkb_core.constraints.soft import CompiledSoft
from tkb_core.contracts.output import ValidationReport
from tkb_core.contracts.score import QualityReport, ScoreReport, StageRun
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import Diagnostic, ScheduleAssignment
from tkb_core.preprocessing.feasibility import PreparedProblem
from tkb_core.solver.model_builder import BuiltModel
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score


@dataclass(frozen=True)
class StageOutcome:
    status: SolveStatus
    assignments: tuple[ScheduleAssignment, ...] = ()
    rule_values: dict[str, tuple[int, int]] = field(default_factory=dict)
    tier_values: dict[int, int] = field(default_factory=dict)
    wall_time: float | None = None
    best_bound: float | None = None


@dataclass(frozen=True)
class QualityOutcome:
    status: SolveStatus
    assignments: tuple[ScheduleAssignment, ...]
    validation: ValidationReport | None
    score: ScoreReport | None
    quality: QualityReport
    feasibility_run: StageRun
    solver_wall_time: float | None
    solver_executed: bool
    diagnostics: tuple[Diagnostic, ...] = ()


def _run_stage(
    prepared: PreparedProblem,
    built: BuiltModel,
    compiled: CompiledSoft,
    options: SolveOptions,
    priority: int | None,
    budget: float,
) -> StageOutcome:
    if priority is None:
        built.model.clear_objective()
    else:
        built.model.minimize(compiled.tiers[priority])
    if built.model.validate():
        return StageOutcome(SolveStatus.MODEL_INVALID)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = budget
    solver.parameters.num_search_workers = options.num_workers
    solver.parameters.random_seed = options.seed
    solver.parameters.relative_gap_limit = 0.0
    solver.parameters.absolute_gap_limit = 0.0
    status_code = int(solver.solve(built.model))
    status = {
        0: SolveStatus.UNKNOWN,
        1: SolveStatus.MODEL_INVALID,
        2: SolveStatus.FEASIBLE,
        3: SolveStatus.INFEASIBLE,
        4: SolveStatus.OPTIMAL,
    }[status_code]
    if status not in (SolveStatus.FEASIBLE, SolveStatus.OPTIMAL):
        return StageOutcome(status, wall_time=solver.wall_time)
    reqs = {r.id: r for r in prepared.normalized.problem.teaching_requirements}
    assignments = []
    for o in prepared.normalized.occurrences:
        req = reqs[o.requirement_id]
        for p, v in zip(prepared.domains[o.id], built.variables[o.id], strict=True):
            if solver.boolean_value(v):
                assignments.append(
                    ScheduleAssignment(
                        occurrence_id=o.id,
                        slot_id=p.start_slot_id,
                        room_id=p.room_id,
                        class_ids=req.class_ids,
                        teacher_ids=req.teacher_ids,
                    )
                )
    return StageOutcome(
        status,
        tuple(assignments),
        {
            r.rule_id: (
                int(solver.value(r.raw_expression)),
                int(solver.value(r.weighted_expression)),
            )
            for r in compiled.rules
        },
        {p: int(solver.value(e)) for p, e in compiled.tiers.items()},
        solver.wall_time,
        float(solver.best_objective_bound) if priority is not None else None,
    )


def run_quality(
    prepared: PreparedProblem, built: BuiltModel, compiled: CompiledSoft, options: SolveOptions
) -> QualityOutcome:
    """Stop at the first unproved active tier; never discard a verified prior schedule."""
    problem = prepared.normalized.problem
    assignments: tuple[ScheduleAssignment, ...] = ()
    validation = None
    score = None
    tiers = {p: StageRun(priority=p) for p in compiled.tiers}
    prefix: list[int] = []
    feasibility = StageRun()
    elapsed = 0.0
    solver_wall = 0.0
    executed = False

    def finish(status: SolveStatus, code: str | None = None) -> QualityOutcome:
        success = status in (SolveStatus.FEASIBLE, SolveStatus.OPTIMAL) and score is not None
        qstatus = "NOT_EVALUATED"
        if success:
            qstatus = (
                "LEXICOGRAPHIC_OPTIMAL" if status == SolveStatus.OPTIMAL else "SCORED_FEASIBLE"
            )
        quality = QualityReport(
            status=qstatus,
            score=score if success else None,
            optimal_prefix=tuple(prefix),
            tier_runs=tuple(tiers.values()),
        )
        return QualityOutcome(
            status,
            assignments if success else (),
            validation if success else None,
            score if success else None,
            quality,
            feasibility,
            solver_wall if executed else None,
            executed,
            (Diagnostic(code=code, message="Quality solving could not be completed"),)
            if code
            else (),
        )

    for priority in (None, *compiled.tiers):
        remaining = options.time_limit_seconds - elapsed
        if remaining <= 0:
            return finish(SolveStatus.FEASIBLE if score is not None else SolveStatus.UNKNOWN)
        start = perf_counter()
        outcome = _run_stage(prepared, built, compiled, options, priority, remaining)
        elapsed += max(0.0, perf_counter() - start)
        executed = True
        if outcome.wall_time is not None:
            solver_wall += outcome.wall_time
        status = outcome.status
        record = StageRun(
            priority=priority,
            raw_status=status,
            wall_time=outcome.wall_time,
            best_bound=outcome.best_bound if priority is not None else None,
        )
        if priority is None:
            feasibility = record
        else:
            tiers[priority] = record
        if status == SolveStatus.INFEASIBLE:
            return finish(
                SolveStatus.INFEASIBLE if score is None else SolveStatus.MODEL_INVALID,
                "INTERNAL_STAGE_INCONSISTENCY" if score is not None else "INFEASIBLE",
            )
        if status == SolveStatus.MODEL_INVALID:
            return finish(status, "MODEL_INVALID")
        if status not in (SolveStatus.FEASIBLE, SolveStatus.OPTIMAL):
            return finish(SolveStatus.FEASIBLE if score is not None else SolveStatus.UNKNOWN)
        hard = validate_schedule(problem, outcome.assignments)
        candidate = evaluate_score(problem, outcome.assignments)
        if not hard.valid or candidate.status != "OK":
            return finish(SolveStatus.MODEL_INVALID, "INTERNAL_VALIDATION_FAILED")
        expected_rules = {r.rule_id: (r.raw_penalty, r.weighted_penalty) for r in candidate.rules}
        assert candidate.tiers is not None
        expected_tiers = {p: candidate.tiers[p - 1] for p in compiled.tiers}
        if expected_rules != outcome.rule_values or expected_tiers != outcome.tier_values:
            return finish(SolveStatus.MODEL_INVALID, "INTERNAL_SCORE_MISMATCH")
        if score is None or candidate.tiers < score.tiers:
            assignments = outcome.assignments
            validation = hard
            score = candidate
        if priority is None:
            continue
        # OPTIMAL is a proof only for this tier under already-proved prefix equalities.
        optimum = outcome.tier_values[priority]
        if status == SolveStatus.OPTIMAL:
            if score is None or score.tiers is None or score.tiers[priority - 1] != optimum:
                return finish(SolveStatus.MODEL_INVALID, "INTERNAL_STAGE_INCONSISTENCY")
            prefix.append(priority)
            tiers[priority] = StageRun(
                priority=priority,
                raw_status=status,
                incumbent_value=optimum,
                best_bound=outcome.best_bound,
                wall_time=outcome.wall_time,
                proved_optimal=True,
            )
            built.model.add(compiled.tiers[priority] == optimum)
        else:
            tiers[priority] = StageRun(
                priority=priority,
                raw_status=status,
                incumbent_value=score.tiers[priority - 1],
                best_bound=outcome.best_bound,
                wall_time=outcome.wall_time,
            )
            return finish(SolveStatus.FEASIBLE)
    return finish(SolveStatus.OPTIMAL)
