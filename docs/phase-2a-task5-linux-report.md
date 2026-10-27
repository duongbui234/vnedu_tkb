# Phase 2A Task 5 — tổng hợp Linux

**Task 5 Linux: đã tổng hợp evidence lịch sử. Pilot performance: NOT_MET. Correctness: không có FAIL quan sát được; coverage INCOMPLETE vì 27 lượt UNKNOWN không có lịch để kiểm. Windows BLOCKED; chưa nghiệm thu hai OS hoặc production.**

> **Chú thích lịch sử:** Các mô tả “chưa có trace”, “chưa build” và các đề xuất chưa thực hiện bên dưới phản ánh thời điểm ghi từng phần của báo cáo. Chẩn đoán về sau được tổng hợp riêng tại [bản tổng hợp evidence TIGHT10](tight10-evidence-synthesis.md); không thay đổi campaign 108 primary, failed=63, ba repeats/fingerprint, các thống kê hoặc Windows BLOCKED trong báo cáo này.

## Phạm vi và provenance

- Chỉ đọc campaign `linux-pilot-20261027-v1`: 108 primary = 36 datasets × 3 repeats, cộng 2 receipts warmup/pilot được kiểm nhưng loại khỏi thống kê primary. Không chạy lại solver campaign, đổi input, seed, workers, budget hoặc guard.
- Frozen plan SHA256: `6b8a324560b1857555f686a955f5af79468e5f80a00d830466b9253e648a9e61`; source HEAD lúc freeze `5b13ca4`, launch primary `914e62a`. Tooling Task 5 dựa trên `9fa1791`.
- Wheel SHA256: `1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9`; uv.lock SHA256: `e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084`.
- Máy lịch sử: Intel Core i7-12700H, 20 logical CPUs, Linux x86_64 kernel7.0.0-38-generic; frozen RAM `40745240 KiB`; Python3.12.3, OR-Tools9.15.6755. Workload UNCONTROLLED, competing workload UNKNOWN. Không suy ảnh hưởng OS hoặc số worker từ campaign này.
- Workers1, solver seed42; generator seeds101/102/103. 10/20/40 lớp lần lượt 15/30/60 GV, 260/520/1040 occurrences, 300/600/1200 tiết, 60 slots. BASE không phòng; MIXED/TIGHT có 2/4/8 phòng.

| Lớp | Solver budget (s) | Watchdog launch→exit (s) | Peak child RSS target |
|---|---:|---:|---:|
| 10 | 60 | 150 | 1 GiB |
| 20 | 120 | 210 | 2 GiB |
| 40 | 180 | 270 | 4 GiB |

## Kiểm tra tính toàn vẹn

- Đối chiếu lại **684 file** trong inventory của audit Task4: tất cả SHA256 khớp, không sửa evidence gốc. Inventory SHA256 `23fe910ae2595ee55c74a6582ef255465c6318bfd31914a9d33204651a37e7b8`.
- Aggregator kiểm seal/plan/environment, bundle/input/witness/manifest hashes, frozen order/membership, source controller/generator/lock, preflight manifest, 110 terminal receipts và file hashes được receipts tham chiếu; journal START/TERMINAL và headroom theo mỗi run; state108/108, pending0, failed63.
- Kiểm runtime identity/options/limits đã ghi cho từng run; paths phải trỏ đúng artifacts được receipts bảo vệ. Tái chạy **chỉ** `validate-schedule`/`evaluate-score` trên lịch đã lưu, kiểm contract/fingerprint/error status và recompute case verdict. 110 outputs được đối chiếu; mọi verdict khớp. Không tạo proof tối ưu mới từ metadata.
- Known machine drift lịch sử: MemTotal giảm4KiB trong audit sau execution. Không sửa frozen identity, không gọi/bypass execution gate. Aggregator báo `NOT_ASSESSED_NO_EXECUTION` cho current execution gate; không xác nhận runtime/máy hiện tại đủ điều kiện chạy mới.
- Hashes là consistency evidence trong workflow local tin cậy, không attestation chống người có thể sửa toàn bộ manifests. Tooling yêu cầu paths local lịch sử vẫn tồn tại; không hỗ trợ relocate bundle.

