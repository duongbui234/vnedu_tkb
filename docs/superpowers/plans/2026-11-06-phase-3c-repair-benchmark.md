# Phase 3C — kế hoạch benchmark repair trên Linux

Ngày 2026-11-06. Trạng thái: **C1–C10 ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-06; bước B–G ĐÃ THỰC HIỆN.**
Campaign `phase3c-linux-02` (2026-11-07) đã chạy xong; xem [báo cáo 3C](../../phase-3c-report.md). Kết quả và sai khác (gồm seal hai tầng): [báo cáo tooling 3C](../../phase-3c-tooling-report.md).
Base `f58f257` trên `main`.

Nguồn: [đặc tả Phase 3](../specs/2026-11-05-phase-3-repair-diagnostics-design.md) §4 (3C), P3-7, P3-10,
P3-11; [kế hoạch hiệu năng v2](2026-11-05-phase-2-linux-performance-v2.md) (tooling, gate, budget);
[báo cáo 3A](../../phase-3a-report.md), [báo cáo 3B](../../phase-3b-report.md),
[nghiệm thu Linux](../../phase-2a-linux-acceptance-report.md) (campaign `phase2-v2-linux-02`).

Tài liệu chỉ là kế hoạch. Lượt soạn không sửa `src/`, `tests/`, `benchmarks/`, không chạy solver hay
campaign. Duyệt kế hoạch **không** phải ủy quyền viết tooling hay chạy campaign.

## 1. Mục tiêu và điều kiện Done

Theo §10 của đặc tả gốc, Phase 3 Done cần "benchmark có số liệu thực" cho repair. 3C trả lời, trên dữ
liệu synthetic, máy Linux của người dùng:

1. Repair có **tìm được lịch hard-valid trong giới hạn** khi dữ liệu đổi không? (trục H, P như v2)
2. Repair **đổi bao nhiêu** so với số thay đổi bắt buộc (`forced`), và có chứng minh tối thiểu không?
3. **Hint** (`use_previous_as_hint`) và **thứ tự** (`BEFORE_QUALITY`/`AFTER_QUALITY`) ảnh hưởng thế nào?
4. Phụ: `explain` mất bao lâu trên bài vô nghiệm cỡ 10/20/40 lớp?

Ngoài phạm vi: Windows, dữ liệu thật, P95/SLA, chấp nhận chất lượng (Q vẫn REVIEW_REQUIRED), tối ưu
hiệu năng repair.

## 2. Dữ liệu

### 2.1 Dataset gốc (C2)

Dùng lại generator v2 (`benchmarks/generate_phase2.py`, không sửa), chỉ seed **s101**:
3 quy mô (10/20/40 lớp) × 3 profile có nghiệm (BASE, MIXED, TIGHT) × 2 biến thể (SOFT, HARD) =
**18 dataset**. Policy 0.4, input 1.1 (repair yêu cầu 1.1). Bundle sinh lại phải trùng byte với hash dataset
trong plan của `phase2-v2-linux-02`; lệch → dừng ở preflight.

### 2.2 Lịch trước (C3)

Bước S trong campaign: chạy `solve` **một lần** cho mỗi dataset gốc, cùng budget/guard như v2, trên đúng
commit và máy của campaign. Lịch phải qua `validate-schedule` và `evaluate-score` độc lập. Dataset nào
không có lịch hợp lệ (UNKNOWN, giới hạn) → bỏ khỏi các bước sau, ghi rõ, không thay bằng nghiệm khác.
Không dùng lại kết quả của campaign-02 (khác commit và campaign).

### 2.3 Nhiễu có seed (C4)

Mỗi dataset gốc sinh 4 input mới từ input gốc và lịch trước, seed cố định theo (dataset, loại nhiễu):

