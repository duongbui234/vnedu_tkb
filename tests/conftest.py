"""Synthetic domain fixtures, unrelated to any vnEdu API schema."""

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def problem_data() -> dict[str, Any]:
    return json.loads((Path(__file__).parent / "fixtures/feasible_small.json").read_text())


@pytest.fixture
def quality_data() -> dict[str, Any]:
    return json.loads(
        (Path(__file__).parent / "fixtures/quality/teacher_preferences.json").read_text()
    )


@pytest.fixture
def quality_case() -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "school": {"school_id": "demo", "academic_year": "demo", "term": "demo"},
        "time_slots": [
            {"id": f"{d}-{s}-{p}", "day": d, "session": s, "period": p}
            for d in (1, 2)
            for s in ("AM", "PM")
            for p in range(1, 5)
        ],
        "classes": [{"id": "c"}],
        "teachers": [{"id": "t"}],
        "subjects": [{"id": "sub"}],
        "teaching_requirements": [
            {
                "id": "r",
                "class_ids": ["c"],
                "teacher_ids": ["t"],
                "subject_id": "sub",
                "periods_per_cycle": 4,
                "block_durations": [2, 1, 1],
            }
        ],
        "constraint_config": {"policy_version": "0.1", "hard": [], "soft": []},
    }


@pytest.fixture
def ordering_case(quality_case: dict[str, Any]) -> dict[str, Any]:
    """Three interchangeable synthetic singles and all four resource-only preferences."""
    quality_case["time_slots"] = quality_case["time_slots"][:4]
    quality_case["teaching_requirements"][0].update(periods_per_cycle=3, block_durations=[1, 1, 1])
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "avoid",
            "code": "TEACHER_AVOID_SLOTS",
            "parameters": {"slot_ids": ["1-AM-1"]},
            "priority": 1,
            "weight": 1,
        },
        {
            "id": "session",
            "code": "TEACHER_MAX_PERIODS_PER_SESSION",
            "parameters": {"limit": 2, "session_ids": ["AM"]},
            "priority": 1,
            "weight": 1,
        },
        {
            "id": "day",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 2},
            "priority": 2,
            "weight": 1,
        },
        {
            "id": "window",
            "code": "TEACHER_PREFERRED_PERIOD_WINDOW",
            "parameters": {"first_period": 2, "last_period": 3, "session_ids": ["AM"]},
            "priority": 3,
            "weight": 1,
        },
    ]
    return quality_case


@pytest.fixture
def hard_case(quality_case: dict[str, Any]) -> dict[str, Any]:
    """Policy 0.2 input: same synthetic calendar, explicit hard variants enabled later."""
    quality_case["constraint_config"]["policy_version"] = "0.2"
    return quality_case


@pytest.fixture
def dist_case(quality_case: dict[str, Any]) -> dict[str, Any]:
    """Policy 0.3 input over three days, for subject-distribution rules (Phase 2C-1)."""
    quality_case["time_slots"] = [
        {"id": f"{d}-{s}-{p}", "day": d, "session": s, "period": p}
        for d in (1, 2, 3)
        for s in ("AM", "PM")
        for p in range(1, 5)
    ]
    quality_case["constraint_config"]["policy_version"] = "0.3"
    return quality_case


@pytest.fixture
def gap_case(quality_case: dict[str, Any]) -> dict[str, Any]:
    """Policy 0.4 input for restricted-slot, gap and free-time rules (Phase 2C-2)."""
    quality_case["constraint_config"]["policy_version"] = "0.4"
    return quality_case


def _diagnostic_base(slot_ids: list[tuple[int, int]]) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "school": {"school_id": "s", "academic_year": "y", "term": "t"},
        "time_slots": [
            {"id": f"d{d}p{p}", "day": d, "session": "AM", "period": p} for d, p in slot_ids
        ],
        "classes": [{"id": "c1", "size": 10}, {"id": "c2", "size": 10}],
        "teachers": [{"id": "t1"}, {"id": "t2"}],
        "subjects": [{"id": "sub"}],
        "teaching_requirements": [],
        "constraint_config": {"policy_version": "0.3", "hard": [], "soft": []},
    }


def _req(rid: str, cls: str, teacher: str, periods: int, **extra: Any) -> dict[str, Any]:
    return {
        "id": rid,
        "class_ids": [cls],
        "teacher_ids": [teacher],
        "subject_id": "sub",
        "periods_per_cycle": periods,
        **extra,
    }


@pytest.fixture
def triangle_case() -> dict[str, Any]:
    """Three single lessons pairwise sharing class c1, teacher t1 or the only lab; 2 slots.

    Every counting precheck passes, yet three mutually exclusive lessons need 3 slots.
    Expected conflict: DEMAND r1-r3 + CLASS_OCCUPANCY c1 + TEACHER_OCCUPANCY t1 +
    ROOM_OCCUPANCY lab.
    """
    data = _diagnostic_base([(1, 1), (1, 2)])
    data["manage_rooms"] = True
    data["rooms"] = [{"id": "lab", "room_type": "lab", "capacity": 30}]
    lab = {"room_required": True, "required_room_type": "lab"}
    data["teaching_requirements"] = [
        _req("r1", "c1", "t1", 1),
        _req("r2", "c1", "t2", 1, **lab),
        _req("r3", "c2", "t1", 1, **lab),
    ]
    return data


@pytest.fixture
def spread_case() -> dict[str, Any]:
    """S05 hard puts r's two lessons on different days; day 2's only slot is t1's lock.

    Expected MODEL conflict: DEMAND r + DEMAND r3 + HARD_RULE spread + TEACHER_OCCUPANCY t1
    (the lock is background at MODEL; at FULL it joins as LOCK r3::1).
    """
    data = _diagnostic_base([(1, 1), (1, 2), (2, 1)])
    data["teaching_requirements"] = [_req("r", "c1", "t1", 2), _req("r3", "c2", "t1", 1)]
    data["locked_assignments"] = [{"occurrence_id": "r3::1", "slot_id": "d2p1"}]
    data["constraint_config"]["hard"] = [
        {
            "id": "spread",
            "code": "SUBJECT_COMPONENT_DAY_SPREAD",
            "parameters": {"requirement_ids": ["r"], "min_day_gap": 1},
        }
    ]
    return data
