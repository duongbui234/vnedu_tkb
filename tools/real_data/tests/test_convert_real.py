"""Canonical timetable CSV -> Core input 1.1 and the real schedule as assignments."""

import random
from pathlib import Path
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.validation.independent_validator import validate_schedule
from tools.real_data import convert_real as cr

HEADER = "lop,thu,buoi,tiet,mon,ma_gv\n"


def _rows(text: str) -> list[cr.Row]:
    return cr.parse_timetable(HEADER + text)


def _conv(text: str, **kw: Any) -> cr.Conversion:
    return cr.convert(_rows(text), **kw)


# 6A1: Toan double on day 2 morning, Van single; 6A2: Toan by the same teacher on day 3.
BASIC = """6A1,2,S,1,Toán,GV01
6A1,2,S,2,Toán,GV01
6A1,2,S,3,Văn,GV02
6A1,3,S,1,Toán,GV01
6A2,3,S,2,Toán,GV01
6A2,2,S,1,Văn,GV02
"""


def test_session_aliases_and_errors() -> None:
    rows = _rows("6A1,2,Sáng,1,Toán,GV01\n6A1,2,chiều,1,Văn,GV02\n6A1,2,PM,2,Văn,GV02\n")
    assert [r.session for r in rows] == ["AM", "PM", "PM"]
    with pytest.raises(cr.TimetableError, match="line 2"):
        _rows("6A1,2,S,x,Toán,GV01\n")
    with pytest.raises(cr.TimetableError, match="buoi"):
        _rows("6A1,2,Trưa,1,Toán,GV01\n")
    with pytest.raises(cr.TimetableError, match="header"):
        cr.parse_timetable("lop,thu,tiet\n6A1,2,1\n")


def test_demand_slots_and_default_frame() -> None:
    conv = _conv(BASIC)
    problem = ScheduleInput.model_validate(conv.input)
    reqs = {r.id: r for r in problem.teaching_requirements}
    assert reqs["6A1|Toán|GV01"].periods_per_cycle == 3
    assert reqs["6A2|Toán|GV01"].periods_per_cycle == 1
    # Default frame: every observed day x observed session x periods 1..max of that session.
    assert sorted(s.id for s in problem.time_slots) == sorted(
        f"{d}-AM-{p}" for d in (2, 3) for p in (1, 2, 3)
    )
    assert {c.id for c in problem.classes} == {"6A1", "6A2"}
    assert {t.id for t in problem.teachers} == {"GV01", "GV02"}
    prepare(problem)  # Core accepts the converted input


def test_explicit_frame_adds_empty_slots() -> None:
    frame = cr.parse_frame(
        "thu,buoi,tiet\n" + "".join(f"{d},S,{p}\n" for d in (2, 3, 4) for p in (1, 2, 3, 4, 5))
    )
    problem = ScheduleInput.model_validate(_conv(BASIC, frame=frame).input)
    assert len(problem.time_slots) == 15


def test_blocks_follow_adjacent_periods_and_long_runs_split() -> None:
    conv = _conv(BASIC + "6A2,4,S,1,Văn,GV02\n6A2,4,S,2,Văn,GV02\n6A2,4,S,3,Văn,GV02\n")
    reqs = {r["id"]: r for r in conv.input["teaching_requirements"]}
    assert reqs["6A1|Toán|GV01"]["block_durations"] == [2, 1]
    assert reqs["6A2|Văn|GV02"]["block_durations"] == [1, 2, 1]
    assert conv.report["split_runs"] == [
        {"requirement": "6A2|Văn|GV02", "day": 4, "session": "AM", "length": 3}
    ]


def test_real_assignments_match_occurrences_and_are_valid() -> None:
    conv = _conv(BASIC)
    problem = ScheduleInput.model_validate(conv.input)
    previous = conv.previous
    assert previous["source_input_fingerprint"] == problem.fingerprint()
    got = {a["occurrence_id"]: a["slot_id"] for a in previous["assignments"]}
    assert got["6A1|Toán|GV01::1"] == "2-AM-1"  # the double, first chronologically
    assert got["6A1|Toán|GV01::2"] == "3-AM-1"
    from tkb_core.domain.models import ScheduleAssignment

    assignments = tuple(ScheduleAssignment.model_validate(a) for a in previous["assignments"])
    assert validate_schedule(problem, assignments).valid


def test_fixed_lessons_are_locked() -> None:
    conv = _conv(BASIC + "6A1,2,S,4,Chào cờ,GV03\n")
    locks = conv.input["locked_assignments"]
    assert locks == [{"occurrence_id": "6A1|Chào cờ|GV03::1", "slot_id": "2-AM-4"}]


