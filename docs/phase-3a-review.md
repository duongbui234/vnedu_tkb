# Phase 3A — rà soát diff `84d1b28..223de89`

Ngày 2026-11-05. Phạm vi: commit `223de89` (21 files, +2598/−17), đối chiếu với
[đặc tả Phase 3](superpowers/specs/2026-11-05-phase-3-repair-diagnostics-design.md),
[kế hoạch 3A](superpowers/plans/2026-11-05-phase-3a-repair.md) và [báo cáo 3A](phase-3a-report.md).
Không sửa product code hay tests; không chạy benchmark hay campaign. Người rà soát là cùng phiên với
người triển khai: đây là **tự kiểm lại** bằng đọc code và probe, **không** phải review của người thứ hai
(P3-12, S3).

**Kết luận: 0 finding P1/P2; 3 finding P3; 5 quan sát.**
**Cập nhật: F1–F3 đã sửa theo TDD (xem dòng "Đã sửa" ở từng finding và mục cuối).** Không finding nào làm một lịch sai hard, sai
score hay sai số thay đổi được xuất ra. Cả ba liên quan khả năng kiểm, chẩn đoán và nhất quán budget.

## Finding

### F1 (P3) — `evaluate-repair` không đối chiếu được với request của người dùng

`evaluate-repair <input> <previous> <repair-result>` tính lại mọi bộ đếm theo **request nhúng trong
file kết quả**. Validator của `RepairResult` chỉ bảo đảm report khớp request nhúng đó. Vì vậy, một kết
quả tạo bằng request lỏng hơn (không vùng, không giới hạn) vẫn PASS, dù người dùng đã định dùng request
chặt hơn. Lệnh không nhận request của người dùng: probe `evaluate-repair … --request r.json` →
`INVALID_ARGUMENTS`.

- Ảnh hưởng: chỉ khi file kết quả bị tạo nhầm hoặc bị sửa có chủ ý. Lịch vẫn hard-valid và số đếm vẫn
  đúng với request nhúng.
- Đề xuất: thêm `--request <file>` (tùy chọn hoặc bắt buộc) cho `evaluate-repair`; khác request nhúng →
  `RESULT_REQUEST_MISMATCH`. Hoặc in hash request nhúng để người dùng so.
- **Đã sửa:** `evaluate-repair` nhận `--request <file>` (tùy chọn). Khác request nhúng →
  `RESULT_REQUEST_MISMATCH`; file request sai → `REPAIR_REQUEST_INVALID`. Không truyền thì hành vi như
  cũ. Regression: `test_evaluate_repair_checks_the_callers_request`.

### F2 (P3) — `max_changes` nhỏ hơn số thay đổi bắt buộc chỉ báo `INFEASIBLE` chung chung

Khi số occurrence `forced` (vị trí cũ không còn hợp lệ) đã lớn hơn `max_changes`, bài toán chắc chắn vô
nghiệm, và điều đó biết được trước khi gọi solver. Hiện pipeline vẫn chạy CP-SAT và trả
`INFEASIBLE / "No validated repair was produced"`. Probe: forced = 1, `max_changes = 0` → đúng như
vậy, `solver_executed=true`.

- Đề xuất: kiểm trước khi gọi solver; nếu forced > `max_changes` → `INFEASIBLE /
  REPAIR_MAX_CHANGES_BELOW_FORCED`, liệt kê occurrence forced, `solver_executed=false`. Đây vẫn là
  INFEASIBLE đã chứng minh (đếm), đúng hướng §6 của đặc tả gốc.
- **Đã sửa:** pipeline đếm forced sau matching. Forced > `max_changes` → `INFEASIBLE /
  REPAIR_MAX_CHANGES_BELOW_FORCED`, liệt kê occurrence, `solver_executed=false`. Regression:
  `test_max_changes_below_forced_is_decided_before_search`.

### F3 (P3) — Budget của `AFTER_QUALITY` không trừ thời gian chuẩn bị

`BEFORE_QUALITY` (và trường hợp không có preference) dùng phần budget còn lại, tức đã trừ thời gian
`prepare`, matching và dựng model. `AFTER_QUALITY` lại truyền nguyên `time_limit_seconds` cho
`run_quality`. Probe (spy): budget 7,0 s được truyền nguyên cho `run_quality`. Tổng wall có thể vượt time
limit một khoảng bằng thời gian chuẩn bị.

- Đây cũng là hành vi của `solve()` (truyền nguyên budget sau `prepare`), nên không phải hồi quy. Nhưng
  hai nhánh của repair đang không nhất quán với nhau.
- Đề xuất: dùng `left()` cho cả hai nhánh, hoặc ghi rõ trong tài liệu rằng time limit là budget solver,
  không phải trần end-to-end.
- **Đã sửa:** `AFTER_QUALITY` dùng phần budget còn lại như `BEFORE_QUALITY`; hết budget → `UNKNOWN`.
  `solve()` không đổi. Regression: `test_quality_stages_get_only_the_remaining_budget` (cả hai thứ tự;
  nhánh `BEFORE` xanh ngay, giữ làm test chặn hồi quy).

