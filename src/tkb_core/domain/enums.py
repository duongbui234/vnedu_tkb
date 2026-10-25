"""Result states; NOT_RUN is a core state, not a CP-SAT solver status."""

from enum import StrEnum


class SolveStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    MODEL_INVALID = "MODEL_INVALID"
    INPUT_INVALID = "INPUT_INVALID"
    UNSUPPORTED_FEATURE = "UNSUPPORTED_FEATURE"
