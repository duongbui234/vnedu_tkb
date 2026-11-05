# Phase 2C-2 — báo cáo triển khai S07–S11

Ngày 2026-11-05. Base `4454d1e` (đặc tả/kế hoạch DRAFT) trên `45f63ee` (`main`), nhánh
`work/phase2a-operational-completion`. Người dùng duyệt D1–D7 theo đề xuất và ủy quyền Task 1–9.
**Trạng thái: TECHNICAL SYNTHETIC — triển khai trong working tree, chờ duyệt commit.**

Phạm vi: [đặc tả](superpowers/specs/2026-11-05-phase-2c-gaps-design.md),
[kế hoạch](superpowers/plans/2026-11-05-phase-2c-gaps.md). Không sửa `benchmarks/`, gate, budget, pins,
`research/` hoặc `reverse-engineering/`; không pilot/campaign, witness hint, wheel hay installed preflight.

## Đã triển khai

| Quyết định | Hiện thực |
|---|---|
| D1 policy 0.4 | `policy_version` nhận `0.4`; S01–S06 (soft + hard) có hiệu lực ở 0.4; năm mã mới `since_policy="0.4"` nên 0.1–0.3 coi là unknown |
| D2 output 1.5 + ScoreReport 1.2 | `QUALITY_POLICY["1.5"]="0.4"`, `SCORE_VERSION["1.5"]="1.2"`; `SCORE_UNITS` theo version (1.2 thêm `idle_periods`, `free_days`, `free_sessions`, `single_period_sessions`); `rule_unit` cho S10 theo `unit` |
| D3 occupied work | `OccupiedWork` + `constraint_config.occupied_work` (chỉ 0.4; rỗng bị bỏ khỏi dump/fingerprint); input kiểm GV/slot/trùng và **ngoài availability** (`null` bị từ chối); fingerprint sort |
| D4 timeline | `GAP_TIMELINE` khi bật S08–S11 và hai buổi cùng ngày giao phút; S07 vẫn hỗ trợ timed |
| D5 chỉ soft | Năm mã không có `hard_policies`; hard → `CUSTOM_RULE` |
| D6 ordering | Năm mã thêm vào allowlist sau oracle |
| D7 S01↔S07 | `SHARED_SLOT_FAMILY`: S01 và S07 cùng GV có ô giao nhau → `OVERLAPPING_RULES` (mọi mode) |

Compiler: `constraints/gaps.py` (S08–S11; mô tả trong [solver-design](solver-design.md)); S07 dùng
đường hệ số placement của S01. Evaluator độc lập trong `score_evaluator.py` (không import compiler).

## Tests mới / sửa

| File | Nội dung |
|---|---|
| `tests/unit/test_gaps_contracts.py` | 0.4/0.5; 0.1–0.3 unknown; mode matrix; hard bị từ chối; tham số; teacher scope; S01↔S07; overlap theo session và S10; GAP_TIMELINE; occupied work (contract, chỉ 0.4, không xuất hiện ở dump cũ, fingerprint); hash fixture cũ; unit theo Score version; cặp 1.5 |
| `tests/unit/test_gaps_score.py` | S07–S11 tính tay: idle, ô can_teach=false/occupied, double, chuỗi bị cắt, nhiều buổi, ngày/buổi rảnh, ngày không có ô dạy, buổi một tiết |
| `tests/unit/test_soft_compilers.py` (thêm) | 17 ca raw với placement cưỡng bức, không objective, cùng giá trị như evaluator |
| `tests/integration/test_gaps_solver.py` | 1.5/Score 1.2 với đánh đổi `(0,1,0)`; ô họp so với ô chỉ unavailable `(0,0,0)` vs `(1,0,0)`; compiler sai → MODEL_INVALID; GAP_TIMELINE; 0.3 vẫn 1.4 |
| `tests/integration/test_gaps_cli.py` | solve→1.5→validate/evaluate; RESULT_VERSION (Score 1.2); score giả → RESULT_SCORE_MISMATCH; evaluate-score không OR-Tools/compiler |
| `tests/properties/test_gaps_oracle.py` | Oracle vét cạn độc lập, 60 seeds × ordering bật/tắt, có ô can_teach=false, occupied work, scope GV và hard S06; spy ordering |

Sửa test cũ có chủ ý: `test_cli.py` (enum thêm 1.5); `test_hard_variant_contracts.py` và
`test_subject_distribution_contracts.py` (version lạ đổi từ `0.4` sang `0.9`); `test_quality_contracts.py`
(registry có thêm năm mã). Thêm fixture `gap_case`.

## Lệnh đã chạy và kết quả

| Lệnh | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS (lock không đổi) |
| `uv run --extra solver pytest` trước khi sửa | 722 passed (baseline) |
| `uv run --extra solver pytest` | **905 passed** |
| `uv run --extra solver pytest tests benchmarks/tests` | **1270 passed, 8 skipped** |
| `uv run ruff check .`, `uv run ruff format --check src tests`, `uv run mypy` | PASS (30 source files) |
| `git diff --check` | PASS |

8 skips là test cần Windows native/opt-in như trước; không phải Windows đã chạy.

## TDD và sai khác so với kế hoạch

- Task 1–6: test chạy RED trước khi sửa product code. Pipeline (Task 7) và CLI (Task 9) xanh ngay vì
  wiring đã có từ Task 1; đã kiểm bằng cách tạm khôi phục file cũ: `cp_sat.py` → 4/5 failed; `cli.py` →
  3/4 failed; khôi phục → xanh. D6: spy test RED khi bỏ mã khỏi allowlist, GREEN khi thêm.
- Ba lỗi lộ ra khi viết test đều là lỗi của test, không phải product code: helper dùng chung dict
  `parameters` và giữ `occupied_work` giữa các lần gọi; oracle vượt giới hạn enumeration (đã thu nhỏ).
- Đặc tả ghi lỗi occupied work là `INPUT_INVALID/OCCUPIED_AVAILABLE`. Thực tế kiểm ở contract input như
  các tham chiếu khác: lỗi là INPUT_INVALID dạng contract (`CONTRACT_INVALID` khi solve,
  `SCHEMA_VALIDATION_FAILED` ở CLI), không có mã riêng.
- “Chuỗi idle” được hiện thực theo các ô **liền kề trong calendar của buổi** (theo thứ tự period), như
  catalog ghi; đặc tả viết “period liên tiếp”. Hai cách trùng nhau khi period không bị khuyết số.
- Oracle dùng calendar symbolic 2 ngày × 2 buổi × 3 tiết, ≤ 4 occurrence; không có timed hay phòng.

## Giới hạn

- Synthetic only: không chứng nhận ô hạn chế, lịch họp, ngưỡng gap hay số ngày rảnh thực tế, chất
  lượng giáo vụ, hiệu năng hay Windows. Chưa có hard mode cho S07–S11.
- Occupied work chỉ dùng cho định nghĩa gap/rảnh; Core không kiểm GV có thực sự họp hay không.
- Timed calendar có buổi chồng giờ bị từ chối cho S08–S11 thay vì được hỗ trợ.
- Số biến tăng theo GV × ngày × buổi × tiết; mới có số đếm model, chưa đo solve. Chưa build wheel cho
  source này. Hạn chế Phase 2A/2B/2C-1 giữ nguyên.
