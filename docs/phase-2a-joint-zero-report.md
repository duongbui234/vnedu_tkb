# Phase 2A — joint-zero candidate, 2026-11-04

**NOT_MET: the requested quality fix is not achieved.** Exactly one new pilot
returned `[0,6,110]` instead of `[0,0,0]`. Controller STOPPED; primary **0/108**,
no retry and no further solver/campaign execution after failure. This candidate
is uncommitted and unqualified. Earlier evidence and packets remain intact.

## Change and hypothesis

In `solver/objectives.py::_solve_tier`, the existing temporary clone now constrains
**every remaining active tier** (`p >= priority`) to zero, instead of only the
current tier. The hypothesis was that daily-load and preferred-window restrictions
would help propagate placements while finding P1=0. No witness, fixture identity,
benchmark profile, external data or new public option enters product search.

The actual objective remains the current tier. Nonnegative penalties mean native
OPTIMAL at zero proves the original current-tier optimum too. Restricted
INFEASIBLE only disproves the suffix-zero combination, not original feasibility or
the attainability of current-tier zero; the original-model fallback is unchanged.
Proved prefix values, including positive ones, are not reset. Hints, deterministic
slice cap12, sticky interleaving and shared monotonic budget remain unchanged.

Tests cover suffix constraint isolation, native joint-zero success and a positive
lower-tier optimum that must not sacrifice P1, plus existing exhaustive
lexicographic, ordering and S03 oracles. Read-only independent review found no
important correctness defects. This correctness evidence is not performance proof.

## Identity, protocol and evidence

New root: `benchmarks/artifacts/phase2a/joint-zero-20261104-v1/`.

| Identity | Value |
|---|---|
| Base HEAD | `537c89125c0e1a81173cd099f08f014194d249b4` |
| Candidate wheel SHA256 | `b2b426ab117afd8872914a51f1e759b57532a06d5ef3feda1e11b6cd0d3aad60` |
| Sealed plan SHA256 | `46ec3dc26db8004b6b3b8d8c32010bc5c5eb67485b0bf88d00b221846e43fb1a` |
| uv.lock SHA256 | `fe404cb126bce893368517318d4982b5f7842990429467d2a793af066c2e4c3b` |
| Pilot input SHA256 | `2249bffbb803ce205df6f631bcf083332bc6af4d571098d129754138e0b85292` |
| Input fingerprint | `b0943eea7ee564a278117af4f387100fd3d7168aa8dcf26d67e7bbac9ecb42ea` |

Python3.12.3 / OR-Tools9.15.6755 / Linux7.0.0-42 x86_64. The preflight's
git/core-tree fields identify base HEAD, not the uncommitted candidate; candidate
identity is the wheel plus exact source hashes in `candidate-source-sha256.json`
and `candidate.patch`. Both new installed environments match all28 Core files.

All36 datasets were verified and all81 raw input/witness/provenance files match
historical bytes. Prepare/headroom/warmup passed. The pilot kept workers1/seed42,
solver60s, watchdog150s, RSS1GiB and reserve2GiB. Frozen primary limits/order,
thresholds, input/search guards and dependency pins were not relaxed.

## Actual pilot, n=1

| Measurement | Result |
|---|---|
| Harness / native status | COMPLETE / FEASIBLE |
| Independent hard validation | PASS; 260 assignments, 300 periods |
| Independent score / witness | **[0,6,110]** / [0,0,0] |
| P1 | OPTIMAL, value0/bound0; **41.684905s** |
| P2 | FEASIBLE, value6/bound0; **15.843754s** |
| P3 | NOT_RUN |
| Total native monotonic time | 58.706259s |
| Core / launch-to-exit | 59.252815s / 59.457403s |
| Peak RSS | 382,853,120 bytes; 365.117MiB, Linux wait4 |
| Exit / resource stop | 0 / none |
| Correctness / performance | PASS / **NOT_MET** |
| Controller / owner | STOPPED (RUN_STOP_POLICY) / IDLE |

**Proven:** the suffix-zero candidate did not produce a retained zero schedule.
It returned exactly the same assignments and score as the preceding single-tier
zero candidate (`comparison.json`). P1 still dominated time, P2 remained unproved,
and P3 was not searched. These two n=1 observations do not establish a stable
speed difference or a performance regression. No primary search was started.

**Unknown:** native status, incumbent and time of the individual joint probe versus
fallback: the campaign stores stage totals, not per-call tracing. The outcome
does not prove whether the probe returned UNKNOWN, was otherwise unproductive,
or how much time each branch consumed. It does not prove a specific upstream
termination branch or that the entire raw60s elapsed. Do not treat the failed
hypothesis as an established root cause or repeat this unchanged candidate.

One source-level limitation remains relevant to further work: when two native
results tie on the current tier, `_solve_tier` chooses the second using `<=`,
without comparing lower-tier values. A better full-vector probe incumbent could
therefore be discarded in that branch. This code path is observable statically;
**there is no per-call evidence that it occurred in this pilot**. No further fix
or run was attempted after the stop gate.

## Commands and checks actually executed

- `uv sync --locked --extra solver`: PASS.
- Regression-first unit tests failed on the prior one-target behavior, then passed
  after implementation. The old native expected-call assertion was updated for
  the newly required conflicting-lower-tier fallback.
- `uv run --extra solver pytest -q`: **356 passed**. Fresh preflight independently
  ran `uv run --extra solver pytest`: **356 passed**.
- `uv run --extra solver pytest tests benchmarks/tests`: **717 passed, 8 skipped**
  (7 native-Windows checks; 1 historical installed-wheel environment opt-in).
- `uv run ruff check .`, `uv run ruff format --check src tests`,
  `uv run ruff format --check src tests benchmarks`, `uv run mypy`,
  `git diff --check`: PASS. Mypy covers28 Core files.
- Fresh generator/preflight/prepare/warmup: PASS. Exactly one pilot: exit2 due to
  qualification failure; native child exit0. No primary command ran.
- `check.py gate` and `check.py score`, installed solver/no-solver Python `-I -B`
  with import guards: PASS, no OR-Tools search import. Rechecked sealed identity,
  both receipts and exact score rules; independent CLI/API hard/score checks,
  witness zero and incomplete-schedule negative control all passed.
- Historical integrity: **365 previous-attempt manifest entries**, **388 older
  declared hash entries**, and all81 old/new raw artifacts checked unchanged.

`partial-summary.json` keeps all108 primary rows NOT_STARTED_GATE_BLOCKED.
The full aggregator was not run because its complete-campaign prerequisites are
absent. The new evidence manifest covers non-venv artifacts; installed identity,
wheel and exact source checks are retained separately. No new Windows execution
or packet was requested/performed; older packets identify older candidates.

Linux operational acceptance remains incomplete. Windows native/cross-OS acceptance
is unverified. No Phase2B/2C, dependency change, research/reverse-engineering edit,
historical evidence edit, upstream send/post, commit, merge or push occurred.
