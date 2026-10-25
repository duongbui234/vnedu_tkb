"""Revalidate caller data, guard allocations and expand stable occurrence IDs."""

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass

from tkb_core.contracts.capabilities import check_capabilities
from tkb_core.contracts.input import ScheduleInput
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import LessonOccurrence, TimeSlot
from tkb_core.solver.options import SolveOptions


def resource_limit() -> CoreError:
    """Return a classified operational limit, never a false infeasibility proof."""
    return CoreError("UNKNOWN", "RESOURCE_LIMIT", "Configured model resource limit exceeded")


@dataclass(frozen=True)
class NormalizedProblem:
    """Owned snapshot, ordered occurrences and elementary occupancy tokens."""

    problem: ScheduleInput
    fingerprint: str
    occurrences: tuple[LessonOccurrence, ...]
    slot_tokens: dict[str, tuple[int, ...]]
    timed: bool


def normalize(problem: ScheduleInput, options: SolveOptions | None = None) -> NormalizedProblem:
    """Copy/revalidate input and expand demands only after checking allocation limits."""
    options = SolveOptions() if options is None else options
    try:
        options = SolveOptions.model_validate(options.model_dump(warnings="error"))
        problem = ScheduleInput.model_validate(problem.model_dump(warnings="error"))
    except (ValueError, TypeError, AttributeError) as exc:
        raise CoreError(
            "INPUT_INVALID", "CONTRACT_INVALID", "Input/options failed revalidation"
        ) from exc
    check_capabilities(problem)
    if len(problem.time_slots) > options.max_slots:
        raise resource_limit()
    if sum(r.occurrence_count for r in problem.teaching_requirements) > options.max_occurrences:
        raise resource_limit()
    occurrences = tuple(
        LessonOccurrence(
            id=f"{r.id}::{i}",
            requirement_id=r.id,
            ordinal=i,
            duration=duration,
            source_reference=r.source_reference,
        )
        for r in sorted(problem.teaching_requirements, key=lambda r: r.id)
        for i, duration in enumerate(
            r.block_durations if r.block_durations is not None else (1,) * r.periods_per_cycle, 1
        )
    )
    slots = sorted(problem.time_slots, key=lambda s: (s.day, s.session, s.period))
    count_timed = sum(s.start_minute is not None for s in slots)
    if count_timed not in (0, len(slots)):
        raise CoreError(
            "INPUT_INVALID", "MIXED_TIMELINE", "All slots must use the same timeline mode"
        )
    timed = bool(slots and count_timed)
    tokens: dict[str, tuple[int, ...]] = {}
    if not timed:
        tokens = {s.id: (i,) for i, s in enumerate(slots)}
    else:
        by_session: dict[tuple[int, str], list[TimeSlot]] = defaultdict(list)
        by_day: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for slot in slots:
            assert slot.start_minute is not None and slot.end_minute is not None
            by_session[slot.day, slot.session].append(slot)
            by_day[slot.day].append((slot.start_minute, slot.end_minute))
        for sequence in by_session.values():
            for left, right in zip(sequence, sequence[1:]):
                assert left.end_minute is not None and right.start_minute is not None
                if left.end_minute > right.start_minute:
                    raise CoreError(
                        "INPUT_INVALID",
                        "TIMELINE_ORDER",
                        "Periods overlap or run backwards within a session",
                    )
        ranges = [
            (min(a for a, _ in times), max(b for _, b in times))
            for _, times in sorted(by_day.items())
        ]
        if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
            raise CoreError(
                "INPUT_INVALID", "TIMELINE_ORDER", "Day ranges must follow cycle-wide time order"
            )
        boundaries = sorted(
            {point for times in by_day.values() for span in times for point in span}
        )
        term_count = 0
        for slot in slots:
            assert slot.start_minute is not None and slot.end_minute is not None
            first = bisect_left(boundaries, slot.start_minute)
            last = bisect_left(boundaries, slot.end_minute)
            term_count += last - first
            if term_count > options.max_occupancy_terms:
                raise resource_limit()
            tokens[slot.id] = tuple(range(first, last))
    return NormalizedProblem(problem, problem.fingerprint(), occurrences, tokens, timed)
