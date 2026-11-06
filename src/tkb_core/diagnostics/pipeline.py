"""``explain_infeasibility()``: prechecks, then a CP-SAT core shrunk by deletion (spec §4, §6).

One shared wall-clock budget covers every solver call; each call receives what is left.
Workers are fixed to 1 and the seed comes from the request. A returned subset is one
conflict proved by CP-SAT, never the unique cause. Minimality is claimed only when every
member has a witness schedule that the independent validator accepts with exactly the other
members enforced. Witnesses are checked and discarded; the report carries no schedule.
"""

from importlib.metadata import version
from time import perf_counter
from typing import TYPE_CHECKING, Any

from tkb_core.contracts.diagnostics import (
    LIMITATIONS,
    Evidence,
    ExplainMetadata,
    ExplainOptions,
    GroupRef,
    InfeasibilityReport,
    PrecheckProof,
    ReportStatus,
    WitnessCheck,
)
from tkb_core.contracts.input import ScheduleInput
from tkb_core.diagnostics.domains import GroupKey, build_domains
from tkb_core.diagnostics.groups import enumerate_groups
from tkb_core.diagnostics.prechecks import run_prechecks
from tkb_core.domain.errors import CoreError
from tkb_core.domain.models import ScheduleAssignment
from tkb_core.preprocessing.normalize import normalize
from tkb_core.solver.options import SolveOptions
from tkb_core.validation.independent_validator import validate_schedule

if TYPE_CHECKING:
    from tkb_core.diagnostics.model import DiagnosticModel, SubsetOutcome


# The model module imports OR-Tools at load time. Load it only when CP-SAT is needed, so
# counting proofs work without the solver extra (review F6). Module-level wrappers keep the
# names patchable in tests.
def _require_solver() -> None:
    try:
        import ortools.sat.python.cp_model  # noqa: F401
    except ImportError as exc:
        raise CoreError(
            "UNSUPPORTED_FEATURE",
            "SOLVER_NOT_INSTALLED",
            "Install the solver extra to execute CP-SAT",
        ) from exc


def build_diagnostic_model(*args: Any, **kwargs: Any) -> "DiagnosticModel":
    from tkb_core.diagnostics import model

    return model.build_diagnostic_model(*args, **kwargs)


def solve_subset(*args: Any, **kwargs: Any) -> "SubsetOutcome":
    from tkb_core.diagnostics import model

    return model.solve_subset(*args, **kwargs)


def _ref(key: GroupKey) -> GroupRef:
    return GroupRef.model_validate({"kind": key[0], "id": key[1]})


