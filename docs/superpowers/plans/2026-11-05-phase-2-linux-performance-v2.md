# Phase 2 — kế hoạch đo hiệu năng Linux theo acceptance v2 (policy 0.4)

Ngày 2026-11-05. Trạng thái: **DRAFT — G1–G10 ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT theo đề xuất ngày 2026-11-05; Task 1–5 ĐÃ TRIỂN KHAI trong working tree, chờ duyệt commit (xem §11); preflight, bundle thật, pilot và campaign chưa thực hiện, mỗi bước vẫn cần ủy quyền riêng (§8).** Base `5d685f9` trên nhánh
`work/phase2a-operational-completion` (source/tests trùng `main` tại `486c6a1`).

Thực hiện E2 của [đánh giá Phase 2](../../phase-2-status-assessment.md): mở rộng benchmark sang policy 0.4
(S01–S11, có và không có hard) cho campaign Linux tiếp theo, không đổi budget hay gate an toàn. Tiêu chí
lấy từ [acceptance v2](../../phase-2a-acceptance-v2-draft.md) (D1–D3 đã duyệt). Phép đo, dataset gốc và
supervisor kế thừa [protocol v1](2026-10-26-phase-2a-operational-validation.md).

Tài liệu này chỉ là kế hoạch. Lượt soạn không sửa `benchmarks/`, `src/`, `tests/`, gate, budget hay pins;
không sinh dataset, không solve, không chạy pilot/campaign, không commit/push. Mọi lựa chọn dataset, rule,
priority và quy mô ma trận dưới đây là **INFERRED — đề xuất để duyệt**, không phải chính sách trường hay
SLA. Duyệt kế hoạch không phải ủy quyền chạy campaign.

## 0. Hiện trạng đã kiểm trong source (VERIFIED)

| Điểm | Hiện trạng | Hệ quả |
|---|---|---|
| Generator | `generate_synthetic.py` tạo input 1.1 với `ConstraintConfigV11(policy_version="0.1")`; `_check_witness_profile` đòi đúng S01–S04/GV; manifest `benchmark_schema_version="1.0"` | Không sinh được policy 0.4 |
| Harness | `verify_output` đòi `result.schema_version == "1.2"`; `judge_case` coi BASE/MIXED khác `(0,0,0)` là P NOT_MET; plan đòi đúng 108 primary và pilot `c10-base-s101` | Không nhận output 1.3–1.5; zero vẫn là gate P (trái D1) |
| Pilot gate | `_qualified` cho pilot đòi `performance == "MET"`, nên `[0,5,120]` chặn primary (0/108, STOPPED) | D2 cần gate mới |
| Identity lịch sử | `_source_ids()` băm `run_benchmarks.py`, `generate_synthetic.py`, `uv.lock`, `windows_runtime.py`, `native_trace.py`; `aggregate_linux._verify_frozen` dựng lại plan và so `source_ids` → `SOURCE_OR_DATASET_DRIFT` | **Sửa hai file v1 sẽ phá việc kiểm lại evidence v1** |
| Budget | `_BUDGETS`: 10→(60 s, 150 s, 1 GiB), 20→(120, 210, 2 GiB), 40→(180, 270, 4 GiB); reserve 2 GiB | Giữ nguyên |
| Guards Core | 10 000 slots/occurrences, 100 000 placements, 1 000 000 occupancy terms; S05 `MAX_SPREAD_PAIRS = 20 000` | Giữ nguyên; chạm guard là RESOURCE_LIMIT/UNKNOWN, không nới |
| Máy lịch sử | Campaign Linux cũ chạy trên máy người dùng (i7-12700H, 20 logical CPUs, ~39 GiB RAM) | Raw evidence không có trong cloud clone |

## 1. Nguyên tắc

- **Không sửa tooling v1.** Code mới nằm trong module mới (§7). Module mới chỉ import các hàm có sẵn
  (`_construct`, supervisor, `classify_run`…) mà không sửa file v1. Như vậy hash v1 giữ nguyên và
  `aggregate_linux.py` vẫn kiểm lại được evidence lịch sử. Evidence, verdict và campaign v1 giữ nguyên;
  không resume campaign v1.
