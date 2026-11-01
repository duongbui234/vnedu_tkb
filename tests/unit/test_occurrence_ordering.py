"""Optional ordering must preserve domains, locks and unsupported/legacy behavior."""

from dataclasses import replace
from math import isqrt
from typing import Any

import pytest

from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.models import ConstraintConfigV11, HardConstraintConfigV11
from tkb_core.preprocessing.feasibility import prepare
from tkb_core.solver import model_builder
from tkb_core.solver.model_builder import build_model


def test_ordering_adds_only_adjacent_rows_without_mutation(ordering_case: dict[str, Any]) -> None:
    source = ScheduleInput.model_validate(ordering_case)
    prepared = prepare(source)
    before = source.model_dump_json()
    domain_snapshot = dict(prepared.domains)
    plain = build_model(prepared)
    ordered = build_model(prepared, order_interchangeable=True)
    assert len(ordered.model.proto.constraints) == len(plain.model.proto.constraints) + 2
    assert [str(v) for v in ordered.model.proto.variables] == [
        str(v) for v in plain.model.proto.variables
    ]
    assert [str(c) for c in list(ordered.model.proto.constraints)[:-2]] == [
        str(c) for c in plain.model.proto.constraints
    ]
    assert all(c.has_linear() for c in list(ordered.model.proto.constraints)[-2:])
    assert ordered.model.validate() == ""
    assert source.model_dump_json() == before and prepared.domains == domain_snapshot


@pytest.mark.parametrize(
    "lock",
    [
        {"slot_id": "1-AM-2"},
        {"room_id": "opaque-room"},
        {"slot_id": "1-AM-2", "room_id": "opaque-room"},
    ],
)
def test_every_locked_member_is_excluded(
    ordering_case: dict[str, Any], lock: dict[str, str]
) -> None:
    ordering_case["manage_rooms"] = True
    ordering_case["classes"][0]["size"] = 10
    ordering_case["rooms"] = [{"id": "opaque-room", "capacity": 20}]
    ordering_case["teaching_requirements"][0]["room_required"] = True
    ordering_case["locked_assignments"] = [{"occurrence_id": "r::2", **lock}]
    prepared = prepare(ScheduleInput.model_validate(ordering_case))
    plain = build_model(prepared)
    ordered = build_model(prepared, order_interchangeable=True)
    assert len(ordered.model.proto.constraints) == len(plain.model.proto.constraints) + 1
    locked_vars = {v.index for v in ordered.variables["r::2"]}
    assert not locked_vars.intersection(list(ordered.model.proto.constraints)[-1].linear.vars)


@pytest.mark.parametrize(
    "difference", ["order", "tokens", "footprint", "room", "duration", "empty", "singleton"]
)
def test_non_equivalent_domains_or_durations_not_grouped(
    ordering_case: dict[str, Any], difference: str
) -> None:
    ordering_case["teaching_requirements"][0].update(periods_per_cycle=2, block_durations=[1, 1])
    prepared = prepare(ScheduleInput.model_validate(ordering_case))
    domains = dict(prepared.domains)
    if difference == "duration":
        occurrences = prepared.normalized.occurrences
        prepared = replace(
            prepared,
            normalized=replace(
                prepared.normalized,
                occurrences=(occurrences[0], occurrences[1].model_copy(update={"duration": 2})),
            ),
        )
    elif difference in ("empty", "singleton"):
        domains = {oid: ps[: 0 if difference == "empty" else 1] for oid, ps in domains.items()}
    elif difference == "order":
        domains["r::2"] = tuple(reversed(domains["r::2"]))
    else:
        first, *rest = domains["r::2"]
        kwargs: dict[str, Any] = {
            "tokens": {"tokens": (999,)},
            "footprint": {"slot_ids": ("different-footprint",)},
            "room": {"room_id": "different-room"},
        }[difference]
        domains["r::2"] = (replace(first, **kwargs), *rest)
    prepared = replace(prepared, domains=domains)
    assert str(build_model(prepared).model.proto) == str(
        build_model(prepared, order_interchangeable=True).model.proto
    )


