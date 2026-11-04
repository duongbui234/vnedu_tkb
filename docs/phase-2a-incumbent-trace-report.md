# Phase 2A — incumbent tie fix and native trace, 2026-11-04

The incumbent-selection bug is fixed and the harness now records each native
call. **Linux pilot acceptance is still NOT_MET:** exactly one pilot returned
`[0,5,120]`, not `[0,0,0]`. Primary is **0/108**, controller STOPPED, owner IDLE.
No retry or further solver/campaign execution followed the failed pilot gate.

## Implemented behavior

`solver/objectives.py::_solve_tier` compares the full active-tier vector in
priority order when choosing between feasible native responses. The proved prefix
is identical in both models. A tie in the current tier therefore keeps the better
lower-tier incumbent; an exact full-vector tie still prefers the second response.
Selected assignments, raw status and bound stay together; native wall times are
summed. Selecting a better FEASIBLE response does **not** inherit another response's
OPTIMAL status or proof. Error propagation and original-model fallback remain.

Five regression cases cover a worse/better lower-tier vector, better current tier,
positive prefix, and exact tie. Two cases failed before the fix, then passed.
Existing native/oracle tests continue checking hard validity and lexicographic
semantics independently.

`benchmarks/native_trace.py` wraps `_run_stage` and `CpSolver.solve` in memory,
restores both methods on exit, and forwards arguments/return values unchanged.
It writes flushed paired stage/native start/end events, or partial error events:
priority/mode, remaining stage and native budget, actual parameters, monotonic and
clock time, deterministic time, response statistics, incumbent/bound, tier values,
model counts and hint-variable counts. UNKNOWN has no incumbent; its raw native
response statistics remain available. No model/hint/parameter mutation, product
instrumentation, installed-source edits, witness hints or extra native solves are
introduced. Tests check model/hint/parameter preservation, result equivalence,
exception restoration, exclusive file creation, controller routing and tamper detection.

The controller launches the observer with isolated installed-wheel Python, seals
its source hash in the plan, and seals each `native-calls.jsonl` hash in the terminal
receipt. Old receipts without traces remain readable; old campaigns are not resumed
against the changed source seals. Logging adds measured overhead; these observations
describe the traced candidate, not an uninstrumented timing experiment.

## Identity and frozen protocol

New evidence: `benchmarks/artifacts/phase2a/incumbent-trace-20261104-v1/`.

| Identity | Value |
|---|---|
| Base HEAD | `537c89125c0e1a81173cd099f08f014194d249b4` |
| Wheel SHA256 | `382a54ba845ce30325670d72a06d13a0b06e2dcd7702fec398e7c262f4d3eead` |
| Sealed plan SHA256 | `10945c1f5c7a7fe482e272713fda0c5c321cef67820d6d47fe0b1936c8b18260` |
| uv.lock SHA256 | `fe404cb126bce893368517318d4982b5f7842990429467d2a793af066c2e4c3b` |
| Input SHA256 | `2249bffbb803ce205df6f631bcf083332bc6af4d571098d129754138e0b85292` |
| Input fingerprint | `b0943eea7ee564a278117af4f387100fd3d7168aa8dcf26d67e7bbac9ecb42ea` |
| Pilot trace SHA256 | `0e4d65fe7f2d6b75fd215c6936e6bb134571a625e7ce1d20bf040e76ba8e3330` |

Python3.12.3, OR-Tools9.15.6755, Linux7.0.0-42 x86_64. The preflight git/core-tree
fields identify base HEAD, not the uncommitted candidate. Actual candidate bytes
are identified by the wheel, `candidate-source-sha256.json`,
`observer-source-sha256.json`, `candidate.patch` and the sealed harness source hash.
All28 Core files match source/wheel/installed bytes in both new venvs.

All36 datasets were verified; all81 input/witness/provenance artifacts remain
byte-identical to historical input. Prepare/headroom/preflight/warmup passed before
the pilot. Warmup's five native calls and sealed trace were audited before pilot.
Pilot limits remained workers1/seed42, solver60s, watchdog150s, RSS1GiB and
reserve2GiB. No threshold, dependency, input, search guard, slice cap12, hint policy
or frozen primary budget/order was relaxed.

## Per-call observations, n=1 pilot

Elapsed below is the observer's monotonic interval around the native solve; native
response wall time and raw response statistics are retained separately.

| Call | Purpose / mode | Budget (s) | Elapsed (s) | Deterministic time | Native status | Outcome |
|---|---|---:|---:|---:|---|---|
| 1 | Hard feasibility / default | 60.000000 | 1.122715 | 1.441670 | OPTIMAL | Hard-valid incumbent |
| 2 | Fixed-hint expression check | 58.871894 | 0.021952 | 0 | OPTIMAL | [22,14,121] |
| 3 | P1 suffix-zero / slice | 58.844068 | **16.919953** | **12.000371** | **UNKNOWN** | No incumbent |
| 4 | P1 original model / interleave | 41.921160 | **24.029257** | 14.294402 | OPTIMAL | [0,7,120], P1 bound0 |
| 5 | P2 / sticky interleave | **17.885541** | **13.701150** | 9.816658 | **FEASIBLE** | [0,5,120], P2 bound0 |

