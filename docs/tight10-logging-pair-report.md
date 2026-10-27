# TIGHT10 — One approved logging OFF→ON pair

Task 2 của [logging pair plan](superpowers/plans/2026-10-27-tight10-logging-pair.md) hoàn tất trên `feature/phase2a-task5-linux-summary`, baseline `2073467`. Một lần gọi parent, đúng **hai native feasibility solves**, OFF→ON, không retry. Cả hai COMPLETE / measurement OK / native feasibility OPTIMAL, mỗi lượt 260 assignments hard-valid và score `(12,77,4)`. Không quality optimization/proof. Windows **BLOCKED**; không Phase 2B/2C.

## Scope, approval và snapshot

- Candidate đã duyệt: `568c69099aae15a2688a4f23f02b6cf1885f8a55e3b6a4c943d3b742f4059da0`; pair-ID `tight10-logging-pair-20261027-v1`.
- Output root: `/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1`.
- Run-IDs: `tight10-logging-pair-20261027-v1-off`, `tight10-logging-pair-20261027-v1-on`; fresh child PIDs **526245**, **528085**, parent PID **526224**.
- User explicitly chấp thuận candidate, MemTotal −4 KiB và workload/power limits. [Authorization](../benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1/pair-authorization.json) và [nguyên văn approval](../benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1/user-authorization.txt) được ghi trước chạy; action `RUN_ONE_LOGGING_PAIR`, scope exact hash/root/IDs/order.
- Source driver SHA256 giữ `e09760bdcc217edfabb9dfa9b18252543eb352c4ee634aa0ea1d1355d9e48169`. Core/wheel, runner/generator, lock/dependencies, input/witness, model, seed **42**, workers **1** giữ nguyên. Model hash `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083` chung cả hai.
- Mỗi native budget **60s**, gap tolerances **0**, watchdog **150s**, RSS observed target **1GiB**; guards 10,000 slots / 10,000 occurrences / 100,000 placements / 1,000,000 occupancy terms. RSS target không phải OS hard cap. Headroom≥3GiB / disk≥256MiB; parent và child admissions PASS, AC online trước cả hai; full current common identity khớp candidate. Chỉ logging profile/callback bundle khác nhau.
- Legacy gate giữ **BLOCKED_MACHINE_DRIFT**, diff duy nhất `MemTotal: 40745240 → 40745236 kB`, −4096 bytes. Không sửa gate/legacy baseline hoặc tự rebaseline.

## Correctness và quality

| Evidence | OFF | ON |
|---|---|---|
| Native status | OPTIMAL (feasibility) | OPTIMAL (feasibility) |
| Harness/member | COMPLETE | COMPLETE |
| Measurement / exit / wait status | OK / 0 / 0 | OK / 0 / 0 |
| Constructor / solve calls | 1 / 1 | 1 / 1 |
| Independent validation | PASS, 260 assignments | PASS, 260 assignments |
| Independent score tiers | (12,77,4) | (12,77,4) |
| Quality proved / optimal prefix | false / [] | false / [] |
| Trace capture | DISABLED; trace_complete=null | COMPLETE; trace_complete=true |
| Actual log callback | None | raw_utf8_flush |
| Solution / bound callbacks | absent / absent | absent / absent |

Full assignments và full per-rule score reports **identical** giữa hai runs. Instrumentation kiểm hard validation, toàn bộ rule raw/weighted values và tier values so với compiled model values trước publish lịch. Audit sau chạy dùng installed interpreter, chặn CpSolver, đọc saved assignments và tính lại independent validation/score: PASS cho cả hai, không rebuild model hoặc native solve thêm.

Feasibility OPTIMAL không là tối ưu soft score. Witness static có `(0,78,0)`, tốt hơn theo thứ tự từ điển vì P1=0<12; không gọi score cặp này là quality improvement. Không có UNKNOWN trong cặp mới; ba UNKNOWN lịch sử vẫn giữ nguyên, không đổi status, không thêm repeats hoặc gộp thống kê với treatments mới.

