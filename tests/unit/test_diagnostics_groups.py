"""Diagnostic group catalogue: stable IDs, deterministic order, granularity (Phase 3B)."""

import json
from pathlib import Path
from typing import Any

from tkb_core.contracts.input import ScheduleInput
from tkb_core.diagnostics.groups import enumerate_groups

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _keys(problem: ScheduleInput, granularity: str) -> list[tuple[str, str]]:
    return [(g.kind, g.id) for g in enumerate_groups(problem, granularity)]  # type: ignore[arg-type]


def test_input_10_model_groups() -> None:
    problem = ScheduleInput.model_validate_json((FIXTURES / "infeasible_teacher.json").read_text())
    assert _keys(problem, "MODEL") == [
        ("CLASS_OCCUPANCY", "demo-class-a"),
        ("CLASS_OCCUPANCY", "demo-class-b"),
        ("DEMAND", "demo-requirement-a"),
        ("DEMAND", "demo-requirement-b"),
        ("TEACHER_OCCUPANCY", "demo-teacher-a"),
        ("TEACHER_OCCUPANCY", "demo-teacher-b"),
    ]
    full = _keys(problem, "FULL")
    assert ("LOCK", "demo-requirement-a::1") in full
    assert set(_keys(problem, "MODEL")) < set(full)


def _hard_case() -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "school": {"school_id": "s", "academic_year": "y", "term": "t"},
        "time_slots": [
            {"id": f"{d}-AM-{p}", "day": d, "session": "AM", "period": p}
            for d in (1, 2)
            for p in (1, 2)
        ],
        "classes": [{"id": "c", "size": 10}, {"id": "idle-class"}],
        "teachers": [{"id": "t", "available_slot_ids": ["1-AM-1", "2-AM-1"]}, {"id": "u"}],
        "subjects": [{"id": "sub"}],
        "manage_rooms": True,
        "rooms": [{"id": "lab", "room_type": "lab", "capacity": 20, "available_slot_ids": []}],
        "teaching_requirements": [
            {
                "id": "r",
                "class_ids": ["c"],
                "teacher_ids": ["t"],
                "subject_id": "sub",
                "periods_per_cycle": 2,
                "room_required": True,
                "required_room_type": "lab",
            },
            {
                "id": "zero",
                "class_ids": ["c"],
                "teacher_ids": ["u"],
                "subject_id": "sub",
                "periods_per_cycle": 0,
            },
        ],
        "constraint_config": {
            "policy_version": "0.3",
            "hard": [
                {"id": "day", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 1}},
                {
                    "id": "avoid",
                    "code": "TEACHER_AVOID_SLOTS",
                    "parameters": {"slot_ids": ["1-AM-2"]},
                },
                {
                    "id": "off",
                    "code": "TEACHER_MAX_PERIODS_PER_SESSION",
                    "parameters": {"limit": 1, "session_ids": ["AM"]},
                    "enabled": False,
                },
            ],
            "soft": [],
        },
    }


def test_policy_hard_rules_rooms_and_availability() -> None:
    problem = ScheduleInput.model_validate(_hard_case())
    assert _keys(problem, "MODEL") == [
        ("CLASS_OCCUPANCY", "c"),
        ("DEMAND", "r"),
        ("HARD_RULE", "day"),
        ("ROOM_OCCUPANCY", "lab"),
        ("TEACHER_OCCUPANCY", "t"),
    ]
    assert _keys(problem, "FULL") == [
        ("CLASS_OCCUPANCY", "c"),
        ("DEMAND", "r"),
        ("HARD_PLACEMENT_RULE", "avoid"),
        ("HARD_RULE", "day"),
        ("ROOM_AVAILABILITY", "lab"),
        ("ROOM_OCCUPANCY", "lab"),
        ("TEACHER_AVAILABILITY", "t"),
        ("TEACHER_OCCUPANCY", "t"),
    ]


def test_order_is_independent_of_input_order() -> None:
    data = _hard_case()
    shuffled = json.loads(json.dumps(data))
    shuffled["teaching_requirements"].reverse()
    shuffled["constraint_config"]["hard"].reverse()
    shuffled["teachers"].reverse()
    for granularity in ("MODEL", "FULL"):
        assert _keys(ScheduleInput.model_validate(data), granularity) == _keys(
            ScheduleInput.model_validate(shuffled), granularity
        )
