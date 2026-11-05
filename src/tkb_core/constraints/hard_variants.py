"""Compile placement-local policy 0.2 hard variants into forbidden slot sets.

S01/S04 hard depend only on the covered slots of one placement, so they are enforced by
removing placements before model construction (like availability). Load limits S02/S03
are linear model constraints in ``constraints.hard``. Nothing here imports OR-Tools,
and the independent validator deliberately does not use this module.
"""

from collections import defaultdict
from collections.abc import Callable, Sequence

from tkb_core.constraints.registry import HARD_POLICIES, parse_parameters
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ConstraintConfigV11, HardConstraintConfigV11, TimeSlot
from tkb_core.domain.rule_parameters import (
    AvoidSlotsParameters,
    PeriodWindowParameters,
    RuleParameters,
)

PlacementFilter = Callable[[str, Sequence[TimeSlot]], bool]


def enabled_hard(
    problem: ScheduleInput,
) -> list[tuple[HardConstraintConfigV11, frozenset[str], RuleParameters | None]]:
    """(rule, resolved teachers, parameters) of enabled compiled hard rules, sorted by ID."""
    config = problem.constraint_config
    if not isinstance(config, ConstraintConfigV11) or config.policy_version not in HARD_POLICIES:
        return []
    everyone = frozenset(t.id for t in problem.teachers)
    policy = config.policy_version
    return [
        (
            r,
            frozenset(r.scope.teacher_ids) or everyone,
            parse_parameters(r.code, r.parameters, policy),
        )
        for r in sorted(config.hard, key=lambda r: r.id)
        if r.enabled
    ]


def placement_filter(problem: ScheduleInput) -> PlacementFilter | None:
    """Return ``allowed(teacher_id, covered_slots)`` or None when nothing is filtered."""
    forbidden: dict[str, set[str]] = defaultdict(set)
    slots = problem.time_slots
    for _, teachers, params in enabled_hard(problem):
        if isinstance(params, AvoidSlotsParameters):
            targets = [s for s in slots if s.id in params.slot_ids]
            blocked = set()
            for slot in slots:
                if slot.start_minute is None:
                    if slot.id in params.slot_ids:
                        blocked.add(slot.id)
                    continue
                assert slot.end_minute is not None
                for target in targets:
                    assert target.start_minute is not None and target.end_minute is not None
                    if max(slot.start_minute, target.start_minute) < min(
                        slot.end_minute, target.end_minute
                    ):
                        blocked.add(slot.id)
                        break
        elif isinstance(params, PeriodWindowParameters):
            blocked = {
                s.id
                for s in slots
                if s.session in params.session_ids
                and not params.first_period <= s.period <= params.last_period
            }
        else:
            continue
        for teacher in teachers:
            forbidden[teacher] |= blocked
    if not forbidden:
        return None
    frozen = {t: frozenset(ids) for t, ids in forbidden.items()}

    def allowed(teacher_id: str, covered: Sequence[TimeSlot]) -> bool:
        blocked = frozen.get(teacher_id)
        return blocked is None or not any(s.id in blocked for s in covered)

    return allowed
