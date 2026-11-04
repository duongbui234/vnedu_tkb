# Phase 2A — current operational verification, 2026-11-03

**PARTIAL — Phase 2A technical synthetic acceptance remains valid; operational
acceptance is not complete. Current Linux pilot is correctness PASS / performance
NOT_MET. Windows native execution is awaiting the user. No primary campaign or
cross-OS acceptance is claimed.**

## Scope and implementation

Base `537c89125c0e1a81173cd099f08f014194d249b4`, working branch
`work/phase2a-operational-completion`. User requested all remaining Phase 2A work.
No Scheduling Core, schema, constraint, dependency, lockfile, research or external
service changes. No commit, merge, push or deletion.

- `windows_runtime.py`: native x64 CPython 3.12 process-handle peak working set
  (bytes), CPU times, watchdog/resource stops, explicit owned wait, console
  cancellation and native host/memory admission probes. Inherited Job Objects
  with unverified resource accounting block admission rather than assume host RAM.
- `run_benchmarks.py`: native dispatch, Windows accounting fields without fabricated
  POSIX wait status, Windows byte-range campaign lock, native identity/headroom.
  Existing Linux fields remain supported. Source seals include the Windows backend.
- `phase2a_preflight.py`: fresh installed solver/no-solver venvs, hash-locked binary
  dependencies, exact source/wheel/installed membership and bytes, Core/native
  tests, lint/format/Core types, tiny CLI roundtrip and guarded scoring, all 36
  dataset witnesses/proofs. No hardcoded 27-file assumption; current Core has 28.
- `aggregate_linux.py`: the existing entrypoint now labels the actual native OS
  and memory method; Windows aggregation cannot silently claim cross-OS acceptance.
  It still requires all 108 primary rows and 110 receipts before producing a full
  campaign report. No partial campaign is promoted to COMPLETE.
- `run_phase2a_windows.ps1`: hash-checked portable packet, local detached worktree
  from the pinned base with LF source, same Linux-built wheel, preflight then
  prepare/warmup/pilot/primary/aggregation under existing gates, evidence export
  excluding venvs. The original checkout is retained. Native PowerShell execution
  has not been tested in this Linux session.

## Linux preflight and preserved history

Evidence root: `benchmarks/artifacts/phase2a/current-linux-20261103-v2/`.
Final installed environments and preflight manifest: `preflight-reviewed/`.

Shared wheel SHA256:
`0e5c83f27505d43ceb06518ff6b0dc27937c14ef010805ab10e1bffc97bdf699`.
Core tree: `6214ebc9ae7ab6b7976fc34fafb031ccd0b20c7b`.

The first preflight attempt is retained at
`current-linux-20261103-v1/preflight/`: environment, wheel and tiny checks succeeded,
but the historical bundle correctly failed current-Core provenance verification.
The generator recomputes source identity as part of each manifest. It was not
weakened to accept an obsolete manifest.

A new 36-dataset bundle was generated under `current-linux-20261103-v2/bundle/`.
All **81 input/witness/provenance JSON files match the old bundle byte for byte**;
only manifests/revision provenance were regenerated for current Core. Current
installed-wheel bundle verification passed. Historical bundles, campaign receipts,
inputs, budgets and outcomes were not overwritten. Historical audits need their
frozen source snapshot; current source seals must not be bypassed to replay them.

## Current Linux pilot — actual measurements, n=1

Campaign `current-linux-20261103-v2`; plan SHA256
`011f7593a1d50feed7ac66cf5178c6fa031be804dd9a88ee1fb9e930f5585253`.
Linux x86_64, Intel Core i7-12700H, 20 logical CPUs, Python 3.12.3,
OR-Tools 9.15.6755. Power/competing workloads were not controlled.

Prepare and tiny warmup PASS. Pilot dataset: `c10-base-s101`, input SHA256
`2249bffbb803ce205df6f631bcf083332bc6af4d571098d129754138e0b85292`.
Workers 1, seed 42, solver budget 60s, launch watchdog 150s, observed RSS target
1 GiB, 2 GiB admission reserve. No guard or budget changes.

| Check/measurement | Observed result |
|---|---|
| Harness / measurement | COMPLETE / OK |
| Solver / returned schedule | FEASIBLE / hard-valid |
| Independent hard validation and score recomputation | PASS / MATCH |
| Final score / known attainable target | `[0,7,116]` / `[0,0,0]` |
| Proof prefix | `[1]`; P2 unproved, P3 NOT_RUN |
| Launch to exit | 58.61331067199353 s |
| Peak child RSS | 370905088 bytes, Linux wait4 kernel accounting |
| Child CPU | 60.438377 s across threads |
| P1 | OPTIMAL, 0, bound 0, monotonic stage wall 41.932915496014175 s |
| P2 | FEASIBLE, 7, bound 0, monotonic stage wall 14.75381600500259 s |
| Correctness / performance / witness comparison | PASS / NOT_MET / WORSE |
| Campaign state | STOPPED, RUN_STOP_POLICY; pilot failed qualification |
| Primary | **0/108, NOT_RUN** |

