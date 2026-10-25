"""Validated run limits, distinct from school/business constraints."""

from typing import Annotated

from pydantic import Field, StrictFloat, StrictInt

from tkb_core.domain.models import DomainModel, PositiveInt


class SolveOptions(DomainModel):
    """Development defaults are configurable and are not performance promises."""

    time_limit_seconds: Annotated[StrictFloat, Field(gt=0)] = 60.0
    num_workers: Annotated[StrictInt, Field(ge=1, le=64)] = 1
    seed: Annotated[StrictInt, Field(ge=0, le=2147483647)] = 42
    max_slots: PositiveInt = 10000
    max_occurrences: PositiveInt = 10000
    max_placements: PositiveInt = 100000
    max_occupancy_terms: PositiveInt = 1000000
