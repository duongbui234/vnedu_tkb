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

## Kiểm installed wheel từ `d7de450`

Bổ sung sau commit `d7de450` (gồm bản sửa F1 của [rà soát](phase-2b-review.md)). Chỉ Linux, mỗi
lệnh chạy một lần (n=1), input synthetic; không phải benchmark và không đo hiệu năng.

- Wheel `vnedu_tkb_core-0.2.0-py3-none-any.whl`, SHA256
  `48e31487dae5d7f0378cf04316b567b89bb6dffb5765e325c37adceabeda2453`, build bằng `uv build --wheel`
  từ tree sạch tại `d7de450`. **Wheel không được commit**; nó chỉ nằm trong scratchpad của phiên cloud.
- Wheel `3bde3b95…` (từ `1e07961`) **đã bị thay thế** vì `cli.py` đổi ở `d7de450`; không dùng nó
  hay receipt của nó cho source hiện tại.
- Python 3.12.3; OR-Tools 9.15.6755. Dependencies cài từ `uv export --frozen` (lock không đổi) vào
  hai venv sạch: `venv-solver` (có OR-Tools) và `venv-core` (không OR-Tools); wheel cài `--no-deps`.
- 29/29 file `tkb_core/*.py` đã cài khớp byte với `src/` tại HEAD ở cả hai venv.

| Lệnh (venv) | Exit | Kết quả |
|---|---|---|
| solver: `solve hard_soft.json --time-limit 10 --workers 1 --seed 42 --output result.json` | 0 | 1.3 OPTIMAL, policy 0.2, LEXICOGRAPHIC_OPTIMAL `[2,0,0]` |
| solver: `validate-schedule hard_soft.json result.json` | 0 | 1.3 SCHEDULE_VALID |
| solver / core: `evaluate-score hard_soft.json result.json` | 0 / 0 | OK `[2,0,0]` |
| core: `validate-schedule hard_soft.json result.json` | 0 | SCHEDULE_VALID |
| core: `evaluate-score hard_soft.json forged.json` | 2 | INVALID_SCHEDULE |
| solver: `validate-schedule hard_soft.json forged.json` | 2 | INPUT_INVALID / INVALID_SCHEDULE |
| core API `validate_schedule(forged)` | – | `HARD_DAY_LIMIT` |
| solver: `solve infeasible.json` | 3 | 1.3 INFEASIBLE, 0 assignments |
| solver: `solve policy01_hard.json` | 2 | 1.2 UNSUPPORTED_FEATURE / CUSTOM_HARD_RULE |
| core: `solve hard_soft.json` | 2 | SOLVER_NOT_INSTALLED |
| solver: `solve legacy10.json --output legacy_result.json` | 0 | output 1.1 |
| core: `validate-schedule legacy10.json legacy_result.json` | 0 | 1.1 SCHEDULE_VALID |
| core: `validate-schedule legacy10.json legacy_forged13.json` | 2 | RESULT_VERSION (F1 đã sửa) |
| core: `evaluate-score legacy10.json legacy_forged13.json` | 2 | RESULT_VERSION (F1 đã sửa) |

Input: `hard_soft.json` (hard S03 limit 2 + hard S01 `1-AM-1` + soft tránh ngày 2); `infeasible.json`
(S03 limit 1); `policy01_hard.json` (cùng rule, policy 0.1); `legacy10.json` =
`tests/fixtures/feasible_small.json`; `forged.json` dời lịch hợp lệ để vượt tải ngày 1;
`legacy_forged13.json` gắn nhãn 1.3/0.2 cho result 1.1 của input 1.0. Chưa kiểm sdist,
Windows/cross-OS, pilot/campaign.

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
- Installed wheel chỉ được kiểm trên Linux, n=1, input synthetic (mục trên); chưa có Windows,
  sdist hoặc campaign. Receipt wheel Phase 2A và wheel `3bde3b95…` không áp dụng cho `d7de450`.
