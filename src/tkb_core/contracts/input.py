"""Input schema 1.0, structural cross-reference checks and canonical fingerprint."""

import hashlib
import json
from collections.abc import Iterable, Sequence
from typing import Literal, Self

from pydantic import StrictBool, model_validator

from tkb_core.domain.models import (
    ClassGroup,
    ConstraintConfig,
    DomainModel,
    Entity,
    LockedAssignment,
    Room,
    SchoolContext,
    Subject,
    Teacher,
    TeachingRequirement,
    TimeSlot,
)


def _unique(values: Iterable[str], label: str) -> set[str]:
    items = tuple(values)
    if len(set(items)) != len(items):
        raise ValueError(f"Duplicate {label}")
    return set(items)


def _references(values: Iterable[str], known: set[str], label: str) -> None:
    ids = _unique(values, label)
    if ids - known:
        raise ValueError(f"Unknown {label} reference")


class ScheduleInput(DomainModel):
    """Domain contract, independent of vnEdu responses, storage and solver libraries."""

    schema_version: Literal["1.0"]
    school: SchoolContext
    time_slots: tuple[TimeSlot, ...]
    classes: tuple[ClassGroup, ...]
    teachers: tuple[Teacher, ...]
    subjects: tuple[Subject, ...]
    rooms: tuple[Room, ...] = ()
    teaching_requirements: tuple[TeachingRequirement, ...]
    locked_assignments: tuple[LockedAssignment, ...] = ()
    constraint_config: ConstraintConfig = ConstraintConfig()
    manage_rooms: StrictBool = False

    @model_validator(mode="after")
    def check_references(self) -> Self:
        collections: dict[str, Sequence[Entity]] = {
            "slot": self.time_slots,
            "class": self.classes,
            "teacher": self.teachers,
            "subject": self.subjects,
            "room": self.rooms,
            "requirement": self.teaching_requirements,
        }
        ids = {
            kind: _unique((record.id for record in records), kind)
            for kind, records in collections.items()
        }
        coordinates = [(s.day, s.session, s.period) for s in self.time_slots]
        if len(set(coordinates)) != len(coordinates):
            raise ValueError("Duplicate slot coordinates")
        for resource in (*self.classes, *self.teachers, *self.rooms):
            if resource.available_slot_ids is not None:
                _references(resource.available_slot_ids, ids["slot"], "availability slot")
        for requirement in self.teaching_requirements:
            _references(requirement.class_ids, ids["class"], "class")
            _references(requirement.teacher_ids, ids["teacher"], "teacher")
            _references((requirement.subject_id,), ids["subject"], "subject")
            if requirement.room_required and not self.manage_rooms:
                raise ValueError("room_required requires manage_rooms=true")
        for rule in (*self.constraint_config.hard, *self.constraint_config.soft):
            _references(rule.scope.class_ids, ids["class"], "rule class")
            _references(rule.scope.teacher_ids, ids["teacher"], "rule teacher")
            _references(rule.scope.subject_ids, ids["subject"], "rule subject")
            _references(rule.scope.room_ids, ids["room"], "rule room")
        requirements = {r.id: r for r in self.teaching_requirements}
        _unique((lock.occurrence_id for lock in self.locked_assignments), "occurrence lock")
        for lock in self.locked_assignments:
            requirement_id, separator, ordinal = lock.occurrence_id.rpartition("::")
            locked_requirement = requirements.get(requirement_id)
            if (
                not separator
                or locked_requirement is None
                or not ordinal.isascii()
                or not ordinal.isdecimal()
            ):
                raise ValueError("Unknown lock occurrence")
            index = int(ordinal)
            if str(index) != ordinal or not 1 <= index <= locked_requirement.occurrence_count:
                raise ValueError("Unknown lock occurrence ordinal")
            if lock.slot_id is not None:
                _references((lock.slot_id,), ids["slot"], "lock slot")
            if lock.room_id is not None:
                _references((lock.room_id,), ids["room"], "lock room")
                if not self.manage_rooms:
                    raise ValueError("room lock requires manage_rooms=true")
        return self

    def fingerprint(self) -> str:
        """Hash canonical v1 data; do not cache because models are caller-mutable."""
        data = self.model_dump(mode="json")
        for name in (
            "time_slots",
            "classes",
            "teachers",
            "subjects",
            "rooms",
            "teaching_requirements",
        ):
            data[name].sort(key=lambda item: item["id"])
        data["locked_assignments"].sort(key=lambda item: item["occurrence_id"])
        for name in ("classes", "teachers", "rooms"):
            for resource in data[name]:
                if resource["available_slot_ids"] is not None:
                    resource["available_slot_ids"].sort()
        for requirement in data["teaching_requirements"]:
            requirement["class_ids"].sort()
            requirement["teacher_ids"].sort()
        for kind in ("hard", "soft"):
            for rule in data["constraint_config"][kind]:
                for resource in ("class_ids", "teacher_ids", "subject_ids", "room_ids"):
                    rule["scope"][resource].sort()
        payload = json.dumps(
            data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