- **Không sửa product code.** Benchmark chạy bằng installed wheel, qua CLI công khai. Không thêm witness
  hint, callback hay rule mới, không sửa semantics S01–S11.
- **Giữ an toàn đo đạc như v1.** Mỗi run một process mới, workers 1, seed 42, guards mặc định, đo đúng PID
  (`os.wait4`), kiểm reserve RAM trước mỗi run, no retry, journal và receipts.
- **Protocol ID mới** `phase2-linux-v2`, dataset schema `2.0` và record schema `2.0`, để không lẫn
  record v2 với record v1.

## 2. Dataset policy 0.4

### 2.1 Tái dùng khung v1

Giữ quy mô 10/20/40 lớp, 6 ngày × 2 buổi × 5 tiết, demand `[4,4,4,4,4,3,3,2,2]`, split, seeds 101/102/103
và bốn profile BASE/MIXED/TIGHT/UNSAT_CAPACITY. Witness được dựng bằng chính `_construct` của v1, gọi qua
import. Availability, locks và phòng dùng cùng quy tắc v1, được viết lại trong module mới để không phụ
thuộc vào `_configure` (hàm này gắn cứng policy 0.1). Sau đó áp cấu hình rule 0.4 dưới đây. Mọi tham số
được suy ra **từ witness đã kiểm** trên input cuối, và witness phải hard-valid với mọi rule hard.

### 2.2 Hai biến thể rule (G2)

| Mã | Biến thể **SOFT** (mọi rule soft) | Biến thể **HARD** | Tham số suy từ witness | Priority SOFT (G3) |
|---|---|---|---|---|
| S01 | 1 instance/GV | soft | 1 ô available không dùng | P1 |
| S02 | 1/GV | **hard** | `limit` = tải max/buổi của GV trong witness; AM+PM | P1 |
| S03 | 1/GV | **hard** | `limit` = tải max/ngày; TIGHT-SOFT dùng `ceil(D/6)−1` như v1 | P2 |
| S04 | 1/GV | soft | window [2,4], AM+PM | P3 |
| S05 | 1 instance/requirement có ≥ 2 component | **hard** | `min_day_gap` = khoảng ngày nhỏ nhất giữa các component trong witness; requirement có hai component cùng ngày bị bỏ (đếm và ghi manifest) | P2 |
| S06 | 1 instance toàn cục | **hard** | `limit` = số tiết max/ngày của một lớp+môn trong witness | P1 |
| S07 | 1/GV | soft | 1 ô available không dùng, **khác** ô S01 (tránh `OVERLAPPING_RULES` của S01↔S07) | P2 |
| S08 | 1/GV | soft | AM+PM (không có ngưỡng) | P3 |
| S09 | 1/GV | soft | `limit` = chuỗi tiết trống dài nhất của GV trong witness | P2 |
| S10 | 1/GV nếu witness có ≥ 1 buổi rảnh | soft | `unit="session"`, `target` = số buổi rảnh của GV trong witness; GV có 0 buổi rảnh thì bỏ (đếm) | P2 |
| S11 | 1/GV | soft | AM+PM (không có ngưỡng) | P3 |

- Mọi `weight = 1` khai báo tường minh. Rule teacher-scope dùng một GV cụ thể. Không instance nào trùng
  family (Core sẽ từ chối).
- S01 dùng 1 ô thay vì 2 như v1, vì TIGHT chỉ có đúng 2 ô available ngoài witness: S01 và S07 mỗi rule
  lấy một ô.
- **HARD** không bật S01 hard vì S01 hard trùng family với S07 soft (`SHARED_SLOT_FAMILY`). S04 hard và
  S07–S11 hard không có (S07–S11 không có hard mode). Ở biến thể HARD, priority của các rule soft còn lại
  giữ như cột SOFT.
- Ở TIGHT-HARD, S03 hard dùng giới hạn từ witness, nên không có `p2_lower_bound` khai báo. Độ khó đến từ
  availability và locks như v1.