## Quan sát

- **O1 — Đổi phòng và đổi slot nặng như nhau** (P3-5). Probe có phòng: phòng cũ bận đúng slot cũ → lịch
  đổi slot (1 thay đổi), dù đổi phòng giữ nguyên slot cũng là 1 thay đổi. Hai cách hòa nhau; lời giải
  không ưu tiên cách ít ảnh hưởng tới GV/HS hơn. Nếu nghiệp vụ muốn ưu tiên giữ slot, cần quyết định
  riêng (ví dụ trọng số khác nhau). Đây không phải lỗi so với đặc tả.
- **O2 — Vùng theo ngày không bao được slot đã bị xóa khỏi calendar.** Ngày của vị trí cũ lấy theo
  calendar mới. Slot cũ không còn → không khớp `days` → occurrence bị đóng băng và forced →
  `REPAIR_FROZEN_TARGET_INVALID`. Đúng đặc tả (không âm thầm giữ), nhưng người dùng phải thêm lớp, GV
  hoặc môn vào scope.
- **O3 — Ghép theo ID phụ thuộc thứ tự block.** Đổi `block_durations` từ `[2,1,1]` sang `[1,1,2]` làm
  `r::1` chuyển từ tiết đôi thành tiết đơn nhưng vẫn là "matched". Đây là giới hạn của ID ổn định
  (§2.1), cần ghi cho upstream.
- **O4 — Độ phủ oracle.** Oracle 3A không có phòng, timed calendar, hard variant, S05–S07, S09, S10 hay
  `occupied_work`, và chấm điểm bằng chính validator/evaluator mà pipeline dùng để tự kiểm. Probe bổ
  sung (ngoài `tests/`): phòng (đổi đúng 1), hard S06 ở policy 0.3 (đổi đúng 1, có chứng minh), và 20 seed
  × 2 thứ tự với 4 worker (0 lệch so với oracle).
- **O5 — Tự kiểm.** Như mọi mốc trước, chưa có người thứ hai đọc 2 600 dòng thay đổi.

## Đã kiểm, không phát hiện lỗi

| Điểm | Cách kiểm |
|---|---|
| `solve()` không đổi | `git diff 84d1b28 223de89` rỗng cho `solver/`, `preprocessing/`, `constraints/`, validator, score evaluator, `benchmarks/` |
| Thứ tự giai đoạn, đẳng thức số thay đổi, fallback, hint | Đọc `pipeline.py`; test tích hợp; mutation check của báo cáo 3A (5/5 bị bắt) |
| Kiểm ba lớp trước khi xuất lịch | Đọc `_verify` và `_report`; test compiler cố ý sai → `MODEL_INVALID / REPAIR_REPORT_MISMATCH` |
| Evaluator độc lập | Import guard; ca tính tay; `check_report` |
| Contract | Số học `RepairReport`; envelope chỉ có report khi có lịch; ghép version 1.2–1.5 |
| CLI | Refactor `_read_model` giữ nguyên mã lỗi cũ; `evaluate-repair` không cần OR-Tools; stale/forged bị bắt |
| Nhiều worker | Probe 40 lần chạy với 4 worker khớp oracle |

## Lệnh đã chạy

| Lệnh | Kết quả |
|---|---|
| `uv run --extra solver python …/review3a/probe.py` | Phòng: OPTIMAL, 1 thay đổi; hard S06: OPTIMAL, 1 thay đổi; 4 worker: 0 lệch; spy budget `AFTER`: 7,0 s |
| Probe F2 (forced 1, `max_changes 0`) | `INFEASIBLE / "No validated repair was produced"`, `solver_executed=true` |
| Probe F1 (`evaluate-repair … --request`) | Exit 2, `INVALID_ARGUMENTS` |

Probe nằm trong scratchpad của phiên (ngoài repo, mất khi container bị thu hồi). Lần chạy full suite gần
nhất là ở bước triển khai (1537 passed, 8 skipped); lượt rà soát không chạy lại.

## Sửa F1–F3 (được người dùng ủy quyền)

Test regression viết trước. Trên `223de89` có **3 failed**: F1, F2 và F3 ở nhánh `AFTER`; ca `BEFORE`
xanh đúng như dự kiến. Sau khi sửa `repair/pipeline.py` và `cli.py`, tất cả xanh. Không sửa `solve()`,
`solver/`, `preprocessing/`, `constraints/`, validator, score evaluator hay `benchmarks/`.

| Lệnh | Kết quả |
|---|---|
| Test repair (unit, integration, oracle) | 189 passed |
| `uv run --extra solver pytest tests benchmarks/tests` | **1541 passed, 8 skipped** (+4 so với 1537) |
| `uv run ruff check .`, `uv run ruff format --check src tests benchmarks`, `uv run mypy`, `git diff --check` | PASS |

Các quan sát O1–O5 vẫn mở; O1 (đổi phòng và đổi slot nặng như nhau) cần quyết định nghiệp vụ riêng.
