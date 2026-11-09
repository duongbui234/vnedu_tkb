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


CELLS_HEADER = "lop,thu,buoi,tiet\n"


def _cells(text: str) -> dict[str, set[cr.Slot]]:
    return cr.parse_class_cells(CELLS_HEADER + text)


def _morning(lop: str, days: tuple[int, ...]) -> str:
    return "".join(f"{lop},{d},S,{p}\n" for d in days for p in (1, 2, 3))


def test_class_cells_limit_each_class_to_its_cells() -> None:
    # 6A1 may use day 2-3 mornings; 6A2 only day 2 morning plus day 3 period 2 (its lesson).
    cells = _cells(_morning("6A1", (2, 3)) + _morning("6A2", (2,)) + "6A2,3,S,2\n")
    conv = _conv(BASIC, class_cells=cells)
    problem = ScheduleInput.model_validate(conv.input)
    classes = {c.id: c for c in problem.classes}
    assert classes["6A1"].available_slot_ids is None  # every frame slot is open
    assert sorted(classes["6A2"].available_slot_ids or ()) == sorted(
        ["2-AM-1", "2-AM-2", "2-AM-3", "3-AM-2"]
    )
    report = conv.report["class_availability"]
    assert report == {
        "source": "class-cells",
        "open_class_slots": 6 + 4,
        "frame_class_slots": 12,
        "cells_outside_frame": 0,
    }
    # The real schedule stays hard-valid on the restricted calendar.
    from tkb_core.domain.models import ScheduleAssignment

    real = tuple(ScheduleAssignment.model_validate(a) for a in conv.previous["assignments"])
    assert validate_schedule(problem, real).valid
    prepare(problem)


def test_class_cells_errors_and_frame_default() -> None:
    assert _conv(BASIC).report["class_availability"]["source"] == "frame"
    with pytest.raises(cr.TimetableError, match="missing"):
        _conv(BASIC, class_cells=_cells(_morning("6A1", (2, 3))))
    # 6A2's day-3 lesson lies outside its cells.
    with pytest.raises(cr.TimetableError, match="outside its class cells"):
        _conv(BASIC, class_cells=_cells(_morning("6A1", (2, 3)) + _morning("6A2", (2,))))
    # Cells beyond the frame are ignored and counted.
    extra = _cells(_morning("6A1", (2, 3)) + _morning("6A2", (2, 3)) + "6A2,5,C,1\n")
    assert _conv(BASIC, class_cells=extra).report["class_availability"]["cells_outside_frame"] == 1
    with pytest.raises(cr.TimetableError, match="line 2"):
        _cells("6A1,2,S,0\n")


def test_cli_reads_class_cells(tmp_path: Path) -> None:
    src = tmp_path / "tkb.csv"
    src.write_text(HEADER + BASIC, encoding="utf-8")
    cells = tmp_path / "class-cells.csv"
    cells.write_text(CELLS_HEADER + _morning("6A1", (2, 3)) + _morning("6A2", (3,)) + "6A2,2,S,1\n")
    out = tmp_path / "out"
    assert cr.main([str(src), "--output", str(out), "--class-cells", str(cells)]) == 0
    data = ScheduleInput.model_validate_json((out / "input.json").read_text(encoding="utf-8"))
    assert {c.id for c in data.classes if c.available_slot_ids is not None} == {"6A2"}


TEACHER_HEADER = "ma_gv,thu,buoi,tiet,loai\n"


def test_teacher_cells_hard_and_soft() -> None:
    # GV01 meets on day 2 P3 (hard) and asks off day 3 P3 (nghi); GV02 has a 'ban' cell and an
    # unknown code. GV02 teaches 6A1 on 2-AM-3, so a hard 'ban' would hit a real lesson.
    cells = cr.parse_teacher_cells(
        TEACHER_HEADER
        + "GV01,2,S,3,hop\nGV01,3,S,3,nghi\nGV02,2,S,3,ban\nGV02,3,S,2,ma_1234\nGV09,2,S,1,hop\n"
    )
    conv = _conv(BASIC, teacher_cells=cells)
    problem = ScheduleInput.model_validate(conv.input)
    teachers = {t.id: t for t in problem.teachers}
    assert "2-AM-3" not in (teachers["GV01"].available_slot_ids or ())
    assert teachers["GV02"].available_slot_ids is None
    soft = {r["id"]: r for r in conv.input["constraint_config"]["soft"]}
    assert soft["S01-GV01"]["parameters"] == {"slot_ids": ["3-AM-3"]}
    assert soft["S01-GV01"]["priority"] == 2 and soft["S01-GV01"]["code"] == "TEACHER_AVOID_SLOTS"
    assert soft["S01-GV02"]["parameters"] == {"slot_ids": ["2-AM-3"]}
    report = conv.report["teacher_availability"]
    assert report["hard_hop"] == 1 and report["soft_nghi"] == 1 and report["soft_ban"] == 1
    assert report["ignored_ma_1234"] == 1 and report["teachers_without_work"] == 1
    assert report["real_lessons_on_soft_cells"] == 1  # GV02 teaches on its 'ban' cell
    prepare(problem)

    strict = _conv(BASIC, teacher_cells=cells, hard_kinds=("hop", "nghi", "ban"))
    strict_report = strict.report["teacher_availability"]
    assert strict_report["real_lessons_on_hard_cells"] == 1
    assert not any(
        r["code"] == "TEACHER_AVOID_SLOTS" for r in strict.input["constraint_config"]["soft"]
    )
    with pytest.raises(cr.TimetableError, match="unknown hard"):
        _conv(BASIC, teacher_cells=cells, hard_kinds=("hop", "vang"))