## Performance: các số đo của đúng cặp này

| Metric | OFF | ON |
|---|---:|---:|
| Native wall (s) | 49.772831433 | 52.574590097000005 |
| Native deterministic time (solver units) | 46.39286630778822 | 46.39286630778822 |
| Branches | 1150007 | 1150007 |
| Conflicts | 25380 | 25380 |
| Binary propagations | 13216444 | 13216444 |
| Integer propagations | 13426438 | 13426438 |
| Booleans | 2796 | 2796 |
| Restarts | 87 | 87 |
| LP iterations | 374745 | 374745 |
| Instrumented stage elapsed (s) | 49.78140821899797 | 52.58334150400333 |
| Child launch→exit (s) | 50.53918489699936 | 53.46562245399764 |
| Kernel process CPU seconds (wait4) | 52.364844 | 55.129688 |
| Kernel peak RSS (KiB) | 151480 | 151424 |
| Kernel peak RSS (bytes) | 155115520 | 155058176 |
| Kernel peak RSS (MiB) | 147.9296875 | 147.875 |
| Sampled peak RSS (bytes) | 155934720 | 156012544 |

ON−OFF native wall = **2.801758664s**; kernel process CPU delta = **2.764844 CPU-s**. Đây là chênh lệch mô tả của một cặp, **không ước lượng causal logging overhead**. Các work counters và deterministic time trùng nhau, phù hợp cùng lượng công việc solver đã quan sát; vẫn không loại trừ workload/frequency/cache/thermal/order effects. Không dùng deterministic_time như wall/CPU seconds hoặc coi native response user_time là kernel process CPU.

Inter-run gap field **0.158226944s** đo từ parent nhận supervisor return/reap OFF đến gọi supervisor ON; không phải native solve→solve latency. Khoảng cách giữa hai instrumented stage timestamps = **1.015729271s**, gồm serialize/validation/child startup/build/identity checks. Không warmup hoặc scripted cooldown.

OFF không tạo trace.log và giữ reason LOGGING_DISABLED; không biến deliberate absence thành failure hoặc zero. ON raw log 14,977 bytes có markers `Starting presolve at 0.00s`, `Starting search at 0.13s with 1 workers.`, `#1 52.57s main`. Raw chunks có thể liền nhau; markers là native elapsed text, **không TTF end-to-end**. `first_feasible_elapsed_seconds=null`, reason NOT_INSTRUMENTED ở cả hai; search-marker elapsed field của driver vẫn null (OFF LOGGING_DISABLED / ON NOT_PARSED). Không suy marker OFF hoặc điền null thành 0.

## Workload/power và giới hạn so sánh

| Snapshot | UTC | Load avg 1/5/15 min | Power quan sát |
|---|---|---|---|
| logging_off pre | 2026-10-27T08:52:11.151154+00:00 | [0.5791015625, 1.26611328125, 1.31884765625] | Mains=1, USB=1; BAT0 Full/100 |
| logging_off post | 2026-10-27T08:53:01.702512+00:00 | [2.02099609375, 1.53857421875, 1.4091796875] | Mains=1, USB=1; BAT0 Full/100 |
| logging_on pre | 2026-10-27T08:53:01.848651+00:00 | [2.02099609375, 1.53857421875, 1.4091796875] | Mains=1, USB=1; BAT0 Full/100 |
| logging_on post | 2026-10-27T08:53:55.329083+00:00 | [2.0126953125, 1.62841796875, 1.4501953125] | Mains=1, USB=1; BAT0 Full/100 |

Parent pre/post và child pre-admission đều lưu raw context; AC/USB online, battery Full/100 ở các snapshots, không observed power change. Giữ `workload_control=UNCONTROLLED`, `competing_workload=UNKNOWN`, không VERIFIED_IDLE. Load avg là rolling observation, có thể gồm chính run; không chứng minh external workload tăng hoặc gây delta. Hai power snapshots không chứng minh power/governor/frequency/temperature ổn định trong solve.

