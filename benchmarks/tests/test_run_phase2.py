"""v2 controller: version pairs, H/Q/P/zero verdicts, pilot gate, plan and stop policy."""

import contextlib
import copy
import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from benchmarks import generate_phase2 as g2
from benchmarks import run_benchmarks as v1
from benchmarks import run_phase2 as r2
from benchmarks.generate_synthetic import Dimensions
from tkb_core.cli import main as cli
from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.score import ScoreReport

ROOT = Path(__file__).resolve().parents[2]


def _policy_input(policy: str) -> dict[str, Any]:
    data = r2.policy04_smoke_input()
    config = data["constraint_config"]
    config["policy_version"] = policy
    if policy != "0.4":
        config["soft"] = []
        config.pop("occupied_work")
    if policy in ("0.1", "0.2"):
        config["hard"] = [h for h in config["hard"] if h["code"] != "SUBJECT_COMPONENT_DAY_SPREAD"]
    if policy == "0.1":
        config["hard"] = []
    return data


def _solve(base: Path, data: dict[str, Any]) -> tuple[Path, Path, int]:
    base.mkdir(parents=True, exist_ok=True)
    source = base / "input.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    result = base / "result.json"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli(["solve", str(source), "--time-limit", "5", "--output", str(result)])
    (base / "stdout.json").write_text(out.getvalue(), encoding="utf-8")
    return source, result, code


def _execution(
    base: Path,
    code: int | None,
    *,
    measured: bool = True,
    rss_kib: int = 1000,
    seconds: float = 1.0,
    stop: str | None = None,
) -> v1.ExecutionRecord:
    fields: dict[str, Any] = dict(
        argv=("python",),
        run_dir=base,
        stdout_path=base / "stdout.json",
        stderr_path=base / "stderr.txt",
        exit_code=code,
        stop_reason=stop,
    )
    if measured:
        fields.update(
            pid=4242,
            raw_wait_status=0,
            cpu_seconds=0.5,
            native_peak_rss_kib=rss_kib,
            peak_resident_bytes=rss_kib * 1024,
            launch_to_exit_seconds=seconds,
            measurement_status="OK",
            measurement_reason=None,
        )
    else:
        fields.update(pid=4242, measurement_status="BLOCKED", measurement_reason="PROBE")
    return v1.ExecutionRecord(**fields)


def _record(
    base: Path, source: Path, execution: v1.ExecutionRecord, verify: bool = True
) -> v1.RunRecord:
    problem = ScheduleInput.model_validate(json.loads(source.read_text()))
    output = (
        r2.verify_output_v2(source, base / "result.json", execution)
        if verify
        else v1.OutputVerification()
    )
    status = v1.classify_run(execution, output)
    record = v1.RunRecord(
        harness_status=status,
        execution=execution,
        output=output,
        identity={
            "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "input_fingerprint": problem.fingerprint(),
        },
        valid_schedule=status == "COMPLETE" and output.valid_schedule,
    )
    (base / "run.json").write_text(record.model_dump_json(indent=2) + "\n")
    return record


def _manifest(
    base: Path,
    source: Path,
    *,
    profile: str = "BASE",
    baseline: ScoreReport | None = None,
    known: tuple[int, int, int] | None = None,
    p2: int | None = None,
) -> Path:
    problem = ScheduleInput.model_validate(json.loads(source.read_text()))
    zero = "0" * 64
    manifest = g2.DatasetManifest(
        dataset_id="c10-base-s101-soft",
        class_count=10,
        profile=profile,
        variant="SOFT",
        seed=101,
        input_fingerprint=problem.fingerprint(),
        ground_truth="INFEASIBLE" if profile == "UNSAT_CAPACITY" else "FEASIBLE",
        known_optimum=known,
        baseline_score=baseline,
        p2_lower_bound=p2,
        capacity_proof=None,
        dimensions=Dimensions(
            classes=1,
            teachers=1,
            subjects=2,
            rooms=0,
            slots=12,
            requirements=2,
            periods=5,
            occurrences=4,
            placements=None,
            occupancy_terms=None,
            slot_tokens=None,
            precheck_status="READY",
            room_required_requirements=0,
            room_occurrences=0,
            room_periods=0,
            locked_occurrences=0,
            locks_with_room=0,
            teacher_loads={},
            teacher_available_slots={},
            class_available_slots={},
        ),
        rule_counts={"soft:TEACHER_TOTAL_GAPS": 1},
        omitted={},
        s05_component_pairs=0,
        sources={"generator_source_sha256": zero},
        files={"input.json": hashlib.sha256(source.read_bytes()).hexdigest()},
    )
    path = base / "dataset-manifest.json"
    path.write_text(manifest.model_dump_json(indent=2))
    return path