def test_locks_fix_the_covering_lesson_and_win_over_hard_cells() -> None:
    locks = cr.parse_locks("ma_gv,thu,buoi,tiet\nGV01,2,S,2\nGV01,4,S,1\nGV02,2,S,3\n")
    # GV01 2-AM-2 is the second period of the 6A1 Toán double that starts at 2-AM-1.
    cells = cr.parse_teacher_cells(TEACHER_HEADER + "GV02,2,S,3,hop\n")
    conv = _conv(BASIC, locked_cells=locks, teacher_cells=cells)
    assert sorted((a["occurrence_id"], a["slot_id"]) for a in conv.input["locked_assignments"]) == [
        ("6A1|Toán|GV01::1", "2-AM-1"),
        ("6A1|Văn|GV02::1", "2-AM-3"),
    ]
    assert conv.report["locks"] == {"given": 3, "locked_occurrences": 2, "on_empty_cell": 1}
    report = conv.report["teacher_availability"]
    assert report["hard_cells_kept_for_locks"] == 1 and report.get("hard_hop", 0) == 0
    problem = ScheduleInput.model_validate(conv.input)
    from tkb_core.domain.models import ScheduleAssignment

    real = tuple(ScheduleAssignment.model_validate(a) for a in conv.previous["assignments"])
    assert validate_schedule(problem, real).valid
    prepare(problem)


def test_soft_cells_outside_the_frame_add_no_empty_rule() -> None:
    cells = cr.parse_teacher_cells(TEACHER_HEADER + "GV01,6,C,5,nghi\n")
    conv = _conv(BASIC, teacher_cells=cells)
    assert not any(
        r["code"] == "TEACHER_AVOID_SLOTS" for r in conv.input["constraint_config"]["soft"]
    )
    assert conv.report["teacher_availability"]["outside_frame"] == 1
    ScheduleInput.model_validate(conv.input)


LIMIT_HEADER = "ma_gv,max_tiet_buoi,max_tiet_ngay\n"


def test_teacher_limits_replace_the_common_load_rules() -> None:
    # GV01 set both limits in STKB; GV02 set none: no S02/S03 for GV02, other rules stay common.
    limits = cr.parse_teacher_limits(LIMIT_HEADER + "GV01,3,6\nGV02,,\nGV09,2,\n")
    assert limits == {"GV01": (3, 6), "GV02": (None, None), "GV09": (2, None)}
    conv = _conv(BASIC, teacher_limits=limits)
    soft = {r["id"]: r for r in conv.input["constraint_config"]["soft"]}
    assert soft["S02-GV01"]["parameters"] == {"limit": 3, "session_ids": ["AM"]}
    assert soft["S02-GV01"]["priority"] == 1
    assert soft["S03-GV01"]["parameters"] == {"limit": 6} and soft["S03-GV01"]["priority"] == 2
    assert "S02-GV02" not in soft and "S03-GV02" not in soft
    assert soft["S09-GV02"]["parameters"] == {"limit": 1, "session_ids": ["AM"]}
    assert soft["S06-ALL"]["parameters"] == {"limit": 2}
    scale = conv.report["scale"]["teacher_limits"]
    assert scale == {
        "source": "teacher-limits",
        "S02_teachers": 1,
        "S03_teachers": 1,
        "S02_limits": {"3": 1},
        "S03_limits": {"6": 1},
        "teachers_missing": 0,
    }
    ScheduleInput.model_validate(conv.input)
    common = _conv(BASIC).report["scale"]["teacher_limits"]
    assert common == {"source": "common"}


