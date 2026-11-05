"""Exact CP-SAT expressions for policy 0.4 gap and free-time preferences (S08-S11).

Every auxiliary variable is fixed by equalities, so raw values are exact even for tiers
that are never optimized. The independent evaluator deliberately shares no code here.
"""

from collections import defaultdict

from ortools.sat.python import cp_model

from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ConstraintConfigV11, TimeSlot
from tkb_core.domain.rule_parameters import (
    FreeTimeParameters,
    GapRunParameters,
    SinglePeriodParameters,
    TotalGapsParameters,
)
from tkb_core.preprocessing.feasibility import PreparedProblem
from tkb_core.solver.model_builder import BuiltModel

GapParameters = TotalGapsParameters | GapRunParameters | FreeTimeParameters | SinglePeriodParameters
Lit = cp_model.IntVar | int
MAX_INTEGER = 2**63 - 1


def _range(value: int) -> None:
    if not 0 <= value <= MAX_INTEGER:
        raise CoreError(
            "INPUT_INVALID", "OBJECTIVE_RANGE", "Objective exceeds exact integer limits"
        )


def _or(model: cp_model.CpModel, items: list[Lit], name: str) -> Lit:
    """Boolean OR of 0/1 literals; constant zeros vanish, a single literal is reused."""
    live = [x for x in items if not (isinstance(x, int) and x == 0)]
    if not live:
        return 0
    if len(live) == 1:
        return live[0]
    result = model.new_bool_var(name)
    model.add_max_equality(result, live)
    return result


