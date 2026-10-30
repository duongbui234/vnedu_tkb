"""Windows handoff preparation: fake-only checks, never native acceptance."""

import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from benchmarks import windows_payload as payload
from benchmarks import windows_preflight as probe


@pytest.fixture(autouse=True)
def forbid_execution(monkeypatch):
    from ortools.sat.python import cp_model

    monkeypatch.setattr(cp_model, "CpSolver", Mock(side_effect=AssertionError("NO_NATIVE")))
    monkeypatch.setattr(probe.subprocess, "run", Mock(side_effect=AssertionError("NO_CHILD")))


def inventory_for(root):
    data = b"original\n"
    (root / "sample.txt").write_bytes(data)
    return {
        "schema_version": "1.0",
        "status": "PREPARED_NOT_AUTHORIZED",
        "windows_status": "BLOCKED",
        "files": [
            {
                "destination": "sample.txt",
                "size_bytes": len(data),
                "sender_sha256": hashlib.sha256(data).hexdigest(),
                "receiver_sha256": None,
                "receiver_reason": "NOT_TRANSFERRED",
            }
        ],
    }


def test_receiver_hash_is_not_approval(tmp_path):
    inv = inventory_for(tmp_path)
    before = copy.deepcopy(inv)
    result = payload.verify_payload(tmp_path, inv)
    assert result["status"] == "PAYLOAD_HASHES_MATCH"
    assert result["windows_preflight_status"] == "NOT_ASSESSED"
    assert result["execution_authorized"] is False
    assert inv == before


@pytest.mark.parametrize("mutation", ["corrupt", "missing", "extra", "duplicate"])
def test_payload_corruption_and_membership_rejected(tmp_path, mutation):
    inv = inventory_for(tmp_path)
    if mutation == "corrupt":
        (tmp_path / "sample.txt").write_bytes(b"modified\n")
    elif mutation == "missing":
        (tmp_path / "sample.txt").unlink()
    elif mutation == "extra":
        (tmp_path / "extra.txt").write_text("extra")
    else:
        inv["files"].append(copy.deepcopy(inv["files"][0]))
    with pytest.raises(ValueError):
        payload.verify_payload(tmp_path, inv)


@pytest.mark.parametrize("name", ["../x", "/x", "C:/x", "a\\b", "a/../b", "AUX", "a."])
def test_unsafe_transport_paths_rejected(tmp_path, name):
    inv = inventory_for(tmp_path)
    inv["files"][0]["destination"] = name
    with pytest.raises(ValueError):
        payload.verify_payload(tmp_path, inv)


def test_symlinks_and_case_collisions_rejected(tmp_path):
    inv = inventory_for(tmp_path)
    (tmp_path / "alias").symlink_to(tmp_path / "sample.txt")
    with pytest.raises(ValueError):
        payload.verify_payload(tmp_path, inv)
    (tmp_path / "alias").unlink()
    row = dict(inv["files"][0], destination="SAMPLE.txt")
    inv["files"].append(row)
    with pytest.raises(ValueError):
        payload.verify_payload(tmp_path, inv)


def test_bundle_checks_nested_hashes_and_exact_membership(tmp_path):
    case = tmp_path / "c10-base-s101"
    case.mkdir()
    (case / "input.json").write_text("{}")
    raw = {"dataset_id": case.name, "files": {"input.json": payload.sha(b"{}")}}
    (case / "manifest.json").write_text(json.dumps(raw))
    root = {
        "datasets": [
            {
                "dataset_id": case.name,
                "manifest_sha256": payload.sha((case / "manifest.json").read_bytes()),
            }
        ]
    }
    (tmp_path / "manifest.json").write_text(json.dumps(root))
    assert payload.bundle_files(tmp_path, expected_ids={case.name})
    (case / "input.json").write_text('{"changed": true}')
    with pytest.raises(ValueError, match="HASH"):
        payload.bundle_files(tmp_path, expected_ids={case.name})


