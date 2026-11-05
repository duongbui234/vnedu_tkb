"""Policy 0.4 dataset invariants for the v2 Linux performance plan; no solve calls."""

import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from benchmarks import generate_phase2 as g2
from benchmarks import generate_synthetic as g1
from benchmarks.generate_phase2 import (
    DatasetGenerationError,
    generate_dataset,
    validate_dataset,
    verify_bundle,
    write_bundle,
)
from tkb_core.domain.models import ConstraintConfigV11
from tkb_core.validation.independent_validator import validate_schedule
from tkb_core.validation.score_evaluator import evaluate_score

ROOT = Path(__file__).resolve().parents[2]
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
HARD_CODES = {
    "TEACHER_MAX_PERIODS_PER_SESSION",
    "TEACHER_MAX_PERIODS_PER_DAY",
    "SUBJECT_COMPONENT_DAY_SPREAD",
    "CLASS_SUBJECT_MAX_PERIODS_PER_DAY",
}
PER_TEACHER = {
    "TEACHER_AVOID_SLOTS",
    "TEACHER_MAX_PERIODS_PER_SESSION",
    "TEACHER_MAX_PERIODS_PER_DAY",
    "TEACHER_PREFERRED_PERIOD_WINDOW",
    "TEACHER_RESTRICTED_SLOTS",
    "TEACHER_TOTAL_GAPS",
    "TEACHER_MAX_GAP_RUN",
    "TEACHER_SINGLE_PERIOD_SESSION",
}
# Penalty of these rules is not forced to zero by a witness-derived parameter.
UNPARAMETERIZED = {"TEACHER_TOTAL_GAPS", "TEACHER_SINGLE_PERIOD_SESSION"}


def _config(artifact: g2.GeneratedDataset) -> ConstraintConfigV11:
    config = artifact.problem.constraint_config
    assert isinstance(config, ConstraintConfigV11)
    return config


@pytest.mark.parametrize("variant", ["SOFT", "HARD"])
@pytest.mark.parametrize("profile", ["BASE", "MIXED", "TIGHT"])
def test_rule_set_follows_plan(profile: str, variant: str) -> None:
    artifact = generate_dataset(10, profile, 101, variant)
    validate_dataset(artifact)
    config = _config(artifact)
    p, m = artifact.problem, artifact.manifest
    assert artifact.witness is not None
    witness = artifact.witness.assignments
    assert config.policy_version == "0.4" and p.schema_version == "1.1"
    assert m.dataset_id == f"c10-{profile.lower()}-s101-{variant.lower()}"
    assert (m.variant, m.policy_version, m.benchmark_schema_version) == (variant, "0.4", "2.0")
    hard_codes = {r.code for r in config.hard}
    soft_codes = {r.code for r in config.soft}
    assert hard_codes == (HARD_CODES if variant == "HARD" else set())
    assert soft_codes == set(SOFT_PRIORITY) - hard_codes
    assert all(r.enabled for r in (*config.hard, *config.soft))
    for rule in config.soft:
        assert rule.weight == 1 and rule.priority == SOFT_PRIORITY[rule.code]
    counts = Counter(r.code for r in (*config.hard, *config.soft))
    teachers = len(p.teachers)
    for code in PER_TEACHER:
        assert counts[code] == teachers
    assert counts["CLASS_SUBJECT_MAX_PERIODS_PER_DAY"] == 1
    multi = sum(1 for r in p.teaching_requirements if r.occurrence_count >= 2)
    assert counts["SUBJECT_COMPONENT_DAY_SPREAD"] + m.omitted["S05_SAME_DAY_REQUIREMENTS"] == multi
    assert counts["TEACHER_MIN_FREE_TIME"] + m.omitted["S10_NO_FREE_SESSION_TEACHERS"] == teachers
    assert m.rule_counts == {
        f"{mode}:{code}": n
        for mode, rules in (("hard", config.hard), ("soft", config.soft))
        for code, n in Counter(r.code for r in rules).items()
    }
    # Hard rules hold on the witness, so the dataset stays known-feasible.
    assert validate_schedule(p, witness).valid
    score = evaluate_score(p, witness)
    assert score.status == "OK" and score.schema_version == "1.2"
    assert m.baseline_score == score
    assert score.tiers is not None
    assert m.known_optimum == ((0, 0, 0) if score.tiers == (0, 0, 0) else None)
    tight_soft_day = profile == "TIGHT" and variant == "SOFT"
    for row in score.rules:
        if row.code in UNPARAMETERIZED or (
            tight_soft_day and row.code == "TEACHER_MAX_PERIODS_PER_DAY"
        ):
            continue
        assert row.raw_penalty == 0, row
    assert score.tiers[0] == 0
    if tight_soft_day:
        assert m.p2_lower_bound is not None and m.p2_lower_bound > 0
        assert score.tiers[1] >= m.p2_lower_bound
    else:
        assert m.p2_lower_bound is None