def compile_gap_rule(
    prepared: PreparedProblem,
    built: BuiltModel,
    rule_id: str,
    params: GapParameters,
    teachers: set[str],
) -> tuple[cp_model.IntVar, int]:
    """Return the exact raw-penalty variable of one S08-S11 rule and its upper bound."""
    problem = prepared.normalized.problem
    model = built.model
    slots = {s.id: s for s in problem.time_slots}
    reqs = {r.id: r for r in problem.teaching_requirements}
    occupied: dict[str, set[str]] = defaultdict(set)
    config = problem.constraint_config
    if isinstance(config, ConstraintConfigV11):
        for entry in config.occupied_work:
            occupied[entry.teacher_id].update(entry.slot_ids)
    calendar: dict[tuple[int, str], list[TimeSlot]] = defaultdict(list)
    for slot in sorted(problem.time_slots, key=lambda x: (x.day, x.session, x.period)):
        calendar[slot.day, slot.session].append(slot)
    # Teacher coverage of each slot, and block starts per (teacher, day, session).
    cover: dict[tuple[str, str], list[cp_model.IntVar]] = defaultdict(list)
    starts: dict[tuple[str, int, str], list[tuple[cp_model.IntVar, int]]] = defaultdict(list)
    for occurrence in prepared.normalized.occurrences:
        teacher = reqs[occurrence.requirement_id].teacher_ids[0]
        if teacher not in teachers:
            continue
        for placement, var in zip(
            prepared.domains[occurrence.id], built.variables[occurrence.id], strict=True
        ):
            for slot_id in placement.slot_ids:
                cover[teacher, slot_id].append(var)
            start = slots[placement.start_slot_id]
            starts[teacher, start.day, start.session].append((var, len(placement.slot_ids)))
    costs: list[Lit] = []
    bound = 0
    tag = f"{rule_id}"
    for t_index, teacher in enumerate(sorted(teachers)):
        if isinstance(params, FreeTimeParameters):
            groups: dict[object, list[TimeSlot]] = defaultdict(list)
            for (day, session), session_slots in calendar.items():
                key = day if params.unit == "day" else (day, session)
                groups[key].extend(session_slots)
            free_terms: list[cp_model.LinearExpr | int] = []
            for g_index, group in enumerate(groups.values()):
                if not any(x.can_teach for x in group):
                    continue  # not an eligible day/session
                if any(x.id in occupied[teacher] for x in group):
                    free_terms.append(0)
                    continue
                busy = _or(
                    model,
                    [v for x in group for v in cover[teacher, x.id]],
                    f"busy_{tag}_{t_index}_{g_index}",
                )
                free_terms.append(1 - busy)
            _range(params.target + len(free_terms))
            short = model.new_int_var(0, params.target, f"short_{tag}_{t_index}")
            model.add_max_equality(short, [0, params.target - sum(free_terms)])
            costs.append(short)
            bound += params.target
            continue
        for b_index, ((day, session), session_slots) in enumerate(calendar.items()):
            if session not in params.session_ids:
                continue
            if isinstance(params, SinglePeriodParameters):
                terms = starts.get((teacher, day, session), [])
                if not terms:
                    continue
                load = sum(n * v for v, n in terms)
                single = model.new_bool_var(f"single_{tag}_{t_index}_{b_index}")
                model.add(load == 1).only_enforce_if(single)
                model.add(load != 1).only_enforce_if(~single)
                costs.append(single)
                bound += 1
                continue
            if not any(cover[teacher, x.id] for x in session_slots):
                continue
            m = len(session_slots)
            teach: list[Lit] = []
            for i, slot in enumerate(session_slots):
                terms_i = cover[teacher, slot.id]
                if not terms_i:
                    teach.append(0)
                    continue
                var = model.new_bool_var(f"teach_{tag}_{t_index}_{b_index}_{i}")
                model.add(var == sum(terms_i))  # at most one by teacher occupancy
                teach.append(var)
            before: list[Lit] = [0]
            for i in range(1, m):
                before.append(
                    _or(model, [before[i - 1], teach[i - 1]], f"bf_{tag}_{t_index}_{b_index}_{i}")
                )
            after: list[Lit] = [0] * m
            for i in range(m - 2, -1, -1):
                after[i] = _or(
                    model, [after[i + 1], teach[i + 1]], f"af_{tag}_{t_index}_{b_index}_{i}"
                )
            idle: list[Lit] = []
            for i, slot in enumerate(session_slots):
                eligible = slot.can_teach and slot.id not in occupied[teacher]
                if not eligible or isinstance(before[i], int) or isinstance(after[i], int):
                    idle.append(0)
                    continue
                gap = model.new_bool_var(f"idle_{tag}_{t_index}_{b_index}_{i}")
                # gap = before AND after AND NOT teach, as exact Boolean equalities.
                model.add(gap <= before[i])
                model.add(gap <= after[i])
                model.add(gap <= 1 - teach[i])
                model.add(gap >= before[i] + after[i] - teach[i] - 1)
                idle.append(gap)
            if isinstance(params, TotalGapsParameters):
                costs.extend(idle)
                bound += max(0, m - 2)
                continue
            _range(params.limit + m)
            runs: list[Lit] = []
            previous: Lit = 0
            for i, gap_i in enumerate(idle):
                if isinstance(gap_i, int):
                    previous = 0  # a non-idle slot cuts the run
                    continue
                run = model.new_int_var(0, m, f"run_{tag}_{t_index}_{b_index}_{i}")
                model.add(run <= m * gap_i)
                model.add(run <= previous + 1)
                model.add(run >= previous + 1 - m * (1 - gap_i))
                runs.append(run)
                previous = run
            if not runs:
                continue
            longest = model.new_int_var(0, m, f"longest_{tag}_{t_index}_{b_index}")
            model.add_max_equality(longest, [0, *runs])
            excess = model.new_int_var(0, max(0, m - params.limit), f"ex_{tag}_{t_index}_{b_index}")
            model.add_max_equality(excess, [0, longest - params.limit])
            costs.append(excess)
            bound += max(0, m - params.limit)
    _range(bound)
    raw = model.new_int_var(0, bound, f"raw_{tag}")
    model.add(raw == sum(costs))
    return raw, bound
