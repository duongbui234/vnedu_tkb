"""Sparse Boolean placement model, imported only for actual solver execution."""

from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise

from ortools.sat.python import cp_model

from tkb_core.constraints.hard import add_occupancy
from tkb_core.domain.models import ConstraintConfigV11, LessonOccurrence
from tkb_core.preprocessing.feasibility import Placement, PreparedProblem

_MAX_LINEAR_ACTIVITY = 2**63 - 1
_RESOURCE_ONLY_SOFT_RULES = frozenset(
    {
        "TEACHER_AVOID_SLOTS",
        "TEACHER_MAX_PERIODS_PER_SESSION",
        "TEACHER_MAX_PERIODS_PER_DAY",
        "TEACHER_PREFERRED_PERIOD_WINDOW",
    }
)


@dataclass(frozen=True)
class BuiltModel:
    """CP-SAT model and its placement selection variables."""

    model: cp_model.CpModel
    variables: dict[str, tuple[cp_model.IntVar, ...]]


def _rank_range_safe(domain_size: int) -> bool:
    """Skip constant ranks and comparisons whose total coefficient activity may overflow."""
    return domain_size > 1 and domain_size * (domain_size - 1) <= _MAX_LINEAR_ACTIVITY


def _add_interchangeable_ordering(prepared: PreparedProblem, built: BuiltModel) -> None:
    """Keep a representative of unlocked label permutations, before any incumbent exists."""
    problem = prepared.normalized.problem
    config = problem.constraint_config
    if problem.schema_version != "1.1" or not isinstance(config, ConstraintConfigV11):
        return
    enabled = [r for r in config.soft if r.enabled]
    if (
        not enabled
        or any(r.code not in _RESOURCE_ONLY_SOFT_RULES for r in enabled)
        or any(r.enabled for r in config.hard)
    ):
        return
    locked = {lock.occurrence_id for lock in problem.locked_assignments}
    groups: dict[tuple[str, int, tuple[Placement, ...]], list[LessonOccurrence]] = defaultdict(list)
    for occurrence in prepared.normalized.occurrences:
        if occurrence.id not in locked:
            groups[
                (
                    occurrence.requirement_id,
                    occurrence.duration,
                    prepared.domains[occurrence.id],
                )
            ].append(occurrence)
    for (_, _, domain), members in groups.items():
        if len(members) < 2 or not _rank_range_safe(len(domain)):
            continue
        ordered = sorted(members, key=lambda o: o.ordinal)
        weights = list(range(len(domain)))
        ranks = [cp_model.LinearExpr.weighted_sum(built.variables[o.id], weights) for o in ordered]
        # Stage the full group first. ExactlyOne makes each expression a placement rank;
        # equal domains/semantics let any valid schedule be relabeled into this order.
        rows = [left <= right for left, right in pairwise(ranks)]
        for row in rows:
            built.model.add(row)


def build_model(prepared: PreparedProblem, *, order_interchangeable: bool = False) -> BuiltModel:
    """Build hard occupancy; opt-in quality ordering preserves resource/score projections.

    Direct/legacy callers retain the old model. Ordering must run before the hard clone
    and before any solve/hint, never as a remapping of an existing incumbent.
    """
    model = cp_model.CpModel()
    variables: dict[str, tuple[cp_model.IntVar, ...]] = {}
    for occurrence in prepared.normalized.occurrences:
        choices = tuple(
            model.new_bool_var(f"x_{len(variables)}_{i}")
            for i in range(len(prepared.domains[occurrence.id]))
        )
        model.add_exactly_one(choices)
        variables[occurrence.id] = choices
    add_occupancy(model, prepared, variables)
    built = BuiltModel(model, variables)
    if order_interchangeable:
        _add_interchangeable_ordering(prepared, built)
    return built
