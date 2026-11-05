"""Change-count terms for repair (Phase 3A, spec §2.3); imported only to execute CP-SAT.

``changed`` of a matched occurrence is ``1 - x[target]``, or the constant 1 when its previous
placement left the domain. The sum is linear in existing placement variables: no new
variables, pairs or big-M terms.
"""

from ortools.sat.python import cp_model

from tkb_core.contracts.repair import RepairRequest
from tkb_core.repair.matching import RepairMatching
from tkb_core.solver.model_builder import BuiltModel


def add_repair_terms(
    built: BuiltModel, matching: RepairMatching, request: RepairRequest
) -> cp_model.LinearExpr:
    """Add frozen placements and ``max_changes``; return the change-count expression."""
    kept = [built.variables[o][i] for o, i in sorted(matching.targets.items())]
    expression = cp_model.LinearExpr.weighted_sum(kept, [-1] * len(kept)) + (
        len(kept) + len(matching.forced)
    )
    for occurrence in sorted(matching.frozen):
        built.model.add(built.variables[occurrence][matching.targets[occurrence]] == 1)
    if request.max_changes is not None:
        built.model.add(expression <= request.max_changes)
    return expression


def add_previous_hint(built: BuiltModel, matching: RepairMatching) -> None:
    """Hint every matched occurrence with a feasible previous placement; nothing else."""
    for occurrence, index in sorted(matching.targets.items()):
        for i, variable in enumerate(built.variables[occurrence]):
            built.model.add_hint(variable, i == index)
