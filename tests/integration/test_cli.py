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
    process = run_cli("benchmark", "unused.json")
    assert process.returncode == 2
    assert json.loads(process.stdout)["status"] == "UNSUPPORTED_FEATURE"


def test_generated_json_schema_describes_versions() -> None:
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.contracts.output import ScheduleResult

    for contract in (ScheduleInput, ScheduleResult):
        schema = contract.model_json_schema()
        version = schema["properties"]["schema_version"]
        assert version.get("const") == "1.0" or version.get("enum") == ["1.0", "1.1"]
        assert "schema_version" in schema["required"]


def test_solve_file_and_revalidate_independently(tmp_path: Path) -> None:
    result_file = tmp_path / "result.json"
    source = ROOT / "tests/fixtures/feasible_double.json"
    solved = run_cli("solve", str(source), "--time-limit", "5", "--output", str(result_file))
    assert solved.returncode == 0, solved.stdout + solved.stderr
    result = json.loads(solved.stdout)
    assert result["valid_schedule"] and result["schema_version"] == "1.1"
    assert json.loads(result_file.read_text()) == result
    checked = run_cli("validate-schedule", str(source), str(result_file))
    assert checked.returncode == 0 and json.loads(checked.stdout)["valid_schedule"]


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_output_must_not_overwrite_input(tmp_path: Path, alias: str) -> None:
    source = tmp_path / "problem.json"
    source.write_bytes((ROOT / "tests/fixtures/feasible_small.json").read_bytes())
    original = source.read_bytes()
    output = source
    if alias == "symlink":
        output = tmp_path / "alias.json"
        output.symlink_to(source)
    elif alias == "hardlink":
        output = tmp_path / "alias.json"
        output.hardlink_to(source)
    process = run_cli("solve", str(source), "--output", str(output))
    assert process.returncode == 2
    assert json.loads(process.stdout)["diagnostics"][0]["code"] == "OUTPUT_CONFLICT"
    assert source.read_bytes() == original


def test_failed_output_write_is_not_success(tmp_path: Path) -> None:
    process = run_cli(
        "solve",
        str(ROOT / "tests/fixtures/feasible_small.json"),
        "--output",
        str(tmp_path / "missing" / "result.json"),
    )
    assert process.returncode == 2
    assert json.loads(process.stdout)["diagnostics"][0]["code"] == "OUTPUT_WRITE_ERROR"


def test_stale_and_forged_validation_are_not_trusted(tmp_path: Path) -> None:
    source = ROOT / "tests/fixtures/feasible_small.json"
    process = run_cli("solve", str(source))
    assert process.returncode == 0
    result = json.loads(process.stdout)
    path = tmp_path / "result.json"
    result["input_fingerprint"] = "0" * 64
    path.write_text(json.dumps(result))
    stale = run_cli("validate-schedule", str(source), str(path))
    assert stale.returncode == 2
    assert json.loads(stale.stdout)["diagnostics"][0]["code"] == "STALE_RESULT"
    result["input_fingerprint"] = json.loads(process.stdout)["input_fingerprint"]
    result["assignments"][0]["teacher_ids"] = ["forged-teacher"]
    path.write_text(json.dumps(result))
    forged = run_cli("validate-schedule", str(source), str(path))
    assert forged.returncode == 2 and not json.loads(forged.stdout)["valid_schedule"]


def test_infeasible_and_guard_have_distinct_exit_codes() -> None:
    bad = run_cli("solve", str(ROOT / "tests/fixtures/infeasible_teacher.json"))
    assert bad.returncode == 3 and json.loads(bad.stdout)["status"] == "INFEASIBLE"
    limited = run_cli(
        "solve", str(ROOT / "tests/fixtures/feasible_small.json"), "--max-placements", "1"
    )
    assert limited.returncode == 4 and json.loads(limited.stdout)["status"] == "UNKNOWN"