Comparability luôn **LIMITED**: n=1/mode, OFF→ON cố định, không kiểm soát cache/nhiệt/frequency/competing jobs; không median/P95/SLA/causal claim, không đổi default logging hoặc kết luận đã sửa UNKNOWN. OFF tự tìm được nghiệm trong cặp này chứng minh logging ON không cần thiết cho lần tìm nghiệm đó; chưa giải thích vì sao ba runs lịch sử UNKNOWN ở 60s. Single trace trước, cặp mới và ba repeats cũ giữ ba nhóm evidence riêng.

## Artifacts và kiểm toàn vẹn

- [Pair result](../benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1/pair-result.json), [manifest](../benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1/manifest.json), [OFF terminal](../benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1/runs/01-off/terminal.json), [ON terminal](../benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1/runs/02-on/terminal.json).
- [Preflight mới](../benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1-audit/preflight.json), [audit độc lập](../benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1-audit/verification.json), parent stdout/stderr ở audit root riêng. Không viết thêm vào root đã manifest sau terminal.
- Manifest **35 files**, SHA256 `fd67e24e39fbdc57fda2798c8924ee105ce6d842afe07704eb75e12f1069abea`; mọi digest và file membership khớp, candidate/driver hash nguyên vẹn. START/terminal/manifest gắn pair approval identity; parameters chỉ khác log_search_progress, callback state đúng profile.
- Hai spawned children đều reap confirmed, không signal/watchdog/resource stop, owner shared **IDLE**. Không re-entry/retry. 123 protected hashes trước Task1 vẫn nguyên vẹn sau Task2; Core/tooling frozen/evidence cũ không đổi. Đây không phải một lần audit lại toàn bộ campaign 108 lượt.

## Lệnh thực chạy và kiểm chứng

Một lần gọi native parent, exit **0**, stdout/stderr chuyển vào audit root:

```sh
/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1/venv-solver/bin/python -I /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/trace_tight10.py run-pair --root /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1 --authorization /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1/pair-authorization.json
```

Installed `python -I -` scripts chạy preflight/authorization và audit saved artifacts với CpSolver constructor chặn; additional native calls = **0**. Không chạy profiler, không đổi runtime env/affinity/power hoặc tự kill jobs.

| Lệnh | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS |
| `uv run --extra solver pytest benchmarks/tests/test_trace_tight10.py -q` | **64 PASS**, 0.65s; fake-only, không native solve |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests benchmarks` | PASS, 54 files |
| `uv run mypy` | PASS, 27 Core source files |
| `git diff --check` | PASS |
| Saved-artifact audit, digest/scope/parameter/validation assertions | PASS, manifest35 + protected123 |

Review độc lập cuối lượt đã đối chiếu candidate/driver hashes, toàn bộ 35 manifest hashes và membership, common identities/profiles, approval/terminal bindings, call counts và arithmetic: không còn finding quan trọng. Một câu stale status trong plan đã được ghi rõ là lịch sử tại cuối Task 1. Reviewer không chạy native/model build hoặc test thêm.

Ruling giữ nguyên: không chạy full pytest vì có native solves ngoài hai calls đã duyệt; các native integration paths khác không được chạy lại. Không sửa code/Core/legacy gates/budget/guards, không thêm repeat hoặc dataset. Windows vẫn BLOCKED.

Bước tiếp theo được đề xuất: tổng hợp static witness, single trace và cặp logging để phân biệt điều đã chứng minh với giả thuyết còn mở về UNKNOWN; chưa tự thực hiện điều tra hoặc phép đo thêm.

## Tổng hợp tiếp sau pair

Đã có [báo cáo tổng hợp static/single/pair](tight10-evidence-synthesis.md), phân biệt kết luận với giả thuyết còn mở về UNKNOWN. Đề xuất hiện tại duy nhất là audit read-only process accounting/context từ receipts đã lưu; chưa thực hiện audit hoặc native measurement thêm.
