"""Shared feature declarations, not scheduling/footprint implementation."""

from tkb_core.constraints.registry import DEFINITIONS, validate_rule_config
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ConstraintConfigV11


def check_capabilities(problem: ScheduleInput) -> None:
    """Refuse enabled semantics that Phase 1 cannot enforce independently."""
    for requirement in problem.teaching_requirements:
        if len(requirement.class_ids) != 1 or len(requirement.teacher_ids) != 1:
            raise CoreError(
                "UNSUPPORTED_FEATURE",
                "MULTIPLE_PARTICIPANTS",
                "Phase 1 supports one class and one teacher per requirement",
            )
        if requirement.block_durations and any(d > 2 for d in requirement.block_durations):
            raise CoreError(
                "UNSUPPORTED_FEATURE", "BLOCK_DURATION", "Phase 1 supports duration 1 or 2 only"
            )
    if isinstance(problem.constraint_config, ConstraintConfigV11):
        validate_rule_config(problem)
        if any(r.enabled for r in problem.constraint_config.hard):
            raise CoreError(
                "UNSUPPORTED_FEATURE",
                "CUSTOM_HARD_RULE",
                "Custom hard modes are not supported in Phase 2A",
            )
        for rule in problem.constraint_config.soft:
            if rule.enabled and "soft" not in DEFINITIONS[rule.code].supported_modes:
                raise CoreError(
                    "UNSUPPORTED_FEATURE", "CUSTOM_RULE", "Preference implementation is unavailable"
                )
        return
    if any(
        rule.enabled for rule in (*problem.constraint_config.hard, *problem.constraint_config.soft)
    ):
        raise CoreError(
            "UNSUPPORTED_FEATURE",
            "CUSTOM_RULE",
            "Enabled custom hard/soft rules are not implemented in Phase 1",
        )
