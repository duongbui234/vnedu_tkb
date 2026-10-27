# c10-tight-s101 — Tổng hợp evidence về UNKNOWN

**Kết luận:** đúng input/model đã kiểm có nghiệm; cả logging OFF và ON đều đã tìm được lịch hard-valid dưới 60s trong các diagnostic runs. Chưa xác định nguyên nhân ba UNKNOWN lịch sử. Không có Core fix, quality proof hoặc bằng chứng logging/MemTotal là nguyên nhân đổi status.

Lượt tổng hợp trên `feature/phase2a-task5-linux-summary`, baseline `7ced3bd`, chỉ đọc saved artifacts và viết tài liệu. Không chạy solver/search/profiling, prepare/build/compile, scorer/validator hoặc đổi Core/budget/guards. Windows **BLOCKED**; không mở Phase 2B/2C.

## Evidence và phạm vi đối chiếu

Nguồn: [static witness và auxiliary](tight10-static-diagnostic-report.md), [single trace](tight10-search-trace-report.md), [logging pair](tight10-logging-pair-report.md). Các đề xuất cũ trong những báo cáo này là lịch sử; kết luận và đúng một đề xuất hiện tại nằm ở đây.

- Target/fingerprint: `c10-tight-s101` / `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee`.
- Input SHA256: `7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735`; witness SHA256: `f9b5274529c9d1bd4d4c301b2626336bd0128b38b57901b90627ca4be1121a57`.
- Saved compiled feasibility proto SHA256: `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083`; static reconstruction và diagnostic identity snapshots khớp. Không gọi đây là raw proto được thu trực tiếp trong ba historical runs nếu receipts cũ không lưu proto đó.
- Frozen Core/wheel, solver version 9.15.6755, numeric options 60s / workers1 / seed42 và guards không đổi. Diagnostic driver/instrumentation và approved machine snapshot có thay đổi được công bố; không coi toàn bộ execution identity của diagnostic là identical với legacy.
- Các approvals cho single trace và pair đã được dùng hết; tổng hợp này không cấp quyền native run tiếp theo. Legacy exact gate vẫn MACHINE_DRIFT với MemTotal −4 KiB, không sửa/normalize baseline.

| Nhóm evidence | Kết quả đã lưu | Điều được chứng minh trong phạm vi mẫu |
|---|---|---|
| Static witness extension | 260 assignments (220 single +40 double =300 periods), score (0,78,0); 4,700 domains và1,255 constraints đều thỏa, gồm254 max-equalities và60 raw equalities; 60 rule raw/weighted và3 tier values khớp | Có satisfying valuation đầy đủ của đúng compiled model; witness không bị domains/auxiliaries đã kiểm loại bỏ. Không phải solver status hoặc quality optimum |
| Historical repeats r1/r2/r3 | UNKNOWN ở60.001373317 /60.002091255 /60.001277716s native feasibility wall; score=null, quality NOT_EVALUATED, các tier NOT_RUN | Ba lượt đó không xuất nghiệm; không chứng minh vô nghiệm. Thiếu native work counters và phase trace để xác định search progress |
| Single trace, logging ON | Feasibility OPTIMAL, native wall55.924939301s; vào search marker0.15s, có nghiệm marker55.92s; hard-valid260, score(12,77,4) | Lần này thực sự vào search và tìm được nghiệm; không phải chỉ dừng ở presolve |
| Logging pair OFF→ON | Cả hai feasibility OPTIMAL, wall49.772831433 /52.574590097s; hard-valid260, score(12,77,4) | Logging ON không là điều kiện cần để tìm nghiệm trong cặp này; cả hai mode thành công trong những lần được đo |

Giữ ba historical repeats riêng với single trace và cặp n=1/mode. Không gộp thành sáu repeats, success rate, median/P95/SLA hoặc viết lại failed=63/campaign108 results. UNKNOWN và mọi giá trị thiếu giữ nguyên null/reason; wall≈60s không phải thời gian tìm nghiệm của một lượt UNKNOWN.