- **Occupied work** (G4): ở MIXED/TIGHT, mỗi GV có 1 ô `occupied_work` nằm ngoài availability. Lý do: để
  benchmark đi qua đường occupied work của S08/S10. BASE không có, vì ở BASE availability là `null`.
- Không có ô `can_teach=false` hay timed calendar có buổi chồng giờ, nên GAP_TIMELINE không xảy ra.
  MIXED/TIGHT dùng timed calendar không chồng giờ như v1.

### 2.3 Sự thật nền và witness score

- Witness vector được tính bằng evaluator độc lập trên input cuối và ghi vào manifest, cùng breakdown
  theo rule.
- S08 và S11 không có ngưỡng, nên witness thường có penalty dương. Vì vậy **không mặc định optimum = 0**
  (G5). `known_optimum = [0,0,0]` chỉ khi witness vector đúng bằng 0. Ngoài ra là `null`, và benchmark
  zero là NOT_APPLICABLE.
- UNSAT_CAPACITY: tạo từ BASE như v1 (một lớp 30 tiết, 29 ô). Có ở cả hai biến thể. Kỳ vọng
  INFEASIBLE từ precheck, `solver_executed=false`, kể cả khi có rule hard.
- Generator dừng với `DATASET_GENERATION_FAILED` nếu:
  - witness không hard-valid với rule hard;
  - S01 và S07 không chọn được ô;
  - contract hoặc capability từ chối input;
  - S05 vượt guard cặp.

  Không đổi seed để né lỗi.

### 2.4 Ma trận (G6)

3 quy mô × 4 profile × 3 seed × 2 biến thể = **72 datasets**. Mỗi dataset chạy 3 repeats, tức
**216 primary**: 162 known-feasible và 54 UNSAT.

| Tổng cấu hình (không phải ước lượng thời lượng) | Giá trị |
|---|---|
| CP-SAT budget tối đa của 162 run feasible | 54 × (60 + 120 + 180) s = 19 440 s ≈ 5,4 h |
| Trần watchdog của 162 run feasible | 54 × (150 + 210 + 270) s = 34 020 s ≈ 9,45 h |

UNSAT thường dừng ở precheck. Phương án nhỏ hơn: 1 repeat cho HARD, tổng 144 primary. Không đề xuất
phương án này, vì nó làm hai biến thể có độ phủ khác nhau.

### 2.5 Prepare (ngoài run đo)

Trước khi seal, với mỗi dataset, chạy validate input/capability. Sau đó đếm placements, occupancy terms
và số cặp S05; số biến của S08/S09 lấy theo công thức của `gaps.py`. Các số này ghi vào manifest
`dimensions`. Một dataset chạm guard vẫn ở lại trong ma trận. Kết quả kỳ vọng của nó được ghi là
RESOURCE_LIMIT, và mẫu số không bị giảm. Prepare không gọi CP-SAT solve.

## 3. Harness nhận output 1.2–1.5 và ScoreReport 1.0–1.2

Bộ kiểm v2 (`verify_output_v2`) nhận input 1.0 hoặc 1.1. Nó suy cặp version kỳ vọng **từ input**, không
từ result:

| Input | Output kỳ vọng | ScoreReport kỳ vọng |
|---|---|---|
| 1.0 | 1.1 | 1.0 |
| 1.1 / policy 0.1 | 1.2 | 1.0 |
| 1.1 / policy 0.2 | 1.3 | 1.0 |
| 1.1 / policy 0.3 | 1.4 | 1.1 |
| 1.1 / policy 0.4 | 1.5 | 1.2 |

- Bảng được kiểm lại khi chạy bằng `QUALITY_POLICY` và `SCORE_VERSION` của **wheel đã cài**. Nếu lệch,
  trả ENVIRONMENT_BLOCKED ngay ở preflight; không chép cứng rồi tin.
