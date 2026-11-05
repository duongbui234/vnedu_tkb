"""Recompute scores from raw assignments, independently of placements and CP-SAT."""

from collections import Counter
from collections.abc import Sequence
from typing import Literal

from tkb_core.constraints.registry import DEFINITIONS, parse_parameters, validate_rule_config
from tkb_core.contracts.capabilities import check_capabilities
from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.score import RuleScore, ScoreReport
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ConstraintConfigV11, Diagnostic, ScheduleAssignment
from tkb_core.domain.rule_parameters import (
    AvoidSlotsParameters,
    DaySpreadParameters,
    MaxDayParameters,
    MaxSessionParameters,
    PeriodWindowParameters,
    SubjectDayLimitParameters,
)
from tkb_core.validation.independent_validator import validate_schedule


def _evaluate_validated(
    problem: ScheduleInput, assignments: Sequence[ScheduleAssignment]
) -> ScoreReport:
    """Score an already checked schedule; callers must use evaluate_score instead."""
    slots = {s.id: s for s in problem.time_slots}
    coords = {(s.day, s.session, s.period): s for s in problem.time_slots}
    reqs = {r.id: r for r in problem.teaching_requirements}
    covered = []
    loads: Counter[tuple[str, int, str]] = Counter()
    # One entry per component (occurrence): requirement and the real day it starts on.
    component_days: list[tuple[str, int]] = []
    subject_days: Counter[tuple[str, str, int]] = Counter()
    for a in assignments:
        rid, _, ordinal = a.occurrence_id.rpartition("::")
        req = reqs[rid]
        duration = req.block_durations[int(ordinal) - 1] if req.block_durations is not None else 1
        start = slots[a.slot_id]
        component_days.append((rid, start.day))
        for offset in range(duration):
            slot = coords[start.day, start.session, start.period + offset]
            teacher = req.teacher_ids[0]
            covered.append((teacher, slot))
            loads[teacher, slot.day, slot.session] += 1
            subject_days[req.class_ids[0], req.subject_id, slot.day] += 1
    rows = []
    config = problem.constraint_config
    if isinstance(config, ConstraintConfigV11):
        for rule in sorted(config.soft, key=lambda r: r.id):
            if not rule.enabled:
                continue
            teachers = set(rule.scope.teacher_ids) or {t.id for t in problem.teachers}
            params = parse_parameters(rule.code, rule.parameters, config.policy_version)
            raw = 0
            if isinstance(params, AvoidSlotsParameters):
                for teacher, slot in covered:
                    if teacher not in teachers:
                        continue
                    if slot.start_minute is None:
                        raw += int(slot.id in params.slot_ids)
                    else:
                        assert slot.end_minute is not None
                        raw += int(
                            any(
                                target.start_minute is not None
                                and target.end_minute is not None
                                and slot.start_minute < target.end_minute
                                and target.start_minute < slot.end_minute
                                for target in (slots[s] for s in params.slot_ids)
                            )
                        )
            elif isinstance(params, MaxSessionParameters):
                raw = sum(
                    max(0, n - params.limit)
                    for (t, _, session), n in loads.items()
                    if t in teachers and session in params.session_ids
                )
            elif isinstance(params, MaxDayParameters):
                daily: Counter[tuple[str, int]] = Counter()
                for (t, day, _), n in loads.items():
                    if t in teachers:
                        daily[t, day] += n
                raw = sum(max(0, n - params.limit) for n in daily.values())
            elif isinstance(params, PeriodWindowParameters):
                raw = sum(
                    1
                    for teacher, slot in covered
                    if teacher in teachers
                    and slot.session in params.session_ids
                    and not params.first_period <= slot.period <= params.last_period
                )
            elif isinstance(params, DaySpreadParameters):
                days = [d for rid, d in component_days if rid in params.requirement_ids]
                k = params.min_day_gap
                raw = sum(
                    max(0, k - abs(days[i] - days[j]))
                    for i in range(len(days))
                    for j in range(i + 1, len(days))
                )
            elif isinstance(params, SubjectDayLimitParameters):
                classes = set(rule.scope.class_ids) or {c.id for c in problem.classes}
                subjects = set(rule.scope.subject_ids) or {s.id for s in problem.subjects}
                raw = sum(
                    max(0, n - params.limit)
                    for (cls, subject, _), n in subject_days.items()
                    if cls in classes and subject in subjects
                )
            else:
                raise CoreError("UNSUPPORTED_FEATURE", "UNKNOWN_RULE", "Unknown enabled preference")
            rows.append(
                RuleScore(
                    rule_id=rule.id,
                    code=rule.code,
                    priority=rule.priority,
                    weight=rule.weight,
                    unit=DEFINITIONS[rule.code].unit,
                    raw_penalty=raw,
                    weighted_penalty=raw * rule.weight,
                )
            )
    totals = tuple(sum(r.weighted_penalty for r in rows if r.priority == p) for p in (1, 2, 3))
    return ScoreReport(
        schema_version=score_version(problem),
        status="OK",
        input_fingerprint=problem.fingerprint(),
        rules=tuple(rows),
        tiers=totals,
    )


def score_version(problem: ScheduleInput) -> Literal["1.0", "1.1"]:
    """Policy 0.3 reports use ScoreReport 1.1 (day_gap_shortfall unit); others keep 1.0."""
    config = problem.constraint_config
    if isinstance(config, ConstraintConfigV11) and config.policy_version == "0.3":
        return "1.1"
    return "1.0"


def evaluate_score(
    problem: ScheduleInput, assignments: Sequence[ScheduleAssignment]
) -> ScoreReport:
    """Validate hard correctness before returning a complete independent score."""
    fingerprint = None
    version: Literal["1.0", "1.1"] = "1.0"

    def error(
        status: Literal[
            "INPUT_INVALID", "UNSUPPORTED_FEATURE", "INVALID_SCHEDULE", "INTERNAL_ERROR"
        ],
        code: str,
    ) -> ScoreReport:
        return ScoreReport(
            schema_version=version,
            status=status,
            input_fingerprint=fingerprint,
            diagnostics=(Diagnostic(code=code, message="Schedule score could not be verified"),),
        )

    try:
        problem = ScheduleInput.model_validate(problem.model_dump(warnings="error"))
        assignments = tuple(
            ScheduleAssignment.model_validate(a.model_dump(warnings="error")) for a in assignments
        )
        fingerprint = problem.fingerprint()
        version = score_version(problem)
    except (ValueError, TypeError, AttributeError):
        return error("INPUT_INVALID", "CONTRACT_INVALID")
    try:
        validate_rule_config(problem)
        check_capabilities(problem)
    except CoreError as exc:
        status: Literal["UNSUPPORTED_FEATURE", "INPUT_INVALID"] = (
            "UNSUPPORTED_FEATURE" if exc.status.value == "UNSUPPORTED_FEATURE" else "INPUT_INVALID"
        )
        return error(status, exc.diagnostics[0].code)
    hard = validate_schedule(problem, assignments)
    if not hard.valid:
        codes = {d.code for d in hard.violations}
        if "UNSUPPORTED_FEATURE" in codes:
            return error("UNSUPPORTED_FEATURE", "UNSUPPORTED_FEATURE")
        if "INPUT_INVALID" in codes:
            return error("INPUT_INVALID", "INPUT_INVALID")
        return error("INVALID_SCHEDULE", "INVALID_SCHEDULE")
    try:
        return _evaluate_validated(problem, assignments)
    except (ValueError, TypeError, KeyError, IndexError, CoreError):
        return error("INTERNAL_ERROR", "INTERNAL_SCORE_ERROR")
