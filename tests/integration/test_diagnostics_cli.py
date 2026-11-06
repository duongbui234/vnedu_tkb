"""CLI for Phase 3B: explain -> check-explanation, argument rules, forged reports (Task 8)."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tkb_core.cli import main

FIXTURES = Path(__file__).parents[1] / "fixtures"
ARGS = ["--time-limit", "10", "--seed", "3", "--granularity", "FULL"]


def _run(argv: list[str], capsys: Any) -> tuple[int, dict[str, Any]]:
    code = main(argv)
    return code, json.loads(capsys.readouterr().out)


def test_explain_then_check_on_core_subset(
    triangle_case: dict[str, Any], tmp_path: Path, capsys: Any
) -> None:
    source, report = tmp_path / "in.json", tmp_path / "report.json"
    source.write_text(json.dumps(triangle_case))
    code, out = _run(["explain", str(source), *ARGS, "--output", str(report)], capsys)
    assert code == 0 and out["status"] == "CORE_SUBSET" and out["minimal_proved"]
    assert json.loads(report.read_text()) == out
    code, checked = _run(["check-explanation", str(source), str(report)], capsys)
    assert code == 0 and checked["report_status"] == "CORE_SUBSET"
    assert checked["infeasibility_evidence"] == "SOLVER" and not checked["minimality_rechecked"]


def test_explain_then_check_on_precheck_fixture(tmp_path: Path, capsys: Any) -> None:
    source = FIXTURES / "infeasible_teacher.json"
    report = tmp_path / "report.json"
    code, out = _run(["explain", str(source), *ARGS, "--output", str(report)], capsys)
    assert code == 0 and out["status"] == "PRECHECK_PROOF"
    code, checked = _run(["check-explanation", str(source), str(report)], capsys)
    assert code == 0 and checked["precheck_proofs_verified"] == len(out["precheck_proofs"]) > 0


@pytest.mark.parametrize(
    "argv",
    [
        ["--seed", "3", "--granularity", "FULL"],
        ["--time-limit", "10", "--granularity", "FULL"],
        ["--time-limit", "10", "--seed", "3"],
        ["--time-limit", "10", "--seed", "3", "--granularity", "SOME"],
    ],
)
def test_explain_requires_every_decision(argv: list[str], capsys: Any) -> None:
    code, out = _run(["explain", str(FIXTURES / "feasible_small.json"), *argv], capsys)
    assert code == 2 and out["diagnostics"][0]["code"] == "INVALID_ARGUMENTS"


def test_explain_rejects_invalid_options(capsys: Any) -> None:
    code, out = _run(
        [
            "explain",
            str(FIXTURES / "feasible_small.json"),
            "--time-limit",
            "0",
            "--seed",
            "1",
            "--granularity",
            "MODEL",
        ],
        capsys,
    )
    assert code == 2 and out["diagnostics"][0]["code"] == "OPTIONS_INVALID"


def test_forged_and_stale_reports_are_refused(tmp_path: Path, capsys: Any) -> None:
    source = FIXTURES / "infeasible_teacher.json"
    report = tmp_path / "report.json"
    _, out = _run(["explain", str(source), *ARGS, "--output", str(report)], capsys)
    forged = json.loads(json.dumps(out))
    forged["precheck_proofs"][0]["available"] = forged["precheck_proofs"][0]["required"] - 1
    forged["precheck_proofs"][0]["required"] += 5
    report.write_text(json.dumps(forged))
    code, err = _run(["check-explanation", str(source), str(report)], capsys)
    assert code == 2 and err["diagnostics"][0]["code"] == "EXPLANATION_MISMATCH"
    report.write_text(json.dumps(out))
    code, err = _run(
        ["check-explanation", str(FIXTURES / "feasible_small.json"), str(report)], capsys
    )
    assert code == 2 and err["diagnostics"][0]["code"] == "STALE_RESULT"
    report.write_text(json.dumps(out | {"status": "NOT_INFEASIBLE"}))
    code, err = _run(["check-explanation", str(source), str(report)], capsys)
    assert code == 2 and err["diagnostics"][0]["code"] == "EXPLANATION_INVALID"


def test_check_explanation_runs_without_ortools(tmp_path: Path, capsys: Any) -> None:
    source = FIXTURES / "infeasible_teacher.json"
    report = tmp_path / "report.json"
    _run(["explain", str(source), *ARGS, "--output", str(report)], capsys)
    script = f"""
import builtins, json, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(('ortools', 'tkb_core.diagnostics')):
        raise ImportError('forbidden import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from tkb_core.cli import main
sys.exit(main(['check-explanation', {str(source)!r}, {str(report)!r}]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "OK"


def test_old_commands_keep_their_behaviour(capsys: Any) -> None:
    code, out = _run(["validate-input", str(FIXTURES / "feasible_small.json")], capsys)
    assert code == 0 and out["status"] == "INPUT_VALID"
    code, out = _run(
        ["solve", str(FIXTURES / "infeasible_teacher.json"), "--time-limit", "5"], capsys
    )
    assert code == 3 and out["status"] == "INFEASIBLE"
