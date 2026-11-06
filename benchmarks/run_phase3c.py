"""Phase 3C repair benchmark controller (plan 2026-11-06), outside Scheduling Core.

Supervision, native accounting, headroom, owner lock and journaling are imported unchanged from
the frozen v1 controller; solve runs (step S) reuse the frozen v2 ``run_cli_once`` and verdict.
New here: repair/explain supervision with independent checks in the no-solver venv, the H/P/C/Q/X
verdicts of ``judge_phase3c`` and a **two-stage seal**: ``plan.json`` (steps S and X) is sealed by
``prepare``; repair inputs depend on the previous schedules solved in step S, so ``derive`` seals
``derived.json`` (step R) only after S, chained to the S terminal receipts. Every input is hashed
before its own run starts. Run as ``python -m benchmarks.run_phase3c`` with the preflight's solver
interpreter, like v2.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

from pydantic import Field, JsonValue, StrictBool, StrictStr, model_validator

from benchmarks import generate_phase2 as g2
from benchmarks import generate_phase3c as g3
from benchmarks import judge_phase3c as j3
from benchmarks import run_benchmarks as v1
from benchmarks import run_phase2 as r2
from benchmarks.run_benchmarks import OutputVerification, RunLimits, RunRecord
from tkb_core.domain.models import DomainModel
from tkb_core.solver.options import SolveOptions

PROTOCOL = "phase3c-linux-v1"
ROOT = Path(__file__).resolve().parents[1]
SHA = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
BUDGETS = r2.BUDGETS
# Smoke only (plan Task 5): small solver budget, generous watchdog; never a measurement.
SMOKE_BUDGET = (5.0, 60.0)
Part = Literal["S", "R1", "R2", "X"]
Stage = Literal["S", "R", "X"]
Label = j3.Label
HINTS = (True, False)
CHECK_TIMEOUT = 900.0


def budget(class_count: int, smoke: bool) -> tuple[float, float, int]:
    seconds, watchdog, rss = BUDGETS[class_count]
    return (SMOKE_BUDGET[0], SMOKE_BUDGET[1], rss) if smoke else (seconds, watchdog, rss)


def run_id(
    part: str,
    dataset_id: str,
    *,
    noise: str | None = None,
    hint: bool | None = None,
    granularity: str | None = None,
) -> str:
    if part == "S":
        return f"S-{dataset_id}"
    if part == "X":
        return f"X-{dataset_id}-{granularity}"
    return f"{part}-{dataset_id}-{noise}-hint{int(bool(hint))}"


class Case3C(DomainModel):
    run_id: StrictStr
    part: Part
    smoke: StrictBool
    dataset_id: StrictStr
    class_count: Literal[10, 20, 40]
    profile: Literal["BASE", "MIXED", "TIGHT", "UNSAT_CAPACITY"]
    variant: Literal["SOFT", "HARD"]
    noise: Literal["N1", "N2", "N3", "N4"] | None = None
    order: Literal["BEFORE_QUALITY", "AFTER_QUALITY"] | None = None
    hint: StrictBool | None = None
    granularity: Literal["MODEL", "FULL"] | None = None
    label: Label
    input_path: Path
    input_sha256: SHA
    dataset_manifest: Path | None = None
    previous_path: Path | None = None
    previous_sha256: SHA | None = None
    request_path: Path | None = None
    request_sha256: SHA | None = None
    time_limit_seconds: float
    limits: RunLimits

    @property
    def stage(self) -> Stage:
        return "R" if self.part in ("R1", "R2") else cast(Stage, self.part)

    @model_validator(mode="after")
    def fixed_policy(self) -> Self:
        seconds, watchdog, rss = budget(self.class_count, self.smoke)
        if (
            self.time_limit_seconds,
            self.limits.watchdog_seconds,
            self.limits.max_resident_bytes,
        ) != (seconds, watchdog, rss):
            raise ValueError("Fixed budget changed")
        repair = self.part in ("R1", "R2")
        if repair != all(
            v is not None
            for v in (
                self.noise,
                self.order,
                self.hint,
                self.previous_path,
                self.previous_sha256,
                self.request_path,
                self.request_sha256,
            )
        ):
            raise ValueError("Repair fields belong to repair rows only")
        if repair and self.order != ("BEFORE_QUALITY" if self.part == "R1" else "AFTER_QUALITY"):
            raise ValueError("Order differs from part")
        if (self.part == "X") != (self.granularity is not None):
            raise ValueError("Granularity belongs to explain rows only")
        unsat = self.profile == "UNSAT_CAPACITY"
        if (self.part == "X") != unsat or (self.label == "UNSAT") != unsat:
            raise ValueError("Only explain rows use UNSAT datasets")
        if (self.part == "S") != (self.label == "BASELINE") or (
            self.part == "S" and self.dataset_manifest is None
        ):
            raise ValueError("Step S solves baseline datasets with their manifest")
        expected = run_id(
            self.part,
            self.dataset_id,
            noise=self.noise,
            hint=self.hint,
            granularity=self.granularity,
        )
        if self.run_id != expected:
            raise ValueError("Run identity mismatch")
        return self


def expected_plan_ids(smoke: bool) -> list[str]:
    s = [run_id("S", i) for i in g3.base_dataset_ids(smoke=smoke)]
    x = [
        run_id("X", i, granularity=g)
        for i in g3.unsat_dataset_ids(smoke=smoke)
        for g in ("MODEL", "FULL")
    ]
    return s + x


def expected_r_ids(sizes: dict[str, int], *, smoke: bool) -> list[str]:
    """Plan C5: R1 all datasets x N1-N4 x hint; R2 10-class datasets with AFTER (smoke: N1)."""
    ids = sorted(sizes)
    if smoke:
        return [run_id("R1", i, noise="N1", hint=True) for i in ids]
    r1 = [run_id("R1", i, noise=n, hint=h) for i in ids for n in g3.NOISES for h in HINTS]
    r2_ = [
        run_id("R2", i, noise=n, hint=h)
        for i in ids
        if sizes[i] == 10
        for n in g3.NOISES
        for h in HINTS
    ]
    return r1 + r2_


class Plan3C(DomainModel):
    """Sealed by ``prepare``: steps S and X."""

    schema_version: Literal["3c-1.0"] = "3c-1.0"
    protocol: Literal["phase3c-linux-v1"] = "phase3c-linux-v1"
    campaign_id: v1.CampaignId
    machine_id: v1.CampaignId
    smoke: StrictBool
    bundle_dir: Path
    bundle_sha256: SHA
    source_ids: dict[str, SHA]
    reference: dict[str, JsonValue] = Field(default_factory=dict)
    cases: tuple[Case3C, ...]
    sealed: StrictBool = False
    preflight_dir: Path | None = None
    preflight_sha256: SHA | None = None
    runtime_identity: dict[str, JsonValue] = Field(default_factory=dict)
    environment: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def membership(self) -> Self:
        if [c.run_id for c in self.cases] != expected_plan_ids(self.smoke):
            raise ValueError("Plan membership differs from policy")
        if any(c.smoke != self.smoke or c.stage == "R" for c in self.cases):
            raise ValueError("Plan rows differ from policy")
        if self.sealed and (
            self.preflight_dir is None
            or self.preflight_sha256 is None
            or not self.runtime_identity
            or not self.environment
        ):
            raise ValueError("Sealed plan lacks preflight identity")
        return self


class Derived3C(DomainModel):
    """Sealed by ``derive`` after step S: repair inputs, requests and rows."""

    schema_version: Literal["3c-1.0"] = "3c-1.0"
    smoke: StrictBool
    plan_sha256: SHA
    previous: dict[str, dict[str, JsonValue]]
    excluded: dict[str, StrictStr]
    noise: dict[str, dict[str, JsonValue]]
    cases: tuple[Case3C, ...]

    @model_validator(mode="after")
    def membership(self) -> Self:
        sizes = {c.dataset_id: c.class_count for c in self.cases}
        if set(sizes) != set(self.previous) or set(self.previous) & set(self.excluded):
            raise ValueError("Every derived row needs a previous schedule")
        if [c.run_id for c in self.cases] != expected_r_ids(sizes, smoke=self.smoke):
            raise ValueError("Derived membership differs from policy")
        if any(c.smoke != self.smoke or c.stage != "R" for c in self.cases):
            raise ValueError("Derived rows differ from policy")
        return self


class State3C(DomainModel):
    schema_version: Literal["3c-1.0"] = "3c-1.0"
    stage: Stage
    status: Literal["COMPLETE", "BLOCKED", "STOPPED", "NEEDS_REVIEW", "CANCELLED"]
    rows: dict[str, Literal["NOT_STARTED", "NOT_STARTED_GATE_BLOCKED", "TERMINAL", "PARTIAL"]]
    completed: int = 0
    reason: StrictStr | None = None


def source_ids() -> dict[str, str]:
    names = {
        "controller_3c": "benchmarks/run_phase3c.py",
        "generator_3c": "benchmarks/generate_phase3c.py",
        "judge_3c": "benchmarks/judge_phase3c.py",
        "aggregator_3c": "benchmarks/aggregate_phase3c.py",
    }
    return r2.source_ids() | {k: v1._sha(ROOT / p) for k, p in names.items()}


def _dataset(root: Path, entries: dict[str, str], ident: str) -> g2.DatasetManifest:
    if ident not in entries:
        raise ValueError("Dataset missing from bundle: " + ident)
    base = v1._safe_file(root, ident)
    if v1._sha(base / "manifest.json") != entries[ident]:
        raise ValueError("Dataset manifest checksum drift")
    data = g2.DatasetManifest.model_validate(
        v1._json_object((base / "manifest.json").read_text(encoding="utf-8"))
    )
    if data.dataset_id != ident:
        raise ValueError("Dataset envelope drift")
    for name, digest in data.files.items():
        if v1._sha(v1._safe_file(base, name)) != digest:
            raise ValueError("Input/witness checksum drift")
    return data


def build_plan(bundle_dir: Path, campaign_id: str, machine_id: str, *, smoke: bool) -> Plan3C:
    """Deterministic S and X rows from a v2 bundle; never solves."""
    root = bundle_dir.absolute()
    bundle = g2.BundleManifest.model_validate(
        v1._json_object((root / "manifest.json").read_text(encoding="utf-8"))
    )
    entries = {e.dataset_id: e.manifest_sha256 for e in bundle.datasets}
    cases: list[Case3C] = []
    for ident in g3.base_dataset_ids(smoke=smoke):
        data = _dataset(root, entries, ident)
        seconds, watchdog, rss = budget(data.class_count, smoke)
        cases.append(
            Case3C(
                run_id=run_id("S", ident),
                part="S",
                smoke=smoke,
                dataset_id=ident,
                class_count=data.class_count,
                profile=data.profile,  # type: ignore[arg-type]
                variant=data.variant,
                label="BASELINE",
                input_path=root / ident / "input.json",
                input_sha256=data.files["input.json"],
                dataset_manifest=root / ident / "manifest.json",
                time_limit_seconds=seconds,
                limits=RunLimits(watchdog_seconds=watchdog, max_resident_bytes=rss),
            )
        )
    for ident in g3.unsat_dataset_ids(smoke=smoke):
        data = _dataset(root, entries, ident)
        seconds, watchdog, rss = budget(data.class_count, smoke)
        for granularity in ("MODEL", "FULL"):
            cases.append(
                Case3C(
                    run_id=run_id("X", ident, granularity=granularity),
                    part="X",
                    smoke=smoke,
                    dataset_id=ident,
                    class_count=data.class_count,
                    profile="UNSAT_CAPACITY",
                    variant=data.variant,
                    granularity=granularity,  # type: ignore[arg-type]
                    label="UNSAT",
                    input_path=root / ident / "input.json",
                    input_sha256=data.files["input.json"],
                    time_limit_seconds=seconds,
                    limits=RunLimits(watchdog_seconds=watchdog, max_resident_bytes=rss),
                )
            )
    return Plan3C(
        campaign_id=campaign_id,
        machine_id=machine_id,
        smoke=smoke,
        bundle_dir=root,
        bundle_sha256=v1._sha(root / "manifest.json"),
        source_ids=source_ids(),
        cases=tuple(cases),
    )


def reference_check(plan: Plan3C, reference_plan: Path) -> dict[str, JsonValue]:
    """Plan C2: selected inputs must be byte-identical to a v2 campaign plan."""
    reference = r2.CampaignPlan.model_validate(v1._json_object(reference_plan.read_text()))
    known = {c.dataset_id: c.input_sha256 for c in reference.primary}
    mismatched = sorted(
        c.dataset_id for c in plan.cases if known.get(c.dataset_id) != c.input_sha256
    )
    if mismatched:
        raise ValueError("REFERENCE_INPUT_DRIFT:" + ",".join(mismatched))
    return {
        "reference_plan_sha256": v1._sha(reference_plan),
        "campaign_id": reference.campaign_id,
        "datasets_checked": len({c.dataset_id for c in plan.cases}),
    }


def _write_new(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        out.write(json.dumps(data, sort_keys=True, indent=2) + "\n")


def derive_cases(
    plan: Plan3C,
    plan_sha256: str,
    previous_paths: dict[str, Path],
    excluded: dict[str, str],
    out: Path,
) -> Derived3C:
    """Write noisy inputs and requests under ``out`` and return the R rows (not yet sealed)."""
    out = out.absolute()
    requests: dict[tuple[str, bool], Path] = {}
    for order in ("BEFORE_QUALITY", "AFTER_QUALITY"):
        for hint in HINTS:
            path = out / "requests" / f"{order}-hint{int(hint)}.json"
            _write_new(path, g3.repair_request(order, hint=hint))
            requests[(order, hint)] = path
    baseline = {c.dataset_id: c for c in plan.cases if c.part == "S"}
    sizes = {i: baseline[i].class_count for i in previous_paths}
    wanted = expected_r_ids(sizes, smoke=plan.smoke)
    noise: dict[str, dict[str, JsonValue]] = {}
    previous: dict[str, dict[str, JsonValue]] = {}
    inputs: dict[tuple[str, str], Path] = {}
    for ident, path in sorted(previous_paths.items()):
        source = baseline[ident]
        data = v1._json_object(source.input_path.read_text(encoding="utf-8"))
        raw = v1._json_object(path.read_text(encoding="utf-8"))
        assignments = raw["assignments"]
        previous[ident] = {"path": str(path.absolute()), "sha256": v1._sha(path)}
        for name in g3.NOISES:
            if not any(r.startswith(f"R1-{ident}-{name}-") for r in wanted):
                continue
            noisy = g3.derive_noise(data, assignments, ident, name)
            target = out / ident / name / "input.json"
            _write_new(target, noisy.data)
            inputs[(ident, name)] = target
            noise[f"{ident}/{name}"] = {
                "description": noisy.description,
                "label": noisy.label,
                "candidate": noisy.candidate,
                "proofs": list(noisy.proofs),
                "input_sha256": v1._sha(target),
            }
    cases = []
    for ident_run in wanted:
        part, _, rest = ident_run.partition("-")
        ident = next(
            i for i in sorted(previous_paths, key=len, reverse=True) if rest.startswith(i + "-")
        )
        name, hint_text = rest[len(ident) + 1 :].split("-")
        hint = hint_text == "hint1"
        order = "BEFORE_QUALITY" if part == "R1" else "AFTER_QUALITY"
        source = baseline[ident]
        seconds, watchdog, rss = budget(source.class_count, plan.smoke)
        target = inputs[(ident, name)]
        cases.append(
            Case3C(
                run_id=ident_run,
                part=part,  # type: ignore[arg-type]
                smoke=plan.smoke,
                dataset_id=ident,
                class_count=source.class_count,
                profile=source.profile,
                variant=source.variant,
                noise=name,  # type: ignore[arg-type]
                order=order,  # type: ignore[arg-type]
                hint=hint,
                label=noise[f"{ident}/{name}"]["label"],  # type: ignore[arg-type]
                input_path=target,
                input_sha256=v1._sha(target),
                previous_path=previous_paths[ident].absolute(),
                previous_sha256=v1._sha(previous_paths[ident]),
                request_path=requests[(order, hint)],
                request_sha256=v1._sha(requests[(order, hint)]),
                time_limit_seconds=seconds,
                limits=RunLimits(watchdog_seconds=watchdog, max_resident_bytes=rss),
            )
        )
    return Derived3C(
        smoke=plan.smoke,
        plan_sha256=plan_sha256,
        previous=previous,
        excluded=excluded,
        noise=noise,
        cases=tuple(cases),
    )


# ----------------------------------------------------------------------------- preflight


def _venv_python(preflight: Path, label: str) -> Path:
    return preflight / f"venv-{label}" / "bin" / "python"


def check_3c_preflight(preflight: Path) -> None:
    """The v2 preflight's installed wheel must contain repair and Phase 3B diagnostics."""
    for label, module in (
        ("solver", "tkb_core.diagnostics.pipeline"),
        ("solver", "tkb_core.repair.pipeline"),
        ("no-solver", "tkb_core.validation.precheck_verifier"),
        ("no-solver", "tkb_core.validation.repair_evaluator"),
    ):
        done = subprocess.run(
            [str(_venv_python(preflight, label)), "-I", "-c", f"import {module}"],
            capture_output=True,
            check=False,
            timeout=120,
        )
        if done.returncode != 0:
            raise ValueError(f"PREFLIGHT_LACKS_3C:{label}:{module}")


