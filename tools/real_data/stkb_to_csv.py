"""Turn STKB 5.0 (format 84) files into the canonical timetable CSV and each class's cells.

The research readers in ``reverse-engineering/scripts`` decode the file read-only (verified in
``docs/research/stkb/07-file-demand-recovery.md``); this module maps their primary class view to
rows ``lop,thu,buoi,tiet,mon,ma_gv`` for ``convert_real.py``:

- storage group 0/1 -> session S/C; storage day index d -> ``thu`` d + 1; periods 1..5;
- a subject index -> the subject's short name; a teacher index -> ``GV###`` (index in the file).
  Teacher names stay in memory; no name/code mapping is written;
- a class may use every cell of each (day, session) in which it has at least one lesson, except
  cells STKB marks with a non-subject code (254/255 seen; their meaning is UNKNOWN).

Teacher cells and locks come from the file suffix (``inspect_stkb_suffix``; codes mapped to the
binary in ``docs/research/stkb/08-suffix-constraints-and-locks.md``): 1000-1006 Họp (meeting),
998 Nghỉ, 999 Bận, 997 Hạn chế; another non-zero code is kept as ``ma_<code>`` (UNKNOWN). A lock
flag equal to 1 marks a locked teacher cell. When the suffix cannot be read, no teacher cells or
locks are written and the summary says why.

Teacher limits come from the 96-byte teacher property record (report 08 §4): byte +1 enables the
max periods per session stored as i32 at +24; byte +2 enables the max periods per day at +28. A
disabled limit is written empty, whatever value is stored; an enabled limit below 1 is not usable
and is counted.

Period windows come from the same record: byte +3 enables the morning window, periods i32 +32 to
+36; byte +4 the afternoon window, +40 to +44. ``GetValue_FromT1toT2`` (0x6c5a40) picks the pair by
the session being scheduled (``this+0x1d7004``, written 0/1 by the "Buổi Sáng"/"Buổi Chiều" radio
handlers, IDs 1752/1753) and adds a coefficient for each period the teacher teaches before the
first or after the last period, over 7 days. Only enabled windows with 1 <= first <= last <= 5
are written; others are counted as invalid.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

READERS = Path(__file__).resolve().parents[2] / "reverse-engineering" / "scripts"
SESSIONS = {0: "S", 1: "C"}
PERIODS_PER_SESSION = 5  # verified storage: 2 groups x 7 day indices x 5 periods

Slot = tuple[int, str, int]
CsvRow = tuple[str, int, str, int, str, str]


TeacherCell = tuple[str, int, str, int, str]


@dataclass
class Extracted:
    rows: list[CsvRow]
    class_cells: dict[str, set[Slot]]
    markers: Counter[int] = field(default_factory=Counter)
    no_teacher_rows: int = 0
    teacher_cells: list[TeacherCell] | None = None
    locks: list[tuple[str, int, str, int]] | None = None
    teacher_limits: list[tuple[str, int | None, int | None]] | None = None
    teacher_windows: list[tuple[str, str, int, int]] | None = None


def slot_kind(code: int) -> str | None:
    """Name of a teacher slot code (report 08); None for 0 (no request)."""
    if code == 0:
        return None
    if 1000 <= code <= 1006:
        return "hop"
    return {998: "nghi", 999: "ban", 997: "hanche"}.get(code, f"ma_{code}")


def teacher_constraints(
    slot_constraints: Mapping[tuple[int, int, int, int], Sequence[int]],
) -> tuple[list[TeacherCell], list[tuple[str, int, str, int]]]:
    """``(group, teacher, day, period) -> (code, lock)`` to coded cells and locked cells."""
    cells: list[TeacherCell] = []
    locks: list[tuple[str, int, str, int]] = []
    for (group, teacher, day, period), (code, lock) in sorted(slot_constraints.items()):
        slot = (f"GV{teacher:03d}", day + 1, SESSIONS[group], period)
        kind = slot_kind(code)
        if kind:
            cells.append((*slot, kind))
        if lock == 1:
            locks.append(slot)
    return cells, locks


TEACHER_RECORD = 96
LIMIT_FIELDS = ((1, 24), (2, 28))  # (enable byte, i32 limit): per session, per day


def teacher_limits(
    properties: bytes, teacher_count: int
) -> tuple[list[tuple[str, int | None, int | None]], int]:
    """Per-teacher (max per session, max per day) from the property records, and invalid count."""
    if len(properties) != TEACHER_RECORD * teacher_count:
        raise ValueError(f"teacher properties must be {TEACHER_RECORD} bytes per teacher")
    limits: list[tuple[str, int | None, int | None]] = []
    invalid = 0
    for i in range(teacher_count):
        base = TEACHER_RECORD * i
        values: list[int | None] = []
        for flag, offset in LIMIT_FIELDS:
            value = int.from_bytes(
                properties[base + offset : base + offset + 4], "little", signed=True
            )
            if not properties[base + flag]:
                values.append(None)
            elif value < 1:
                invalid += 1
                values.append(None)
            else:
                values.append(value)
        limits.append((f"GV{i + 1:03d}", values[0], values[1]))
    return limits, invalid


WINDOW_FIELDS = ((3, 32, "S"), (4, 40, "C"))  # (enable byte, i32 first/last pair, session)


def teacher_windows(
    properties: bytes, teacher_count: int
) -> tuple[list[tuple[str, str, int, int]], int]:
    """Enabled period windows ``(GV###, S/C, first, last)`` and the count of unusable ones."""
    if len(properties) != TEACHER_RECORD * teacher_count:
        raise ValueError(f"teacher properties must be {TEACHER_RECORD} bytes per teacher")
    windows: list[tuple[str, str, int, int]] = []
    invalid = 0
    for i in range(teacher_count):
        base = TEACHER_RECORD * i
        for flag, offset, session in WINDOW_FIELDS:
            if not properties[base + flag]:
                continue
            first, last = (
                int.from_bytes(properties[base + o : base + o + 4], "little", signed=True)
                for o in (offset, offset + 4)
            )
            if 1 <= first <= last <= PERIODS_PER_SESSION:
                windows.append((f"GV{i + 1:03d}", session, first, last))
            else:
                invalid += 1
    return windows, invalid


def extract(
    class_cells: Mapping[tuple[int, int, int, int], Sequence[int]],
    groups: Sequence[Sequence[Sequence[str]]],
    subjects: Sequence[Sequence[str]],
    teacher_count: int,
) -> Extracted:
    """Map decoded class cells ``(group, class, day, period) -> (subject, teacher, room, ...)``."""
    class_ids: dict[str, str] = {}
    rows: list[CsvRow] = []
    marked: dict[str, set[Slot]] = defaultdict(set)
    taught: dict[str, set[tuple[int, str]]] = defaultdict(set)
    markers: Counter[int] = Counter()
    no_teacher = 0
    for (group, index, day, period), record in sorted(class_cells.items()):
        name, class_id = groups[group][index - 1][0].strip(), groups[group][index - 1][1]
        if class_ids.setdefault(name, class_id) != class_id:
            raise ValueError(f"class name {name!r} belongs to two class ids")
        subject, teacher = record[0], record[1]
        if subject == 0:
            continue
        slot = (day + 1, SESSIONS[group], period)
        if not 1 <= subject <= len(subjects):
            markers[subject] += 1
            marked[name].add(slot)
            continue
        code = f"GV{teacher:03d}" if 1 <= teacher <= teacher_count else ""
        no_teacher += not code
        rows.append((name, *slot, subjects[subject - 1][0].strip(), code))
        taught[name].add(slot[:2])
    cells = {
        name: {(d, s, p) for d, s in days for p in range(1, PERIODS_PER_SESSION + 1)} - marked[name]
        for name, days in taught.items()
    }
    return Extracted(rows, cells, markers, no_teacher)


def _readers() -> Any:
    if str(READERS) not in sys.path:
        sys.path.insert(0, str(READERS))
    import inspect_stkb_file as prefix  # noqa: PLC0415
    import inspect_stkb_schedule as schedule  # noqa: PLC0415
    import inspect_stkb_suffix as suffix  # noqa: PLC0415

    return prefix, schedule, suffix


def read_file(data: bytes) -> tuple[Extracted, dict[str, Any]]:
    """Decode one file through the demand section; the constraint suffix is not needed."""
    prefix, schedule, suffix = _readers()
    counts, catalog = prefix.inspect(data)
    reader = prefix.Reader(data)
    reader.pos = counts["parsed_prefix_bytes"]
    decoded = schedule.read_schedule_sections(reader, counts)
    audit = schedule.audit_schedule(decoded, counts)
    extracted = extract(
        decoded["class_cells"], catalog["groups"], catalog["subjects"], counts["teacher_count"]
    )
    suffix_status: dict[str, Any]
    try:
        tail = suffix.read_suffix(reader, counts, decoded)
    except (ValueError, UnicodeDecodeError) as exc:
        suffix_status = {"read": False, "error": str(exc)[:200]}
    else:
        extracted.teacher_cells, extracted.locks = teacher_constraints(tail["slot_constraints"])
        limit_status: dict[str, Any] | None = None
        if tail["teacher_properties"] is not None:
            extracted.teacher_limits, invalid = teacher_limits(
                tail["teacher_properties"], counts["teacher_count"]
            )
            extracted.teacher_windows, bad_windows = teacher_windows(
                tail["teacher_properties"], counts["teacher_count"]
            )
            limit_status = {
                "windows": len(extracted.teacher_windows),
                "invalid_windows": bad_windows,
                "max_per_session": sum(a is not None for _, a, _ in extracted.teacher_limits),
                "max_per_day": sum(b is not None for _, _, b in extracted.teacher_limits),
                "invalid": invalid,
            }
        suffix_status = {
            "read": True,
            "absent_from": tail["absent_from"],
            "plans": tail["plans"],
            "teacher_cells": dict(Counter(c[4] for c in extracted.teacher_cells)),
            "locked_cells": len(extracted.locks),
            "teacher_limits": limit_status,
        }
    groups = counts["group_counts"]
    teacher_marks = sum(
        1 for key, record in decoded["teacher_cells"].items() if record[0] > groups[key[0]]
    )
    total, remaining = audit["total_periods"], audit["remaining_periods"]
    if not audit["placed_periods"]:
        category = "empty"
    elif audit["issue_counts"]:
        category = "issues"
    elif remaining == 0:
        category = "full"
    elif remaining <= 0.05 * total:
        category = "near"
    else:
        category = "partial"
    summary = {
        "category": category,
        "classes": len(extracted.class_cells),
        "teachers": counts["teacher_count"],
        "subjects": counts["subject_count"],
        "total_periods": total,
        "placed_periods": audit["placed_periods"],
        "remaining_periods": remaining,
        "audit_issues": audit["issue_counts"],
        "rows": len(extracted.rows),
        "no_teacher_rows": extracted.no_teacher_rows,
        "class_marker_cells": {str(k): v for k, v in sorted(extracted.markers.items())},
        "teacher_marker_cells": teacher_marks,
        "class_cells": sum(len(c) for c in extracted.class_cells.values()),
        "suffix": suffix_status,
    }
    return extracted, summary


def write_csvs(extracted: Extracted, folder: Path) -> None:
    folder.mkdir(parents=True)
    with (folder / "tkb.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("lop", "thu", "buoi", "tiet", "mon", "ma_gv"))
        writer.writerows(extracted.rows)
    with (folder / "class-cells.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("lop", "thu", "buoi", "tiet"))
        for name in sorted(extracted.class_cells):
            writer.writerows((name, *cell) for cell in sorted(extracted.class_cells[name]))
    if extracted.teacher_cells is not None:
        with (folder / "teacher-cells.csv").open("x", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(("ma_gv", "thu", "buoi", "tiet", "loai"))
            writer.writerows(extracted.teacher_cells)
    if extracted.locks is not None:
        with (folder / "locks.csv").open("x", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(("ma_gv", "thu", "buoi", "tiet"))
            writer.writerows(extracted.locks)
    if extracted.teacher_windows is not None:
        with (folder / "teacher-windows.csv").open("x", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(("ma_gv", "buoi", "tu_tiet", "den_tiet"))
            writer.writerows(extracted.teacher_windows)
    if extracted.teacher_limits is not None:
        with (folder / "teacher-limits.csv").open("x", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(("ma_gv", "max_tiet_buoi", "max_tiet_ngay"))
            writer.writerows(
                (t, "" if a is None else a, "" if b is None else b)
                for t, a, b in extracted.teacher_limits
            )


def school_key(path: Path) -> str:
    """Files saved by ``stkb_api download`` are named ``<site>_<year>_<term>_<file>.STKB``."""
    return path.stem.split("_", 1)[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", type=Path, help=".STKB files")
    parser.add_argument("--output", type=Path, required=True, help="new directory for the results")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"output {args.output} already exists; nothing is overwritten")
    keys = [school_key(p) for p in args.files]
    if len(set(keys)) != len(keys):
        parser.error("two files map to the same school; pass one file per school")
    args.output.mkdir(parents=True)
    results = []
    for path, key in zip(args.files, keys, strict=True):
        try:
            extracted, summary = read_file(path.read_bytes())
        except (ValueError, UnicodeDecodeError, struct.error, IndexError, KeyError) as exc:
            # One unreadable file must not abort the batch and lose summary.json.
            results.append({"school": key, "file": path.name, "error": str(exc)[:200]})
            continue
        if extracted.rows:
            write_csvs(extracted, args.output / key)
        results.append({"school": key, "file": path.name, **summary})
    with (args.output / "summary.json").open("x", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=1)
    print(json.dumps(Counter(r.get("category", "error") for r in results), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
