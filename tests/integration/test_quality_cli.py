"""CLI recomputes quality rather than trusting result claims."""

import json
from pathlib import Path
from typing import Any

from tkb_core.cli import main


def test_solve_score_and_forged_score(
    quality_case: dict[str, Any], tmp_path: Path, capsys: Any
) -> None:
    quality_case["constraint_config"]["soft"] = [
        {
            "id": "pref",
            "code": "TEACHER_MAX_PERIODS_PER_DAY",
            "parameters": {"limit": 1},
            "weight": 1,
            "priority": 1,
        }
    ]
    p = tmp_path / "p.json"
    r = tmp_path / "r.json"
    p.write_text(json.dumps(quality_case))
    assert main(["solve", str(p), "--output", str(r)]) == 0
    capsys.readouterr()
    assert main(["evaluate-score", str(p), str(r)]) == 0
    score = json.loads(capsys.readouterr().out)
    assert score["status"] == "OK" and score["tiers"] == [2, 0, 0]
    assert main(["validate-schedule", str(p), str(r)]) == 0
    assert json.loads(capsys.readouterr().out)["score"] == score
    raw = json.loads(r.read_text())
    raw["quality"]["score"]["rules"][0]["raw_penalty"] += 1
    raw["quality"]["score"]["rules"][0]["weighted_penalty"] += 1
    raw["quality"]["score"]["tiers"][0] += 1
    r.write_text(json.dumps(raw))
    assert main(["evaluate-score", str(p), str(r)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "INPUT_INVALID" and out["tiers"] is None
    assert out["diagnostics"][0]["code"] == "RESULT_SCORE_MISMATCH"


def test_score_malformed_json_is_score_report(tmp_path: Path, capsys: Any) -> None:
    p = tmp_path / "bad"
    p.write_text('{"schema_version":NaN}')
    assert main(["evaluate-score", str(p), str(p)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["schema_version"] == "1.0" and out["tiers"] is None and out["rules"] == []


def test_evaluate_score_without_solver_imports(
    quality_case: dict[str, Any], tmp_path: Path
) -> None:
    import subprocess
    import sys

    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.solver.cp_sat import solve

    p = tmp_path / "p.json"
    r = tmp_path / "r.json"
    p.write_text(json.dumps(quality_case))
    r.write_text(solve(ScheduleInput.model_validate(quality_case)).model_dump_json())
    script = """
import builtins,sys
original=builtins.__import__
def guarded(name,*args,**kwargs):
    blocked=('ortools','tkb_core.preprocessing','tkb_core.constraints.soft',
             'tkb_core.solver.objectives','tkb_core.solver.model_builder')
    if name.startswith(blocked):
        raise ImportError('blocked '+name)
    return original(name,*args,**kwargs)
builtins.__import__=guarded
from tkb_core.cli import main
raise SystemExit(main(['evaluate-score',sys.argv[1],sys.argv[2]]))
"""
    proc = subprocess.run(
        [sys.executable, "-c", script, str(p), str(r)], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["status"] == "OK"