def test_teacher_limits_errors_and_missing_teachers() -> None:
    with pytest.raises(cr.TimetableError, match="at least 1"):
        cr.parse_teacher_limits(LIMIT_HEADER + "GV01,0,\n")
    with pytest.raises(cr.TimetableError, match="header"):
        cr.parse_teacher_limits("ma_gv,max\nGV01,3\n")
    conv = _conv(BASIC, teacher_limits={"GV01": (4, None)})
    assert conv.report["scale"]["teacher_limits"]["teachers_missing"] == 1  # GV02: no limits


def test_avoid_priority_moves_teacher_requests() -> None:
    cells = cr.parse_teacher_cells(TEACHER_HEADER + "GV01,3,S,3,nghi\n")
    conv = _conv(BASIC, teacher_cells=cells, avoid_priority=1)
    soft = {r["id"]: r for r in conv.input["constraint_config"]["soft"]}
    assert soft["S01-GV01"]["priority"] == 1
    assert conv.report["teacher_availability"]["soft_priority"] == 1
    with pytest.raises(cr.TimetableError, match="priority"):
        _conv(BASIC, teacher_cells=cells, avoid_priority=4)


WINDOW_HEADER = "ma_gv,buoi,tu_tiet,den_tiet\n"


def test_teacher_windows_become_avoid_rules_outside_the_window() -> None:
    # GV01 teaches mornings only in periods 2..3; frame of BASIC is AM periods 1..3.
    windows = cr.parse_teacher_windows(WINDOW_HEADER + "GV01,S,2,3\nGV02,S,1,5\nGV09,C,1,2\n")
    assert windows == {"GV01": {"AM": (2, 3)}, "GV02": {"AM": (1, 5)}, "GV09": {"PM": (1, 2)}}
    conv = _conv(BASIC, teacher_windows=windows)
    soft = {r["id"]: r for r in conv.input["constraint_config"]["soft"]}
    rule = soft["S01K-GV01"]
    assert rule["code"] == "TEACHER_AVOID_SLOTS" and rule["priority"] == 2
    assert rule["parameters"] == {"slot_ids": ["2-AM-1", "3-AM-1"]}
    assert "S01K-GV02" not in soft  # a full window excludes nothing
    report = conv.report["scale"]["teacher_windows"]
    assert report == {
        "source": "teacher-windows",
        "teachers": 1,
        "cells_outside": 2,
        "real_lessons_outside": 2,  # GV01 teaches 6A1 Toán on 2-AM-1 and 3-AM-1
        "full_windows": 1,
        "cells_also_avoided": 0,
        "teachers_without_work": 1,
    }
    ScheduleInput.model_validate(conv.input)
    assert _conv(BASIC).report["scale"]["teacher_windows"] == {"source": "none"}


def test_teacher_window_cells_already_avoided_are_not_penalised_twice() -> None:
    windows = cr.parse_teacher_windows(WINDOW_HEADER + "GV01,S,2,3\n")
    # 2-AM-1 is a Nghỉ cell (soft S01) and outside GV01's window; 3-AM-1 is only outside.
    cells = cr.parse_teacher_cells(TEACHER_HEADER + "GV01,2,S,1,nghi\n")
    conv = _conv(BASIC, teacher_cells=cells, teacher_windows=windows)
    soft = {r["id"]: r for r in conv.input["constraint_config"]["soft"]}
    assert soft["S01-GV01"]["parameters"] == {"slot_ids": ["2-AM-1"]}
    assert soft["S01K-GV01"]["parameters"] == {"slot_ids": ["3-AM-1"]}
    report = conv.report["scale"]["teacher_windows"]
    assert report["cells_also_avoided"] == 1 and report["cells_outside"] == 1
    # Every window cell already avoided: no empty S01K rule.
    both = cr.parse_teacher_cells(TEACHER_HEADER + "GV01,2,S,1,nghi\nGV01,3,S,1,ban\n")
    conv = _conv(BASIC, teacher_cells=both, teacher_windows=windows)
    assert not any(r["id"] == "S01K-GV01" for r in conv.input["constraint_config"]["soft"])
    assert conv.report["scale"]["teacher_windows"]["cells_also_avoided"] == 2
    ScheduleInput.model_validate(conv.input)


def test_teacher_window_errors() -> None:
    with pytest.raises(cr.TimetableError, match="tu_tiet"):
        cr.parse_teacher_windows(WINDOW_HEADER + "GV01,S,4,2\n")
    with pytest.raises(cr.TimetableError, match="twice"):
        cr.parse_teacher_windows(WINDOW_HEADER + "GV01,S,1,2\nGV01,S,1,3\n")
    with pytest.raises(cr.TimetableError, match="buoi"):
        cr.parse_teacher_windows(WINDOW_HEADER + "GV01,X,1,2\n")
