"""Convert a school's real timetable (canonical CSV) into Core input 1.1 and its assignments.

Plan: docs/superpowers/plans/2026-11-07-real-timetable-intake.md (§4, §5). Tooling outside the
Scheduling Core; it never edits a timetable. Demand, double periods and fixed lessons are read from
the timetable itself; cells Core cannot represent are excluded, listed, and blocked for the class
and teacher involved so that Core and the real schedule face the same remaining problem.

Canonical CSV, one row per taught period: ``lop,thu,buoi,tiet,mon,ma_gv`` (UTF-8). ``buoi`` is
S/C, Sáng/Chiều or AM/PM. Teacher codes must already be pseudonymised (§3).

Optional class cells, one row per period a class may be taught in: ``lop,thu,buoi,tiet``. When
given, each class may use only those cells of the frame (``available_slot_ids``), so Core faces the
same calendar as the school; every lesson of the timetable must lie inside its class's cells.

Optional teacher cells ``ma_gv,thu,buoi,tiet,loai`` (``loai`` hop/nghi/ban/hanche, from STKB) and
locks ``ma_gv,thu,buoi,tiet``. Kinds listed as hard (default: hop) are removed from the teacher's
``available_slot_ids``; the other known kinds become one soft TEACHER_AVOID_SLOTS (S01) rule per
teacher at priority 2, scored for the real and the Core schedule alike. Each locked teacher cell
locks the lesson that covers it at its block start. A lock wins over a hard teacher cell: that
cell stays open for the teacher, and the report counts it.

Optional teacher limits ``ma_gv,max_tiet_buoi,max_tiet_ngay`` (STKB teacher properties, empty when
the school did not enable the limit). When given, the per-teacher load rules of the scale follow
the school: S02 (periods per session) and S03 (periods per day) exist only for a teacher with that
limit enabled, at that limit. The other rules keep the common scale.

Optional teacher period windows ``ma_gv,buoi,tu_tiet,den_tiet`` (STKB ``GetValue_FromT1toT2``: a
teacher should teach that session only from period ``tu_tiet`` to ``den_tiet``; STKB adds a small
penalty per period taught outside). Each window becomes a soft TEACHER_AVOID_SLOTS rule over the
frame cells of that session outside the window, at the priority of the other teacher requests.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment

COLUMNS = ("lop", "thu", "buoi", "tiet", "mon", "ma_gv")
CLASS_CELL_COLUMNS = ("lop", "thu", "buoi", "tiet")
TEACHER_CELL_COLUMNS = ("ma_gv", "thu", "buoi", "tiet", "loai")
LOCK_COLUMNS = ("ma_gv", "thu", "buoi", "tiet")
LIMIT_COLUMNS = ("ma_gv", "max_tiet_buoi", "max_tiet_ngay")
WINDOW_COLUMNS = ("ma_gv", "buoi", "tu_tiet", "den_tiet")
TEACHER_KINDS = ("hop", "nghi", "ban", "hanche")
AVOID_PRIORITY = 2  # teacher requests (Nghỉ/Bận/Hạn chế) when not hard; chosen before scoring
SESSIONS = {
    "s": "AM",
    "sáng": "AM",
    "sang": "AM",
    "am": "AM",
    "c": "PM",
    "chiều": "PM",
    "chieu": "PM",
    "pm": "PM",
}
# Lessons a school fixes in place (flag ceremony, class meeting); matched case-insensitively.
FIXED_PATTERNS = ("chào cờ", "chao co", "sinh hoạt", "sinh hoat", "shl")
# Measurement scale (plan §5, RD5): fixed before any real data was opened. Not a quality profile.
S02_LIMIT, S03_LIMIT, S06_LIMIT, S09_LIMIT, S05_GAP = 4, 5, 2, 1, 1

Slot = tuple[int, str, int]
TeacherLimits = dict[str, tuple[int | None, int | None]]  # teacher -> (per session, per day)
TeacherWindows = dict[str, dict[str, tuple[int, int]]]  # teacher -> session -> (first, last)


class TimetableError(ValueError):
    """The timetable file cannot be read as the canonical format."""


@dataclass(frozen=True, order=True)
class Row:
    lop: str
    day: int
    session: str
    period: int
    subject: str
    teacher: str

    @property
    def slot(self) -> Slot:
        return (self.day, self.session, self.period)


@dataclass
class Conversion:
    input: dict[str, Any]
    previous: dict[str, Any]
    report: dict[str, Any] = field(default_factory=dict)


def _int(value: str, name: str, line: int) -> int:
    try:
        number = int(value)
    except ValueError:
        raise TimetableError(f"line {line}: '{name}' is not a whole number: {value!r}") from None
    if number < 1:
        raise TimetableError(f"line {line}: '{name}' must be at least 1")
    return number


def _session(value: str, line: int) -> str:
    key = value.strip().casefold()
    if key not in SESSIONS:
        raise TimetableError(f"line {line}: unknown 'buoi' {value!r} (use S/C, Sáng/Chiều, AM/PM)")
    return SESSIONS[key]


def _reader(text: str, needed: tuple[str, ...]) -> csv.DictReader[str]:
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    header = tuple(h.strip() for h in reader.fieldnames or ())
    missing = [c for c in needed if c not in header]
    if missing:
        raise TimetableError(f"header lacks column(s) {missing}; expected {list(needed)}")
    return reader


def parse_timetable(text: str) -> list[Row]:
    reader = _reader(text, COLUMNS)
    rows = []
    for raw in reader:
        cells = {k.strip(): (v or "").strip() for k, v in raw.items() if k is not None}
        if not any(cells.values()):
            continue
        line = reader.line_num
        if not cells["lop"] or not cells["mon"]:
            raise TimetableError(f"line {line}: 'lop' and 'mon' are required")
        rows.append(
            Row(
                cells["lop"],
                _int(cells["thu"], "thu", line),
                _session(cells["buoi"], line),
                _int(cells["tiet"], "tiet", line),
                cells["mon"],
                cells["ma_gv"],
            )
        )
    if not rows:
        raise TimetableError("timetable has no rows")
    return rows


def parse_frame(text: str) -> list[Slot]:
    reader = _reader(text, ("thu", "buoi", "tiet"))
    return sorted(
        {
            (
                _int(r["thu"].strip(), "thu", reader.line_num),
                _session(r["buoi"], reader.line_num),
                _int(r["tiet"].strip(), "tiet", reader.line_num),
            )
            for r in reader
        }
    )


def parse_class_cells(text: str) -> dict[str, set[Slot]]:
    """Cells each class may be taught in; a class absent from the file has no cells."""
    reader = _reader(text, CLASS_CELL_COLUMNS)
    cells: dict[str, set[Slot]] = defaultdict(set)
    for raw in reader:
        row = {k.strip(): (v or "").strip() for k, v in raw.items() if k is not None}
        if not any(row.values()):
            continue
        line = reader.line_num
        if not row["lop"]:
            raise TimetableError(f"line {line}: 'lop' is required")
        cells[row["lop"]].add(
            (
                _int(row["thu"], "thu", line),
                _session(row["buoi"], line),
                _int(row["tiet"], "tiet", line),
            )
        )
    return dict(cells)


def _cell(row: dict[str, str], line: int) -> Slot:
    return (
        _int(row["thu"], "thu", line),
        _session(row["buoi"], line),
        _int(row["tiet"], "tiet", line),
    )


def parse_teacher_cells(text: str) -> dict[str, dict[str, set[Slot]]]:
    """Teacher -> kind -> cells; unknown kinds are kept (and later only counted)."""
    reader = _reader(text, TEACHER_CELL_COLUMNS)
    cells: dict[str, dict[str, set[Slot]]] = defaultdict(lambda: defaultdict(set))
    for raw in reader:
        row = {k.strip(): (v or "").strip() for k, v in raw.items() if k is not None}
        if not any(row.values()):
            continue
        if not row["ma_gv"] or not row["loai"]:
            raise TimetableError(f"line {reader.line_num}: 'ma_gv' and 'loai' are required")
        cells[row["ma_gv"]][row["loai"]].add(_cell(row, reader.line_num))
    return {t: dict(k) for t, k in cells.items()}


def parse_locks(text: str) -> set[tuple[str, Slot]]:
    reader = _reader(text, LOCK_COLUMNS)
    locks = set()
    for raw in reader:
        row = {k.strip(): (v or "").strip() for k, v in raw.items() if k is not None}
        if any(row.values()):
            locks.add((row["ma_gv"], _cell(row, reader.line_num)))
    return locks


def parse_teacher_limits(text: str) -> TeacherLimits:
    """Teacher -> (max periods per session, max per day); an empty value means no limit."""
    reader = _reader(text, LIMIT_COLUMNS)
    limits: TeacherLimits = {}
    for raw in reader:
        row = {k.strip(): (v or "").strip() for k, v in raw.items() if k is not None}
        if not any(row.values()):
            continue
        line = reader.line_num
        if not row["ma_gv"]:
            raise TimetableError(f"line {line}: 'ma_gv' is required")
        session, day = (
            _int(row[c], c, line) if row[c] else None for c in ("max_tiet_buoi", "max_tiet_ngay")
        )
        limits[row["ma_gv"]] = (session, day)
    return limits


def parse_teacher_windows(text: str) -> TeacherWindows:
    """Teacher -> session -> (first, last) period the teacher should teach in that session."""
    reader = _reader(text, WINDOW_COLUMNS)
    windows: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
    for raw in reader:
        row = {k.strip(): (v or "").strip() for k, v in raw.items() if k is not None}
        if not any(row.values()):
            continue
        line = reader.line_num
        if not row["ma_gv"]:
            raise TimetableError(f"line {line}: 'ma_gv' is required")
        session = _session(row["buoi"], line)
        first, last = _int(row["tu_tiet"], "tu_tiet", line), _int(row["den_tiet"], "den_tiet", line)
        if first > last:
            raise TimetableError(f"line {line}: 'tu_tiet' {first} is after 'den_tiet' {last}")
        if session in windows[row["ma_gv"]]:
            raise TimetableError(f"line {line}: window of {row['ma_gv']} {session} given twice")
        windows[row["ma_gv"]][session] = (first, last)
    return dict(windows)


def format_timetable(rows: list[Row]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for r in sorted(rows):
        writer.writerow((r.lop, r.day, r.session, r.period, r.subject, r.teacher))
    return out.getvalue()


def slot_id(slot: Slot) -> str:
    return f"{slot[0]}-{slot[1]}-{slot[2]}"


def _default_frame(rows: list[Row]) -> list[Slot]:
    days = sorted({r.day for r in rows})
    last: dict[str, int] = {}
    for r in rows:
        last[r.session] = max(last.get(r.session, 0), r.period)
    return [(d, s, p) for d in days for s in sorted(last) for p in range(1, last[s] + 1)]


def _runs(slots: list[Slot]) -> list[list[Slot]]:
    """Consecutive periods of one day and session, in time order."""
    runs: list[list[Slot]] = []
    for slot in sorted(slots):
        prev = runs[-1][-1] if runs else None
        if prev and prev[:2] == slot[:2] and prev[2] + 1 == slot[2]:
            runs[-1].append(slot)
        else:
            runs.append([slot])
    return runs


def _exclusions(rows: list[Row]) -> tuple[list[Row], list[tuple[str, Row]]]:
    by_class = Counter((r.lop, r.slot) for r in rows)
    excluded = [("CLASS_SLOT_MULTI", r) for r in rows if by_class[(r.lop, r.slot)] > 1]
    rest = [r for r in rows if by_class[(r.lop, r.slot)] == 1]
    excluded += [("NO_TEACHER", r) for r in rest if not r.teacher]
    rest = [r for r in rest if r.teacher]
    by_teacher = Counter((r.teacher, r.slot) for r in rest)
    excluded += [("TEACHER_SLOT_MULTI", r) for r in rest if by_teacher[(r.teacher, r.slot)] > 1]
    kept = [r for r in rest if by_teacher[(r.teacher, r.slot)] == 1]
    return kept, excluded


def _scale(
    teachers: list[str],
    spread: list[str],
    sessions: list[str],
    limits: TeacherLimits | None = None,
) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = [
        {
            "id": "S06-ALL",
            "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": S06_LIMIT},
            "priority": 1,
            "weight": 1,
        }
    ]
    per_teacher = (
        (
            "S02",
            "TEACHER_MAX_PERIODS_PER_SESSION",
            {"limit": S02_LIMIT, "session_ids": sessions},
            1,
        ),
        ("S03", "TEACHER_MAX_PERIODS_PER_DAY", {"limit": S03_LIMIT}, 2),
        ("S09", "TEACHER_MAX_GAP_RUN", {"limit": S09_LIMIT, "session_ids": sessions}, 2),
        ("S08", "TEACHER_TOTAL_GAPS", {"session_ids": sessions}, 3),
        ("S11", "TEACHER_SINGLE_PERIOD_SESSION", {"session_ids": sessions}, 3),
    )
    for t in teachers:
        for tag, code, params, priority in per_teacher:
            if limits is not None and tag in ("S02", "S03"):
                limit = limits.get(t, (None, None))[0 if tag == "S02" else 1]
                if limit is None:
                    continue  # the school set no such limit for this teacher
                params = {**params, "limit": limit}
            rules.append(
                {
                    "id": f"{tag}-{t}",
                    "code": code,
                    "parameters": params,
                    "priority": priority,
                    "weight": 1,
                    "scope": {"teacher_ids": [t]},
                }
            )
    for req in spread:
        rules.append(
            {
                "id": f"S05-{req}",
                "code": "SUBJECT_COMPONENT_DAY_SPREAD",
                "parameters": {"requirement_ids": [req], "min_day_gap": S05_GAP},
                "priority": 2,
                "weight": 1,
            }
        )
    return rules


def _class_cells(
    rows: list[Row], class_cells: dict[str, set[Slot]], known: set[Slot]
) -> tuple[dict[str, set[str]], int]:
    """Open slot ids per class, and how many given cells fall outside the frame."""
    classes = sorted({r.lop for r in rows})
    missing = [c for c in classes if c not in class_cells]
    if missing:
        raise TimetableError(f"class cells missing for class(es) {missing[:5]}")
    allowed = {c: {slot_id(s) for s in class_cells[c] & known} for c in classes}
    outside = sum(len(class_cells[c] - known) for c in classes)
    bad = sorted({(r.lop, r.slot) for r in rows if slot_id(r.slot) not in allowed[r.lop]})
    if bad:
        raise TimetableError(f"timetable uses cells outside its class cells: {bad[:5]}")
    return allowed, outside


def convert(
    rows: list[Row],
    *,
    frame: list[Slot] | None = None,
    school: str = "SCH",
    class_cells: dict[str, set[Slot]] | None = None,
    teacher_cells: dict[str, dict[str, set[Slot]]] | None = None,
    hard_kinds: tuple[str, ...] = ("hop",),
    locked_cells: set[tuple[str, Slot]] | None = None,
    teacher_limits: TeacherLimits | None = None,
    avoid_priority: int = AVOID_PRIORITY,
    teacher_windows: TeacherWindows | None = None,
) -> Conversion:
    slots = sorted(frame) if frame is not None else _default_frame(rows)
    known = set(slots)
    outside = sorted({r.slot for r in rows} - known)
    if outside:
        raise TimetableError(f"timetable uses periods outside the frame: {outside[:5]}")
    ids = [slot_id(s) for s in slots]
    allowed: dict[str, set[str]] | None = None
    cells_outside_frame = 0
    if class_cells is not None:
        allowed, cells_outside_frame = _class_cells(rows, class_cells, known)
    kept, excluded = _exclusions(rows)

    blocked_class: dict[str, set[str]] = defaultdict(set)
    blocked_teacher: dict[str, set[str]] = defaultdict(set)
    for _, r in excluded:
        blocked_class[r.lop].add(slot_id(r.slot))
        if r.teacher:
            blocked_teacher[r.teacher].add(slot_id(r.slot))

    if avoid_priority not in (1, 2, 3):
        raise TimetableError(f"avoid priority must be 1, 2 or 3, not {avoid_priority}")
    unknown_kinds = sorted(set(hard_kinds) - set(TEACHER_KINDS))
    if unknown_kinds:
        raise TimetableError(f"unknown hard teacher cell kind(s) {unknown_kinds}")
    cell_owner: dict[tuple[str, Slot], tuple[str, Slot]] = {}

    cells: dict[tuple[str, str, str], list[Slot]] = defaultdict(list)
    for r in kept:
        cells[(r.lop, r.subject, r.teacher)].append(r.slot)

    requirements, assignments, locks, spread, split = [], [], [], [], []
    for (lop, subject, teacher), taught in sorted(cells.items()):
        req = f"{lop}|{subject}|{teacher}"
        blocks: list[list[Slot]] = []
        for run in _runs(taught):
            if len(run) > 2:
                split.append(
                    {"requirement": req, "day": run[0][0], "session": run[0][1], "length": len(run)}
                )
            blocks += [run[i : i + 2] for i in range(0, len(run), 2)]
        requirements.append(
            {
                "id": req,
                "class_ids": [lop],
                "teacher_ids": [teacher],
                "subject_id": subject,
                "periods_per_cycle": len(taught),
                "block_durations": [len(b) for b in blocks],
            }
        )
        fixed = any(p in subject.casefold() for p in FIXED_PATTERNS)
        for i, block in enumerate(blocks, 1):
            for cell in block:
                cell_owner[(teacher, cell)] = (f"{req}::{i}", block[0])
            assignments.append(
                {
                    "occurrence_id": f"{req}::{i}",
                    "slot_id": slot_id(block[0]),
                    "class_ids": [lop],
                    "teacher_ids": [teacher],
                    "room_id": None,
                }
            )
            if fixed:
                locks.append({"occurrence_id": f"{req}::{i}", "slot_id": slot_id(block[0])})
        if len(blocks) >= 2 and not fixed:
            spread.append(req)

    fixed_locks = list(locks)  # lessons fixed by name (flag ceremony, class meeting)
    locked = {a["occurrence_id"] for a in locks}
    lock_report = {"given": 0, "locked_occurrences": 0, "on_empty_cell": 0}
    if locked_cells is not None:
        lock_report["given"] = len(locked_cells)
        for teacher, cell in sorted(locked_cells):
            owner = cell_owner.get((teacher, cell))
            if owner is None:
                lock_report["on_empty_cell"] += 1
            elif owner[0] not in locked:
                locked.add(owner[0])
                locks.append({"occurrence_id": owner[0], "slot_id": slot_id(owner[1])})
                lock_report["locked_occurrences"] += 1

    teachers_with_work = sorted({r.teacher for r in kept})
    hard_teacher: dict[str, set[str]] = defaultdict(set)
    avoid: dict[str, set[str]] = defaultdict(set)
    taught_cells = {(r.teacher, slot_id(r.slot)) for r in kept}
    locked_slots = {
        (teacher, slot_id(cell))
        for (teacher, cell), (occ, _) in cell_owner.items()
        if occ in locked
    }
    teacher_report: dict[str, Any] = {"source": "none"}
    if teacher_cells is not None:
        counts = Counter[str]()
        for teacher in teachers_with_work:
            for kind, given in teacher_cells.get(teacher, {}).items():
                inside = {slot_id(c) for c in given & known}
                counts["outside_frame"] += len(given - known)
                if kind not in TEACHER_KINDS:
                    counts[f"ignored_{kind}"] += len(inside)
                elif kind in hard_kinds:
                    kept_open = {s for s in inside if (teacher, s) in locked_slots}
                    counts["hard_cells_kept_for_locks"] += len(kept_open)
                    hard_teacher[teacher] |= inside - kept_open
                    counts[f"hard_{kind}"] += len(inside - kept_open)
                    counts["real_lessons_on_hard_cells"] += sum(
                        (teacher, s) in taught_cells for s in inside
                    )
                elif inside:  # an empty S01 rule is invalid; cells outside the frame are counted
                    avoid[teacher] |= inside
                    counts[f"soft_{kind}"] += len(inside)
                    counts["real_lessons_on_soft_cells"] += sum(
                        (teacher, s) in taught_cells for s in inside
                    )
        teacher_report = {
            "source": "teacher-cells",
            "hard_kinds": sorted(hard_kinds),
            "soft_priority": avoid_priority,
            "teachers_without_work": len(set(teacher_cells) - set(teachers_with_work)),
            **dict(sorted(counts.items())),
        }

    def teacher_entry(name: str) -> dict[str, Any]:
        entry: dict[str, Any] = {"id": name}
        closed = blocked_teacher.get(name, set()) | hard_teacher.get(name, set())
        if closed:
            entry["available_slot_ids"] = [s for s in ids if s not in closed]
        return entry

    def class_entry(name: str) -> dict[str, Any]:
        entry: dict[str, Any] = {"id": name}
        open_ids = [
            s
            for s in ids
            if s not in blocked_class.get(name, ()) and (allowed is None or s in allowed[name])
        ]
        if len(open_ids) < len(ids):
            entry["available_slot_ids"] = open_ids
        return entry

    sessions = sorted({s[1] for s in slots})
    soft_rules = _scale(teachers_with_work, spread, sessions, teacher_limits)
    limit_report: dict[str, Any] = {"source": "common"}
    if teacher_limits is not None:
        own = [teacher_limits[t] for t in teachers_with_work if t in teacher_limits]
        limit_report = {
            "source": "teacher-limits",
            "S02_teachers": sum(a is not None for a, _ in own),
            "S03_teachers": sum(b is not None for _, b in own),
            "S02_limits": {str(k): v for k, v in sorted(Counter(a for a, _ in own if a).items())},
            "S03_limits": {str(k): v for k, v in sorted(Counter(b for _, b in own if b).items())},
            "teachers_missing": sum(t not in teacher_limits for t in teachers_with_work),
        }
    for teacher in sorted(avoid):
        soft_rules.append(
            {
                "id": f"S01-{teacher}",
                "code": "TEACHER_AVOID_SLOTS",
                "parameters": {"slot_ids": [s for s in ids if s in avoid[teacher]]},
                "priority": avoid_priority,
                "weight": 1,
                "scope": {"teacher_ids": [teacher]},
            }
        )
    window_report: dict[str, Any] = {"source": "none"}
    if teacher_windows is not None:
        window_counts = Counter[str]()
        for teacher in teachers_with_work:
            window_outside: set[str] = set()
            for session, (first, last) in teacher_windows.get(teacher, {}).items():
                window_cells = {
                    slot_id(c) for c in slots if c[1] == session and not first <= c[2] <= last
                }
                if not window_cells:
                    window_counts["full_windows"] += 1
                window_outside |= window_cells
            if window_outside:
                window_counts["teachers"] += 1
                window_counts["cells_outside"] += len(window_outside)
                window_counts["real_lessons_outside"] += sum(
                    (teacher, s) in taught_cells for s in window_outside
                )
                soft_rules.append(
                    {
                        "id": f"S01K-{teacher}",
                        "code": "TEACHER_AVOID_SLOTS",
                        "parameters": {"slot_ids": [s for s in ids if s in window_outside]},
                        "priority": avoid_priority,
                        "weight": 1,
                        "scope": {"teacher_ids": [teacher]},
                    }
                )
        window_report = {
            "source": "teacher-windows",
            "teachers": window_counts["teachers"],
            "cells_outside": window_counts["cells_outside"],
            "real_lessons_outside": window_counts["real_lessons_outside"],
            "full_windows": window_counts["full_windows"],
            "teachers_without_work": len(set(teacher_windows) - set(teachers_with_work)),
        }
    data: dict[str, Any] = {
        "schema_version": "1.1",
        "school": {"school_id": school, "academic_year": "unknown", "term": "unknown"},
        "time_slots": [
            {"id": slot_id(s), "day": s[0], "session": s[1], "period": s[2]} for s in slots
        ],
        "classes": [class_entry(c) for c in sorted({r.lop for r in rows})],
        "teachers": [teacher_entry(t) for t in sorted({r.teacher for r in rows if r.teacher})],
        "subjects": [{"id": s} for s in sorted({r.subject for r in kept})],
        "teaching_requirements": requirements,
        "locked_assignments": locks,
        "constraint_config": {
            "policy_version": "0.4",
            "hard": [],
            "soft": soft_rules,
        },
    }
    fingerprint = ScheduleInput.model_validate(data).fingerprint()
    previous = {
        "schema_version": "1.0",
        "source_input_fingerprint": fingerprint,
        "assignments": assignments,
    }
    report = {
        "school": school,
        "block_source": "timetable",
        "counts": {
            "rows": len(rows),
            "classes": len(data["classes"]),
            "teachers": len(teachers_with_work),
            "requirements": len(requirements),
            "periods": len(kept),
            "slots": len(slots),
        },
        "excluded": [
            {
                "reason": reason,
                "lop": r.lop,
                "thu": r.day,
                "buoi": r.session,
                "tiet": r.period,
                "mon": r.subject,
                "ma_gv": r.teacher,
            }
            for reason, r in sorted(excluded, key=lambda e: (e[0], e[1]))
        ],
        "excluded_periods": len(excluded),
        "class_availability": {
            "source": "class-cells" if allowed is not None else "frame",
            "open_class_slots": sum(len(c.get("available_slot_ids", ids)) for c in data["classes"]),
            "frame_class_slots": len(ids) * len(data["classes"]),
            "cells_outside_frame": cells_outside_frame,
        },
        "split_runs": split,
        "fixed_requirements": sorted({a["occurrence_id"].split("::")[0] for a in fixed_locks}),
        "teacher_availability": teacher_report,
        "locks": lock_report,
        "scale": {
            "S02": S02_LIMIT,
            "S03": S03_LIMIT,
            "S06": S06_LIMIT,
            "S09": S09_LIMIT,
            "S05": S05_GAP,
            "teacher_limits": limit_report,
            "teacher_windows": window_report,
        },
    }
    return Conversion(data, previous, report)


def export_rows(problem: ScheduleInput, assignments: tuple[ScheduleAssignment, ...]) -> list[Row]:
    """Write a schedule back as canonical rows (one per taught period); used for round trips."""
    reqs = {r.id: r for r in problem.teaching_requirements}
    by_id = {s.id: s for s in problem.time_slots}
    by_key = {(s.day, s.session, s.period): s for s in problem.time_slots}
    rows = []
    for a in assignments:
        req_id, ordinal = a.occurrence_id.rsplit("::", 1)
        req = reqs[req_id]
        durations = req.block_durations or (1,) * req.periods_per_cycle
        start = by_id[a.slot_id]
        for i in range(durations[int(ordinal) - 1]):
            s = by_key[(start.day, start.session, start.period + i)]
            rows.append(
                Row(a.class_ids[0], s.day, s.session, s.period, req.subject_id, a.teacher_ids[0])
            )
    return rows


def _write(path: Path, data: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("timetable", type=Path, help="canonical CSV (lop,thu,buoi,tiet,mon,ma_gv)")
    parser.add_argument(
        "--frame", type=Path, help="optional CSV of teaching periods (thu,buoi,tiet)"
    )
    parser.add_argument(
        "--class-cells",
        type=Path,
        help="optional CSV of cells each class may use (lop,thu,buoi,tiet)",
    )
    parser.add_argument(
        "--teacher-cells", type=Path, help="optional CSV ma_gv,thu,buoi,tiet,loai from STKB"
    )
    parser.add_argument(
        "--teacher-hard", default="hop", help="teacher cell kinds that are hard (default: hop)"
    )
    parser.add_argument("--locks", type=Path, help="optional CSV of locked teacher cells")
    parser.add_argument(
        "--teacher-limits",
        type=Path,
        help="optional CSV ma_gv,max_tiet_buoi,max_tiet_ngay; replaces the common S02/S03",
    )
    parser.add_argument(
        "--teacher-windows",
        type=Path,
        help="optional CSV ma_gv,buoi,tu_tiet,den_tiet: soft rule for periods outside the window",
    )
    parser.add_argument(
        "--avoid-priority",
        type=int,
        default=AVOID_PRIORITY,
        help=f"priority of soft teacher cells (default {AVOID_PRIORITY})",
    )
    parser.add_argument("--output", type=Path, required=True, help="new directory for the results")
    parser.add_argument("--school", default="SCH", help="pseudonymous school code")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output {args.output} already exists; nothing is overwritten")
    try:
        rows = parse_timetable(args.timetable.read_text(encoding="utf-8"))
        frame = parse_frame(args.frame.read_text(encoding="utf-8")) if args.frame else None
        cells = (
            parse_class_cells(args.class_cells.read_text(encoding="utf-8"))
            if args.class_cells
            else None
        )
        teacher_cells = (
            parse_teacher_cells(args.teacher_cells.read_text(encoding="utf-8"))
            if args.teacher_cells
            else None
        )
        locks = parse_locks(args.locks.read_text(encoding="utf-8")) if args.locks else None
        limits = (
            parse_teacher_limits(args.teacher_limits.read_text(encoding="utf-8"))
            if args.teacher_limits
            else None
        )
        windows = (
            parse_teacher_windows(args.teacher_windows.read_text(encoding="utf-8"))
            if args.teacher_windows
            else None
        )
        conv = convert(
            rows,
            frame=frame,
            school=args.school,
            class_cells=cells,
            teacher_cells=teacher_cells,
            hard_kinds=tuple(k for k in args.teacher_hard.split(",") if k),
            locked_cells=locks,
            teacher_limits=limits,
            avoid_priority=args.avoid_priority,
            teacher_windows=windows,
        )
    except TimetableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.output.mkdir(parents=True)
    _write(args.output / "input.json", conv.input)
    _write(args.output / "real-assignments.json", conv.previous)
    _write(args.output / "conversion-report.json", conv.report)
    counts = conv.report["counts"]
    print(
        f"{args.school}: {counts['classes']} lớp, {counts['teachers']} GV, "
        f"{counts['requirements']} phân công, {counts['periods']} tiết; "
        f"loại {conv.report['excluded_periods']} tiết"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