def test_native_gate_blocks_linux_even_with_reference(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    with pytest.raises(ValueError, match="WINDOWS_NATIVE_REQUIRED"):
        probe.native_gate("user-message-reference")


def test_native_gate_requires_reference_x64_and_isolation(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(probe.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(probe, "isolated", lambda: True)
    with pytest.raises(ValueError, match="APPROVAL_REFERENCE_REQUIRED"):
        probe.native_gate("")
    probe.native_gate("actual-user-approval-reference")
    monkeypatch.setattr(probe, "isolated", lambda: False)
    with pytest.raises(ValueError, match="ISOLATED_INTERPRETER_REQUIRED"):
        probe.native_gate("reference")


def test_guard_blocks_solver_and_restores_importer():
    import builtins

    original = builtins.__import__
    with probe.import_guard(scoring=True):
        with pytest.raises(ImportError, match="FORBIDDEN"):
            __import__("tkb_core.preprocessing.normalize")
        with pytest.raises(ImportError, match="FORBIDDEN"):
            __import__("ortools.sat.python.cp_model")
    assert builtins.__import__ is original


def test_smoke_only_synthetic_duration_one_two_and_default_options():
    raw = probe.smoke_input()
    assert sorted(raw["teaching_requirements"][0]["block_durations"]) == [1, 2]
    assert {r["priority"] for r in raw["constraint_config"]["soft"]} == {1, 2, 3}
    assert len(raw["constraint_config"]["soft"]) == 4
    command = probe.solve_arguments(Path("tiny.json"), Path("result.json"))
    assert command == ["solve", "tiny.json", "--output", "result.json"]


def test_tiny_input_contract_valid_without_search():
    from tkb_core.contracts.input import ScheduleInput

    problem = ScheduleInput.model_validate(probe.smoke_input())
    assert problem.schema_version == "1.1"


def test_bundle_missing_file_and_extra_file_rejected(tmp_path):
    (tmp_path / "manifest.json").write_text('{"datasets": []}')
    (tmp_path / "extra").write_text("unexpected")
    with pytest.raises(ValueError, match="MEMBERSHIP"):
        payload.bundle_files(tmp_path, expected_ids=set())


def test_cli_spawn_error_has_persistent_failed_receipt(tmp_path):
    def fail(*args, **kwargs):
        raise OSError("python not found")

    with pytest.raises(OSError):
        probe.cli_case(tmp_path, "missing", "missing.exe", [], 0, "status", "OK", runner=fail)
    record = json.loads((tmp_path / "missing.receipt.json").read_text())
    assert record["status"] == "FAIL" and record["exit_code"] is None
    assert record["reason"] == "python not found"


def test_cli_receipt_keeps_actual_failure_and_no_retry(tmp_path):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return type(
            "Fake", (), {"stdout": b'{"status":"INPUT_INVALID"}', "stderr": b"why", "returncode": 2}
        )()

    with pytest.raises(ValueError, match="CLI_EXPECTATION"):
        probe.cli_case(
            tmp_path,
            "case",
            "python.exe",
            ["validate-input", "tiny.json"],
            0,
            "status",
            "INPUT_VALID",
            runner=fake_run,
        )
    assert len(calls) == 1
    receipt = json.loads((tmp_path / "case.receipt.json").read_text())
    assert receipt["exit_code"] == 2 and receipt["status"] == "FAIL"
    assert (tmp_path / "case.stderr.txt").read_text() == "why"
    with pytest.raises(FileExistsError):
        probe.cli_case(tmp_path, "case", "python.exe", [], 0, "status", "OK", runner=fake_run)
    assert len(calls) == 1


def test_versions_reject_missing_solver_and_unexpected_packages():
    locked = {"vnedu-tkb-core": "0.2.0", "pydantic": "2.14.1", "ortools": "9.15.6755"}
    installed = {"vnedu-tkb-core": "0.2.0", "pydantic": "2.14.1"}
    with pytest.raises(ValueError):
        probe.check_versions(installed, locked, "solver")
    probe.check_versions(installed, locked, "no-solver")
    with pytest.raises(ValueError):
        probe.check_versions(dict(installed, ortools="9.15.6755"), locked, "no-solver")
    with pytest.raises(ValueError):
        probe.check_versions(dict(installed, unexpected="1"), locked, "no-solver")


@pytest.mark.parametrize("failure", [None, "source", "extra", "editable"])
def test_installed_bytes_and_editable_identity_with_fake_environment(
    tmp_path, monkeypatch, failure
):
    monkeypatch.setattr(probe.platform, "platform", lambda: "FAKE_WINDOWS")
    package = tmp_path / "venv/Lib/site-packages/tkb_core"
    source = tmp_path / "payload/source/src/tkb_core"
    wheel = tmp_path / "payload/wheel/vnedu_tkb_core-0.2.0-py3-none-any.whl"
    package.mkdir(parents=True)
    source.mkdir(parents=True)
    wheel.parent.mkdir()
    names = ["__init__.py", *[f"fake_{i}.py" for i in range(26)]]
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in names:
            data = b"# fake source\n"
            archive.writestr("tkb_core/" + name, data)
            (source / name).write_bytes(data)
            (package / name).write_bytes(data)
    (source.parent.parent / "uv.lock").write_text(
        '[[package]]\nname="vnedu-tkb-core"\nversion="0.2.0"\n'
        '[[package]]\nname="pydantic"\nversion="2.14.1"\n'
    )
    monkeypatch.setitem(
        sys.modules, "tkb_core", SimpleNamespace(__file__=str(package / "__init__.py"))
    )
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "venv"))
    monkeypatch.setattr(
        probe.metadata,
        "distribution",
        lambda name: SimpleNamespace(
            read_text=lambda path: json.dumps({"dir_info": {"editable": failure == "editable"}})
        ),
    )
    monkeypatch.setattr(
        probe.metadata,
        "distributions",
        lambda: [
            SimpleNamespace(metadata={"Name": "vnedu-tkb-core"}, version="0.2.0"),
            SimpleNamespace(metadata={"Name": "pydantic"}, version="2.14.1"),
        ],
    )
    monkeypatch.setattr(probe.importlib.util, "find_spec", lambda name: None)
    if failure == "source":
        (source / "fake_0.py").write_text("changed")
    if failure == "extra":
        (package / "unexpected.py").write_text("extra")
    if failure:
        with pytest.raises(ValueError):
            probe.installed_environment(tmp_path / "payload", "no-solver")
    else:
        result = probe.installed_environment(tmp_path / "payload", "no-solver")
        assert result["source_files_compared"] == 27
        assert result["check"] == "INSTALLED_IDENTITY_ONLY"


def test_main_linux_rejected_before_files_or_core_import(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "linux")
    output = tmp_path / "never-created"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "probe",
            "smoke",
            "--payload",
            str(tmp_path),
            "--inventory",
            str(tmp_path / "missing.json"),
            "--output",
            str(output),
            "--approval-reference",
            "reference",
            "--machine-id",
            "fake-machine",
        ],
    )
    monkeypatch.setattr(probe, "installed_environment", Mock(side_effect=AssertionError("NO_CORE")))
    assert probe.main() == 2
    assert not output.exists()
    assert "WINDOWS_NATIVE_REQUIRED" in capsys.readouterr().out
    probe.installed_environment.assert_not_called()