## Correctness, performance và quality

| Chỉ số | Kết quả và denominator |
|---|---|
| Thu thập primary | 108/108 COMPLETE, 0 pending |
| Lịch trả về | 54/81 known-feasible; 54/54 hard-valid và score recomputation khớp |
| Correctness | 81 PASS = 54 lịch + 27 UNSAT đúng; 27 NOT_ASSESSED; 0 FAIL |
| Solver status | 18 OPTIMAL, 36 FEASIBLE, 27 UNKNOWN, 27 INFEASIBLE |
| Pilot performance | 18/81 MET; 63/81 NOT_MET; 27 UNSAT NOT_APPLICABLE |
| Quality so witness trên đúng input | 18 EQUAL, 36 WORSE, 27 NO_SCHEDULE; 27 UNSAT NOT_APPLICABLE; 0 BETTER |
| Measurement | 108/108 OK; 0 crash/watchdog/resource stop; 0 thiếu launch/RSS measurements |
| Qualification runner | 45/108 đạt = 18 known-feasible MET + 27 UNSAT đúng; **63/108 không đạt** |

`failed=63` được giữ nguyên, phân rã thành **27 NO_SCHEDULE** (TIGHT mọi cỡ, UNKNOWN) và **36 ZERO_TARGET_NOT_MET** (BASE/MIXED 20/40 lớp, có lịch hard-valid nhưng vector khác0). Trong campaign này hai nhóm rời nhau; code vẫn đếm causes không loại trừ nhau nếu một run tương lai có nhiều nguyên nhân. Không gọi chúng là63correctness failures. UNKNOWN không được đổi thành INFEASIBLE, PASS, score0 hoặc loại khỏi denominator.

Tất cả108runs ở dưới watchdog/RAM target. Đây là kết quả gate trên mỗi run, không là thống kê latency gộp. Không nới budget hoặc giảm profile để làm đẹp tỷ lệ.

| Lớp/profile | n | Status | Lịch hợp lệ | Performance | Quality so witness |
|---|---:|---|---:|---|---|
| 10/BASE | 9 | OPTIMAL×9 | 9 | MET×9 | EQUAL×9 |
| 10/MIXED | 9 | OPTIMAL×9 | 9 | MET×9 | EQUAL×9 |
| 10/TIGHT | 9 | UNKNOWN×9 | 0 | NOT_MET×9 | NO_SCHEDULE×9 |
| 10/UNSAT_CAPACITY | 9 | INFEASIBLE×9 | 0 | NOT_APPLICABLE×9 | NOT_APPLICABLE×9 |
| 20/BASE | 9 | FEASIBLE×9 | 9 | NOT_MET×9 | WORSE×9 |
| 20/MIXED | 9 | FEASIBLE×9 | 9 | NOT_MET×9 | WORSE×9 |
| 20/TIGHT | 9 | UNKNOWN×9 | 0 | NOT_MET×9 | NO_SCHEDULE×9 |
| 20/UNSAT_CAPACITY | 9 | INFEASIBLE×9 | 0 | NOT_APPLICABLE×9 | NOT_APPLICABLE×9 |
| 40/BASE | 9 | FEASIBLE×9 | 9 | NOT_MET×9 | WORSE×9 |
| 40/MIXED | 9 | FEASIBLE×9 | 9 | NOT_MET×9 | WORSE×9 |
| 40/TIGHT | 9 | UNKNOWN×9 | 0 | NOT_MET×9 | NO_SCHEDULE×9 |
| 40/UNSAT_CAPACITY | 9 | INFEASIBLE×9 | 0 | NOT_APPLICABLE×9 | NOT_APPLICABLE×9 |

### Profile Z — BASE/MIXED

