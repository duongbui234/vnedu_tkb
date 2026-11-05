"""CLI roundtrip for Phase 3A: solve -> repair -> validate-schedule -> evaluate-repair."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tkb_core.cli import main

REQUEST = {
    "schema_version": "1.0",
    "change_order": "BEFORE_QUALITY",
    "max_changes": None,
    "change_scope": None,
    "use_previous_as_hint": True,
}


@pytest.fixture
def files(gap_case: dict[str, Any], tmp_path: Path, capsys: Any) -> dict[str, Path]:
    """An old input solved by the CLI and a new input where one used slot became unavailable."""
    old, solved = tmp_path / "old.json", tmp_path / "solved.json"
    old.write_text(json.dumps(gap_case))
    assert main(["solve", str(old), "--time-limit", "5", "--output", str(solved)]) == 0
    capsys.readouterr()
    used = json.loads(solved.read_text())["assignments"][-1]["slot_id"]
    gap_case["teachers"][0]["available_slot_ids"] = [
        s["id"] for s in gap_case["time_slots"] if s["id"] != used
    ]
    new, request = tmp_path / "new.json", tmp_path / "request.json"
    new.write_text(json.dumps(gap_case))
    request.write_text(json.dumps(REQUEST))
    return {"old": old, "solved": solved, "new": new, "request": request, "tmp": tmp_path}


def _repair(files: dict[str, Path], previous: Path, capsys: Any) -> tuple[int, dict[str, Any]]:
    out = files["tmp"] / "repaired.json"
    code = main(
        [
            "repair",
            str(files["new"]),
            str(previous),
            "--request",
            str(files["request"]),
            "--time-limit",
            "5",
            "--output",
            str(out),
        ]
    )
    printed = json.loads(capsys.readouterr().out)
    if code == 0:
        assert json.loads(out.read_text()) == printed
    return code, printed


def test_repair_roundtrip(files: dict[str, Path], capsys: Any) -> None:
    code, envelope = _repair(files, files["solved"], capsys)
    assert code == 0
    assert envelope["schema_version"] == "1.0"
    assert envelope["result"]["schema_version"] == "1.5"
    assert envelope["repair"]["changed"] == 1 and envelope["repair"]["forced"] == 1
    result = files["tmp"] / "result-only.json"
    result.write_text(json.dumps(envelope["result"]))
    assert main(["validate-schedule", str(files["new"]), str(result)]) == 0
    assert json.loads(capsys.readouterr().out)["valid_schedule"] is True
    repaired = files["tmp"] / "repaired.json"
    assert main(["evaluate-repair", str(files["new"]), str(files["solved"]), str(repaired)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert (report["status"], report["changed"]) == ("OK", 1)


def test_previous_schedule_file_is_accepted(files: dict[str, Path], capsys: Any) -> None:
    solved = json.loads(files["solved"].read_text())
    previous = files["tmp"] / "previous.json"
    previous.write_text(json.dumps({"schema_version": "1.0", "assignments": solved["assignments"]}))
    code, envelope = _repair(files, previous, capsys)
    assert code == 0 and envelope["repair"]["changed"] == 1
    repaired = files["tmp"] / "repaired.json"
    assert main(["evaluate-repair", str(files["new"]), str(previous), str(repaired)]) == 0


def test_forged_report_and_stale_files_are_rejected(files: dict[str, Path], capsys: Any) -> None:
    assert _repair(files, files["solved"], capsys)[0] == 0
    repaired = files["tmp"] / "repaired.json"
    raw = json.loads(repaired.read_text())
    previous_slot = raw["repair"]["changes"][0]["previous_slot_id"]
    raw["repair"]["changes"][0]["slot_id"] = next(
        s["id"]
        for s in json.loads(files["new"].read_text())["time_slots"]
        if s["id"] not in (previous_slot, raw["repair"]["changes"][0]["slot_id"])
    )
    forged = files["tmp"] / "forged.json"
    forged.write_text(json.dumps(raw))
    assert main(["evaluate-repair", str(files["new"]), str(files["solved"]), str(forged)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["diagnostics"][0]["code"] == "RESULT_REPAIR_MISMATCH"
    # Wrong input, then wrong previous schedule.
    assert main(["evaluate-repair", str(files["old"]), str(files["solved"]), str(repaired)]) == 2
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "STALE_RESULT"
    other = files["tmp"] / "other.json"
    other.write_text(json.dumps({"schema_version": "1.0", "assignments": []}))
    assert main(["evaluate-repair", str(files["new"]), str(other), str(repaired)]) == 2
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "STALE_RESULT"


def test_invalid_request_and_output_conflict(files: dict[str, Path], capsys: Any) -> None:
    files["request"].write_text(json.dumps({**REQUEST, "max_changes": -1}))
    assert _repair(files, files["solved"], capsys)[0] == 2
    files["request"].write_text(json.dumps(REQUEST))
    code = main(
        [
            "repair",
            str(files["new"]),
            str(files["solved"]),
            "--request",
            str(files["request"]),
            "--output",
            str(files["solved"]),
        ]
    )
    assert code == 2
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "OUTPUT_CONFLICT"


def test_request_errors_are_classified(files: dict[str, Path], capsys: Any) -> None:
    files["request"].write_text(json.dumps({**REQUEST, "max_changes": -1}))
    code, out = _repair(files, files["solved"], capsys)
    assert code == 2 and out["diagnostics"][0]["code"] == "REPAIR_REQUEST_INVALID"
    files["request"].write_text(json.dumps(REQUEST))
    bad = files["tmp"] / "bad-previous.json"
    bad.write_text(json.dumps({"schema_version": "1.0", "assignments": [], "x": 1}))
    code, out = _repair(files, bad, capsys)
    assert code == 2 and out["diagnostics"][0]["code"] == "PREVIOUS_SCHEDULE_INVALID"


def test_legacy_input_is_unsupported(
    problem_data: dict[str, Any], files: dict[str, Path], capsys: Any
) -> None:
    files["new"].write_text(json.dumps(problem_data))
    code, envelope = _repair(files, files["solved"], capsys)
    assert code == 2
    assert envelope["result"]["status"] == "UNSUPPORTED_FEATURE"
    assert envelope["result"]["diagnostics"][0]["code"] == "REPAIR_INPUT_VERSION"


def test_evaluate_repair_without_solver_or_compilers(files: dict[str, Path], capsys: Any) -> None:
    assert _repair(files, files["solved"], capsys)[0] == 0
    script = """
