# Phase 2A Linux closeout

User approval: complete the Linux scope in one pass, including Core changes,
checks, fresh wheel/preflight, one warmup/pilot and gated primary campaign.
No retries, threshold/budget changes, historical edits, commits, merges or pushes.

1. Add regressions and a temporary zero-target tier search, preserving fallback,
   independent validation, proof semantics and the shared solver budget.
   Files: solver/objectives.py, tier unit/native tests, solver-design.md.
2. Run locked sync, full Core and benchmark tests, lint, format and types. Freeze
   the resulting source bytes; create a fresh bundle with unchanged input/witness
   bytes, installed-wheel preflight and campaign identity.
3. Run one warmup and pilot. Stop on any failed gate. Only after PASS, execute
   the frozen 108 primary runs without retries and aggregate actual receipts.
4. Record measured Linux acceptance and prepare the same-wheel Windows handoff.
   Windows native execution/cross-OS acceptance remains pending its environment.

Ruling: continue in the existing dirty worktree because its operational tooling
is part of the authorized work; preserve all existing changes and evidence.
Ruling: try zero only in a cloned model. All active penalties are nonnegative;
native OPTIMAL at zero proves the original tier optimum, while restricted
INFEASIBLE proves nothing about original feasibility and must fall back.

Execution evidence: `benchmarks/artifacts/phase2a/linux-closeout-20261104-v1/`.
Final report: [Linux closeout attempt](../../phase-2a-linux-closeout-report.md).

- [x] Regression-first candidate implemented; native/oracle and independent review passed.
- [x] Locked sync, 355 Core tests, final combined 716 passed / 8 skipped,
  lint/format/types, fresh wheel/preflight and unchanged 81 raw artifacts verified.
- [x] Prepare and one warmup passed; exactly one pilot returned [0,6,110],
  correctness PASS / performance NOT_MET. Controller STOPPED, owner IDLE.
- [ ] Linux operational acceptance: gate failed, primary blocked at 0/108.
- [x] No-solver receipt/score audit, partial summary, same-wheel Windows candidate
  packet, patch reconstruction and manifest checks completed. No retry.

Ruling: stop solver/campaign execution after the failed pilot, as authorized.
Do not tune another candidate or run primary under this failed qualification.
The candidate remains uncommitted and unqualified; Windows native is NOT_RUN.
