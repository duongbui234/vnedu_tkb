"""Resource occupancy indexed by symbolic slots or elementary physical-time segments."""

from collections import defaultdict

from ortools.sat.python import cp_model

from tkb_core.preprocessing.feasibility import PreparedProblem


def add_occupancy(
    model: cp_model.CpModel,
    prepared: PreparedProblem,
    variables: dict[str, tuple[cp_model.IntVar, ...]],
) -> None:
    """Add AtMostOne per resource/token; all slots of a block share its Boolean."""
    index: dict[tuple[str, str, int], list[cp_model.IntVar]] = defaultdict(list)
    requirements = {r.id: r for r in prepared.normalized.problem.teaching_requirements}
    for occurrence in prepared.normalized.occurrences:
        req = requirements[occurrence.requirement_id]
        for placement, variable in zip(
            prepared.domains[occurrence.id], variables[occurrence.id], strict=True
        ):
            resources = [("class", req.class_ids[0]), ("teacher", req.teacher_ids[0])]
            if placement.room_id is not None:
                resources.append(("room", placement.room_id))
            for kind, resource_id in resources:
                for token in placement.tokens:
                    index[kind, resource_id, token].append(variable)
    for choices in index.values():
        if len(choices) > 1:
            model.add_at_most_one(choices)