def prepare(
    bundle: Path,
    preflight: Path,
    output: Path,
    campaign_id: str,
    machine_id: str,
    *,
    smoke: bool,
    reference_plan: Path | None,
) -> Plan3C:
    """Seal plan.json (steps S, X) only; never runs a schedule."""
    r2.check_version_table()
    r2._check_preflight(preflight)
    check_3c_preflight(preflight)
    plan = build_plan(bundle, campaign_id, machine_id, smoke=smoke)
    if reference_plan is not None:
        plan = Plan3C.model_validate(
            plan.model_dump() | {"reference": reference_check(plan, reference_plan)}
        )
    elif not smoke:
        raise ValueError("REFERENCE_PLAN_REQUIRED")
    runtime = v1._runtime_identity(
        python=Path(sys.executable), preflight_dir=preflight, lock_path=ROOT / "uv.lock"
    )
    machine = v1._machine_identity()
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with v1._campaign_owner(v1._OWNER_ROOT, output, campaign_id):
        headroom = v1.check_headroom(2 * 1024**3)
        if headroom.status != "PASS":
            raise ValueError(f"PREPARE_HEADROOM_BLOCKED:{headroom.reason}")
        output.mkdir()
        v1._write_json(output / "prepare-headroom.json", headroom, exclusive=True)
        r2._verify_bundle_isolated(plan.bundle_dir, output / "bundle-verification")

        def git(*args: str) -> str:
            return subprocess.check_output(("git", "-C", str(ROOT), *args), text=True).strip()

        environment: dict[str, JsonValue] = {
            "machine": machine,
            "git_head": git("rev-parse", "HEAD"),
            "git_status": git("status", "--porcelain"),
            "windows_status": "NOT_RUN",
            "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
        }
        sealed = Plan3C.model_validate(
            plan.model_dump()
            | dict(
                sealed=True,
                preflight_dir=preflight.absolute(),
                preflight_sha256=v1._sha(preflight / "preflight-manifest.json"),
                runtime_identity=runtime,
                environment=environment,
            )
        )
        v1._write_json(output / "plan.json", sealed, exclusive=True)
        v1._write_json(output / "environment.json", environment, exclusive=True)
        v1._write_json(
            output / "seal.json",
            {
                "schema_version": "3c-1.0",
                "plan_sha256": v1._sha(output / "plan.json"),
                "environment_sha256": v1._sha(output / "environment.json"),
            },
            exclusive=True,
        )
    return sealed


