"""Phase 3C inputs: dataset selection, seeded noise N1-N4, precheck labelling (Task 1)."""

import json
from typing import Any

import pytest

from benchmarks import generate_phase2 as g2
from benchmarks import generate_phase3c as g3
from tkb_core.contracts.input import ScheduleInput


def test_dataset_selection_matches_plan() -> None:
    base = g3.base_dataset_ids()
    assert len(base) == 18 == len(set(base))
    assert all("-s101-" in i for i in base)
    assert {i.split("-")[1] for i in base} == {"base", "mixed", "tight"}
    unsat = g3.unsat_dataset_ids()
    assert len(unsat) == 18 and all("unsat_capacity" in i for i in unsat)
    assert set(base) | set(unsat) <= g2.expected_dataset_ids()
    assert g3.base_dataset_ids(smoke=True) == (
        g2.dataset_id(10, "BASE", 101, "HARD"),
        g2.dataset_id(10, "BASE", 101, "SOFT"),
    )


@pytest.fixture(scope="module")
def dataset() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    generated = g2.generate_dataset(10, "BASE", 101, "SOFT")
    assert generated.witness is not None
    data = generated.problem.model_dump(mode="json")
    previous = [a.model_dump(mode="json") for a in generated.witness.assignments]
    return data, previous


def _derive(dataset: Any, noise: str) -> g3.NoisyInput:
    data, previous = dataset
    return g3.derive_noise(data, previous, "c10-base-s101-soft", noise)


@pytest.mark.parametrize("noise", g3.NOISES)
def test_noise_is_deterministic_and_valid(dataset: Any, noise: str) -> None:
    first, second = _derive(dataset, noise), _derive(dataset, noise)
    assert json.dumps(first.data, sort_keys=True) == json.dumps(second.data, sort_keys=True)
    assert first.description == second.description
    assert first.data != dataset[0]
    ScheduleInput.model_validate(first.data)
    assert first.label in ("GROUND_TRUTH_UNKNOWN", "EXPECTED_INFEASIBLE")
    assert 0 <= first.candidate < g3.MAX_CANDIDATES


def test_n1_removes_a_day_the_teacher_teaches(dataset: Any) -> None:
    data, previous = dataset
    noisy = _derive(dataset, "N1")
    teacher, day = noisy.description["teacher"], noisy.description["day"]
    slots = {s["id"]: s for s in data["time_slots"]}
    assert any(
        a["teacher_ids"] == [teacher] and slots[a["slot_id"]]["day"] == day for a in previous
    )
    allowed = next(t for t in noisy.data["teachers"] if t["id"] == teacher)["available_slot_ids"]
    assert allowed and all(slots[s]["day"] != day for s in allowed)


def test_n2_moves_one_requirement_to_another_teacher(dataset: Any) -> None:
    data, _ = dataset
    noisy = _derive(dataset, "N2")
    before = {r["id"]: r["teacher_ids"] for r in data["teaching_requirements"]}
    after = {r["id"]: r["teacher_ids"] for r in noisy.data["teaching_requirements"]}
    changed = [i for i in before if before[i] != after[i]]
    assert changed == [noisy.description["requirement"]]
    assert after[changed[0]] == [noisy.description["new_teacher"]]


def test_n3_adds_and_drops_one_period(dataset: Any) -> None:
    data, _ = dataset
    noisy = _derive(dataset, "N3")
    before = {r["id"]: r["periods_per_cycle"] for r in data["teaching_requirements"]}
    after = {r["id"]: r["periods_per_cycle"] for r in noisy.data["teaching_requirements"]}
    added, removed = noisy.description["added"], noisy.description["removed"]
    assert added != removed
    assert after[added] == before[added] + 1 and after[removed] == before[removed] - 1
    assert sum(after.values()) == sum(before.values())
    source = next(r for r in data["teaching_requirements"] if r["id"] == removed)
    count = len(source["block_durations"]) if source.get("block_durations") else before[removed]
    assert noisy.description["dropped_occurrence"] == f"{removed}::{count}"


def test_n4_locks_two_occurrences_away_from_their_previous_slot(dataset: Any) -> None:
    _, previous = dataset
    noisy = _derive(dataset, "N4")
    locks = noisy.data["locked_assignments"]
    old = {a["occurrence_id"]: a["slot_id"] for a in previous}
    assert len(locks) == 2 and len({lock["occurrence_id"] for lock in locks}) == 2
    assert all(old[lock["occurrence_id"]] != lock["slot_id"] for lock in locks)


def _tiny() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """One teacher, one class, 2 lessons on 2 slots: removing a day leaves 1 slot for 2."""
    data = {
        "schema_version": "1.1",
        "school": {"school_id": "s", "academic_year": "y", "term": "t"},
        "time_slots": [
            {"id": "d1", "day": 1, "session": "AM", "period": 1},
            {"id": "d2", "day": 2, "session": "AM", "period": 1},
        ],
        "classes": [{"id": "c"}],
        "teachers": [{"id": "t"}],
        "subjects": [{"id": "x"}],
        "teaching_requirements": [
            {
                "id": "r",
                "class_ids": ["c"],
                "teacher_ids": ["t"],
                "subject_id": "x",
                "periods_per_cycle": 2,
            }
        ],
        "constraint_config": {"policy_version": "0.4", "hard": [], "soft": []},
    }
    previous = [
        {"occurrence_id": "r::1", "slot_id": "d1", "class_ids": ["c"], "teacher_ids": ["t"]},
        {"occurrence_id": "r::2", "slot_id": "d2", "class_ids": ["c"], "teacher_ids": ["t"]},
    ]
    return data, previous


def test_noise_with_counting_proof_is_labelled_after_all_candidates() -> None:
    data, previous = _tiny()
    noisy = g3.derive_noise(data, previous, "tiny", "N1")
    assert noisy.label == "EXPECTED_INFEASIBLE"
    assert noisy.candidate == g3.MAX_CANDIDATES - 1
    assert noisy.proofs == ("PC_RESOURCE_CAPACITY", "PC_RESOURCE_CAPACITY")


def test_requests_are_explicit() -> None:
    request = g3.repair_request("AFTER_QUALITY", hint=False)
    assert request == {
        "schema_version": "1.0",
        "change_order": "AFTER_QUALITY",
        "max_changes": None,
        "change_scope": None,
        "use_previous_as_hint": False,
    }