| ID | Nhiễu | Cách áp | Thay đổi bắt buộc kỳ vọng |
|---|---|---|---|
| N1 | GV bận một ngày | Chọn một GV có tiết; bỏ mọi ô của một ngày GV đó đang dạy khỏi `available_slot_ids` | ≥ số tiết của GV ngày đó (`forced`) |
| N2 | Đổi GV cho 1 requirement | Chuyển một requirement sang GV khác (cùng môn nếu có) | Không bắt buộc; chỉ phải đổi khi trùng lịch GV mới |
| N3 | Thêm và bớt tiết | +1 tiết ở một requirement, −1 tiết ở một requirement khác | 1 `new`, 1 `dropped`; đổi thêm nếu tiết mới không có chỗ |
| N4 | Khóa mới | Khóa 2 occurrence vào ô khác vị trí cũ | ≥ 2 (`forced/LOCK`) |

Generator chạy precheck của 3B trên input mới. Nếu có phản chứng đếm (input chắc chắn vô nghiệm), thử ứng
viên kế tiếp theo thứ tự xác định, tối đa 10 lần; vẫn không được thì giữ input vô nghiệm và đánh dấu
`EXPECTED_INFEASIBLE`. Generator **không** đảm bảo input có nghiệm khi không có phản chứng; trường hợp đó là
`GROUND_TRUTH_UNKNOWN`, và repair trả INFEASIBLE là kết quả hợp lệ được ghi riêng (§4).

Mọi input, lịch trước và request được băm và ghi vào manifest trước khi seal.

## 3. Ma trận (C5)

| Phần | Dataset | Nhiễu | Hint | Thứ tự | Số run |
|---|---|---|---|---|---:|
| S — solve lịch trước | 18 | — | — | — | 18 |
| R1 — repair chính | 18 | 4 | có / không | `BEFORE_QUALITY` | 144 |
| R2 — so thứ tự | 6 (10 lớp) | 4 | có / không | `AFTER_QUALITY` | 48 |
| X — explain | 18 UNSAT_CAPACITY (s101–s103 × 3 quy mô × 2 biến thể) + run R1/R2 trả INFEASIBLE | — | — | `MODEL`, `FULL` | 36 + tùy |

Mỗi ô chạy **một lần** (n = 1); khác biệt giữa ô là kết quả quan sát, không phải kết luận thống kê.
`max_changes = null`, `change_scope = null` (không giới hạn, không vùng) cho mọi request.

Phương án nhỏ hơn: bỏ R2 (−48 run, −0,8 h). Không đề xuất, vì R2 là phép đo duy nhất cho đánh đổi
BEFORE/AFTER mà báo cáo 3A mới chỉ thấy trên một fixture.

## 4. Phân loại kết quả (C7)

| Trục | Nhãn | Quy tắc |
|---|---|---|
| **H** | PASS / FAIL / NOT_APPLICABLE | PASS khi lịch qua `validate-schedule`, `evaluate-score` và `evaluate-repair` (đếm lại khớp, request khớp). FAIL khi bất kỳ bước nào lệch, hoặc INFEASIBLE trên input có lịch đã biết. NOT_APPLICABLE khi không có lịch |
| **P** | MET / NOT_MET / INCOMPLETE / NOT_APPLICABLE | MET: H PASS, launch-to-exit ≤ watchdog, peak RSS ≤ target. NOT_MET: UNKNOWN, watchdog, resource stop có đo đủ. INCOMPLETE: thiếu đo. NOT_APPLICABLE: INFEASIBLE được chứng minh |
| **C** (thay đổi) | số liệu | `changed`, `forced`, `slot_changes`, `room_only_changes`, `new`, `dropped`, `min_changes_proved`, tỷ lệ `changed / max(forced, 1)` |
| **Q** | REVIEW_REQUIRED | Ghi vector P1–P3 và proof prefix; không có nhãn ACCEPTED |
| **X** | thời gian, status | Status `explain`, số lời gọi solver, `minimal_proved`, wall time |

Ở mức campaign:

- **R1 đạt P** khi mọi run có kết quả hoặc INFEASIBLE được chứng minh, không thiếu đo, và mọi run có lịch đều
  H PASS trong giới hạn.
