"""CP-SAT parameters of each stage search mode."""

from tkb_core.solver import objectives
from tkb_core.solver.options import SolveOptions

BASE = {
    "max_time_in_seconds": 7.5,
    "num_search_workers": 1,
    "random_seed": 42,
    "relative_gap_limit": 0.0,
    "absolute_gap_limit": 0.0,
}


def _params(search: objectives.TierSearch, *, fix_hint: bool = False, workers: int = 1) -> dict:
    options = SolveOptions(num_workers=workers)
    return objectives._stage_parameters(options, 7.5, fix_hint=fix_hint, search=search)


def test_default_keeps_previous_settings() -> None:
    assert _params("default") == BASE
    assert _params("default", workers=4) == {**BASE, "num_search_workers": 4}


def test_fix_hint_only_adds_fixing() -> None:
    assert _params("default", fix_hint=True) == {
        **BASE,
        "fix_variables_to_their_hinted_value": True,
    }


def test_slice_caps_deterministic_time_without_interleaving() -> None:
    assert _params("slice") == {**BASE, "max_deterministic_time": 12.0}


def test_interleave_has_no_deterministic_cap() -> None:
    assert _params("interleave") == {**BASE, "interleave_search": True}