**Proven from trace and source:**

- The joint-zero probe found no incumbent while reaching its configured
  `max_deterministic_time=12`. It consumed about16.92s without improving the saved
  schedule. This is consistent with its deterministic cap; no native termination
  branch was instrumented to establish the exact internal return path.
- The original P1 fallback then spent about24.03s proving P1=0, with P2=7/P3=120.
  Trace constraint counts are2325 for verification/fallback and2328 for the probe,
  consistent with three temporary zero equalities; P2 has2326 including the P1 lock.
- **The fixed tie-selection branch was not exercised by this pilot:** call3 was
  UNKNOWN, so it supplied no candidate to compare against call4. The bug fix is
  regression-proven but cannot explain this pilot's score change.
- P2 improved7→5 but returned FEASIBLE/bound0 with **4.184391s of its raw budget
  unused**. Its actual parameters are max_time17.88554124600023, workers1, seed42,
  interleave_search=true, absolute/relative gap0; no deterministic cap is set.
- Monotonic and clock endpoint deltas agree within approximately7microseconds
  for each call. There is no observed seconds-scale endpoint clock discrepancy.
  This does not instrument internal clock reads or exclude an intermediate jump.
- The native child exited0, no watchdog/RSS stop occurred, and Core stopped at
  the first unproved tier as designed. No call6/P3 followed. The raw deadline alone
  does not explain call5's return; the full60s was not consumed by the application.

The measured bottleneck is now separated: a nonproductive joint probe, a long P1
fallback, and a P2 native return before its raw deadline followed by Core's stop
policy. Why the zero CSP was not solved within its deterministic slice, and which
OR-Tools admission/termination branch ended call5, remain **unproved**. Earlier
upstream cutoff hypotheses are not promoted to established causes by this trace.

## Independent result and resource checks

Hard validity PASS:260 assignments/300 teaching periods. Independent CLI/API score
recomputation exactly matches all rule rows and `[0,5,120]`; same-input witness is
hard-valid `[0,0,0]`. Missing-assignment negative control is rejected. No scoring
process imports OR-Tools/preprocessing/compiler/search under its import guard.

P1 stage40.949517s; P2 stage13.701291s; P3 NOT_RUN. Native monotonic total55.795836s;
Core wall56.153271s; launch-to-exit56.533945s. Peak RSS410,972,160bytes
(391.934MiB), measured by Linux wait4. Correctness PASS / performance NOT_MET.
`[0,5,120]` is lexicographically better than prior `[0,6,110]`, but lower P3 itself
is worse and was never optimized. One traced run cannot establish a stable gain
or attribute the difference to the tie fix, which was not exercised.

## Commands and verification

- `uv sync --locked --extra solver`: PASS.
- `uv run --extra solver pytest`: **361 passed**, both standalone and fresh preflight.
- `uv run --extra solver pytest tests benchmarks/tests`: final **726 passed,
  8 skipped** (7 require native Windows;1 historical installed-wheel opt-in).
- `uv run ruff check .`, `uv run ruff format --check src tests`,
  `uv run ruff format --check src tests benchmarks`, `uv run mypy`,
  `git diff --check`: PASS. Mypy covers28 Core files.
- Read-only source review: no important findings; no solver/campaign run by reviewer.
- First combined suite retained725 passed/8 skipped/1 fixture setup error: the
  synthetic pilot prerequisite was BLOCKED. It was not counted as PASS. Its
  aggregator subset passed23 checks separately; the final frozen full suite passed.
  Import/style lint findings were fixed before source sealing; no failed formal
  pilot or campaign was retried.
- Fresh generation/preflight/prepare, one warmup and exactly one pilot: executed.
  Pilot controller exit2 is a failed qualification, distinct from native exit0.
- `audit_trace.py warmup` and `audit_trace.py pilot`: PASS; paired stage/native
  events, exact parameter equality, source/receipt hashes and response consistency.
- Installed solver/no-solver `check.py gate` / `check.py score`, `-I -B` with guards:
  PASS. Exact identity/receipt integrity and independent schedule/score checks.
- Final historical audit:239 joint-zero manifest entries,365 preceding closeout
  entries and388 older declared hash entries still match; all81 raw artifacts match.

`partial-summary.json` retains all108 primary rows NOT_STARTED_GATE_BLOCKED.
Full aggregation was not invoked without108 primary/110 total receipts. New
`SHA256SUMS` covers non-venv artifacts; installed identity checks are retained.
No primary, retry, Windows native run, new Windows packet, research/reverse-engineering
edit, historical edit, upstream send/post, commit, merge or push occurred.
Linux operational and cross-OS acceptance remain incomplete.
