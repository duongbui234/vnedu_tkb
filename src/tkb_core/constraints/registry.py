"""Static policy metadata; importing contracts never imports OR-Tools."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import JsonValue

from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ConstraintConfigV11, DomainModel
from tkb_core.domain.rule_parameters import (
    AvoidSlotsParameters,
    MaxDayParameters,
    MaxSessionParameters,
    PeriodWindowParameters,
    RuleParameters,
)

if TYPE_CHECKING:
    from tkb_core.contracts.input import ScheduleInput


@dataclass(frozen=True)
class RuleDefinition:
    """Semantics known independently of runtime implementation availability."""

    code: str
    policy_id: str
    parameters: type[DomainModel]
    unit: str = "teaching_periods"
    supported_modes: tuple[str, ...] = ()


DEFINITIONS = {
    d.code: d
    for d in (
        RuleDefinition(
            "TEACHER_AVOID_SLOTS", "S01", AvoidSlotsParameters, supported_modes=("soft",)
        ),
        RuleDefinition(
            "TEACHER_MAX_PERIODS_PER_SESSION",
            "S02",
            MaxSessionParameters,
            supported_modes=("soft",),
        ),
        RuleDefinition(
            "TEACHER_MAX_PERIODS_PER_DAY", "S03", MaxDayParameters, supported_modes=("soft",)
        ),
        RuleDefinition(
            "TEACHER_PREFERRED_PERIOD_WINDOW",
            "S04",
            PeriodWindowParameters,
            supported_modes=("soft",),
        ),
    )
}


def parse_parameters(code: str, parameters: dict[str, JsonValue]) -> RuleParameters | None:
    """Validate known parameters; unknown disabled payloads retain array order."""
    definition = DEFINITIONS.get(code)
    if definition is None:
        return None
    parsed = definition.parameters.model_validate(parameters)
    assert isinstance(
        parsed,
        (AvoidSlotsParameters, MaxSessionParameters, MaxDayParameters, PeriodWindowParameters),
    )
    for field in ("slot_ids", "session_ids"):
        values = getattr(parsed, field, ())
        if len(values) != len(set(values)):
            raise ValueError("Duplicate rule parameter references")
    return parsed


def validate_rule_config(problem: "ScheduleInput") -> None:
    """Reject unresolved overlapping preferences instead of adding duplicate costs."""
    config = problem.constraint_config
    if not isinstance(config, ConstraintConfigV11):
        return
    enabled = [r for r in config.soft if r.enabled]
    slots = {s.id: s for s in problem.time_slots}
    for i, r in enumerate(enabled):
        if r.code not in DEFINITIONS:
            raise CoreError("UNSUPPORTED_FEATURE", "UNKNOWN_RULE", "Unknown enabled rule")
        if r.scope.class_ids or r.scope.subject_ids or r.scope.room_ids:
            raise CoreError("UNSUPPORTED_FEATURE", "RULE_SCOPE", "Only teacher scope is supported")
        teachers = set(r.scope.teacher_ids) or {t.id for t in problem.teachers}
        params = parse_parameters(r.code, r.parameters)
        for other in enabled[:i]:
            if other.code != r.code:
                continue
            actors = set(other.scope.teacher_ids) or {t.id for t in problem.teachers}
            if not teachers & actors:
                continue
            op = parse_parameters(other.code, other.parameters)
            overlap = True
            if isinstance(params, AvoidSlotsParameters) and isinstance(op, AvoidSlotsParameters):

                def hits(covered_id: str, targets: tuple[str, ...]) -> bool:
                    a = slots[covered_id]
                    if a.start_minute is None:
                        return covered_id in targets
                    assert a.end_minute is not None
                    for target in targets:
                        b = slots[target]
                        if b.start_minute is not None and b.end_minute is not None:
                            if a.start_minute < b.end_minute and b.start_minute < a.end_minute:
                                return True
                    return False

                overlap = any(
                    s.can_teach and hits(s.id, params.slot_ids) and hits(s.id, op.slot_ids)
                    for s in slots.values()
                )
            elif isinstance(params, (MaxSessionParameters, PeriodWindowParameters)) and isinstance(
                op, (MaxSessionParameters, PeriodWindowParameters)
            ):
                overlap = bool(set(params.session_ids) & set(op.session_ids))
            if overlap:
                raise CoreError(
                    "INPUT_INVALID", "OVERLAPPING_RULES", "Effective rule scopes overlap"
                )