def check_identity(plan: Plan3C, plan_path: Path, preflight: Path) -> str:
    """Any drift of seal, sources, bundle, preflight, runtime or machine blocks a run."""
    root = plan_path.parent
    seal = v1._json_object((root / "seal.json").read_text())
    digest = v1._sha(plan_path)
    if (
        seal.get("schema_version") != "3c-1.0"
        or seal.get("plan_sha256") != digest
        or seal.get("environment_sha256") != v1._sha(root / "environment.json")
    ):
        raise ValueError("SEALED_IDENTITY_DRIFT")
    if not plan.sealed or plan.preflight_dir != preflight.absolute():
        raise ValueError("UNSEALED_PLAN")
    current = build_plan(plan.bundle_dir, plan.campaign_id, plan.machine_id, smoke=plan.smoke)
    if (current.bundle_sha256, current.source_ids, current.cases) != (
        plan.bundle_sha256,
        plan.source_ids,
        plan.cases,
    ):
        raise ValueError("SOURCE_OR_DATASET_DRIFT")
    if v1._sha(preflight / "preflight-manifest.json") != plan.preflight_sha256:
        raise ValueError("PREFLIGHT_DRIFT")
    runtime = v1._runtime_identity(
        python=Path(sys.executable), preflight_dir=preflight, lock_path=ROOT / "uv.lock"
    )
    if runtime != plan.runtime_identity:
        raise ValueError("RUNTIME_DRIFT")
    if v1._machine_identity() != plan.environment.get("machine"):
        raise ValueError("MACHINE_DRIFT")
    return digest


