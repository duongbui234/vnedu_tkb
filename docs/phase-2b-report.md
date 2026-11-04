# Phase 2B — báo cáo triển khai hard variants S01–S04

Ngày 2026-11-05. Base `91c16da` (đặc tả/kế hoạch DRAFT) trên `124b89d`, nhánh
`work/phase2a-operational-completion`. Người dùng duyệt D1–D7 theo đề xuất và ủy quyền Task 1–8.
**Trạng thái: TECHNICAL SYNTHETIC — triển khai trong working tree, chờ duyệt commit.**

Phạm vi: [đặc tả](superpowers/specs/2026-11-05-phase-2b-hard-variants-design.md),
[kế hoạch](superpowers/plans/2026-11-05-phase-2b-hard-variants.md). Không sửa `benchmarks/`,
gate, budget, pins, `research/` hoặc `reverse-engineering/`; không pilot/campaign, không witness
hint, không build wheel hoặc installed preflight.

## Đã triển khai

| Quyết định | Hiện thực |
|---|---|
| D1 policy 0.2 | `ConstraintConfigV11.policy_version` nhận `0.1`/`0.2`; `registry.supports_mode`, `hard_policies=("0.2",)`; capability 0.1 giữ nguyên nhánh cũ |
| D2 output 1.3 | `ScheduleResult` 1.3 = shape 1.2; `QUALITY_POLICY` ép cặp 1.2↔0.1, 1.3↔0.2; `solve` và CLI chọn version theo policy |
| D3 lọc domain S01/S04 | `constraints/hard_variants.placement_filter` (không OR-Tools) gọi trong `prepare` trước lock/prechecks |
| D4 overlap mọi mode | `validate_rule_config` dùng enabled hard ∪ soft khi policy 0.2 |
| D5 ordering | `_add_interchangeable_ordering` cho phép khi enabled hard ⊂ S01–S04 của policy 0.2 |
| D6 không precheck tổng hợp | S02/S03 chỉ là ràng buộc model; CP-SAT chứng minh INFEASIBLE |
| D7 diagnostic | `HARD_AVOID_SLOT`, `HARD_SESSION_LIMIT`, `HARD_DAY_LIMIT`, `HARD_PERIOD_WINDOW`; schema `Diagnostic` không đổi |

S02/S03: `constraints/hard.add_load_limits` thêm `Σ duration·x ≤ limit` trong `build_model` ngay sau
occupancy, trước clone hard model; range ngoài int64 → `INPUT_INVALID/HARD_RULE_RANGE`.
Validator: `_hard_variant_violations` trong `independent_validator.py`, code riêng, không import
compiler/preprocessing/solver/score evaluator (có test chặn import trong subprocess).

## Tests mới

| File | Nội dung |
|---|---|
| `tests/unit/test_hard_variant_contracts.py` | Version dispatch, envelope strict, capability matrix, overlap mọi mode, fingerprint, cặp output/policy |
| `tests/unit/test_hard_variant_validator.py` | Lịch forged từng family, double, AM/PM, limit 0, timed alias, disabled/scope, evaluate_score, cô lập import |
| `tests/unit/test_hard_variant_domains.py` | Lọc S01/S04, S02/S03 không lọc, domains 0.1 byte-identical, EMPTY_DOMAIN, LOCK_CONFLICT, timed |
| `tests/unit/test_hard_variant_model.py` | Load = limit hợp lệ, limit+1 cấm, double = 2, S03 cộng buổi, range guard, model 0.1 không đổi |
| `tests/integration/test_hard_variants_solver.py` | Output 1.3/NOT_REQUESTED, hard+soft LEXICOGRAPHIC_OPTIMAL `(2,0,0)`, INFEASIBLE, empty demand, compiler thiếu → MODEL_INVALID, 0.1 vẫn từ chối |
| `tests/integration/test_hard_variants_cli.py` | solve→1.3→validate/evaluate, forged vi phạm hard exit 2, RESULT_VERSION, evaluate-score không OR-Tools/compiler |
| `tests/properties/test_hard_variant_oracle.py` | Oracle vét cạn độc lập, 60 seeds × ordering bật/tắt: FEASIBLE/INFEASIBLE và optimum vector khớp |

Sửa test cũ: `tests/integration/test_cli.py` kỳ vọng enum output thêm `1.3` (thay đổi contract có
chủ ý); thêm fixture `hard_case` trong `tests/conftest.py`.

## Lệnh đã chạy và kết quả

| Lệnh | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS (lock không đổi) |
| `uv run --extra solver pytest` (trước khi sửa) | 363 passed — baseline cloud |
| `uv run --extra solver pytest` | **532 passed** |
| `uv run --extra solver pytest tests benchmarks/tests` | **897 passed, 8 skipped** |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` (và `benchmarks`) | PASS |
| `uv run mypy` | PASS, 29 source files |
| `git diff --check` | PASS |

8 skips là các test cần Windows native/historical opt-in như trước; không phải Windows đã chạy.
Mỗi nhóm test mới được chạy RED trước khi sửa product code, trừ CLI (sửa trước rồi xác nhận RED bằng
cách tạm stash `cli.py`: 4 failed; khôi phục: 4 passed).

## Sai khác so với kế hoạch

- Plan Task 2 muốn giữ 0.2 hard UNSUPPORTED đến Task 6. Toàn bộ Task 1–8 nằm trong một working
  tree chưa commit, nên capability được mở sớm trong code nhưng không có trạng thái trung gian nào
  được phát hành; trạng thái cuối có đủ compiler + checker + oracle.
- S02/S03 compiler nằm trong `constraints/hard.py` (đã import OR-Tools) thay vì phần lazy-import
  của `hard_variants.py`.
- Không thêm test stub riêng cho “tier INFEASIBLE sau incumbent” và zero-probe: `run_quality`
  không đổi; regression 2A hiện có vẫn PASS, và ràng buộc hard nằm trong `built.model` mà probe clone.
- Oracle dùng calendar symbolic; timed alias được kiểm ở unit tests validator/domain.

## Giới hạn

- Synthetic only: không chứng nhận ngưỡng trường (H10), hiệu năng, Windows/cross-OS hay chất lượng
  giáo vụ. Không có benchmark/campaign mới; không tuyên bố tốc độ.
- INFEASIBLE không chỉ ra rule nguyên nhân (không IIS/relax).
- Hạn chế Phase 2A giữ nguyên: acceptance v2 DRAFT, zero NOT_MET, primary 0/108, Windows chưa
  nghiệm thu. Raw evidence `benchmarks/artifacts/` không có trong clone cloud và không được tạo.
- Wheel/installed preflight chưa chạy cho source mới; receipt wheel cũ không áp dụng.
