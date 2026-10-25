"""Expected boundary/preflight failures, with structured non-record diagnostics."""

from tkb_core.domain.enums import SolveStatus
from tkb_core.domain.models import Diagnostic


class CoreError(Exception):
    """A classified failure; UNKNOWN resource limits never claim infeasibility."""

    def __init__(
        self,
        status: SolveStatus | str,
        code: str,
        message: str,
        resource_ids: tuple[str, ...] = (),
        slot_ids: tuple[str, ...] = (),
        occurrence_ids: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.status = SolveStatus(status)
        self.diagnostics = (
            Diagnostic(
                code=code,
                message=message,
                resource_ids=resource_ids,
                slot_ids=slot_ids,
                occurrence_ids=occurrence_ids,
            ),
        )
