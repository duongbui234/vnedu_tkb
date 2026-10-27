# c10-tight-s101 — Tổng hợp evidence về UNKNOWN

**Kết luận cập nhật:** đúng input/model đã kiểm có nghiệm; bốn diagnostic executions đã tìm được cùng lịch hard-valid dưới60s. Lượt native CPU mới đo **46.008923 CPU-s /46.036537386s boundary wall**, ratio **0.999400163705**. Đây là evidence của một lượt thành công, **chưa giải thích ba UNKNOWN lịch sử**; không Core fix, quality proof hoặc causal logging/MemTotal claim.

Bản tổng hợp ban đầu từ baseline `7ced3bd`; cập nhật native CPU trên `feature/phase2a-task5-linux-summary`, baseline `c9e7405`. Lượt này chỉ đọc saved artifacts và sửa đúng file tổng hợp này. Không chạy solver/search/profiling, prepare/build/compile, scorer/validator hoặc đổi Core/budget/guards. Windows **BLOCKED**; không mở Phase 2B/2C.

## Evidence và phạm vi đối chiếu

Nguồn: [static witness và auxiliary](tight10-static-diagnostic-report.md), [single trace](tight10-search-trace-report.md), [logging pair](tight10-logging-pair-report.md), [CPU/wall accounting audit](tight10-accounting-audit-report.md) và [native CPU execution](tight10-native-cpu-report.md). Các đề xuất audit/measurement cũ đã được thực hiện theo approval riêng; không phải authorization chạy lại.

- Target/fingerprint: `c10-tight-s101` / `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee`.
- Input SHA256: `7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735`; witness SHA256: `f9b5274529c9d1bd4d4c301b2626336bd0128b38b57901b90627ca4be1121a57`.
- Saved compiled feasibility proto SHA256: `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083`; static reconstruction và diagnostic identity snapshots khớp. Không gọi đây là raw proto được thu trực tiếp trong ba historical runs nếu receipts cũ không lưu proto đó.
- Frozen Core/wheel, solver version 9.15.6755, numeric options 60s / workers1 / seed42 và guards không đổi. Diagnostic driver/instrumentation và approved machine snapshot có thay đổi được công bố; không coi toàn bộ execution identity của diagnostic là identical với legacy.
- Native CPU run-ID `tight10-native-cpu-20261027-v1`, candidate SHA256 `5585a43eee2ac961591f320b56e743347efe449a976fbed78c7ad620631c2499`, fixed logging OFF /native_cpu_v1; measurement thuộc execution identity này, không phải measurement bổ sung cho receipts cũ.
- Các approvals single trace, pair và native CPU đã được dùng hết; tổng hợp này không cấp quyền native run tiếp theo. Single/pair lưu snapshot MemTotal40745236KiB (−4KiB so với legacy), legacy gate khi đó MACHINE_DRIFT. Candidate native CPU mới lưu40745240KiB khớp legacy, fresh legacy gate PASS; không sửa/normalize snapshot hoặc đồng nhất những execution identities này.

| Nhóm evidence | Kết quả đã lưu | Điều được chứng minh trong phạm vi mẫu |
|---|---|---|
| Static witness extension | 260 assignments (220 single +40 double =300 periods), score (0,78,0); 4,700 domains và1,255 constraints đều thỏa, gồm254 max-equalities và60 raw equalities; 60 rule raw/weighted và3 tier values khớp | Có satisfying valuation đầy đủ của đúng compiled model; witness không bị domains/auxiliaries đã kiểm loại bỏ. Không phải solver status hoặc quality optimum |
| Historical repeats r1/r2/r3 | UNKNOWN ở60.001373317 /60.002091255 /60.001277716s native feasibility wall; score=null, quality NOT_EVALUATED, các tier NOT_RUN | Ba lượt đó không xuất nghiệm; không chứng minh vô nghiệm. Thiếu native work counters và phase trace để xác định search progress |
| Single trace, logging ON | Feasibility OPTIMAL, native wall55.924939301s; vào search marker0.15s, có nghiệm marker55.92s; hard-valid260, score(12,77,4) | Lần này thực sự vào search và tìm được nghiệm; không phải chỉ dừng ở presolve |
| Logging pair OFF→ON | Cả hai feasibility OPTIMAL, wall49.772831433 /52.574590097s; hard-valid260, score(12,77,4) | Logging ON không là điều kiện cần để tìm nghiệm trong cặp này; cả hai mode thành công trong những lần được đo |
| Native CPU v1, logging OFF | Một attempt/native call, feasibility OPTIMAL; native response wall46.033664557s, CPU-boundary46.008923CPU-s /wall46.036537386s; hard-valid260, score(12,77,4) | Đã tách measurement tại native-call boundary khỏi whole-child accounting của đúng lượt này; chưa đo lại historical UNKNOWN |