def _solved_case(tmp_path: Path) -> tuple[Path, Path, ScoreReport]:
    base = tmp_path / "run"
    source, result, code = _solve(base, r2.policy04_smoke_input())
    assert code == 0
    score = ScoreReport.model_validate(json.loads(result.read_text())["quality"]["score"])
    assert score.tiers == (0, 0, 1)
    return base, source, score


def test_budgets_and_version_table_match_v1_and_core() -> None:
    assert r2.BUDGETS == v1._BUDGETS
    r2.check_version_table()


def test_version_table_drift_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    from tkb_core.contracts import output

    monkeypatch.setitem(output.SCORE_VERSION, "1.5", "1.1")
    with pytest.raises(ValueError, match="VERSION_TABLE_DRIFT"):
        r2.check_version_table()


@pytest.mark.parametrize(
    ("policy", "output_version", "score_version"),
    [("0.1", "1.2", "1.0"), ("0.2", "1.3", "1.0"), ("0.3", "1.4", "1.1"), ("0.4", "1.5", "1.2")],
)
def test_verify_accepts_each_policy_pair(
    tmp_path: Path, policy: str, output_version: str, score_version: str
) -> None:
    source, result, code = _solve(tmp_path, _policy_input(policy))
    assert code == 0
    assert json.loads(result.read_text())["schema_version"] == output_version
    verified = r2.verify_output_v2(source, result, _execution(tmp_path, code))
    assert verified.status == "VALID_SCHEDULE"
    assert verified.score is not None and verified.score.schema_version == score_version


def test_v1_verifier_rejects_policy_04_but_v2_accepts(tmp_path: Path) -> None:
    source, result, code = _solve(tmp_path, r2.policy04_smoke_input())
    execution = _execution(tmp_path, code)
    assert v1.verify_cli_output(source, result, execution).status == "INVALID"
    assert r2.verify_output_v2(source, result, execution).status == "VALID_SCHEDULE"


def test_verify_rejects_a_result_from_another_policy(tmp_path: Path) -> None:
    source, _, _ = _solve(tmp_path / "a", r2.policy04_smoke_input())
    other_source, other_result, code = _solve(tmp_path / "b", _policy_input("0.3"))
    # Same calendar, but a 1.4 result cannot describe a policy 0.4 input.
    (tmp_path / "a" / "stdout.json").write_text((tmp_path / "b" / "stdout.json").read_text())
    (tmp_path / "a" / "result.json").write_text(other_result.read_text())
    verified = r2.verify_output_v2(
        source, tmp_path / "a" / "result.json", _execution(tmp_path / "a", code)
    )
    assert verified.status == "INVALID"


def test_verify_rejects_exit_mismatch_and_input_10(tmp_path: Path) -> None:
    source, result, _ = _solve(tmp_path, r2.policy04_smoke_input())
    assert r2.verify_output_v2(source, result, _execution(tmp_path, 4)).status == "INVALID"
    legacy = json.loads(source.read_text())
    legacy["schema_version"] = "1.0"
    legacy.pop("constraint_config")
    old = tmp_path / "legacy.json"
    old.write_text(json.dumps(legacy))
    assert r2.verify_output_v2(old, result, _execution(tmp_path, 0)).status == "INVALID"


def test_nonzero_score_is_p_met_and_q_review(tmp_path: Path) -> None:
    base, source, score = _solved_case(tmp_path)
    _record(base, source, _execution(base, 0))
    verdict = r2.judge_case(base, _manifest(base, source, baseline=score))
    assert verdict.hard == "PASS" and verdict.performance == "MET"
    assert verdict.quality == "REVIEW_REQUIRED" and verdict.witness_comparison == "EQUAL"
    assert verdict.zero == "NOT_APPLICABLE" and verdict.reasons == ()