def check_derived(root: Path, plan_digest: str) -> tuple[Derived3C, str]:
    seal = v1._json_object((root / "seal-derived.json").read_text())
    derived_path = root / "derived.json"
    digest = v1._sha(derived_path)
    if seal != {"schema_version": "3c-1.0", "plan_sha256": plan_digest, "derived_sha256": digest}:
        raise ValueError("DERIVED_SEAL_DRIFT")
    derived = Derived3C.model_validate(v1._json_object(derived_path.read_text()))
    if derived.plan_sha256 != plan_digest:
        raise ValueError("DERIVED_PLAN_DRIFT")
    for case in derived.cases:
        for path, expected in (
            (case.input_path, case.input_sha256),
            (case.previous_path, case.previous_sha256),
            (case.request_path, case.request_sha256),
        ):
            if path is None or v1._sha(path) != expected:
                raise ValueError("DERIVED_INPUT_DRIFT")
    return derived, digest


# ----------------------------------------------------------------------------- runs


def _checked(argv: list[str], base: Path, name: str) -> tuple[int, dict[str, Any] | None]:
    """One independent check in the no-solver venv; stdout/stderr kept beside the run."""
    done = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=CHECK_TIMEOUT)
    (base / f"check-{name}.stdout").write_text(done.stdout)
    (base / f"check-{name}.stderr").write_text(done.stderr)
    try:
        return done.returncode, json.loads(done.stdout)
    except ValueError:
        return done.returncode, None


