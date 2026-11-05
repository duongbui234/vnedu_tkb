"""Independent S05/S06 scoring from raw assignments (Phase 2C-1)."""

from typing import Any

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.validation.score_evaluator import evaluate_score


def _spread(k: int, requirements: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "id": "spread",
        "code": "SUBJECT_COMPONENT_DAY_SPREAD",
        "parameters": {"requirement_ids": requirements or ["r"], "min_day_gap": k},
        "priority": 1,
        "weight": 1,
        **extra,
    }


def _subject_day(limit: int, **extra: Any) -> dict[str, Any]:
    return {
        "id": "subject-day",
        "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY",
        "parameters": {"limit": limit},
        "priority": 1,
        "weight": 1,
        **extra,
    }


def _assign(occurrence: str, slot: str, cls: str = "c", teacher: str = "t") -> ScheduleAssignment:
    return ScheduleAssignment(
        occurrence_id=occurrence, slot_id=slot, class_ids=(cls,), teacher_ids=(teacher,)
    )


def _score(data: dict[str, Any], rules: list[dict[str, Any]], *assignments: Any) -> Any:
    data["constraint_config"]["soft"] = rules
    report = evaluate_score(ScheduleInput.model_validate(data), assignments)
    assert report.status == "OK", report.diagnostics
    assert report.schema_version == "1.1"
    return report


def test_spread_policy_example(dist_case: dict[str, Any]) -> None:
    # Components on days (1, 1, 3) with k=2: pairs give 2 + 0 + 0.
    report = _score(
        dist_case,
        [_spread(2)],
        _assign("r::1", "1-AM-1"),
        _assign("r::2", "1-PM-1"),
        _assign("r::3", "3-AM-1"),
    )
    (row,) = report.rules
    assert (row.unit, row.raw_penalty, report.tiers) == ("day_gap_shortfall", 2, (2, 0, 0))


def test_spread_counts_component_pairs_not_periods(dist_case: dict[str, Any]) -> None:
    # Split [2,1,1,1] = 4 components, 6 pairs. Days (1,2,3,3), k=3:
    # (1,2)=2 (1,3)=1 (1,3)=1 (2,3)=2 (2,3)=2 (3,3)=3 -> 11.
    dist_case["teaching_requirements"][0].update(periods_per_cycle=5, block_durations=[2, 1, 1, 1])
    report = _score(
        dist_case,
        [_spread(3)],
        _assign("r::1", "1-AM-1"),
        _assign("r::2", "2-AM-1"),
        _assign("r::3", "3-AM-1"),
        _assign("r::4", "3-PM-1"),
    )
    assert report.rules[0].raw_penalty == 11


def test_single_component_group_scores_zero(dist_case: dict[str, Any]) -> None:
    dist_case["teaching_requirements"][0].update(periods_per_cycle=2, block_durations=[2])
    report = _score(dist_case, [_spread(3)], _assign("r::1", "1-AM-1"))
    assert [r.raw_penalty for r in report.rules] == [0]


def test_group_spans_requirements_and_ignores_others(dist_case: dict[str, Any]) -> None:
    dist_case["classes"].append({"id": "c2"})
    dist_case["teaching_requirements"].append(
        {
            "id": "r2",
            "class_ids": ["c2"],
            "teacher_ids": ["t"],
            "subject_id": "sub",
            "periods_per_cycle": 1,
        }
    )
    dist_case["teaching_requirements"][0].update(periods_per_cycle=2, block_durations=[2])
    assignments = (_assign("r::1", "1-AM-1"), _assign("r2::1", "1-PM-1", cls="c2"))
    assert _score(dist_case, [_spread(1, ["r", "r2"])], *assignments).rules[0].raw_penalty == 1
    assert _score(dist_case, [_spread(1, ["r"])], *assignments).rules[0].raw_penalty == 0


def test_spread_uses_day_values_not_ranks(dist_case: dict[str, Any]) -> None:
    for slot in dist_case["time_slots"]:
        if slot["day"] == 3:
            slot["day"] = 5
            slot["id"] = slot["id"].replace("3-", "5-", 1)
    dist_case["teaching_requirements"][0].update(periods_per_cycle=2, block_durations=[1, 1])
    report = _score(dist_case, [_spread(3)], _assign("r::1", "2-AM-1"), _assign("r::2", "5-AM-1"))
    assert report.rules[0].raw_penalty == 0  # |5-2| = 3, although the days are adjacent ranks
    report = _score(dist_case, [_spread(4)], _assign("r::1", "2-AM-1"), _assign("r::2", "5-AM-1"))
    assert report.rules[0].raw_penalty == 1


def test_subject_day_counts_periods_across_sessions(dist_case: dict[str, Any]) -> None:
    schedule = (
        _assign("r::1", "1-AM-1"),  # double: 2 periods
        _assign("r::2", "1-PM-1"),
        _assign("r::3", "3-AM-1"),
    )
    assert _score(dist_case, [_subject_day(2)], *schedule).rules[0].raw_penalty == 1
    assert _score(dist_case, [_subject_day(0)], *schedule).rules[0].raw_penalty == 4
    assert _score(dist_case, [_subject_day(3)], *schedule).rules[0].raw_penalty == 0


def test_subject_day_scope_and_weight(dist_case: dict[str, Any]) -> None:
    dist_case["classes"].append({"id": "c2"})
    schedule = (_assign("r::1", "1-AM-1"), _assign("r::2", "1-PM-1"), _assign("r::3", "3-AM-1"))
    other = _subject_day(0, scope={"class_ids": ["c2"]})
    assert _score(dist_case, [other], *schedule).rules[0].raw_penalty == 0
    scoped = _subject_day(
        2, scope={"class_ids": ["c"], "subject_ids": ["sub"]}, weight=3, priority=2
    )
    report = _score(dist_case, [scoped], *schedule)
    assert (report.rules[0].weighted_penalty, report.tiers) == (3, (0, 3, 0))


def test_mixed_units_in_one_tier(dist_case: dict[str, Any]) -> None:
    report = _score(
        dist_case,
        [_spread(2), _subject_day(2)],
        _assign("r::1", "1-AM-1"),
        _assign("r::2", "1-PM-1"),
        _assign("r::3", "3-AM-1"),
    )
    units = {r.code: (r.unit, r.raw_penalty) for r in report.rules}
    assert units == {
        "SUBJECT_COMPONENT_DAY_SPREAD": ("day_gap_shortfall", 2),
        "CLASS_SUBJECT_MAX_PERIODS_PER_DAY": ("teaching_periods", 1),
    }
    assert report.tiers == (3, 0, 0)
