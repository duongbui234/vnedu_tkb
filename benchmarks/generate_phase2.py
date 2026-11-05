"""Construct and verify policy 0.4 datasets for the Phase 2 Linux plan v2; never solves.

Reuses the frozen Phase 2A witness construction by import only, so the v1 generator and
its recorded source hash stay unchanged. Run as ``python -m benchmarks.generate_phase2``.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import PositiveInt

from benchmarks import generate_synthetic as v1
from benchmarks.generate_synthetic import (
    SHA,
    BundleEntry,
    CapacityProof,
    DatasetGenerationError,
    Dimensions,
    Profile,
    SourceRevision,
    WitnessArtifact,
)
from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.score import ScoreReport
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import (
    ConstraintConfigV11,
    DomainModel,
    HardConstraintConfigV11,
    NonNegativeInt,
    OccupiedWork,
    ScheduleAssignment,
    SoftConstraintConfigV11,
)
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score

__all__ = [
    "DatasetGenerationError",
    "generate_dataset",
    "validate_dataset",
    "verify_bundle",
    "write_bundle",
]

PROTOCOL = "phase2-linux-v2"
SIZES = v1.SIZES
PROFILES = v1.PROFILES
SEEDS = v1.SEEDS
VARIANTS: tuple[Literal["SOFT", "HARD"], ...] = ("SOFT", "HARD")
Variant = Literal["SOFT", "HARD"]
ROOT = v1.ROOT

# G3: benchmark priorities, not a school policy.
SOFT_PRIORITY = {
    "TEACHER_AVOID_SLOTS": 1,
    "TEACHER_MAX_PERIODS_PER_SESSION": 1,
    "CLASS_SUBJECT_MAX_PERIODS_PER_DAY": 1,
    "TEACHER_MAX_PERIODS_PER_DAY": 2,
    "SUBJECT_COMPONENT_DAY_SPREAD": 2,
    "TEACHER_RESTRICTED_SLOTS": 2,
    "TEACHER_MAX_GAP_RUN": 2,
    "TEACHER_MIN_FREE_TIME": 2,
    "TEACHER_PREFERRED_PERIOD_WINDOW": 3,
    "TEACHER_TOTAL_GAPS": 3,
    "TEACHER_SINGLE_PERIOD_SESSION": 3,
}
# G2: the HARD variant enforces these; every other code stays soft.
HARD_CODES = frozenset(
    {
        "TEACHER_MAX_PERIODS_PER_SESSION",
        "TEACHER_MAX_PERIODS_PER_DAY",
        "SUBJECT_COMPONENT_DAY_SPREAD",
        "CLASS_SUBJECT_MAX_PERIODS_PER_DAY",
    }
)
# No threshold parameter exists, so the witness penalty is reported, never forced to zero.
UNPARAMETERIZED = frozenset({"TEACHER_TOTAL_GAPS", "TEACHER_SINGLE_PERIOD_SESSION"})
SESSIONS = ("AM", "PM")


class DatasetManifest(DomainModel):
    benchmark_schema_version: Literal["2.0"] = "2.0"
    protocol: Literal["phase2-linux-v2"] = "phase2-linux-v2"
    dataset_id: str
    class_count: Literal[10, 20, 40]
    profile: Profile
    variant: Variant
    seed: NonNegativeInt
    policy_version: Literal["0.4"] = "0.4"
    input_fingerprint: SHA
    ground_truth: Literal["FEASIBLE", "INFEASIBLE"]
    known_optimum: tuple[NonNegativeInt, NonNegativeInt, NonNegativeInt] | None
    baseline_score: ScoreReport | None
    p2_lower_bound: NonNegativeInt | None
    capacity_proof: CapacityProof | None
    dimensions: Dimensions
    rule_counts: dict[str, PositiveInt]
    omitted: dict[str, NonNegativeInt]
    s05_component_pairs: NonNegativeInt
    sources: dict[str, SHA]
    files: dict[str, SHA]


class BundleManifest(DomainModel):
    benchmark_schema_version: Literal["2.0"] = "2.0"
    protocol: Literal["phase2-linux-v2"] = "phase2-linux-v2"
    revision: SourceRevision
    datasets: tuple[BundleEntry, ...]


@dataclass(frozen=True)
class GeneratedDataset:
    problem: ScheduleInput
    witness: WitnessArtifact | None
    provenance_problem: ScheduleInput | None
    provenance_witness: WitnessArtifact | None
    manifest: DatasetManifest


def dataset_id(size: int, profile: str, seed: int, variant: str) -> str:
    return f"{v1._id(size, profile, seed)}-{variant.lower()}"


def expected_dataset_ids() -> set[str]:
    return {
        dataset_id(size, profile, seed, variant)
        for size in SIZES
        for profile in PROFILES
        for seed in SEEDS
        for variant in VARIANTS
    }


def _sources() -> dict[str, str]:
    base = v1._sources()
    return {
        "generator_source_sha256": v1._sha(Path(__file__).read_bytes().replace(b"\r\n", b"\n")),
        "generator_v1_source_sha256": base["generator_source_sha256"],
        "core_source_sha256": base["core_source_sha256"],
        "uv_lock_sha256": base["uv_lock_sha256"],
    }


def _resources(
    problem: ScheduleInput, assignments: tuple[ScheduleAssignment, ...], profile: str, seed: int
) -> None:
    """Availability, locks and rooms exactly as the v1 frame draws them (same RNG order)."""
    if profile not in ("MIXED", "TIGHT"):
        return
    rng = random.Random(seed + 1000)
    all_slots = {s.id for s in problem.time_slots}
    teacher_slots: dict[str, set[str]] = defaultdict(set)
    class_slots: dict[str, set[str]] = defaultdict(set)
    for a in assignments:
        for sid in v1._footprint(problem, a):
            teacher_slots[a.teacher_ids[0]].add(sid)
            class_slots[a.class_ids[0]].add(sid)

    def availability(used: set[str], target: int) -> tuple[str, ...]:
        return tuple(sorted(used | set(rng.sample(sorted(all_slots - used), target - len(used)))))

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
    from tkb_core.domain.models import LockedAssignment

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


@dataclass(frozen=True)
class _Stats:
    used: dict[str, set[str]]
    session_loads: Counter[tuple[str, int, str]]
    day_loads: Counter[tuple[str, int]]
    taught: dict[tuple[str, int, str], set[str]]
    subject_days: Counter[tuple[str, str, int]]
    component_days: dict[str, list[int]]


def _stats(problem: ScheduleInput, assignments: Sequence[ScheduleAssignment]) -> _Stats:
    slots = {s.id: s for s in problem.time_slots}
    reqs = {r.id: r for r in problem.teaching_requirements}
    used: dict[str, set[str]] = defaultdict(set)
    session_loads: Counter[tuple[str, int, str]] = Counter()
    day_loads: Counter[tuple[str, int]] = Counter()
    taught: dict[tuple[str, int, str], set[str]] = defaultdict(set)
    subject_days: Counter[tuple[str, str, int]] = Counter()
    component_days: dict[str, list[int]] = defaultdict(list)
    for a in assignments:
        req = reqs[a.occurrence_id.rpartition("::")[0]]
        component_days[req.id].append(slots[a.slot_id].day)
        teacher = a.teacher_ids[0]
        for sid in v1._footprint(problem, a):
            s = slots[sid]
            used[teacher].add(sid)
            session_loads[teacher, s.day, s.session] += 1
            day_loads[teacher, s.day] += 1
            taught[teacher, s.day, s.session].add(sid)
            subject_days[req.class_ids[0], req.subject_id, s.day] += 1
    return _Stats(used, session_loads, day_loads, taught, subject_days, component_days)


def _gap_and_free(
    problem: ScheduleInput, stats: _Stats, teacher: str, occupied: set[str]
) -> tuple[int, int]:
    """Longest idle run and fully free sessions, per the catalog definitions of S09/S10."""
    calendar: dict[tuple[int, str], list[Any]] = defaultdict(list)
    for slot in sorted(problem.time_slots, key=lambda x: (x.day, x.session, x.period)):
        calendar[slot.day, slot.session].append(slot)
    longest = free = 0
    for (day, session), session_slots in calendar.items():
        mine = stats.taught.get((teacher, day, session), set())
        if not mine and not any(x.id in occupied for x in session_slots):
            free += int(any(x.can_teach for x in session_slots))
        if len(mine) < 2:
            continue
        periods = [x.period for x in session_slots if x.id in mine]
        first, last = min(periods), max(periods)
        run = 0
        for slot in session_slots:
            idle = (
                first < slot.period < last
                and slot.can_teach
                and slot.id not in mine
                and slot.id not in occupied
            )
            run = run + 1 if idle else 0
            longest = max(longest, run)
    return longest, free


def _day_limit(total: int) -> int:
    return max(0, (total + 5) // 6 - 1)


def _rule_config(
    problem: ScheduleInput,
    assignments: Sequence[ScheduleAssignment],
    profile: str,
    variant: str,
    seed: int,
) -> ConstraintConfigV11:
    """Witness-derived policy 0.4 rules (plan §2.2); deterministic for one identity."""
    rng = random.Random(seed + 2000)
    all_slots = sorted(s.id for s in problem.time_slots)
    stats = _stats(problem, assignments)
    occupied_work: list[OccupiedWork] = []
    occupied: dict[str, set[str]] = defaultdict(set)
    if profile in ("MIXED", "TIGHT"):
        for teacher in problem.teachers:
            assert teacher.available_slot_ids is not None
            outside = sorted(set(all_slots) - set(teacher.available_slot_ids))
            if not outside:
                raise DatasetGenerationError("No slot outside availability for occupied work")
            slot = rng.choice(outside)
            occupied[teacher.id].add(slot)
            occupied_work.append(OccupiedWork(teacher_id=teacher.id, slot_ids=(slot,)))
    rules: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    both = list(SESSIONS)
    for teacher in problem.teachers:
        available = set(teacher.available_slot_ids or all_slots)
        free_slots = sorted(available - stats.used[teacher.id])
        if len(free_slots) < 2:
            raise DatasetGenerationError("Too few unused available slots for S01/S07")
        avoid, restricted = rng.sample(free_slots, 2)
        total = len(stats.used[teacher.id])
        max_session = max(
            (n for (t, _, _), n in stats.session_loads.items() if t == teacher.id), default=0
        )
        max_day = max((n for (t, _), n in stats.day_loads.items() if t == teacher.id), default=0)
        day_limit = _day_limit(total) if profile == "TIGHT" and variant == "SOFT" else max_day
        longest, free = _gap_and_free(problem, stats, teacher.id, occupied[teacher.id])
        scope = {"teacher_ids": (teacher.id,)}
        per_teacher: list[tuple[str, dict[str, Any]]] = [
            ("TEACHER_AVOID_SLOTS", {"slot_ids": [avoid]}),
            ("TEACHER_MAX_PERIODS_PER_SESSION", {"limit": max_session, "session_ids": both}),
            ("TEACHER_MAX_PERIODS_PER_DAY", {"limit": day_limit}),
            (
                "TEACHER_PREFERRED_PERIOD_WINDOW",
                {"first_period": 2, "last_period": 4, "session_ids": both},
            ),
            ("TEACHER_RESTRICTED_SLOTS", {"slot_ids": [restricted]}),
            ("TEACHER_TOTAL_GAPS", {"session_ids": both}),
            ("TEACHER_MAX_GAP_RUN", {"limit": longest, "session_ids": both}),
            ("TEACHER_SINGLE_PERIOD_SESSION", {"session_ids": both}),
        ]
        if free >= 1:
            per_teacher.append(("TEACHER_MIN_FREE_TIME", {"unit": "session", "target": free}))
        rules.extend((code, params, scope) for code, params in per_teacher)
    for req in problem.teaching_requirements:
        days = stats.component_days[req.id]
        if len(days) < 2:
            continue
        gap = min(abs(a - b) for i, a in enumerate(days) for b in days[i + 1 :])
        if gap >= 1:
            rules.append(
                (
                    "SUBJECT_COMPONENT_DAY_SPREAD",
                    {"requirement_ids": [req.id], "min_day_gap": gap},
                    {},
                )
            )
    rules.append(
        ("CLASS_SUBJECT_MAX_PERIODS_PER_DAY", {"limit": max(stats.subject_days.values())}, {})
    )
    hard: list[HardConstraintConfigV11] = []
    soft: list[SoftConstraintConfigV11] = []
    for code, params, scope in rules:
        suffix = (
            scope["teacher_ids"][0]
            if scope
            else params["requirement_ids"][0]
            if code == "SUBJECT_COMPONENT_DAY_SPREAD"
            else "ALL"
        )
        ident = f"{code}-{suffix}"
        if variant == "HARD" and code in HARD_CODES:
            hard.append(
                HardConstraintConfigV11(id=ident, code=code, parameters=params, scope=scope)
            )
        else:
            soft.append(
                SoftConstraintConfigV11(
                    id=ident,
                    code=code,
                    priority=SOFT_PRIORITY[code],
                    weight=1,
                    parameters=params,
                    scope=scope,
                )
            )
    return ConstraintConfigV11(
        policy_version="0.4",
        hard=tuple(sorted(hard, key=lambda r: r.id)),
        soft=tuple(sorted(soft, key=lambda r: r.id)),
        occupied_work=tuple(occupied_work),
    )


def _omitted(problem: ScheduleInput, config: ConstraintConfigV11) -> dict[str, int]:
    rules = (*config.hard, *config.soft)
    spread = sum(r.code == "SUBJECT_COMPONENT_DAY_SPREAD" for r in rules)
    free = sum(r.code == "TEACHER_MIN_FREE_TIME" for r in rules)
    multi = sum(r.occurrence_count >= 2 for r in problem.teaching_requirements)
    return {
        "S05_SAME_DAY_REQUIREMENTS": multi - spread,
        "S10_NO_FREE_SESSION_TEACHERS": len(problem.teachers) - free,
    }


def _check_protocol(problem: ScheduleInput, size: int, profile: str) -> None:
    """The v1 frame checks (calendar, demand, rooms, locks), without the v1 rule check."""
    expected = {(d, s, p) for d in range(1, 7) for s in SESSIONS for p in range(1, 6)}
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
        ) != sorted(v1.SPLITS):
            raise DatasetGenerationError("Class demand/split differs from protocol")
        if sum(r.room_required for r in requirements) != int(timed):
            raise DatasetGenerationError("Room scope differs from protocol")
    expected_locks = size * 26 // (10 if profile == "MIXED" else 5) if timed else 0
    if (
        problem.manage_rooms != timed
        or len(problem.rooms) != (size // 5 if timed else 0)
        or len(problem.locked_assignments) != expected_locks
    ):
        raise DatasetGenerationError("Rooms/locks differ from profile")


def _artifact_files(
    problem: ScheduleInput,
    witness: WitnessArtifact | None,
    provenance_problem: ScheduleInput | None,
    provenance_witness: WitnessArtifact | None,
) -> dict[str, bytes]:
    files = {"input.json": v1._json_bytes(problem)}
    if witness is not None:
        files["witness.json"] = v1._json_bytes(witness)
    if provenance_problem is not None:
        files["provenance-input.json"] = v1._json_bytes(provenance_problem)
    if provenance_witness is not None:
        files["provenance-witness.json"] = v1._json_bytes(provenance_witness)
    return files


def _files(dataset: GeneratedDataset) -> dict[str, bytes]:
    return _artifact_files(
        dataset.problem, dataset.witness, dataset.provenance_problem, dataset.provenance_witness
    )


def _manifest(
    size: int,
    profile: Profile,
    seed: int,
    variant: Variant,
    problem: ScheduleInput,
    witness: WitnessArtifact | None,
    provenance_problem: ScheduleInput | None,
    provenance_witness: WitnessArtifact | None,
) -> DatasetManifest:
    problem = ScheduleInput.model_validate(problem.model_dump(mode="json", warnings="error"))
    config = problem.constraint_config
    if (
        problem.schema_version != "1.1"
        or not isinstance(config, ConstraintConfigV11)
        or config.policy_version != "0.4"
    ):
        raise DatasetGenerationError("Phase 2 profiles require input1.1/policy0.4")
    _check_protocol(problem, size, profile)
    infeasible = profile == "UNSAT_CAPACITY"
    target = provenance_problem if infeasible else problem
    evidence = provenance_witness if infeasible else witness
    if (
        target is None
        or evidence is None
        or evidence.role != ("PROVENANCE_ONLY" if infeasible else "FEASIBLE_BASELINE")
        or evidence.construction.seed != seed
        or evidence.input_fingerprint != target.fingerprint()
    ):
        raise DatasetGenerationError("Witness role, input fingerprint or construction mismatch")
    if not validate_schedule(target, evidence.assignments).valid:
        raise DatasetGenerationError("Witness fails independent hard validation")
    expected = _rule_config(
        target, evidence.assignments, "BASE" if infeasible else profile, variant, seed
    )
    if target.constraint_config != expected or config != expected:
        raise DatasetGenerationError("Rule configuration differs from the witness protocol")
    score = evaluate_score(target, evidence.assignments)
    if score.status != "OK" or score.tiers is None or score.schema_version != "1.2":
        raise DatasetGenerationError("Witness cannot be independently scored")
    tight_soft = profile == "TIGHT" and variant == "SOFT"
    for row in score.rules:
        derived = row.code not in UNPARAMETERIZED and not (
            tight_soft and row.code == "TEACHER_MAX_PERIODS_PER_DAY"
        )
        if derived and row.raw_penalty != 0:
            raise DatasetGenerationError("Witness-derived parameter does not hold on witness")
    if score.tiers[0] != 0:
        raise DatasetGenerationError("Witness must have zero P1 penalty")
    proof = baseline = lower = optimum = None
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
        assert c.available_slot_ids is not None
        data = target.model_dump(mode="json")
        data["classes"][0]["available_slot_ids"] = list(c.available_slot_ids)
        if data != problem.model_dump(mode="json"):
            raise DatasetGenerationError("UNSAT mutation differs from its provenance")
        proof = CapacityProof(class_id=c.id, demand_periods=demand, available_periods=available)
    else:
        if provenance_problem is not None or provenance_witness is not None:
            raise DatasetGenerationError("Feasible case cannot contain unrelated provenance")
        baseline = score
        optimum = (0, 0, 0) if score.tiers == (0, 0, 0) else None
        if tight_soft:
            loads = Counter(
                t
                for r in problem.teaching_requirements
                for t in r.teacher_ids
                for _ in range(r.periods_per_cycle)
            )
            lower = sum(max(0, loads[t.id] - 6 * _day_limit(loads[t.id])) for t in problem.teachers)
            if lower <= 0 or score.tiers[1] < lower:
                raise DatasetGenerationError("TIGHT witness/lower bound mismatch")
    try:
        dims = v1._dimensions(problem, infeasible)
    except CoreError as exc:
        raise DatasetGenerationError("DATASET_GENERATION_FAILED: preparation failed") from exc
    if (
        dims.classes != size
        or dims.teachers != size * 3 // 2
        or dims.periods != size * 30
        or dims.occurrences != size * 26
        or evidence.construction.swap_attempts != 5 * size
    ):
        raise DatasetGenerationError("Dataset dimensions or construction do not match protocol")
    rules = (*config.hard, *config.soft)
    spread_sizes = [
        sum(
            r.occurrence_count
            for r in problem.teaching_requirements
            if r.id in rule.parameters["requirement_ids"]  # type: ignore[operator]
        )
        for rule in rules
        if rule.code == "SUBJECT_COMPONENT_DAY_SPREAD"
    ]
    return DatasetManifest(
        dataset_id=dataset_id(size, profile, seed, variant),
        class_count=size,
        profile=profile,
        variant=variant,
        seed=seed,
        input_fingerprint=problem.fingerprint(),
        ground_truth="INFEASIBLE" if infeasible else "FEASIBLE",
        known_optimum=optimum,
        baseline_score=baseline,
        p2_lower_bound=lower,
        capacity_proof=proof,
        dimensions=dims,
        rule_counts={
            f"{mode}:{code}": n
            for mode, group in (("hard", config.hard), ("soft", config.soft))
            for code, n in Counter(r.code for r in group).items()
        },
        omitted=_omitted(problem, config),
        s05_component_pairs=sum(n * (n - 1) // 2 for n in spread_sizes),
        sources=_sources(),
        files={
            name: v1._sha(data)
            for name, data in _artifact_files(
                problem, witness, provenance_problem, provenance_witness
            ).items()
        },
    )


def generate_dataset(class_count: int, profile: str, seed: int, variant: str) -> GeneratedDataset:
    """Construct one v2 dataset and verify it without CP-SAT or retries."""
    if (
        type(class_count) is not int
        or class_count not in SIZES
        or profile not in PROFILES
        or type(seed) is not int
        or seed < 0
        or variant not in VARIANTS
    ):
        raise DatasetGenerationError("Unsupported size/profile/seed/variant")
    typed_profile: Profile = profile  # type: ignore[assignment]
    typed_variant: Variant = variant  # type: ignore[assignment]
    if profile == "UNSAT_CAPACITY":
        base = generate_dataset(class_count, "BASE", seed, variant)
        problem = ScheduleInput.model_validate(base.problem.model_dump(mode="json"))
        problem.classes[0].available_slot_ids = tuple(s.id for s in problem.time_slots[:29])
        problem = ScheduleInput.model_validate(problem.model_dump(mode="json"))
        witness = None
        provenance_problem: ScheduleInput | None = base.problem
        assert base.witness is not None
        provenance_witness: WitnessArtifact | None = base.witness.model_copy(
            update={"role": "PROVENANCE_ONLY"}
        )
    else:
        problem, assignments, construction = v1._construct(class_count, profile != "BASE", seed)
        _resources(problem, assignments, profile, seed)
        problem.constraint_config = _rule_config(problem, assignments, profile, variant, seed)
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
        class_count,
        typed_profile,
        seed,
        typed_variant,
        problem,
        witness,
        provenance_problem,
        provenance_witness,
    )
    return GeneratedDataset(problem, witness, provenance_problem, provenance_witness, manifest)


def validate_dataset(dataset: GeneratedDataset) -> None:
    """Regenerate from the declared identity and require identical artifacts and manifest."""
    try:
        declared = DatasetManifest.model_validate(dataset.manifest.model_dump(warnings="error"))
        actual = _manifest(
            declared.class_count,
            declared.profile,
            declared.seed,
            declared.variant,
            dataset.problem,
            dataset.witness,
            dataset.provenance_problem,
            dataset.provenance_witness,
        )
        if actual != declared:
            raise DatasetGenerationError("Manifest differs from verified artifacts")
        reference = generate_dataset(
            declared.class_count, declared.profile, declared.seed, declared.variant
        )
        if _files(reference) != _files(dataset) or reference.manifest != declared:
            raise DatasetGenerationError("Artifacts differ from deterministic regeneration")
    except (ValueError, TypeError, AttributeError, KeyError, CoreError) as exc:
        raise DatasetGenerationError(
            "DATASET_GENERATION_FAILED: artifact validation failed"
        ) from exc


def _revision() -> SourceRevision:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=False
        )
        blob = subprocess.run(
            ["git", "show", "HEAD:benchmarks/generate_phase2.py"],
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
    """Publish a new bundle under an exclusive root, manifest last."""
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
                    for variant in VARIANTS:
                        artifact = generate_dataset(size, profile, seed, variant)
                        dest = staging / artifact.manifest.dataset_id
                        dest.mkdir()
                        for name, data in _files(artifact).items():
                            (dest / name).write_bytes(data)
                        data = v1._json_bytes(artifact.manifest)
                        (dest / "manifest.json").write_bytes(data)
                        entries.append(
                            BundleEntry(
                                dataset_id=artifact.manifest.dataset_id,
                                manifest_sha256=v1._sha(data),
                            )
                        )
        manifest = BundleManifest(revision=_revision(), datasets=tuple(entries))
        (staging / "manifest.json").write_bytes(v1._json_bytes(manifest))
        output.mkdir()
        for child in sorted(staging.iterdir()):
            if child.name != "manifest.json":
                child.rename(output / child.name)
        (staging / "manifest.json").rename(output / "manifest.json")
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def verify_bundle(root: Path) -> BundleManifest:
    """Check a transported bundle against deterministic regeneration with current sources."""
    try:
        manifest = BundleManifest.model_validate(v1._parse(v1._read(root, "manifest.json")))
        expected = expected_dataset_ids()
        ids = [e.dataset_id for e in manifest.datasets]
        if len(ids) != len(expected) or set(ids) != expected:
            raise DatasetGenerationError("Bundle dataset membership differs from protocol")
        for entry in manifest.datasets:
            base = root / entry.dataset_id
            if not base.resolve().is_relative_to(root.resolve()):
                raise DatasetGenerationError("Dataset path escapes bundle")
            data = v1._read(base, "manifest.json")
            if v1._sha(data) != entry.manifest_sha256:
                raise DatasetGenerationError("Dataset manifest checksum mismatch")
            item = DatasetManifest.model_validate(v1._parse(data))
            if item.dataset_id != entry.dataset_id:
                raise DatasetGenerationError("Dataset identity mismatch")
            names = (
                {"input.json", "provenance-input.json", "provenance-witness.json"}
                if item.profile == "UNSAT_CAPACITY"
                else {"input.json", "witness.json"}
            )
            if set(item.files) != names:
                raise DatasetGenerationError("Unexpected artifact membership")
            raw = {name: v1._read(base, name) for name in names}
            if any(v1._sha(value) != item.files[name] for name, value in raw.items()):
                raise DatasetGenerationError("Artifact checksum mismatch")

            parsed = {name: v1._parse(value) for name, value in raw.items()}
            problem = ScheduleInput.model_validate(parsed["input.json"])
            witness = (
                WitnessArtifact.model_validate(parsed["witness.json"])
                if "witness.json" in parsed
                else None
            )
            provenance_problem = (
                ScheduleInput.model_validate(parsed["provenance-input.json"])
                if "provenance-input.json" in parsed
                else None
            )
            provenance_witness = (
                WitnessArtifact.model_validate(parsed["provenance-witness.json"])
                if "provenance-witness.json" in parsed
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
                "protocol": PROTOCOL,
                "datasets": len(manifest.datasets),
                "output": str(args.output),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
