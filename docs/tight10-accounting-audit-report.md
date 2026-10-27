# c10-tight-s101 — Read-only CPU/wall và context audit

**Kết luận:** ba UNKNOWN lịch sử đều có kernel accounting OK, nhận62,704–62,792 CPU-s trong60,879–60,971s child wall. Ratio CPU/child wall từng lượt≈1,030, không có ratio rất thấp trong ba receipts này. Điều đó **không xác định nguyên nhân UNKNOWN**, không đo CPU riêng native solve, không loại trừ scheduling/frequency/thermal/search-progress khác nhau.

Audit trên `feature/phase2a-task5-linux-summary`, baseline `79582d5`; chỉ đọc saved receipts/context và ghi báo cáo/evidence mới. Không chạy solver/search/profiling, build/compile hoặc lấy workload/power hiện tại. Không sửa Core/budget/guards, legacy gate hoặc raw artifacts. Windows **BLOCKED**, không Phase2B/2C.

## Sáu executions, giữ nguyên các nhóm

Các số thập phân trong bảng được làm tròn để đọc; [audit.json](../benchmarks/artifacts/phase2a/tight10-accounting-audit-v1/audit.json) giữ raw values, full execution/identity/context và nguồn từng field. Không pool thành6repeats/success rate hoặc thống kê khác execution identity. Ba historical repeats, single trace và pair n=1/mode vẫn riêng.

| Execution | Native status | Native feasibility wall (s) | Child launch→exit (s) | Kernel CPU user+sys (CPU-s) | CPU / child wall | Kernel peak RSS (KiB) |
|---|---|---:|---:|---:|---:|---:|
| Legacy r1 | UNKNOWN | 60.001373317 | 60.970566616 | 62.792184 | 1.029876996 | 130332 |
| Legacy r2 | UNKNOWN | 60.002091255 | 60.879143864 | 62.733361 | 1.030457346 | 130364 |
| Legacy r3 | UNKNOWN | 60.001277716 | 60.895198964 | 62.704237 | 1.029707400 | 130364 |
| Single ON | OPTIMAL | 55.924939301 | 56.913798120 | 58.514631 | 1.028127325 | 150020 |
| Pair OFF | OPTIMAL | 49.772831433 | 50.539184897 | 52.364844 | 1.036123636 | 151480 |
| Pair ON | OPTIMAL | 52.574590097 | 53.465622454 | 55.129688 | 1.031124028 | 151424 |

Native wall lịch sử lấy từ `result.json#metadata.feasibility_run.wall_time`; diagnostic lấy `trace-result.json#counters.wall_time`. CPU và child wall lấy từ kernel `execution` receipt, phương pháp **linux_wait4**, không dùng native response user_time hoặc deterministic_time làm CPU seconds. RSS có field ru_maxrss/unit KiB, đúng bytes=KiB×1024; sampled peak được giữ riêng trong raw execution, không thay cho kernel peak hoặc coi chênh sampled/kernel là lỗi memory.

Cả6 measurement_status=OK, measurement_reason=null; harness/member COMPLETE. Ba UNKNOWN có exit_code=4/raw_wait_status=1024, đúng mapping CLI UNKNOWN→4, **không phải child crash**. Diagnostic exit0/wait0. Tất cả signal=null, stop_reason=null, error_type=null, wait status có dữ liệu: không watchdog/resource stop hoặc unconfirmed reap trong những receipts này. Không thay null thành0.

## Identity và provenance

| Execution | Exact run-ID | Child PID | Plan/candidate binding SHA256 |
|---|---|---:|---|
| Legacy r1 | `primary-c10-tight-s101-7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735-w1-s42-r1` | 424318 | `6b8a324560b1857555f686a955f5af79468e5f80a00d830466b9253e648a9e61` |
| Legacy r2 | `primary-c10-tight-s101-7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735-w1-s42-r2` | 450700 | `6b8a324560b1857555f686a955f5af79468e5f80a00d830466b9253e648a9e61` |
| Legacy r3 | `primary-c10-tight-s101-7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735-w1-s42-r3` | 535116 | `6b8a324560b1857555f686a955f5af79468e5f80a00d830466b9253e648a9e61` |
| Single ON | `tight10-trace-20261027-v2` | 399367 | `802f1f06ab5565d5b09c994fe1cb8c7044c8469096a2e130ce1be53ab9d77006` |
| Pair OFF | `tight10-logging-pair-20261027-v1-off` | 526245 | `568c69099aae15a2688a4f23f02b6cf1885f8a55e3b6a4c943d3b742f4059da0` |
| Pair ON | `tight10-logging-pair-20261027-v1-on` | 528085 | `568c69099aae15a2688a4f23f02b6cf1885f8a55e3b6a4c943d3b742f4059da0` |

