"""Campaign controls on synthetic metadata/typed execution boundaries; no campaign runs."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from benchmarks import run_benchmarks as runner


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def put(path: Path, data: Any) -> bytes:
    raw = (json.dumps(data, sort_keys=True, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return raw


@pytest.fixture
def unit_bundle(tmp_path: Path) -> Path:
    """Metadata-only fixture; deliberately not Core input, never used by a real solve."""
    root = tmp_path / "bundle"
    root.mkdir()
    entries = []
    for size in (10, 20, 40):
        for profile in ("BASE", "MIXED", "TIGHT", "UNSAT_CAPACITY"):
            for seed in (101, 102, 103):
                ident = f"c{size}-{profile.lower()}-s{seed}"
                base = root / ident
                base.mkdir()
                raw = put(base / "input.json", {"unit_metadata_only": ident})
                fp = sha(raw)
                artifacts = {"input.json": fp}
                names = (
                    ("provenance-input.json", "provenance-witness.json")
                    if profile == "UNSAT_CAPACITY"
                    else ("witness.json",)
                )
                for name in names:
                    artifacts[name] = sha(put(base / name, {"unit": ident, "artifact": name}))
                score = None
                if profile != "UNSAT_CAPACITY":
                    score = {
                        "schema_version": "1.0",
                        "status": "OK",
                        "input_fingerprint": fp,
                        "diagnostics": [],
                        "rules": [],
                        "tiers": [0, 0, 0],
                    }
                    if profile == "TIGHT":
                        score["rules"] = [
                            dict(
                                rule_id="unit-day",
                                code="TEACHER_MAX_PERIODS_PER_DAY",
                                priority=2,
                                weight=1,
                                unit="teaching_periods",
                                raw_penalty=8 * size,
                                weighted_penalty=8 * size,
                            )
                        ]
                        score["tiers"] = [0, 8 * size, 0]
                meta = dict(
                    benchmark_schema_version="1.0",
                    dataset_id=ident,
                    class_count=size,
                    profile=profile,
                    seed=seed,
                    input_fingerprint=fp,
                    ground_truth="INFEASIBLE" if profile == "UNSAT_CAPACITY" else "FEASIBLE",
                    known_optimum=[0, 0, 0] if profile in ("BASE", "MIXED") else None,
                    baseline_score=score,
                    p2_lower_bound=6 * size if profile == "TIGHT" else (0 if score else None),
                    capacity_proof=None,
                    dimensions={"classes": size},
                    sources={
                        "generator_source_sha256": "1" * 64,
                        "core_source_sha256": "2" * 64,
                        "uv_lock_sha256": "3" * 64,
                    },
                    files=artifacts,
                )
                content = put(base / "manifest.json", meta)
                entries.append({"dataset_id": ident, "manifest_sha256": sha(content)})
    put(
        root / "manifest.json",
        {
            "benchmark_schema_version": "1.0",
            "protocol": "phase2a-operational-v1",
            "revision": {"repository_head": None, "generator_matches_head": False},
            "datasets": entries,
        },
    )
    return root


def test_matrix_counts_budgets_and_ids(unit_bundle: Path) -> None:
    p = runner.build_campaign_plan(unit_bundle, "unit-campaign", "unit-machine")
    assert len(p.primary) == 108 and len({c.run_id for c in p.primary}) == 108
    assert sum(c.ground_truth == "FEASIBLE" for c in p.primary) == 81
    assert sum(c.ground_truth == "INFEASIBLE" for c in p.primary) == 27
    for size, time, watch, cap in ((10, 60, 150, 1), (20, 120, 210, 2), (40, 180, 270, 4)):
        cases = [c for c in p.primary if c.class_count == size]
        assert len(cases) == 36
        assert all(
            c.options.time_limit_seconds == time
            and c.limits.watchdog_seconds == watch
            and c.limits.max_resident_bytes == cap * 1024**3
            for c in cases
        )
        assert all(c.options.num_workers == 1 and c.options.seed == 42 for c in cases)
    for ident in {c.dataset_id for c in p.primary}:
        assert sorted(c.repeat for c in p.primary if c.dataset_id == ident) == [1, 2, 3]


def test_seeded_order_is_frozen(unit_bundle: Path) -> None:
    a = runner.build_campaign_plan(unit_bundle, "unit-campaign", "unit-machine")
    b = runner.build_campaign_plan(unit_bundle, "unit-campaign", "unit-machine")
    assert a.model_dump_json() == b.model_dump_json()
    assert a.order_seed == 2026
    ids = [c.dataset_id for c in a.primary]
    assert ids[:36] != sorted(ids[:36]) and ids[:36] != ids[36:72]


def test_pilot_is_excluded_from_primary(unit_bundle: Path) -> None:
    p = runner.build_campaign_plan(unit_bundle, "unit-campaign", "unit-machine")
    assert p.pilot.dataset_id == "c10-base-s101" and p.pilot.repeat == 0
    assert p.pilot.run_id not in {c.run_id for c in p.primary}
    assert p.warmup is None  # bound from frozen Task2 only at sealing, never a primary row


@pytest.mark.parametrize("corruption", ["member", "input", "unknown", "budget"])
def test_matrix_rejects_drift(unit_bundle: Path, corruption: str) -> None:
    if corruption == "member":
        path = unit_bundle / "manifest.json"
        d = json.loads(path.read_text())
        d["datasets"].pop()
        put(path, d)
    elif corruption == "input":
        (unit_bundle / "c10-base-s101/input.json").write_text("changed")
    elif corruption == "unknown":
        path = unit_bundle / "manifest.json"
        d = json.loads(path.read_text())
        d["ignored"] = True
        put(path, d)
    else:
        p = runner.build_campaign_plan(unit_bundle, "unit-campaign", "unit-machine")
        data = p.model_dump(mode="json")
        data["primary"][0]["options"]["time_limit_seconds"] = 999.0
        with pytest.raises(ValueError):
            runner.CampaignPlan.model_validate(data)
        return
    with pytest.raises(ValueError):
        runner.build_campaign_plan(unit_bundle, "unit-campaign", "unit-machine")


@pytest.fixture
def headroom_fs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    proc = tmp_path / "proc"
    cg = tmp_path / "cgroup"
    (proc / "self").mkdir(parents=True)
    cg.mkdir()
    (proc / "meminfo").write_text(f"MemAvailable: {10 * 1024**2} kB\n")
    (proc / "self/cgroup").write_text("0::/parent/child\n")
    (proc / "self/mountinfo").write_text(f"1 0 0:1 / {cg} rw - cgroup2 cgroup rw\n")
    (cg / "cgroup.controllers").write_text("cpu memory")
    for name in ("parent", "parent/child"):
        scope = cg / name
        scope.mkdir(exist_ok=True)
        (scope / "memory.max").write_text("max")
        (scope / "memory.current").write_text("0")
    monkeypatch.setattr(runner, "_PROC_ROOT", proc, raising=False)
    monkeypatch.setattr(runner, "_CGROUP_ROOT", cg, raising=False)
    return proc, cg


def test_headroom_uses_tightest_ancestor(headroom_fs: tuple[Path, Path]) -> None:
    proc, cg = headroom_fs
    (cg / "parent/memory.max").write_text(str(5 * 1024**3))
    (cg / "parent/memory.current").write_text(str(2 * 1024**3))
    r = runner.check_headroom(2 * 1024**3)
    assert r.status == "BLOCKED" and r.available_bytes == 3 * 1024**3
    assert r.required_bytes == 4 * 1024**3
    (cg / "parent/memory.max").write_text("max")
    assert runner.check_headroom(2 * 1024**3).status == "PASS"


@pytest.mark.parametrize("missing", ["scope", "mount", "controller", "malformed", "namespace"])
def test_unknown_scope_blocks(headroom_fs: tuple[Path, Path], missing: str) -> None:
    proc, cg = headroom_fs
    if missing == "scope":
        (cg / "parent/memory.max").unlink()
    if missing == "mount":
        (proc / "self/mountinfo").write_text("")
    if missing == "controller":
        (cg / "cgroup.controllers").write_text("cpu")
    if missing == "malformed":
        (cg / "parent/memory.max").write_text("-7")
    if missing == "namespace":
        (proc / "self/mountinfo").write_text(f"1 0 0:1 /hidden {cg} rw - cgroup2 cgroup rw\n")
    r = runner.check_headroom(1024**3)
    assert r.status == "BLOCKED" and r.available_bytes is None and r.reason


def test_second_campaign_cannot_acquire_owner(tmp_path: Path) -> None:
    owner = tmp_path / "owner"
    with runner._campaign_owner(owner, tmp_path / "campaign-a", "a"):
        with pytest.raises(ValueError, match="ACTIVE"):
            with runner._campaign_owner(owner, tmp_path / "campaign-b", "b"):
                pass
    with runner._campaign_owner(owner, tmp_path / "campaign-b", "b"):
        pass


def test_stale_active_marker_needs_review(tmp_path: Path) -> None:
    owner = tmp_path / "owner"
    owner.mkdir()
    put(
        owner / "active.json",
        {
            "schema_version": "1.0",
            "state": "RUNNING",
            "campaign_root": "old",
            "campaign_id": "old",
            "pid": 999999,
        },
    )
    before = (owner / "active.json").read_bytes()
    with pytest.raises(ValueError, match="STALE"):
        with runner._campaign_owner(owner, tmp_path / "new", "new"):
            pass
    assert (owner / "active.json").read_bytes() == before


def case_record(
    root: Path,
    meta: Path,
    *,
    status: str = "OPTIMAL",
    tiers: tuple[int, int, int] = (0, 0, 0),
    peak: int = 1024**2,
    harness: str = "COMPLETE",
    executed: bool | None = None,
) -> Any:
    """Typed simulated execution evidence, never claimed as a real solver measurement."""
    from tkb_core.contracts.output import ScheduleResult, SolverRunMetadataV12, ValidationReport
    from tkb_core.contracts.score import QualityReport, RuleScore, ScoreReport, StageRun

    data = json.loads(meta.read_text())
    fp = data["input_fingerprint"]
    root.mkdir()
    success = status in ("OPTIMAL", "FEASIBLE")
    score = None
    if success:
        score = ScoreReport(
            status="OK",
            input_fingerprint=fp,
            tiers=tiers,
            rules=tuple(
                RuleScore(
                    rule_id=f"unit{p}",
                    code="unit",
                    priority=p,
                    weight=1,
                    unit="teaching_periods",
                    raw_penalty=n,
                    weighted_penalty=n,
                )
                for p, n in enumerate(tiers, 1)
                if n
            ),
        )
    quality = QualityReport(status="NOT_EVALUATED")
    if success:
        stages = tuple(
            StageRun(
                priority=p,
                raw_status="OPTIMAL",
                incumbent_value=n,
                best_bound=n,
                proved_optimal=True,
            )
            if status == "OPTIMAL"
            else StageRun(priority=p)
            for p, n in enumerate(tiers, 1)
        )
        quality = QualityReport(
            status="LEXICOGRAPHIC_OPTIMAL" if status == "OPTIMAL" else "SCORED_FEASIBLE",
            score=score,
            tier_runs=stages,
            optimal_prefix=(1, 2, 3) if status == "OPTIMAL" else (),
        )
    result = ScheduleResult(
        schema_version="1.2",
        status=status,
        input_fingerprint=fp,
        valid_schedule=success,
        validation=ValidationReport(valid=True) if success else None,
        metadata=SolverRunMetadataV12(
            solver_executed=(data["profile"] != "UNSAT_CAPACITY") if executed is None else executed
        ),
        quality=quality,
    )
    (root / "result.json").write_text(result.model_dump_json())
    (root / "stdout.json").write_text(result.model_dump_json())
    (root / "stderr.txt").touch()
    code = {"OPTIMAL": 0, "FEASIBLE": 0, "INFEASIBLE": 3, "UNKNOWN": 4, "MODEL_INVALID": 5}.get(
        status, 2
    )
    e = runner.ExecutionRecord(
        argv=("typed-unit-boundary",),
        run_dir=root,
        stdout_path=root / "stdout.json",
        stderr_path=root / "stderr.txt",
        pid=123,
        raw_wait_status=code << 8,
        exit_code=code,
        launch_to_exit_seconds=1.0,
        cpu_seconds=0.0,
        native_peak_rss_kib=peak // 1024,
        peak_resident_bytes=peak,
        measurement_status="OK",
        measurement_reason=None,
    )
    output = runner.OutputVerification(
        status="VALID_SCHEDULE" if success else "VALID_CORE_ERROR",
        solver_status=status,
        valid_schedule=success,
        score=score,
    )
    limits = runner.RunLimits(
        watchdog_seconds=runner._BUDGETS[data["class_count"]][1],
        max_resident_bytes=runner._BUDGETS[data["class_count"]][2],
    )
    r = runner.RunRecord(
        harness_status=harness,
        execution=e,
        output=output,
        valid_schedule=harness == "COMPLETE" and success,
        identity={
            "input_sha256": data["files"]["input.json"],
            "input_fingerprint": fp,
            "limits": limits.model_dump(mode="json"),
        },
    )
    (root / "run.json").write_text(r.model_dump_json())
    return r


def test_complete_is_not_pilot_pass(tmp_path: Path, unit_bundle: Path) -> None:
    meta = unit_bundle / "c10-base-s101/manifest.json"
    case_record(tmp_path / "run", meta, status="UNKNOWN")
    v = runner.check_case(tmp_path / "run", meta)
    assert (
        v.correctness == "NOT_ASSESSED"
        and v.performance == "NOT_MET"
        and v.quality == "NO_SCHEDULE"
    )


@pytest.mark.parametrize(
    "profile,status,executed,correct",
    [
        ("BASE", "INFEASIBLE", True, "FAIL"),
        ("UNSAT_CAPACITY", "INFEASIBLE", False, "PASS"),
        ("UNSAT_CAPACITY", "INFEASIBLE", True, "FAIL"),
        ("UNSAT_CAPACITY", "UNKNOWN", False, "FAIL"),
        ("BASE", "INPUT_INVALID", False, "FAIL"),
    ],
)
def test_expected_unsat_and_false_infeasible(
    tmp_path: Path, unit_bundle: Path, profile: str, status: str, executed: bool, correct: str
) -> None:
    meta = unit_bundle / f"c10-{profile.lower()}-s101/manifest.json"
    case_record(tmp_path / "run", meta, status=status, executed=executed)
    v = runner.check_case(tmp_path / "run", meta)
    assert v.correctness == correct
    if profile == "UNSAT_CAPACITY":
        assert v.quality == "NOT_APPLICABLE" and v.performance == "NOT_APPLICABLE"


@pytest.mark.parametrize(
    "profile,status,vec,correct,perf,quality",
    [
        ("BASE", "OPTIMAL", (0, 0, 0), "PASS", "MET", "EQUAL"),
        ("BASE", "FEASIBLE", (1, 0, 0), "PASS", "NOT_MET", "WORSE"),
        ("BASE", "OPTIMAL", (1, 0, 0), "FAIL", "NOT_ASSESSED", "WORSE"),
        ("TIGHT", "FEASIBLE", (0, 90, 0), "PASS", "MET", "WORSE"),
        ("TIGHT", "OPTIMAL", (0, 90, 0), "FAIL", "NOT_ASSESSED", "WORSE"),
        ("TIGHT", "FEASIBLE", (0, 59, 0), "FAIL", "NOT_ASSESSED", "BETTER"),
    ],
)
def test_zero_target_and_tight_witness(
    tmp_path: Path,
    unit_bundle: Path,
    profile: str,
    status: str,
    vec: tuple[int, int, int],
    correct: str,
    perf: str,
    quality: str,
) -> None:
    meta = unit_bundle / f"c10-{profile.lower()}-s101/manifest.json"
    case_record(tmp_path / "run", meta, status=status, tiers=vec)
    v = runner.check_case(tmp_path / "run", meta)
    assert (v.correctness, v.performance, v.quality) == (correct, perf, quality)


def test_kernel_peak_over_cap_without_sample_stop(tmp_path: Path, unit_bundle: Path) -> None:
    meta = unit_bundle / "c10-base-s101/manifest.json"
    case_record(tmp_path / "run", meta, peak=2 * 1024**3)
    v = runner.check_case(tmp_path / "run", meta)
    assert v.correctness == "PASS" and v.performance == "NOT_MET"


@pytest.fixture
def campaign(unit_bundle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Only the execution boundary is simulated; journal/state/identity use real files."""
    plan = runner.build_campaign_plan(unit_bundle, "unit-campaign", "unit-machine")
    root = tmp_path / "campaign"
    root.mkdir()
    pref = tmp_path / "preflight"
    pref.mkdir()
    put(pref / "preflight-manifest.json", {"unit": True})
    warm = plan.pilot.model_dump()
    warm.update(
        phase="warmup",
        dataset_id="tiny",
        class_count=None,
        profile="WARMUP",
        generator_seed=0,
        dataset_manifest=None,
        manifest_sha256=None,
        options=runner.SolveOptions(time_limit_seconds=10.0),
        limits=runner.RunLimits(watchdog_seconds=15.0, max_resident_bytes=256 * 1024**2),
        run_id=f"warmup-tiny-{plan.pilot.input_sha256}-w1-s42-r0",
    )
    plan = plan.model_copy(
        update=dict(
            sealed=True,
            warmup=runner.PlannedCase(**warm),
            preflight_dir=pref,
            preflight_sha256=runner._sha(pref / "preflight-manifest.json"),
            runtime_identity={"unit_runtime": True},
            environment={"unit_machine": True},
        )
    )
    runner._write_json(root / "plan.json", plan)
    runner._write_json(root / "environment.json", plan.environment)
    put(
        root / "seal.json",
        {
            "schema_version": "1.0",
            "plan_sha256": runner._sha(root / "plan.json"),
            "environment_sha256": runner._sha(root / "environment.json"),
        },
    )
    monkeypatch.setattr(runner, "_OWNER_ROOT", tmp_path / "owner")
    monkeypatch.setattr(runner, "_runtime_identity", lambda **kw: {"unit_runtime": True})
    monkeypatch.setattr(runner, "_machine_identity", lambda: {"unit_machine": True})
    monkeypatch.setattr(
        runner,
        "check_headroom",
        lambda cap: runner.HeadroomCheck(
            status="PASS",
            target_bytes=cap,
            required_bytes=cap + 2 * 1024**3,
            available_bytes=10 * 1024**3,
            host_available_bytes=10 * 1024**3,
        ),
    )
    calls: list[str] = []
    outcomes: dict[str, dict[str, Any]] = {}

    def fake_run(**kw: Any) -> runner.RunRecord:
        case = next(
            c
            for c in (plan.warmup, plan.pilot, *plan.primary)
            if c is not None and c.run_id == kw["run_dir"].name
        )
        calls.append(case.run_id)
        # Warmup has the same input identity as the pilot solely in this unit fixture.
        assert case.dataset_manifest is not None or case.phase == "warmup"
        defaults = (
            {"status": "INFEASIBLE"}
            if case.profile == "UNSAT_CAPACITY"
            else {"tiers": (0, 8 * case.class_count, 0)}
            if case.profile == "TIGHT"
            else {}
        )
        defaults.update(outcomes.get(case.run_id, {}))
        kw["run_dir"].parent.mkdir(parents=True, exist_ok=True)
        record = case_record(
            kw["run_dir"],
            plan.pilot.dataset_manifest if case.phase == "warmup" else case.dataset_manifest,
            **defaults,
        )
        return record

    monkeypatch.setattr(runner, "run_cli_once", fake_run)
    return root / "plan.json", pref, plan, calls, outcomes