@pytest.mark.parametrize("profile", ["BASE", "MIXED", "TIGHT"])
def test_slot_preferences_and_occupied_work(profile: str) -> None:
    artifact = generate_dataset(10, profile, 102, "SOFT")
    config = _config(artifact)
    assert artifact.witness is not None
    used: dict[str, set[str]] = {}
    for a in artifact.witness.assignments:
        used.setdefault(a.teacher_ids[0], set()).update(g1._footprint(artifact.problem, a))
    all_slots = {s.id for s in artifact.problem.time_slots}
    occupied = {o.teacher_id: set(o.slot_ids) for o in config.occupied_work}
    for teacher in artifact.problem.teachers:
        available = set(teacher.available_slot_ids or all_slots)
        rules = {r.code: r for r in config.soft if r.scope.teacher_ids == (teacher.id,)}
        avoid = set(rules["TEACHER_AVOID_SLOTS"].parameters["slot_ids"])  # type: ignore[arg-type]
        restricted = set(
            rules["TEACHER_RESTRICTED_SLOTS"].parameters["slot_ids"]  # type: ignore[arg-type]
        )
        assert len(avoid) == len(restricted) == 1 and not avoid & restricted
        assert (avoid | restricted) <= available - used.get(teacher.id, set())
        if profile == "BASE":
            assert teacher.id not in occupied
        else:
            assert len(occupied[teacher.id]) == 1
            assert not occupied[teacher.id] & available
    assert (profile == "BASE") == (not config.occupied_work)


@pytest.mark.parametrize("profile", ["BASE", "MIXED", "TIGHT"])
def test_resources_match_the_v1_frame(profile: str) -> None:
    old = g1.generate_dataset(10, profile, 103).problem
    new = generate_dataset(10, profile, 103, "HARD").problem
    assert new.time_slots == old.time_slots
    assert new.teaching_requirements == old.teaching_requirements
    assert new.locked_assignments == old.locked_assignments
    assert new.rooms == old.rooms
    assert [c.available_slot_ids for c in new.classes] == [
        c.available_slot_ids for c in old.classes
    ]
    assert [t.available_slot_ids for t in new.teachers] == [
        t.available_slot_ids for t in old.teachers
    ]


@pytest.mark.parametrize("variant", ["SOFT", "HARD"])
def test_unsat_capacity_stays_a_precheck_infeasible(variant: str) -> None:
    artifact = generate_dataset(10, "UNSAT_CAPACITY", 101, variant)
    validate_dataset(artifact)
    m = artifact.manifest
    assert artifact.witness is None and artifact.provenance_witness is not None
    assert m.ground_truth == "INFEASIBLE" and m.baseline_score is None
    assert m.known_optimum is None and m.p2_lower_bound is None
    assert m.capacity_proof is not None
    assert (m.capacity_proof.demand_periods, m.capacity_proof.available_periods) == (30, 29)
    assert m.dimensions.precheck_status == "INFEASIBLE"
    base = generate_dataset(10, "BASE", 101, variant)
    assert artifact.provenance_problem == base.problem
    assert _config(artifact) == _config(base)


def test_larger_sizes_generate() -> None:
    for size in (20, 40):
        artifact = generate_dataset(size, "TIGHT", 101, "HARD")
        validate_dataset(artifact)
        assert artifact.manifest.dimensions.classes == size


def test_deterministic_and_identity_changes_bytes() -> None:
    a = generate_dataset(10, "MIXED", 101, "SOFT")
    b = generate_dataset(10, "MIXED", 101, "SOFT")
    assert g2._files(a) == g2._files(b) and a.manifest == b.manifest
    for other in (
        generate_dataset(10, "MIXED", 102, "SOFT"),
        generate_dataset(10, "MIXED", 101, "HARD"),
    ):
        assert g2._files(other)["input.json"] != g2._files(a)["input.json"]


def _mutate(artifact: g2.GeneratedDataset, mutation: str) -> g2.GeneratedDataset:
    data = artifact.problem.model_dump(mode="json")
    config = data["constraint_config"]
    if mutation == "parameter":
        rule = next(r for r in config["soft"] if r["code"] == "TEACHER_MAX_GAP_RUN")
        rule["parameters"]["limit"] += 1
    elif mutation == "drop_rule":
        config["soft"] = config["soft"][1:]
    elif mutation == "priority":
        config["soft"][0]["priority"] = 3 if config["soft"][0]["priority"] != 3 else 1
    elif mutation == "occupied":
        config["occupied_work"] = config["occupied_work"][1:]
    elif mutation == "policy":
        config["policy_version"] = "0.3"
        config.pop("occupied_work", None)
    from tkb_core.contracts.input import ScheduleInput

    problem = ScheduleInput.model_validate(data)
    return g2.GeneratedDataset(
        problem,
        artifact.witness,
        artifact.provenance_problem,
        artifact.provenance_witness,
        artifact.manifest,
    )


