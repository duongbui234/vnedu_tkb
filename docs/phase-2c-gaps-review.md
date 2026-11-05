# Phase 2C-2 — rà soát diff `4454d1e..933f3ae`

Ngày 2026-11-05. Phạm vi: 32 files (+1683/−70) của commit `933f3ae`, đối chiếu với
[đặc tả 2C-2](superpowers/specs/2026-11-05-phase-2c-gaps-design.md) và
[kế hoạch](superpowers/plans/2026-11-05-phase-2c-gaps.md). Không sửa product code hay tests; không
pilot/campaign. Người rà soát cùng phiên với người triển khai: đây là tự kiểm lại bằng probe và red
test, **không** phải review của một người thứ hai.

**Kết luận: 0 finding P1/P2; 1 finding P3 (độ chặt contract cho policy cũ); 3 quan sát.**
**Cập nhật: F1 đã sửa theo TDD; O1 đã ghi vào catalog (xem cuối mục F1).**

## Finding

### F1 (P3) — policy 0.1–0.3 nay chấp nhận key `occupied_work: []`

Trước 2C-2, `occupied_work` là field lạ với mọi policy nên payload chứa nó bị từ chối. Sau 2C-2,
`ConstraintConfigV11` có field này cho mọi policy; validator chỉ từ chối khi danh sách **khác rỗng** ở
policy < 0.4. Vì vậy một input 0.1/0.2/0.3 có `"occupied_work": []` trước bị INPUT_INVALID, nay hợp lệ.

- Hash của input hợp lệ cũ **không đổi** (mục dưới); field rỗng bị bỏ khỏi dump/fingerprint.
- Trái nguyên tắc AGENTS.md “reject unknown input fields … instead of ignoring them”: với policy cũ,
  field này không có nghĩa nên nên bị từ chối như trước. Câu đặc tả §3 (“field không được có mặt
  (khác rỗng → INPUT_INVALID)”) mơ hồ; test `test_occupied_work_only_in_policy_04` đã mã hóa cách đọc
  “cho phép rỗng”.
- Red test ngoài `tests/`:
  `/tmp/claude-0/-home-user-vnedu-tkb/bedca8ac-76d7-5ff6-ab6e-cd8ebb0f9957/scratchpad/review2c2/test_review2c2_red.py`
  → **3 failed** trên HEAD; cùng test trên worktree tạm `4454d1e` → **3 passed**.
- Ảnh hưởng thấp: không đổi lịch, điểm hay hash của input hợp lệ cũ; chỉ nới chấp nhận một payload.
- **Đã sửa (được người dùng ủy quyền):** `ConstraintConfigV11.occupied_work_policy` từ chối khi key có
  trong `model_fields_set` và policy < 0.4, kể cả danh sách rỗng. Dump vẫn bỏ danh sách rỗng, nên
  input cũ revalidate được và hash không đổi. Regression trong `tests/unit/test_gaps_contracts.py`
  (3 policy RED → GREEN; thêm ca 0.4 với `[]` tường minh có cùng hash với payload không có key). Red
  test ở scratchpad nay PASS. Câu §3 của đặc tả đã làm rõ.

## Quan sát (không phải lỗi so với đặc tả)

- **O1 — S10 coi ngày GV chỉ “không thể dạy” là ngày rảnh.** Ngày có ô dạy được của trường, GV không
  dạy và không có occupied work được tính là rảnh, kể cả khi GV unavailable cả ngày. Đúng định nghĩa
  §4 của đặc tả, nhưng caller cần biết: muốn ngày đó không tính, phải khai báo occupied work.
- **O2 — Occupied work yêu cầu availability tường minh.** GV có `available_slot_ids = null` không thể
  khai báo occupied work; upstream phải liệt kê availability. Có chủ ý (D3), nhưng là chi phí tích hợp.
- **O3 — Coverage.** Oracle chỉ dùng period liên tục và calendar symbolic. Probe sai khác (dưới) bổ
  sung period khuyết số, nhưng nằm ngoài `tests/`.

## Đã kiểm, không phát hiện lỗi

| Điểm | Cách kiểm |
|---|---|
| Hash/hành vi policy 0.1–0.3 | 12 fixtures + payload 0.1/0.2/0.3 chứa S08 disabled với params tùy ý (không có key `occupied_work`): fingerprint giống hệt giữa `4454d1e` và `933f3ae` |
| Compiler ↔ evaluator cho S07–S11 | Probe sai khác: 300 instance ngẫu nhiên (period khuyết số, ô `can_teach=false` cả ở biên, tiết đôi, occupied work, 1–3 requirement, 2 GV), 5 lịch ngẫu nhiên hợp lệ mỗi instance → **921 lịch, 0 sai khác** giữa raw compile (placement cưỡng bức) và evaluator độc lập |
| Big-M S09, reify S11 | Nằm trong probe trên và test compiler/oracle |
| Overlap S01↔S07, `GAP_TIMELINE`, cặp 1.5/0.4/Score 1.2, ordering D6 | Đọc `registry.py`/`output.py`/`model_builder.py`; tests contract, CLI, oracle/spy |

## Lệnh đã chạy

| Lệnh | Kết quả |
|---|---|
| So fingerprint với worktree tạm `4454d1e` (đã xóa) | 16/16 giống nhau khi không có key `occupied_work`; khác biệt duy nhất là F1 |
| `uv run --extra solver python …/review2c2/diff_probe.py` | 921 lịch, 0 sai khác |
| `uv run --extra solver pytest …/review2c2/test_review2c2_red.py` | HEAD: 3 failed (red); `4454d1e`: 3 passed |
| `uv run --extra solver pytest tests benchmarks/tests` | 1270 passed, 8 skipped |
| `uv run ruff check .` | PASS |
| `uv run mypy` | PASS, 30 source files |

Probe và red test nằm trong scratchpad của phiên (ngoài repo, mất khi container bị thu hồi). File này
được commit cùng bản sửa F1.
