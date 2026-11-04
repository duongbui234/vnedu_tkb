# Phase 2A Linux closeout attempt — 2026-11-04

**NOT_MET.** The authorized integrated attempt reached its single pilot and stopped
on the quality gate. Phase 2A Linux operational acceptance is unfinished. Primary
is **0/108**, with no retry. Windows native and cross-OS acceptance are also pending.

## Change and correctness

The candidate changes only `src/tkb_core/solver/objectives.py`: the first
single-worker tier slice searches a temporary clone constrained to objective zero.
All S01–S04 penalties are nonnegative, so native OPTIMAL at zero also proves the
original tier optimum. Restricted INFEASIBLE becomes UNKNOWN and falls back to
the original model using the remaining shared budget. The original model never
receives the temporary equality. Original-model INFEASIBLE/MODEL_INVALID errors
are propagated instead of being hidden behind a probe's UNKNOWN result.

Public contracts, rules, dependencies, hints and occurrence ordering are unchanged.
The internal deterministic slice cap remains 12s, and sticky interleaving remains.
The candidate is **uncommitted and not performance-qualified**; passing regression
tests does not make this a successful quality fix.

Regression coverage includes temporary-constraint isolation, impossible-zero
fallback, error propagation, native zero and positive optima, hint/budget handling,
and existing exhaustive lexicographic/ordering/S03 oracles. A read-only independent
Core review found no important defects; its test-fixture aliasing observation was
fixed with a copy before the final suite.

## Frozen identity and evidence

New evidence root: `benchmarks/artifacts/phase2a/linux-closeout-20261104-v1/`.

| Identity | Value |
|---|---|
| Base HEAD | `537c89125c0e1a81173cd099f08f014194d249b4` |
| Candidate wheel SHA256 | `6d180a6e67ba28a735673c7044292ab78519550551bd142aff35cffa336c600f` |
| uv.lock SHA256 | `fe404cb126bce893368517318d4982b5f7842990429467d2a793af066c2e4c3b` |
| Sealed plan SHA256 | `f8cfc853baa0ff94914d8aa5c88134a18abfc5aa0a17f086c309422f3895ab2d` |
| Pilot input SHA256 | `2249bffbb803ce205df6f631bcf083332bc6af4d571098d129754138e0b85292` |
| Input fingerprint | `b0943eea7ee564a278117af4f387100fd3d7168aa8dcf26d67e7bbac9ecb42ea` |
| Runtime | Python 3.12.3, OR-Tools 9.15.6755, Linux x86_64 |

The preflight's `core_tree=6214ebc9ae7ab6b7976fc34fafb031ccd0b20c7b`
is the **base HEAD tree**, not the uncommitted candidate's source identity.
Candidate bytes are recorded in `candidate-source-sha256.json`, checked against
all 28 wheel/installed Core files in both new venvs, and transported in the patch.
No commit was created to obtain an identifier. The current kernel is 7.0.0-42;
historical evidence used 7.0.0-38. Fresh machine identity was sealed; historical
machine gates were not weakened or used to certify this execution.

All 36 datasets were regenerated with current source provenance. All **81 raw
input/witness/provenance artifacts match historical bytes**. Preflight PASS covers
installed-wheel isolation, locked versions, exact Core bytes, no-solver environment,
tiny CLI roundtrip, guarded scoring and all 36 dataset witnesses/proofs.
Prepare, headroom and warmup passed before the pilot. Pilot limits remained
workers1/seed42, solver60s, watchdog150s, RSS1GiB plus reserve2GiB; all other frozen
campaign thresholds, order and 10/20/40 budgets remain unchanged.

## Measured result, n=1

| Metric | Candidate pilot |
|---|---|
| Native/public status | FEASIBLE / SCORED_FEASIBLE |
| Independent hard validity | PASS, 260 assignments / 300 teaching periods |
| Independent score | **[0,6,110]**, exact rule/tier match |
| Same-input witness score | [0,0,0], independently valid |
| P1 | OPTIMAL, value/bound 0/0; 40.597339s |
| P2 | FEASIBLE, incumbent/bound 6/0; 15.833180s |
| P3 | NOT_RUN |
| Native monotonic total | 57.616613s |
| Core wall / launch-to-exit | 58.171472s / 58.353296s |
| Peak RSS | 381,771,776 bytes, 364.086MiB; Linux wait4 ru_maxrss |
| Harness / exit / resource stop | COMPLETE / 0 / none |
| Correctness / quality / performance | PASS / WORSE than witness / NOT_MET |
| Controller disposition | STOPPED, RUN_STOP_POLICY; owner IDLE |