def test_unsupported_cells_are_excluded_and_blocked() -> None:
    conv = _conv(
        BASIC
        + "6A2,2,S,4,Chào cờ,\n"  # no teacher
        + "6A1,3,S,3,Tin,GV05\n6A1,3,S,3,Tin,GV06\n"  # split group: two rows in one class cell
        + "6A1,2,S,5,Thể dục,GV07\n6A2,2,S,5,Thể dục,GV07\n"  # combined classes
    )
    reasons = sorted((e["reason"], e["lop"]) for e in conv.report["excluded"])
    assert reasons == [
        ("CLASS_SLOT_MULTI", "6A1"),
        ("CLASS_SLOT_MULTI", "6A1"),
        ("NO_TEACHER", "6A2"),
        ("TEACHER_SLOT_MULTI", "6A1"),
        ("TEACHER_SLOT_MULTI", "6A2"),
    ]
    problem = ScheduleInput.model_validate(conv.input)
    classes = {c.id: c for c in problem.classes}
    teachers = {t.id: t for t in problem.teachers}
    assert classes["6A2"].available_slot_ids is not None
    assert "2-AM-4" not in classes["6A2"].available_slot_ids
    assert "3-AM-3" not in (classes["6A1"].available_slot_ids or ())
    assert "2-AM-5" not in (teachers["GV07"].available_slot_ids or ())
    assert conv.report["excluded_periods"] == 5
    assert all("Tin" not in r.subject_id for r in problem.teaching_requirements)


def test_measurement_scale_rules() -> None:
    conv = _conv(BASIC)
    soft = {r["id"]: r for r in conv.input["constraint_config"]["soft"]}
    assert conv.input["constraint_config"]["policy_version"] == "0.4"
    assert soft["S06-ALL"]["parameters"] == {"limit": 2} and soft["S06-ALL"]["priority"] == 1
    s02 = soft["S02-GV01"]
    assert s02["parameters"] == {"limit": 4, "session_ids": ["AM"]} and s02["priority"] == 1
    assert soft["S03-GV01"]["parameters"] == {"limit": 5} and soft["S03-GV01"]["priority"] == 2
    assert soft["S09-GV01"]["parameters"] == {"limit": 1, "session_ids": ["AM"]}
    assert soft["S08-GV01"]["priority"] == 3 and soft["S11-GV01"]["priority"] == 3
    # Spread only for requirements with at least two components.
    spread = [r for r in soft.values() if r["code"] == "SUBJECT_COMPONENT_DAY_SPREAD"]
    assert [r["parameters"] for r in spread] == [
        {"requirement_ids": ["6A1|Toán|GV01"], "min_day_gap": 1}
    ]
    assert all(r["weight"] == 1 for r in soft.values())


def test_cli_writes_outputs(tmp_path: Path) -> None:
    src = tmp_path / "tkb.csv"
    src.write_text(HEADER + BASIC, encoding="utf-8")
    out = tmp_path / "out"
    assert cr.main([str(src), "--output", str(out), "--school", "SCH01"]) == 0
    assert {p.name for p in out.iterdir()} == {
        "input.json",
        "real-assignments.json",
        "conversion-report.json",
    }
    with pytest.raises(SystemExit):
        cr.main([str(src), "--output", str(out), "--school", "SCH01"])  # never overwrites


def test_round_trip_from_a_core_schedule() -> None:
    """A Core-made schedule exported as a 'school file' converts back to the same lessons."""
    from tkb_core.solver.cp_sat import solve
    from tkb_core.solver.options import SolveOptions

    rng = random.Random(3)
    slots = [
        {"id": f"{d}-{s}-{p}", "day": d, "session": s, "period": p}
        for d in (2, 3, 4)
        for s in ("AM",)
        for p in range(1, 6)
    ]
    reqs: list[dict[str, Any]] = []
    for c in ("6A1", "6A2", "6A3"):
        for j, (sub, t) in enumerate(
            (("Toán", "GV01"), ("Văn", "GV02"), ("Anh", "GV03"), ("Lý", "GV04"))
        ):
            n = (4, 4, 3, 2)[j]
            reqs.append(
                {
                    "id": f"{c}-{sub}",
                    "class_ids": [c],
                    "teacher_ids": [t if c != "6A3" else f"{t}b"],
                    "subject_id": sub,
                    "periods_per_cycle": n,
                }
            )
    rng.shuffle(reqs)
    data = {
        "schema_version": "1.1",
        "school": {"school_id": "x", "academic_year": "y", "term": "t"},
        "time_slots": slots,
        "classes": [{"id": c} for c in ("6A1", "6A2", "6A3")],
        "teachers": [{"id": t} for t in sorted({r["teacher_ids"][0] for r in reqs})],
        "subjects": [{"id": s} for s in ("Toán", "Văn", "Anh", "Lý")],
        "teaching_requirements": reqs,
        "constraint_config": {"policy_version": "0.1", "hard": [], "soft": []},
    }
    original = ScheduleInput.model_validate(data)
    result = solve(original, SolveOptions(time_limit_seconds=10.0))
    assert result.status in ("FEASIBLE", "OPTIMAL")
    rows = cr.export_rows(original, result.assignments)
    conv = cr.convert(cr.parse_timetable(cr.format_timetable(rows)))
    problem = ScheduleInput.model_validate(conv.input)
    from tkb_core.domain.models import ScheduleAssignment

    back = tuple(ScheduleAssignment.model_validate(a) for a in conv.previous["assignments"])
    assert validate_schedule(problem, back).valid
    assert sorted(cr.export_rows(problem, back)) == sorted(rows)
    assert conv.report["excluded"] == []