- Version sai cặp → OUTPUT_INVALID.
- Error envelope 1.0, ánh xạ exit/status, fingerprint, "error không lộ lịch" và kiểm độc lập qua
  `validate-schedule` và `evaluate-score` giữ như v1.
- ScoreReport được parse theo version. Breakdown giữ `unit` của từng rule (S10 theo `unit`).
- Campaign chỉ dùng policy 0.4. Các cặp khác chỉ để test hồi quy bộ kiểm.

## 4. Phân loại H/Q/P/zero (acceptance v2)

Mỗi run có `case-verdict` v2 gồm bốn trục độc lập:

| Trục | Nhãn | Quy tắc |
|---|---|---|
| **H** | PASS / FAIL / NOT_APPLICABLE | H1–H6 của v2. FAIL khi: hard/score/proof sai; known-feasible trả INFEASIBLE, INPUT_INVALID, UNSUPPORTED hoặc MODEL_INVALID; UNSAT không đúng kỳ vọng; vector có proof prefix tệ hơn witness; claim LEXICOGRAPHIC_OPTIMAL tệ hơn witness; dưới `p2_lower_bound` (chỉ TIGHT-SOFT). NOT_APPLICABLE khi không có lịch (UNKNOWN, watchdog, resource) |
| **Q** | REVIEW_REQUIRED / NO_SCHEDULE / NOT_APPLICABLE (UNSAT), kèm thông tin BETTER/EQUAL/WORSE so witness | Chưa có quality profile (G7), nên mọi lịch hợp lệ là REVIEW_REQUIRED. Ghi vector, proof prefix, tier NOT_RUN, breakdown theo rule/unit. Không có nhãn ACCEPTED |
| **P** | MET / NOT_MET / INCOMPLETE / NOT_APPLICABLE | MET khi: H PASS, có lịch, measurement OK, launch-to-exit ≤ watchdog, peak RSS ≤ target. **Score nonzero không ảnh hưởng.** NOT_MET khi known-feasible không có lịch hoặc vượt giới hạn mà đo đủ. INCOMPLETE khi thiếu measurement hoặc thiếu run. UNSAT: NOT_APPLICABLE (đúng hay sai do H quyết định) |
| **ZERO** | MET / NOT_MET / NOT_APPLICABLE | Chỉ cho dataset có `known_optimum = [0,0,0]`. Báo riêng, không phải gate |

Ở mức campaign, P đạt khi đủ 216 outcomes và measurements, 162/162 known-feasible có lịch hard-valid
trong giới hạn, và 54/54 UNSAT đúng. Thiếu run nào thì là INCOMPLETE. Kết luận tách theo biến thể, quy mô
và profile, với n = 3 mỗi fingerprint:

- không tính P95 hay SLA;
- median chỉ là conditional-on-success, có kèm số failure;
- không gộp các fingerprint khác nhau;
- timeout là censored.

## 5. Sealed plan, pilot, campaign

Plan v2 gồm warmup, **2 pilot** và 216 primary. Pilot là `c10-base-s101-soft` và `c10-base-s101-hard`,
repeat 0. Pilot không được tính vào primary. Thứ tự primary được shuffle bằng seed 2026 theo từng repeat
và đóng băng.

Seal ghi các thông tin sau:

- hash `plan.json` và `environment.json`;
- bundle SHA;
- `source_ids` mới: controller, generator, verifier và aggregator v2, cùng các file v1 được import;
- wheel SHA và lock SHA;
- preflight manifest SHA;
- bảng budget.

Mọi drift → STOPPED hoặc BLOCKED, không chạy tiếp.

Trình tự (mỗi bước cần ủy quyền như §8):

1. **Preflight** trên máy chạy: core tests; build wheel một lần; hai venv sạch (có và không OR-Tools);
   smoke solve 0.4 → 1.5, rồi validate và evaluate Score 1.2; kiểm bảng §3; kiểm reserve RAM. Tái dùng
   `phase2a_preflight.py` không sửa, và thêm bước smoke 0.4 trong module mới.
