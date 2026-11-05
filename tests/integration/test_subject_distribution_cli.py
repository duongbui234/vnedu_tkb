"""CLI roundtrip for policy 0.3: solve -> 1.4 -> independent rechecks (Phase 2C-1)."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tkb_core.cli import main

HARD = {"id": "sd", "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY", "parameters": {"limit": 2}}
SOFT = {
    "id": "spread",
    "code": "SUBJECT_COMPONENT_DAY_SPREAD",
    "parameters": {"requirement_ids": ["r"], "min_day_gap": 2},
    "priority": 1,
    "weight": 1,
}


def _files(data: dict[str, Any], tmp_path: Path) -> tuple[Path, Path]:
    p, r = tmp_path / "p.json", tmp_path / "r.json"
    p.write_text(json.dumps(data))
    return p, r


def test_solve_validate_and_score(dist_case: dict[str, Any], tmp_path: Path, capsys: Any) -> None:
    dist_case["constraint_config"].update(hard=[HARD], soft=[SOFT])
    p, r = _files(dist_case, tmp_path)
    assert main(["solve", str(p), "--output", str(r)]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == "1.4"
    assert main(["validate-schedule", str(p), str(r)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["schema_version"], report["valid_schedule"]) == ("1.4", True)
    assert main(["evaluate-score", str(p), str(r)]) == 0
    score = json.loads(capsys.readouterr().out)
    assert (score["schema_version"], score["tiers"]) == ("1.1", [2, 0, 0])
    assert score["rules"][0]["unit"] == "day_gap_shortfall"


def test_forged_result_violating_hard_rule(
    dist_case: dict[str, Any], tmp_path: Path, capsys: Any
) -> None:
    dist_case["constraint_config"]["soft"] = [SOFT]
    p, r = _files(dist_case, tmp_path)
    assert main(["solve", str(p), "--output", str(r)]) == 0
    capsys.readouterr()
    raw = json.loads(r.read_text())
    for assignment, slot in zip(raw["assignments"], ["1-AM-1", "1-PM-1", "3-AM-1"], strict=True):
        assignment["slot_id"] = slot
    dist_case["constraint_config"]["hard"] = [HARD]
    p.write_text(json.dumps(dist_case))
    from tkb_core.contracts.input import ScheduleInput

    fingerprint = ScheduleInput.model_validate(dist_case).fingerprint()
    raw["input_fingerprint"] = raw["quality"]["score"]["input_fingerprint"] = fingerprint
    r.write_text(json.dumps(raw))
    assert main(["evaluate-score", str(p), str(r)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert (out["status"], out["schema_version"]) == ("INVALID_SCHEDULE", "1.1")
    assert main(["validate-schedule", str(p), str(r)]) == 2


def test_result_version_must_match_policy(
    dist_case: dict[str, Any], tmp_path: Path, capsys: Any
) -> None:
    p, r = _files(dist_case, tmp_path)
    assert main(["solve", str(p), "--output", str(r)]) == 0
    capsys.readouterr()
    raw = json.loads(r.read_text())
    raw["schema_version"], raw["quality"]["policy_version"] = "1.3", "0.2"
    raw["quality"]["score"]["schema_version"] = "1.0"
    r.write_text(json.dumps(raw))
    assert main(["evaluate-score", str(p), str(r)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert (out["schema_version"], out["diagnostics"][0]["code"]) == ("1.1", "RESULT_VERSION")


def test_evaluate_score_without_solver_or_compilers(
    dist_case: dict[str, Any], tmp_path: Path
) -> None:
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.solver.cp_sat import solve

    dist_case["constraint_config"].update(hard=[HARD], soft=[SOFT])
    p, r = _files(dist_case, tmp_path)
    r.write_text(solve(ScheduleInput.model_validate(dist_case)).model_dump_json())
    script = """
import builtins,sys
original=builtins.__import__
def guarded(name,*args,**kwargs):
    blocked=('ortools','tkb_core.preprocessing','tkb_core.constraints.soft',
             'tkb_core.constraints.hard','tkb_core.constraints.hard_variants',
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
    assert json.loads(proc.stdout)["tiers"] == [2, 0, 0]
