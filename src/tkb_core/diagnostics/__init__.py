"""Phase 3B infeasibility diagnostics: a separate path; ``solve()``/``repair()`` never call it.

``explain_infeasibility`` needs OR-Tools and is imported lazily, so the group catalogue and
prechecks stay importable on their own.
"""

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "explain_infeasibility":
        from tkb_core.diagnostics.pipeline import explain_infeasibility

        return explain_infeasibility
    raise AttributeError(name)
