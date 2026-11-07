"""Scoring the real schedule independently, and comparing it with a Core schedule."""

import json
from pathlib import Path

from tools.real_data import compare_real, convert_real, make_template, score_real

TEXT = """lop,thu,buoi,tiet,mon,ma_gv
6A1,2,S,1,Toán,GV01
6A1,2,S,2,Toán,GV01
6A1,2,S,3,Toán,GV01
6A1,2,S,4,Văn,GV02
6A1,3,S,1,Văn,GV02
6A2,2,S,4,Toán,GV01
6A2,2,S,5,Toán,GV01
6A2,3,S,3,Văn,GV02
"""


def _write(tmp_path: Path, text: str = TEXT) -> Path:
    src = tmp_path / "tkb.csv"
    src.write_text(text, encoding="utf-8")
    out = tmp_path / "conv"
    assert convert_real.main([str(src), "--output", str(out), "--school", "SCH01"]) == 0
    return out


def test_score_real_reports_hard_and_scale(tmp_path: Path) -> None:
    out = _write(tmp_path)
    report = score_real.score_files(out / "input.json", out / "real-assignments.json")
    assert report["hard_valid"] is True
    # GV01 teaches 5 periods in the day-2 morning: S02 (<= 4/session) is exceeded by 1.
    assert report["rules"]["TEACHER_MAX_PERIODS_PER_SESSION"]["raw_penalty"] == 1
    # 6A1 has 3 Toan periods on day 2: S06 (<= 2/day) exceeded by 1.
    assert report["rules"]["CLASS_SUBJECT_MAX_PERIODS_PER_DAY"]["raw_penalty"] == 1
    assert report["tiers"][0] == 2
    assert report["worst_teachers"][0]["teacher"] == "GV01"
    assert report["counts"] == {"classes": 2, "teachers": 2, "requirements": 4, "periods": 8}


def test_score_real_flags_a_clash(tmp_path: Path) -> None:
    out = _write(tmp_path)
    data = json.loads((out / "real-assignments.json").read_text())
    # Move a Van period onto a slot where GV02 already teaches.
    for a in data["assignments"]:
        if a["occurrence_id"] == "6A2|Văn|GV02::1":
            a["slot_id"] = "3-AM-1"
    (out / "real-assignments.json").write_text(json.dumps(data))
    report = score_real.score_files(out / "input.json", out / "real-assignments.json")
    assert report["hard_valid"] is False and report["hard_violations"]


def test_compare_real_runs_core_and_checks_independently(tmp_path: Path) -> None:
    out = _write(tmp_path)
    cmp_dir = tmp_path / "cmp"
    assert compare_real.main([str(out), "--output", str(cmp_dir), "--time-limit", "10"]) == 0
    report = json.loads((cmp_dir / "comparison.json").read_text())
    assert report["core"]["status"] in ("FEASIBLE", "OPTIMAL")
    assert report["core"]["hard_valid"] is True
    assert report["core"]["independent_score_matches"] is True
    assert report["real"]["tiers"][0] == 2
    rows = {r["code"]: r for r in report["by_rule"]}
    assert set(rows["CLASS_SUBJECT_MAX_PERIODS_PER_DAY"]) == {"code", "real", "core", "better"}
    assert report["lexicographic"] in ("CORE_BETTER", "EQUAL", "REAL_BETTER")
    assert (cmp_dir / "comparison.md").read_text().startswith("# ")


def test_template_xlsx_and_sample(tmp_path: Path) -> None:
    import zipfile

    xlsx = tmp_path / "mau.xlsx"
    make_template.write_xlsx(xlsx)
    with zipfile.ZipFile(xlsx) as z:
        names = set(z.namelist())
        assert {"[Content_Types].xml", "xl/workbook.xml", "xl/worksheets/sheet1.xml"} <= names
        sheet = z.read("xl/worksheets/sheet1.xml").decode()
        assert all(h in sheet for h in ("lop", "thu", "buoi", "tiet", "mon", "ma_gv"))
    # The sample rows shipped with the template convert cleanly.
    rows = convert_real.parse_timetable(make_template.sample_csv())
    assert convert_real.convert(rows).report["excluded"] == []
