"""Refresh installed-wheel Phase 2A evidence in a new directory on either native OS."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import tomllib
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def sha(path: Path) -> str:
    """Hash exact artifact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_run(argv: list[str], log: Path, *, timeout: float = 300) -> str:
    """Run a setup/check command once, with fresh logs and an explicit deadline."""
    timed_out = False
    with log.with_suffix(".stdout").open("xb") as out, log.with_suffix(".stderr").open("xb") as err:
        if sys.platform == "win32":
            from benchmarks.windows_runtime import setup_process

            with setup_process(argv, out, err) as child:
                try:
                    code = child.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
            code = child.returncode
        else:
            previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
            try:
                pid = os.posix_spawn(
                    sys.executable,
                    (
                        sys.executable,
                        "-I",
                        "-c",
                        "import os,sys;os.chdir(sys.argv[1]);os.execvp(sys.argv[2],sys.argv[2:])",
                        str(ROOT),
                        *argv,
                    ),
                    os.environ,
                    setsid=True,
                    setsigmask=previous_mask,
                    file_actions=[
                        (os.POSIX_SPAWN_OPEN, 0, os.devnull, os.O_RDONLY, 0),
                        (os.POSIX_SPAWN_OPEN, 1, str(log.with_suffix(".stdout")), os.O_WRONLY, 0),
                        (os.POSIX_SPAWN_OPEN, 2, str(log.with_suffix(".stderr")), os.O_WRONLY, 0),
                    ],
                )
                try:
                    started = time.monotonic()
                    signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
                    # Keep the group leader unreaped until its owned group has been stopped.
                    while os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
                        if time.monotonic() - started >= timeout:
                            timed_out = True
                            break
                        time.sleep(0.02)
                finally:
                    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
                    os.killpg(pid, signal.SIGKILL)
                    for _ in range(250):
                        reaped, wait_status = os.waitpid(pid, os.WNOHANG)
                        if reaped:
                            code = os.waitstatus_to_exitcode(wait_status)
                            break
                        time.sleep(0.02)
                    else:
                        raise TimeoutError("SETUP_REAP_UNCONFIRMED")
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
    log.with_suffix(".command.json").write_text(
        json.dumps(
            {
                "argv": argv,
                "exit_code": code,
                "timed_out": timed_out,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if timed_out:
        raise TimeoutError(str(log))
    if code != 0:
        raise RuntimeError(f"CHECK_FAILED:{log}:{code}")
    return log.with_suffix(".stdout").read_text(encoding="utf-8")


def probe(preflight: Path, label: str) -> dict[str, Any]:
    """Check all installed bytes/versions against the shared wheel and source snapshot."""
    import tkb_core

    if not sys.flags.isolated or sys.version_info[:2] != (3, 12):
        raise ValueError("ISOLATED_PYTHON_3_12_REQUIRED")
    package = Path(tkb_core.__file__).resolve().parent
    if (
        not package.is_relative_to(Path(sys.prefix).resolve())
        or "site-packages" not in package.parts
    ):
        raise ValueError("INSTALLED_CORE_REQUIRED")
    direct = json.loads(
        metadata.distribution("vnedu-tkb-core").read_text("direct_url.json") or "{}"
    )
    if direct.get("dir_info", {}).get("editable"):
        raise ValueError("EDITABLE_CORE")
    locked = {
        p["name"]: p["version"] for p in tomllib.loads((ROOT / "uv.lock").read_text())["package"]
    }
    actual = {
        d.metadata["Name"].lower().replace("_", "-"): d.version for d in metadata.distributions()
    }
    if any(locked.get(name) != value for name, value in actual.items()):
        raise ValueError("LOCK_VERSION_DRIFT")
    if (
        actual.get("pydantic") != locked["pydantic"]
        or actual.get("vnedu-tkb-core") != locked["vnedu-tkb-core"]
    ):
        raise ValueError("REQUIRED_DEPENDENCY_MISSING")
    if label == "solver" and actual.get("ortools") != locked["ortools"]:
        raise ValueError("SOLVER_MISSING")
    if label == "no-solver" and importlib.util.find_spec("ortools") is not None:
        raise ValueError("SOLVER_IN_SCORING_ENVIRONMENT")
    wheels = list((preflight / "distribution").glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError("ONE_SHARED_WHEEL_REQUIRED")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = {n for n in archive.namelist() if n.startswith("tkb_core/") and n.endswith(".py")}
        source = {
            p.relative_to(ROOT / "src").as_posix() for p in (ROOT / "src/tkb_core").rglob("*.py")
        }
        installed = {p.relative_to(package.parent).as_posix() for p in package.rglob("*.py")}
        if not names or names != source or names != installed:
            raise ValueError("CORE_MEMBERSHIP_DRIFT")
        for name in names:
            if (
                not archive.read(name)
                == (ROOT / "src" / name).read_bytes()
                == (package.parent / name).read_bytes()
            ):
                raise ValueError("CORE_BYTES_DRIFT:" + name)

    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()

    return {
        "status": "PASS",
        "environment": label,
        "installed_versions": actual,
        "source_files_compared": len(names),
        "tkb_core_file": str(package / "__init__.py"),
        "python": sys.executable,
        "python_version": platform.python_version(),
        "platform": sys.platform,
        "machine": platform.machine(),
        "git_commit": git("rev-parse", "HEAD"),
        "core_tree": git("rev-parse", "HEAD:src/tkb_core"),
        "wheel_sha256": sha(wheels[0]),
        "uv_lock_sha256": sha(ROOT / "uv.lock"),
    }


def setup(
    output: Path,
    bundle: Path,
    wheel: Path | None,
    wheel_sha256: str | None,
) -> dict[str, Any]:
    """Create fresh isolated environments, verify the bundle, and seal actual preflight."""
    if sys.platform not in ("linux", "win32") or sys.version_info[:2] != (3, 12):
        raise ValueError("NATIVE_LINUX_OR_WINDOWS_PYTHON_3_12_REQUIRED")
    output, bundle = output.absolute(), bundle.absolute()
    if output.resolve().is_relative_to(bundle.resolve()) or bundle.resolve().is_relative_to(
        output.resolve()
    ):
        raise ValueError("PREFLIGHT_BUNDLE_OVERLAP")
    output.mkdir(parents=True, exist_ok=False)
    (output / "distribution").mkdir()
    (output / "logs").mkdir()
    (output / "smoke").mkdir()

    def run(name: str, argv: list[str], timeout: float = 300) -> str:
        print("CHECK " + name, flush=True)
        return checked_run(argv, output / "logs" / name, timeout=timeout)

    for name, argv in (
        ("core-tests", ["uv", "run", "--extra", "solver", "pytest"]),
        (
            "native-tests",
            [
                "uv",
                "run",
                "--extra",
                "solver",
                "pytest",
                "benchmarks/tests/test_windows_runtime.py",
                "benchmarks/tests/test_phase2a_preflight.py",
            ],
        ),
        ("lint", ["uv", "run", "ruff", "check", "."]),
        ("format", ["uv", "run", "ruff", "format", "--check", "src", "tests", "benchmarks"]),
        ("types", ["uv", "run", "mypy"]),
    ):
        run(name, argv)
    if wheel is None:
        run("wheel", ["uv", "build", "--wheel", "--out-dir", str(output / "distribution")])
        wheel = next((output / "distribution").glob("*.whl"))
    else:
        if not wheel_sha256 or sha(wheel) != wheel_sha256:
            raise ValueError("SHARED_WHEEL_HASH_REQUIRED_OR_MISMATCH")
        target = output / "distribution" / wheel.name
        shutil.copyfile(wheel, target)
        wheel = target
    pythons = {}
    for label in ("solver", "no-solver"):
        extra = ["--extra", "solver"] if label == "solver" else []
        requirements = run(
            "export-" + label,
            [
                "uv",
                "export",
                "--locked",
                "--no-dev",
                "--no-emit-project",
                *extra,
            ],
        )
        requirement_path = output / ("requirements-" + label + ".txt")
        requirement_path.write_text(requirements, encoding="utf-8")
        venv = output / ("venv-" + label)
        run("venv-" + label, ["uv", "venv", "--python", sys.executable, str(venv)])
        python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        pythons[label] = str(python)
        run(
            "dependencies-" + label,
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--require-hashes",
                "--only-binary",
                ":all:",
                "-r",
                str(requirement_path),
            ],
        )
        run(
            "install-" + label,
            ["uv", "pip", "install", "--python", str(python), "--no-deps", str(wheel)],
        )
        run("pip-check-" + label, ["uv", "pip", "check", "--python", str(python)])
        env = json.loads(
            run(
                "identity-" + label,
                [
                    str(python),
                    "-I",
                    str(Path(__file__).resolve()),
                    "probe",
                    "--output",
                    str(output),
                    "--label",
                    label,
                ],
            )
        )
        (output / ("environment-" + label + ".json")).write_text(
            json.dumps(env, indent=2) + "\n", encoding="utf-8"
        )
    tiny = output / "smoke/input.json"
    shutil.copyfile(ROOT / "tests/fixtures/quality/priority_tradeoff.json", tiny)
    run(
        "tiny-solve",
        [
            pythons["solver"],
            "-I",
            "-m",
            "tkb_core.cli",
            "solve",
            str(tiny),
            "--time-limit",
            "5",
            "--output",
            str(output / "smoke/result.json"),
        ],
        timeout=15,
    )
    for label in ("solver", "no-solver"):
        for command in ("validate-schedule", "evaluate-score"):
            run(
                label + "-" + command,
                [
                    pythons[label],
                    "-I",
                    "-m",
                    "tkb_core.cli",
                    command,
                    str(tiny),
                    str(output / "smoke/result.json"),
                ],
            )
    run(
        "guarded-scorer",
        [
            pythons["no-solver"],
            "-I",
            str(Path(__file__).resolve()),
            "guard-score",
            "--output",
            str(output),
        ],
    )
    run(
        "bundle-verification",
        [
            pythons["solver"],
            "-I",
            str(Path(__file__).resolve()),
            "verify-bundle",
            "--output",
            str(output),
            "--bundle",
            str(bundle),
        ],
        timeout=150,
    )
    env = json.loads((output / "environment-solver.json").read_text())
    files = {
        path.relative_to(output).as_posix(): sha(path)
        for directory in (output / "logs", output / "smoke", output / "distribution")
        for path in directory.rglob("*")
        if path.is_file()
    }
    for label in ("solver", "no-solver"):
        name = "environment-" + label + ".json"
        files[name] = sha(output / name)
    manifest = {
        "preflight_schema_version": "1.0",
        "protocol": "phase2a-operational-v1",
        "linux_status": "PASS" if sys.platform == "linux" else "NOT_RUN",
        "windows_status": "PASS" if sys.platform == "win32" else "NOT_RUN",
        "wheel_sha256": sha(wheel),
        "uv_lock_sha256": sha(ROOT / "uv.lock"),
        "git_commit": env["git_commit"],
        "core_tree": env["core_tree"],
        "bundle_manifest_sha256": sha(bundle / "manifest.json"),
        "files": files,
    }
    (output / "preflight-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    """Separate setup from isolated installed-package probes; failures never seal PASS."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("setup", "probe", "guard-score", "verify-bundle"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--wheel-sha256")
    parser.add_argument("--label", choices=("solver", "no-solver"))
    args = parser.parse_args()
    try:
        if args.mode == "setup":
            if args.bundle is None:
                parser.error("setup requires --bundle")
            result = setup(args.output, args.bundle, args.wheel, args.wheel_sha256)
        elif args.mode == "probe":
            if args.label is None:
                parser.error("probe requires --label")
            result = probe(args.output, args.label)
        else:
            # Only benchmark modules are added; Core still resolves from isolated site-packages.
            sys.path.insert(0, str(ROOT))
            if args.mode == "guard-score":
                from benchmarks.windows_preflight import import_guard

                with import_guard(scoring=True):
                    from tkb_core.cli import main as core_main

                    return core_main(
                        [
                            "evaluate-score",
                            str(args.output / "smoke/input.json"),
                            str(args.output / "smoke/result.json"),
                        ]
                    )
            if args.bundle is None:
                parser.error("verify-bundle requires --bundle")
            from benchmarks.generate_synthetic import verify_bundle
            from benchmarks.windows_preflight import import_guard

            with import_guard(scoring=False):
                verified = verify_bundle(args.bundle)
            result = {
                "status": "PASS",
                "dataset_count": len(verified.datasets),
                "search_executed": False,
            }
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
