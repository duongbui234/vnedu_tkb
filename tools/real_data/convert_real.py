"""Convert a school's real timetable (canonical CSV) into Core input 1.1 and its assignments.

Plan: docs/superpowers/plans/2026-11-07-real-timetable-intake.md (§4, §5). Tooling outside the
Scheduling Core; it never edits a timetable. Demand, double periods and fixed lessons are read from
the timetable itself; cells Core cannot represent are excluded, listed, and blocked for the class
and teacher involved so that Core and the real schedule face the same remaining problem.

Canonical CSV, one row per taught period: ``lop,thu,buoi,tiet,mon,ma_gv`` (UTF-8). ``buoi`` is
S/C, Sáng/Chiều or AM/PM. Teacher codes must already be pseudonymised (§3).
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


def _scale(teachers: list[str], spread: list[str], sessions: list[str]) -> list[dict[str, Any]]:
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


def convert(rows: list[Row], *, frame: list[Slot] | None = None, school: str = "SCH") -> Conversion:
    slots = sorted(frame) if frame is not None else _default_frame(rows)
    known = set(slots)
    outside = sorted({r.slot for r in rows} - known)
    if outside:
        raise TimetableError(f"timetable uses periods outside the frame: {outside[:5]}")
    ids = [slot_id(s) for s in slots]
    kept, excluded = _exclusions(rows)

    blocked_class: dict[str, set[str]] = defaultdict(set)
    blocked_teacher: dict[str, set[str]] = defaultdict(set)
    for _, r in excluded:
        blocked_class[r.lop].add(slot_id(r.slot))
        if r.teacher:
            blocked_teacher[r.teacher].add(slot_id(r.slot))

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

    def resource(name: str, blocked: dict[str, set[str]]) -> dict[str, Any]:
        entry: dict[str, Any] = {"id": name}
        if blocked.get(name):
            entry["available_slot_ids"] = [s for s in ids if s not in blocked[name]]
        return entry

    teachers_with_work = sorted({r.teacher for r in kept})
    sessions = sorted({s[1] for s in slots})
    data: dict[str, Any] = {
        "schema_version": "1.1",
        "school": {"school_id": school, "academic_year": "unknown", "term": "unknown"},
        "time_slots": [
            {"id": slot_id(s), "day": s[0], "session": s[1], "period": s[2]} for s in slots
        ],
        "classes": [resource(c, blocked_class) for c in sorted({r.lop for r in rows})],
        "teachers": [
            resource(t, blocked_teacher) for t in sorted({r.teacher for r in rows if r.teacher})
        ],
        "subjects": [{"id": s} for s in sorted({r.subject for r in kept})],
        "teaching_requirements": requirements,
        "locked_assignments": locks,
        "constraint_config": {
            "policy_version": "0.4",
            "hard": [],
            "soft": _scale(teachers_with_work, spread, sessions),
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
        "split_runs": split,
        "fixed_requirements": sorted({a["occurrence_id"].split("::")[0] for a in locks}),
        "scale": {
            "S02": S02_LIMIT,
            "S03": S03_LIMIT,
            "S06": S06_LIMIT,
            "S09": S09_LIMIT,
            "S05": S05_GAP,
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
    parser.add_argument("--output", type=Path, required=True, help="new directory for the results")
    parser.add_argument("--school", default="SCH", help="pseudonymous school code")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output {args.output} already exists; nothing is overwritten")
    try:
        rows = parse_timetable(args.timetable.read_text(encoding="utf-8"))
        frame = parse_frame(args.frame.read_text(encoding="utf-8")) if args.frame else None
        conv = convert(rows, frame=frame, school=args.school)
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
