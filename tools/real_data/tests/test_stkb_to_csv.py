"""STKB decoded cells -> canonical rows and class cells (synthetic catalogs, no real file)."""

from pathlib import Path

import pytest

from tools.real_data import convert_real as cr
from tools.real_data import stkb_to_csv as st

GROUPS = [[["6A1", "11"], ["6A2", "12"]], [["6A1", "11"]]]
SUBJECTS = [["Toán", "Toán học", "1"], ["Văn", "Ngữ văn", "2"]]


def _cell(subject: int, teacher: int = 0) -> tuple[int, ...]:
    return (subject, teacher, 0, 0, 0, 0, 0, 0, 0)


def _decoded() -> dict[tuple[int, int, int, int], tuple[int, ...]]:
    cells = {
        (g, c, d, p): _cell(0)
        for g, size in enumerate((2, 1))
        for c in range(1, size + 1)
        for d in range(1, 8)
        for p in range(1, 6)
    }
    cells[(0, 1, 1, 1)] = _cell(1, 3)  # 6A1 Monday(thu 2) morning P1 Toán GV003
    cells[(0, 1, 1, 2)] = _cell(1, 3)
    cells[(0, 1, 1, 5)] = _cell(255)  # marked cell in a taught session
    cells[(0, 2, 2, 1)] = _cell(2, 0)  # 6A2 thu 3 morning, no teacher
    cells[(1, 1, 1, 3)] = _cell(2, 4)  # 6A1 thu 2 afternoon
    cells[(1, 1, 4, 1)] = _cell(254)  # marked cell in an untaught session: no cells anyway
    return cells


def test_extract_rows_sessions_and_pseudonyms() -> None:
    ex = st.extract(_decoded(), GROUPS, SUBJECTS, teacher_count=4)
    assert sorted(ex.rows) == [
        ("6A1", 2, "C", 3, "Văn", "GV004"),
        ("6A1", 2, "S", 1, "Toán", "GV003"),
        ("6A1", 2, "S", 2, "Toán", "GV003"),
        ("6A2", 3, "S", 1, "Văn", ""),
    ]
    assert ex.no_teacher_rows == 1
    assert ex.markers == {255: 1, 254: 1}


def test_class_cells_cover_taught_sessions_minus_marks() -> None:
    ex = st.extract(_decoded(), GROUPS, SUBJECTS, teacher_count=4)
    assert ex.class_cells["6A1"] == {(2, "S", p) for p in (1, 2, 3, 4)} | {
        (2, "C", p) for p in range(1, 6)
    }
    assert ex.class_cells["6A2"] == {(3, "S", p) for p in range(1, 6)}


def test_same_name_two_ids_is_rejected() -> None:
    groups = [[["6A1", "11"]], [["6A1", "99"]]]
    cells = {(0, 1, 1, 1): _cell(1, 1), (1, 1, 1, 1): _cell(1, 1)}
    with pytest.raises(ValueError, match="two class ids"):
        st.extract(cells, groups, SUBJECTS, teacher_count=1)


def test_csvs_feed_convert_real(tmp_path: Path) -> None:
    ex = st.extract(_decoded(), GROUPS, SUBJECTS, teacher_count=4)
    ex.rows = [r for r in ex.rows if r[5]]  # convert_real excludes teacherless cells anyway
    st.write_csvs(ex, tmp_path / "s")
    rows = cr.parse_timetable((tmp_path / "s" / "tkb.csv").read_text(encoding="utf-8"))
    cells = cr.parse_class_cells((tmp_path / "s" / "class-cells.csv").read_text(encoding="utf-8"))
    conv = cr.convert(rows, class_cells=cells)
    assert conv.report["class_availability"]["source"] == "class-cells"
    assert st.school_key(Path("123456789_2026_1_123.STKB")) == "123456789"


def test_read_file_rejects_non_stkb_bytes() -> None:
    with pytest.raises(ValueError):
        st.read_file(b"not an stkb file at all")


