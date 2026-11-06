"""Phase 3C repair benchmark inputs (plan C2, C4), outside Scheduling Core.

Datasets come from the frozen v2 generator (``generate_phase2``, imported unchanged). Noise is
applied to a dataset input using the previous schedule solved in the same campaign; every choice
is drawn from a ``random.Random`` seeded by (dataset, noise, candidate). A noisy input with an
arithmetic infeasibility proof (Phase 3B prechecks) is retried with the next candidate, at most
``MAX_CANDIDATES`` times, and otherwise kept and labelled ``EXPECTED_INFEASIBLE``. No noisy input
is claimed feasible: without a proof it is ``GROUND_TRUTH_UNKNOWN``.
"""

from __future__ import annotations

import copy
import hashlib
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from benchmarks import generate_phase2 as g2

SEED = 101
SIZES = (10, 20, 40)
PROFILES = ("BASE", "MIXED", "TIGHT")
VARIANTS = ("SOFT", "HARD")
UNSAT_SEEDS = (101, 102, 103)
NOISES = ("N1", "N2", "N3", "N4")
MAX_CANDIDATES = 10
Noise = Literal["N1", "N2", "N3", "N4"]
Label = Literal["GROUND_TRUTH_UNKNOWN", "EXPECTED_INFEASIBLE"]


class NoiseError(ValueError):
    """No candidate of a noise type can be applied to this input."""


def base_dataset_ids(*, smoke: bool = False) -> tuple[str, ...]:
    """Plan C2: s101 x 3 sizes x BASE/MIXED/TIGHT x SOFT/HARD (smoke: BASE 10 classes)."""
    if smoke:
        return tuple(sorted(g2.dataset_id(10, "BASE", SEED, v) for v in VARIANTS))
    return tuple(
        sorted(g2.dataset_id(s, p, SEED, v) for s in SIZES for p in PROFILES for v in VARIANTS)
    )


def unsat_dataset_ids(*, smoke: bool = False) -> tuple[str, ...]:
    """Plan C8: every UNSAT_CAPACITY dataset of the v2 matrix (smoke: one)."""
    if smoke:
        return (g2.dataset_id(10, "UNSAT_CAPACITY", SEED, "SOFT"),)
    return tuple(
        sorted(
            g2.dataset_id(s, "UNSAT_CAPACITY", seed, v)
            for s in SIZES
            for seed in UNSAT_SEEDS
            for v in VARIANTS
        )
    )


def noise_seed(dataset_id: str, noise: str) -> int:
    digest = hashlib.sha256(f"phase3c|{dataset_id}|{noise}".encode()).hexdigest()
    return int(digest[:12], 16)


def repair_request(order: str, *, hint: bool) -> dict[str, Any]:
    """Plan C5: no change limit, no change scope; order and hint always explicit."""
    if order not in ("BEFORE_QUALITY", "AFTER_QUALITY"):
        raise ValueError("Unknown change order")
    return {
        "schema_version": "1.0",
        "change_order": order,
        "max_changes": None,
        "change_scope": None,
        "use_previous_as_hint": hint,
    }


def _duration(requirement: dict[str, Any], ordinal: int) -> int:
    blocks = requirement.get("block_durations")
    return int(blocks[ordinal - 1]) if blocks else 1