def test_equal_resources_across_requirements_not_grouped(ordering_case: dict[str, Any]) -> None:
    req = ordering_case["teaching_requirements"][0]
    req.update(periods_per_cycle=1, block_durations=[1])
    ordering_case["teaching_requirements"].append({**req, "id": "other-opaque-requirement"})
    p = prepare(ScheduleInput.model_validate(ordering_case))
    assert str(build_model(p).model.proto) == str(
        build_model(p, order_interchangeable=True).model.proto
    )


@pytest.mark.parametrize("scenario", ["legacy", "disabled", "none", "unknown", "hard"])
def test_ordering_not_enabled_for_other_semantics(
    ordering_case: dict[str, Any], scenario: str
) -> None:
    if scenario == "legacy":
        ordering_case.update(schema_version="1.0", constraint_config={"hard": [], "soft": []})
    elif scenario == "none":
        ordering_case["constraint_config"]["soft"] = []
    elif scenario == "disabled":
        for rule in ordering_case["constraint_config"]["soft"]:
            rule["enabled"] = False
    prepared = prepare(ScheduleInput.model_validate(ordering_case))
    if scenario == "unknown":
        # Deliberately bypass boundary validation to exercise the conservative helper guard.
        prepared.normalized.problem.constraint_config.soft[0].code = "future_identity_rule"
    if scenario == "hard":
        config = prepared.normalized.problem.constraint_config
        assert isinstance(config, ConstraintConfigV11)
        config.hard = (HardConstraintConfigV11(id="future-hard", code="future-hard"),)
    assert str(build_model(prepared).model.proto) == str(
        build_model(prepared, order_interchangeable=True).model.proto
    )


def test_rank_range_guard_skips_whole_group(
    ordering_case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    p = prepare(ScheduleInput.model_validate(ordering_case))
    monkeypatch.setattr(model_builder, "_MAX_LINEAR_ACTIVITY", 10)
    assert str(build_model(p).model.proto) == str(
        build_model(p, order_interchangeable=True).model.proto
    )


def test_rank_range_integer_boundaries_without_allocation() -> None:
    bound = 2**63 - 1
    last = (1 + isqrt(1 + 4 * bound)) // 2
    assert not model_builder._rank_range_safe(0)
    assert not model_builder._rank_range_safe(1)
    assert model_builder._rank_range_safe(2)
    assert model_builder._rank_range_safe(last)
    assert not model_builder._rank_range_safe(last + 1)


def test_ordinal_order_is_numeric_not_iteration_or_string_order(
    ordering_case: dict[str, Any],
) -> None:
    ordering_case["time_slots"] = [
        {"id": f"opaque-{i}", "day": 1, "session": "AM", "period": i} for i in range(1, 11)
    ]
    ordering_case["constraint_config"]["soft"][0]["parameters"]["slot_ids"] = ["opaque-1"]
    ordering_case["teaching_requirements"][0].update(periods_per_cycle=10, block_durations=[1] * 10)
    p = prepare(ScheduleInput.model_validate(ordering_case))
    p = replace(
        p, normalized=replace(p.normalized, occurrences=tuple(reversed(p.normalized.occurrences)))
    )
    plain = build_model(p)
    ordered = build_model(p, order_interchangeable=True)
    extra = list(ordered.model.proto.constraints)[len(plain.model.proto.constraints) :]
    assert len(extra) == 9
    values = {
        v.index: int(j == int(oid.rpartition("::")[2]) - 1)
        for oid, vs in ordered.variables.items()
        for j, v in enumerate(vs)
    }
    for row in extra:
        value = sum(values[v] * c for v, c in zip(row.linear.vars, row.linear.coeffs, strict=True))
        limits = list(row.linear.domain)
        assert limits[0] <= value <= limits[-1]
