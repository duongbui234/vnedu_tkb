"""Phase 3C controller: plan membership, budgets, two-stage seal inputs (Task 2).

Execution paths (supervision, journal, receipts) are exercised by the smoke run recorded in
the tooling report; these tests cover the deterministic, solver-free parts.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from benchmarks import generate_phase2 as g2
from benchmarks import generate_phase3c as g3
from benchmarks import run_benchmarks as v1
from benchmarks import run_phase3c as r3

ROOT = Path(__file__).resolve().parents[2]
# v2 tooling at f58f257 (plan Task 5): 3C imports it and must never edit it.
FROZEN_V2 = {
    "benchmarks/run_phase2.py": "0c580391034952bd30b0ae826e865b418e20cc9d5b732dcaef80bf9323526bef",
    "benchmarks/generate_phase2.py": (
        "233811025ba55fdec1c02e4e159e2979bb394dd792d05ab3a5c56679122cb1a0"
    ),
    "benchmarks/aggregate_phase2.py": (
        "e6db43a573b69b24239ada257f4ad168a5bdaeb2dd70e514d3c68dafcb08d36f"
    ),
}


@pytest.mark.parametrize(("path", "digest"), sorted(FROZEN_V2.items()))
def test_v2_tooling_is_unchanged(path: str, digest: str) -> None:
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest


@pytest.fixture(scope="module")
def bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A partial v2 bundle holding only the smoke datasets, written like write_bundle."""
    root = tmp_path_factory.mktemp("bundle")
    entries = []
    for ident in (*g3.base_dataset_ids(smoke=True), *g3.unsat_dataset_ids(smoke=True)):
        size, profile, seed, variant = ident.split("-")
        artifact = g2.generate_dataset(
            int(size[1:]), profile.upper(), int(seed[1:]), variant.upper()
        )
        dest = root / ident
        dest.mkdir()
        for name, data in g2._files(artifact).items():
            (dest / name).write_bytes(data)
        manifest = v1._json_bytes(artifact.manifest)
        (dest / "manifest.json").write_bytes(manifest)
        entries.append(
            g2.BundleEntry(dataset_id=ident, manifest_sha256=v1._sha(dest / "manifest.json"))
        )
    bundle = g2.BundleManifest(revision=g2._revision(), datasets=tuple(entries))
    (root / "manifest.json").write_bytes(v1._json_bytes(bundle))
    return root


def test_smoke_plan_membership_and_budgets(bundle: Path) -> None:
    plan = r3.build_plan(bundle, "phase3c-test", "machine", smoke=True)
    parts = [c.part for c in plan.cases]
    assert parts == ["S", "S", "X", "X"]
    assert [c.run_id for c in plan.cases] == [
        "S-c10-base-s101-hard",
        "S-c10-base-s101-soft",
        "X-c10-unsat_capacity-s101-soft-MODEL",
        "X-c10-unsat_capacity-s101-soft-FULL",
    ]
    assert all(c.time_limit_seconds == r3.SMOKE_BUDGET[0] for c in plan.cases)
    assert plan.cases[2].label == "UNSAT" and plan.cases[0].label == "BASELINE"


def test_full_plan_requires_full_membership(bundle: Path) -> None:
    smoke = r3.build_plan(bundle, "phase3c-test", "machine", smoke=True)
    with pytest.raises(ValidationError):
        r3.Plan3C.model_validate(smoke.model_dump() | {"smoke": False})


def test_case_budget_cannot_change(bundle: Path) -> None:
    case = r3.build_plan(bundle, "phase3c-test", "machine", smoke=True).cases[0]
    with pytest.raises(ValidationError):
        r3.Case3C.model_validate(case.model_dump() | {"time_limit_seconds": 30.0})
    with pytest.raises(ValidationError):
        r3.Case3C.model_validate(case.model_dump() | {"smoke": False})  # full budget differs
    with pytest.raises(ValidationError):
        r3.Case3C.model_validate(case.model_dump() | {"run_id": "S-other"})


def test_expected_r_membership_counts() -> None:
    sizes = {i: int(i.split("-")[0][1:]) for i in g3.base_dataset_ids()}
    full = r3.expected_r_ids(sizes, smoke=False)
    assert sum(i.startswith("R1-") for i in full) == 144
    assert sum(i.startswith("R2-") for i in full) == 48
    smoke = r3.expected_r_ids({i: 10 for i in g3.base_dataset_ids(smoke=True)}, smoke=True)
    assert smoke == ["R1-c10-base-s101-hard-N1-hint1", "R1-c10-base-s101-soft-N1-hint1"]


def _previous(bundle: Path, out: Path) -> dict[str, Path]:
    paths = {}
    for ident in g3.base_dataset_ids(smoke=True):
        witness = json.loads((bundle / ident / "witness.json").read_text())
        path = out / f"{ident}-previous.json"
        path.write_text(
            json.dumps({"schema_version": "1.0", "assignments": witness["assignments"]})
        )
        paths[ident] = path
    return paths


def test_derive_writes_hashed_inputs_and_requests(bundle: Path, tmp_path: Path) -> None:
    plan = r3.build_plan(bundle, "phase3c-test", "machine", smoke=True)
    previous = _previous(bundle, tmp_path)
    first = r3.derive_cases(plan, "a" * 64, previous, {}, tmp_path / "one")
    second = r3.derive_cases(plan, "a" * 64, previous, {}, tmp_path / "two")
    assert [c.run_id for c in first.cases] == r3.expected_r_ids(
        {i: 10 for i in previous}, smoke=True
    )
    for left, right in zip(first.cases, second.cases, strict=True):
        assert left.input_sha256 == right.input_sha256 == v1._sha(left.input_path)
        assert left.request_sha256 == v1._sha(left.request_path)  # type: ignore[arg-type]
        assert left.previous_sha256 == v1._sha(left.previous_path)  # type: ignore[arg-type]
        assert left.order == "BEFORE_QUALITY" and left.hint is True
        assert left.time_limit_seconds == r3.SMOKE_BUDGET[0]
    key = f"{first.cases[0].dataset_id}/N1"
    assert first.noise[key]["input_sha256"] == first.cases[0].input_sha256


def test_derive_records_exclusions(bundle: Path, tmp_path: Path) -> None:
    plan = r3.build_plan(bundle, "phase3c-test", "machine", smoke=True)
    previous = _previous(bundle, tmp_path)
    hard = g3.base_dataset_ids(smoke=True)[0]
    del previous[hard]
    derived = r3.derive_cases(plan, "a" * 64, previous, {hard: "S_NO_SCHEDULE"}, tmp_path / "d")
    assert derived.excluded == {hard: "S_NO_SCHEDULE"}
    assert all(c.dataset_id != hard for c in derived.cases)


def test_sealed_derived_rejects_unknown_rows(bundle: Path, tmp_path: Path) -> None:
    plan = r3.build_plan(bundle, "phase3c-test", "machine", smoke=True)
    derived = r3.derive_cases(plan, "a" * 64, _previous(bundle, tmp_path), {}, tmp_path / "d")
    data: dict[str, Any] = derived.model_dump()
    data["cases"] = data["cases"][:1]
    with pytest.raises(ValidationError):
        r3.Derived3C.model_validate(data)