- 10lớp:18/18 đạt vector(0,0,0), metadata LEXICOGRAPHIC_OPTIMAL với prefix[1,2,3]. Known zero witness cộng penalty không âm xác nhận zero là optimum cho đúng bài đó; không suy mọi bài trường đều tối ưu được.
- 20lớp:18/18 có lịch nhưng chưa zero; BASE9/9 prefix rỗng. MIXED:5/9 prefix[1,2],4/9 prefix[1]; các điểm/bounds của tiers chưa proof vẫn được giữ ở JSON, không gọi điểm đã tính là điểm đã chứng minh.
- 40lớp:18/18 có lịch; prefix rỗng. Quality stage P1 trả UNKNOWN sau feasibility đã có incumbent nên top-level FEASIBLE được giữ đúng. Không đánh đồng raw UNKNOWN ở tier với top-level UNKNOWN không có lịch.
- Không có scalar score trung bình/gộp tiers hoặc so độ đẹp giữa khác fingerprint. JSON giữ từng vector/tier status/value/bound/proof và các scalar measurements riêng.

### Profile C — TIGHT

27/27 UNKNOWN ngay feasibility; mọi quality tier NOT_RUN, optimal_prefix rỗng, score=null. Tỷ lệ BETTER/EQUAL/WORSE trên9lượt ở mỗi cỡ là0/0/0, NO_SCHEDULE9/9; không có vector để so witness và không có proof đạt lower bound.

| Dataset | Witness vector | P2 lower bound khi P1=0 | Lịch trả về |
|---|---|---:|---|
| c10-tight-s101 | (0, 78, 0) | 60 | 0/3 |
| c10-tight-s102 | (0, 80, 0) | 60 | 0/3 |
| c10-tight-s103 | (0, 83, 0) | 60 | 0/3 |
| c20-tight-s101 | (0, 158, 0) | 120 | 0/3 |
| c20-tight-s102 | (0, 159, 0) | 120 | 0/3 |
| c20-tight-s103 | (0, 166, 0) | 120 | 0/3 |
| c40-tight-s101 | (0, 321, 0) | 240 | 0/3 |
| c40-tight-s102 | (0, 320, 0) | 240 | 0/3 |
| c40-tight-s103 | (0, 335, 0) | 240 | 0/3 |

Lower bound là bound có điều kiện, không phải điểm optimum đã chứng minh attainable. Witness thuộc đúng input đã freeze là bằng chứng có nghiệm; UNKNOWN trong ngân sách không phủ định witness.

### UNSAT_CAPACITY

27/27 trả INFEASIBLE từ precheck (`solver_executed=false`), đúng chứng cứ30tiết>29slots của một lớp. Không có assignments/score; performance và quality NOT_APPLICABLE. Thời gian các ca này chỉ là launch/precheck/exit, không phải thời gian tìm lịch khả thi.

## Thời gian và RAM theo fingerprint

Mỗi dòng dưới đây là **một dataset/fingerprint riêng, n=3**. Median chỉ tính trong3repeats của dòng đó. Dataset→fingerprint đầy đủ nằm trong JSON cùng input SHA256 và3run IDs. Không tính median/P95 xuyên dataset, profile hoặc cỡ. Thời gian là launch→exit, gồm startup/preprocessing/solve/validation/I/O; parent verification được đo riêng. RSS là peak đúng child từ Linux wait4.ru_maxrss KiB×1024, trình bày MiB (2²⁰bytes), gồm Python/native, không chỉ solver. Không có hard memory cap hay đo TTF; TTF giữ null/NOT_INSTRUMENTED.

