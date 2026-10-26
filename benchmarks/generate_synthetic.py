"""Construct and verify synthetic Phase 2A artifacts without running a solver."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import Field, StrictBool, StrictStr, model_validator

import tkb_core
from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.score import ScoreReport
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import (
    ClassGroup,
    ConstraintConfigV11,
    DomainModel,
    LockedAssignment,
    NonNegativeInt,
    Room,
    ScheduleAssignment,
    SchoolContext,
    SoftConstraintConfigV11,
    Subject,
    Teacher,
    TeachingRequirement,
    TimeSlot,
)
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score

SIZES = (10, 20, 40)
PROFILES: tuple[Literal["BASE", "MIXED", "TIGHT", "UNSAT_CAPACITY"], ...] = (
    "BASE",
    "MIXED",
    "TIGHT",
    "UNSAT_CAPACITY",
)
SEEDS = (101, 102, 103)
SPLITS = (
    (2, 1, 1),
    (2, 1, 1),
    (1, 1, 1, 1),
    (1, 1, 1, 1),
    (1, 1, 1, 1),
    (2, 1),
    (2, 1),
    (1, 1),
    (1, 1),
)
Profile = Literal["BASE", "MIXED", "TIGHT", "UNSAT_CAPACITY"]
SHA = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
ROOT = Path(__file__).resolve().parents[1]
Token = tuple[str, str, str]


class DatasetGenerationError(ValueError):
    """Input, witness or manifest failed protocol verification; never a solver result."""


class Construction(DomainModel):
    method: Literal["template-and-resource-safe-swaps-v1"] = "template-and-resource-safe-swaps-v1"
    seed: NonNegativeInt
    swap_attempts: NonNegativeInt
    swap_successes: NonNegativeInt

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.swap_successes > self.swap_attempts:
            raise ValueError("Swap successes exceed attempts")
        return self


class WitnessArtifact(DomainModel):
    benchmark_schema_version: Literal["1.0"] = "1.0"
    role: Literal["FEASIBLE_BASELINE", "PROVENANCE_ONLY"]
    input_fingerprint: SHA
    assignments: tuple[ScheduleAssignment, ...]
    construction: Construction


class CapacityProof(DomainModel):
    class_id: StrictStr
    demand_periods: NonNegativeInt
    available_periods: NonNegativeInt


class Dimensions(DomainModel):
    classes: NonNegativeInt
    teachers: NonNegativeInt
    subjects: NonNegativeInt
    rooms: NonNegativeInt
    slots: NonNegativeInt
    requirements: NonNegativeInt
    periods: NonNegativeInt
    occurrences: NonNegativeInt
    placements: NonNegativeInt | None
    occupancy_terms: NonNegativeInt | None
    slot_tokens: NonNegativeInt | None
    precheck_status: Literal["READY", "INFEASIBLE"]
    precheck_code: str | None = None
    room_required_requirements: NonNegativeInt
    room_occurrences: NonNegativeInt
    room_periods: NonNegativeInt
    locked_occurrences: NonNegativeInt
    locks_with_room: NonNegativeInt
    teacher_loads: dict[str, NonNegativeInt]
    teacher_available_slots: dict[str, NonNegativeInt]
    class_available_slots: dict[str, NonNegativeInt]


class DatasetManifest(DomainModel):
    benchmark_schema_version: Literal["1.0"] = "1.0"
    dataset_id: StrictStr
    class_count: Literal[10, 20, 40]
    profile: Profile
    seed: NonNegativeInt
    input_fingerprint: SHA
    ground_truth: Literal["FEASIBLE", "INFEASIBLE"]
    known_optimum: tuple[NonNegativeInt, NonNegativeInt, NonNegativeInt] | None
    baseline_score: ScoreReport | None
    p2_lower_bound: NonNegativeInt | None
    capacity_proof: CapacityProof | None
    dimensions: Dimensions
    sources: dict[str, SHA]
    files: dict[str, SHA]


class BundleEntry(DomainModel):
    dataset_id: StrictStr
    manifest_sha256: SHA


class SourceRevision(DomainModel):
    repository_head: Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{40,64}$")] | None
    generator_matches_head: StrictBool


class BundleManifest(DomainModel):
    benchmark_schema_version: Literal["1.0"] = "1.0"
    protocol: Literal["phase2a-operational-v1"] = "phase2a-operational-v1"
    revision: SourceRevision
    datasets: tuple[BundleEntry, ...]


@dataclass(frozen=True)
class GeneratedDataset:
    problem: ScheduleInput
    witness: WitnessArtifact | None
    provenance_problem: ScheduleInput | None
    provenance_witness: WitnessArtifact | None
    manifest: DatasetManifest


def _json_bytes(value: DomainModel) -> bytes:
    return (
        json.dumps(
            value.model_dump(mode="json"),
            sort_keys=True,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sources() -> dict[str, str]:
    # Normalize source newlines, not artifact bytes, for cross-platform source identity.
    if tkb_core.__file__ is None:
        raise DatasetGenerationError("Imported Core has no inspectable source identity")
    core_root = Path(tkb_core.__file__).resolve().parent
    core = [
        (
            str(p.relative_to(core_root.parent)).replace("\\", "/"),
            _sha(p.read_bytes().replace(b"\r\n", b"\n")),
        )
        for p in sorted(core_root.rglob("*.py"))
    ]
    return {
        "generator_source_sha256": _sha(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "core_source_sha256": _sha(json.dumps(core, separators=(",", ":")).encode()),
        "uv_lock_sha256": _sha((ROOT / "uv.lock").read_bytes().replace(b"\r\n", b"\n")),
    }


def _id(size: int, profile: str, seed: int) -> str:
    return f"c{size:02}-{profile.lower()}-s{seed}"


def _slot(day: int, session: str, period: int) -> str:
    return f"d{day:02}-{session.lower()}-p{period:02}"


def _footprint(problem: ScheduleInput, assignment: ScheduleAssignment) -> tuple[str, ...]:
    rid, _, ordinal = assignment.occurrence_id.rpartition("::")
    req = next(r for r in problem.teaching_requirements if r.id == rid)
    duration = req.block_durations[int(ordinal) - 1] if req.block_durations is not None else 1
    start = next(s for s in problem.time_slots if s.id == assignment.slot_id)
    return tuple(_slot(start.day, start.session, start.period + i) for i in range(duration))


def _tokens(problem: ScheduleInput, assignment: ScheduleAssignment) -> set[Token]:
    actors = [("class", assignment.class_ids[0]), ("teacher", assignment.teacher_ids[0])]
    if assignment.room_id is not None:
        actors.append(("room", assignment.room_id))
    return {
        (kind, actor, slot) for kind, actor in actors for slot in _footprint(problem, assignment)
    }


def _construct(
    size: int, timed: bool, seed: int
) -> tuple[ScheduleInput, tuple[ScheduleAssignment, ...], Construction]:
    rng = random.Random(seed)
    teachers = size * 3 // 2
    slots = []
    for day in range(1, 7):
        for session, begin in (("AM", 420), ("PM", 780)):
            for period in range(1, 6):
                start = (day - 1) * 1440 + begin + (period - 1) * 45
                slots.append(
                    TimeSlot(
                        id=_slot(day, session, period),
                        day=day,
                        session=session,
                        period=period,
                        start_minute=start if timed else None,
                        end_minute=start + 45 if timed else None,
                    )
                )
    components = [
        (subject, ordinal, duration)
        for subject, split in enumerate(SPLITS)
        for ordinal, duration in enumerate(split, 1)
    ]
    sessions = [(day, session) for day in range(1, 7) for session in ("AM", "PM")]
    rng.shuffle(sessions)
    template = {}
    used: set[str] = set()
    doubles = [c for c in components if c[2] == 2]
    for (subject, ordinal, _), (day, session) in zip(doubles, sessions, strict=False):
        period = rng.choice((2, 3))
        template[subject, ordinal] = _slot(day, session, period)
        used.update((_slot(day, session, period), _slot(day, session, period + 1)))
    singles = [s.id for s in slots if s.period in (2, 3, 4) and s.id not in used]
    rng.shuffle(singles)
    for (subject, ordinal, _), slot in zip(
        (c for c in components if c[2] == 1), singles, strict=False
    ):
        template[subject, ordinal] = slot
    room_enabled = timed
    reqs = []
    assignments = []
    rooms = (
        [
            Room(id=f"R{zone:02}-{j}", room_type=f"lab-{zone:02}", capacity=40)
            for zone in range(size // 10)
            for j in (1, 2)
        ]
        if room_enabled
        else []
    )
    problem = ScheduleInput(
        schema_version="1.1",
        school=SchoolContext(
            school_id="synthetic-school", academic_year="synthetic-cycle", term="demo"
        ),
        time_slots=tuple(slots),
        classes=tuple(ClassGroup(id=f"C{i + 1:03}", size=32) for i in range(size)),
        teachers=tuple(Teacher(id=f"T{i + 1:03}") for i in range(teachers)),
        subjects=tuple(Subject(id=f"SUB{i + 1:02}") for i in range(9)),
        rooms=tuple(rooms),
        teaching_requirements=(),
        manage_rooms=room_enabled,
        constraint_config=ConstraintConfigV11(policy_version="0.1"),
    )
    for i in range(size):
        for subject, split in enumerate(SPLITS):
            teacher = f"T{(i + subject * teachers // 9) % teachers + 1:03}"
            room_required = room_enabled and subject == i % 9
            req = TeachingRequirement(
                id=f"REQ-C{i + 1:03}-S{subject + 1:02}",
                class_ids=(f"C{i + 1:03}",),
                teacher_ids=(teacher,),
                subject_id=f"SUB{subject + 1:02}",
                periods_per_cycle=sum(split),
                block_durations=split,
                room_required=room_required,
                required_room_type=f"lab-{i // 10:02}" if room_required else None,
            )
            reqs.append(req)
            for ordinal, _ in enumerate(split, 1):
                assignments.append(
                    ScheduleAssignment(
                        occurrence_id=f"{req.id}::{ordinal}",
                        slot_id=template[subject, ordinal],
                        class_ids=req.class_ids,
                        teacher_ids=req.teacher_ids,
                    )
                )
    problem.teaching_requirements = tuple(reqs)
    occupied: dict[Token, str] = {}
    for index, a in enumerate(assignments):
        req = next(r for r in reqs if a.occurrence_id.rpartition("::")[0] == r.id)
        if req.room_required:
            for room in rooms:
                if room.room_type != req.required_room_type:
                    continue
                candidate = a.model_copy(update={"room_id": room.id})
                if not _tokens(problem, candidate) & occupied.keys():
                    a = candidate
                    break
            else:
                raise DatasetGenerationError("DATASET_GENERATION_FAILED: no witness room")
            assignments[index] = a
        tokens = _tokens(problem, a)
        if tokens & occupied.keys():
            raise DatasetGenerationError("DATASET_GENERATION_FAILED: initial resource collision")
        occupied.update(dict.fromkeys(tokens, a.occurrence_id))
    by_duration: dict[int, list[int]] = defaultdict(list)
    for index, a in enumerate(assignments):
        by_duration[len(_footprint(problem, a))].append(index)
    successes = 0
    for _ in range(5 * size):
        left = rng.randrange(len(assignments))
        a = assignments[left]
        pool = by_duration[len(_footprint(problem, a))]
        if rng.randrange(2) == 0:
            pool = [idx for idx in pool if assignments[idx].class_ids == a.class_ids]
        right = rng.choice(pool)
        b = assignments[right]
        if left == right or a.slot_id == b.slot_id:
            continue
        before_a, before_b = _tokens(problem, a), _tokens(problem, b)
        for token in before_a | before_b:
            del occupied[token]
        new_a = a.model_copy(update={"slot_id": b.slot_id})
        new_b = b.model_copy(update={"slot_id": a.slot_id})
        after_a, after_b = _tokens(problem, new_a), _tokens(problem, new_b)
        if not (after_a & after_b or (after_a | after_b) & occupied.keys()):
            assignments[left], assignments[right] = new_a, new_b
            occupied.update(dict.fromkeys(after_a, new_a.occurrence_id))
            occupied.update(dict.fromkeys(after_b, new_b.occurrence_id))
            successes += 1
        else:
            occupied.update(dict.fromkeys(before_a, a.occurrence_id))
            occupied.update(dict.fromkeys(before_b, b.occurrence_id))
    return (
        problem,
        tuple(assignments),
        Construction(seed=seed, swap_attempts=5 * size, swap_successes=successes),
    )


def _configure(
    problem: ScheduleInput, assignments: tuple[ScheduleAssignment, ...], profile: str, seed: int
) -> None:
    rng = random.Random(seed + 1000)
    all_slots = {s.id for s in problem.time_slots}
    slots = {s.id: s for s in problem.time_slots}
    teacher_slots: dict[str, set[str]] = defaultdict(set)
    class_slots: dict[str, set[str]] = defaultdict(set)
    sessions: Counter[tuple[str, int, str]] = Counter()
    days: Counter[tuple[str, int]] = Counter()
    for a in assignments:
        for sid in _footprint(problem, a):
            teacher_slots[a.teacher_ids[0]].add(sid)
            class_slots[a.class_ids[0]].add(sid)
            s = slots[sid]
            sessions[a.teacher_ids[0], s.day, s.session] += 1
            days[a.teacher_ids[0], s.day] += 1

    def availability(used: set[str], target: int) -> tuple[str, ...]:
        return tuple(sorted(used | set(rng.sample(sorted(all_slots - used), target - len(used)))))

    if profile in ("MIXED", "TIGHT"):
        for c in problem.classes:
            c.available_slot_ids = availability(class_slots[c.id], 42 if profile == "MIXED" else 32)
        for t in problem.teachers:
            used = teacher_slots[t.id]
            t.available_slot_ids = availability(
                used, max(36, len(used) + 6) if profile == "MIXED" else len(used) + 2
            )
        count = len(assignments) // (10 if profile == "MIXED" else 5)
        room_first = rng.choice([a for a in assignments if a.room_id is not None])
        selected = [
            room_first,
            *rng.sample(
                [a for a in assignments if a.occurrence_id != room_first.occurrence_id], count - 1
            ),
        ]
        problem.locked_assignments = tuple(
            sorted(
                (
                    LockedAssignment(
                        occurrence_id=a.occurrence_id,
                        slot_id=a.slot_id,
                        room_id=a.room_id if a.occurrence_id == room_first.occurrence_id else None,
                    )
                    for a in selected
                ),
                key=lambda lock: lock.occurrence_id,
            )
        )
    rules = []
    for teacher in problem.teachers:
        available = (
            set(teacher.available_slot_ids) if teacher.available_slot_ids is not None else all_slots
        )
        avoid = sorted(rng.sample(sorted(available - teacher_slots[teacher.id]), 2))
        max_session = max((n for (t, _, _), n in sessions.items() if t == teacher.id), default=0)
        max_day = max((n for (t, _), n in days.items() if t == teacher.id), default=0)
        total = len(teacher_slots[teacher.id])
        day_limit = max(0, (total + 5) // 6 - 1) if profile == "TIGHT" else max_day
        for code, priority, parameters in (
            ("TEACHER_AVOID_SLOTS", 1, {"slot_ids": avoid}),
            (
                "TEACHER_MAX_PERIODS_PER_SESSION",
                1,
                {"limit": max_session, "session_ids": ["AM", "PM"]},
            ),
            ("TEACHER_MAX_PERIODS_PER_DAY", 2, {"limit": day_limit}),
            (
                "TEACHER_PREFERRED_PERIOD_WINDOW",
                3,
                {"first_period": 2, "last_period": 4, "session_ids": ["AM", "PM"]},
            ),
        ):
            rules.append(
                SoftConstraintConfigV11(
                    id=f"{code}-{teacher.id}",
                    code=code,
                    priority=priority,
                    weight=1,
                    parameters=parameters,
                    scope={"teacher_ids": (teacher.id,)},
                )
            )
    problem.constraint_config = ConstraintConfigV11(policy_version="0.1", soft=tuple(rules))


def _dimensions(problem: ScheduleInput, infeasible: bool) -> Dimensions:
    code: str | None
    try:
        prepared = prepare(problem)
    except CoreError as exc:
        if not infeasible or exc.status.value != "INFEASIBLE":
            raise DatasetGenerationError(
                "DATASET_GENERATION_FAILED: preparation rejected dataset"
            ) from exc
        placements = terms = tokens = None
        code = exc.diagnostics[0].code
    else:
        if infeasible:
            raise DatasetGenerationError("Capacity case was not rejected by precheck")
        placements = sum(len(v) for v in prepared.domains.values())
        terms = sum(
            len(p.tokens) * (2 + int(p.room_id is not None))
            for values in prepared.domains.values()
            for p in values
        )
        tokens = len({t for values in prepared.normalized.slot_tokens.values() for t in values})
        code = None
    room_reqs = [r for r in problem.teaching_requirements if r.room_required]
    return Dimensions(
        classes=len(problem.classes),
        teachers=len(problem.teachers),
        subjects=len(problem.subjects),
        rooms=len(problem.rooms),
        slots=len(problem.time_slots),
        requirements=len(problem.teaching_requirements),
        periods=sum(r.periods_per_cycle for r in problem.teaching_requirements),
        occurrences=sum(r.occurrence_count for r in problem.teaching_requirements),
        placements=placements,
        occupancy_terms=terms,
        slot_tokens=tokens,
        precheck_status="INFEASIBLE" if infeasible else "READY",
        precheck_code=code,
        room_required_requirements=len(room_reqs),
        room_occurrences=sum(r.occurrence_count for r in room_reqs),
        room_periods=sum(r.periods_per_cycle for r in room_reqs),
        locked_occurrences=len(problem.locked_assignments),
        locks_with_room=sum(lock.room_id is not None for lock in problem.locked_assignments),
        teacher_loads={
            t.id: sum(
                r.periods_per_cycle for r in problem.teaching_requirements if t.id in r.teacher_ids
            )
            for t in problem.teachers
        },
        teacher_available_slots={
            t.id: len(t.available_slot_ids)
            if t.available_slot_ids is not None
            else len(problem.time_slots)
            for t in problem.teachers
        },
        class_available_slots={
            c.id: len(c.available_slot_ids)
            if c.available_slot_ids is not None
            else len(problem.time_slots)
            for c in problem.classes
        },
    )


def _files(
    problem: ScheduleInput,
    witness: WitnessArtifact | None,
    provenance_problem: ScheduleInput | None,
    provenance_witness: WitnessArtifact | None,
) -> dict[str, bytes]:
    files = {"input.json": _json_bytes(problem)}
    if witness is not None:
        files["witness.json"] = _json_bytes(witness)
    if provenance_problem is not None:
        files["provenance-input.json"] = _json_bytes(provenance_problem)
    if provenance_witness is not None:
        files["provenance-witness.json"] = _json_bytes(provenance_witness)
    return files


def _check_protocol(problem: ScheduleInput, size: int, profile: Profile) -> None:
    expected = {
        (day, session, period)
        for day in range(1, 7)
        for session in ("AM", "PM")
        for period in range(1, 6)
    }
    if {(slot.day, slot.session, slot.period) for slot in problem.time_slots} != expected:
        raise DatasetGenerationError("Calendar differs from six-day protocol")
    timed = profile in ("MIXED", "TIGHT")
    for slot in problem.time_slots:
        start = (
            (slot.day - 1) * 1440 + (420 if slot.session == "AM" else 780) + (slot.period - 1) * 45
        )
        if not slot.can_teach or (slot.start_minute, slot.end_minute) != (
            (start, start + 45) if timed else (None, None)
        ):
            raise DatasetGenerationError("Calendar minutes/mode differ from protocol")
    if len(problem.subjects) != 9 or len(problem.teaching_requirements) != 9 * size:
        raise DatasetGenerationError("Requirement/subject count differs from protocol")
    for group in problem.classes:
        requirements = [r for r in problem.teaching_requirements if group.id in r.class_ids]
        if len({r.subject_id for r in requirements}) != 9 or sorted(
            r.block_durations for r in requirements if r.block_durations is not None
        ) != sorted(SPLITS):
            raise DatasetGenerationError("Class demand/split differs from protocol")
        if sum(r.room_required for r in requirements) != int(timed):
            raise DatasetGenerationError("Room scope differs from protocol")
        if timed and len(group.available_slot_ids or ()) != (42 if profile == "MIXED" else 32):
            raise DatasetGenerationError("Class availability differs from profile")
    expected_locks = size * 26 // (10 if profile == "MIXED" else 5) if timed else 0
    if (
        problem.manage_rooms != timed
        or len(problem.rooms) != (size // 5 if timed else 0)
        or len(problem.locked_assignments) != expected_locks
    ):
        raise DatasetGenerationError("Rooms/locks differ from profile")
    if timed and (
        not any(lock.room_id and lock.slot_id for lock in problem.locked_assignments)
        or not any(lock.slot_id and lock.room_id is None for lock in problem.locked_assignments)
    ):
        raise DatasetGenerationError("Missing time-only or time-and-room lock")
    if problem.constraint_config.hard or len(problem.constraint_config.soft) != 4 * len(
        problem.teachers
    ):
        raise DatasetGenerationError("Rule declarations differ from profile")


def _check_witness_profile(
    problem: ScheduleInput, assignments: tuple[ScheduleAssignment, ...], profile: Profile
) -> None:
    slots = {s.id: s for s in problem.time_slots}
    used: dict[str, set[str]] = defaultdict(set)
    sessions: Counter[tuple[str, int, str]] = Counter()
    days: Counter[tuple[str, int]] = Counter()
    for assignment in assignments:
        teacher_id = assignment.teacher_ids[0]
        for sid in _footprint(problem, assignment):
            used[teacher_id].add(sid)
            slot = slots[sid]
            sessions[teacher_id, slot.day, slot.session] += 1
            days[teacher_id, slot.day] += 1
    config = problem.constraint_config
    assert isinstance(config, ConstraintConfigV11)
    for teacher in problem.teachers:
        total = len(used[teacher.id])
        available = teacher.available_slot_ids
        if profile in ("MIXED", "TIGHT"):
            expected_count = max(36, total + 6) if profile == "MIXED" else total + 2
            if available is None or len(available) != expected_count:
                raise DatasetGenerationError("Teacher availability differs from profile")
        elif available is not None:
            raise DatasetGenerationError("BASE teacher availability must be unrestricted")
        maximum_session = max(
            (n for (t, _, _), n in sessions.items() if t == teacher.id), default=0
        )
        maximum_day = max((n for (t, _), n in days.items() if t == teacher.id), default=0)
        expected_parameters = {
            "TEACHER_AVOID_SLOTS": (1, None),
            "TEACHER_MAX_PERIODS_PER_SESSION": (
                1,
                {"limit": maximum_session, "session_ids": ["AM", "PM"]},
            ),
            "TEACHER_MAX_PERIODS_PER_DAY": (
                2,
                {"limit": max(0, (total + 5) // 6 - 1) if profile == "TIGHT" else maximum_day},
            ),
            "TEACHER_PREFERRED_PERIOD_WINDOW": (
                3,
                {"first_period": 2, "last_period": 4, "session_ids": ["AM", "PM"]},
            ),
        }
        rules = [r for r in config.soft if r.scope.teacher_ids == (teacher.id,)]
        if len(rules) != 4 or {r.code for r in rules} != set(expected_parameters):
            raise DatasetGenerationError("Expected exactly S01-S04 for each teacher")
        for rule in rules:
            priority, parameters = expected_parameters[rule.code]
            if (
                not rule.enabled
                or rule.weight != 1
                or rule.priority != priority
                or rule.scope.class_ids
                or rule.scope.subject_ids
                or rule.scope.room_ids
            ):
                raise DatasetGenerationError("Rule activation/scope/priority differs from profile")
            if parameters is not None:
                if rule.parameters != parameters:
                    raise DatasetGenerationError("Rule parameters differ from witness protocol")
            else:
                avoid = rule.parameters.get("slot_ids")
                allowed = set(available) if available is not None else set(slots)
                if (
                    set(rule.parameters) != {"slot_ids"}
                    or not isinstance(avoid, list)
                    or len(avoid) != 2
                    or len(set(avoid)) != 2
                    or not set(avoid) <= allowed - used[teacher.id]
                ):
                    raise DatasetGenerationError("Avoid slots must be two unused available slots")


def _manifest(
    size: int,
    profile: Profile,
    seed: int,
    problem: ScheduleInput,
    witness: WitnessArtifact | None,
    provenance_problem: ScheduleInput | None,
    provenance_witness: WitnessArtifact | None,
) -> DatasetManifest:
    problem = ScheduleInput.model_validate(problem.model_dump(warnings="error"))
    config = problem.constraint_config
    if problem.schema_version != "1.1" or not isinstance(config, ConstraintConfigV11):
        raise DatasetGenerationError("Operational profiles require input1.1/policy0.1")
    _check_protocol(problem, size, profile)
    target = provenance_problem if profile == "UNSAT_CAPACITY" else problem
    evidence = provenance_witness if profile == "UNSAT_CAPACITY" else witness
    expected_role = "PROVENANCE_ONLY" if profile == "UNSAT_CAPACITY" else "FEASIBLE_BASELINE"
    if (
        target is None
        or evidence is None
        or evidence.role != expected_role
        or evidence.construction.seed != seed
        or evidence.input_fingerprint != target.fingerprint()
    ):
        raise DatasetGenerationError("Witness role, input fingerprint or construction mismatch")
    target = ScheduleInput.model_validate(target.model_dump(warnings="error"))
    evidence = WitnessArtifact.model_validate(evidence.model_dump(warnings="error"))
    if not validate_schedule(target, evidence.assignments).valid:
        raise DatasetGenerationError("Witness fails independent hard validation")
    _check_witness_profile(
        target, evidence.assignments, "BASE" if profile == "UNSAT_CAPACITY" else profile
    )
    score = evaluate_score(target, evidence.assignments)
    if score.status != "OK":
        raise DatasetGenerationError("Witness cannot be independently scored")
    infeasible = profile == "UNSAT_CAPACITY"
    if infeasible:
        if witness is not None or problem.locked_assignments or problem.rooms:
            raise DatasetGenerationError("UNSAT cannot claim a feasible witness/locks/rooms")
        c = problem.classes[0]
        demand = sum(
            r.periods_per_cycle for r in problem.teaching_requirements if c.id in r.class_ids
        )
        available = len(c.available_slot_ids) if c.available_slot_ids is not None else 60
        if demand != 30 or available != 29:
            raise DatasetGenerationError("Invalid capacity proof")
        # Provenance and target may differ only in the declared capacity mutation.
        assert c.available_slot_ids is not None
        data = target.model_dump(mode="json")
        data["classes"][0]["available_slot_ids"] = list(c.available_slot_ids)
        if data != problem.model_dump(mode="json"):
            raise DatasetGenerationError("UNSAT mutation differs from its provenance")
        proof = CapacityProof(class_id=c.id, demand_periods=demand, available_periods=available)
        baseline = None
        lower = None
        optimum = None
    else:
        if provenance_problem is not None or provenance_witness is not None:
            raise DatasetGenerationError("Feasible case cannot contain unrelated provenance")
        proof = None
        baseline = score
        if profile in ("BASE", "MIXED"):
            if score.tiers != (0, 0, 0):
                raise DatasetGenerationError("Profile Z witness must have zero score")
            lower = 0
            optimum = (0, 0, 0)
        else:
            loads = {
                t.id: sum(
                    r.periods_per_cycle
                    for r in problem.teaching_requirements
                    if t.id in r.teacher_ids
                )
                for t in problem.teachers
            }
            lower = sum(max(0, d - 6 * max(0, (d + 5) // 6 - 1)) for d in loads.values())
            if (
                score.tiers is None
                or score.tiers[0] != 0
                or score.tiers[1] < lower
                or score.tiers[2] != 0
                or lower <= 0
            ):
                raise DatasetGenerationError("Profile C witness/lower bound mismatch")
            optimum = None
    dims = _dimensions(problem, infeasible)
    if (
        dims.classes != size
        or dims.teachers != size * 3 // 2
        or dims.periods != size * 30
        or dims.occurrences != size * 26
        or evidence.construction.swap_attempts != 5 * size
    ):
        raise DatasetGenerationError("Dataset dimensions or construction do not match protocol")
    return DatasetManifest(
        dataset_id=_id(size, profile, seed),
        class_count=size,
        profile=profile,
        seed=seed,
        input_fingerprint=problem.fingerprint(),
        ground_truth="INFEASIBLE" if infeasible else "FEASIBLE",
        known_optimum=optimum,
        baseline_score=baseline,
        p2_lower_bound=lower,
        capacity_proof=proof,
        dimensions=dims,
        sources=_sources(),
        files={
            name: _sha(data)
            for name, data in _files(
                problem, witness, provenance_problem, provenance_witness
            ).items()
        },
    )


def generate_dataset(class_count: int, profile: Profile, seed: int) -> GeneratedDataset:
    """Construct one protocol dataset; validate it without CP-SAT or retries."""
    if (
        type(class_count) is not int
        or class_count not in SIZES
        or profile not in PROFILES
        or type(seed) is not int
        or seed < 0
    ):
        raise DatasetGenerationError("Unsupported size/profile/seed")
    if profile == "UNSAT_CAPACITY":
        base = generate_dataset(class_count, "BASE", seed)
        problem = ScheduleInput.model_validate(base.problem.model_dump(mode="json"))
        problem.classes[0].available_slot_ids = tuple(s.id for s in problem.time_slots[:29])
        witness = None
        provenance_problem = base.problem
        assert base.witness is not None
        provenance_witness = base.witness.model_copy(update={"role": "PROVENANCE_ONLY"})
    else:
        problem, assignments, construction = _construct(class_count, profile != "BASE", seed)
        _configure(problem, assignments, profile, seed)
        problem = ScheduleInput.model_validate(problem.model_dump(mode="json"))
        witness = WitnessArtifact(
            role="FEASIBLE_BASELINE",
            input_fingerprint=problem.fingerprint(),
            assignments=assignments,
            construction=construction,
        )
        provenance_problem = None
        provenance_witness = None
    manifest = _manifest(
        class_count, profile, seed, problem, witness, provenance_problem, provenance_witness
    )
    return GeneratedDataset(problem, witness, provenance_problem, provenance_witness, manifest)


def validate_dataset(dataset: GeneratedDataset) -> None:
    """Recompute proof, score, dimensions and hashes; reject caller mutations."""
    try:
        declared = DatasetManifest.model_validate(dataset.manifest.model_dump(warnings="error"))
        actual = _manifest(
            declared.class_count,
            declared.profile,
            declared.seed,
            dataset.problem,
            dataset.witness,
            dataset.provenance_problem,
            dataset.provenance_witness,
        )
        if actual != declared:
            raise DatasetGenerationError("Manifest differs from verified artifacts")
    except (ValueError, TypeError, AttributeError) as exc:
        raise DatasetGenerationError(
            "DATASET_GENERATION_FAILED: artifact validation failed"
        ) from exc


def _revision() -> SourceRevision:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=False
        )
        blob = subprocess.run(
            ["git", "show", "HEAD:benchmarks/generate_synthetic.py"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
    except OSError:
        return SourceRevision(repository_head=None, generator_matches_head=False)
    return SourceRevision(
        repository_head=head.stdout.decode("ascii").strip() if head.returncode == 0 else None,
        generator_matches_head=blob.returncode == 0
        and blob.stdout.replace(b"\r\n", b"\n")
        == Path(__file__).read_bytes().replace(b"\r\n", b"\n"),
    )


def write_bundle(output: Path) -> BundleManifest:
    """Publish a new bundle with an exclusive root and commit manifest last."""
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        entries = []
        for size in SIZES:
            for profile in PROFILES:
                for seed in SEEDS:
                    artifact = generate_dataset(size, profile, seed)
                    validate_dataset(artifact)
                    dest = staging / artifact.manifest.dataset_id
                    dest.mkdir()
                    for name, data in _files(
                        artifact.problem,
                        artifact.witness,
                        artifact.provenance_problem,
                        artifact.provenance_witness,
                    ).items():
                        (dest / name).write_bytes(data)
                    data = _json_bytes(artifact.manifest)
                    (dest / "manifest.json").write_bytes(data)
                    entries.append(
                        BundleEntry(
                            dataset_id=artifact.manifest.dataset_id, manifest_sha256=_sha(data)
                        )
                    )
        manifest = BundleManifest(revision=_revision(), datasets=tuple(entries))
        (staging / "manifest.json").write_bytes(_json_bytes(manifest))
        # Exclusive mkdir, unlike rename-to-directory, cannot replace a racing empty root.
        output.mkdir()
        for child in sorted(staging.iterdir()):
            if child.name != "manifest.json":
                child.rename(output / child.name)
        (staging / "manifest.json").rename(output / "manifest.json")
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _read(base: Path, name: str) -> bytes:
    path = base / name
    if not path.resolve().is_relative_to(base.resolve()):
        raise DatasetGenerationError("Artifact path escapes its bundle")
    return path.read_bytes()


def _parse(data: bytes) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise DatasetGenerationError("Duplicate JSON key")
            result[key] = value
        return result

    def constant(value: str) -> None:
        raise DatasetGenerationError("Non-finite JSON")

    return json.loads(data, object_pairs_hook=unique, parse_constant=constant)


def verify_bundle(root: Path) -> BundleManifest:
    """Check a transported bundle with the current pinned generator/Core sources."""
    try:
        manifest = BundleManifest.model_validate(_parse(_read(root, "manifest.json")))
        expected = {_id(size, p, seed) for size in SIZES for p in PROFILES for seed in SEEDS}
        if len(manifest.datasets) != 36 or {e.dataset_id for e in manifest.datasets} != expected:
            raise DatasetGenerationError("Bundle dataset membership differs from protocol")
        for entry in manifest.datasets:
            base = root / entry.dataset_id
            if not base.resolve().is_relative_to(root.resolve()):
                raise DatasetGenerationError("Dataset path escapes bundle")
            data = _read(base, "manifest.json")
            if _sha(data) != entry.manifest_sha256:
                raise DatasetGenerationError("Dataset manifest checksum mismatch")
            item = DatasetManifest.model_validate(_parse(data))
            if item.dataset_id != entry.dataset_id:
                raise DatasetGenerationError("Dataset identity mismatch")
            names = (
                {"input.json", "provenance-input.json", "provenance-witness.json"}
                if item.profile == "UNSAT_CAPACITY"
                else {"input.json", "witness.json"}
            )
            if set(item.files) != names:
                raise DatasetGenerationError("Unexpected artifact membership")
            raw = {name: _read(base, name) for name in names}
            if any(_sha(value) != item.files[name] for name, value in raw.items()):
                raise DatasetGenerationError("Artifact checksum mismatch")
            problem = ScheduleInput.model_validate(_parse(raw["input.json"]))
            witness = (
                WitnessArtifact.model_validate(_parse(raw["witness.json"]))
                if "witness.json" in raw
                else None
            )
            provenance_problem = (
                ScheduleInput.model_validate(_parse(raw["provenance-input.json"]))
                if "provenance-input.json" in raw
                else None
            )
            provenance_witness = (
                WitnessArtifact.model_validate(_parse(raw["provenance-witness.json"]))
                if "provenance-witness.json" in raw
                else None
            )
            validate_dataset(
                GeneratedDataset(problem, witness, provenance_problem, provenance_witness, item)
            )
        return manifest
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise DatasetGenerationError(
            "DATASET_GENERATION_FAILED: bundle verification failed"
        ) from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Generate artifacts only; no runner, search, timing or RAM measurements."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = write_bundle(args.output)
    except (ValueError, OSError, CoreError) as exc:
        print(json.dumps({"status": "DATASET_GENERATION_FAILED", "error_type": type(exc).__name__}))
        return 2
    print(
        json.dumps(
            {
                "status": "DATASETS_VERIFIED",
                "datasets": len(manifest.datasets),
                "output": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