Time and RAM targets were met; the BASE zero-score target was not. This is a
quality/performance failure, not a hard-validity failure. P1 consumed most of the
available solve time in this run; this observation does not establish a general
root cause or a regression against another Core version without a controlled pair.
No automatic retry, primary launch, larger budget, different workers or easier
profile was used to turn the failed pilot into PASS.

`pilot-audit.json` verifies both terminal receipts/hashes and re-runs independent
output checks without search. Current execution identity gate PASS, owner IDLE.
There is no orphan scheduling child or in-progress campaign. No latency/SLA,
speedup, P95, Windows result or production-readiness conclusion follows from n=1.

## Checks actually executed and review

| Command/check | Result |
|---|---|
| `uv sync --locked --extra solver` | PASS; no lock/dependency changes |
| `uv run --extra solver pytest` | PASS, 351 Core tests, final run 6.35s |
| `uv run --extra solver pytest tests benchmarks/tests -q` | **712 passed, 8 skipped**, 99.10s, final stable Python source |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests benchmarks` | PASS, 74 files |
| `uv run mypy` | PASS, 28 Core source files |
| `uv build --wheel` through preflight | PASS; shared wheel retained |
| Two isolated installed environments, exact 28-file Core comparison | PASS |
| Installed tiny solve/validate/score, no-solver and guarded scorer | PASS |
| Current bundle, 36 datasets; input preservation, 81 artifacts | PASS |
| Current campaign prepare/warmup/pilot and receipt/output audit | PASS / PASS / NOT_MET / VERIFIED |

Seven skips require native Windows APIs/locking/Job Objects; the eighth is the
historical installed-wheel test requiring `TKB_PREFLIGHT_DIR`. These skips do not
certify Windows. Current installed-wheel behavior was exercised by fresh preflight.

One independent review found two Important bugs in the new tooling. Both were
reproduced RED and fixed GREEN: setup-command deadlines now contain descendant
work (POSIX process group with an unreaped leader; Windows kill-on-close Job Object
assigned to a blocked trampoline before work starts), and Windows cancellation
protects spawn/ownership/cleanup across the whole lifecycle. Regression tests check
surviving descendants, interrupted PID capture, POSIX cleanup and signal-mask
inheritance. The reviewer did not re-review
the fixes or later PowerShell script; the author ran final regressions/full suite.
No deferred reviewer Minor findings.

The first full-suite attempt recorded 707 passed, 6 skipped and one campaign fixture
error while controller files were being formatted. The isolated fixture rerun and
stable full suite passed; that initial attempt is not counted as PASS. Logs are
retained under `.superpowers/sdd/2026-11-03-phase-2a-operational-completion/`.

Exploratory expanded mypy commands failed because of namespace/package resolution,
Linux versus Windows API stubs and pre-existing untyped benchmark imports. Only
the configured Core mypy gate is reported PASS; the entire benchmark/Windows
tooling is not claimed to have passed strict static typing.

## Windows handoff and remaining acceptance

Packet: `benchmarks/artifacts/phase2a/windows-current-20261103-v2.zip`, with shared
wheel, identical current bundle, patch, inventory and PowerShell entrypoint. Copy
and extract to a short new path, for example `C:\tkb-2a-20261103`, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\tkb-2a-20261103\run-windows.ps1 -Repository D:\code\vnedu_tkb
```

Replace only the two local paths. The repository must contain base commit 537c891;
no network fetch is performed. The script creates a separate detached worktree and
new evidence directories; no commit, merge, push, cleanup or implicit retry. Do not
run concurrent campaigns on shared hardware. Return `windows-evidence.zip`, including
partial/error evidence if a native check or pilot fails. If PowerShell fails before
export, return its exact error and any created evidence directory.

Windows uncertainties requiring actual execution: post-exit peak queries, fast/spike
children, native cancellation/cleanup, Job Object containment, byte-range locking,
binary dependency availability and PowerShell/path behavior. A Windows pilot must
pass before its primary campaign; Linux NOT_MET must not be relabeled from Windows
success. Two-OS acceptance additionally needs complete campaigns and exchanged
schedule validation/scoring. School policy calibration remains unconfirmed.

**Outstanding:** current Linux quality/performance gate; current 108-run primary
on each platform; native Windows preflight/supervisor/pilot/campaign; cross-OS
result validation and final acceptance. No Phase 2B/2C, repair, UI or adapter work
was started. Completing tooling and reporting a NOT_MET outcome is not completing
these operational acceptance conditions.

Native API references: [PROCESS_MEMORY_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters),
[GlobalMemoryStatusEx](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-globalmemorystatusex),
[Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