- Các row giữ nguyên full raw identity snapshot; historical bind vào plan `6b8a3245…`, single bind vào candidate `802f1f06…`, pair bind vào candidate `568c6909…` cùng mode/profile riêng. Các digest đầy đủ ở bảng, không dùng prefix làm identity gate.
- Chung input SHA256 `7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735`; fingerprint input `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee` đã xác nhận trong [static/synthesis](tight10-evidence-synthesis.md). Không gán fingerprint mới cho input khác.
- Core/wheel/version và numeric options/limits khớp:60s, workers1, seed42; guards10,000slots /10,000occurrences /100,000placements /1,000,000occupancy terms; watchdog150s, RSS target1GiB. Hai snapshot MemTotal khác nhau: legacy40745240 /diagnostic40745236 KiB; drift−4KiB được duyệt riêng, không coi execution identities hoàn toàn giống nhau. Historical invoke installed CLI; diagnostics invoke driver wrappers/source hashes riêng và logging policy riêng.
- Historical run.json không lưu raw model hash hoặc native work counters: `null / NOT_CAPTURED_IN_LEGACY_RECEIPTS`. Diagnostic model hash giữ nguyên `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083`. Không dựng lại counters/proto lịch sử từ diagnostic.
- Historical score=null, quality NOT_EVALUATED/tiers NOT_RUN giữ nguyên; diagnostic score(12,77,4), không quality proof. TTF end-to-end null cùng original reason giữ nguyên; không dùng native wall làm latency nghiệm cho UNKNOWN.

## Operational context tìm lại đúng nguồn

| Execution | Pre-context timestamp UTC | Load avg 1/5/15min trước run | Load avg sau run |
|---|---|---|---|
| Legacy r1 | 2026-10-26T19:16:38.082290+00:00 | [1.4052734375, 1.39892578125, 1.62646484375] | null / NOT_CAPTURED_IN_SAVED_RECEIPTS |
| Legacy r2 | 2026-10-26T19:41:36.077550+00:00 | [1.13427734375, 1.19482421875, 1.26953125] | null / NOT_CAPTURED_IN_SAVED_RECEIPTS |
| Legacy r3 | 2026-10-26T21:02:45.856607+00:00 | [1.27880859375, 1.2216796875, 1.1953125] | null / NOT_CAPTURED_IN_SAVED_RECEIPTS |
| Single ON | 2026-10-27T07:29:22.722418+00:00 | [2.734375, 1.4169921875, 1.1484375] | null / NOT_CAPTURED_IN_SAVED_RECEIPTS |
| Pair OFF | 2026-10-27T08:52:11.151154+00:00 | [0.5791015625, 1.26611328125, 1.31884765625] | [2.02099609375, 1.53857421875, 1.4091796875] |
| Pair ON | 2026-10-27T08:53:01.848651+00:00 | [2.02099609375, 1.53857421875, 1.4091796875] | [2.0126953125, 1.62841796875, 1.4501953125] |

**Nguồn historical:** `pilot-linux-20261027-v1/journal.jsonl`, đúng một START và một TERMINAL cho từng run-ID/phase primary; tất cả plan_sha256 khớp plan. START.detail.operational_context là pre-context. TERMINAL.detail.terminal_sha256 khớp actual terminal receipt; các file digests trong terminal khớp raw files. START timestamp/context timestamp là lúc admission/journal, không phải native solve entry hoặc TTF. Journal TERMINAL timestamp được giữ trong audit.json nhưng **không là post-context**: event này chỉ chứa terminal digest, không load/power snapshot. Không lấy snapshot của run khác/campaign environment làm post-context thay thế.

**Nguồn single:** `identity-before-run.json#context`, chỉ pre-context; không có saved post-context trong root manifest. Post=null với reason NOT_CAPTURED_IN_SAVED_RECEIPTS.

**Nguồn pair:** mỗi `runs/01-off|02-on/terminal.json#pre_context|post_context`, cùng pair-result đã lưu. Child pre-context riêng ở `attempt/child-identity.json#admission.context` cũng giữ nguyên trong audit.json, không gộp timestamp với parent pre-context.

Tất cả available snapshots ghi AC Mains online=1, USB online=1/status Charging, BAT0 Full/capacity100. Pair pre/post không đổi raw power fields; historical/single thiếu post nên không suy power ổn định suốt run. Mọi row vẫn workload_control=UNCONTROLLED và competing_workload=UNKNOWN. Load status OBSERVED không phải VERIFIED_IDLE. Không có số đo watts, energy, governor/frequency/nhiệt hoặc per-core CPU service để bù vào.

## Diễn giải có giới hạn