def verify_repair(
    case: Case3C, base: Path, execution: v1.ExecutionRecord, core: Path
) -> OutputVerification:
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.contracts.repair import RepairResult

    if execution.exit_code is None or not (base / "result.json").is_file():
        return OutputVerification(status="INVALID", diagnostics=("NO_RESULT",))
    try:
        envelope = RepairResult.model_validate(v1._json_object((base / "result.json").read_text()))
        problem = ScheduleInput.model_validate(v1._json_object(case.input_path.read_text()))
    except (OSError, ValueError) as exc:
        return OutputVerification(
            status="INVALID", diagnostics=("RESULT_CONTRACT", type(exc).__name__)
        )
    result = envelope.result
    expected_code = {"INFEASIBLE": 3, "UNKNOWN": 4, "MODEL_INVALID": 5}.get(
        str(result.status), 0 if result.valid_schedule else 2
    )
    if result.input_fingerprint != problem.fingerprint() or execution.exit_code != expected_code:
        return OutputVerification(status="INVALID", diagnostics=("RESULT_IDENTITY",))
    if not result.valid_schedule:
        return OutputVerification(status="VALID_CORE_ERROR", solver_status=str(result.status))
    (base / "schedule.json").write_text(result.model_dump_json())
    assert case.previous_path is not None and case.request_path is not None
    cli = [str(core), "-I", "-m", "tkb_core.cli"]
    checks = (
        (
            "validate",
            [*cli, "validate-schedule", str(case.input_path), str(base / "schedule.json")],
            "SCHEDULE_VALID",
        ),
        (
            "score",
            [*cli, "evaluate-score", str(case.input_path), str(base / "schedule.json")],
            "OK",
        ),
        (
            "repair",
            [
                *cli,
                "evaluate-repair",
                str(case.input_path),
                str(case.previous_path),
                str(base / "result.json"),
                "--request",
                str(case.request_path),
            ],
            "OK",
        ),
    )
    for name, argv, status in checks:
        code, parsed = _checked(argv, base, name)
        if code != 0 or parsed is None or parsed.get("status") != status:
            return OutputVerification(status="INVALID", diagnostics=("INDEPENDENT_CHECK", name))
    score = result.quality.score if result.quality else None
    return OutputVerification(
        status="VALID_SCHEDULE", solver_status=str(result.status), valid_schedule=True, score=score
    )


