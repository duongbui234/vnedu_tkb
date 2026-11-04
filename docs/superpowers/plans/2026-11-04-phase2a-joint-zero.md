# Phase 2A — joint zero search

User authorization: fix P1/P2, regression and fresh preflight, exactly one new
pilot; primary only if PASS. No witness hints, threshold/budget changes or retries.
No historical evidence edits, research changes, commits, merges or pushes.

Hypothesis: probing only the current tier leaves lower-tier zero constraints out
of propagation. A suffix-zero probe can seek a compatible incumbent directly.
It is optional restricted search, not a change to the lexicographic objective.

1. Regression-first: constrain every remaining active tier to zero in the existing
   temporary probe. Preserve original-model fallback, proof/status, hints and budget.
   Cover joint feasibility, conflicting lower-tier targets and positive prefix.
2. Run locked sync, Core/benchmark tests, lint, format, types and source review.
3. Freeze a new wheel/bundle/preflight in a new evidence directory; verify all81
   raw input/witness bytes against historical evidence. Seal fresh machine identity.
4. One warmup and exactly one pilot using the existing controller and frozen limits.
   Stop on failure. Only after PASS, execute the sealed108 primary rows once.
5. No-solver hash/receipt/score audit and actual outcome report. Preserve prior work.

Ruling: work in the existing dirty workspace to preserve authorized operational
tooling and the preceding candidate. No worktree/commit/approval detour is needed.
Ruling: no extra full-size diagnostic search before the one qualifying pilot.
Development native tests remain tiny synthetic fixtures, not campaign retries.

## Outcome

- [x] Candidate and regressions; Core356 passed, combined717 passed /8 skipped;
  lint/format/types and independent source review passed.
- [x] New wheel/preflight, all36 datasets and81 unchanged raw artifacts verified.
- [x] One warmup PASS; exactly one pilot NOT_MET, score[0,6,110].
- [ ] Linux acceptance /108 primary: blocked by failed pilot, no retry.
- [x] No-solver identity/receipt/score audit and historical hash checks passed;
  [actual report](../../phase-2a-joint-zero-report.md) written.

Ruling: stop all solver/campaign and implementation work after pilot failure.
No unchanged-candidate rerun, threshold relaxation or additional diagnostic solve.
Evidence: `benchmarks/artifacts/phase2a/joint-zero-20261104-v1/`.
