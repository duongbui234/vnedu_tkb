"""Static policy metadata; importing contracts never imports OR-Tools."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import JsonValue

from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import (
    ConstraintConfigV11,
    DomainModel,
    HardConstraintConfigV11,
    SoftConstraintConfigV11,
)
from tkb_core.domain.rule_parameters import (
    AvoidSlotsParameters,
    DaySpreadParameters,
    MaxDayParameters,
    MaxSessionParameters,
    PeriodWindowParameters,
    RuleParameters,
    SubjectDayLimitParameters,
)

if TYPE_CHECKING:
    from tkb_core.contracts.input import ScheduleInput

POLICY_ORDER = ("0.1", "0.2", "0.3")
# Policies whose enabled hard rules are compiled (0.1 refuses every enabled hard rule).
HARD_POLICIES = ("0.2", "0.3")
TEACHER_SCOPE = "teacher"
NO_SCOPE = "none"
CLASS_SUBJECT_SCOPE = "class_subject"


@dataclass(frozen=True)
class RuleDefinition:
    """Semantics known independently of runtime implementation availability."""

    code: str
    policy_id: str
    parameters: type[DomainModel]
    unit: str = "teaching_periods"
    # Policy 0.1 modes; unchanged so historical inputs keep their capability verdicts.
    supported_modes: tuple[str, ...] = ()
    # Policies whose hard mode has a compiler, independent checker and oracle tests.
    hard_policies: tuple[str, ...] = ()
    # Policies whose soft mode has a compiler, independent evaluator and oracle tests.
    soft_policies: tuple[str, ...] = ()
    scope: str = TEACHER_SCOPE
    # First policy that knows the code; None keeps it known (parsed, checked) in every policy.
    since_policy: str | None = None


DEFINITIONS = {
    d.code: d
    for d in (
        RuleDefinition(
            "TEACHER_AVOID_SLOTS",
            "S01",
            AvoidSlotsParameters,
            supported_modes=("soft",),
            hard_policies=HARD_POLICIES,
            soft_policies=("0.1", "0.2", "0.3"),
        ),
        RuleDefinition(
            "TEACHER_MAX_PERIODS_PER_SESSION",
            "S02",
            MaxSessionParameters,
            supported_modes=("soft",),
            hard_policies=HARD_POLICIES,
            soft_policies=("0.1", "0.2", "0.3"),
        ),
        RuleDefinition(
            "TEACHER_MAX_PERIODS_PER_DAY",
            "S03",
            MaxDayParameters,
            supported_modes=("soft",),
            hard_policies=HARD_POLICIES,
            soft_policies=("0.1", "0.2", "0.3"),
        ),
        RuleDefinition(
            "TEACHER_PREFERRED_PERIOD_WINDOW",
            "S04",
            PeriodWindowParameters,
            supported_modes=("soft",),
            hard_policies=HARD_POLICIES,
            soft_policies=("0.1", "0.2", "0.3"),
        ),
        RuleDefinition(
            "SUBJECT_COMPONENT_DAY_SPREAD",
            "S05",
            DaySpreadParameters,
            unit="day_gap_shortfall",
            hard_policies=("0.3",),
            soft_policies=("0.3",),
            scope=NO_SCOPE,
            since_policy="0.3",
        ),
        RuleDefinition(
            "CLASS_SUBJECT_MAX_PERIODS_PER_DAY",
            "S06",
            SubjectDayLimitParameters,
            hard_policies=("0.3",),
            soft_policies=("0.3",),
            scope=CLASS_SUBJECT_SCOPE,
            since_policy="0.3",
        ),
    )
}


def known_in_policy(code: str, policy_version: str) -> bool:
    """Whether the policy parses/checks this code (it may still lack an enabled mode).

    Codes introduced by a later policy stay unknown to older ones, so their payloads stay raw.
    """
    definition = DEFINITIONS.get(code)
    if definition is None:
        return False
    if definition.since_policy is None:
        return True
    return POLICY_ORDER.index(policy_version) >= POLICY_ORDER.index(definition.since_policy)


def supports_mode(code: str, mode: str, policy_version: str) -> bool:
    """Whether ``code`` may be enabled in ``mode`` under ``policy_version``."""
    definition = DEFINITIONS.get(code)
    if definition is None:
        return False
    if mode == "soft":
        return policy_version in definition.soft_policies
    return mode == "hard" and policy_version in definition.hard_policies


def enabled_rules(
    config: ConstraintConfigV11,
) -> list[HardConstraintConfigV11 | SoftConstraintConfigV11]:
    """Enabled soft rules, plus enabled hard rules where the policy defines hard modes."""
    hard = list(config.hard) if config.policy_version in HARD_POLICIES else []
    return [r for r in (*hard, *config.soft) if r.enabled]


def parse_parameters(
    code: str, parameters: dict[str, JsonValue], policy_version: str
) -> RuleParameters | None:
    """Validate parameters of codes known to the policy; others retain raw array order."""
    if not known_in_policy(code, policy_version):
        return None
    parsed = DEFINITIONS[code].parameters.model_validate(parameters)
    assert isinstance(
        parsed,
        (
            AvoidSlotsParameters,
            MaxSessionParameters,
            MaxDayParameters,
            PeriodWindowParameters,
            DaySpreadParameters,
            SubjectDayLimitParameters,
        ),
    )
    for field in ("slot_ids", "session_ids", "requirement_ids"):
        values = getattr(parsed, field, ())
        if len(values) != len(set(values)):
            raise ValueError("Duplicate rule parameter references")
    return parsed


def _scope_allowed(rule: HardConstraintConfigV11 | SoftConstraintConfigV11) -> bool:
    kind = DEFINITIONS[rule.code].scope
    scope = rule.scope
    if kind == TEACHER_SCOPE:
        return not (scope.class_ids or scope.subject_ids or scope.room_ids)
    if kind == CLASS_SUBJECT_SCOPE:
        return not (scope.teacher_ids or scope.room_ids)
    return not (scope.class_ids or scope.subject_ids or scope.room_ids or scope.teacher_ids)


def validate_rule_config(problem: "ScheduleInput") -> None:
    """Reject unknown codes, unsupported scopes and overlapping rules of one family.

    Overlap is checked whatever the modes: policy 0.1 checks only preferences (its enabled
    hard rules are refused later); later policies include enabled hard variants.
    """
    config = problem.constraint_config
    if not isinstance(config, ConstraintConfigV11):
        return
    policy = config.policy_version
    enabled = enabled_rules(config)
    slots = {s.id: s for s in problem.time_slots}
    everyone = {t.id for t in problem.teachers}
    all_classes = {c.id for c in problem.classes}
    all_subjects = {s.id for s in problem.subjects}
    for i, r in enumerate(enabled):
        if not known_in_policy(r.code, policy):
            raise CoreError("UNSUPPORTED_FEATURE", "UNKNOWN_RULE", "Unknown enabled rule")
        if not _scope_allowed(r):
            raise CoreError("UNSUPPORTED_FEATURE", "RULE_SCOPE", "Rule scope is not supported")
        params = parse_parameters(r.code, r.parameters, policy)
        for other in enabled[:i]:
            if other.code != r.code:
                continue
            op = parse_parameters(other.code, other.parameters, policy)
            if isinstance(params, DaySpreadParameters) and isinstance(op, DaySpreadParameters):
                overlap = bool(set(params.requirement_ids) & set(op.requirement_ids))
            elif isinstance(params, SubjectDayLimitParameters):
                overlap = bool(
                    (set(r.scope.class_ids) or all_classes)
                    & (set(other.scope.class_ids) or all_classes)
                ) and bool(
                    (set(r.scope.subject_ids) or all_subjects)
                    & (set(other.scope.subject_ids) or all_subjects)
                )
            elif not (set(r.scope.teacher_ids) or everyone) & (
                set(other.scope.teacher_ids) or everyone
            ):
                overlap = False
            elif isinstance(params, AvoidSlotsParameters) and isinstance(op, AvoidSlotsParameters):

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
            else:
                overlap = True
            if overlap:
                raise CoreError(
                    "INPUT_INVALID", "OVERLAPPING_RULES", "Effective rule scopes overlap"
                )