def verify_explain(
    case: Case3C, base: Path, execution: v1.ExecutionRecord, core: Path
) -> OutputVerification:
    from tkb_core.contracts.diagnostics import InfeasibilityReport
    from tkb_core.contracts.input import ScheduleInput

    if execution.exit_code != 0 or not (base / "report.json").is_file():
        return OutputVerification(status="INVALID", diagnostics=("NO_REPORT",))
    try:
        report = InfeasibilityReport.model_validate(
            v1._json_object((base / "report.json").read_text())
        )
        problem = ScheduleInput.model_validate(v1._json_object(case.input_path.read_text()))
    except (OSError, ValueError) as exc:
        return OutputVerification(
            status="INVALID", diagnostics=("REPORT_CONTRACT", type(exc).__name__)
        )
    if report.input_fingerprint != problem.fingerprint():
        return OutputVerification(status="INVALID", diagnostics=("REPORT_IDENTITY",))
    code, parsed = _checked(
        [
            str(core),
            "-I",
            "-m",
            "tkb_core.cli",
            "check-explanation",
            str(case.input_path),
            str(base / "report.json"),
        ],
        base,
        "explanation",
    )
    if code != 0 or parsed is None or parsed.get("status") != "OK":
        return OutputVerification(
            status="INVALID", diagnostics=("INDEPENDENT_CHECK", "explanation")
        )
    return OutputVerification(status="VALID_CORE_ERROR", solver_status=report.status)


def run_child(
    case: Case3C,
    argv: tuple[str, ...],
    base: Path,
    preflight: Path,
    verify: Callable[[v1.ExecutionRecord], OutputVerification],
) -> RunRecord:
    """Supervise one child like v2: pre-spawn hash checks, v1 supervision, verification."""
    base = base.absolute()
    if base.exists() or base.is_symlink():
        raise FileExistsError(base)
    hashed = [(case.input_path, case.input_sha256)]
    if case.previous_path is not None and case.previous_sha256 is not None:
        hashed.append((case.previous_path, case.previous_sha256))
    if case.request_path is not None and case.request_sha256 is not None:
        hashed.append((case.request_path, case.request_sha256))
    identity: dict[str, JsonValue] = {"expected_input_sha256": case.input_sha256}
    try:
        for path, digest in hashed:
            if v1._sha(path) != digest:
                raise ValueError("INPUT_HASH_MISMATCH")
        identity.update(
            v1._runtime_identity(
                python=Path(sys.executable), preflight_dir=preflight, lock_path=ROOT / "uv.lock"
            )
        )
        identity["tooling_3c_source_sha256"] = v1._sha(Path(__file__))
        identity["input_sha256"] = case.input_sha256
        identity["limits"] = case.limits.model_dump(mode="json")
    except (OSError, ValueError) as exc:
        base.mkdir(parents=True)
        execution = v1.ExecutionRecord(
            argv=argv,
            run_dir=base,
            stdout_path=base / "stdout.json",
            stderr_path=base / "stderr.txt",
            error_type=type(exc).__name__,
        )
        record = RunRecord(
            harness_status="ENVIRONMENT_BLOCKED",
            execution=execution,
            output=OutputVerification(diagnostics=(str(exc),)),
            identity=identity,
        )
    else:
        execution = v1.supervise(argv, base, case.limits)
        started = time.monotonic()
        try:
            output = verify(execution)
            for path, digest in hashed:
                if v1._sha(path) != digest:
                    raise ValueError("INPUT_CHANGED")
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            output = OutputVerification(
                status="INVALID", diagnostics=("VERIFY_FAILED", type(exc).__name__)
            )
        status = v1.classify_run(execution, output)
        record = RunRecord(
            harness_status=status,
            execution=execution,
            output=output,
            identity=identity,
            valid_schedule=status == "COMPLETE" and output.valid_schedule,
            parent_verification_seconds=time.monotonic() - started,
        )
    with (base / "run.json").open("x", encoding="utf-8") as handle:
        handle.write(record.model_dump_json(indent=2) + "\n")
    return record


def _explain_argv(case: Case3C, base: Path, granularity: str) -> tuple[str, ...]:
    return (
        sys.executable,
        "-I",
        "-m",
        "tkb_core.cli",
        "explain",
        str(case.input_path),
        "--time-limit",
        str(case.time_limit_seconds),
        "--seed",
        "42",
        "--granularity",
        granularity,
        "--output",
        str(base / "report.json"),
    )


