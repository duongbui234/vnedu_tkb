"""Exercise the real module/installed CLI boundary in subprocesses."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tkb_core.cli", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize("name", ["feasible_small.json", "empty_requirements.json"])
def test_validate_fixture_reports_only_contract_validity(name: str) -> None:
    process = run_cli("validate-input", str(ROOT / "tests/fixtures" / name))
    assert process.returncode == 0, process.stderr
    data = json.loads(process.stdout)
    assert data["status"] == "INPUT_VALID"
    assert data["checked"] == "contract"
    assert data["solver_executed"] is False
    assert len(data["input_fingerprint"]) == 64
    assert process.stderr == ""


@pytest.mark.parametrize(
    "content", ["{broken", '{"schema_version":"1.0","schema_version":"2.0"}', '{"value":NaN}']
)
def test_malformed_json_is_a_structured_error(tmp_path: Path, content: str) -> None:
    path = tmp_path / "bad.json"
    path.write_text(content)
    process = run_cli("validate-input", str(path))
    assert process.returncode == 2
    assert json.loads(process.stdout)["status"] == "INPUT_INVALID"
    assert "Traceback" not in process.stderr


def test_missing_file_reports_io_error(tmp_path: Path) -> None:
    process = run_cli("validate-input", str(tmp_path / "missing.json"))
    assert process.returncode == 2
    assert json.loads(process.stdout)["diagnostics"][0]["code"] == "INPUT_READ_ERROR"


def test_schema_error_does_not_echo_input_records(
    tmp_path: Path, problem_data: dict[str, Any]
) -> None:
    problem_data["teachers"][0]["password"] = "do-not-print-this"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(problem_data))
    process = run_cli("validate-input", str(path))
    assert process.returncode == 2
    assert json.loads(process.stdout)["status"] == "INPUT_INVALID"
    assert "do-not-print-this" not in process.stdout + process.stderr


def test_phase_zero_does_not_advertise_solve() -> None:
    process = run_cli("solve", "unused.json")
    assert process.returncode == 2
    assert json.loads(process.stdout)["status"] == "UNSUPPORTED_FEATURE"


def test_generated_json_schema_describes_versions() -> None:
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.contracts.output import ScheduleResult

    for contract in (ScheduleInput, ScheduleResult):
        schema = contract.model_json_schema()
        assert schema["properties"]["schema_version"]["const"] == "1.0"
        assert "schema_version" in schema["required"]