def _apply(
    data: dict[str, Any], previous: Sequence[dict[str, Any]], noise: str, rng: random.Random
) -> tuple[dict[str, Any], dict[str, Any]]:
    new = copy.deepcopy(data)
    slots = {s["id"]: s for s in new["time_slots"]}
    requirements = {r["id"]: r for r in new["teaching_requirements"]}
    active = sorted(
        (r for r in new["teaching_requirements"] if r["periods_per_cycle"] > 0),
        key=lambda r: r["id"],
    )
    if noise == "N1":
        teaching = sorted({(a["teacher_ids"][0], slots[a["slot_id"]]["day"]) for a in previous})
        if not teaching:
            raise NoiseError("No teacher teaches in the previous schedule")
        teacher_id, day = rng.choice(teaching)
        teacher = next(t for t in new["teachers"] if t["id"] == teacher_id)
        current = teacher.get("available_slot_ids")
        if current is None:
            current = [s["id"] for s in new["time_slots"]]
        teacher["available_slot_ids"] = [s for s in current if slots[s]["day"] != day]
        return new, {"teacher": teacher_id, "day": day}
    if noise == "N2":
        if not active:
            raise NoiseError("No requirement to reassign")
        requirement = rng.choice(active)
        old = requirement["teacher_ids"][0]
        same = sorted(
            {
                r["teacher_ids"][0]
                for r in new["teaching_requirements"]
                if r["subject_id"] == requirement["subject_id"]
            }
            - {old}
        )
        pool = same or sorted({t["id"] for t in new["teachers"]} - {old})
        if not pool:
            raise NoiseError("No other teacher")
        teacher_id = rng.choice(pool)
        requirement["teacher_ids"] = [teacher_id]
        return new, {
            "requirement": requirement["id"],
            "old_teacher": old,
            "new_teacher": teacher_id,
        }
    if noise == "N3":
        if len(active) < 2:
            raise NoiseError("Need two requirements")
        added = rng.choice(active)
        # Only the last occurrence may disappear, so the other occurrence IDs stay stable.
        removable = [
            r
            for r in active
            if r is not added and (not r.get("block_durations") or r["block_durations"][-1] == 1)
        ]
        if not removable:
            raise NoiseError("No requirement can lose a single period")
        removed = rng.choice(removable)
        blocks = removed.get("block_durations")
        count = len(blocks) if blocks else removed["periods_per_cycle"]
        dropped = f"{removed['id']}::{count}"
        new_ordinal = (
            len(added["block_durations"]) + 1
            if added.get("block_durations")
            else added["periods_per_cycle"] + 1
        )
        added["periods_per_cycle"] += 1
        if added.get("block_durations"):
            added["block_durations"].append(1)
        removed["periods_per_cycle"] -= 1
        if removed.get("block_durations"):
            removed["block_durations"].pop()
            if not removed["block_durations"]:
                removed["block_durations"] = None
        if new.get("locked_assignments"):
            new["locked_assignments"] = [
                lock for lock in new["locked_assignments"] if lock["occurrence_id"] != dropped
            ]
        return new, {
            "added": added["id"],
            "removed": removed["id"],
            "new_occurrence": f"{added['id']}::{new_ordinal}",
            "dropped_occurrence": dropped,
        }
    if noise == "N4":
        locked = {lock["occurrence_id"] for lock in new.get("locked_assignments") or []}
        coordinates = {(s["day"], s["session"], s["period"]): s for s in new["time_slots"]}
        classes = {c["id"]: c for c in new["classes"]}
        teachers = {t["id"]: t for t in new["teachers"]}
        candidates = sorted(
            (a for a in previous if a["occurrence_id"] not in locked),
            key=lambda a: a["occurrence_id"],
        )
        if len(candidates) < 2:
            raise NoiseError("Need two unlocked occurrences")
        chosen = rng.sample(candidates, 2)
        locks = []
        for assignment in sorted(chosen, key=lambda a: a["occurrence_id"]):
            requirement_id, _, ordinal = assignment["occurrence_id"].rpartition("::")
            requirement = requirements[requirement_id]
            duration = _duration(requirement, int(ordinal))
            learner = classes[requirement["class_ids"][0]]
            teacher = teachers[requirement["teacher_ids"][0]]
            targets = []
            for start in sorted(new["time_slots"], key=lambda s: s["id"]):
                if start["id"] == assignment["slot_id"]:
                    continue
                cells = [
                    coordinates.get((start["day"], start["session"], start["period"] + d))
                    for d in range(duration)
                ]
                if any(c is None or not c.get("can_teach", True) for c in cells):
                    continue
                ids = [c["id"] for c in cells if c is not None]
                if all(
                    r.get("available_slot_ids") is None
                    or all(i in r["available_slot_ids"] for i in ids)
                    for r in (learner, teacher)
                ):
                    targets.append(start["id"])
            if not targets:
                raise NoiseError("No alternative slot for a lock")
            locks.append(
                {"occurrence_id": assignment["occurrence_id"], "slot_id": rng.choice(targets)}
            )
        new["locked_assignments"] = [*(new.get("locked_assignments") or []), *locks]
        return new, {"locks": locks}
    raise ValueError("Unknown noise")


def counting_proofs(data: dict[str, Any]) -> tuple[str, ...]:
    """Phase 3B prechecks on the clean domain; an input error raises ``CoreError``."""
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.diagnostics.domains import build_domains
    from tkb_core.diagnostics.prechecks import run_prechecks
    from tkb_core.preprocessing.normalize import normalize

    problem = ScheduleInput.model_validate(data)
    domains = build_domains(
        normalize(problem), expanded=False, max_placements=100000, max_occupancy_terms=1000000
    )
    return tuple(p.code for p in run_prechecks(domains))


def core_rejection(data: dict[str, Any]) -> str | None:
    """Diagnostic code when the core's own preparation rejects ``data`` as an input, else None.

    ``prepare`` is the step ``solve`` and ``repair`` run first; INFEASIBLE or UNKNOWN from it are
    outcomes on a valid input and are not rejections. Incident phase3c-linux-01: the 3B prechecks
    read a conflicting lock as an infeasibility proof, while the core reports INPUT_INVALID.
    """
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.domain.errors import CoreError
    from tkb_core.preprocessing.feasibility import prepare
    from tkb_core.solver.options import SolveOptions

    try:
        prepare(ScheduleInput.model_validate(data), SolveOptions())
    except CoreError as exc:
        if exc.status in ("INPUT_INVALID", "UNSUPPORTED_FEATURE"):
            return exc.diagnostics[0].code
    return None


@dataclass(frozen=True)
class NoisyInput:
    data: dict[str, Any]
    description: dict[str, Any]
    label: Label
    candidate: int
    proofs: tuple[str, ...]


def derive_noise(
    data: dict[str, Any], previous: Sequence[dict[str, Any]], dataset_id: str, noise: str
) -> NoisyInput:
    """Apply ``noise`` deterministically; skip inputs the core rejects; retry while a counting
    proof shows infeasibility."""
    from tkb_core.domain.errors import CoreError

    if noise not in NOISES:
        raise ValueError("Unknown noise")
    seed = noise_seed(dataset_id, noise)
    last: NoisyInput | None = None
    for candidate in range(MAX_CANDIDATES):
        rng = random.Random(seed * MAX_CANDIDATES + candidate)
        new, description = _apply(data, previous, noise, rng)
        try:
            proofs = counting_proofs(new)
        except CoreError:
            continue  # the candidate made an invalid input; try the next one
        if core_rejection(new) is not None:
            continue  # the core would answer INPUT_INVALID, not a repair; try the next one
        if not proofs:
            return NoisyInput(new, description, "GROUND_TRUTH_UNKNOWN", candidate, ())
        last = NoisyInput(new, description, "EXPECTED_INFEASIBLE", candidate, proofs)
    if last is None:
        raise NoiseError("Every candidate produced an invalid input")
    return last