def test_zero_is_reported_but_not_a_p_gate(tmp_path: Path) -> None:
    base, source, score = _solved_case(tmp_path)
    _record(base, source, _execution(base, 0))
    verdict = r2.judge_case(base, _manifest(base, source, baseline=score, known=(0, 0, 0)))
    assert verdict.zero == "NOT_MET" and verdict.performance == "MET"


def test_limits_and_missing_measurement(tmp_path: Path) -> None:
    base, source, score = _solved_case(tmp_path)
    _record(base, source, _execution(base, 0, rss_kib=1024**2 + 1))
    manifest = _manifest(base, source, baseline=score)
    over = r2.judge_case(base, manifest)
    assert over.hard == "PASS" and over.performance == "NOT_MET"
    (base / "run.json").unlink()
    _record(base, source, _execution(base, 0, seconds=151.0))
    assert r2.judge_case(base, manifest).performance == "NOT_MET"
    (base / "run.json").unlink()
    record = _record(base, source, _execution(base, 0, measured=False))
    assert record.harness_status == "MEASUREMENT_BLOCKED"
    blocked = r2.judge_case(base, manifest)
    assert blocked.performance == "INCOMPLETE" and blocked.hard == "NOT_APPLICABLE"


def test_lower_bound_violation_is_h_fail(tmp_path: Path) -> None:
    base, source, score = _solved_case(tmp_path)
    _record(base, source, _execution(base, 0))
    verdict = r2.judge_case(base, _manifest(base, source, baseline=score, p2=5))
    assert verdict.hard == "FAIL" and "BELOW_DECLARED_LOWER_BOUND" in verdict.reasons


def test_watchdog_without_schedule_is_p_not_met(tmp_path: Path) -> None:
    base, source, score = _solved_case(tmp_path)
    _record(base, source, _execution(base, -9, stop="WATCHDOG"), verify=False)
    verdict = r2.judge_case(base, _manifest(base, source, baseline=score, known=(0, 0, 0)))
    assert verdict.hard == "NOT_APPLICABLE" and verdict.performance == "NOT_MET"
    assert verdict.quality == "NO_SCHEDULE" and verdict.zero == "NOT_MET"


def _unsat(tmp_path: Path) -> tuple[Path, Path]:
    data = r2.policy04_smoke_input()
    data["classes"] = [{"id": "C1", "available_slot_ids": ["d1-am-p1", "d1-am-p2", "d1-am-p3"]}]
    base = tmp_path / "unsat"
    source, _, code = _solve(base, data)
    assert code == 3
    _record(base, source, _execution(base, 3))
    return base, source


def test_unsat_expectation(tmp_path: Path) -> None:
    base, source = _unsat(tmp_path)
    verdict = r2.judge_case(base, _manifest(base, source, profile="UNSAT_CAPACITY"))
    assert verdict.hard == "PASS"
    assert (verdict.performance, verdict.quality) == ("NOT_APPLICABLE", "NOT_APPLICABLE")
    # The same INFEASIBLE outcome on a known-feasible dataset is a hard-correctness failure.
    wrong = r2.judge_case(base, _manifest(base, source, profile="BASE"))
    assert wrong.hard == "FAIL" and wrong.reasons == ("UNEXPECTED_CORE_ERROR:INFEASIBLE",)


def _case(phase: str = "pilot", profile: str = "BASE") -> r2.PlannedCase:
    size = 10
    budget = r2.BUDGETS[size]
    ident = g2.dataset_id(size, profile, 101, "SOFT")
    repeat = 0 if phase == "pilot" else 1
    sha = "a" * 64
    return r2.PlannedCase(
        run_id=f"{phase}-{ident}-{sha}-w1-s42-r{repeat}",
        dataset_id=ident,
        phase=phase,
        repeat=repeat,
        class_count=size,
        profile=profile,
        variant="SOFT",
        generator_seed=101,
        input_path=Path("/x/input.json"),
        dataset_manifest=Path("/x/manifest.json"),
        manifest_sha256=sha,
        input_sha256=sha,
        input_fingerprint=sha,
        ground_truth="INFEASIBLE" if profile == "UNSAT_CAPACITY" else "FEASIBLE",
        options=r2.SolveOptions(time_limit_seconds=budget[0]),
        limits=v1.RunLimits(watchdog_seconds=budget[1], max_resident_bytes=budget[2]),
    )


