"""CLI roundtrip for policy 0.2: solve -> 1.3 -> independent rechecks (Phase 2B)."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tkb_core.cli import main

HARD = {"id": "h", "code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 2}}


def _files(data: dict[str, Any], tmp_path: Path) -> tuple[Path, Path]:
    p, r = tmp_path / "p.json", tmp_path / "r.json"
    p.write_text(json.dumps(data))
    return p, r


def test_solve_validate_and_score(hard_case: dict[str, Any], tmp_path: Path, capsys: Any) -> None:
    hard_case["constraint_config"]["hard"] = [HARD]
    p, r = _files(hard_case, tmp_path)
    assert main(["solve", str(p), "--output", str(r)]) == 0
    assert json.loads(capsys.readouterr().out)["schema_version"] == "1.3"
    assert main(["validate-schedule", str(p), str(r)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "1.3" and report["valid_schedule"]
    assert main(["evaluate-score", str(p), str(r)]) == 0
    assert json.loads(capsys.readouterr().out)["tiers"] == [0, 0, 0]


def test_forged_result_violating_hard_rule(
    hard_case: dict[str, Any], tmp_path: Path, capsys: Any
) -> None:
    p, r = _files(hard_case, tmp_path)
    assert main(["solve", str(p), "--output", str(r)]) == 0
    capsys.readouterr()
    raw = json.loads(r.read_text())
    day_1 = ["1-AM-1", "1-AM-3", "1-AM-4"]
    for assignment, slot in zip(raw["assignments"], day_1, strict=True):
        assignment["slot_id"] = slot
    hard_case["constraint_config"]["hard"] = [HARD]
    p.write_text(json.dumps(hard_case))
    from tkb_core.contracts.input import ScheduleInput

    fingerprint = ScheduleInput.model_validate(hard_case).fingerprint()
    raw["input_fingerprint"] = raw["quality"]["score"]["input_fingerprint"] = fingerprint
    raw["schema_version"], raw["quality"]["policy_version"] = "1.3", "0.2"
    raw["validation"] = {"valid": True, "violations": []}
    r.write_text(json.dumps(raw))
    assert main(["validate-schedule", str(p), str(r)]) == 2
    out = capsys.readouterr().out
    assert json.loads(out)["diagnostics"][0]["code"] == "INVALID_SCHEDULE"
    assert main(["evaluate-score", str(p), str(r)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "INVALID_SCHEDULE"


def test_policy_and_result_version_must_pair(
    hard_case: dict[str, Any], tmp_path: Path, capsys: Any
) -> None:
    p, r = _files(hard_case, tmp_path)
    assert main(["solve", str(p), "--output", str(r)]) == 0
    capsys.readouterr()
    raw = json.loads(r.read_text())
    raw["schema_version"], raw["quality"]["policy_version"] = "1.2", "0.1"
    r.write_text(json.dumps(raw))
    assert main(["validate-schedule", str(p), str(r)]) == 2
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "RESULT_VERSION"


def test_evaluate_score_without_solver_or_compilers(
    hard_case: dict[str, Any], tmp_path: Path
) -> None:
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.solver.cp_sat import solve

    hard_case["constraint_config"]["hard"] = [HARD]
    p, r = _files(hard_case, tmp_path)
    r.write_text(solve(ScheduleInput.model_validate(hard_case)).model_dump_json())
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
    assert json.loads(proc.stdout)["status"] == "OK"