## Điều đã chứng minh và điều chưa chứng minh

**Correctness:** satisfying witness extension và các lịch native hợp lệ là bằng chứng độc lập rằng mẫu này có nghiệm. Giả thuyết cụ thể “witness mất placement hoặc bị hard/compiled equalities/domains đã kiểm loại bỏ” không phù hợp evidence này. Không suy compiler đúng trên mọi input/lịch, hoặc đã loại mọi bug solver/compiler/runtime.

**Quality:** ba diagnostic successes có full assignments và full score reports giống nhau khi đối chiếu saved JSON. Score(12,77,4) kém witness(0,78,0) theo lexicographic order vì P1=12>0; P2=77<78 không đảo kết luận. Native OPTIMAL thuộc feasibility không objective chất lượng; quality_proved=false, optimal_prefix=[]. Chưa chứng minh witness tối ưu, chưa tối ưu quality hoặc đạt target P2 nào.

**Performance:** ba diagnostic successes có cùng deterministic_time `46.39286630778822`, branches1,150,007, conflicts25,380, binary propagations13,216,444, integer propagations13,426,438 và restarts87; LP iterations374,745 được giữ trong raw response single và pair counters. Counters giống nhau và cùng lịch cuối không chứng minh toàn bộ search trajectory giống nhau. Native wall khác nhau cho thấy thời gian thực đo biến thiên giữa các execution contexts đã lưu; chưa quy được phần biến thiên cho logging hay môi trường.

Riêng matched pair ON−OFF = **+2.801758664s** native wall. Không gọi đây là causal overhead hoặc suy log ON luôn chậm hơn; single trace ON thuộc driver/time/context khác và không phải repeat thêm của pair. Deterministic time không có đơn vị wall/CPU seconds. Native response user_time không thay kernel process CPU accounting. TTF end-to-end vẫn null/NOT_INSTRUMENTED; native markers không thay TTF.

**Drift/workload/power:** MemTotal legacy40745240→diagnostic40745236 KiB là drift được duyệt riêng, chưa có evidence về quan hệ nhân quả với status. Diagnostic snapshots có AC online, nhưng workload_control=UNCONTROLLED, competing_workload=UNKNOWN; load averages không chứng minh idle, competing load hoặc throughput. Không có xác nhận power/governor/frequency/nhiệt ổn định trong solve; không đo công suất W. Legacy gate vẫn BLOCKED, Windows BLOCKED.

## Các giả thuyết còn mở

| Giả thuyết | Evidence liên quan | Khoảng trống khiến chưa kết luận |
|---|---|---|
| Throughput/CPU scheduling/môi trường làm lượng công việc hoàn thành trong60s khác nhau | Diagnostic counters giống nhau nhưng wall khác; workload chưa kiểm soát | Chưa đối chiếu process accounting/context lịch sử; thiếu counters của UNKNOWN. CPU toàn child cũng không định vị được native bottleneck |
| Historical runs đạt progress/search trajectory khác trước deadline | Cùng input/seed không cung cấp trace hoặc counters bị thiếu | Không thể dựng lại branch/conflict/presolve progress của UNKNOWN từ status và wall alone |
| Logging/callback có ảnh hưởng timing | Một pair OFF→ON có chênh lệch wall; OFF cũng tìm được nghiệm | n=1/mode, order/cache/nhiệt/workload bị confound; chưa tách native logging khỏi callback/file flush. Không có causal estimate |
| MemTotal −4KiB là nguyên nhân | Hai snapshot khác field này | Không có phép đối chứng riêng cho drift; không thể kết luận có ảnh hưởng hoặc hoàn toàn vô hại chỉ từ độ nhỏ |

