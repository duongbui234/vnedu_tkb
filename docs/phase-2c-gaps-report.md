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

## Kiểm installed wheel từ `6a1d937`

Bổ sung sau commit `6a1d937` (gồm bản sửa F1 của [rà soát](phase-2c-gaps-review.md)). Chỉ Linux, mỗi
lệnh chạy một lần (n=1), input synthetic; không phải benchmark và không đo hiệu năng.

- Wheel `vnedu_tkb_core-0.2.0-py3-none-any.whl`, SHA256
  `cdd3428264bc92db0e5aadb2704cc277d46f405bebc7c062c6d0786abbda35d1`, build bằng `uv build --wheel`
  từ tree sạch tại `6a1d937`. **Wheel không được commit**; nó chỉ nằm trong scratchpad của phiên cloud.
  Wheel `5b23a5da…` (từ `f697e41`, Phase 2C-1) không khớp source hiện tại.
- Python 3.12.3; OR-Tools 9.15.6755. Dependencies từ `uv export --frozen` (lock không đổi) vào hai venv
  sạch: `venv-solver` (có OR-Tools) và `venv-core` (không OR-Tools); wheel cài `--no-deps`.
- 30/30 file `tkb_core/*.py` đã cài khớp byte với `src/` tại HEAD ở cả hai venv.

| Lệnh (venv) | Exit | Kết quả |
|---|---|---|
| solver: `solve gaps.json --time-limit 10 --workers 1 --seed 42 --output result.json` | 0 | 1.5 OPTIMAL, policy 0.4, LEXICOGRAPHIC_OPTIMAL, Score 1.2 `[0,0,0]` (4 unit) |
| solver: `solve gaps_noocc.json … --output result_noocc.json` | 0 | 1.5 OPTIMAL `[1,0,0]` |
| solver: `validate-schedule gaps.json result.json` | 0 | 1.5 SCHEDULE_VALID |
| solver / core: `evaluate-score gaps.json result.json` | 0 / 0 | Score 1.2 OK `[0,0,0]` |
| core: `evaluate-score gaps_noocc.json result_noocc.json` | 0 | Score 1.2 OK `[1,0,0]` |
| core: `evaluate-score gaps_noocc.json forged_score.json` | 2 | INPUT_INVALID / RESULT_SCORE_MISMATCH |
| core: `validate-schedule gaps_noocc.json forged_score.json` | 2 | INPUT_INVALID / RESULT_SCORE_MISMATCH |
| core: `evaluate-score gaps_noocc.json result.json` | 2 | INPUT_INVALID / STALE_RESULT |
| solver: `solve policy03_gaps.json` | 2 | 1.4 UNSUPPORTED_FEATURE / UNKNOWN_RULE |
| core: `validate-input policy03_empty_occ.json` | 2 | INPUT_INVALID / SCHEMA_VALIDATION_FAILED (F1 đã sửa) |
| core: `solve gaps.json` | 2 | SOLVER_NOT_INSTALLED |

Input: `gaps.json` (GV chỉ dạy được 1-AM-1/3/4, 3 tiết đơn; ô 1-AM-2 là `occupied_work`; S08 P1, S11 và
S07 P2, S10 ngày target 1 P3); `gaps_noocc.json` (cùng input, không occupied work: 1-AM-2 chỉ
unavailable nên là tiết trống → `[1,0,0]`, và ngày 2 vẫn tính rảnh như ghi chú O1); `forged_score.json`
đặt mọi penalty của result `[1,0,0]` về 0; `policy03_gaps.json` (cùng rule, policy 0.3);
`policy03_empty_occ.json` (policy 0.3 với `occupied_work: []`). Chưa kiểm sdist, Windows/cross-OS,
pilot/campaign.

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
- Số biến tăng theo GV × ngày × buổi × tiết; mới có số đếm model, chưa đo solve. Installed wheel chỉ
  kiểm trên Linux, n=1, input synthetic (mục trên). Hạn chế Phase 2A/2B/2C-1 giữ nguyên.