**Proven:** P1 still consumes most native time; P2 remains unproved and P3 does not
run. The candidate did not solve the zero-target acceptance problem. The saved
historical pilot scored [0,7,116]; this candidate scored [0,6,110], but a single
observation on different kernel identities does not establish a speedup or stable
quality improvement. No native per-call trace was added to the product, so stage
totals do not identify which P1 probe/fallback consumed how much time.

**Hypotheses, not established causes:** a zero-target CSP may still be difficult;
the sequential probe may fail to find zero promptly, leaving interleave to prove
P1; interleave admission/cutoff may still limit P2. This run does not prove a
specific OR-Tools termination branch, upstream defect or that all raw 60s elapsed.
The earlier upstream standalone evidence concerns the previous model/search
capture and cannot identify this candidate's native cutoff.

The next implementation needs to reduce time spent reaching/proving a compatible
P1/P2 zero incumbent, with general synthetic oracle coverage. Repeating this
unchanged candidate, increasing budgets, lowering targets, or supplying the benchmark
witness as a product hint would not establish the requested fix.

## Checks actually executed

- `uv sync --locked --extra solver`: PASS.
- `uv run --extra solver pytest`: **355 passed** in the final Core check and preflight.
- `uv run --extra solver pytest tests benchmarks/tests`: **716 passed, 8 skipped**.
  Seven skips require native Windows; one requires a specified historical installed
  wheel via `TKB_PREFLIGHT_DIR`. Current installed-wheel preflight ran separately.
- `uv run ruff check .`, `uv run ruff format --check src tests`,
  `uv run ruff format --check src tests benchmarks`, `uv run mypy`,
  `git diff --check`: PASS. Core mypy covers 28 files, not all benchmark tooling.
- Fresh preflight setup, generate36, prepare, one warmup, **one pilot**: executed.
  Pilot returned exit2 because its quality gate failed. No primary command ran.
- `check.py gate` in installed solver venv and `check.py score` in installed
  no-solver venv, both `-I -B` with forbidden-import guards: PASS. Exact seals,
  both receipts and source/wheel identity checked; CLI/API score and hard validity
  recomputed, witness zero verified, incomplete-schedule negative control rejected.
- Final historical audit verified **388 declared hash entries**; all 81 old/new
  input/witness artifacts still match. Historical evidence was not edited.

Development failures were retained in the logs rather than counted as PASS:
initial regressions failed before implementation, and the old stage-count assertion
needed the newly required impossible-zero fallback. A native test inspection using
negative indexing into the OR-Tools constraint container crashed; positive indexing
fixed the test inspection, and the final complete suite passed. No campaign retry
was involved.

## Deliverables and boundary

`partial-summary.json` retains all 108 planned primary rows as
NOT_STARTED_GATE_BLOCKED; it is not a full campaign aggregate. The full aggregator
was not invoked because its 108-run/110-receipt prerequisites are absent.

`windows-handoff.zip` contains the identical wheel/bundle, a source/test/tooling
patch and the existing native PowerShell driver. Its inventory and ZIP are checked,
and the patch was applied to a temporary base snapshot to compare exact current
Python bytes (`windows-patch-check.json`). It is an **unqualified candidate handoff**,
not evidence of Windows execution or authorization to bypass the Linux stop.
Windows native accounting, PowerShell execution and cross-OS validation remain
unverified. Preserve the old packets and all old evidence.

Packet SHA256: `5e966668117ab1ac9597b09ce1560b0c5e4ff9329918bb160582469d382d8060`;
549,994 bytes, 124 ZIP members, 123 manifest entries checked. The evidence root's
`SHA256SUMS` covers all retained non-venv artifacts; venv files are deliberately
excluded, with the installed identity and wheel/source checks retained instead.

No Phase 2B/2C, new solver/campaign after the failed gate, product dependency change,
research/reverse-engineering edit, upstream send/post, commit, merge or push occurred.