def execute_case(case: Case3C, base: Path, preflight: Path) -> tuple[RunRecord, j3.Verdict3C]:
    core = _venv_python(preflight, "no-solver")
    if case.part == "S":
        record = r2.run_cli_once(
            python=Path(sys.executable),
            input_path=case.input_path,
            run_dir=base,
            preflight_dir=preflight,
            lock_path=ROOT / "uv.lock",
            input_sha256=case.input_sha256,
            limits=case.limits,
            options=SolveOptions(time_limit_seconds=case.time_limit_seconds),
        )
        assert case.dataset_manifest is not None
        return record, j3.judge_solve(record, base, case.dataset_manifest)
    if case.part == "X":
        assert case.granularity is not None
        record = run_child(
            case,
            _explain_argv(case, base, case.granularity),
            base,
            preflight,
            lambda e: verify_explain(case, base, e, core),
        )
        return record, j3.judge_explain(record, base, case.label, case.limits)
    assert case.previous_path is not None and case.request_path is not None
    argv = (
        sys.executable,
        "-I",
        "-m",
        "tkb_core.cli",
        "repair",
        str(case.input_path),
        str(case.previous_path),
        "--request",
        str(case.request_path),
        "--time-limit",
        str(case.time_limit_seconds),
        "--workers",
        "1",
        "--seed",
        "42",
        "--output",
        str(base / "result.json"),
    )
    record = run_child(case, argv, base, preflight, lambda e: verify_repair(case, base, e, core))
    verdict = j3.judge_repair(record, base, case.label, case.limits)
    if verdict.status == "INFEASIBLE" and record.harness_status == "COMPLETE":
        # Plan C8: explain every infeasible repair input (FULL), as a separate supervised child.
        follow = base / "explain"
        explain_case = case.model_copy(update={"granularity": None})
        explain_record = run_child(
            explain_case,
            _explain_argv(case, follow, "FULL"),
            follow,
            preflight,
            lambda e: verify_explain(explain_case, follow, e, core),
        )
        explain_verdict = j3.judge_explain(explain_record, follow, case.label, case.limits)
        v1._write_json(follow / "verdict.json", explain_verdict, exclusive=True)
        observed = dict(explain_verdict.explain or {})
        observed["harness_status"] = explain_record.harness_status
        observed["hard"] = explain_verdict.hard
        verdict = verdict.model_copy(update={"explain": observed})
    return record, verdict


# ----------------------------------------------------------------------------- journal


def _files(base: Path) -> dict[str, JsonValue]:
    return {
        str(p.relative_to(base)): v1._sha(p)
        for p in sorted(base.rglob("*"))
        if p.is_file() and p.name != "terminal.json"
    }


def read_terminals(
    root: Path, stage: Stage, digest: str, cases: tuple[Case3C, ...]
) -> dict[str, tuple[RunRecord, j3.Verdict3C]]:
    """Replay a stage journal and verify every terminal receipt."""
    path = root / f"journal-{stage}.jsonl"
    known = {c.run_id: c for c in cases}
    started: set[str] = set()
    terminal: dict[str, tuple[RunRecord, j3.Verdict3C]] = {}
    if not path.exists():
        return terminal
    for line in path.read_text().splitlines():
        event = v1._json_object(line)
        if event.get("schema_version") != "3c-1.0" or event.get("digest") != digest:
            raise ValueError("JOURNAL_INVALID")
        ident = event["run_id"]
        if ident not in known:
            raise ValueError("UNKNOWN_RUN")
        if event["event"] == "START":
            if ident in started:
                raise ValueError("DUPLICATE_START")
            started.add(ident)
        elif event["event"] == "TERMINAL":
            base = root / stage / ident
            if event["detail"] != {"terminal_sha256": v1._sha(base / "terminal.json")}:
                raise ValueError("TERMINAL_RECEIPT_DRIFT")
            receipt = v1._json_object((base / "terminal.json").read_text())
            if receipt.get("digest") != digest or receipt.get("files") != _files(base):
                raise ValueError("TERMINAL_EVIDENCE_DRIFT")
            record = RunRecord.model_validate(v1._json_object((base / "run.json").read_text()))
            verdict = j3.Verdict3C.model_validate(
                v1._json_object((base / "verdict.json").read_text())
            )
            terminal[ident] = (record, verdict)
    if started - set(terminal):
        raise ValueError("UNFINISHED_START")
    return terminal


def _state(root: Path, stage: Stage) -> State3C | None:
    path = root / f"state-{stage}.json"
    return State3C.model_validate(v1._json_object(path.read_text())) if path.exists() else None


