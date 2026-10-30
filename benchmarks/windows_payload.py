"""Read-only frozen payload inventory and receiver hash checks; never import Core."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

CORE_COMMIT = "4cfa643148b967ad7baf674fe6439699afbe51e2"
CORE_TREE = "1efd459b2514f448dcf4ac297989de09eb76a3a1"
WHEEL_SHA = "1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9"
LOCK_SHA = "e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084"
BUNDLE_SHA = "a278a02dd9e10fedc7c5fcf44ef81d038d7712eba929d881a0f6193fc97cc93d"
PREFLIGHT = ".worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1"
BUNDLE = ".worktrees/phase2a-generator/benchmarks/artifacts/phase2a/task1-v1"


def sha(data: bytes) -> str:
    """SHA256 of exact bytes, with no newline normalization."""
    return hashlib.sha256(data).hexdigest()


def safe_relative(name: str) -> str:
    """Reject traversal and paths ambiguous or special on Windows."""
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("UNSAFE_PATH")
    path = PurePosixPath(name)
    if path.is_absolute() or str(path) != name:
        raise ValueError("UNSAFE_PATH")
    for part in path.parts:
        if part in (".", "..") or part.endswith((".", " ")):
            raise ValueError("UNSAFE_PATH")
        if re.search(r'[<>:"|?*\x00-\x1f]', part):
            raise ValueError("UNSAFE_PATH")
        if part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL"} | {
            f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
        }:
            raise ValueError("UNSAFE_PATH")
    return name


def regular_files(root: Path) -> dict[str, Path]:
    """Enumerate exact regular-file membership, rejecting symbolic links."""
    if root.is_symlink() or root.is_junction() or not root.is_dir():
        raise ValueError("INVALID_ROOT")
    result = {}
    for path in root.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ValueError("SYMLINK_OR_JUNCTION")
        if path.is_file():
            name = safe_relative(path.relative_to(root).as_posix())
            result[name] = path
        elif not path.is_dir():
            raise ValueError("NOT_REGULAR_FILE")
    return result


def bundle_files(root: Path, *, expected_ids: set[str] | None = None) -> dict[str, Path]:
    """Check root/child manifests and full raw membership without Core imports."""
    files = regular_files(root)
    manifest = json.loads(files["manifest.json"].read_bytes())
    if expected_ids is None:
        expected_ids = {
            f"c{size:02}-{profile}-s{seed}"
            for size in (10, 20, 40)
            for profile in ("base", "mixed", "tight", "unsat_capacity")
            for seed in (101, 102, 103)
        }
    entries = manifest["datasets"]
    if len(entries) != len(expected_ids) or {e["dataset_id"] for e in entries} != expected_ids:
        raise ValueError("BUNDLE_MEMBERSHIP")
    expected = {"manifest.json"}
    for entry in entries:
        dataset = safe_relative(entry["dataset_id"])
        name = f"{dataset}/manifest.json"
        data = files[name].read_bytes()
        if sha(data) != entry["manifest_sha256"]:
            raise ValueError("BUNDLE_MANIFEST_HASH")
        item = json.loads(data)
        if item["dataset_id"] != dataset:
            raise ValueError("DATASET_ID")
        expected.add(name)
        for child, digest in item["files"].items():
            child_name = f"{dataset}/{safe_relative(child)}"
            expected.add(child_name)
            if sha(files[child_name].read_bytes()) != digest:
                raise ValueError("BUNDLE_FILE_HASH")
    if set(files) != expected:
        raise ValueError("BUNDLE_FILE_MEMBERSHIP")
    return files


def build_inventory(repo: Path) -> dict:
    """Describe a future payload using Git objects and existing frozen files only."""
    rows = []

    def add(origin, destination, data, role):
        rows.append(
            {
                "origin": origin,
                "destination": safe_relative(destination),
                "role": role,
                "size_bytes": len(data),
                "sender_sha256": sha(data),
                "receiver_sha256": None,
                "receiver_reason": "NOT_TRANSFERRED",
            }
        )

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=repo)

    if git("rev-parse", f"{CORE_COMMIT}:src/tkb_core").decode().strip() != CORE_TREE:
        raise ValueError("CORE_TREE")
    selected = {
        "README.md",
        "AGENTS.md",
        "pyproject.toml",
        "uv.lock",
        ".python-version",
        ".gitignore",
        "benchmarks/generate_synthetic.py",
        *[
            f"docs/{n}.md"
            for n in (
                "assumptions",
                "domain-model",
                "solver-design",
                "constraint-catalog",
                "phase-1-report",
                "phase-2a-report",
            )
        ],
    }
    for path in git("ls-tree", "-r", "--name-only", CORE_COMMIT).decode().splitlines():
        if path.startswith(("src/tkb_core/", "tests/")) or path in selected:
            add(
                {"kind": "git_blob", "commit": CORE_COMMIT, "path": path},
                f"source/{path}",
                git("show", f"{CORE_COMMIT}:{path}"),
                "FROZEN_SOURCE",
            )

    def local(path, dest, role):
        full = repo / path
        if full.is_symlink() or not full.is_file():
            raise ValueError("SOURCE_NOT_REGULAR")
        add({"kind": "local_file", "path": path}, dest, full.read_bytes(), role)

    wheel = f"{PREFLIGHT}/distribution/vnedu_tkb_core-0.2.0-py3-none-any.whl"
    if sha((repo / wheel).read_bytes()) != WHEEL_SHA:
        raise ValueError("WHEEL_HASH")
    if sha(git("show", f"{CORE_COMMIT}:uv.lock")) != LOCK_SHA:
        raise ValueError("LOCK_HASH")
    local(wheel, "wheel/vnedu_tkb_core-0.2.0-py3-none-any.whl", "CORE_WHEEL")
    if sha((repo / BUNDLE / "manifest.json").read_bytes()) != BUNDLE_SHA:
        raise ValueError("BUNDLE_ROOT_HASH")
    for relative in sorted(bundle_files(repo / BUNDLE)):
        local(
            f"{BUNDLE}/{relative}",
            f"source/benchmarks/artifacts/phase2a/task1-v1/{relative}",
            "FROZEN_BUNDLE",
        )
    # Historical probes/results are references, never Windows execution entrypoints.
    refs = [
        "preflight-manifest.json",
        "installation-probe.py",
        "registry-probe.py",
        "verify-installed-bundle.py",
        "no-solver-guard.py",
        "smoke-checks.py",
        "requirements-solver.txt",
        "requirements-no-solver.txt",
    ]
    for name in refs:
        local(f"{PREFLIGHT}/{name}", f"linux-reference/{name}", "LINUX_REFERENCE")
    for path in sorted(regular_files(repo / PREFLIGHT / "smoke")):
        local(f"{PREFLIGHT}/smoke/{path}", f"linux-reference/smoke/{path}", "LINUX_REFERENCE")
    docs = [
        "phase-2a-operational-report.md",
        "phase-2a-windows-preflight-handoff-checklist.md",
        "phase-2a-windows-preflight-handoff-templates.md",
        "phase-2a-windows-task2-runbook.md",
        "phase-2a-windows-task2-preparation-report.md",
    ]
    for name in docs:
        local(f"docs/{name}", f"docs/{name}", "HANDOFF_DOC")
    for name in ("windows_payload.py", "windows_preflight.py"):
        local(f"benchmarks/{name}", f"tools/{name}", "WINDOWS_TOOLING")
    local(
        "benchmarks/tests/test_windows_handoff.py",
        "preparation-reference/test_windows_handoff.py",
        "LINUX_FAKE_TEST_SOURCE_REFERENCE_ONLY",
    )
    destinations = [r["destination"].casefold() for r in rows]
    if len(destinations) != len(set(destinations)):
        raise ValueError("DUPLICATE_DESTINATION")
    return {
        "schema_version": "1.0",
        "protocol": "phase2a-operational-v1",
        "status": "PREPARED_NOT_AUTHORIZED",
        "windows_status": "BLOCKED",
        "reason": "INVENTORY_ONLY; NO_PAYLOAD_CREATED_OR_TRANSFERRED; NO_WINDOWS_EXECUTION",
        "core_commit": CORE_COMMIT,
        "core_tree": CORE_TREE,
        "expected_wheel_sha256": WHEEL_SHA,
        "expected_lock_sha256": LOCK_SHA,
        "expected_bundle_manifest_sha256": BUNDLE_SHA,
        "dataset_count": 36,
        "file_count": len(rows),
        "total_bytes": sum(r["size_bytes"] for r in rows),
        "files": sorted(rows, key=lambda r: r["destination"]),
    }


def verify_payload(root: Path, inventory: dict) -> dict:
    """Receiver byte consistency only; does not grant approval or Windows PASS."""
    actual = regular_files(root)
    expected = {}
    folded = set()
    for row in inventory["files"]:
        name = safe_relative(row["destination"])
        if name.casefold() in folded:
            raise ValueError("DUPLICATE_DESTINATION")
        folded.add(name.casefold())
        expected[name] = row
    if not expected or set(expected) != set(actual):
        raise ValueError("PAYLOAD_MEMBERSHIP")
    verified = []
    for name, row in sorted(expected.items()):
        data = actual[name].read_bytes()
        digest = sha(data)
        if type(row["size_bytes"]) is not int or len(data) != row["size_bytes"]:
            raise ValueError(f"PAYLOAD_SIZE: {name}")
        if digest != row["sender_sha256"]:
            raise ValueError(f"PAYLOAD_HASH: {name}")
        verified.append({"destination": name, "receiver_sha256": digest, "size_bytes": len(data)})
    return {
        "status": "PAYLOAD_HASHES_MATCH",
        "windows_preflight_status": "NOT_ASSESSED",
        "execution_authorized": False,
        "files": verified,
    }


def main() -> int:
    """Emit inventory or receiver verification; never copy or execute a payload."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    build = sub.add_parser("inventory")
    build.add_argument("--repo", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = (
            build_inventory(args.repo)
            if args.mode == "inventory"
            else verify_payload(args.root, json.loads(args.inventory.read_bytes()))
        )
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