| Dataset | Launch→exit min / median / max (s) | Peak RSS max trong3repeats (MiB) |
|---|---:|---:|
| c10-base-s101 | 39.302 / 40.257 / 50.355 | 167.31 |
| c10-base-s102 | 37.495 / 37.603 / 44.859 | 176.06 |
| c10-base-s103 | 27.125 / 27.177 / 32.159 | 166.98 |
| c10-mixed-s101 | 36.537 / 37.146 / 42.937 | 147.18 |
| c10-mixed-s102 | 19.626 / 19.775 / 23.379 | 134.69 |
| c10-mixed-s103 | 25.516 / 25.611 / 30.497 | 133.11 |
| c10-tight-s101 | 60.879 / 60.895 / 60.971 | 127.31 |
| c10-tight-s102 | 60.878 / 60.881 / 60.968 | 126.59 |
| c10-tight-s103 | 60.875 / 60.876 / 60.967 | 124.00 |
| c10-unsat_capacity-s101 | 0.404 / 0.404 / 0.454 | 51.97 |
| c10-unsat_capacity-s102 | 0.403 / 0.404 / 0.860 | 51.97 |
| c10-unsat_capacity-s103 | 0.353 / 0.353 / 0.455 | 51.97 |
| c20-base-s101 | 121.505 / 121.615 / 122.798 | 231.18 |
| c20-base-s102 | 121.528 / 121.564 / 121.686 | 231.36 |
| c20-base-s103 | 121.568 / 121.624 / 121.864 | 229.59 |
| c20-mixed-s101 | 121.414 / 121.417 / 121.609 | 162.43 |
| c20-mixed-s102 | 121.364 / 121.465 / 121.581 | 165.39 |
| c20-mixed-s103 | 121.365 / 121.391 / 121.408 | 163.95 |
| c20-tight-s101 | 121.050 / 121.106 / 121.108 | 138.44 |
| c20-tight-s102 | 121.013 / 121.114 / 121.144 | 137.83 |
| c20-tight-s103 | 121.008 / 121.058 / 121.136 | 139.00 |
| c20-unsat_capacity-s101 | 0.454 / 0.454 / 0.606 | 51.97 |
| c20-unsat_capacity-s102 | 0.504 / 0.504 / 0.606 | 51.97 |
| c20-unsat_capacity-s103 | 0.454 / 0.504 / 0.555 | 51.97 |
| c40-base-s101 | 182.303 / 182.310 / 182.657 | 321.09 |
| c40-base-s102 | 182.405 / 182.623 / 182.712 | 354.75 |
| c40-base-s103 | 182.287 / 182.307 / 182.698 | 312.53 |
| c40-mixed-s101 | 181.785 / 181.876 / 181.959 | 203.84 |
| c40-mixed-s102 | 181.766 / 181.977 / 182.021 | 205.26 |
| c40-mixed-s103 | 181.814 / 181.853 / 182.035 | 206.50 |
| c40-tight-s101 | 181.380 / 181.431 / 181.543 | 169.57 |
| c40-tight-s102 | 181.377 / 181.450 / 182.384 | 171.39 |
| c40-tight-s103 | 181.397 / 181.401 / 181.497 | 167.50 |
| c40-unsat_capacity-s101 | 0.706 / 0.756 / 0.757 | 51.97 |
| c40-unsat_capacity-s102 | 0.655 / 0.656 / 0.807 | 51.97 |
| c40-unsat_capacity-s103 | 0.655 / 0.706 / 0.755 | 51.97 |

JSON cũng có min/median/max/n/missing cho core wall, tổng solver wall, feasibility wall, CPU, parent verification và peak RSS trong cùng fingerprint. Null measurements không được biến thành0 hoặc trộn vào median. Ba repeats/seed42 không đủ P95, SLA, ước lượng reliability production hoặc kết luận deterministic; MIXED20 có score khác giữa repeats.

## Diễn giải bottleneck và quyết định

