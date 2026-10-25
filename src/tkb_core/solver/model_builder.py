"""Sparse Boolean placement model, imported only for actual solver execution."""

from dataclasses import dataclass

from ortools.sat.python import cp_model

from tkb_core.constraints.hard import add_occupancy
from tkb_core.preprocessing.feasibility import PreparedProblem


@dataclass(frozen=True)
class BuiltModel:
    """CP-SAT model and its placement selection variables."""

    model: cp_model.CpModel
    variables: dict[str, tuple[cp_model.IntVar, ...]]


def build_model(prepared: PreparedProblem) -> BuiltModel:
    """ExactlyOne placement per occurrence plus shared-resource hard occupancy."""
    model = cp_model.CpModel()
    variables: dict[str, tuple[cp_model.IntVar, ...]] = {}
    for occurrence in prepared.normalized.occurrences:
        choices = tuple(
            model.new_bool_var(f"x_{len(variables)}_{i}")
            for i in range(len(prepared.domains[occurrence.id]))
        )
        model.add_exactly_one(choices)
        variables[occurrence.id] = choices
    add_occupancy(model, prepared, variables)
    return BuiltModel(model, variables)
