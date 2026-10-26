"""Strict parameters; these declarations do not imply solver capability."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from tkb_core.domain.models import DomainModel, Identifier, NonNegativeInt, PositiveInt


class AvoidSlotsParameters(DomainModel):
    slot_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class MaxSessionParameters(DomainModel):
    limit: NonNegativeInt
    session_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class MaxDayParameters(DomainModel):
    limit: NonNegativeInt


class PeriodWindowParameters(DomainModel):
    first_period: PositiveInt
    last_period: PositiveInt
    session_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.first_period > self.last_period:
            raise ValueError("Window bounds reversed")
        return self


RuleParameters = (
    AvoidSlotsParameters | MaxSessionParameters | MaxDayParameters | PeriodWindowParameters
)
