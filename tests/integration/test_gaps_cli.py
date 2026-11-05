"""CLI roundtrip for policy 0.4: solve -> 1.5 -> independent rechecks (Phase 2C-2)."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tkb_core.cli import main


def _case(data: dict[str, Any]) -> dict[str, Any]:
    data["teachers"][0]["available_slot_ids"] = ["1-AM-1", "1-AM-3", "1-AM-4"]
    data["teaching_requirements"][0].update(periods_per_cycle=3, block_durations=[1, 1, 1])
    data["constraint_config"]["soft"] = [
        {
            "id": "g",
            "code": "TEACHER_TOTAL_GAPS",
            "parameters": {"session_ids": ["AM"]},
            "priority": 1,
            "weight": 1,
        }
    ]
    return data


def _files(data: dict[str, Any], tmp_path: Path) -> tuple[Path, Path]:
    p, r = tmp_path / "p.json", tmp_path / "r.json"
    p.write_text(json.dumps(data))
    return p, r


def test_solve_validate_and_score(gap_case: dict[str, Any], tmp_path: Path, capsys: Any) -> None:
    p, r = _files(_case(gap_case), tmp_path)
    assert main(["solve", str(p), "--output", str(r)]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == "1.5"
    assert main(["validate-schedule", str(p), str(r)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["schema_version"], report["valid_schedule"]) == ("1.5", True)
    assert main(["evaluate-score", str(p), str(r)]) == 0
    score = json.loads(capsys.readouterr().out)
    assert (score["schema_version"], score["tiers"]) == ("1.2", [1, 0, 0])
    assert score["rules"][0]["unit"] == "idle_periods"


def test_result_version_must_match_policy(
    gap_case: dict[str, Any], tmp_path: Path, capsys: Any
) -> None:
    gap_case["constraint_config"]["soft"] = []
    p, r = _files(gap_case, tmp_path)
    assert main(["solve", str(p), "--output", str(r)]) == 0
    capsys.readouterr()
    raw = json.loads(r.read_text())
    raw["schema_version"], raw["quality"]["policy_version"] = "1.4", "0.3"
    raw["quality"]["score"]["schema_version"] = "1.1"
    r.write_text(json.dumps(raw))
    assert main(["evaluate-score", str(p), str(r)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert (out["schema_version"], out["diagnostics"][0]["code"]) == ("1.2", "RESULT_VERSION")


def test_forged_score_is_rejected(gap_case: dict[str, Any], tmp_path: Path, capsys: Any) -> None:
    p, r = _files(_case(gap_case), tmp_path)
    assert main(["solve", str(p), "--output", str(r)]) == 0
    capsys.readouterr()
    raw = json.loads(r.read_text())
    row = raw["quality"]["score"]["rules"][0]
    row["raw_penalty"] = row["weighted_penalty"] = 0
    raw["quality"]["score"]["tiers"] = [0, 0, 0]
    raw["quality"]["tier_runs"][0].update(incumbent_value=0, best_bound=0.0)
    r.write_text(json.dumps(raw))
    assert main(["evaluate-score", str(p), str(r)]) == 2
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "RESULT_SCORE_MISMATCH"


def test_evaluate_score_without_solver_or_compilers(
    gap_case: dict[str, Any], tmp_path: Path
) -> None:
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.solver.cp_sat import solve

    data = _case(gap_case)
    p, r = _files(data, tmp_path)
    r.write_text(solve(ScheduleInput.model_validate(data)).model_dump_json())
    script = """
import builtins,sys
original=builtins.__import__
def guarded(name,*args,**kwargs):
    blocked=('ortools','tkb_core.preprocessing','tkb_core.constraints.soft',
             'tkb_core.constraints.gaps','tkb_core.constraints.hard',
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
    assert json.loads(proc.stdout)["tiers"] == [1, 0, 0]