- Không gộp các ô khác nhiễu, quy mô hay biến thể thành một con số; không suy P95.
- So hint/không hint và BEFORE/AFTER theo **cặp cùng input**.

## 5. Budget, giới hạn, gate (C6, C7)

Giữ nguyên v2: budget 60/120/180 s, watchdog 150/210/270 s, RSS target 1/2/4 GiB, reserve 2 GiB,
workers 1, seed 42. Repair dùng `--time-limit` bằng budget của quy mô. `explain` dùng cùng budget.

| Sự kiện | Hành động |
|---|---|
| Identity, bundle, preflight, headroom fail | BLOCKED trước run, không chạy |
| H FAIL, `evaluate-repair` lệch, CRASH, OUTPUT_INVALID, MEASUREMENT_BLOCKED | STOPPED, giữ evidence |
| UNKNOWN, watchdog, resource stop có đo đủ; INFEASIBLE | Không dừng; ghi nhận, sang run sau |
| Bước S không có lịch cho một dataset | Bỏ dataset đó khỏi R1/R2/X, ghi rõ; không dừng |
| Ctrl-C, mất điện | Campaign kết thúc; chạy lại cần ID mới và ủy quyền mới |

No retry, no resume ngoài cơ chế admission gate đã có ở v2.

## 6. Ước lượng thời lượng (trần budget, không phải dự báo)

Ở campaign-02, run có lịch thường kết thúc gần budget + vài giây. Repair có tầng chất lượng sau tầng thay
đổi, nên giả định mỗi run dùng gần hết budget.

| Phần | Phép tính | Trần budget |
|---|---|---:|
| S | 6 × (60 + 120 + 180) s | 0,6 h |
| R1 | 48 × (60 + 120 + 180) s | 4,8 h |
| R2 | 48 × 60 s | 0,8 h |
| X (UNSAT) | 36 run, kỳ vọng dừng ở precheck (vài giây) | < 0,1 h |
| **Tổng** | | **≈ 6,2 h** (trần watchdog: S 1,05 h + R1 8,4 h + R2 2 h ≈ 11,5 h) |

Cần một khoảng chạy liền khoảng 7–12 giờ, dài hơn bước F của v2 một chút.

## 7. Task tooling khi được duyệt (TDD, chưa thực hiện)

| Task | File mới | Nội dung và test RED trước |
|---|---|---|
| 1 | `benchmarks/generate_phase3c.py` + test | Chọn 18 dataset s101 và 18 UNSAT; kiểm trùng byte với hash v2; N1–N4 xác định theo seed; precheck 3B để gắn `EXPECTED_INFEASIBLE`; thử lại tối đa 10 ứng viên; manifest băm input/request |
| 2 | `benchmarks/run_phase3c.py` + test | Import supervisor/measurement của v1/v2 (không sửa); thứ tự S → R1 → R2 → X; lịch trước từ bước S; argv `repair … --request …` và `explain …`; seal plan; gate §5 |
| 3 | `benchmarks/judge_phase3c.py` + test | Verdict H/P/C/Q/X; chạy `validate-schedule`, `evaluate-score`, `evaluate-repair --request` trong venv không OR-Tools |
| 4 | `benchmarks/aggregate_phase3c.py` + test | Bảng theo quy mô × biến thể × nhiễu; so cặp hint và BEFORE/AFTER; censored; không P95 |
| 5 | — | Smoke trong cloud (không phải số đo) đến hết bước S và 2 run R1; `pytest tests benchmarks/tests`, ruff, format, mypy; regression: tooling v1/v2 trùng byte với `f58f257` |

Không thêm benchmarks vào wheel, không thêm dependency, không sửa `src/`.

## 8. Ranh giới phê duyệt