def _outcome(
    tmp_path: Path, *, performance: str = "MET", hard: str = "PASS"
) -> tuple[v1.RunRecord, r2.CaseVerdict]:
    base, source, _ = _solved_case(tmp_path)
    record = _record(base, source, _execution(base, 0))
    verdict = r2.CaseVerdict(
        hard=hard,
        quality="REVIEW_REQUIRED",
        performance=performance,
        run_sha256="b" * 64,
    )
    return record, verdict


def test_pilot_gate_follows_d2(tmp_path: Path) -> None:
    record, met = _outcome(tmp_path)
    assert (
        r2.qualified(record, met, _case("pilot")) and r2.stop_status(record, met, _case()) is None
    )
    slow = met.model_copy(update={"performance": "NOT_MET"})
    assert r2.stop_status(record, slow, _case("pilot")) == "STOPPED"
    # Primary keeps collecting through P NOT_MET, but never through H FAIL.
    assert r2.stop_status(record, slow, _case("primary")) is None
    fail = met.model_copy(update={"hard": "FAIL"})
    assert r2.stop_status(record, fail, _case("primary")) == "STOPPED"


def test_unsafe_harness_states_stop(tmp_path: Path) -> None:
    record, met = _outcome(tmp_path)
    for status in ("CRASH", "OUTPUT_INVALID", "ENVIRONMENT_BLOCKED"):
        changed = record.model_copy(update={"harness_status": status, "valid_schedule": False})
        assert r2.stop_status(changed, met, _case("primary")) == "STOPPED"
    cancelled = record.model_copy(update={"harness_status": "CANCELLED", "valid_schedule": False})
    assert r2.stop_status(cancelled, met, _case("primary")) == "CANCELLED"


def test_planned_case_rejects_budget_and_pilot_drift() -> None:
    data = _case("pilot").model_dump()
    with pytest.raises(ValueError):
        r2.PlannedCase.model_validate(
            data | {"options": r2.SolveOptions(time_limit_seconds=90.0).model_dump()}
        )
    other = g2.dataset_id(10, "MIXED", 101, "SOFT")
    with pytest.raises(ValueError):
        r2.PlannedCase.model_validate(
            data | {"dataset_id": other, "run_id": data["run_id"].replace("base", "mixed")}
        )


def _fake_bundle(root: Path) -> Path:
    real = g2.generate_dataset(10, "BASE", 101, "SOFT").manifest
    entries = []
    for ident in sorted(g2.expected_dataset_ids()):
        size, profile, seed, variant = ident.split("-")
        dest = root / ident
        dest.mkdir(parents=True)
        names = (
            ("input.json", "provenance-input.json", "provenance-witness.json")
            if profile == "unsat_capacity"
            else ("input.json", "witness.json")
        )
        files = {}
        for name in names:
            data = f"{ident}/{name}".encode()
            (dest / name).write_bytes(data)
            files[name] = hashlib.sha256(data).hexdigest()
        manifest = real.model_copy(
            update={
                "dataset_id": ident,
                "class_count": int(size[1:]),
                "profile": profile.upper(),
                "variant": variant.upper(),
                "seed": int(seed[1:]),
                "ground_truth": "INFEASIBLE" if profile == "unsat_capacity" else "FEASIBLE",
                "files": files,
            }
        )
        raw = manifest.model_dump_json(indent=2).encode()
        (dest / "manifest.json").write_bytes(raw)
        entries.append({"dataset_id": ident, "manifest_sha256": hashlib.sha256(raw).hexdigest()})
    bundle = {
        "benchmark_schema_version": "2.0",
        "protocol": "phase2-linux-v2",
        "revision": {"repository_head": None, "generator_matches_head": False},
        "datasets": entries,
    }
    (root / "manifest.json").write_text(json.dumps(bundle))
    return root