1. **Quan sát:** TIGHT thất bại ở bước tìm nghiệm, chưa tới tối ưu. Ví dụ `c10-tight-s101` repeat1: feasibility UNKNOWN sau60.001s solver, launch→exit60.971s. Đây là ưu tiên điều tra vì ngay10lớp cũng0/9lượt có nghiệm dù witness hợp lệ. Chưa có profiler/trace nên chưa khẳng định nguyên nhân là presolve, symmetry hay model encoding.
2. **Quan sát:** BASE/MIXED20–40 tốn budget nhưng còn penalty. Ví dụ `c20-base-s101` repeat1 feasibility21.713s, P1 FEASIBLE98.243s với value7/bound0; `c20-mixed-s101` chứng minh P1/P2=0 nhưng P3 FEASIBLE value89/bound0. `c40-base-s101` feasibility110.147s rồi P1 UNKNOWN69.812s, giữ incumbent cũ. Đây là các dấu hiệu từ stage metadata, không phải phép đo time-to-first-feasible.
3. **Quan sát:** không có memory/watchdog gate failure; không đủ chứng cứ ưu tiên tăng RAM hoặc nới timeout. Không sửa thuật toán, bật hint, nới guards hay tuning trong Task5.

**Quyết định đề xuất, chưa thực hiện:** tiếp tục Phase2A bằng một nhiệm vụ chẩn đoán tối thiểu cho TIGHT10 (ưu tiên `c10-tight-s101`), với witness/fingerprint làm căn cứ và regression tái hiện trước khi cân nhắc performance fix. Chưa chấp nhận pilot performance hiện tại, chưa mở2B/2C/repair hoặc UI/API. Chỉ thực hiện search/profiling mới khi có yêu cầu riêng và xử lý execution identity gate đúng policy.

## Tooling, kiểm chứng và cách chạy lại tổng hợp

- Thêm `benchmarks/aggregate_linux.py` riêng để không đổi source hash của controller đã freeze; tái dùng models, receipt/journal readers, `check_case`, independent CLI checks hiện có. Không thêm dependency, export/entrypoint Core hay package contents.
- `summarize` giữ đủ outcomes, counts theo profile, metrics chỉ theo dataset+fingerprint. `aggregate_campaign` yêu cầu108terminal primary+2prerequisites, từ chối bytes/order/policy/verdict/state drift. CLI JSON ra stdout hoặc file mới; exit2 khi evidence thiếu/sai, từ chối ghi vào campaign/bundle/preflight hoặc overwrite file sẵn có.
- Regression: hỗn hợp COMPLETE/UNKNOWN/CRASH/MEASUREMENT_BLOCKED, denominator/nulls/vector gate, fingerprint separation, correctness FAIL, UNSAT exclusion, nhiều failure causes; simulated110receipts, immutable input/output, corruption/missing evidence, independent mismatch, exclusive output, interrupted result missing. Synthetic fixture chỉ mô phỏng execution boundary, không là số đo solver.
- Ruling: `không chạy lại solver` áp dụng cho campaign; full regression suite vẫn chạy tiny fixture solves theo yêu cầu kiểm tra của AGENTS. Không dùng thời gian tests làm benchmark.

```sh
uv sync --locked --extra solver
uv run --extra solver pytest tests benchmarks/tests
uv run ruff check .
uv run ruff format --check src tests
uv run mypy
uv run python -m benchmarks.aggregate_linux \
  /home/ddevtk/code/vnedu_tkb/benchmarks/artifacts/phase2a/pilot-linux-20261027-v1 \
  --output /tmp/tkb-task5-summary.json
```

Cần `TKB_PREFLIGHT_DIR` trỏ tới frozen `preflight-linux-v1` để full regression gồm installed-wheel probes; các probes thuộc tests, không chạy lại108cases. File output phải chưa tồn tại. Frozen paths nằm trong plan cần giữ nguyên. Lệnh aggregation không chạy solve, spawn supervisor hay lấy execution ownership marker.

Evidence Task5 local: `benchmarks/artifacts/phase2a/task5-linux-v1/task5-summary.json` trong worktree `phase2a-task5`, SHA256 `7a3cf9df36e373761f0c96d8687b7215e2a2be51475fa425e9283d1015e9ffe7`; `historical-inventory-check.json` ghi684file hashes match. Raw artifacts vẫn ở checkout gốc, được Git ignore và không commit/upload. Báo cáo Markdown này giữ kết quả chính để review khi không có raw local.

