# Phase 2C-1 — rà soát diff `ebc9b85..aed452b`

Ngày 2026-11-05. Phạm vi: 35 files (+1686/−78) của commit `aed452b`, đối chiếu với
[đặc tả 2C-1](superpowers/specs/2026-11-05-phase-2c-subject-distribution-design.md) và
[kế hoạch](superpowers/plans/2026-11-05-phase-2c-subject-distribution.md). Không sửa product code
hay tests; không pilot/campaign. Người rà soát cùng phiên với người triển khai: đây là tự kiểm lại
bằng probe và red test, **không** phải review của một người thứ hai.

**Kết luận: 0 finding về tính đúng (P1/P2); 1 finding P3 về hiệu quả model; 2 quan sát.**
**Cập nhật: F1 đã sửa theo TDD (xem cuối mục F1).**

## Finding

### F1 (P3, hiệu quả) — soft S05 lặp lại biểu thức ngày trong từng cặp; không có guard số cặp

`soft._compile_distribution` dựng `day_of[o] = Σ day·x` cho mỗi component rồi đưa nguyên hai biểu
thức đó vào ràng buộc `diff == day_i − day_j` của **mỗi cặp**. Số hạng tuyến tính vì vậy tăng theo
khoảng `cặp × 2 × |domain|`, thay vì `|domain|` mỗi component cộng vài hạng tử mỗi cặp.

- Probe (6 ngày × 2 buổi × 5 tiết, 60 placement/occurrence): n=10 → 5.491 hạng tử; n=20 → 23.181;
  n=40 (780 cặp) → **95.161**. Thời gian compile vẫn nhỏ (0,07 s ở n=40); chưa đo thời gian solve.
- Red test ngoài `tests/`:
  `/tmp/claude-0/-home-user-vnedu-tkb/bedca8ac-76d7-5ff6-ab6e-cd8ebb0f9957/scratchpad/review2c/test_review2c_red.py`
  → **1 failed** (95.161 > 2·2.400 + 10·780 = 12.600).
- Kế hoạch (bảng rủi ro) ghi “bound và đếm cặp trước build”; code chỉ kiểm range của bound, không
  có giới hạn số cặp. Một nhóm rất lớn sẽ tăng bộ nhớ theo bậc hai trước khi bất kỳ guard nào chạy.
- Không ảnh hưởng tính đúng: giá trị raw vẫn là equality chính xác, oracle 60 seeds vẫn khớp.
- **Đã sửa (được người dùng ủy quyền):** `soft._compile_distribution` tạo một `IntVar` ngày mỗi
  component (`day_var == Σ day·x`) và dùng biến này trong `diff` của mọi cặp; thêm guard
  `MAX_SPREAD_PAIRS = 20 000` cặp mỗi rule → `UNKNOWN/RESOURCE_LIMIT` trước khi tạo biến cặp.
  Regression trong `tests/unit/test_soft_compilers.py`: giới hạn số hạng (RED 95.161 → GREEN) và
  guard (RED vì chưa có, GREEN; đúng giới hạn vẫn OPTIMAL). Sau sửa: n=10 → 791, n=20 → 1.981,
  n=40 → 5.561 hạng tử. Red test ở scratchpad nay PASS; oracle và mọi test penalty giữ nguyên.

## Quan sát (không phải lỗi so với đặc tả)

- **O1 — Một mã đã khai báo nhưng chưa có mode** (`PENDING_RULE`) phải giữ lỗi `CUSTOM_RULE`; vì vậy
  triển khai dùng `since_policy` thay cho “biết mã khi có mode”. Đặc tả §2 chưa nhắc chi tiết này;
  báo cáo 2C-1 đã ghi lại.
- **O2 — Oracle** không dùng S02, timed calendar, lock hay phòng (đã ghi trong báo cáo 2C-1).

## Đã kiểm, không phát hiện lỗi

| Điểm | Cách kiểm |
|---|---|
| Hash/hành vi policy 0.1/0.2 không đổi | Fingerprint 10 fixtures + payload 0.1/0.2 mang S05/S06 disabled với params tùy ý: giống hệt giữa `ebc9b85` và `aed452b` (worktree tạm, đã xóa) |
| Overlap S05 (chung requirement) và S06 (giao lớp×môn), mọi mode | Đọc `registry.validate_rule_config`; tests contract |
| Soft S05 là equality, bound `C(n,2)·k`, range guard | Đọc compiler; test placement cưỡng bức không objective |
| Cửa sổ hard S05 ở biên calendar | Probe ngày 1,2,5: k=3 → OPTIMAL ở ngày (2,5); k=4 → OPTIMAL; k=5 → INFEASIBLE, đúng định nghĩa theo cặp |
| Bucket S06 gộp nhiều requirement cùng lớp+môn | Probe hai GV cùng lớp/môn: soft `(1,2,0)` khớp evaluator; hard hợp lệ theo validator |
| Validator `HARD_*` | Đọc `independent_validator.py`; tests forged; subprocess guard |
| Cặp output 1.4 ↔ 0.3 ↔ Score 1.1 trong contract, `solve`, CLI | Đọc `output.py`/`cp_sat.py`/`cli.py`; CLI phân loại result sai version score là `SCHEMA_VALIDATION_FAILED` |
| Ordering D7 | Guard chỉ cho S01–S06 và policy 0.2/0.3; oracle bật/tắt ordering và spy test |

## Lệnh đã chạy

| Lệnh | Kết quả |
|---|---|
| So fingerprint với worktree tạm `ebc9b85` (đã xóa) | 12/12 giống nhau |
| `uv run --extra solver python …/review2c/probe.py` | P2 tăng trưởng hạng tử; P3, P4 đúng |
| `uv run --extra solver pytest …/review2c/test_review2c_red.py` | 1 failed (red, như dự định) |
| `uv run --extra solver pytest tests benchmarks/tests` | 1085 passed, 8 skipped |
| `uv run ruff check .` | PASS |
| `uv run mypy` | PASS, 29 source files |

Probe và red test nằm trong scratchpad của phiên (ngoài repo, mất khi container bị thu hồi). File này
được commit cùng bản sửa F1.
