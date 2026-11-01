# Quality-only occurrence ordering — implementation report

Base main: `a0aff814b57e85152bd8dde2551ea86450006ec2`. Worktree:
`D:/code/vnedu_tkb-tier1-ordering`, branch `feat/tier1-occurrence-ordering`.
User authorized implementation of the proposal on2026-11-01; no commit/merge/push.

Closeout update 2026-11-01: the sentence above records the original implementation
scope. The user subsequently authorized commit and local merge, with no push or
worktree deletion. Current Phase2A acceptance and refreshed checks are in
[phase-2a-report.md](phase-2a-report.md); integration receipts are retained under
`C:/tkb-checkout-check/phase2a-closeout-v1/`. The implementation and measurements
below remain the historical record of their respective runs.

## Behavior

When input1.1 has enabled supported soft rules, public `solve` opts into placement-rank
ordering before the hard clone. Groups share requirement, duration and the entire ordered
Placement tuple (start, footprint, room, tokens); every locked member, including room-only
locks, is excluded. Adjacent ranks follow numeric ordinal, using existing placement
Booleans and no extra variables. Domain0/1, unknown semantics, enabled custom hard and
unsafe int64 rank activity skip the optional optimization. No input/data mutation or
post-incumbent remapping is performed.

This chooses a representative of interchangeable unlocked labels, preserving the set of
resource/score projections under current S01–S04 semantics. Labeled output can differ;
the independent validator still accepts noncanonical hard-valid schedules. Direct
`build_model` callers default to the old model; Phase1/no-active-quality paths stay off.
The current sticky-interleave search and monotonic timing in objectives are unchanged,
as are hints, fixed-hint verification, compiler/range guards, schemas/options and locks.

## Regression evidence

- RED: the structural regression failed with missing `order_interchangeable` keyword
  before implementation; then GREEN with helper/wiring.
- 20 unit cases: row/variable structure, no mutation, every lock type, different
  requirement/duration/domain sequence/tokens/footprint/room, empty/singleton domain,
  unsupported/no-active/legacy semantics, full-group range fallback/int64 boundaries,
  reversed occurrence iteration with ordinal10 after9.
- 9 exhaustive projection oracles:2/3 singles, mixed durations, locks, rooms and timed
  aliases. Python enumeration uses independent validation/scoring; native enumeration
  with/without ordering retains exactly the same profiles/score vectors and one
  representative per unlocked permutation orbit. The projection includes identity and
  selected placement of excluded locked members (important for room-only locks).
- 7 native/integration cases: equal tiny lexicographic optimum vectors, unchanged locks
  and independent scores, ordering already present in hard clone/full-model prefix,
  fixed-hint only for verification, all-tier proofs, legacy/no-quality off,
  OBJECTIVE_RANGE before any stage and guarded no-solver validation/scoring.
- Existing stage-budget/status/prefix/mismatch, contract unknown-field/schema and
  packaging tests remain in the complete suite. No custom S01/S02/S03/S04 formulas added.

## Commands actually executed

All commands ran inside the new worktree with the existing pinned uv tool.

| Required check | Result |
|---|---|
| `uv sync --locked --extra solver` | PASS,30 packages resolved/checked |
| `uv run --extra solver pytest` | PASS,351 tests (baseline315) |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` | PASS,57 files formatted |
| `uv run mypy` | PASS,28 source files |

Additional commands: targeted RED/green/unit/stage/oracle/native tests, ruff formatting,
read-only git status/diff/identity checks. Logs are in
`C:/tkb-checkout-check/tier1-ordering-impl-v1/`.

Final independent fresh-context review:0 Critical/Important/Minor findings; ready for
handoff. Reviewer inspected all tracked/untracked changes and required-check logs;
did not rerun native tests. Review and complete file snapshots are recorded with the
external evidence/ledger. No deferred minors. c10 finite-budget effects and frozen
Linux Task2 acceptance remain outside the reviewed measurements; the former can improve,
stay unchanged or regress, and the latter is not operationally accepted by this task.

## Boundaries

No campaign/benchmark/c10 solve, manual hints, external services, Desktop/SQLite/vnEdu,
dependency change, commit, merge or push. `research/` and `reverse-engineering/` are
unchanged. Native execution was limited to tiny regressions and the required test suite.
No speedup, quality improvement under a timeout, or model size/performance result on the
c10 dataset is claimed. Representation changes can improve, leave unchanged or worsen
finite-budget behavior; that requires a separately scoped evaluation.

Task2 frozen Linux: **DEFERRED_NOT_ACCEPTED**.