1. Có bằng chứng process accounting hợp lệ và lượng CPU toàn child đáng kể cho cả ba UNKNOWN. Không quan sát ratio thấp ở chúng; những receipts này không ủng hộ mô tả child hầu như không nhận được CPU. **Không loại trừ CPU starvation cục bộ trong native solve** vì accounting gộp cả startup/build/decode/validation và mọi child threads.
2. Accounting chỉ gồm child; không bao gồm admission/verification chạy ở parent. Ratio>1 có thể do CPU nhiều threads cộng dồn ở các giai đoạn khác nhau; không chứng minh CP-SAT dùng workers>1 hoặc native solve đạt100% utilization. Không lấy CPU_s trừ một overhead tính từ wall seconds để ước lượng native CPU.
3. UNKNOWN child chạy lâu hơn và tổng CPU lớn hơn từng diagnostic success trong những row đã lưu. Không suy UNKNOWN đã làm nhiều native search work hơn: thiếu counters lịch sử, wrapper/entrypoint khác, CPU mỗi đơn vị công việc phụ thuộc nhiều yếu tố chưa đo. Không suy throughput hoặc speed-up từ các tổng này.
4. Pre-load của single ON lớn hơn cả ba historical UNKNOWN nhưng single vẫn tìm được nghiệm. Quan sát này không hỗ trợ một quy tắc đơn giản “load trung bình cao thì UNKNOWN”; không chứng minh load không ảnh hưởng, cũng không xác định competing jobs. Load rolling có thể gồm các workloads trước đó hoặc chính run.
5. Accounting/context audit đóng khoảng trống “chưa đọc CPU/context lịch sử”; chưa đóng khoảng trống **native phase CPU và progress tại deadline**. Không khôi phục được branch/conflict/LP/presolve progress lịch sử, không quy nguyên nhân cho logging, MemTotal, rule/compiler, symmetry hoặc frequency. Root cause UNKNOWN vẫn mở.

Correctness/quality không được kiểm lại bằng solver hoặc scorer ở audit này; kết quả đã lưu giữ nguyên. Không sửa failed=63/campaign108 hoặc ba repeats lịch sử; không benchmark mới hoặc nghiệm thu SLA/Windows.

## Kiểm chứng và artifact đầu ra

- [audit.json](../benchmarks/artifacts/phase2a/tight10-accounting-audit-v1/audit.json):6rows với exact run-ID/full identity, raw execution, ratio/reason, pre/post/child context cùng nguồn, thiếu dữ liệu giữ null/reason.
- [source-hashes.json](../benchmarks/artifacts/phase2a/tight10-accounting-audit-v1/source-hashes.json):75unique input/source hashes, journal/plan/candidate và receipts liên quan; input digests khớp trước/sau extraction. Hash journal trong audit là provenance/content snapshot, không là chữ ký chứng minh hoàn hảo lịch sử.
- [audit.py](../benchmarks/artifacts/phase2a/tight10-accounting-audit-v1/audit.py): one-off standard-library extraction script; không thêm module/API/tests vào sản phẩm. Assertions kiểm6unique rows, receipt bindings/digests, measurement/exit/reap/RSS units, identities/options và123protected hashes.
- Bốn assert cases kiểm ratio với CPU=0 hợp lệ, CPU missing, wall≤0 và measurement BLOCKED. Không fill null bằng0 hoặc chia trên missing/invalid measurement. Saved inputs không bị ghi lại; output nằm ở root audit mới.

Lệnh thực chạy: `python3 .superpowers/sdd/tight10-accounting-audit/audit.py` → PASS6rows/75source hashes/123protected hashes, native calls0. `uv sync --locked --extra solver`, `uv run ruff check .`, `uv run ruff format --check src tests benchmarks` (54files), `uv run mypy` (27Core files) và `git diff --check` đều PASS. Decimal-ratio assertions,75source hashes/123protected hashes, local links và docs-only tracked scope PASS. [Output manifest](../benchmarks/artifacts/phase2a/tight10-accounting-audit-v1/manifest.json) chốt3files audit/script/source-hashes mới; không sửa source inputs. Không chạy pytest/native integration vì lượt này audit saved data và full suite có solver calls ngoài scope.

## Đúng một bước tiếp theo — chưa thực hiện

**Chỉ lập kế hoạch đo CPU user+system riêng quanh native feasibility solve và lưu native work counters tại kết thúc/deadline, trên cùng mẫu/options/guards.** Mục đích là bỏ confound accounting toàn child trong một diagnostic tương lai; không hứa tái hiện UNKNOWN hoặc chứng minh causality từ một mẫu. Kế hoạch cần chỉ rõ boundary đo, overhead/instrumentation, fake tests, source/candidate hash mới và approval riêng trước native run; không tự thêm retries, đổi budgets hoặc chạy để tìm mẫu UNKNOWN. Lượt audit này chưa lập kế hoạch, triển khai instrumentation hoặc thực hiện phép đo đó.

## Kế hoạch tiếp sau audit

Đã lập [kế hoạch native feasibility CPU](superpowers/plans/2026-10-27-tight10-native-cpu.md): rusage/self quanh bound native call, final response counters, fixed logging OFF và candidate/approval mới. Lượt lập kế hoạch chỉ docs; chưa instrumentation/prepare/candidate hoặc native run thêm.
