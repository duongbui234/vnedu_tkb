"""Output schemas 1.0-1.5 with guardrails against contradictory schedule claims."""

from typing import Annotated, Any, Literal, Self

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    StrictBool,
    StrictFloat,
    model_serializer,
    model_validator,
)

from tkb_core.contracts.score import QualityReport, StageRun
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import (
    Diagnostic,
    DomainModel,
    Identifier,
    NonNegativeInt,
    PositiveInt,
    ScheduleAssignment,
)

# Quality output version -> the only policy version it may describe; strict pairing keeps
# a 1.2 reader from misreading policy 0.2 hard-variant semantics.
QUALITY_POLICY = {"1.2": "0.1", "1.3": "0.2", "1.4": "0.3", "1.5": "0.4"}
# Quality output version -> the ScoreReport version its embedded score must use.
SCORE_VERSION = {"1.2": "1.0", "1.3": "1.0", "1.4": "1.1", "1.5": "1.2"}


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


class SolverRunMetadataV12(SolverRunMetadata):
    """Measurements of feasibility and quality calls; not a global scalar objective."""

    feasibility_run: StageRun = Field(default_factory=StageRun)


class ScheduleResult(DomainModel):
    """Versioned result; structural consistency alone is not scheduling correctness."""

    schema_version: Literal["1.0", "1.1", "1.2", "1.3", "1.4", "1.5"]
    status: SolveStatus
    input_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None
    valid_schedule: StrictBool = False
    assignments: tuple[ScheduleAssignment, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    validation: ValidationReport | None = None
    quality: QualityReport | None = None
    metadata: SolverRunMetadataV12 | SolverRunMetadata | RunMetadata = Field(
        default_factory=RunMetadata
    )

    @model_validator(mode="before")
    @classmethod
    def metadata_version(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            version = data.get("schema_version")
            metadata_types: dict[str, type[RunMetadata]] = {
                "1.0": RunMetadata,
                "1.1": SolverRunMetadata,
                "1.2": SolverRunMetadataV12,
                "1.3": SolverRunMetadataV12,
                "1.4": SolverRunMetadataV12,
                "1.5": SolverRunMetadataV12,
            }
            metadata_type = metadata_types.get(version) if isinstance(version, str) else None
            if metadata_type is not None:
                data["metadata"] = metadata_type.model_validate(data.get("metadata", {}))
        return data

    @model_validator(mode="after")
    def check_result(self) -> Self:
        quality_output = self.schema_version in QUALITY_POLICY
        if not quality_output and "quality" in self.model_fields_set:
            raise ValueError("Legacy output cannot contain quality")
        if quality_output:
            if not isinstance(self.metadata, SolverRunMetadataV12) or self.quality is None:
                raise ValueError("Quality output requires versioned metadata/report")
            if self.quality.policy_version != QUALITY_POLICY[self.schema_version]:
                raise ValueError("Output schema version does not match policy version")
            score = self.quality.score
            if score is not None and score.schema_version != SCORE_VERSION[self.schema_version]:
                raise ValueError("Output schema version does not match score version")
            if self.valid_schedule and self.quality.status == "NOT_EVALUATED":
                raise ValueError("Valid quality output requires complete evaluation")
            if self.status == SolveStatus.OPTIMAL and self.quality.status == "SCORED_FEASIBLE":
                raise ValueError("Partial quality proof cannot claim optimality")
            if self.metadata.objective_value is not None or self.metadata.best_bound is not None:
                raise ValueError("Quality is not a global scalar objective")
            if (
                self.quality.score is not None
                and self.quality.score.input_fingerprint != self.input_fingerprint
            ):
                raise ValueError("Score fingerprint mismatch")
            if (
                self.quality.status in ("SCORED_FEASIBLE", "LEXICOGRAPHIC_OPTIMAL")
                and not self.valid_schedule
            ):
                raise ValueError("Quality requires valid schedule")
            if (
                self.quality.status == "LEXICOGRAPHIC_OPTIMAL"
                and self.status != SolveStatus.OPTIMAL
            ):
                raise ValueError("Quality optimal status mismatch")
        elif isinstance(self.metadata, SolverRunMetadataV12):
            raise ValueError("Legacy output cannot contain stage metadata")
        if not quality_output and (self.schema_version == "1.1") != isinstance(
            self.metadata, SolverRunMetadata
        ):
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

    @model_serializer(mode="wrap")
    def serialize_version(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data = dict(handler(self))
        if self.schema_version not in QUALITY_POLICY:
            data.pop("quality", None)
        return data
