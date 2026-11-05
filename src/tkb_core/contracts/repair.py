"""Phase 3A repair contracts (version 1.0), separate from the solve input/output contracts.

A repair reads a new ``ScheduleInput``, a previous schedule and an explicit request, and
returns an envelope around an ordinary ``ScheduleResult`` of the existing version. These
records carry claims; ``validation.repair_evaluator`` recomputes every count independently.
"""

import hashlib
import json
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictFloat, model_validator

from tkb_core.contracts.output import ScheduleResult
from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import (
    DomainModel,
    Identifier,
    NonNegativeInt,
    PositiveInt,
    ScheduleAssignment,
)

Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ChangeOrder = Literal["BEFORE_QUALITY", "AFTER_QUALITY"]
ForcedReason = Literal["LOCK", "DOMAIN"]
# Quality outputs a repair may wrap; input 1.0 and its 1.1 output are not repairable.
REPAIRABLE_OUTPUTS = frozenset({"1.2", "1.3", "1.4", "1.5"})


def _unique(values: tuple[str, ...] | tuple[int, ...], label: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(f"Duplicate {label}")


class PreviousSchedule(DomainModel):
    """The schedule in use; a target to stay close to, never a hard constraint by itself."""

    schema_version: Literal["1.0"]
    source_input_fingerprint: Fingerprint | None = None
    assignments: tuple[ScheduleAssignment, ...]

    @model_validator(mode="after")
    def unique_occurrences(self) -> Self:
        _unique(tuple(a.occurrence_id for a in self.assignments), "previous occurrence")
        return self

    def fingerprint(self) -> str:
        """Hash canonical data; assignment and participant order do not matter."""
        data = self.model_dump(mode="json")
        data["assignments"].sort(key=lambda a: a["occurrence_id"])
        for assignment in data["assignments"]:
            assignment["class_ids"].sort()
            assignment["teacher_ids"].sort()
        payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def from_result(cls, result: ScheduleResult) -> "PreviousSchedule":
        """Accept only an independently validated schedule as a previous schedule."""
        if not result.valid_schedule or result.schema_version not in (
            "1.1",
            *sorted(REPAIRABLE_OUTPUTS),
        ):
            raise ValueError("Previous result must be a valid schedule (output 1.1-1.5)")
        return cls(
            schema_version="1.0",
            source_input_fingerprint=result.input_fingerprint,
            assignments=result.assignments,
        )


class ChangeScope(DomainModel):
    """Occurrences matching any listed criterion may move; other matched ones stay put."""

    class_ids: tuple[Identifier, ...] = ()
    teacher_ids: tuple[Identifier, ...] = ()
    subject_ids: tuple[Identifier, ...] = ()
    days: tuple[PositiveInt, ...] = ()

    @model_validator(mode="after")
    def non_empty(self) -> Self:
        if not (self.class_ids or self.teacher_ids or self.subject_ids or self.days):
            raise ValueError("A change scope needs at least one criterion")
        for label in ("class_ids", "teacher_ids", "subject_ids", "days"):
            _unique(getattr(self, label), label)
        return self


class RepairRequest(DomainModel):
    """Every decision is required: there is no implicit repair default."""

    schema_version: Literal["1.0"]
    change_order: ChangeOrder
    max_changes: NonNegativeInt | None
    change_scope: ChangeScope | None
    use_previous_as_hint: StrictBool


class RepairChange(DomainModel):
    """One matched occurrence whose (slot, room) differs from the previous schedule."""

    occurrence_id: Identifier
    previous_slot_id: Identifier
    previous_room_id: Identifier | None
    slot_id: Identifier
    room_id: Identifier | None
    forced: ForcedReason | None = None

    @property
    def slot_changed(self) -> bool:
        return self.slot_id != self.previous_slot_id

    @model_validator(mode="after")
    def differs(self) -> Self:
        if (self.slot_id, self.room_id) == (self.previous_slot_id, self.previous_room_id):
            raise ValueError("An unchanged occurrence is not a change")
        return self


class ChangeStage(DomainModel):
    """Evidence of the change-minimization solve; not part of the P1-P3 proof prefix."""

    raw_status: SolveStatus = SolveStatus.NOT_RUN
    incumbent_value: NonNegativeInt | None = None
    best_bound: StrictFloat | None = None
    wall_time: Annotated[StrictFloat, Field(ge=0)] | None = None
    proved_optimal: StrictBool = False

    @model_validator(mode="after")
    def evidence(self) -> Self:
        if self.proved_optimal and (
            self.raw_status != SolveStatus.OPTIMAL or self.incumbent_value is None
        ):
            raise ValueError("Optimality requires exact stage evidence")
        if self.raw_status == SolveStatus.NOT_RUN and (
            self.wall_time is not None
            or self.best_bound is not None
            or self.incumbent_value is not None
        ):
            raise ValueError("Unexecuted stage cannot claim measurements")
        return self


class RepairReport(DomainModel):
    """Counts in the unit of one occurrence; every count is recomputable independently."""

    change_order: ChangeOrder
    max_changes: NonNegativeInt | None
    change_scope: ChangeScope | None
    matched: NonNegativeInt
    new: NonNegativeInt
    dropped: NonNegativeInt
    changed: NonNegativeInt
    slot_changes: NonNegativeInt
    room_only_changes: NonNegativeInt
    unchanged: NonNegativeInt
    frozen: NonNegativeInt
    forced: NonNegativeInt
    changes: tuple[RepairChange, ...]
    new_occurrence_ids: tuple[Identifier, ...]
    dropped_occurrence_ids: tuple[Identifier, ...]
    change_stage: ChangeStage
    min_changes_proved: StrictBool

    @model_validator(mode="after")
    def arithmetic(self) -> Self:
        _unique(tuple(c.occurrence_id for c in self.changes), "changed occurrence")
        _unique(self.new_occurrence_ids, "new occurrence")
        _unique(self.dropped_occurrence_ids, "dropped occurrence")
        slot = sum(c.slot_changed for c in self.changes)
        if (
            self.changed != len(self.changes)
            or self.slot_changes != slot
            or self.room_only_changes != self.changed - slot
            or self.unchanged + self.changed != self.matched
            or self.forced != sum(c.forced is not None for c in self.changes)
            or self.new != len(self.new_occurrence_ids)
            or self.dropped != len(self.dropped_occurrence_ids)
            or self.frozen > self.matched
        ):
            raise ValueError("Repair counts are inconsistent")
        if self.max_changes is not None and self.changed > self.max_changes:
            raise ValueError("Changes exceed the declared maximum")
        stage = self.change_stage
        if stage.incumbent_value is not None and stage.incumbent_value != self.changed:
            raise ValueError("Change stage value differs from the reported schedule")
        if self.min_changes_proved != stage.proved_optimal:
            raise ValueError("Minimality claim requires a proved change stage")
        return self


class RepairResult(DomainModel):
    """Envelope: an existing-version ScheduleResult plus the repair evidence."""

    schema_version: Literal["1.0"] = "1.0"
    result: ScheduleResult
    # Null only when the previous schedule or request itself failed revalidation.
    previous_fingerprint: Fingerprint | None
    previous_source_input_fingerprint: Fingerprint | None
    previous_assignment_count: NonNegativeInt
    request: RepairRequest | None
    repair: RepairReport | None

    @model_validator(mode="after")
    def consistent(self) -> Self:
        if self.result.valid_schedule != (self.repair is not None):
            raise ValueError("A repair report exists exactly for a valid schedule")
        if self.repair is not None:
            if self.previous_fingerprint is None or self.request is None:
                raise ValueError("A repaired schedule requires its previous schedule and request")
            if self.result.schema_version not in REPAIRABLE_OUTPUTS:
                raise ValueError("Repair wraps quality outputs 1.2-1.5 only")
            if self.repair.matched + self.repair.dropped != self.previous_assignment_count:
                raise ValueError("Matched and dropped must cover the previous schedule")
            if (
                self.repair.change_order != self.request.change_order
                or self.repair.max_changes != self.request.max_changes
                or self.repair.change_scope != self.request.change_scope
            ):
                raise ValueError("Report parameters differ from the request")
        return self
