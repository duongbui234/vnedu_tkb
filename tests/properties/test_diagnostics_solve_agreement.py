"""Independent cross-check of the diagnostic model's infeasible side (review F4).

The exhaustive oracle uses ``build_diagnostic_model`` itself as reference, so a shared mistake
in the copied S02/S03/S05/S06 bucket logic would go unseen. Here, with every group on, the
MODEL diagnostic model must agree with ``solve()`` (separate model code) on seeded inputs
carrying hard rules. The verifier's independent group catalogue is compared as well.
"""

import random
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.diagnostics.domains import build_domains
from tkb_core.diagnostics.groups import enumerate_groups
from tkb_core.diagnostics.model import build_diagnostic_model, solve_subset
from tkb_core.domain.errors import CoreError
from tkb_core.preprocessing.normalize import normalize
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.precheck_verifier import recompute_groups

RULES: list[dict[str, Any]] = [
    {
        "id": "sess",
        "code": "TEACHER_MAX_PERIODS_PER_SESSION",
        "parameters": {"limit": 1, "session_ids": ["AM"]},
    },
    {"id": "day", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 2}},
    {"id": "subj", "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY", "parameters": {"limit": 1}},
    {
        "id": "spread",
        "code": "SUBJECT_COMPONENT_DAY_SPREAD",
        "parameters": {"requirement_ids": ["r0"], "min_day_gap": 2},
    },
    {"id": "avoid", "code": "TEACHER_AVOID_SLOTS", "parameters": {"slot_ids": ["d1AMp1"]}},
    {
        "id": "win",
        "code": "TEACHER_PREFERRED_PERIOD_WINDOW",
        "parameters": {"first_period": 1, "last_period": 2, "session_ids": ["PM"]},
    },
]


def generate(seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    slots = [(d, s, p) for d in (1, 2, 3) for s in ("AM", "PM") for p in (1, 2, 3)]
    data: dict[str, Any] = {
        "schema_version": "1.1",
        "school": {"school_id": "s", "academic_year": "y", "term": "t"},
        "time_slots": [
            {"id": f"d{d}{s}p{p}", "day": d, "session": s, "period": p} for d, s, p in slots
        ],
        "classes": [{"id": f"c{i}"} for i in range(3)],
        "teachers": [{"id": f"t{i}"} for i in range(3)],
        "subjects": [{"id": "a"}, {"id": "b"}],
        "teaching_requirements": [],
        "constraint_config": {"policy_version": "0.3", "hard": [], "soft": []},
    }
    for i in range(rng.randint(3, 6)):
        n = rng.randint(1, 5)
        req: dict[str, Any] = {
            "id": f"r{i}",
            "class_ids": [f"c{rng.randrange(3)}"],
            "teacher_ids": [f"t{rng.randrange(3)}"],
            "subject_id": rng.choice("ab"),
            "periods_per_cycle": n,
        }
        if n >= 2 and rng.random() < 0.4:
            req["block_durations"] = [2] + [1] * (n - 2)
        data["teaching_requirements"].append(req)
    if rng.random() < 0.3:
        data["teachers"][0]["available_slot_ids"] = [
            f"d{d}{s}p{p}" for d, s, p in rng.sample(slots, 12)
        ]
    if rng.random() < 0.3:
        data["locked_assignments"] = [{"occurrence_id": "r1::1", "slot_id": "d2AMp2"}]
    data["constraint_config"]["hard"] = rng.sample(RULES, rng.randint(1, 3))
    return data


@pytest.mark.parametrize("seed", range(200))
def test_all_on_diagnostic_model_agrees_with_solve(seed: int) -> None:
    problem = ScheduleInput.model_validate(generate(seed))
    for granularity in ("MODEL", "FULL"):
        expected = {(g.kind, g.id) for g in enumerate_groups(problem, granularity)}
        assert recompute_groups(problem, granularity) == expected
    try:
        normalized = normalize(problem)
        domains = build_domains(
            normalized, expanded=False, max_placements=10**5, max_occupancy_terms=10**6
        )
    except CoreError:
        pytest.skip("refused before diagnosis")
    result = solve(problem, SolveOptions(time_limit_seconds=10.0))
    if result.status not in ("OPTIMAL", "FEASIBLE", "INFEASIBLE"):
        pytest.skip(f"solve() returned {result.status}")
    groups = enumerate_groups(problem, "MODEL")
    status = solve_subset(
        build_diagnostic_model(domains, groups), {(g.kind, g.id) for g in groups}, 10.0, 1
    ).status
    assert status == ("INFEASIBLE" if result.status == "INFEASIBLE" else "FEASIBLE")