def test_plan_membership_order_and_pilots(tmp_path: Path) -> None:
    plan = r2.build_campaign_plan(_fake_bundle(tmp_path / "bundle"), "c1", "m1")
    assert len(plan.primary) == r2.PRIMARY_COUNT == 216
    assert sum(c.ground_truth == "INFEASIBLE" for c in plan.primary) == 54
    assert [c.dataset_id for c in plan.pilots] == ["c10-base-s101-soft", "c10-base-s101-hard"]
    assert [(c.dataset_id, c.repeat) for c in plan.primary] == r2.primary_order(
        g2.expected_dataset_ids()
    )
    assert set(plan.source_ids) >= {"controller", "generator", "controller_v1", "generator_v1"}
    data = plan.model_dump()
    swapped = copy.deepcopy(data)
    rows = list(swapped["primary"])
    rows[0], rows[1] = rows[1], rows[0]
    swapped["primary"] = rows
    with pytest.raises(ValueError):
        r2.CampaignPlan.model_validate(swapped)
    with pytest.raises(ValueError):
        r2.CampaignPlan.model_validate(data | {"primary": data["primary"][:-1]})
    with pytest.raises(ValueError):
        r2.CampaignPlan.model_validate(data | {"pilots": data["pilots"][::-1]})
    with pytest.raises(ValueError):
        r2.CampaignPlan.model_validate(data | {"sealed": True})


def test_plan_rejects_tampered_bundle(tmp_path: Path) -> None:
    root = _fake_bundle(tmp_path / "bundle")
    (root / "c20-mixed-s102-hard" / "input.json").write_bytes(b"changed")
    with pytest.raises(ValueError):
        r2.build_campaign_plan(root, "c1", "m1")


def test_unsealed_plan_never_executes(tmp_path: Path) -> None:
    plan = r2.build_campaign_plan(_fake_bundle(tmp_path / "bundle"), "c1", "m1")
    path = tmp_path / "campaign" / "plan.json"
    path.parent.mkdir()
    path.write_text(plan.model_dump_json())
    state = r2.execute_campaign(path, tmp_path / "preflight", phase="pilot")
    assert state.status == "BLOCKED" and state.reason is not None
    assert state.reason.startswith("IDENTITY_BLOCKED")
    assert not (tmp_path / "campaign" / "pilot").exists()


def test_policy04_smoke_uses_installed_style_cli(tmp_path: Path) -> None:
    def run(name: str, argv: list[str], timeout: float = 300) -> str:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        assert done.returncode == 0, (name, done.stderr)
        return done.stdout

    result = r2.run_policy04_smoke(
        tmp_path / "smoke", {"solver": sys.executable, "no-solver": sys.executable}, run
    )
    assert (result["status"], result["output_version"], result["score_version"]) == (
        "PASS",
        "1.5",
        "1.2",
    )


def test_cli_argument_contract() -> None:
    with pytest.raises(SystemExit):
        r2.main(["--phase", "preflight"])
    with pytest.raises(SystemExit):
        r2.main(["--phase", "pilot", "--preflight-dir", "/x"])


def test_output_invalid_on_known_feasible_is_h_fail(tmp_path: Path) -> None:
    """Review F1: a schedule whose embedded score disagrees is a Core technical error."""
    base, source, score = _solved_case(tmp_path)
    result = json.loads((base / "result.json").read_text())
    row = result["quality"]["score"]["rules"][0]
    row["raw_penalty"] += 1
    row["weighted_penalty"] += 1
    result["quality"]["score"]["tiers"][row["priority"] - 1] += 1
    text = json.dumps(result)
    (base / "result.json").write_text(text)
    (base / "stdout.json").write_text(text)
    record = _record(base, source, _execution(base, 0))
    assert record.harness_status == "OUTPUT_INVALID"
    verdict = r2.judge_case(base, _manifest(base, source, baseline=score))
    assert verdict.hard == "FAIL"
    assert verdict.reasons[0].startswith("OUTPUT_INVALID")
    assert r2.stop_status(record, verdict, _case("primary")) == "STOPPED"