Kiểm chứng cuối và review được ghi ở phần bổ sung bên dưới sau khi lệnh hoàn tất. Không sửa `src/tkb_core`, frozen controller/generator, dependency/uv.lock, nghiên cứu, AGENTS hoặc dữ liệu thật. Windows BLOCKED; Task5 Linux không hoàn thành nghiệm thu vận hành hai OS hay toàn Phase2.

### Kết quả lệnh thực tế trong lượt Task5

| Lệnh | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS; lock không đổi |
| `uv run --extra solver pytest benchmarks/tests/test_campaign_linux.py -q` (baseline) | 64 passed,6.84s |
| `uv run --extra solver pytest benchmarks/tests/test_aggregate_linux.py -q` | 23 passed,37.26s |
| `TKB_PREFLIGHT_DIR=<frozen-preflight> uv run --extra solver pytest tests benchmarks/tests` | **439 passed,91.35s**, không skips; 2 DeprecationWarnings `~` trên bool từ importlib/native dependency context, không suppress |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` | PASS,44files |
| `uv run ruff format --check benchmarks` | PASS,8files |
| `uv run mypy` | PASS,27source files (cấu hình hiện tại chỉ kiểm Core) |
| `uv run python -m benchmarks.aggregate_linux <frozen-campaign> --output <new-task5-summary>` | PASS,110outputs/receipts,108primary; report SHA256 ở trên |
| One-off SHA256 inventory audit | PASS,684files; không ghi raw artifacts |

Đã quan sát RED→GREEN cho import aggregator chưa tồn tại và regression interrupted/no-result; các test integrity bổ sung kiểm fixture synthetic. Lượt đầu của nhóm integrity có3failures vì fixture warmup dùng limits của pilot; sửa đúng fixture theo planned warmup limits, không nới production gate. Không chạy `uv build` hoặc wheel smoke mới vì package/Core/allowlist/dependencies không đổi; full suite bao gồm packaging regression và installed-wheel boundary probes. Không đo benchmark mới hoặc gọi solve campaign.

### Review độc lập và trạng thái bàn giao

Reviewer fresh-context kết luận **Ship trong phạm vi Task5 Linux**, không Critical/Important/Minor findings. Reviewer chạy riêng23aggregator tests PASS/31.61s; tự đối chiếu115hashes trong summary,108outcome rows và36dòng Markdown timing/RSS với evidence. Không chạy solver campaign, không sửa file. Reviewer không chạy độc lập full suite/lint/mypy hoặc kiểm Windows/current execution eligibility; các kiểm tra full-suite/tooling do tác giả chạy và kết quả ghi ở trên. Không có deferred minors hoặc fix pass sau review.

Thay đổi được giữ riêng trên nhánh `feature/phase2a-task5-linux-summary` tại worktree `.worktrees/phase2a-task5` để review/tích hợp; chưa merge main hoặc push. Các rulings: module aggregator riêng giữ frozen runner hash; lịch sử được kiểm bằng frozen evidence thay vì live execution gate; full regression dùng tiny solves được AGENTS yêu cầu, không lặp search campaign. Chi phí/giới hạn tương ứng: phải giữ local paths/source snapshot; không xác nhận được máy hiện tại chạy mới; regression runtime không là benchmark sản phẩm.

### Kế hoạch chẩn đoán tiếp sau Task5

Đã lập [kế hoạch TIGHT10 tĩnh](superpowers/plans/2026-10-27-tight10-static-diagnosis.md) cho `c10-tight-s101`. Đối chiếu planning baseline cho thấy witness hard-valid/score(0,78,0),260/260placements khớp domain;3lượt lịch sử UNKNOWN ở feasibility. Chưa build model/search/profiling hoặc sửa Core; chưa xác định nguyên nhân gốc. Các bước build-only/bounds check trong kế hoạch cần yêu cầu thực hiện riêng.