2. **Generate + validate bundle** (72 datasets), sau đó prepare (§2.5). Đây là bước không solve.
3. **Seal**, sau đó warmup (không đo).
4. **Pilot** (2 run). Pilot đạt khi harness COMPLETE, H PASS, có lịch hard-valid, measurement OK, trong
   watchdog và RSS (**D2**). Q REVIEW_REQUIRED và ZERO NOT_MET/NOT_APPLICABLE vẫn cho qua. Pilot không có
   lịch thì dừng: pilot là phép kiểm harness, không phải mẫu đo.
5. **Primary** 216 run tuần tự, no retry. Chỉ chạy tiếp sau khi người dùng xem pilot và cho phép.
6. **Aggregate + report** (v2): `docs/phase-2-linux-performance-report.md`.

## 6. Gate dừng

| Gate | Hành động |
|---|---|
| Identity drift (source, wheel, lock, bundle, plan, environment, preflight) | STOPPED trước run |
| Không đủ reserve 2 GiB trước run | ENVIRONMENT_BLOCKED, dừng; không chạy rồi gọi là OOM |
| Measurement khác OK, `REAP_UNCONFIRMED`, exit code thiếu | NEEDS_REVIEW hoặc STOPPED |
| CRASH, OUTPUT_INVALID, MEASUREMENT_BLOCKED, ENVIRONMENT_BLOCKED | STOPPED |
| H FAIL ở bất kỳ run nào (kể cả UNSAT sai) | STOPPED, giữ evidence |
| Pilot không đạt điều kiện bước 4 của §5 | STOPPED, primary không mở |
| CANCELLED (người dùng ngắt) | Dừng; resume chỉ khi có lệnh tường minh |
| UNKNOWN, RESOURCE_LIMIT, WATCHDOG_TIMEOUT, RESOURCE_STOP có measurement đủ | **Không dừng**: ghi P NOT_MET, tiếp run sau |
| Score nonzero, WORSE so witness, ZERO NOT_MET | Không dừng, không phải lỗi |

Không nới budget, guards hay hard; không giảm mẫu số; không đổi profile sau khi thấy kết quả. Một
campaign STOPPED giữ nguyên trạng. Muốn chạy lại phải dùng campaign ID mới, và cần ủy quyền mới.

## 7. Task khi được duyệt (TDD, chưa thực hiện)

| Task | File mới | Nội dung và test RED trước |
|---|---|---|
| 1 | `benchmarks/generate_phase2.py`, `benchmarks/tests/test_generate_phase2.py` | Hai biến thể. Test: tham số từ witness; S01 khác S07; witness hard-valid với rule hard; witness vector bằng evaluator; `known_optimum` chỉ khi vector 0; S05/S10 bỏ đúng và có đếm; occupied ngoài availability; deterministic bytes; UNSAT vẫn INFEASIBLE; altered input → generation failed |
| 2 | `benchmarks/run_phase2.py` (import supervisor v1), `benchmarks/tests/test_run_phase2.py` | `verify_output_v2` với bảng §3, gồm mọi cặp sai. `judge_case_v2` H/Q/P/zero: nonzero vẫn P MET; UNKNOWN là P NOT_MET; H FAIL thì dừng. Plan v2 có 216 + 2 pilot, seal, gate §6, pilot theo D2 |
| 3 | `benchmarks/aggregate_phase2.py` và test | Mẫu số đủ; null không thành 0; tách biến thể/quy mô/profile; censored timeout; Q/zero báo riêng |
| 4 | Smoke 0.4 trong `run_phase2.py` | Preflight installed wheel 0.4 → 1.5, Score 1.2, venv không OR-Tools |
| 5 | — | `uv run --extra solver pytest tests benchmarks/tests`, ruff, format, mypy. **Thêm regression:** `aggregate_linux._verify_frozen` vẫn qua với hash v1 (`run_benchmarks.py` và `generate_synthetic.py` byte-identical so với `5d685f9`) |

Không thêm benchmarks vào wheel/sdist, không thêm dependency. `benchmarks/artifacts/` vẫn local và không
commit.

## 8. Ranh giới phê duyệt

