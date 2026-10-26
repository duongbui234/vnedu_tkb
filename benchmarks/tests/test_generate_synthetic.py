"""Synthetic dataset invariants; no solve calls and no benchmark measurements."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from benchmarks.generate_synthetic import (
    DatasetGenerationError,
    generate_dataset,
    validate_dataset,
    verify_bundle,
    write_bundle,
)
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score


@pytest.mark.parametrize("size", [10, 20, 40])
@pytest.mark.parametrize("profile", ["BASE", "MIXED", "TIGHT", "UNSAT_CAPACITY"])
def test_profile_invariants(size: int, profile: str) -> None:
    artifact = generate_dataset(size, profile, 101)
    validate_dataset(artifact)
    p = artifact.problem
    assert len(p.classes) == size and len(p.teachers) == size * 3 // 2
    assert len(p.subjects) == 9 and len(p.time_slots) == 60
    assert sum(r.periods_per_cycle for r in p.teaching_requirements) == size * 30
    assert sum(r.occurrence_count for r in p.teaching_requirements) == size * 26
    assert artifact.manifest.dimensions.occurrences == size * 26
    if profile != "UNSAT_CAPACITY":
        assert artifact.manifest.dimensions.placements <= 72000
    else:
        assert artifact.manifest.dimensions.placements is None
        assert artifact.manifest.dimensions.occupancy_terms is None
        assert artifact.manifest.dimensions.precheck_status == "INFEASIBLE"
    for c in p.classes:
        reqs = [r for r in p.teaching_requirements if c.id in r.class_ids]
        assert sorted(r.periods_per_cycle for r in reqs) == [2, 2, 3, 3, 4, 4, 4, 4, 4]
        assert sum(sum(d == 2 for d in r.block_durations) for r in reqs) == 4
    reached = {p.classes[0].id}
    while True:
        teachers = {
            t
            for r in p.teaching_requirements
            if reached.intersection(r.class_ids)
            for t in r.teacher_ids
        }
        connected = {
            c
            for r in p.teaching_requirements
            if teachers.intersection(r.teacher_ids)
            for c in r.class_ids
        }
        if connected == reached:
            break
        reached = connected
    assert len(reached) == size  # Larger cases are not independent copies of ten-class blocks.
    if profile == "UNSAT_CAPACITY":
        assert artifact.witness is None
        assert artifact.manifest.ground_truth == "INFEASIBLE"
        proof = artifact.manifest.capacity_proof
        assert proof.demand_periods == 30 and proof.available_periods == 29
        assert artifact.provenance_witness.role == "PROVENANCE_ONLY"
        assert artifact.provenance_witness.input_fingerprint != p.fingerprint()
        assert validate_schedule(
            artifact.provenance_problem, artifact.provenance_witness.assignments
        ).valid
        assert artifact.manifest.baseline_score is None
        return
    assert artifact.witness.role == "FEASIBLE_BASELINE"
    assert artifact.witness.input_fingerprint == p.fingerprint()
    assert validate_schedule(p, artifact.witness.assignments).valid
    score = evaluate_score(p, artifact.witness.assignments)
    assert score == artifact.manifest.baseline_score
    assert artifact.witness.construction.swap_attempts == 5 * size
    assert len(p.constraint_config.soft) == 4 * len(p.teachers)
    if profile in ("BASE", "MIXED"):
        assert score.tiers == (0, 0, 0) and artifact.manifest.known_optimum == (0, 0, 0)
    else:
        assert artifact.manifest.known_optimum is None
        assert artifact.manifest.p2_lower_bound > 0
        assert score.tiers[0] == 0 and score.tiers[1] >= artifact.manifest.p2_lower_bound
        assert score.tiers[2] == 0
    if profile == "BASE":
        assert not p.rooms and not p.locked_assignments
        assert all(s.start_minute is None for s in p.time_slots)
    else:
        expected = 42 if profile == "MIXED" else 32
        assert all(len(c.available_slot_ids) == expected for c in p.classes)
        assert len(p.rooms) == size // 5
        assert len(p.locked_assignments) == size * 26 // (10 if profile == "MIXED" else 5)
        assert any(
            lock.room_id is not None and lock.slot_id is not None for lock in p.locked_assignments
        )
        assert any(
            lock.room_id is None and lock.slot_id is not None for lock in p.locked_assignments
        )


def test_deterministic_and_seed_changes_bytes() -> None:
    a = generate_dataset(10, "MIXED", 101)
    b = generate_dataset(10, "MIXED", 101)
    assert a.problem.model_dump_json() == b.problem.model_dump_json()
    assert a.witness == b.witness and a.manifest == b.manifest
    c = generate_dataset(10, "MIXED", 102)
    assert a.manifest.files["input.json"] != c.manifest.files["input.json"]


@pytest.mark.parametrize(
    "mutation", ["split", "availability", "room", "lock", "witness", "manifest"]
)
def test_mutated_artifacts_are_not_labeled_feasible(mutation: str) -> None:
    a = generate_dataset(10, "MIXED", 101)
    if mutation == "split":
        a.problem.teaching_requirements[0].block_durations = (1,)
    elif mutation == "availability":
        a.problem.teachers[0].available_slot_ids = ()
    elif mutation == "room":
        for room in a.problem.rooms:
            room.available_slot_ids = ()
    elif mutation == "lock":
        a.problem.locked_assignments[0].slot_id = "unknown-slot"
    elif mutation == "witness":
        a.witness.assignments[0].slot_id = "unknown-slot"
    else:
        a.manifest.files["input.json"] = "0" * 64
    with pytest.raises(DatasetGenerationError):
        validate_dataset(a)


def test_bundle_hashes_roundtrip_and_existing_output(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    manifest = write_bundle(root)
    assert len(manifest.datasets) == 36
    assert verify_bundle(root) == manifest
    for entry in manifest.datasets:
        data = (root / entry.dataset_id / "manifest.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry.manifest_sha256
    with pytest.raises(FileExistsError):
        write_bundle(root)
    entry = manifest.datasets[0]
    p = root / entry.dataset_id / "input.json"
    raw = json.loads(p.read_text())
    raw["teaching_requirements"][0]["periods_per_cycle"] += 1
    p.write_text(json.dumps(raw))
    with pytest.raises(DatasetGenerationError):
        verify_bundle(root)


@pytest.mark.parametrize(
    "size,profile,seed",
    [
        (11, "BASE", 101),
        (10, "OTHER", 101),
        (True, "BASE", 101),
        (10, "BASE", True),
        (10, "BASE", -1),
    ],
)
def test_rejects_non_protocol_arguments(size: Any, profile: Any, seed: Any) -> None:
    with pytest.raises(DatasetGenerationError):
        generate_dataset(size, profile, seed)


def test_rehashed_bad_witness_still_fails_independent_validation() -> None:
    a = generate_dataset(10, "MIXED", 101)
    a.witness.assignments[0].slot_id = a.witness.assignments[1].slot_id
    data = (
        json.dumps(a.witness.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, indent=2)
        + "\n"
    ).encode()
    a.manifest.files["witness.json"] = hashlib.sha256(data).hexdigest()
    with pytest.raises(DatasetGenerationError):
        validate_dataset(a)


def test_construction_counts_cannot_claim_more_successes_than_attempts() -> None:
    from pydantic import ValidationError

    from benchmarks.generate_synthetic import Construction

    with pytest.raises(ValidationError):
        Construction(seed=101, swap_attempts=50, swap_successes=51)


def test_no_solver_imports_in_generator() -> None:
    import subprocess
    import sys

    script = """