def test_teacher_constraints_codes_and_locks() -> None:
    slots = {
        (0, 1, 1, 1): (1000, 0),
        (0, 1, 1, 2): (1006, 1),
        (1, 2, 3, 4): (998, 0),
        (1, 2, 3, 5): (999, 0),
        (0, 2, 2, 1): (997, 0),
        (0, 3, 2, 1): (42, 0),
        (0, 3, 2, 2): (0, 1),
        (0, 3, 2, 3): (0, 0),
    }
    cells, locks = st.teacher_constraints(slots)
    assert cells == [
        ("GV001", 2, "S", 1, "hop"),
        ("GV001", 2, "S", 2, "hop"),
        ("GV002", 3, "S", 1, "hanche"),
        ("GV003", 3, "S", 1, "ma_42"),
        ("GV002", 4, "C", 4, "nghi"),
        ("GV002", 4, "C", 5, "ban"),
    ]
    assert locks == [("GV001", 2, "S", 2), ("GV003", 3, "S", 2)]


def test_teacher_limits_use_enable_flags() -> None:
    import struct

    props = bytearray(96 * 3)
    # GV001: max/buổi on (+1) = 3, max/ngày on (+2) = 6
    props[1], props[2] = 1, 1
    struct.pack_into("<i", props, 24, 3)
    struct.pack_into("<i", props, 28, 6)
    # GV002: values stored but both flags off -> no limit (report 08: never use disabled values)
    struct.pack_into("<i", props, 96 + 24, 5)
    struct.pack_into("<i", props, 96 + 28, 10)
    # GV003: max/ngày on with 0 -> not a usable limit, counted as invalid
    props[192 + 2] = 1
    limits, invalid = st.teacher_limits(bytes(props), 3)
    assert limits == [("GV001", 3, 6), ("GV002", None, None), ("GV003", None, None)]
    assert invalid == 1
    with pytest.raises(ValueError, match="96"):
        st.teacher_limits(bytes(95), 1)


def test_teacher_limits_csv_round_trip(tmp_path: Path) -> None:
    ex = st.extract(_decoded(), GROUPS, SUBJECTS, teacher_count=4)
    ex.teacher_limits = [("GV001", 3, None), ("GV002", None, 6)]
    st.write_csvs(ex, tmp_path / "s")
    text = (tmp_path / "s" / "teacher-limits.csv").read_text(encoding="utf-8")
    assert cr.parse_teacher_limits(text) == {"GV001": (3, None), "GV002": (None, 6)}


def test_teacher_windows_use_session_flags() -> None:
    import struct

    props = bytearray(96 * 3)
    props[3] = 1  # GV001 morning window 2..4 (byte +3, i32 +32/+36)
    struct.pack_into("<2i", props, 32, 2, 4)
    struct.pack_into("<2i", props, 40, 1, 3)  # afternoon values stored, flag +4 off: ignored
    props[96 + 4] = 1  # GV002 afternoon window 1..2 (byte +4, i32 +40/+44)
    struct.pack_into("<2i", props, 96 + 40, 1, 2)
    props[192 + 3] = 1  # GV003 morning window 4..2: not usable, counted
    struct.pack_into("<2i", props, 192 + 32, 4, 2)
    windows, invalid = st.teacher_windows(bytes(props), 3)
    assert windows == [("GV001", "S", 2, 4), ("GV002", "C", 1, 2)]
    assert invalid == 1


def test_teacher_windows_csv_round_trip(tmp_path: Path) -> None:
    ex = st.extract(_decoded(), GROUPS, SUBJECTS, teacher_count=4)
    ex.teacher_windows = [("GV001", "S", 2, 4), ("GV002", "C", 1, 2)]
    st.write_csvs(ex, tmp_path / "s")
    text = (tmp_path / "s" / "teacher-windows.csv").read_text(encoding="utf-8")
    assert cr.parse_teacher_windows(text) == {"GV001": {"AM": (2, 4)}, "GV002": {"PM": (1, 2)}}
