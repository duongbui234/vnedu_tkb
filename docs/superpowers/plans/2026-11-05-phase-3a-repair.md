# Phase 3A — kế hoạch triển khai repair

Ngày 2026-11-05. Trạng thái: **DRAFT — P3-1 đến P3-12 đã duyệt ngày 2026-11-05; chưa triển khai (bước B và C cần ủy quyền riêng).**
Đặc tả: [2026-11-05-phase-3-repair-diagnostics-design.md](../specs/2026-11-05-phase-3-repair-diagnostics-design.md).
Base `86f624d` trên `main`.

Kế hoạch giả định P3-1 đến P3-12 được duyệt như đề xuất. Nếu chọn khác, cập nhật đặc tả và các task bị ảnh
hưởng trước khi viết code. Mỗi task theo TDD: test RED trước, sửa tối thiểu, GREEN. Nếu wiring có sẵn làm
test mới xanh ngay, kiểm hiệu lực của test bằng cách tạm khôi phục file cũ. Không sửa `benchmarks/`,
gate, budget hay pins; không chạy campaign; không commit trong từng task.

## Ranh giới phê duyệt

| Bước | Cần duyệt riêng |
|---|---|
| A. Duyệt đặc tả + P3-1 đến P3-12 | Có (lượt này dừng ở đây) |
| B. Cập nhật runbook D/E/F ghim commit trước Phase 3 (P3-1) | Có (tài liệu; nên làm trước bước C) |
| C. Task 1–8 trong working tree, chạy checks | Có (product code) |
| D. Commit + push lên `main` | Có |
| E. Tự rà soát, sửa finding, kiểm installed wheel | Có, từng bước |

## Task 1 — Contract (P3-2, P3-3, P3-4)

Files: `src/tkb_core/contracts/repair.py` (mới), `tests/unit/test_repair_contracts.py` (mới).

RED:

- `PreviousSchedule` 1.0, `RepairRequest` 1.0 và `RepairResult` 1.0 roundtrip;
- field lạ, trùng occurrence, `max_changes < 0`, `change_order` sai, `change_scope` rỗng hay ID trùng →
  lỗi;
- `RepairResult` bọc được `ScheduleResult` 1.1–1.5 và giữ đúng ghép version;
- chuyển một `ScheduleResult` `valid_schedule=true` sang `PreviousSchedule`; `valid_schedule=false` bị từ
  chối.

## Task 2 — Evaluator độc lập (§2.4)

Files: `src/tkb_core/validation/repair_evaluator.py` (mới), `tests/unit/test_repair_evaluator.py` (mới).

RED: các ca tính tay (đổi slot, chỉ đổi phòng, tiết đôi, `NEW`, `DROPPED`, đóng băng bị phá,
`max_changes` bị vượt); kiểm tham chiếu với input mới; subprocess import guard (không ortools, compiler
hay preprocessing).

## Task 3 — Ghép và phân loại (§2.1)

Files: `src/tkb_core/repair/matching.py` (mới; package `repair` mới), tests unit.

RED:

- phân loại `MATCHED` / `MATCHED_TARGET_INVALID` / `NEW` / `DROPPED` dựa trên domain đã chuẩn bị (dùng
  `prepare()`);
- khóa mới khác vị trí cũ → thay đổi bắt buộc;
- vùng đóng băng có target invalid → `INPUT_INVALID / REPAIR_FROZEN_TARGET_INVALID`, liệt kê occurrence;
- tham chiếu sai trong lịch trước → `PREVIOUS_SCHEDULE_INVALID`.

## Task 4 — Compiler thay đổi (§2.3)

Files: `src/tkb_core/repair/compiler.py` (mới), tests unit.

RED, raw đếm thay đổi với placement cưỡng bức, không có objective:

- `changed_l = 1 − x[l,p₀]`;
- target invalid → 1 cố định;
- `max_changes` → ràng buộc `≤ K`;
- vùng đóng băng → cố định placement.

Đếm số biến và số hạng trên fixture 10 lớp để có số tham chiếu (không tuyên bố hiệu năng).

## Task 5 — Pipeline `repair()` (§2.3, §2.4, §2.5)

Files: `src/tkb_core/repair/pipeline.py` (mới); có thể tách helper dùng chung từ `solver/cp_sat.py` nếu
cần, nhưng **không đổi hành vi `solve()`**; `tests/integration/test_repair_solver.py` (mới).

RED:

- không thay đổi dữ liệu → 0 thay đổi;
- GV bận một slot → số thay đổi tối thiểu tính tay;
- `max_changes` quá nhỏ → INFEASIBLE;
- `BEFORE` khác `AFTER` trên fixture có đánh đổi tính tay;
- khóa mới thắng lịch trước;
- hint bật hoặc tắt cho cùng kết quả tối ưu trên fixture nhỏ;
- compiler cố ý sai → `MODEL_INVALID / REPAIR_REPORT_MISMATCH`, không xuất lịch;
- budget hết → `UNKNOWN`, hoặc `FEASIBLE` với proof đúng.

## Task 6 — Oracle vét cạn

Files: `tests/properties/test_repair_oracle.py` (mới, oracle Python tự viết, không dùng model helpers).

≥ 60 seed nhỏ (≤ 4 occurrence, 2 ngày × 2 buổi × 3 tiết), có S01–S11 ngẫu nhiên. So FEASIBLE/INFEASIBLE
và vector lexicographic với cả hai `change_order`, có hoặc không có `max_changes` và vùng, có hoặc không
có hint.

## Task 7 — CLI và package

Files: `src/tkb_core/cli.py`, `src/tkb_core/contracts/capabilities.py`,
`tests/integration/test_repair_cli.py` (mới), `tests/integration/test_cli.py` (enum lệnh).

RED:

- `repair` → envelope → `validate-schedule` trên `result` → `evaluate-repair` OK;
- `evaluate-repair` chạy được không cần OR-Tools;
- repair result giả → `RESULT_REPAIR_MISMATCH`; input khác → `STALE_RESULT`;
- input 1.0 → `UNSUPPORTED_FEATURE`;
- hồi quy: output và hash của `solve` cho các fixture hiện có không đổi.

## Task 8 — Tài liệu

Files:

- `README.md`;
- `docs/domain-model.md` (lịch trước, phân loại, đơn vị thay đổi);
- `docs/solver-design.md` (tầng thay đổi);
- `docs/constraint-catalog.md` (repair không phải soft rule; ghi quan hệ với P1–P3);
- `docs/phase-3a-report.md` (mới);
- trạng thái đặc tả và kế hoạch.

## Checks trước khi báo hoàn thành (bước C)

```bash
uv sync --locked --extra solver
```

```bash
uv run --extra solver pytest tests benchmarks/tests
```

```bash
uv run ruff check .
```

```bash
uv run ruff format --check src tests benchmarks
```

```bash
uv run mypy
```

```bash
git diff --check
```

Baseline tại `f873126` (source hiện tại): 1352 passed, 8 skipped. Báo số thực chạy. Test byte-identical
của tooling v1 phải vẫn PASS.

## Rủi ro và giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| Sửa `cp_sat.py` để dùng chung code làm đổi hành vi `solve()` | Ưu tiên module `repair/` riêng; nếu tách helper thì có test hồi quy hash/output cho mọi fixture |
| Ghép version output sai trong envelope | Test cặp 1.1–1.5 trong Task 1 và Task 7 |
| Evaluator vô tình dùng chung logic với compiler | Import guard và oracle thứ ba |
| Campaign Phase 2 v2 chạy trên commit có code 3A | Bước B ghim commit trong runbook D/E/F trước khi code |