| Bước | Cần duyệt riêng |
|---|---|
| A. Duyệt kế hoạch và G1–G10 | Có (lượt này dừng ở đây) |
| B. Task 1–5 trong working tree, chạy checks | Có |
| C. Commit/push tooling | Có |
| D. Preflight, generate/prepare bundle trên máy chạy | Có |
| E. Seal, warmup, pilot | Có |
| F. Primary 216 run | Có, sau khi xem pilot |
| G. Report, commit report | Có |

## 9. Quyết định cần duyệt

- [x] **G1 — Module mới, không sửa tooling v1.** *(Đề xuất: chọn. Bắt buộc nếu muốn giữ khả năng kiểm
  lại evidence v1.)*
- [x] **G2 — Hai biến thể SOFT/HARD như §2.2**, HARD = S02/S03/S05/S06 hard. *(Đề xuất: chọn.)*
- [x] **G3 — Priority SOFT**: P1 S01/S02/S06; P2 S03/S05/S07/S09/S10; P3 S04/S08/S11; weight 1.
  *(Đề xuất: chọn. Đây là cấu hình benchmark, không phải policy trường.)*
- [x] **G4 — Occupied work 1 ô/GV ở MIXED/TIGHT.** *(Đề xuất: chọn.)*
- [x] **G5 — Không ép witness zero**: S08/S11 giữ penalty thật; zero benchmark chỉ áp dụng khi witness =
  0. Phương án khác là viết lại cách dựng witness để không có tiết trống; phương án này đổi dataset gốc
  nên không đề xuất. *(Đề xuất: chọn.)*
- [x] **G6 — Ma trận 72 datasets × 3 repeats = 216 primary**, budget/watchdog/RSS/reserve giữ nguyên.
  *(Đề xuất: chọn.)*
- [x] **G7 — Q = REVIEW_REQUIRED cho mọi lịch** (chưa có quality profile). Profile, nếu có, phải chốt trước
  seal. *(Đề xuất: chọn.)*
- [x] **G8 — Gate dừng §6**: H FAIL hoặc an toàn → dừng; P NOT_MET → tiếp. *(Đề xuất: chọn.)*
- [x] **G9 — Máy chạy.** *(Đề xuất: máy Linux của người dùng, cùng máy với campaign lịch sử nếu được;
  workload ghi UNCONTROLLED nếu không kiểm soát được.)* Container cloud bị thu hồi khi idle, CPU không rõ
  và dùng chung, nên chỉ dùng cho Task 1–5 và smoke nhỏ, không dùng cho số đo P.
- [x] **G10 — Hai pilot (SOFT và HARD) phải cùng đạt** trước khi xin mở primary. *(Đề xuất: chọn.)*

E5 (chính sách version) không ảnh hưởng kế hoạch này, vì kế hoạch không tạo version product mới.

## 10. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Model 40 lớp với S08–S11 cho 60 GV có thể vượt budget, guard hoặc RSS | Prepare ghi dimensions trước. Chạm guard hoặc vượt giới hạn là kết quả P NOT_MET hợp lệ, không nới |
| Kết quả không so được với v1 | Rule set, priority và protocol đều khác. Báo cáo không đặt cạnh số v1 như cùng bài |
| Witness có ô available không đủ cho S01 và S07 | Generator dừng rõ; TIGHT được thiết kế đúng 2 ô |
| Import hàm private v1 gắn với chi tiết nội bộ | Ghi hash file v1 trong `source_ids` v2; test byte-identical |
| Campaign dài (trần watchdog ~9,45 h cho phần feasible) | Journal/resume theo run ID như v1; không retry |

## 11. Ghi nhận thực hiện Task 1–5 (2026-11-05)

Được ủy quyền "Triển khai Task 1–5". Chỉ thêm file mới; không sửa `src/`, tooling v1, gate, budget hay pins.
Không sinh bundle thật, không chạy preflight, pilot hay campaign.