Đây là giả thuyết cần evidence, không là findings yêu cầu sửa Core hoặc nới budget. Số lượng auxiliaries, branches/conflicts/LP iterations không tự chứng minh bottleneck cụ thể. Hiện chưa đủ căn cứ quy UNKNOWN cho presolve, symmetry, quality tiers hoặc một rule cụ thể; quality tiers lịch sử chưa chạy.

## Đúng một bước điều tra tiếp theo — chưa thực hiện

**Audit read-only process accounting và operational context đã lưu cho ba UNKNOWN lịch sử, đối chiếu với ba diagnostic successes, giữ từng execution identity riêng.**

Đây là một phép đối chiếu saved receipts, không là search/profiling experiment mới. Ba historical `run.json` có schema chứa `execution.cpu_seconds`, `launch_to_exit_seconds`, measurement status/reason và RSS fields; lượt tổng hợp chỉ xác nhận availability/schema, chưa lấy các giá trị này để phân tích. Context không có top-level `context` trong các run.json đó: audit phải tìm bằng chứng đúng provenance trong identity/journal/admission đã lưu nếu có, và ghi null + MISSING nếu không có; không gán context hiện tại ngược cho historical runs.

Đầu ra của cùng bước này là bảng sáu rows: run-ID/group/fingerprint/identity, native feasibility wall và nguồn, child launch→exit, kernel CPU-seconds/method/status/reason, ratio CPU/child wall nếu cả hai đo hợp lệ, RSS/unit, timestamps/load/power/workload provenance hoặc missing reason, và xác nhận không watchdog/resource/reap failure. Không gộp thống kê giữa groups hoặc thay missing bằng0. Ratio toàn child có thể >1 vì nhiều threads và gồm startup/build/decode/validation; không coi đó là CP-SAT worker count, native CPU utilization hoặc bằng chứng máy idle.

**Lý do chọn:** tận dụng accounting đã thu để kiểm xem giả thuyết thiếu CPU service/môi trường có thêm bằng chứng hoặc bị giới hạn bởi dữ liệu thiếu, trước khi xin thêm native measurement. **Tiêu chí đọc:** chỉ mô tả accounting/context khác hoặc không đủ dữ liệu; CPU/wall gần nhau cũng không loại frequency/thermal/search-path differences. Không tái dựng counters bị thiếu hoặc kết luận nguyên nhân từ ratio/load. Bước audit này chưa được thực hiện và không bao gồm chạy lại solver, thêm instrumentation, đổi logging/defaults, budget/guards hoặc sửa Core.

## Kiểm chứng và giới hạn của lượt tổng hợp

- Standard-library read-only assertions kiểm15 static +15 auxiliary +17 single-trace +35 pair manifest digests (**82 entries**, có thể trùng file giữa manifests; không phải82 independent samples), saved proto hash và123 protected hashes: PASS.
- Saved JSON so sánh ba diagnostic assignments/full score reports: identical. Ba historical UNKNOWN, score null và tier NOT_RUN/wall null giữ nguyên.
- Không import Core/OR-Tools, chạy lại probe/build/validator/scorer hoặc native run để tổng hợp. Availability check lịch sử chỉ đọc schema/field names; chưa thực hiện accounting/context comparison được đề xuất.
- Chỉ tài liệu thay đổi; không dữ liệu/candidate/receipt/manifest cũ bị ghi lại. Các số đo ở đây đều là lịch sử, không benchmark mới.
- Không chạy pytest trong lượt docs-only; full suite có native solves trái yêu cầu. Kết quả64 fake tests của Task2 là lịch sử, không ghi thành test mới của lượt này.

Lệnh thực chạy: `uv sync --locked --extra solver` PASS; `uv run ruff check .` PASS; `uv run ruff format --check src tests benchmarks` PASS (54 files); `uv run mypy` PASS (27 Core source files); `git diff --check` PASS. Standard-library asserts về manifest/hash/status/nulls và links/scope PASS. Không chạy full pytest hoặc thêm fake tests vì chỉ thay tài liệu và user cấm native solve thêm.
