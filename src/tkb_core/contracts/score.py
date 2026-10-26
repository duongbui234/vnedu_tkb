"""Pure-data scores and stage evidence; never a substitute for recomputation."""

from typing import Annotated, Literal, Self

from pydantic import Field, StrictFloat, StrictInt, model_validator

from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import Diagnostic, DomainModel, Identifier, NonNegativeInt, PositiveInt

Priority = Annotated[StrictInt, Field(ge=1, le=3)]
Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class RuleScore(DomainModel):
    rule_id: Identifier
    code: Identifier
    priority: Priority
    weight: PositiveInt
    unit: Literal["teaching_periods"] = "teaching_periods"
    raw_penalty: NonNegativeInt
    weighted_penalty: NonNegativeInt

    @model_validator(mode="after")
    def arithmetic(self) -> Self:
        if self.weighted_penalty != self.raw_penalty * self.weight:
            raise ValueError("Weighted score mismatch")
        return self


class ScoreReport(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal[
        "OK", "INPUT_INVALID", "UNSUPPORTED_FEATURE", "INVALID_SCHEDULE", "INTERNAL_ERROR"
    ]
    input_fingerprint: Fingerprint | None = None
    diagnostics: tuple[Diagnostic, ...] = ()
    rules: tuple[RuleScore, ...] = ()
    tiers: tuple[NonNegativeInt, NonNegativeInt, NonNegativeInt] | None = None

    @model_validator(mode="after")
    def arithmetic(self) -> Self:
        if self.status == "OK":
            totals = tuple(
                sum(r.weighted_penalty for r in self.rules if r.priority == p) for p in (1, 2, 3)
            )
            if self.input_fingerprint is None or self.tiers != totals or self.diagnostics:
                raise ValueError("Successful score requires exact totals and fingerprint")
            if len({r.rule_id for r in self.rules}) != len(self.rules):
                raise ValueError("Duplicate score row")
        elif self.rules or self.tiers is not None:
            raise ValueError("Errors cannot expose partial scores")
        return self


class StageRun(DomainModel):
    priority: Priority | None = None
    raw_status: SolveStatus = SolveStatus.NOT_RUN
    incumbent_value: NonNegativeInt | None = None
    best_bound: StrictFloat | None = None
    wall_time: Annotated[StrictFloat, Field(ge=0)] | None = None
    proved_optimal: bool = False

    @model_validator(mode="after")
    def evidence(self) -> Self:
        if self.proved_optimal and (
            self.raw_status != SolveStatus.OPTIMAL or self.incumbent_value is None
        ):
            raise ValueError("Optimality requires exact stage evidence")
        if self.raw_status == SolveStatus.NOT_RUN and (
            self.wall_time is not None or self.best_bound is not None or self.proved_optimal
        ):
            raise ValueError("Unexecuted stage cannot claim measurements")
        if self.priority is None and (
            self.best_bound is not None or self.incumbent_value is not None or self.proved_optimal
        ):
            raise ValueError("Feasibility has no quality objective")
        return self


class QualityReport(DomainModel):
    policy_version: Literal["0.1"] = "0.1"
    status: Literal["NOT_REQUESTED", "NOT_EVALUATED", "SCORED_FEASIBLE", "LEXICOGRAPHIC_OPTIMAL"]
    score: ScoreReport | None = None
    optimal_prefix: tuple[Priority, ...] = ()
    tier_runs: tuple[StageRun, ...] = ()

    @model_validator(mode="after")
    def evidence(self) -> Self:
        active = [r.priority for r in self.tier_runs]
        if None in active or active != sorted(set(active)):
            raise ValueError("Tiers must be unique and ordered")
        prefix = tuple(r.priority for r in self.tier_runs[: len(self.optimal_prefix)])
        if self.optimal_prefix != prefix or any(
            not r.proved_optimal for r in self.tier_runs[: len(prefix)]
        ):
            raise ValueError("Invalid proof prefix")
        if any(r.proved_optimal for r in self.tier_runs[len(prefix) :]):
            raise ValueError("Optimal proof cannot skip a tier")
        if self.status in ("SCORED_FEASIBLE", "LEXICOGRAPHIC_OPTIMAL"):
            if self.score is None or self.score.status != "OK":
                raise ValueError("Scored quality requires successful evaluation")
        if self.status == "LEXICOGRAPHIC_OPTIMAL" and (not active or len(prefix) != len(active)):
            raise ValueError("Every active tier requires proof")
        if self.status == "NOT_EVALUATED" and self.score is not None:
            raise ValueError("No score before evaluation")
        if self.status == "NOT_REQUESTED" and (active or prefix):
            raise ValueError("No proof without preferences")
        return self