| File mới | Nội dung |
|---|---|
| `benchmarks/generate_phase2.py` | Generator policy 0.4, hai biến thể, 72 datasets. Witness dựng bằng `_construct` của v1 (import); availability/locks trùng v1 |
| `benchmarks/run_phase2.py` | Bảng version, `verify_output_v2`, `judge_case` H/Q/P/zero, plan v2 (216 + 2 pilot), gate §6, controller, preflight v2 và smoke 0.4. Supervisor, headroom, journal và owner lock import nguyên từ v1 |
| `benchmarks/aggregate_phase2.py` | Tổng hợp chỉ đọc. Mẫu số đủ; null không thành 0; thời gian conditional-on-success; timeout là censored; không P95 |
| `benchmarks/tests/test_generate_phase2.py`, `test_run_phase2.py`, `test_aggregate_phase2.py`, `test_phase2_v1_frozen.py` | 70 test mới |

Lệnh và kết quả:

| Lệnh | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS (lock không đổi) |
| `uv run --extra solver pytest tests benchmarks/tests` | **1341 passed, 8 skipped** (trước thay đổi: 1271 passed, 8 skipped); 8 skip vẫn là Windows/opt-in |
| `uv run ruff check .`, `uv run ruff format --check src tests benchmarks` | PASS |
| `uv run mypy` | PASS (30 source files; phạm vi mypy của dự án chỉ gồm `src/`, `benchmarks/` không được kiểm kiểu, như v1) |
| Test byte-identical | 6 file v1 trùng SHA-256 tại `5d685f9` |

Kiểm trong bộ nhớ (không ghi bundle, không solve): cả 72 dataset sinh và tự kiểm được trong khoảng 2 phút.

Sai khác so với kế hoạch và các phát hiện:

- **TDD:** Task 1 và Task 3 viết test trước và chạy RED (module chưa có). Task 2 lại viết code trước test. Để
  bù, đã mutation-check sáu gate, mỗi lần tạm sửa một gate rồi khôi phục: zero làm gate P, cặp version
  cứng 1.2, bỏ dừng khi H FAIL, bỏ gate pilot, bỏ kiểm thứ tự, bỏ lower bound. Cả sáu đều làm test đỏ.
- **Zero NOT_APPLICABLE ở cả 72 datasets:** S08/S11 làm P3 của witness dương (c10 ≈ 72, c40 ≈ 275), nên
  không dataset nào có `known_optimum`. Đây là hệ quả dự kiến của G5. Benchmark zero của v1 vẫn là
  hồ sơ riêng.
- **S05 bỏ khoảng một nửa requirement nhiều component** (ví dụ 19/40 ở c10-s101), vì witness đặt các
  component cùng ngày. S10 bỏ các GV không có buổi rảnh (4–18 GV/dataset). Số bỏ được ghi trong
  `omitted` của manifest.
- **Input 1.0 → output 1.1 không được hỗ trợ:** bộ kiểm v2 trả `INPUT_VERSION_UNSUPPORTED`. Campaign
  chỉ dùng 0.4; bảng §3 vẫn kiểm đủ bốn cặp 0.1–0.4 với Core đã cài.
- **Schema record:** `RunRecord` dùng lại model v1 (schema 1.0). Verdict, plan, state, journal và seal
  dùng 2.0.
- **Kiểm bundle khi prepare:** watchdog 1 800 s và 2 GiB, vì kiểm bundle là tái sinh 72 dataset. Đây là
  giới hạn cho tooling, không phải budget solve.
- **Prepare §2.5:** manifest ghi dimensions của v1 (placements, occupancy terms, tokens) và số cặp S05;
  chưa đếm biến S08/S09.
- **Warmup** vẫn là fixture tiny 0.1 như v1. Smoke 0.4 là bước preflight riêng, và preflight chạy thêm
  `benchmarks/tests`.
- **Chưa chạy end-to-end** `preflight`, `prepare` và `execute_campaign`, vì cần wheel cài đặt và ủy quyền
  bước D/E. Test chỉ kiểm rằng plan chưa seal không chạy run nào. Test smoke dùng interpreter dev cho cả
  hai nhãn solver/no-solver.
