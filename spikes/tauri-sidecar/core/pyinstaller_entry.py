"""PyInstaller entry point: the packaged tkb-core behaves exactly like `python -m tkb_core.cli`.

`tkb-core self-check` (spike only) imports the solver stack and prints versions, so a packaging
problem shows as a traceback instead of Core's generic SOLVER_NOT_INSTALLED.
"""

import sys


def self_check() -> int:
    import json
    import platform
    from importlib.metadata import version

    from ortools.sat.python import cp_model  # noqa: F401

    from tkb_core.solver.model_builder import build_model  # noqa: F401

    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "ortools": version("ortools"),
                "pydantic": version("pydantic"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["self-check"]:
        raise SystemExit(self_check())
    from tkb_core.cli import main

    raise SystemExit(main())