def test_measurement_failure_is_not_h_fail(tmp_path: Path) -> None:
    base, source, score = _solved_case(tmp_path)
    _record(base, source, _execution(base, 0, measured=False))
    verdict = r2.judge_case(base, _manifest(base, source, baseline=score))
    assert verdict.hard == "NOT_APPLICABLE" and verdict.performance == "INCOMPLETE"


def test_input_changed_after_capture_is_never_spawned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review F4: v1's last pre-spawn hash check is kept."""
    source, _, _ = _solve(tmp_path / "src", r2.policy04_smoke_input())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    original = r2.expected_versions

    def mutate(problem: Any) -> tuple[str, str]:
        source.write_text(source.read_text() + " ")
        return original(problem)

    def never(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("spawned after the input changed")

    monkeypatch.setattr(v1, "_runtime_identity", lambda **kwargs: {})
    monkeypatch.setattr(r2, "expected_versions", mutate)
    monkeypatch.setattr(v1, "supervise", never)
    record = r2.run_cli_once(
        python=Path(sys.executable),
        input_path=source,
        run_dir=tmp_path / "run",
        preflight_dir=tmp_path / "preflight",
        lock_path=ROOT / "uv.lock",
        input_sha256=digest,
        limits=v1.RunLimits(watchdog_seconds=15.0, max_resident_bytes=256 * 1024**2),
        options=r2.SolveOptions(time_limit_seconds=10.0),
    )
    assert record.harness_status == "ENVIRONMENT_BLOCKED"
    assert record.output.diagnostics == ("INPUT_CHANGED_BEFORE_SPAWN",)


def test_bundle_verification_is_guarded_and_bounded(tmp_path: Path) -> None:
    """Review F5: installed interpreter, import guard and v1-style peak RSS condition."""
    argv = r2.bundle_verification_argv(Path("/venv/bin/python"), tmp_path / "bundle")
    assert argv[:3] == ("/venv/bin/python", "-I", "-c")
    assert "import_guard(scoring=False)" in argv[3]
    ok = _execution(tmp_path, 0)
    (tmp_path / "stdout.json").write_text("BUNDLE_VERIFIED\n")
    assert r2.bundle_verification_passed(ok)
    big = _execution(tmp_path, 0, rss_kib=2 * 1024**2 + 1)
    assert not r2.bundle_verification_passed(big)
    assert not r2.bundle_verification_passed(_execution(tmp_path, 0, measured=False))
    (tmp_path / "stdout.json").write_text("other\n")
    assert not r2.bundle_verification_passed(ok)


def test_guarded_bundle_script_runs(tmp_path: Path) -> None:
    argv = r2.bundle_verification_argv(Path(sys.executable), tmp_path / "missing")
    done = subprocess.run(list(argv), capture_output=True, text=True, cwd=tmp_path)
    # A missing bundle fails inside verify_bundle, after the guarded import succeeded.
    assert done.returncode != 0 and "DatasetGenerationError" in done.stderr


def test_preflight_verifies_bundle_with_installed_solver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from benchmarks import phase2a_preflight as pf

    calls: dict[str, list[str]] = {}

    def fake_run(argv: list[str], log: Path, *, timeout: float = 300) -> str:
        calls[log.name] = argv
        if log.name.startswith("identity-"):
            return json.dumps({"git_commit": "c", "core_tree": "t"})
        return ""

    wheel = tmp_path / "core.whl"
    wheel.write_bytes(b"wheel")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "manifest.json").write_text("{}")
    monkeypatch.setattr(pf, "checked_run", fake_run)
    monkeypatch.setattr(r2, "run_policy04_smoke", lambda *a, **k: {"status": "PASS"})
    monkeypatch.setattr(sys, "platform", "linux")
    out = tmp_path / "preflight"
    r2.preflight(out, bundle, wheel, hashlib.sha256(b"wheel").hexdigest())
    argv = calls["bundle-verification"]
    assert argv[0] == str(out / "venv-solver" / "bin/python")
    assert "import_guard(scoring=False)" in argv[3]