import builtins
original=builtins.__import__
def guarded(name,*args,**kwargs):
    blocked=('ortools','tkb_core.solver.cp_sat','tkb_core.solver.model_builder',
             'tkb_core.constraints.soft')
    if name.startswith(blocked):
        raise ImportError('forbidden solver import: '+name)
    return original(name,*args,**kwargs)
builtins.__import__=guarded
from benchmarks.generate_synthetic import generate_dataset,validate_dataset
artifact=generate_dataset(10,'MIXED',101)
validate_dataset(artifact)
assert artifact.manifest.baseline_score.tiers==(0,0,0)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_publication_does_not_replace_a_racing_empty_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import benchmarks.generate_synthetic as generator

    monkeypatch.setattr(generator, "SIZES", (10,))
    monkeypatch.setattr(generator, "PROFILES", ("BASE",))
    monkeypatch.setattr(generator, "SEEDS", (101,))
    output = tmp_path / "bundle"
    original = Path.rename
    created = False

    def racing_rename(source: Path, target: Path) -> Path:
        nonlocal created
        if Path(target) == output:
            output.mkdir()
            created = True
        return original(source, target)

    monkeypatch.setattr(Path, "rename", racing_rename)
    try:
        generator.write_bundle(output)
    except FileExistsError:
        assert created and list(output.iterdir()) == []
    else:
        assert not created, "Publishing replaced a directory created by another process"


