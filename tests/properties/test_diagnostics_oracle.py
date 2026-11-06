"""Exhaustive oracle for Phase 3B diagnostics (Task 7).

Tiny seeded inputs; for every subset of diagnostic groups the feasibility is decided by a
reference model **without** B11 ordering. Checks: (a) a reported subset is infeasible, (b) a
``minimal_proved`` subset is a true MUS, (c) B11 ordering never changes the status of any
subset, (d) NOT_INFEASIBLE iff the full input is feasible; precheck proofs only on
infeasible inputs. A diversity check makes sure every outcome kind is exercised.
"""

import random
from collections import Counter
from itertools import combinations
from typing import Any

import pytest

from tkb_core.contracts.diagnostics import ExplainOptions
from tkb_core.contracts.input import ScheduleInput
from tkb_core.diagnostics.domains import build_domains
from tkb_core.diagnostics.groups import enumerate_groups
from tkb_core.diagnostics.model import build_diagnostic_model, solve_subset
from tkb_core.diagnostics.pipeline import explain_infeasibility
from tkb_core.preprocessing.normalize import normalize

SEEDS = range(60)
MAX_GROUPS = 8
OUTCOMES: Counter[str] = Counter()


def _base(slots: list[tuple[int, int]]) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "school": {"school_id": "s", "academic_year": "y", "term": "t"},
        "time_slots": [
            {"id": f"d{d}p{p}", "day": d, "session": "AM", "period": p} for d, p in slots
        ],
        "classes": [{"id": "c1", "size": 10}, {"id": "c2", "size": 10}],
        "teachers": [{"id": "t1"}, {"id": "t2"}],
        "subjects": [{"id": "sub"}],
        "teaching_requirements": [],
        "constraint_config": {"policy_version": "0.3", "hard": [], "soft": []},
    }


def _req(rid: str, cls: str, teacher: str, periods: int, lab: bool = False) -> dict[str, Any]:
    req: dict[str, Any] = {
        "id": rid,
        "class_ids": [cls],
        "teacher_ids": [teacher],
        "subject_id": "sub",
        "periods_per_cycle": periods,
    }
    if lab:
        req.update(room_required=True, required_room_type="lab")
    return req


def generate(seed: int) -> dict[str, Any]:
    """Mix of a triangle motif, an S05+lock motif and random inputs, all perturbed."""
    rng = random.Random(seed)
    kind = seed % 3
    if kind == 0:  # class/teacher/lab triangle on two slots (no counting proof)
        data = _base([(1, 1), (1, 2)])
        data["manage_rooms"] = True
        data["rooms"] = [{"id": "lab", "room_type": "lab", "capacity": 30}]
        data["teaching_requirements"] = [
            _req("r0", "c1", "t1", 1),
            _req("r1", "c1", "t2", 1, lab=True),
            _req("r2", "c2", "t1", 1, lab=True),
        ]
        if rng.random() < 0.3:
            data["time_slots"].append({"id": "d2p1", "day": 2, "session": "AM", "period": 1})
        if rng.random() < 0.3:
            data["teaching_requirements"][rng.randrange(3)]["teacher_ids"] = ["t2"]
        if rng.random() < 0.3:
            data["locked_assignments"] = [{"occurrence_id": "r0::1", "slot_id": "d1p1"}]
    elif kind == 1:  # S05 spread blocked by a locked lesson of the same teacher
        data = _base([(1, 1), (1, 2), (2, 1)])
        data["teaching_requirements"] = [_req("r0", "c1", "t1", 2), _req("r1", "c2", "t1", 1)]
        data["locked_assignments"] = [{"occurrence_id": "r1::1", "slot_id": "d2p1"}]
        data["constraint_config"]["hard"] = [
            {
                "id": "spread",
                "code": "SUBJECT_COMPONENT_DAY_SPREAD",
                "parameters": {"requirement_ids": ["r0"], "min_day_gap": 1},
            }
        ]
        if rng.random() < 0.3:
            data["time_slots"].append({"id": "d2p2", "day": 2, "session": "AM", "period": 2})
        if rng.random() < 0.3:
            data["teaching_requirements"][1]["teacher_ids"] = ["t2"]
        if rng.random() < 0.3:
            data["teachers"][0]["available_slot_ids"] = ["d1p1", "d2p1"]
    else:  # random
        slots = [(1, 1), (1, 2), (2, 1)]
        ids = [f"d{d}p{p}" for d, p in slots]
        data = _base(slots)
        rooms = rng.random() < 0.5
        if rooms:
            data["manage_rooms"] = True
            data["rooms"] = [{"id": "lab", "room_type": "lab", "capacity": 30}]
        for i in range(rng.randint(2, 3)):
            data["teaching_requirements"].append(
                _req(
                    f"r{i}",
                    rng.choice(["c1", "c2"]),
                    rng.choice(["t1", "t2"]),
                    rng.choice([1, 1, 2]),
                    lab=rooms and rng.random() < 0.5,
                )
            )
        if rng.random() < 0.3:
            rng.choice(data["teachers"])["available_slot_ids"] = rng.sample(ids, 2)
        if rng.random() < 0.3:
            data["locked_assignments"] = [{"occurrence_id": "r0::1", "slot_id": rng.choice(ids)}]
        if rng.random() < 0.3:
            data["constraint_config"]["hard"] = [
                {"id": "day", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 1}}
            ]
    return data