import builtins,sys
original=builtins.__import__
def guarded(name,*args,**kwargs):
    blocked=('ortools','tkb_core.preprocessing','tkb_core.constraints.soft',
             'tkb_core.constraints.gaps','tkb_core.constraints.hard',
             'tkb_core.solver.objectives','tkb_core.solver.model_builder',
             'tkb_core.repair')
    if name.startswith(blocked):
        raise ImportError('blocked '+name)
    return original(name,*args,**kwargs)
builtins.__import__=guarded
from tkb_core.cli import main
raise SystemExit(main(['evaluate-repair',sys.argv[1],sys.argv[2],sys.argv[3]]))
"""
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(files["new"]),
            str(files["solved"]),
            str(files["tmp"] / "repaired.json"),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert json.loads(proc.stdout)["status"] == "OK"


def test_evaluate_repair_checks_the_callers_request(files: dict[str, Path], capsys: Any) -> None:
    """Review F1: a result produced under another request is rejected when one is given."""
    assert _repair(files, files["solved"], capsys)[0] == 0
    repaired = files["tmp"] / "repaired.json"
    args = ["evaluate-repair", str(files["new"]), str(files["solved"]), str(repaired)]
    assert main([*args, "--request", str(files["request"])]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "OK"
    stricter = files["tmp"] / "stricter.json"
    stricter.write_text(json.dumps({**REQUEST, "max_changes": 5}))
    assert main([*args, "--request", str(stricter)]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["diagnostics"][0]["code"] == "RESULT_REQUEST_MISMATCH"
    broken = files["tmp"] / "broken.json"
    broken.write_text(json.dumps({**REQUEST, "change_order": "SOMETIMES"}))
    assert main([*args, "--request", str(broken)]) == 2
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == (
        "REPAIR_REQUEST_INVALID"
    )