@pytest.mark.parametrize("mutation", ["parameter", "drop_rule", "priority", "occupied", "policy"])
def test_mutated_rules_are_rejected(mutation: str) -> None:
    artifact = generate_dataset(10, "MIXED", 101, "SOFT")
    with pytest.raises(DatasetGenerationError):
        validate_dataset(_mutate(artifact, mutation))


def test_manifest_mutation_is_rejected() -> None:
    artifact = generate_dataset(10, "BASE", 101, "SOFT")
    changed = artifact.manifest.model_copy(update={"known_optimum": (0, 0, 0)})
    with pytest.raises(DatasetGenerationError):
        validate_dataset(
            g2.GeneratedDataset(artifact.problem, artifact.witness, None, None, changed)
        )


def test_witness_that_breaks_a_hard_rule_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    original = g2._rule_config

    def tighter(*args: Any, **kwargs: Any) -> ConstraintConfigV11:
        config = original(*args, **kwargs)
        hard = [
            r.model_copy(update={"parameters": {"limit": 0}})
            if r.code == "TEACHER_MAX_PERIODS_PER_DAY"
            else r
            for r in config.hard
        ]
        return config.model_copy(update={"hard": tuple(hard)})

    monkeypatch.setattr(g2, "_rule_config", tighter)
    with pytest.raises(DatasetGenerationError):
        generate_dataset(10, "BASE", 101, "HARD")


@pytest.mark.parametrize(
    ("size", "profile", "seed", "variant"),
    [
        (15, "BASE", 101, "SOFT"),
        (10, "ZERO", 101, "SOFT"),
        (10, "BASE", -1, "SOFT"),
        (10, "BASE", 101, "MIXED"),
        (True, "BASE", 101, "SOFT"),
    ],
)
def test_rejects_non_protocol_arguments(size: Any, profile: Any, seed: Any, variant: Any) -> None:
    with pytest.raises(DatasetGenerationError):
        generate_dataset(size, profile, seed, variant)


def test_bundle_roundtrip_and_tamper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(g2, "SIZES", (10,))
    monkeypatch.setattr(g2, "PROFILES", ("BASE", "UNSAT_CAPACITY"))
    monkeypatch.setattr(g2, "SEEDS", (101,))
    root = tmp_path / "bundle"
    manifest = write_bundle(root)
    assert manifest.protocol == "phase2-linux-v2"
    assert len(manifest.datasets) == 4
    assert verify_bundle(root) == manifest
    for entry in manifest.datasets:
        data = (root / entry.dataset_id / "manifest.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry.manifest_sha256
    with pytest.raises(FileExistsError):
        write_bundle(root)
    target = root / "c10-base-s101-soft" / "input.json"
    data = json.loads(target.read_text())
    data["constraint_config"]["soft"][0]["weight"] = 2
    target.write_text(json.dumps(data))
    with pytest.raises(DatasetGenerationError):
        verify_bundle(root)


def test_full_matrix_membership() -> None:
    ids = g2.expected_dataset_ids()
    assert len(ids) == 72
    assert "c40-unsat_capacity-s103-hard" in ids and "c10-base-s101-soft" in ids


def test_sources_record_v1_and_v2_generators() -> None:
    sources = g2._sources()
    assert (
        sources["generator_v1_source_sha256"]
        == hashlib.sha256(
            (ROOT / "benchmarks/generate_synthetic.py").read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
    )
    assert set(sources) == {
        "generator_source_sha256",
        "generator_v1_source_sha256",
        "core_source_sha256",
        "uv_lock_sha256",
    }


def test_no_solver_imports_in_generator() -> None:
    script = """
import builtins
original=builtins.__import__
def guarded(name,*args,**kwargs):
    blocked=('ortools','tkb_core.solver.cp_sat','tkb_core.solver.model_builder',
             'tkb_core.constraints.soft','tkb_core.constraints.gaps')
    if name.startswith(blocked):
        raise ImportError('forbidden solver import: '+name)
    return original(name,*args,**kwargs)
builtins.__import__=guarded
from benchmarks.generate_phase2 import generate_dataset,validate_dataset
artifact=generate_dataset(10,'MIXED',101,'HARD')
validate_dataset(artifact)
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