def explain_infeasibility(problem: ScheduleInput, options: ExplainOptions) -> InfeasibilityReport:
    """Diagnose ``problem``; input/capability errors are raised as ``CoreError`` unchanged."""
    started = perf_counter()
    options = ExplainOptions.model_validate(options.model_dump(warnings="error"))
    calls = 0
    solver_version: str | None = None

    def left() -> float:
        return options.time_limit_seconds - (perf_counter() - started)

    def report(
        status: ReportStatus,
        fingerprint: str,
        *,
        proofs: tuple[PrecheckProof, ...] = (),
        subset: tuple[GroupKey, ...] = (),
        unresolved: tuple[GroupKey, ...] = (),
        witnesses: tuple[WitnessCheck, ...] = (),
        minimal: bool = False,
    ) -> InfeasibilityReport:
        evidence = None
        if status == "PRECHECK_PROOF":
            evidence = Evidence(infeasibility="ARITHMETIC")
        elif status == "CORE_SUBSET":
            evidence = Evidence(infeasibility="SOLVER", minimality_witnesses=witnesses)
        return InfeasibilityReport(
            schema_version="1.0",
            status=status,
            input_fingerprint=fingerprint,
            granularity=options.granularity,
            precheck_proofs=proofs,
            subset=tuple(_ref(g) for g in subset),
            minimal_proved=minimal,
            unresolved=tuple(_ref(g) for g in unresolved),
            evidence=evidence,
            metadata=ExplainMetadata(
                solver_version=solver_version,
                seed=options.seed,
                num_workers=1,
                time_limit_seconds=options.time_limit_seconds,
                wall_time=perf_counter() - started,
                solver_calls=calls,
            ),
            limitations=LIMITATIONS,
        )

    limits = options.model_dump(exclude={"granularity", "time_limit_seconds", "seed"})
    solve_options = SolveOptions(
        time_limit_seconds=options.time_limit_seconds, num_workers=1, seed=options.seed, **limits
    )
    fingerprint = problem.fingerprint()
    guards = {
        "max_placements": options.max_placements,
        "max_occupancy_terms": options.max_occupancy_terms,
    }
    try:
        normalized = normalize(problem, solve_options)
        # Counting proofs never depend on granularity: compute them on the clean domain first,
        # so a larger FULL domain cannot hide one behind the resource guard (review F1).
        domains = build_domains(normalized, expanded=False, **guards)
        proofs = run_prechecks(domains)
        if proofs:
            return report("PRECHECK_PROOF", fingerprint, proofs=proofs)
        if options.granularity == "FULL":
            domains = build_domains(normalized, expanded=True, **guards)
    except CoreError as exc:
        if exc.diagnostics[0].code == "RESOURCE_LIMIT":
            return report("RESOURCE_LIMIT", fingerprint)
        raise
    if left() <= 0:  # review F5: preparation used the whole budget
        return report("UNKNOWN", fingerprint)

    _require_solver()
    solver_version = version("ortools")
    groups = enumerate_groups(normalized.problem, options.granularity)
    every: set[GroupKey] = {(str(g.kind), g.id) for g in groups}
    built = build_diagnostic_model(domains, groups)
    first = solve_subset(built, every, left(), options.seed)
    calls += 1
    if first.status == "FEASIBLE":
        return report("NOT_INFEASIBLE", fingerprint)
    if first.status == "UNKNOWN":
        return report("UNKNOWN", fingerprint)
    if not first.core:
        raise CoreError(
            "MODEL_INVALID", "DIAGNOSTIC_MODEL", "Diagnostic model is infeasible without groups"
        )
    current = list(first.core)
    witnesses: dict[GroupKey, tuple[ScheduleAssignment, ...]] = {}
    unresolved: list[GroupKey] = []
    if left() > 0:
        confirm = solve_subset(built, set(current), left(), options.seed)
        calls += 1
    else:
        confirm = None
    if confirm is None or confirm.status == "UNKNOWN":
        return report("CORE_SUBSET", fingerprint, subset=tuple(current), unresolved=tuple(current))
    if confirm.status == "FEASIBLE":
        raise CoreError(
            "MODEL_INVALID", "DIAGNOSTIC_MODEL", "Solver core is not infeasible on its own"
        )
    for group in sorted(first.core):
        if group not in current:
            continue
        if left() <= 0:
            unresolved.append(group)
            continue
        trial = [g for g in current if g != group]
        outcome = solve_subset(built, set(trial), left(), options.seed)
        calls += 1
        if outcome.status == "INFEASIBLE":
            current = trial
        elif outcome.status == "FEASIBLE":
            witnesses[group] = outcome.assignments
        else:
            unresolved.append(group)
    checks: list[WitnessCheck] = []
    for group in sorted(current):
        if group not in witnesses:
            continue
        enforced = set(current) - {group}
        result = validate_schedule(
            normalized.problem, witnesses[group], relaxed_groups=frozenset(every - enforced)
        )
        checks.append(WitnessCheck(group=_ref(group), validator_valid=result.valid))
    unresolved = [g for g in unresolved if g in current]
    minimal = (
        not unresolved
        and len(checks) == len(current)
        and all(check.validator_valid for check in checks)
    )
    return report(
        "CORE_SUBSET",
        fingerprint,
        subset=tuple(sorted(current)),
        unresolved=tuple(sorted(unresolved)),
        witnesses=tuple(checks),
        minimal=minimal,
    )
