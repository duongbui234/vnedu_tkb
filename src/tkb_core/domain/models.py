"""Typed domain records; parsing these records does not prove scheduling feasibility."""

from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StrictInt,
    StrictStr,
    model_validator,
)

Identifier = Annotated[StrictStr, Field(min_length=1, pattern=r"\S")]
PositiveInt = Annotated[StrictInt, Field(gt=0)]
NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class DomainModel(BaseModel):
    """Reject unknown fields and non-finite numeric fields at the JSON boundary."""

    model_config = ConfigDict(extra="forbid", validate_default=True, allow_inf_nan=False)


class Entity(DomainModel):
    """An opaque source ID, never inferred from a human-readable name."""

    id: Identifier
    source_reference: Identifier | None = None


class SchoolContext(DomainModel):
    """Calendar scope supplied by the caller, not discovered from vnEdu."""

    school_id: Identifier
    academic_year: Identifier
    term: Identifier
    timezone: Identifier = "Asia/Ho_Chi_Minh"


class TimeSlot(Entity):
    """An explicitly ordered period; optional minutes share a cycle-wide origin."""

    day: PositiveInt
    session: Identifier
    period: PositiveInt
    can_teach: StrictBool = True
    start_minute: NonNegativeInt | None = None
    end_minute: NonNegativeInt | None = None

    @model_validator(mode="after")
    def check_interval(self) -> Self:
        if (self.start_minute is None) != (self.end_minute is None):
            raise ValueError("Both start_minute and end_minute are required together")
        if self.start_minute is not None and self.end_minute is not None:
            if self.start_minute >= self.end_minute:
                raise ValueError("end_minute must follow start_minute")
        return self


class AvailableResource(Entity):
    """None means all teaching slots; an empty tuple means no available slots."""

    available_slot_ids: tuple[Identifier, ...] | None = None


class ClassGroup(AvailableResource):
    """One learner resource; overlapping subgroup membership is not modeled yet."""

    size: PositiveInt | None = None


class Teacher(AvailableResource):
    """A teaching resource with explicit optional availability."""


class Subject(Entity):
    """A subject catalog entry without implicit curriculum rules."""


class Room(AvailableResource):
    """An optional physical room; missing capacity does not imply unlimited capacity."""

    room_type: Identifier | None = None
    capacity: PositiveInt | None = None


class TeachingRequirement(Entity):
    """A caller-confirmed demand; block order determines occurrence ordinals."""

    class_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    subject_id: Identifier
    teacher_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    periods_per_cycle: NonNegativeInt
    room_required: StrictBool = False
    required_room_type: Identifier | None = None
    block_durations: tuple[PositiveInt, ...] | None = None

    @property
    def occurrence_count(self) -> int:
        """Count single lessons or explicitly declared blocks without allocating them."""
        return self.periods_per_cycle if self.block_durations is None else len(self.block_durations)

    @model_validator(mode="after")
    def check_demand(self) -> Self:
        if self.block_durations is not None:
            if sum(self.block_durations) != self.periods_per_cycle:
                raise ValueError("Block duration sum must equal periods_per_cycle")
        if self.required_room_type is not None and not self.room_required:
            raise ValueError("required_room_type requires room_required=true")
        return self


class LessonOccurrence(Entity):
    """A normalized occurrence record for Phase 1; Phase 0 does not expand demands."""

    requirement_id: Identifier
    ordinal: PositiveInt
    duration: PositiveInt = 1


class LockedAssignment(DomainModel):
    """Time and room locks can be expressed separately in one record per occurrence."""

    occurrence_id: Identifier
    slot_id: Identifier | None = None
    room_id: Identifier | None = None

    @model_validator(mode="after")
    def check_target(self) -> Self:
        if self.slot_id is None and self.room_id is None:
            raise ValueError("A lock must specify slot_id or room_id")
        return self


class RuleScope(DomainModel):
    """An empty scope applies globally; resource references are checked by the input."""

    class_ids: tuple[Identifier, ...] = ()
    teacher_ids: tuple[Identifier, ...] = ()
    subject_ids: tuple[Identifier, ...] = ()
    room_ids: tuple[Identifier, ...] = ()


class HardConstraintConfig(DomainModel):
    """A declared hard rule; Phase 0 carries data but does not enforce the rule."""

    code: Identifier
    scope: RuleScope = Field(default_factory=RuleScope)
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    enabled: StrictBool = True


class SoftConstraintConfig(HardConstraintConfig):
    """A declared preference with an explicit integer weight, never an implicit score."""

    weight: PositiveInt


class ConstraintConfig(DomainModel):
    """Rule declarations, not a registry of implemented constraint capabilities."""

    hard: tuple[HardConstraintConfig, ...] = ()
    soft: tuple[SoftConstraintConfig, ...] = ()


class ScheduleAssignment(DomainModel):
    """Transport record; independent validation of its meaning belongs to Phase 1."""

    occurrence_id: Identifier
    slot_id: Identifier
    class_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    teacher_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    room_id: Identifier | None = None


class Diagnostic(DomainModel):
    """A structured error or violation without embedded input records."""

    code: Identifier
    message: StrictStr
    resource_ids: tuple[Identifier, ...] = ()
    slot_ids: tuple[Identifier, ...] = ()
    occurrence_ids: tuple[Identifier, ...] = ()