def reference(problem: ScheduleInput, granularity: str) -> tuple[dict[frozenset[Any], str], Any]:
    domains = build_domains(
        normalize(problem),
        expanded=granularity == "FULL",
        max_placements=10**5,
        max_occupancy_terms=10**6,
    )
    groups = enumerate_groups(problem, granularity)  # type: ignore[arg-type]
    keys = [(g.kind, g.id) for g in groups]
    plain = build_diagnostic_model(domains, groups, order_interchangeable=False)
    ordered = build_diagnostic_model(domains, groups)
    status: dict[frozenset[Any], str] = {}
    for size in range(len(keys) + 1):
        for subset in combinations(keys, size):
            ref = solve_subset(plain, set(subset), 10.0, 1).status
            assert ref != "UNKNOWN"
            assert solve_subset(ordered, set(subset), 10.0, 1).status == ref, (
                "B11 ordering changed the status of a subset",
                subset,
            )
            status[frozenset(subset)] = ref
    return status, keys


@pytest.mark.parametrize("granularity", ["MODEL", "FULL"])
@pytest.mark.parametrize("seed", SEEDS)
def test_oracle(seed: int, granularity: str) -> None:
    problem = ScheduleInput.model_validate(generate(seed))
    if len(enumerate_groups(problem, granularity)) > MAX_GROUPS:  # type: ignore[arg-type]
        OUTCOMES["SKIPPED_SIZE"] += 1
        pytest.skip("too many groups for exhaustive enumeration")
    report = explain_infeasibility(
        problem,
        ExplainOptions(time_limit_seconds=20.0, seed=seed, granularity=granularity),  # type: ignore[arg-type]
    )
    status, keys = reference(problem, granularity)
    everything = status[frozenset(keys)]
    OUTCOMES[report.status] += 1
    if report.status == "NOT_INFEASIBLE":
        assert everything == "FEASIBLE"
    elif report.status == "PRECHECK_PROOF":
        assert everything == "INFEASIBLE"
    else:
        assert report.status == "CORE_SUBSET", report.status
        assert everything == "INFEASIBLE"
        chosen = frozenset((g.kind, g.id) for g in report.subset)
        assert status[chosen] == "INFEASIBLE"
        assert report.minimal_proved, "tiny instances must finish deletion"
        for member in chosen:
            assert status[chosen - {member}] == "FEASIBLE", "not a MUS"


def test_oracle_diversity() -> None:
    """Runs last in this module: every outcome kind must have been exercised."""
    if not OUTCOMES:
        pytest.skip("oracle cases not run in this session")
    for kind in ("PRECHECK_PROOF", "CORE_SUBSET", "NOT_INFEASIBLE"):
        assert OUTCOMES[kind] >= 3, OUTCOMES
