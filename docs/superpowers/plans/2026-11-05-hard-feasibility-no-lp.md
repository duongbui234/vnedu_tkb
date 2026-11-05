# Hard feasibility no-LP implementation plan

> **For agentic workers:** Use superpowers:executing-plans; execute inline with one fresh final review. No commits are authorized.

**Goal:** Opt in only initial public quality feasibility with workers1 to linearization_level=0.
**Architecture:** Add one internal search mode and keyword-only run_quality opt-in; cp_sat selects it. Repair callers retain default. No model or budget changes.
**Tech Stack:** Python 3.12, locked OR-Tools 9.15.6755, pytest, ruff, mypy.
**Spec:** ../specs/2026-11-05-hard-feasibility-no-lp-design.md (user approved).

## Global constraints

- No preflight, pilot/campaign, owner recovery, installed-package edits, commit/merge/push.
- Native tiny regression tests are authorized; no witness hints or benchmark runs.
- Preserve all existing local notes and measured worktree/evidence.

## Review focus

- First UNKNOWN must stop without retry, fabricated schedule or tier proof.
- First INFEASIBLE/MODEL_INVALID propagate; no status masking.
- Expression verification must keep LP/default mode although priority is null.
- Both repair orders and workers>1 must retain their original modes.
- Remaining budget and raw metadata must stay correct near deadline.

## Task 1: Isolate first-stage parameter change with regressions

**Files:** objectives.py, cp_sat.py; test_stage_parameters.py, test_hard_feasibility_stage.py, test_hard_feasibility_native.py, test_repair_solver.py; solver-design.md.
**Interface:** run_quality(..., *, initial_feasibility_search: Literal["default", "feasibility_no_lp"] = "default"); existing callers unchanged unless explicitly opting in.

- [x] Write parameter/dispatch regression; run it and observe expected RED before product changes.
- [x] Add the search mode and opt-in from public quality solve workers1 only.
- [x] Exercise fake initial statuses, near-deadline budget and later UNKNOWN with both modes.
- [x] Capture native model/parameter boundary for default/no-LP; model bytes identical, only one parameter differs.
- [x] Check native feasible/UNSAT tiny cases with rooms, double periods, locks and hard S02/S03/S05/S06; independently validate schedules/scores.
- [x] Check repair BEFORE/AFTER default path and workers/legacy isolation.
- [x] Update solver-design with scope and unmeasured performance limitation.

## Task 2: Verify and present reviewable diff

- [x] Run uv sync --locked --extra solver, full core tests, benchmark tests, ruff check, ruff format --check src tests, mypy and git diff --check.
- [x] Have one read-only fresh reviewer inspect this change against the approved design; resolve material findings and rerun affected checks.
- [x] Write commit review with exact files, commands/results, exclusions, proposed commit message and remaining approval boundaries. Do not stage/commit.

## Execution record

Base 120058e5a75d15c11280b126ac364684d5470605; branch work/hard-feasibility-no-lp in a new isolated worktree. Implementation directly authorized; no extra plan approval requested.

Task 1: complete. RED: 2 expected new regressions failed before code; focused GREEN 68 tests.
Task 2: complete. Core final 1118 passed; benchmarks 446 passed/8 skipped; sync/lint/format/mypy/diff checks PASS. Fresh read-only review: no findings. No commit/staging.
Ruling: updated the existing native tier-search test first-call expectation after full-suite failure; subsequent stage expectations unchanged.