def test_junction_rejected_without_following_it(tmp_path, monkeypatch):
    inventory_for(tmp_path)
    monkeypatch.setattr(Path, "is_junction", lambda p: p.name == "sample.txt")
    with pytest.raises(ValueError, match="JUNCTION"):
        payload.regular_files(tmp_path)


@pytest.mark.parametrize("mismatch", [False, True])
def test_smoke_fake_responses_compare_independent_score(tmp_path, monkeypatch, mismatch):
    score = {"status": "OK", "tiers": [2, 1, 3], "rules": [{"fake": i} for i in range(4)]}
    calls = []

    def fake_cli(root, name, python, args, code, field, expected):
        calls.append((name, args))
        if name == "solve":
            return {
                "schema_version": "1.2",
                "metadata": {"solver_executed": True},
                "input_fingerprint": "a" * 64,
                "quality": {
                    "score": dict(score, input_fingerprint="a" * 64),
                    "tier_runs": [{"priority": i} for i in (1, 2, 3)],
                },
            }
        if name == "score":
            return dict(
                score, input_fingerprint="a" * 64, tiers=[9, 9, 9] if mismatch else score["tiers"]
            )
        if name == "validate":
            return {"status": expected, "score": dict(score, input_fingerprint="a" * 64)}
        if name.startswith("stale-"):
            return {"status": expected, "diagnostics": [{"code": "STALE_RESULT"}]}
        return {"status": expected, "metadata": {"solver_executed": False}, "assignments": []}

    monkeypatch.setattr(probe, "cli_case", fake_cli)
    if mismatch:
        with pytest.raises(ValueError, match="SCORE_MISMATCH"):
            probe.smoke(tmp_path)
    else:
        assert probe.smoke(tmp_path)["status"] == "PASS"
        assert sum(name == "solve" for name, args in calls) == 1
        assert not any("--time-limit" in args for name, args in calls)


@pytest.mark.parametrize("location", ["inside", "parent", "alias"])
def test_output_cannot_overlap_payload(tmp_path, location):
    root = tmp_path / "payload"
    root.mkdir()
    if location == "inside":
        output = root / "check"
    elif location == "parent":
        output = tmp_path
    else:
        alias = tmp_path / "alias"
        alias.symlink_to(root, target_is_directory=True)
        output = alias / "check"
    with pytest.raises(ValueError, match="OUTPUT_PAYLOAD_OVERLAP"):
        probe.check_output_location(output, root)
    assert list(root.iterdir()) == []


def test_guard_reports_forbidden_import_even_if_caller_catches():
    with probe.import_guard(scoring=False) as denied:
        try:
            __import__("ortools.sat.python.cp_model")
        except ImportError:
            pass
    assert denied == ["ortools.sat.python.cp_model"]


def test_cli_logs_preserve_exact_child_bytes(tmp_path):
    stdout = b'{"status":"OK"}\r\n'
    stderr = b"raw\xff\r\n"

    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=0)

    assert (
        probe.cli_case(tmp_path, "raw", "python", [], 0, "status", "OK", runner=fake_run)["status"]
        == "OK"
    )
    assert (tmp_path / "raw.stdout.json").read_bytes() == stdout
    assert (tmp_path / "raw.stderr.txt").read_bytes() == stderr