def test_generator_does_not_accept_calendar_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    import benchmarks.generate_synthetic as generator

    construct = generator._construct

    def drift(*args: Any) -> Any:
        problem, assignments, construction = construct(*args)
        problem.time_slots[
            -1
        ].day = 7  # Unused period: witness remains valid but protocol is wrong.
        return problem, assignments, construction

    monkeypatch.setattr(generator, "_construct", drift)
    with pytest.raises(DatasetGenerationError):
        generator.generate_dataset(10, "BASE", 101)


def test_source_identity_describes_imported_core_not_an_unused_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import benchmarks.generate_synthetic as generator

    reference = generator.generate_dataset(10, "BASE", 101)
    (tmp_path / "uv.lock").write_bytes((generator.ROOT / "uv.lock").read_bytes())
    monkeypatch.setattr(generator, "ROOT", tmp_path)
    artifact = generator.generate_dataset(10, "BASE", 101)
    assert (
        artifact.manifest.sources["core_source_sha256"]
        == reference.manifest.sources["core_source_sha256"]
    )


def test_tight_profile_rejects_silent_limit_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    import benchmarks.generate_synthetic as generator

    configure = generator._configure

    def changed(*args: Any) -> None:
        configure(*args)
        problem = args[0]
        for rule in problem.constraint_config.soft:
            if rule.code == "TEACHER_MAX_PERIODS_PER_DAY":
                rule.parameters["limit"] = 0

    monkeypatch.setattr(generator, "_configure", changed)
    with pytest.raises(DatasetGenerationError):
        generator.generate_dataset(10, "TIGHT", 101)


def test_generation_failure_publishes_no_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import benchmarks.generate_synthetic as generator

    def fail(*args: Any) -> Any:
        raise DatasetGenerationError("test failure")

    monkeypatch.setattr(generator, "generate_dataset", fail)
    output = tmp_path / "bundle"
    with pytest.raises(DatasetGenerationError):
        generator.write_bundle(output)
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


def test_manifest_does_not_accept_legacy_input_as_phase2a_profile() -> None:
    import benchmarks.generate_synthetic as generator
    from tkb_core.contracts.input import ScheduleInput

    artifact = generator.generate_dataset(10, "BASE", 101)
    raw = artifact.problem.model_dump(mode="json")
    raw["schema_version"] = "1.0"
    raw["constraint_config"].pop("policy_version")
    for rule in raw["constraint_config"]["soft"]:
        rule.pop("id")
        rule.pop("priority")
        rule["enabled"] = False
    legacy = ScheduleInput.model_validate(raw)
    witness = artifact.witness.model_copy(update={"input_fingerprint": legacy.fingerprint()})
    with pytest.raises(DatasetGenerationError):
        generator._manifest(10, "BASE", 101, legacy, witness, None, None)


@pytest.mark.parametrize("mutation", ["availability", "disabled", "priority", "family"])
def test_profiles_reject_silently_weakened_rules_and_availability(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    import benchmarks.generate_synthetic as generator

    configure = generator._configure

    def changed(*args: Any) -> None:
        configure(*args)
        problem = args[0]
        if mutation == "availability":
            for teacher in problem.teachers:
                teacher.available_slot_ids = None
        else:
            for rule in problem.constraint_config.soft:
                if rule.code == "TEACHER_PREFERRED_PERIOD_WINDOW":
                    if mutation == "disabled":
                        rule.enabled = False
                    elif mutation == "priority":
                        rule.priority = 2
                    else:
                        rule.code = "TEACHER_MAX_PERIODS_PER_DAY"
                        rule.parameters = {"limit": 60}

    monkeypatch.setattr(generator, "_configure", changed)
    with pytest.raises(DatasetGenerationError):
        generator.generate_dataset(10, "TIGHT" if mutation == "availability" else "BASE", 101)