def run_phase(campaign: Any, phase: str, *, resume: bool = False) -> Any:
    path, pref, _, _, _ = campaign
    return runner.execute_campaign(path, pref, phase=phase, resume=resume)


def ready(campaign: Any) -> None:
    assert run_phase(campaign, "warmup").status == "COMPLETE"
    assert run_phase(campaign, "pilot").status == "COMPLETE"


def test_campaign_persists_rows_in_plan_order(campaign: Any) -> None:
    path, _, plan, calls, _ = campaign
    ready(campaign)
    state = run_phase(campaign, "primary")
    assert state.status == "COMPLETE"
    assert len(state.rows) == 108 and state.completed == 108 and state.pending == 0
    assert state.failed == 0
    assert run_phase(campaign, "primary", resume=True).failed == 0
    assert calls[2:] == [c.run_id for c in plan.primary]
    journal = [
        json.loads(line) for line in (path.parent / "journal.jsonl").read_text().splitlines()
    ]
    assert [
        e["run_id"] for e in journal if e["phase"] == "primary" and e["event"] == "START"
    ] == calls[2:]
    assert all(
        (path.parent / "primary" / c.run_id / "terminal.json").is_file() for c in plan.primary
    )


def test_resume_skips_failed_terminal_runs(campaign: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    path, _, plan, calls, outcomes = campaign
    ready(campaign)
    outcomes[plan.primary[0].run_id] = dict(status="UNKNOWN")
    real = runner.check_headroom
    count = 0

    def headroom(cap: int) -> Any:
        nonlocal count
        count += 1
        if count == 2:
            return runner.HeadroomCheck(
                status="BLOCKED",
                target_bytes=cap,
                required_bytes=cap + 2 * 1024**3,
                reason="UNIT_HEADROOM",
            )
        return real(cap)

    monkeypatch.setattr(runner, "check_headroom", headroom)
    state = run_phase(campaign, "primary")
    assert state.status == "BLOCKED" and state.attempted == 1 and state.pending == 107
    raw = (path.parent / "primary" / plan.primary[0].run_id / "run.json").read_bytes()
    monkeypatch.setattr(runner, "check_headroom", real)
    assert run_phase(campaign, "primary", resume=True).status == "COMPLETE"
    assert calls.count(plan.primary[0].run_id) == 1
    assert (path.parent / "primary" / plan.primary[0].run_id / "run.json").read_bytes() == raw


def test_gate_failure_starts_no_child(campaign: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    path, _, plan, calls, _ = campaign
    ready(campaign)
    monkeypatch.setattr(
        runner,
        "check_headroom",
        lambda cap: runner.HeadroomCheck(
            status="BLOCKED", target_bytes=cap, required_bytes=cap + 2 * 1024**3, reason="UNIT"
        ),
    )
    state = run_phase(campaign, "primary")
    assert state.status == "BLOCKED" and state.attempted == 0 and len(calls) == 2
    assert state.rows[plan.primary[0].run_id] == "NOT_STARTED_GATE_BLOCKED"
    assert not (path.parent / "primary" / plan.primary[0].run_id).exists()


def test_partial_run_is_not_overwritten(campaign: Any) -> None:
    path, _, plan, calls, _ = campaign
    ready(campaign)
    partial = path.parent / "primary" / plan.primary[0].run_id
    partial.mkdir(parents=True)
    (partial / "stdout.json").write_text("partial evidence")
    assert run_phase(campaign, "primary", resume=True).status == "NEEDS_REVIEW"
    assert len(calls) == 2 and (partial / "stdout.json").read_text() == "partial evidence"


@pytest.mark.parametrize("drift", ["source", "input", "plan", "machine", "preflight"])
def test_changed_identity_blocks_resume(
    campaign: Any, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    path, pref, plan, calls, _ = campaign
    ready(campaign)
    if drift == "source":
        monkeypatch.setattr(runner, "_source_ids", lambda: {"controller": "0" * 64})
    elif drift == "input":
        plan.primary[0].input_path.write_text("changed")
    elif drift == "plan":
        path.write_bytes(path.read_bytes() + b" ")
    elif drift == "machine":
        monkeypatch.setattr(runner, "_machine_identity", lambda: {"unit_machine": False})
    else:
        (pref / "preflight-manifest.json").write_text("{}")
    assert run_phase(campaign, "primary", resume=True).status == "BLOCKED"
    assert len(calls) == 2


@pytest.mark.parametrize("harness", ["CANCELLED", "MEASUREMENT_BLOCKED", "CRASH", "OUTPUT_INVALID"])
def test_cancel_or_unconfirmed_reap_stops_next_case(campaign: Any, harness: str) -> None:
    _, _, plan, calls, outcomes = campaign
    ready(campaign)
    outcomes[plan.primary[0].run_id] = dict(harness=harness, status="UNKNOWN")
    state = run_phase(campaign, "primary")
    assert state.status in ("STOPPED", "CANCELLED", "NEEDS_REVIEW") and state.pending == 107
    assert len(calls) == 3


def test_pilot_not_met_never_starts_primary(campaign: Any) -> None:
    _, _, plan, calls, outcomes = campaign
    run_phase(campaign, "warmup")
    outcomes[plan.pilot.run_id] = dict(status="UNKNOWN")
    assert run_phase(campaign, "pilot").status == "STOPPED"
    assert run_phase(campaign, "primary").status == "BLOCKED"
    assert len(calls) == 2


def test_explicit_resume_required_and_terminal_tamper_rejected(campaign: Any) -> None:
    path, _, plan, calls, _ = campaign
    ready(campaign)
    assert run_phase(campaign, "pilot").status == "BLOCKED"
    assert run_phase(campaign, "pilot", resume=True).status == "COMPLETE"
    (path.parent / "pilot" / plan.pilot.run_id / "stdout.json").write_text("changed")
    assert run_phase(campaign, "primary").status == "NEEDS_REVIEW"
    assert len(calls) == 2


def test_cli_requires_explicit_phase(capsys: Any) -> None:
    with pytest.raises(SystemExit) as error:
        runner.main([])
    assert error.value.code == 2
    assert "--phase" in capsys.readouterr().err


def test_headroom_contract_rejects_false_pass() -> None:
    with pytest.raises(ValueError):
        runner.HeadroomCheck(
            status="PASS",
            target_bytes=1024,
            required_bytes=2048,
            available_bytes=1,
            host_available_bytes=1,
        )


def test_start_journal_keeps_admission_evidence(campaign: Any) -> None:
    path, _, _, _, _ = campaign
    run_phase(campaign, "warmup")
    events = [json.loads(line) for line in (path.parent / "journal.jsonl").read_text().splitlines()]
    detail = events[0]["detail"]
    assert detail["headroom"]["status"] == "PASS" and detail["disk_free_bytes"] > 0


def test_journal_rejects_nonprefix_execution_order(campaign: Any) -> None:
    path, _, plan, _, _ = campaign
    ready(campaign)
    put(path.parent / "bogus.json", {})
    event = {
        "schema_version": "1.0",
        "plan_sha256": runner._sha(path),
        "phase": "primary",
        "event": "START",
        "run_id": plan.primary[1].run_id,
        "detail": None,
        "timestamp_utc": "2026-10-27T00:00:00+00:00",
    }
    with (path.parent / "journal.jsonl").open("a") as out:
        out.write(json.dumps(event) + "\n")
    assert run_phase(campaign, "primary", resume=True).reason == "JOURNAL_ORDER_DRIFT"


def test_prepare_seals_without_scheduling(
    campaign: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.contracts.output import ScheduleResult, SolverRunMetadataV12
    from tkb_core.contracts.score import QualityReport

    path, pref, plan, calls, _ = campaign
    (pref / "smoke").mkdir()
    problem = ScheduleInput.model_validate_json(
        (runner.ROOT / "tests/fixtures/quality/priority_tradeoff.json").read_text()
    )
    (pref / "smoke/input.json").write_text(problem.model_dump_json())
    result = ScheduleResult(
        schema_version="1.2",
        status="UNKNOWN",
        input_fingerprint=problem.fingerprint(),
        metadata=SolverRunMetadataV12(solver_executed=False),
        quality=QualityReport(status="NOT_EVALUATED"),
    )
    # prepare must reject a frozen setup with no known feasible result.
    (pref / "smoke/result.json").write_text(result.model_dump_json())
    put(
        pref / "preflight-manifest.json",
        {
            "files": {
                name: runner._sha(pref / name) for name in ("smoke/input.json", "smoke/result.json")
            }
        },
    )
    monkeypatch.setattr(runner, "_verify_frozen_bundle", lambda *args: None)
    with pytest.raises(ValueError, match="WARMUP_FIXTURE_INVALID"):
        runner._prepare_campaign(
            plan.bundle_dir, pref, tmp_path / "bad-prepare", "new", "unit-machine"
        )
    assert calls == [] and not (tmp_path / "bad-prepare/plan.json").exists()


@pytest.mark.parametrize(
    "argv",
    [
        ["--phase", "prepare", "--preflight-dir", "x", "--resume"],
        ["--phase", "primary", "--preflight-dir", "x"],
        ["--phase", "primary", "--preflight-dir", "x", "--plan", "p", "--bundle", "b"],
    ],
)
def test_cli_rejects_mixed_or_incomplete_arguments(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        runner.main(argv)
    assert error.value.code == 2


def test_resource_stop_with_missing_measurement_stops_campaign(
    campaign: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, plan, calls, outcomes = campaign
    ready(campaign)
    original = runner.run_cli_once

    def bad_probe(**kw: Any) -> Any:
        record = original(**kw)
        record = record.model_copy(
            update={
                "harness_status": "RESOURCE_STOP",
                "valid_schedule": False,
                "execution": record.execution.model_copy(
                    update={
                        "measurement_status": "BLOCKED",
                        "measurement_reason": "UNIT_PROBE_LOST",
                        "stop_reason": "RESOURCE_LIMIT",
                    }
                ),
            }
        )
        (kw["run_dir"] / "run.json").write_text(record.model_dump_json())
        return record

    monkeypatch.setattr(runner, "run_cli_once", bad_probe)
    state = run_phase(campaign, "primary")
    assert state.status == "STOPPED" and len(calls) == 3


def test_unconfirmed_reap_leaves_owner_needs_review(
    campaign: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, _, calls, _ = campaign
    ready(campaign)
    original = runner.run_cli_once

    def unconfirmed(**kw: Any) -> Any:
        record = original(**kw)
        record = record.model_copy(
            update={
                "harness_status": "MEASUREMENT_BLOCKED",
                "valid_schedule": False,
                "execution": record.execution.model_copy(
                    update={
                        "measurement_status": "BLOCKED",
                        "measurement_reason": "REAP_UNCONFIRMED",
                    }
                ),
            }
        )
        (kw["run_dir"] / "run.json").write_text(record.model_dump_json())
        return record

    monkeypatch.setattr(runner, "run_cli_once", unconfirmed)
    assert run_phase(campaign, "primary").status == "NEEDS_REVIEW"
    assert json.loads((runner._OWNER_ROOT / "active.json").read_text())["state"] == "NEEDS_REVIEW"
    assert len(calls) == 3


@pytest.mark.parametrize(
    "reason",
    [
        "REAP_UNCONFIRMED",
        "OWNERSHIP_OR_WAIT4_LOST",
        "PID_MISMATCH",
        "OWNERSHIP_NOT_CONFIRMED",
        "NOT_REAPED",
    ],
)
def test_cancel_with_uncertain_cleanup_keeps_owner(
    campaign: Any, monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    _, _, _, calls, _ = campaign
    ready(campaign)
    original = runner.run_cli_once

    def uncertain(**kw: Any) -> Any:
        record = original(**kw)
        record = record.model_copy(
            update={
                "harness_status": "CANCELLED",
                "valid_schedule": False,
                "execution": record.execution.model_copy(
                    update={
                        "measurement_status": "BLOCKED",
                        "measurement_reason": reason,
                        "raw_wait_status": None,
                        "exit_code": None,
                        "stop_reason": "PARENT_INTERRUPTED",
                    }
                ),
            }
        )
        (kw["run_dir"] / "run.json").write_text(record.model_dump_json())
        return record

    monkeypatch.setattr(runner, "run_cli_once", uncertain)
    assert run_phase(campaign, "primary").status == "NEEDS_REVIEW"
    assert json.loads((runner._OWNER_ROOT / "active.json").read_text())["state"] == "NEEDS_REVIEW"
    assert len(calls) == 3


@pytest.mark.parametrize("harness", ["WATCHDOG_TIMEOUT", "RESOURCE_STOP"])
def test_interrupted_unsat_without_result_is_unassessed(
    unit_bundle: Path, tmp_path: Path, harness: str
) -> None:
    manifest = unit_bundle / "c10-unsat_capacity-s101/manifest.json"
    base = tmp_path / "run"
    case_record(base, manifest, status="INFEASIBLE", harness=harness)
    (base / "result.json").unlink()
    verdict = runner.check_case(base, manifest)
    assert verdict.correctness == "NOT_ASSESSED" and verdict.quality == "NOT_APPLICABLE"
    assert verdict.performance == "NOT_APPLICABLE"


def test_pre_spawn_terminal_remains_terminal_on_resume(
    campaign: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, _, calls, _ = campaign
    ready(campaign)

    def not_started(**kw: Any) -> Any:
        calls.append(kw["run_dir"].name)
        base = kw["run_dir"]
        base.mkdir(parents=True)
        record = runner.RunRecord(
            harness_status="ENVIRONMENT_BLOCKED",
            execution=runner.ExecutionRecord(
                argv=("unit-not-spawned",),
                run_dir=base,
                stdout_path=base / "stdout.json",
                stderr_path=base / "stderr.txt",
                error_type="ValueError",
            ),
            output=runner.OutputVerification(diagnostics=("UNIT_RUNTIME_GATE",)),
            identity={"expected_input_sha256": kw["input_sha256"]},
        )
        (base / "run.json").write_text(record.model_dump_json())
        return record

    monkeypatch.setattr(runner, "run_cli_once", not_started)
    state = run_phase(campaign, "primary")
    assert state.status == "STOPPED"
    state = run_phase(campaign, "primary", resume=True)
    assert state.status == "STOPPED" and state.attempted == 1 and len(calls) == 3


def test_start_context_is_timestamped_and_explicit(campaign: Any) -> None:
    from datetime import datetime

    path, _, _, _, _ = campaign
    run_phase(campaign, "warmup")
    events = [json.loads(line) for line in (path.parent / "journal.jsonl").read_text().splitlines()]
    context = events[0]["detail"]["operational_context"]
    assert datetime.fromisoformat(context["timestamp_utc"]).tzinfo is not None
    assert "load_average" in context and "power" in context
    assert context["workload_control"] == "UNCONTROLLED"
    assert all("timestamp_utc" in e for e in events)


def test_repository_owner_root_is_shared_across_worktrees(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    common = root / ".git"
    common.mkdir(parents=True)
    (common / "worktrees/a").mkdir(parents=True)
    (common / "worktrees/a/commondir").write_text("../..\n")
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / ".git").write_text(f"gitdir: {common}/worktrees/a\n")
    assert runner._repository_owner_root(root) == runner._repository_owner_root(linked)


def test_prepare_freezes_plan_without_starting_any_run(
    campaign: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from tkb_core.contracts.input import ScheduleInput
    from tkb_core.contracts.output import ScheduleResult, SolverRunMetadataV12
    from tkb_core.contracts.score import QualityReport
    from tkb_core.domain.models import ScheduleAssignment
    from tkb_core.validation.independent_validator import validate_schedule
    from tkb_core.validation.score_evaluator import evaluate_score

    _, pref, plan, calls, _ = campaign
    (pref / "smoke").mkdir()
    problem = ScheduleInput.model_validate_json(
        (runner.ROOT / "tests/fixtures/quality/priority_tradeoff.json").read_text()
    )
    assignments = (
        ScheduleAssignment(occurrence_id="r::1", slot_id="A", class_ids=("c",), teacher_ids=("t",)),
    )
    validation = validate_schedule(problem, assignments)
    score = evaluate_score(problem, assignments)
    assert validation.valid and score.status == "OK"
    result = ScheduleResult(
        schema_version="1.2",
        status="FEASIBLE",
        input_fingerprint=problem.fingerprint(),
        valid_schedule=True,
        assignments=assignments,
        validation=validation,
        metadata=SolverRunMetadataV12(solver_executed=False),
        quality=QualityReport(status="SCORED_FEASIBLE", score=score),
    )
    (pref / "smoke/input.json").write_text(problem.model_dump_json())
    (pref / "smoke/result.json").write_text(result.model_dump_json())
    put(
        pref / "preflight-manifest.json",
        {
            "files": {
                name: runner._sha(pref / name) for name in ("smoke/input.json", "smoke/result.json")
            }
        },
    )
    verified = []
    monkeypatch.setattr(
        runner, "_verify_frozen_bundle", lambda bundle, output: verified.append(bundle)
    )
    output = tmp_path / "prepared"
    sealed = runner._prepare_campaign(plan.bundle_dir, pref, output, "prepared", "unit-machine")
    assert sealed.sealed and sealed.warmup is not None and len(sealed.primary) == 108
    assert calls == [] and verified == [plan.bundle_dir]
    seal = json.loads((output / "seal.json").read_text())
    assert seal["plan_sha256"] == runner._sha(output / "plan.json")
    assert seal["environment_sha256"] == runner._sha(output / "environment.json")
    assert not (output / "journal.jsonl").exists()
    before = (output / "plan.json").read_bytes()
    with pytest.raises(FileExistsError):
        runner._prepare_campaign(plan.bundle_dir, pref, output, "prepared", "unit-machine")
    assert before == (output / "plan.json").read_bytes() and calls == []
