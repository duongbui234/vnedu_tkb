"""Compile exact integer preferences; evaluator deliberately shares no arithmetic here."""

from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from tkb_core.constraints.registry import parse_parameters
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ConstraintConfigV11
from tkb_core.domain.rule_parameters import (
    AvoidSlotsParameters,
    MaxDayParameters,
    MaxSessionParameters,
    PeriodWindowParameters,
)
from tkb_core.preprocessing.feasibility import PreparedProblem
from tkb_core.solver.model_builder import BuiltModel

Expression = cp_model.LinearExpr | int
MAX_OBJECTIVE = 2**53 - 1
MAX_INTEGER = 2**63 - 1


@dataclass(frozen=True)
class CompiledRule:
    rule_id: str
    priority: int
    raw_expression: Expression
    weighted_expression: Expression
    raw_upper_bound: int
    weighted_upper_bound: int


@dataclass(frozen=True)
class CompiledSoft:
    rules: tuple[CompiledRule, ...]
    tiers: dict[int, Expression]
    upper_bounds: dict[int, int]


def _range(value: int, maximum: int = MAX_INTEGER) -> None:
    if not 0 <= value <= maximum:
        raise CoreError(
            "INPUT_INVALID", "OBJECTIVE_RANGE", "Objective exceeds exact integer limits"
        )


def compile_soft(prepared: PreparedProblem, built: BuiltModel) -> CompiledSoft:
    """Add exact expressions for enabled preferences without pruning hard domains."""
    problem = prepared.normalized.problem
    config = problem.constraint_config
    if not isinstance(config, ConstraintConfigV11):
        return CompiledSoft((), {}, {})
    slots = {s.id: s for s in problem.time_slots}
    reqs = {r.id: r for r in problem.teaching_requirements}
    rules = []
    tier_bounds: dict[int, int] = defaultdict(int)
    for rule in sorted(config.soft, key=lambda r: r.id):
        if not rule.enabled:
            continue
        params = parse_parameters(rule.code, rule.parameters)
        teachers = set(rule.scope.teacher_ids) or {t.id for t in problem.teachers}
        costs = []
        buckets: dict[tuple[str, int, str], list[tuple[cp_model.IntVar, int]]] = defaultdict(list)
        bucket_bounds: dict[tuple[str, int, str], int] = defaultdict(int)
        raw_bound = 0
        for occurrence in prepared.normalized.occurrences:
            req = reqs[occurrence.requirement_id]
            teacher = req.teacher_ids[0]
            if teacher not in teachers:
                continue
            maxima: dict[tuple[str, int, str], int] = defaultdict(int)
            max_cost = 0
            for placement, var in zip(
                prepared.domains[occurrence.id], built.variables[occurrence.id], strict=True
            ):
                covered = [slots[s] for s in placement.slot_ids]
                cost = 0
                if isinstance(params, AvoidSlotsParameters):
                    for slot in covered:
                        if prepared.normalized.timed:
                            assert slot.start_minute is not None and slot.end_minute is not None
                            intersects = False
                            for target_id in params.slot_ids:
                                target = slots[target_id]
                                assert (
                                    target.start_minute is not None
                                    and target.end_minute is not None
                                )
                                if max(slot.start_minute, target.start_minute) < min(
                                    slot.end_minute, target.end_minute
                                ):
                                    intersects = True
                                    break
                            cost += int(intersects)
                        else:
                            cost += int(slot.id in params.slot_ids)
                elif isinstance(params, PeriodWindowParameters):
                    cost = sum(
                        int(
                            s.session in params.session_ids
                            and (s.period < params.first_period or s.period > params.last_period)
                        )
                        for s in covered
                    )
                elif isinstance(params, (MaxSessionParameters, MaxDayParameters)):
                    start = covered[0]
                    if (
                        isinstance(params, MaxSessionParameters)
                        and start.session not in params.session_ids
                    ):
                        continue
                    bucket = (
                        teacher,
                        start.day,
                        start.session if isinstance(params, MaxSessionParameters) else "",
                    )
                    buckets[bucket].append((var, occurrence.duration))
                    maxima[bucket] = max(maxima[bucket], occurrence.duration)
                else:
                    raise CoreError(
                        "UNSUPPORTED_FEATURE", "UNKNOWN_RULE", "No compiler for preference"
                    )
                if cost:
                    costs.append(cost * var)
                    max_cost = max(max_cost, cost)
            raw_bound += max_cost
            for key, n in maxima.items():
                bucket_bounds[key] += n
        if isinstance(params, (MaxSessionParameters, MaxDayParameters)):
            _range(params.limit)
            raw_bound = sum(max(0, n - params.limit) for n in bucket_bounds.values())
        _range(raw_bound)
        weighted_bound = raw_bound * rule.weight
        _range(rule.weight)
        _range(weighted_bound, MAX_OBJECTIVE)
        tier_bounds[rule.priority] += weighted_bound
        _range(tier_bounds[rule.priority], MAX_OBJECTIVE)
        if isinstance(params, (MaxSessionParameters, MaxDayParameters)):
            costs = []
            for bucket, terms in buckets.items():
                # CP-SAT also validates unsimplified expression ranges, including alternatives.
                _range(sum(n for _, n in terms) + params.limit)
                bound = bucket_bounds[bucket]
                excess = built.model.new_int_var(
                    0, max(0, bound - params.limit), f"excess_{rule.id}_{bucket}"
                )
                built.model.add_max_equality(
                    excess, [0, sum(n * v for v, n in terms) - params.limit]
                )
                costs.append(excess)
        # Bound the aggregate before weighting: unselected placement alternatives must
        # not inflate CP-SAT's syntactic objective domain and overflow it.
        raw = built.model.new_int_var(0, raw_bound, f"raw_{rule.id}")
        built.model.add(raw == sum(costs))
        rules.append(
            CompiledRule(rule.id, rule.priority, raw, raw * rule.weight, raw_bound, weighted_bound)
        )
    tiers = {
        p: sum(r.weighted_expression for r in rules if r.priority == p) for p in sorted(tier_bounds)
    }
    return CompiledSoft(tuple(rules), tiers, dict(tier_bounds))
