# Phase 2A — incumbent tie handling and native trace

Authorization: fix incumbent selection on current-tier ties; observational native
call tracing in harness; regression, fresh preflight and exactly one pilot.
Primary only after PASS. Keep frozen limits, no witness hints, no retry,
historical edits, dependency changes, research changes, commits, merges or pushes.

1. Regression-first fix in solver/objectives.py: compare active tier vectors on
   tied objectives, retaining the selected native status/bound and total wall time.
2. Add benchmarks/native_trace.py as an installed-wheel CLI observer; hook it in
   the controller, seal its source identity and receipt hashes. Trace parameters,
   mode/priority/budget, native timing, response stats, incumbent/bound and stage
   outcomes without changing models, hints, options or native call count.
3. Full Core/benchmark tests, lint/format/types and independent source review;
   freeze new source/wheel/bundle/preflight, verify all81 historical raw artifacts.
4. One warmup and exactly one pilot using existing limits and supervision. Stop
   on a failed gate. Only if pilot PASS, execute sealed108 primary rows once.
5. No-solver receipt/score/trace audit and report proven observations separately
   from cutoff hypotheses. Preserve all previous evidence and report limitations.

Ruling: continue in the dirty workspace to preserve prior authorized work.
Ruling: selecting a better FEASIBLE incumbent does not inherit OPTIMAL raw status
from another native response; return the selected response's honest metadata.

## Outcome

- [x] Tie regressions RED→GREEN; observational tracing and source/receipt seals.
- [x] Core361 passed; final combined726 passed/8 skipped; lint/format/types and
  independent review passed. Fresh wheel/preflight and81 unchanged raw artifacts.
- [x] One warmup PASS, trace audit PASS; exactly one pilot returned[0,5,120], NOT_MET.
- [ ] Linux primary108 /operational acceptance: gate-blocked,0 attempted, no retry.
- [x] No-solver trace/identity/receipt/score audit and historical hashes passed;
  [observed result and limitations](../../phase-2a-incumbent-trace-report.md) recorded.

Ruling: stop further implementation and solver/campaign execution after pilot
failure. Call3 UNKNOWN means the tie-selection fix was not exercised in the pilot;
call5 left4.184391s raw budget unused, but exact native cutoff remains unproved.
Evidence: `benchmarks/artifacts/phase2a/incumbent-trace-20261104-v1/`.
