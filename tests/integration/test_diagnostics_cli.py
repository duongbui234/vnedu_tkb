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


def test_explain_model_invalid_exits_5(
    triangle_case: dict[str, Any], tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F3: same exit code as solve/repair for a model failure."""
    from tkb_core.domain.errors import CoreError

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise CoreError("MODEL_INVALID", "DIAGNOSTIC_MODEL", "Diagnostic model was rejected")

    monkeypatch.setattr("tkb_core.diagnostics.pipeline.build_diagnostic_model", broken)
    source = tmp_path / "in.json"
    source.write_text(json.dumps(triangle_case))
    code, out = _run(["explain", str(source), *ARGS], capsys)
    assert code == 5 and out["status"] == "MODEL_INVALID"


@pytest.mark.parametrize(
    ("needs_solver", "exit_code", "status"),
    [(False, 0, "PRECHECK_PROOF"), (True, 2, "UNSUPPORTED_FEATURE")],
)
def test_explain_without_ortools(
    triangle_case: dict[str, Any], tmp_path: Path, needs_solver: bool, exit_code: int, status: str
) -> None:
    """F6: counting proofs need no solver; otherwise a structured SOLVER_NOT_INSTALLED error."""
    source = tmp_path / "in.json"
    if needs_solver:
        source.write_text(json.dumps(triangle_case))
    else:
        source.write_text((FIXTURES / "infeasible_teacher.json").read_text())
    script = f"""
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith('ortools'):
        raise ImportError('No module named ' + repr(name))
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from tkb_core.cli import main
sys.exit(main(['explain', {str(source)!r}, '--time-limit', '5', '--seed', '1',
               '--granularity', 'FULL']))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == exit_code, result.stderr
    out = json.loads(result.stdout)
    assert out["status"] == status
    if needs_solver:
        assert out["diagnostics"][0]["code"] == "SOLVER_NOT_INSTALLED"
    else:
        assert out["metadata"]["solver_calls"] == 0
