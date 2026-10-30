"""S03 bound helper: hand-calculated intervals, fallbacks and unchanged error paths."""

from dataclasses import replace
from typing import Any

import pytest

from tkb_core.constraints.s03_bounds import (
    BoundInterval,
    S03Bounds,
    S03BoundsDecision,
    TeacherDayBound,
    derive_s03_bounds,
)
from tkb_core.constraints.soft import compile_soft
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.errors import CoreError
from tkb_core.preprocessing.feasibility import Placement, PreparedProblem, prepare
from tkb_core.solver.cp_sat import solve
from tkb_core.solver.model_builder import build_model


def _slot(day: int, period: int, session: str = "AM") -> dict[str, Any]:
    return {"id": f"{day}-{session}-{period}", "day": day, "session": session, "period": period}


def _req(
    rid: str, teacher: str, blocks: list[int], cls: str = "c1", **extra: Any
) -> dict[str, Any]:
    return {
        "id": rid,
        "class_ids": [cls],
        "teacher_ids": [teacher],
        "subject_id": "sub",
        "periods_per_cycle": sum(blocks),
        "block_durations": blocks,
        **extra,
    }


def _data(
    slots: list[dict[str, Any]],
    reqs: list[dict[str, Any]],
    *,
    teachers: list[Any] | None = None,
    locks: list[dict[str, Any]] | None = None,
    rooms: list[dict[str, Any]] | None = None,
    limit: int = 1,
    rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if rules is None:
        rules = [
            {
                "id": "s03",
                "code": "TEACHER_MAX_PERIODS_PER_DAY",
                "parameters": {"limit": limit},
                "weight": 3,
                "priority": 1,
            }
        ]
    return {
        "schema_version": "1.1",
        "school": {"school_id": "demo", "academic_year": "demo", "term": "demo"},
        "time_slots": slots,
        "classes": [{"id": "c1", "size": 20}, {"id": "c2", "size": 20}],
        "teachers": [t if isinstance(t, dict) else {"id": t} for t in (teachers or ["t", "u"])],
        "subjects": [{"id": "sub"}],
        "rooms": rooms or [],
        "manage_rooms": bool(rooms),
        "teaching_requirements": reqs,
        "locked_assignments": locks or [],
        "constraint_config": {"policy_version": "0.1", "hard": [], "soft": rules},
    }


def _prepared(data: dict[str, Any]) -> PreparedProblem:
    return prepare(ScheduleInput.model_validate(data))


def _sparse() -> dict[str, Any]:
    """Teacher t: three singles, unavailable on day 11; calendar days 11, 2, 7."""
    slots = [_slot(11, 1), _slot(2, 1), _slot(7, 1), _slot(2, 2), _slot(7, 2), _slot(11, 2)]
    t = {"id": "t", "available_slot_ids": ["2-AM-1", "2-AM-2", "7-AM-1", "7-AM-2"]}
    return _data(slots, [_req("r1", "t", [1, 1, 1])], teachers=[t, "u"])


def _by_day(bounds: S03Bounds, teacher: str) -> dict[int, TeacherDayBound]:
    return {b.day: b for b in bounds.days if b.teacher_id == teacher}


def _derive(data: dict[str, Any], teachers: set[str], limit: int = 1) -> S03BoundsDecision:
    return derive_s03_bounds(_prepared(data), frozenset(teachers), limit)


def test_r01_dynamic_days_and_order_invariance() -> None:
    decision = _derive(_sparse(), {"t"})
    assert decision.reason is None and decision.bounds is not None
    days = _by_day(decision.bounds, "t")
    assert sorted(days) == [2, 7, 11]
    assert days[2].load == days[7].load == BoundInterval(1, 2)
    assert days[11].load == days[11].excess == BoundInterval(0, 0)
    assert days[2].excess == BoundInterval(0, 1)
    assert decision.bounds.raw == BoundInterval(1, 1)
    reordered = _sparse()
    reordered["time_slots"].reverse()
    reordered["teachers"][0]["available_slot_ids"].reverse()
    assert _derive(reordered, {"t"}) == decision


def test_r02_absent_day_and_zero_demand_teacher() -> None:
    decision = _derive(_sparse(), {"t", "u"})
    assert decision.bounds is not None
    for bound in _by_day(decision.bounds, "u").values():
        assert bound.load == bound.excess == BoundInterval(0, 0)
    assert decision.bounds.raw == BoundInterval(1, 1)
    prepared = _prepared(_sparse())
    built = build_model(prepared)
    compile_soft(prepared, built)
    names = [v.name for v in built.model.proto.variables if v.name.startswith("excess_")]
    assert sorted(names) == ["excess_s03_('t', 2, '')", "excess_s03_('t', 7, '')"]


def test_r03_empty_calendar_and_demand() -> None:
    data = _data([], [])
    decision = _derive(data, {"t", "u"})
    assert decision == S03BoundsDecision(S03Bounds((), BoundInterval(0, 0)), None)
    result = solve(ScheduleInput.model_validate(data))
    assert result.status == "FEASIBLE" and not result.metadata.solver_executed
    assert result.diagnostics[0].code == "EMPTY_PROBLEM"


def test_r04_scope_sums_per_teacher() -> None:
    data = _sparse()
    data["teachers"].append({"id": "v"})
    data["teachers"][1]["available_slot_ids"] = ["2-AM-1", "2-AM-2"]
    data["teaching_requirements"].append(_req("r2", "u", [1, 1], cls="c2"))
    single_t = _derive(data, {"t"})
    single_u = _derive(data, {"u"})
    pair = _derive(data, {"t", "u"})
    everyone = _derive(data, {"t", "u", "v"})
    assert single_t.bounds is not None and single_u.bounds is not None
    assert single_t.bounds.raw == BoundInterval(1, 1)
    assert single_u.bounds.raw == BoundInterval(1, 1)
    assert _by_day(single_u.bounds, "u")[2].load == BoundInterval(2, 2)
    assert pair.bounds is not None and everyone.bounds is not None
    assert pair.bounds.raw == everyone.bounds.raw == BoundInterval(2, 2)


def test_r05_overlapping_rules_and_disabled_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    rule = {"code": "TEACHER_MAX_PERIODS_PER_DAY", "parameters": {"limit": 1}, "weight": 1}
    overlapping = _sparse()
    overlapping["constraint_config"]["soft"] = [
        {**rule, "id": "a", "priority": 1},
        {**rule, "id": "b", "priority": 2, "scope": {"teacher_ids": ["t"]}},
    ]
    with pytest.raises(CoreError) as err:
        _prepared(overlapping)
    assert err.value.diagnostics[0].code == "OVERLAPPING_RULES"

    def forbidden(*args: Any) -> S03BoundsDecision:
        raise AssertionError("disabled rule must not reach the bound helper")

    monkeypatch.setattr("tkb_core.constraints.soft.derive_s03_bounds", forbidden)
    disabled = _sparse()
    disabled["constraint_config"]["soft"] = [{**rule, "id": "a", "priority": 1, "enabled": False}]
    prepared = _prepared(disabled)
    assert compile_soft(prepared, build_model(prepared)).rules == ()


def test_r06_timed_overlap_counts_slot_ids() -> None:
    slots = [
        {"id": "a1", "day": 2, "session": "A", "period": 1, "start_minute": 0, "end_minute": 45},
        {"id": "a2", "day": 2, "session": "A", "period": 2, "start_minute": 45, "end_minute": 90},
        {"id": "b1", "day": 2, "session": "B", "period": 1, "start_minute": 30, "end_minute": 75},
    ]
    decision = _derive(_data(slots, [_req("r1", "t", [1, 1])]), {"t"})
    assert decision.bounds is not None
    assert _by_day(decision.bounds, "t")[2].load == BoundInterval(2, 3)


@pytest.mark.parametrize(
    "minutes,code",
    [([(0, 45), None], "MIXED_TIMELINE"), ([(0, 45), (30, 60)], "TIMELINE_ORDER")],
)
def test_r07_timeline_errors_unchanged(minutes: list[tuple[int, int] | None], code: str) -> None:
    slots = [_slot(2, 1), _slot(2, 2)]
    for slot, span in zip(slots, minutes, strict=True):
        if span is not None:
            slot["start_minute"], slot["end_minute"] = span
    with pytest.raises(CoreError) as err:
        _prepared(_data(slots, [_req("r1", "t", [1])]))
    assert err.value.diagnostics[0].code == code


def test_r08_room_alternatives_do_not_multiply_union() -> None:
    rooms = [{"id": "R1", "capacity": 30}, {"id": "R2", "capacity": 30}]
    data = _data([_slot(2, 1)], [_req("r1", "t", [1], room_required=True)], rooms=rooms)
    prepared = _prepared(data)
    assert len(prepared.domains["r1::1"]) == 2
    decision = derive_s03_bounds(prepared, frozenset({"t"}), 0)
    assert decision.bounds is not None
    assert _by_day(decision.bounds, "t")[2].load == BoundInterval(1, 1)


@pytest.mark.parametrize(
    "lock,lower",
    [
        (None, 0),
        ({"slot_id": "2-AM-1"}, 1),
        ({"slot_id": "2-AM-1", "room_id": "R1"}, 1),
        ({"room_id": "R1"}, 0),
    ],
)
def test_r09_only_explicit_time_locks_fix_load(lock: dict[str, str] | None, lower: int) -> None:
    rooms = [{"id": "R1", "capacity": 30}, {"id": "R2", "capacity": 30}]
    slots = [_slot(d, p) for d in (2, 7) for p in (1, 2, 3)]
    locks = [] if lock is None else [{"occurrence_id": "r1::1", **lock}]
    data = _data(slots, [_req("r1", "t", [1, 1])], locks=locks, rooms=rooms)
    decision = _derive(data, {"t"})
    assert decision.bounds is not None
    assert _by_day(decision.bounds, "t")[2].load.lower == lower
    assert _by_day(decision.bounds, "t")[7].load.lower == 0


def test_r10_locked_double_contributes_two_and_bad_blocks_stay_errors() -> None:
    slots = [_slot(d, p) for d in (2, 7) for p in (1, 2, 3)]
    locks = [{"occurrence_id": "r1::1", "slot_id": "2-AM-1"}]
    decision = _derive(_data(slots, [_req("r1", "t", [2, 1])], locks=locks), {"t"})
    assert decision.bounds is not None
    assert _by_day(decision.bounds, "t")[2].load == BoundInterval(2, 3)
    gap = [
        {"id": "a1", "day": 2, "session": "A", "period": 1, "start_minute": 0, "end_minute": 45},
        {"id": "a2", "day": 2, "session": "A", "period": 2, "start_minute": 50, "end_minute": 95},
    ]
    boundary = [_slot(2, 1), _slot(2, 2), _slot(2, 1, "PM")]
    for bad_slots, start in ((gap, "a1"), (boundary, "2-AM-2")):
        lock = [{"occurrence_id": "r1::1", "slot_id": start}]
        with pytest.raises(CoreError) as err:
            _prepared(_data(bad_slots, [_req("r1", "t", [2])], locks=lock))
        assert err.value.diagnostics[0].code == "LOCK_CONFLICT"


@pytest.mark.parametrize(
    "requirement",
    [
        _req("r1", "t", [1], teacher_ids=["t", "u"]),
        _req("r1", "t", [3]),
    ],
)
def test_r11_unsupported_semantics_fallback(
    monkeypatch: pytest.MonkeyPatch, requirement: dict[str, Any]
) -> None:
    data = _data([_slot(2, p) for p in (1, 2, 3)], [requirement])
    assert solve(ScheduleInput.model_validate(data)).status == "UNSUPPORTED_FEATURE"
    monkeypatch.setattr("tkb_core.preprocessing.normalize.check_capabilities", lambda p: None)
    decision = _derive(data, {"t", "u"})
    assert decision == S03BoundsDecision(None, "UNVERIFIED_SEMANTICS")


@pytest.mark.parametrize(
    "limit,expected", [(0, BoundInterval(3, 3)), (1, BoundInterval(1, 1)), (5, BoundInterval(0, 0))]
)
def test_r12_limit_edges(limit: int, expected: BoundInterval) -> None:
    decision = _derive(_sparse(), {"t"}, limit)
    assert decision.bounds is not None
    assert decision.bounds.raw == expected
    excess = _by_day(decision.bounds, "t")[2].excess
    assert excess == BoundInterval(max(0, 1 - limit), max(0, 2 - limit))


def test_r12_fully_locked_fixed_interval_is_accepted() -> None:
    locks = [
        {"occurrence_id": "r1::1", "slot_id": "2-AM-1"},
        {"occurrence_id": "r1::2", "slot_id": "7-AM-1"},
    ]
    slots = [_slot(d, p) for d in (2, 7) for p in (1, 2)]
    data = _data(slots, [_req("r1", "t", [1, 1])], locks=locks, limit=0)
    decision = _derive(data, {"t"}, 0)
    assert decision.bounds is not None
    for day in (2, 7):
        bound = _by_day(decision.bounds, "t")[day]
        assert bound.load == bound.excess == BoundInterval(1, 1)
    assert decision.bounds.raw == BoundInterval(2, 2)
    prepared = _prepared(data)
    built = build_model(prepared)
    compiled = compile_soft(prepared, built)
    built.model.minimize(compiled.tiers[1])
    assert not built.model.validate()


def _two_singles() -> PreparedProblem:
    slots = [_slot(2, 1), _slot(2, 2), _slot(7, 1)]
    locks = [{"occurrence_id": "r1::2", "slot_id": "7-AM-1"}]
    return _prepared(_data(slots, [_req("r1", "t", [1, 1])], locks=locks))


def test_r13_incomplete_inconsistent_and_lock_domain_fallbacks() -> None:
    base = _two_singles()
    teachers = frozenset({"t"})
    missing = replace(base, domains={"r1::1": base.domains["r1::1"]})
    assert derive_s03_bounds(missing, teachers, 1) == S03BoundsDecision(
        None, "INCOMPLETE_PREPARED_DATA"
    )
    unknown_slot = (Placement("ghost", ("ghost",), None, (0,)),)
    dangling = replace(base, domains={**base.domains, "r1::1": unknown_slot})
    assert derive_s03_bounds(dangling, teachers, 1) == S03BoundsDecision(
        None, "INCOMPLETE_PREPARED_DATA"
    )
    unlocked = replace(base, domains={**base.domains, "r1::2": base.domains["r1::1"]})
    assert derive_s03_bounds(unlocked, teachers, 1) == S03BoundsDecision(
        None, "UNVERIFIED_SEMANTICS"
    )
    split = (Placement("2-AM-1", ("2-AM-1", "7-AM-1"), None, (0, 2)),)
    cross_day = replace(base, domains={**base.domains, "r1::1": split})
    assert derive_s03_bounds(cross_day, teachers, 1) == S03BoundsDecision(
        None, "UNVERIFIED_SEMANTICS"
    )


def test_r13_conservation_violation_is_inconsistent() -> None:
    slots = [_slot(2, 1), _slot(2, 2)]
    base = _prepared(_data(slots, [_req("r1", "t", [1, 1])]))
    same_slot = (base.domains["r1::1"][0],)
    crowded = replace(base, domains={"r1::1": same_slot, "r1::2": same_slot})
    assert derive_s03_bounds(crowded, frozenset({"t"}), 1) == S03BoundsDecision(
        None, "INCONSISTENT_BOUNDS"
    )


def test_r13_compiler_fallback_is_atomic(monkeypatch: pytest.MonkeyPatch) -> None:
    slots = [_slot(2, 1), _slot(2, 2)]
    base = _prepared(_data(slots, [_req("r1", "t", [1, 1])]))
    same_slot = (base.domains["r1::1"][0],)
    crowded = replace(base, domains={"r1::1": same_slot, "r1::2": same_slot})
    production = build_model(crowded)
    compile_soft(crowded, production)
    monkeypatch.setattr(
        "tkb_core.constraints.soft.derive_s03_bounds",
        lambda *a: S03BoundsDecision(None, "TEST_BASELINE"),
    )
    baseline = build_model(crowded)
    compile_soft(crowded, baseline)
    assert str(production.model.proto) == str(baseline.model.proto)

    sparse = _prepared(_sparse())
    disjoint = S03Bounds(
        (
            TeacherDayBound("t", 2, BoundInterval(1, 2), BoundInterval(0, 1)),
            TeacherDayBound("t", 7, BoundInterval(1, 2), BoundInterval(5, 6)),
            TeacherDayBound("t", 11, BoundInterval(0, 0), BoundInterval(0, 0)),
        ),
        BoundInterval(1, 1),
    )
    monkeypatch.setattr(
        "tkb_core.constraints.soft.derive_s03_bounds",
        lambda *a: S03BoundsDecision(disjoint, None),
    )
    staged = build_model(sparse)
    compile_soft(sparse, staged)
    monkeypatch.setattr(
        "tkb_core.constraints.soft.derive_s03_bounds",
        lambda *a: S03BoundsDecision(None, "TEST_BASELINE"),
    )
    untouched = build_model(sparse)
    compile_soft(sparse, untouched)
    assert str(staged.model.proto) == str(untouched.model.proto)


def test_r14_unsafe_integer_range_and_existing_objective_guard() -> None:
    prepared = _prepared(_sparse())
    assert derive_s03_bounds(prepared, frozenset({"t"}), 2**63) == S03BoundsDecision(
        None, "UNSAFE_INTEGER_RANGE"
    )
    data = _sparse()
    data["constraint_config"]["soft"][0].update(weight=2**53, parameters={"limit": 0})
    prepared = _prepared(data)
    with pytest.raises(CoreError) as err:
        compile_soft(prepared, build_model(prepared))
    assert err.value.diagnostics[0].code == "OBJECTIVE_RANGE"
