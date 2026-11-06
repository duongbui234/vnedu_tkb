"""Phase 3B infeasibility diagnostics contracts (version 1.0).

An ``InfeasibilityReport`` explains why an input has no schedule with one of two kinds of
evidence: arithmetic precheck proofs (recomputed by ``validation.precheck_verifier``) or a
conflicting subset of constraint groups proved infeasible by CP-SAT. A subset is one
conflict, never "the" cause. The report carries no assignments. Nothing here imports
OR-Tools.
"""

from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictFloat, StrictInt, model_validator

from tkb_core.domain.models import DomainModel, Identifier, NonNegativeInt, PositiveInt

Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Granularity = Literal["MODEL", "FULL"]
ReportStatus = Literal[
    "PRECHECK_PROOF", "CORE_SUBSET", "NOT_INFEASIBLE", "UNKNOWN", "RESOURCE_LIMIT"
]
# Model groups exist at every granularity; domain groups only at FULL (spec §3.2).
MODEL_KINDS = ("DEMAND", "CLASS_OCCUPANCY", "TEACHER_OCCUPANCY", "ROOM_OCCUPANCY", "HARD_RULE")
DOMAIN_KINDS = (
    "LOCK",
    "CLASS_AVAILABILITY",
    "TEACHER_AVAILABILITY",
    "ROOM_AVAILABILITY",
    "HARD_PLACEMENT_RULE",
)
GroupKind = Literal[
    "DEMAND",
    "CLASS_OCCUPANCY",
    "TEACHER_OCCUPANCY",
    "ROOM_OCCUPANCY",
    "HARD_RULE",
    "LOCK",
    "CLASS_AVAILABILITY",
    "TEACHER_AVAILABILITY",
    "ROOM_AVAILABILITY",
    "HARD_PLACEMENT_RULE",
]
PrecheckCode = Literal[
    "PC_EMPTY_DOMAIN",
    "PC_RESOURCE_CAPACITY",
    "PC_ROOM_CAPACITY",
    "PC_LOCK_OVERLAP",
    "PC_HARD_DAY_LOAD",
    "PC_HARD_SESSION_LOAD",
    "PC_HARD_SUBJECT_DAY",
    "PC_HARD_DAY_SPREAD",
]
ResourceKind = Literal["CLASS", "TEACHER", "ROOM", "ROOM_TYPE", "ROOM_ALL", "CLASS_SUBJECT"]
LIMITATIONS = "One conflicting subset, not the unique cause; the input may contain other conflicts."


class ExplainOptions(DomainModel):
    """Every run decision is explicit; resource guards share the solve defaults."""

    time_limit_seconds: Annotated[StrictFloat, Field(gt=0)]
    seed: Annotated[StrictInt, Field(ge=0, le=2147483647)]
    granularity: Granularity
    max_slots: PositiveInt = 10000
    max_occurrences: PositiveInt = 10000
    max_placements: PositiveInt = 100000
    max_occupancy_terms: PositiveInt = 1000000


class GroupRef(DomainModel):
    """One diagnosable condition, identified by kind and an ID taken from the input."""

    kind: GroupKind
    id: Identifier


class PrecheckProof(DomainModel):
    """A necessary counting condition that fails: ``required`` exceeds ``available``."""

    code: PrecheckCode
    rule_id: Identifier | None = None
    resource_kind: ResourceKind | None = None
    resource_ids: tuple[Identifier, ...] = ()
    occurrence_ids: tuple[Identifier, ...] = ()
    required: NonNegativeInt
    available: NonNegativeInt

    @model_validator(mode="after")
    def violated(self) -> Self:
        if self.required <= self.available:
            raise ValueError("A precheck proof needs required > available")
        return self


class WitnessCheck(DomainModel):
    """Independent validation of the schedule proving one subset member is necessary."""

    group: GroupRef
    validator_valid: StrictBool


class Evidence(DomainModel):
    """Who proved what: arithmetic proofs, or a solver claim plus validated witnesses."""

    infeasibility: Literal["ARITHMETIC", "SOLVER"]
    minimality_witnesses: tuple[WitnessCheck, ...] = ()


class ExplainMetadata(DomainModel):
    """Run facts; wall time is a measurement, not a performance promise."""

    solver_version: Identifier | None
    seed: Annotated[StrictInt, Field(ge=0, le=2147483647)]
    num_workers: Literal[1]
    time_limit_seconds: Annotated[StrictFloat, Field(gt=0)]
    wall_time: Annotated[StrictFloat, Field(ge=0)]
    solver_calls: NonNegativeInt


def _key(group: GroupRef) -> tuple[str, str]:
    return group.kind, group.id


class InfeasibilityReport(DomainModel):
    """Envelope for one diagnosis; status decides which evidence fields may be present."""

    schema_version: Literal["1.0"]
    status: ReportStatus
    input_fingerprint: Fingerprint
    granularity: Granularity
    precheck_proofs: tuple[PrecheckProof, ...] = ()
    subset: tuple[GroupRef, ...] = ()
    minimal_proved: StrictBool = False
    unresolved: tuple[GroupRef, ...] = ()
    evidence: Evidence | None = None
    metadata: ExplainMetadata
    limitations: Literal[
        "One conflicting subset, not the unique cause; the input may contain other conflicts."
    ]

    @model_validator(mode="after")
    def consistent(self) -> Self:
        subset = [_key(g) for g in self.subset]
        if len(set(subset)) != len(subset):
            raise ValueError("Duplicate subset group")
        if self.status == "PRECHECK_PROOF":
            if (
                not self.precheck_proofs
                or self.subset
                or self.unresolved
                or self.minimal_proved
                or self.evidence is None
                or self.evidence.infeasibility != "ARITHMETIC"
                or self.evidence.minimality_witnesses
            ):
                raise ValueError("A precheck report carries only arithmetic proofs")
            return self
        if self.status == "CORE_SUBSET":
            if self.precheck_proofs or not self.subset or self.evidence is None:
                raise ValueError("A core report carries a non-empty subset and evidence")
            if self.evidence.infeasibility != "SOLVER":
                raise ValueError("Subset infeasibility is a solver claim")
            members = set(subset)
            unresolved = {_key(g) for g in self.unresolved}
            witnessed = {_key(w.group) for w in self.evidence.minimality_witnesses}
            if not unresolved <= members or not witnessed <= members:
                raise ValueError("Unresolved groups and witnesses must belong to the subset")
            if self.minimal_proved and (
                unresolved
                or witnessed != members
                or not all(w.validator_valid for w in self.evidence.minimality_witnesses)
            ):
                raise ValueError("Minimality needs a validated witness for every member")
            return self
        if (
            self.precheck_proofs
            or self.subset
            or self.unresolved
            or self.minimal_proved
            or self.evidence is not None
        ):
            raise ValueError("Only infeasibility reports carry evidence")
        return self
