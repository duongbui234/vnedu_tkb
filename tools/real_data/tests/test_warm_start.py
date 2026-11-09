"""Warm start from a given schedule, and compare_real with worker/warm-start options."""

import json
from pathlib import Path

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult
from tkb_core.solver import objectives
from tkb_core.validation.independent_validator import validate_schedule
from tools.real_data import compare_real, score_real, warm_start
from tools.real_data import convert_real as cr

# Two classes, three teachers; the real schedule breaks S06 (3 Toán on one day for 6A1).
TIMETABLE = """lop,thu,buoi,tiet,mon,ma_gv
6A1,2,S,1,Toán,GV01
6A1,2,S,2,Toán,GV01
6A1,2,S,3,Toán,GV01
6A1,3,S,1,Văn,GV02
6A1,3,S,2,Anh,GV03
6A1,4,S,1,Văn,GV02
6A2,2,S,3,Văn,GV02
6A2,3,S,1,Toán,GV01
6A2,3,S,3,Anh,GV03
6A2,4,S,2,Toán,GV01
"""


def _converted(tmp_path: Path, *, reverse: bool) -> Path:
    conv = cr.convert(cr.parse_timetable(TIMETABLE), school="T")
    if reverse:  # the order bug: file order differs from Core's occurrence order
        conv.previous["assignments"].reverse()
    folder = tmp_path / "conv"
    folder.mkdir()
    for name, data in (("input.json", conv.input), ("real-assignments.json", conv.previous)):
        (folder / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return folder


@pytest.mark.parametrize("reverse", [False, True])
def test_warm_start_runs_quality_from_the_given_schedule(tmp_path: Path, reverse: bool) -> None:
    folder = _converted(tmp_path, reverse=reverse)
    out = tmp_path / "result.json"
    args = [
        str(folder / "real-assignments.json"),
        "solve",
        str(folder / "input.json"),
        "--output",
        str(out),
        "--time-limit",
        "20",
        "--workers",
        "2",
        "--seed",
        "42",
    ]
    assert warm_start.main(args) == 0
    assert objectives._run_stage.__name__ == "_run_stage"  # patch removed
    result = ScheduleResult.model_validate_json(out.read_text(encoding="utf-8"))
    problem = ScheduleInput.model_validate_json((folder / "input.json").read_text())
    assert result.status in ("FEASIBLE", "OPTIMAL")
    assert validate_schedule(problem, result.assignments).valid
    real = score_real.score_files(folder / "input.json", folder / "real-assignments.json")
    assert result.quality is not None and result.quality.score is not None
    assert tuple(result.quality.score.tiers or ()) <= tuple(real["tiers"])


def test_compare_with_workers_and_warm_start(tmp_path: Path) -> None:
    folder = _converted(tmp_path, reverse=True)
    report = compare_real.compare(folder, tmp_path, 20.0, workers=2, warm_start=True)
    run = report["core"]["run"]
    assert run["workers"] == 2 and run["warm_start"] and run["exit"] == 0
    assert warm_start.APPLIED in run["stderr"]
    assert report["core"]["hard_valid"] and report["core"]["independent_score_matches"]
    assert [t["priority"] for t in report["core"]["tier_runs"]] == [1, 2, 3]
    assert report["lexicographic"] in ("CORE_BETTER", "EQUAL")
    assert "2 worker, warm start" in compare_real.render(report)