def execute_stage(plan_path: Path, preflight: Path, stage: Stage) -> State3C:
    """Run one explicitly selected stage once; no retry, no resume."""
    plan_path = plan_path.absolute()
    root = plan_path.parent
    plan = Plan3C.model_validate(v1._json_object(plan_path.read_text()))
    state = State3C(stage=stage, status="BLOCKED", rows={})
    try:
        r2.check_version_table()
        digest = check_identity(plan, plan_path, preflight)
        if stage == "R":
            derived, digest = check_derived(root, digest)
            cases = derived.cases
        else:
            cases = tuple(c for c in plan.cases if c.stage == stage)
        required = {"S": None, "R": "S", "X": "R"}[stage]
        if required is not None:
            previous = _state(root, cast(Stage, required))
            if previous is None or previous.status != "COMPLETE":
                raise ValueError("PREREQUISITE_NOT_COMPLETE:" + required)
        if (root / f"journal-{stage}.jsonl").exists():
            raise ValueError("STAGE_ALREADY_STARTED")
    except (OSError, ValueError, KeyError) as exc:
        state.reason = "IDENTITY_OR_ORDER_BLOCKED:" + str(exc)
        return state
    state.rows = {c.run_id: "NOT_STARTED" for c in cases}
    with v1._campaign_owner(v1._OWNER_ROOT, root, plan.campaign_id) as lease:

        def finish(status: Any, reason: str | None = None) -> State3C:
            state.status = status
            state.reason = reason
            state.completed = sum(v == "TERMINAL" for v in state.rows.values())
            if status == "NEEDS_REVIEW":
                lease["state"] = "NEEDS_REVIEW"
            v1._write_json(root / f"state-{stage}.json", state)
            return state

        def event(kind: str, case: Case3C, detail: JsonValue = None) -> None:
            v1._journal(
                root / f"journal-{stage}.jsonl",
                {
                    "schema_version": "3c-1.0",
                    "digest": digest,
                    "stage": stage,
                    "event": kind,
                    "run_id": case.run_id,
                    "detail": detail,
                },
            )

        for case in cases:
            try:
                headroom = v1.check_headroom(case.limits.max_resident_bytes)
                disk = shutil.disk_usage(root)
                if headroom.status != "PASS" or disk.free < 256 * 1024**2:
                    state.rows[case.run_id] = "NOT_STARTED_GATE_BLOCKED"
                    event("GATE_BLOCKED", case, {"headroom": headroom.model_dump(mode="json")})
                    return finish("BLOCKED", "ADMISSION_GATE_BLOCKED")
            except (OSError, ValueError) as exc:
                event("GATE_BLOCKED", case, {"reason": str(exc)})
                return finish("BLOCKED", "ADMISSION_CHECK_FAILED")
            event(
                "START",
                case,
                {
                    "headroom": headroom.model_dump(mode="json"),
                    "disk_free_bytes": disk.free,
                    "operational_context": v1._operational_context(),
                },
            )
            state.rows[case.run_id] = "PARTIAL"
            base = root / stage / case.run_id
            record, verdict = execute_case(case, base, preflight)
            v1._write_json(base / "verdict.json", verdict, exclusive=True)
            v1._write_json(
                base / "terminal.json",
                {
                    "schema_version": "3c-1.0",
                    "digest": digest,
                    "run_id": case.run_id,
                    "files": _files(base),
                },
                exclusive=True,
            )
            event("TERMINAL", case, {"terminal_sha256": v1._sha(base / "terminal.json")})
            state.rows[case.run_id] = "TERMINAL"
            stop = j3.stop_status(record, verdict)
            if stop:
                return finish(stop, "RUN_STOP_POLICY:" + case.run_id)
            finish("BLOCKED", "IN_PROGRESS")
        return finish("COMPLETE")


def derive(plan_path: Path, preflight: Path) -> Derived3C:
    """After a COMPLETE step S: generate and seal the repair inputs (second seal)."""
    plan_path = plan_path.absolute()
    root = plan_path.parent
    plan = Plan3C.model_validate(v1._json_object(plan_path.read_text()))
    digest = check_identity(plan, plan_path, preflight)
    state = _state(root, "S")
    if state is None or state.status != "COMPLETE":
        raise ValueError("STEP_S_NOT_COMPLETE")
    if (root / "derived.json").exists() or (root / "derived").exists():
        raise FileExistsError(root / "derived.json")
    s_cases = tuple(c for c in plan.cases if c.stage == "S")
    terminal = read_terminals(root, "S", digest, s_cases)
    previous: dict[str, Path] = {}
    excluded: dict[str, str] = {}
    for case in s_cases:
        record, verdict = terminal[case.run_id]
        if record.valid_schedule and verdict.hard == "PASS":
            previous[case.dataset_id] = root / "S" / case.run_id / "result.json"
        else:
            excluded[case.dataset_id] = f"S_{record.harness_status}_{verdict.status}"
    derived = derive_cases(plan, digest, previous, excluded, root / "derived")
    v1._write_json(root / "derived.json", derived, exclusive=True)
    v1._write_json(
        root / "seal-derived.json",
        {
            "schema_version": "3c-1.0",
            "plan_sha256": digest,
            "derived_sha256": v1._sha(root / "derived.json"),
        },
        exclusive=True,
    )
    return derived


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparing = commands.add_parser("prepare")
    preparing.add_argument("--bundle", type=Path, required=True)
    preparing.add_argument("--preflight-dir", type=Path, required=True)
    preparing.add_argument("--output", type=Path, required=True)
    preparing.add_argument("--campaign-id", required=True)
    preparing.add_argument("--machine-id", required=True)
    preparing.add_argument("--reference-plan", type=Path)
    preparing.add_argument("--smoke", action="store_true")
    running = commands.add_parser("run")
    running.add_argument("--plan", type=Path, required=True)
    running.add_argument("--preflight-dir", type=Path, required=True)
    running.add_argument("--stage", choices=("S", "R", "X"), required=True)
    deriving = commands.add_parser("derive")
    deriving.add_argument("--plan", type=Path, required=True)
    deriving.add_argument("--preflight-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            plan = prepare(
                args.bundle,
                args.preflight_dir,
                args.output,
                args.campaign_id,
                args.machine_id,
                smoke=args.smoke,
                reference_plan=args.reference_plan,
            )
            print(json.dumps({"status": "PREPARED", "rows": len(plan.cases), "smoke": plan.smoke}))
            return 0
        if args.command == "derive":
            derived = derive(args.plan, args.preflight_dir)
            print(
                json.dumps(
                    {"status": "DERIVED", "rows": len(derived.cases), "excluded": derived.excluded}
                )
            )
            return 0
        state = execute_stage(args.plan, args.preflight_dir, args.stage)
        print(state.model_dump_json())
        return 0 if state.status == "COMPLETE" else 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