| Bước | Cần duyệt riêng |
|---|---|
| A. Duyệt kế hoạch và C1–C10 | Đã duyệt 2026-11-06 |
| B. Task 1–5, smoke, checks | Đã thực hiện 2026-11-06 (smoke trên máy Linux) |
| C. Commit + push tooling; runbook D/E/F cho 3C | Đã thực hiện (`1ab0764`, runbook cập nhật cho linux-02 ở `629354e`) |
| D. Preflight, sinh bundle 3C trên máy Linux | Đã thực hiện (linux-01 và linux-02) |
| E. Seal, warmup, pilot (1 run S + 1 run R1 mỗi biến thể ở 10 lớp) | Đã thực hiện (chế độ smoke, xem runbook) |
| F. Campaign đầy đủ (≈ 7–12 giờ) | Đã chạy: `phase3c-linux-01` dừng (lỗi tooling, sửa ở `67b4502`); `phase3c-linux-02` COMPLETE 2026-11-07 |
| G. Báo cáo 3C, commit báo cáo | Đã thực hiện 2026-11-07 ([báo cáo](../../phase-3c-report.md)) |

## 9. Quyết định cần duyệt

- [x] **C1 — Module mới** `benchmarks/*_phase3c.py`, import nhưng không sửa tooling v1/v2. *(Đề xuất: chọn.)*
- [x] **C2 — 18 dataset gốc** = s101 × 3 quy mô × BASE/MIXED/TIGHT × SOFT/HARD, trùng byte với bundle v2.
  *(Đề xuất: chọn. Ba seed sẽ gấp ba thời lượng.)*
- [x] **C3 — Lịch trước từ bước S** trong chính campaign; không dùng lại kết quả campaign-02. *(Đề xuất:
  chọn; tốn khoảng 0,6 h nhưng giữ identity một commit, một campaign.)*
- [x] **C4 — Bốn loại nhiễu N1–N4** như §2.3, mức nhiễu cố định, có precheck để gắn nhãn vô nghiệm.
  *(Đề xuất: chọn.)*
- [x] **C5 — Ma trận** R1 (144 run, BEFORE, có/không hint) + R2 (48 run, AFTER, chỉ 10 lớp), n = 1.
  *(Đề xuất: chọn.)*
- [x] **C6 — Budget/watchdog/RSS/reserve như v2**; repair và explain dùng budget của quy mô. *(Đề xuất: chọn.)*
- [x] **C7 — Verdict H/P/C/Q/X và gate** như §4–§5; INFEASIBLE không là lỗi trừ khi input có lịch đã biết.
  *(Đề xuất: chọn.)*
- [x] **C8 — Phần X:** `explain` MODEL và FULL trên 18 UNSAT_CAPACITY và mọi run repair trả INFEASIBLE.
  Không dựng riêng bài vô nghiệm kiểu không-đếm ở quy mô lớn trong 3C. *(Đề xuất: chọn. Hệ quả: thời gian
  đường core của `explain` ở 20/40 lớp chỉ được đo nếu nhiễu tình cờ sinh ra bài như vậy; ghi là hạn chế.)*
- [x] **C9 — Máy:** máy Linux của người dùng, cùng máy với campaign-02; workload ghi UNCONTROLLED nếu không
  kiểm soát được. *(Đề xuất: chọn.)*
- [x] **C10 — Phạm vi kết luận:** "repair synthetic trên một máy Linux, n = 1 mỗi ô". Không P95/SLA, không
  Windows, không chấp nhận chất lượng. *(Đề xuất: chọn.)*

## 10. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Nhiễu sinh nhiều input vô nghiệm, ít số liệu repair | Precheck + thử lại ứng viên; báo số `EXPECTED_INFEASIBLE` theo loại nhiễu |
| Repair 40 lớp không có lịch trong budget (UNKNOWN) | P NOT_MET hợp lệ; không nới budget (S1) |
| Model repair tắt ordering interchangeable nên chậm hơn `solve()` (báo cáo 3A) | Đo đúng điều đó; so với thời gian bước S cùng dataset |
| Lịch trước ở bước S kém (FEASIBLE, không tối ưu) | Repair đo so với lịch trước như nó là; ghi vector lịch trước |
| Tooling mới phá v1/v2 | Regression trùng byte; module mới; không sửa file cũ |
| Thời lượng dài, máy ngủ | `tmux` + `systemd-inhibit` như runbook F |
