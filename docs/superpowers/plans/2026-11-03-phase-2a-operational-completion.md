# Phase 2A operational completion

> **For agentic workers:** use superpowers:executing-plans. The user's request on
> 2026-11-03 authorizes completing remaining Phase 2A work. Do not commit, merge,
> push, or open Phase 2B/2C.

**Goal:** complete the outstanding operational checks against current Core, with
honest per-platform acceptance and reproducible evidence.

**Architecture:** retain the existing synthetic protocol, installed-wheel isolation,
Linux controller, and independent validation. Extend only the missing Windows
measurement/control boundaries; refresh preflight in new directories. Never change
frozen historical bundles, receipts, budgets, or acceptance thresholds to obtain PASS.

**Tech Stack:** pinned Python 3.12, uv.lock, standard library, native OS APIs.

**Spec:** ../specs/2026-10-26-phase-2-quality-design.md and
2026-10-26-phase-2a-operational-validation.md.

## Global constraints

- Core technical acceptance already exists at 537c891; do not add scheduling rules.
- Input 1.1/policy 0.1, output 1.2; synthetic opaque IDs only.
- Primary protocol: 36 datasets, three repeats, workers 1, seed 42;
  10/20/40 classes: solver 60/120/180s, watchdog 150/210/270s, RSS 1/2/4 GiB.
- Reserve 2 GiB before every run; no automatic retry, overwrite or budget relaxation.
- Windows native runs are performed by the user; Linux cannot certify Windows.
- No credentials, API calls, research changes, dependency changes or production SLA.

## Review focus

- Windows peak memory must survive fast exit and spike/release; no cumulative peaks.
- Probe/cleanup errors must not publish a schedule or imply INFEASIBLE.
- Installed Core must match the same wheel and checkout on both systems.
- Historical preflight is tied to old Core and cannot certify current Core.
- Missing Windows evidence and failed performance gates must remain explicit.

## Tasks

- [x] 1. Add Windows supervisor and shared platform dispatch with regression tests;
  preserve Linux behavior, locks, identity and existing output contracts.
- [x] 2. Provide reproducible current-wheel preflight and Windows commands, run all
  available correctness/tooling checks, prepare a portable handoff for the user.
- [ ] 3. Execute current Linux warmup/pilot/primary with unchanged protocol when gates
  permit; aggregate all outcomes. Windows execution awaits the user's native results.
- [x] 4. Review the change, run required final checks, update acceptance documentation
  with actual evidence and outstanding conditions. Do not mark two-OS acceptance
  complete while native Windows evidence or performance gates remain unmet.

## Execution checkpoint

2026-11-03: Linux installed preflight and 36-dataset verification PASS. New bundle's
81 non-manifest artifacts exactly match historical bytes. Prepare/warmup PASS;
pilot correctness PASS / performance NOT_MET, score [0,7,116], target [0,0,0].
Controller stopped before primary (0/108); owner IDLE, receipts/audit verified.
No retry or gate relaxation. Windows execution remains external/user-dependent.
Two Important review findings were reproduced and fixed with RED→GREEN regressions;
final Python suite 712 passed, 8 skipped. Task 3 is intentionally incomplete;
tooling delivery does not turn failed or absent operational evidence into acceptance.