Giữ ba historical repeats riêng với single trace, cặp n=1/mode và native CPU n=1. Không gộp thành bảy repeats, success rate, median/P95/SLA hoặc viết lại failed=63/campaign108 results. UNKNOWN và mọi giá trị thiếu giữ nguyên null/reason; wall≈60s không phải thời gian tìm nghiệm của một lượt UNKNOWN.

## Điều đã chứng minh và điều chưa chứng minh

**Correctness:** satisfying witness extension và các lịch native hợp lệ là bằng chứng độc lập rằng mẫu này có nghiệm. Giả thuyết cụ thể “witness mất placement hoặc bị hard/compiled equalities/domains đã kiểm loại bỏ” không phù hợp evidence này. Không suy compiler đúng trên mọi input/lịch, hoặc đã loại mọi bug solver/compiler/runtime.

**Quality:** bốn diagnostic successes có full assignments và full score reports giống nhau khi đối chiếu saved JSON. Score(12,77,4) kém witness(0,78,0) theo lexicographic order vì P1=12>0; P2=77<78 không đảo kết luận. Native OPTIMAL thuộc feasibility không objective chất lượng; quality_proved=false, optimal_prefix=[]. Chưa chứng minh witness tối ưu, chưa tối ưu quality hoặc đạt target P2 nào.

**Performance:** bốn diagnostic successes có cùng deterministic_time `46.39286630778822`, branches1,150,007, conflicts25,380, binary propagations13,216,444, integer propagations13,426,438 và restarts87; LP iterations374,745 được giữ trong raw response single, pair và native CPU counters. Counters giống nhau và cùng lịch cuối không chứng minh toàn bộ search trajectory giống nhau. Native wall khác nhau cho thấy thời gian thực đo biến thiên giữa các execution contexts đã lưu; chưa quy được phần biến thiên cho logging hay môi trường.

Riêng matched pair ON−OFF = **+2.801758664s** native wall. Không gọi đây là causal overhead hoặc suy log ON luôn chậm hơn; single trace ON thuộc driver/time/context khác và không phải repeat thêm của pair. Deterministic time không có đơn vị wall/CPU seconds. Native response user_time không thay kernel process CPU accounting. TTF end-to-end vẫn null/NOT_INSTRUMENTED; native markers không thay TTF.

**Native CPU — hai scopes riêng:** native_cpu_v1 lấy getrusage(RUSAGE_SELF) ngay quanh bound native solve, sau guards và trước response/decode/validation/file writes. User delta45.997800CPU-s +system delta0.011123CPU-s =46.008923CPU-s; elapsed boundary46.036537386s, ratio0.999400163705. Native response wall46.033664557s là field khác, không thay boundary wall. Whole child wait4 ghi48.614788CPU-s /46.808505258s, ratio1.038588772105. Chênh CPU toàn child−boundary≈2.605865CPU-s là accounting ngoài interval, không định vị phần nào hoặc nguyên nhân latency.

CPU scope vẫn gồm **mọi thread của child trong interval**, không riêng CP-SAT; có overhead clock/bookkeeping sát boundary, không calibration/trừ overhead. Ratio≈1 chỉ mô tả lượt thành công này, không chứng minh exclusive core hoặc không có scheduling gap. Sáu executions cũ (ba UNKNOWN, single, pair) chưa có measurement này: native-boundary CPU=null/NOT_INSTRUMENTED; không suy ngược từ whole-child ratio, native user_time hoặc deterministic_time.

Native return_code4 của lượt mới là **CP-SAT OPTIMAL** với process exit0; khác CLI exit4 biểu diễn UNKNOWN trong historical receipts. Native call trả trước60s nên counters là **final-at-return**, không snapshot đồng bộ t=60.000s; termination_cause=null/NOT_EXPOSED. Không biến timing/counter thiếu thành0 hoặc gán nguyên nhân timeout từ status alone.

**Drift/workload/power:** single/pair thành công ở snapshot40745236KiB, native CPU thành công ở40745240KiB khớp legacy. Như vậy snapshot−4KiB không cần thiết cho diagnostic success mới; vẫn chưa chứng minh MemTotal hoàn toàn vô hại hoặc gây đổi status. Legacy gate của native CPU PASS, không dùng kết quả này sửa gate/status lịch sử. Available snapshots có AC online nhưng workload_control=UNCONTROLLED, competing_workload=UNKNOWN; không proof idle, power/governor/frequency/nhiệt ổn định hoặc công suất W. Windows vẫn BLOCKED.

