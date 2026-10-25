"""Output schemas 1.0/1.1 with guardrails against contradictory schedule claims."""

from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictFloat, model_validator

from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import (
    Diagnostic,
    DomainModel,
    Identifier,
    NonNegativeInt,
    PositiveInt,
    ScheduleAssignment,
)


class ValidationReport(DomainModel):
    """Pure-data report produced by the independent schedule checker."""

    valid: StrictBool
    violations: tuple[Diagnostic, ...] = ()

    @model_validator(mode="after")
    def check_claim(self) -> Self:
        if self.valid and self.violations:
            raise ValueError("A valid report cannot contain violations")
        return self


class RunMetadata(DomainModel):
    """No solver execution is implied by a default empty metadata object."""

    solver_version: Identifier | None = None
    wall_time: Annotated[StrictFloat, Field(ge=0)] | None = None
    objective_value: StrictFloat | None = None
    best_bound: StrictFloat | None = None


class SolverRunMetadata(RunMetadata):
    """Version 1.1 execution metadata; absent measurements remain null."""

    solver_executed: StrictBool
    solver_wall_time: Annotated[StrictFloat, Field(ge=0)] | None = None
    seed: NonNegativeInt | None = None
    num_workers: PositiveInt | None = None
    time_limit_seconds: Annotated[StrictFloat, Field(gt=0)] | None = None


class ScheduleResult(DomainModel):
    """Versioned result; structural consistency alone is not scheduling correctness."""

    schema_version: Literal["1.0", "1.1"]
    status: SolveStatus
    input_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    valid_schedule: StrictBool = False
    assignments: tuple[ScheduleAssignment, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    validation: ValidationReport | None = None
    metadata: SolverRunMetadata | RunMetadata = Field(default_factory=RunMetadata)

    @model_validator(mode="after")
    def check_result(self) -> Self:
        if (self.schema_version == "1.1") != isinstance(self.metadata, SolverRunMetadata):
            raise ValueError("Execution metadata must match output schema version")
        if self.valid_schedule:
            if self.status not in (SolveStatus.FEASIBLE, SolveStatus.OPTIMAL):
                raise ValueError("Only a successful solve can claim valid_schedule")
            if self.validation is None or not self.validation.valid:
                raise ValueError("valid_schedule requires a valid independent validation report")
            if self.input_fingerprint is None:
                raise ValueError("valid_schedule requires input_fingerprint")
        if self.assignments and not self.valid_schedule:
            raise ValueError("Unvalidated or unsuccessful results cannot expose assignments")
        return self
