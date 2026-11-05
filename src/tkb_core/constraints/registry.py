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
    FreeTimeParameters,
    GapRunParameters,
    MaxDayParameters,
    MaxSessionParameters,
    PeriodWindowParameters,
    RestrictedSlotsParameters,
    RuleParameters,
    SinglePeriodParameters,
    SubjectDayLimitParameters,
    TotalGapsParameters,
)

if TYPE_CHECKING:
    from tkb_core.contracts.input import ScheduleInput

POLICY_ORDER = ("0.1", "0.2", "0.3", "0.4")
# Policies whose enabled hard rules are compiled (0.1 refuses every enabled hard rule).
HARD_POLICIES = ("0.2", "0.3", "0.4")
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
            soft_policies=("0.1", "0.2", "0.3", "0.4"),
        ),
        RuleDefinition(
            "TEACHER_MAX_PERIODS_PER_SESSION",
            "S02",
            MaxSessionParameters,
            supported_modes=("soft",),
            hard_policies=HARD_POLICIES,
            soft_policies=("0.1", "0.2", "0.3", "0.4"),
        ),
        RuleDefinition(
            "TEACHER_MAX_PERIODS_PER_DAY",
            "S03",
            MaxDayParameters,
            supported_modes=("soft",),
            hard_policies=HARD_POLICIES,
            soft_policies=("0.1", "0.2", "0.3", "0.4"),
        ),
        RuleDefinition(
            "TEACHER_PREFERRED_PERIOD_WINDOW",
            "S04",
            PeriodWindowParameters,
            supported_modes=("soft",),
            hard_policies=HARD_POLICIES,
            soft_policies=("0.1", "0.2", "0.3", "0.4"),
        ),
        RuleDefinition(
            "SUBJECT_COMPONENT_DAY_SPREAD",
            "S05",
            DaySpreadParameters,
            unit="day_gap_shortfall",
            hard_policies=("0.3", "0.4"),
            soft_policies=("0.3", "0.4"),
            scope=NO_SCOPE,
            since_policy="0.3",
        ),
        RuleDefinition(
            "CLASS_SUBJECT_MAX_PERIODS_PER_DAY",
            "S06",
            SubjectDayLimitParameters,
            hard_policies=("0.3", "0.4"),
            soft_policies=("0.3", "0.4"),
            scope=CLASS_SUBJECT_SCOPE,
            since_policy="0.3",
        ),
        # Phase 2C-2 (policy 0.4): soft only, teacher scope.
        RuleDefinition(
            "TEACHER_RESTRICTED_SLOTS",
            "S07",
            RestrictedSlotsParameters,
            soft_policies=("0.4",),
            since_policy="0.4",
        ),
        RuleDefinition(
            "TEACHER_TOTAL_GAPS",
            "S08",
            TotalGapsParameters,
            unit="idle_periods",
            soft_policies=("0.4",),
            since_policy="0.4",
        ),
        RuleDefinition(
            "TEACHER_MAX_GAP_RUN",
            "S09",
            GapRunParameters,
            unit="idle_periods",
            soft_policies=("0.4",),
            since_policy="0.4",
        ),
        RuleDefinition(
            "TEACHER_MIN_FREE_TIME",
            "S10",
            FreeTimeParameters,
            unit="free_days",  # free_sessions when parameters.unit == "session"
            soft_policies=("0.4",),
            since_policy="0.4",
        ),
        RuleDefinition(
            "TEACHER_SINGLE_PERIOD_SESSION",
            "S11",
            SinglePeriodParameters,
            unit="single_period_sessions",
            soft_policies=("0.4",),
            since_policy="0.4",
        ),
    )
}
# S01 and S07 are distinct preferences, but policy forbids counting one teacher period twice.
SHARED_SLOT_FAMILY = frozenset({"TEACHER_AVOID_SLOTS", "TEACHER_RESTRICTED_SLOTS"})
GAP_CODES = frozenset(
    {
        "TEACHER_TOTAL_GAPS",
        "TEACHER_MAX_GAP_RUN",
        "TEACHER_MIN_FREE_TIME",
        "TEACHER_SINGLE_PERIOD_SESSION",
    }
)


def rule_unit(code: str, params: object) -> str:
    """Raw-penalty unit of one rule; S10 depends on its chosen unit."""
    if isinstance(params, FreeTimeParameters) and params.unit == "session":
        return "free_sessions"
    return DEFINITIONS[code].unit


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
            RestrictedSlotsParameters,
            TotalGapsParameters,
            GapRunParameters,
            FreeTimeParameters,
            SinglePeriodParameters,
        ),
    )
    for field in ("slot_ids", "session_ids", "requirement_ids"):
        values = getattr(parsed, field, ())
        if len(values) != len(set(values)):
            raise ValueError("Duplicate rule parameter references")
    return parsed


SLOT_PARAMETERS = (AvoidSlotsParameters, RestrictedSlotsParameters)
SESSION_PARAMETERS = (
    MaxSessionParameters,
    PeriodWindowParameters,
    TotalGapsParameters,
    GapRunParameters,
    SinglePeriodParameters,
)


def _gap_timeline_ambiguous(problem: "ScheduleInput") -> bool:
    """Two sessions of one day overlapping in minutes make per-session gaps undefined."""
    timed = [s for s in problem.time_slots if s.start_minute is not None]
    for i, a in enumerate(timed):
        for b in timed[i + 1 :]:
            assert a.start_minute is not None and a.end_minute is not None
            assert b.start_minute is not None and b.end_minute is not None
            if (
                a.day == b.day
                and a.session != b.session
                and a.start_minute < b.end_minute
                and b.start_minute < a.end_minute
            ):
                return True
    return False


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
            if other.code != r.code and {r.code, other.code} != SHARED_SLOT_FAMILY:
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
            elif isinstance(params, SLOT_PARAMETERS) and isinstance(op, SLOT_PARAMETERS):

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
            elif isinstance(params, SESSION_PARAMETERS) and isinstance(op, SESSION_PARAMETERS):
                overlap = bool(set(params.session_ids) & set(op.session_ids))
            else:
                overlap = True
            if overlap:
                raise CoreError(
                    "INPUT_INVALID", "OVERLAPPING_RULES", "Effective rule scopes overlap"
                )
    if any(r.code in GAP_CODES for r in enabled) and _gap_timeline_ambiguous(problem):
        raise CoreError(
            "UNSUPPORTED_FEATURE",
            "GAP_TIMELINE",
            "Gap and free-time rules need sessions that do not overlap within a day",
        )