## Các giả thuyết còn mở

| Giả thuyết | Evidence liên quan | Khoảng trống khiến chưa kết luận |
|---|---|---|
| Throughput/CPU scheduling/môi trường làm lượng công việc hoàn thành trong60s khác nhau | Accounting audit đã khớp ba UNKNOWN: CPU/child-wall≈1,030; native CPU mới≈0,9994 ở một success | Không có native-boundary CPU hoặc work counters của UNKNOWN; whole-child không định vị native bottleneck. Không loại frequency/thermal/scheduling cục bộ |
| Historical runs đạt progress/search trajectory khác trước deadline | Cùng input/seed không cung cấp trace hoặc counters bị thiếu | Không thể dựng lại branch/conflict/presolve progress của UNKNOWN từ status và wall alone |
| Logging/callback có ảnh hưởng timing | Một pair OFF→ON có chênh lệch wall; OFF cũng tìm được nghiệm | n=1/mode, order/cache/nhiệt/workload bị confound; chưa tách native logging khỏi callback/file flush. Không có causal estimate |
| MemTotal −4KiB là nguyên nhân | Có diagnostic successes ở cả snapshot−4KiB và snapshot khớp legacy | Không có đối chứng chỉ đổi riêng MemTotal; không chứng minh causal effect hoặc giải thích historical UNKNOWN |

Đây là giả thuyết cần evidence, không là findings yêu cầu sửa Core hoặc nới budget. Số lượng auxiliaries, branches/conflicts/LP iterations không tự chứng minh bottleneck cụ thể. Hiện chưa đủ căn cứ quy UNKNOWN cho presolve, symmetry, quality tiers hoặc một rule cụ thể; quality tiers lịch sử chưa chạy.

## Chốt điều đã chứng minh và khoảng trống UNKNOWN

- **Đã đóng cho đúng mẫu:** witness mapping/hard occupancy/bounds và full auxiliary valuation; có nghiệm compiled model; logging OFF và ON đều tìm được lịch; accounting/context lịch sử có provenance; native CPU boundary đã đo ở một success và khác scope whole-child.
- **Chưa đóng:** native CPU, work/progress counters và phase trajectory của ba UNKNOWN tại deadline; CPU service/frequency/thermal/cache/workload thực tế trong các interval đó. Các field không được thu không thể tái dựng từ status/wall/load. Historical pre-context có trong journal START; post-context của chúng và single trace thiếu với reason, không lấy context hiện tại bù vào.
- **Chưa đủ căn cứ:** kết luận UNKNOWN do compiler/rule/symmetry/presolve/logging/MemTotal, tuyên bố đã sửa nguyên nhân, hứa60s luôn đủ hoặc đổi default/budget/guards. Counters và lịch cuối giống nhau không chứng minh mọi search trajectory giống nhau; n=1/mode không cho causal estimate/SLA.
- **Ranh giới vận hành:** giữ ba UNKNOWN, score null/quality NOT_EVALUATED/tiers NOT_RUN, failed63 và campaign108 receipts nguyên vẹn; không chạy thêm để ép tái hiện UNKNOWN hoặc tự sửa Core. Việc thiếu historical telemetry được giữ là giới hạn của kết luận, không biến thành một nguyên nhân đã xác định.

## Kiểm chứng lượt cập nhật native CPU

- Standard-library read-only asserts kiểm15static +15auxiliary +17single +35pair +19CPU manifest digests (**101entries**, có thể trùng files, không phải independent samples), native CPU arithmetic, saved assignments/full score và common work counters của bốn diagnostic successes: PASS.
- **168protected hashes** từ archived execution ledger của native CPU plan còn khớp. Old raw artifacts/candidates/receipts/manifests không bị ghi lại; chỉ file tổng hợp này thay đổi.
- Không import Core/OR-Tools, rebuild, rerun validator/scorer/probe hoặc đo runtime/context mới. Những giá trị trình bày ở đây là evidence đã lưu từ runs được duyệt trước đó.
- Không chạy pytest trong lượt docs-only; full suite có native solves trái yêu cầu. 109fake tests PASS của native CPU task là kết quả lịch sử, không được ghi thành tests chạy mới ở đây.

Lệnh thực chạy: `uv sync --locked --extra solver` PASS; `uv run ruff check .` PASS; `uv run ruff format --check src tests benchmarks` PASS (54 files); `uv run mypy` PASS (27 Core source files); `git diff --check` PASS. Standard-library assertions về101manifest entries, CPU arithmetic, comparisons,168protected hashes và local links/one-file scope PASS. Không chạy pytest hoặc solver/search/profiling trong lượt này.
