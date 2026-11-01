# Quality occurrence ordering implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. One fresh final reviewer; no commits, merges or pushes (explicit user scope).

**Goal:** Add only quality-path ordering of fully interchangeable unlocked occurrences before the hard clone.

**Architecture:** `build_model(prepared, *, order_interchangeable=False)` keeps legacy/direct callers unchanged. A private builder helper groups unlocked occurrences by requirement, duration and identical ordered Placement tuples, checks supported quality semantics and integer range, then adds adjacent rank inequalities without new variables. `solve` opts in only for active quality requests before cloning; objectives/search/timing stay byte-identical.

**Tech stack:** Existing Python3.12/Pydantic/OR-Tools pins; no dependency changes.

**Spec:** `C:/tkb-checkout-check/windows-tier1-ec9ced1-readonly-review-v1/proposal.md`, explicitly authorized by the user on2026-11-01. Base main a0aff814b57e85152bd8dde2551ea86450006ec2.

## Global constraints

- Synthetic opaque IDs only; no services, Desktop, SQLite, vnEdu, research changes.
- Same requirement/duration/full ordered `(start_slot_id,slot_ids,room_id,tokens)` domain; numeric ordinal ordering, not string ID sorting.
- Exclude every locked occurrence including room-only locks. Preserve IDs/domains/inputs; no post-incumbent relabeling/manual hints.
- S01–S04 quality1.1 active only; no Phase1/no-soft effect. Skip unsupported/non-equivalent/unrepresentable groups conservatively.
- Stage rank rows per group, safe int64 activity;0 new placement/aux variables. No extra solve or proof/budget changes.
- Native allowed only in small regressions/required suite, no campaign/benchmark. Task2 frozen Linux DEFERRED_NOT_ACCEPTED.
- User forbids commit/merge/push; retain uncommitted worktree and external evidence/ledger.

## Review focus

1. Partial room locks and mixed durations must never be exchanged; test excluded members and projection preservation.
2. Equal domain sets in different order or with different tokens/footprints/rooms must not be grouped; test artificial PreparedProblem variations.
3. Ordinal10 must follow9 even if occurrence iteration is reversed; inspect constraints with known rank assignments.
4. Empty/singleton domains, unknown semantics and int64 boundaries must skip optional optimization without new input errors/variables.
5. Canonicalization must preserve all physical/score projections while validator accepts noncanonical schedules; exhaustive oracle plus native tiny verification and unchanged pipeline tests.

## Task1: representation change with full regression and documentation

**Files:** modify `src/tkb_core/solver/model_builder.py`, `src/tkb_core/solver/cp_sat.py`, `docs/solver-design.md`; add `tests/unit/test_occurrence_ordering.py`, `tests/properties/test_occurrence_ordering_oracle.py`, `tests/integration/test_occurrence_ordering_native.py`; shared small fixture in `tests/conftest.py`; implementation report in docs. No change to objectives/compiler/validation/contracts/options/lock.

**Interfaces:** builder optional keyword above; private `_rank_range_safe(domain_size: int) -> bool`; private ordering helper, no new public JSON field.

- [x] Baseline locked sync and required-suite pytest pass.
- [x] RED: add structural/group/range/identity tests and observe missing keyword failure before implementation.
- [x] GREEN: add private helper and quality-only wiring; run targeted tests and stage regressions.
- [x] Add exhaustive small projection oracle (2/3occurrences, locks/rooms/mixed durations/timed aliases), native tiny optimal-score/clone/hint/no-solver regressions; prove one representative per label orbit without mirroring inequality in the oracle.
- [x] Update solver design and report limitations: canonical output may relabel unlocked occurrences; no speed/quality promise; preserve existing search/timing.
- [x] Run all5 required checks, diff/identity check and fresh whole-change reviewer. No findings; outcomes recorded externally.

## Verification

`uv sync --locked --extra solver`; `uv run --extra solver pytest`; `uv run ruff check .`; `uv run ruff format --check src tests`; `uv run mypy`.

Logs/ledger: `C:/tkb-checkout-check/tier1-ordering-impl-v1/`. No benchmark/eval run or commit. User authorization already covers execution of this plan as a concrete rendering of the approved proposal.
