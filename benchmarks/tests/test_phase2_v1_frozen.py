"""v2 tooling must leave every v1 source byte-identical (plan G1).

`aggregate_linux._verify_frozen` rebuilds a historical plan and compares its recorded
`source_ids`; any edit to these files would make v1 evidence unverifiable. The digests are
those of commit 5d685f9 (before the v2 tooling was added).
"""

import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FROZEN_V1 = {
    "benchmarks/run_benchmarks.py": (
        "ee198681bafd1af6194e46e19853bce3f75e4b02b0c6fdf01e0d567dfdc6acc2"
    ),
    "benchmarks/generate_synthetic.py": (
        "8144a3fc0270a7f83812913e9040b74d233b1bd702856ff63f026d2079f56c93"
    ),
    "benchmarks/aggregate_linux.py": (
        "43940736abf4ca40dc5fd97c8318fc36d0aa8e6e29219a8898fd3112b2119e3d"
    ),
    "benchmarks/phase2a_preflight.py": (
        "7dead91b3223a05ba8b70276f09a84ede3bbe523427d08bda26903d21585c5ac"
    ),
    "benchmarks/native_trace.py": (
        "4f1b35d44fde9479bd2a2f565595f3a5318ce76ae61b69eaa93c2d7b62821939"
    ),
    "benchmarks/windows_runtime.py": (
        "73afa1e1c14a618ab55bc2256cae51cb896dfd7f2015209fc0f4b1d23461e766"
    ),
}


@pytest.mark.parametrize("path", sorted(FROZEN_V1))
def test_v1_tooling_is_byte_identical(path: str) -> None:
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == FROZEN_V1[path]


def test_v1_source_identity_is_what_v2_records() -> None:
    from benchmarks import run_benchmarks as v1
    from benchmarks import run_phase2 as r2

    old = v1._source_ids()
    new = r2.source_ids()
    assert new["controller_v1"] == old["controller"]
    assert new["generator_v1"] == old["generator"]
    assert new["native_trace"] == old["native_trace"]
    assert new["windows_runtime"] == old["windows_runtime"]
    assert new["lock"] == old["lock"]
