# Phase 2C-1 — báo cáo triển khai phân phối môn S05/S06

Ngày 2026-11-05. Base `ebc9b85` (đặc tả/kế hoạch DRAFT) trên `7e83fd3` (`main`), nhánh
`work/phase2a-operational-completion`. Người dùng duyệt D1–D7 theo đề xuất và ủy quyền Task 1–8.
**Trạng thái: TECHNICAL SYNTHETIC — triển khai trong working tree, chờ duyệt commit.**

Phạm vi: [đặc tả](superpowers/specs/2026-11-05-phase-2c-subject-distribution-design.md),
[kế hoạch](superpowers/plans/2026-11-05-phase-2c-subject-distribution.md). Không sửa `benchmarks/`,
gate, budget, pins, `research/` hoặc `reverse-engineering/`; không pilot/campaign, witness hint,
wheel hay installed preflight.

## Đã triển khai

| Quyết định | Hiện thực |
|---|---|
| D1 policy 0.3 | `policy_version` nhận `0.3`; `RuleDefinition` có `soft_policies`/`hard_policies`/`since_policy`; S05/S06 `since_policy="0.3"` nên 0.1/0.2 coi là mã unknown (raw params, UNKNOWN_RULE) |
| D2 output 1.4 + ScoreReport 1.1 | `QUALITY_POLICY["1.4"]="0.3"`, `SCORE_VERSION` ép 1.2/1.3→Score 1.0, 1.4→Score 1.1; `RuleScore.unit` thêm `day_gap_shortfall`, Score 1.0 từ chối unit này; `solve`/CLI/evaluator chọn version theo policy |
| D3 nhóm S05 | `DaySpreadParameters(requirement_ids, min_day_gap≥1)`; scope phải rỗng; reference/duplicate kiểm ở contract; fingerprint sort `requirement_ids` |
| D4 khoảng cách | Hiệu giá trị `TimeSlot.day` của start slot |
| D5 scope S06 | `SubjectDayLimitParameters(limit)`; scope `class_ids`/`subject_ids`, cấm teacher/room |
| D6 hard | S05: cửa sổ k ngày ≤ 1 component; S06: bucket ≤ limit (`constraints/hard.add_distribution_limits`, trước clone hard model); validator `HARD_DAY_SPREAD`, `HARD_SUBJECT_DAY_LIMIT` |
| D7 ordering | S05/S06 thêm vào allowlist ordering sau oracle (mục dưới) |

Soft compiler: `soft._compile_distribution` (S05 `AddAbsEquality` + `AddMaxEquality` từng cặp; S06
`AddMaxEquality` theo bucket), raw là equality và có range guard `OBJECTIVE_RANGE`. Evaluator và
validator viết riêng, không import compiler/solver (subprocess guard). Overlap theo family bất kể mode.

## Tests mới / sửa

| File | Nội dung |
|---|---|
| `tests/unit/test_subject_distribution_contracts.py` | Version 0.3/0.4, 0.1/0.2 coi mã mới là unknown (cả payload raw), mode matrix, tham số, scope theo family, overlap S05/S06, fingerprint, Score 1.0/1.1 units, cặp output/policy/score |
| `tests/unit/test_subject_distribution_score.py` | Ví dụ policy (1,1,3)/k=2→2; split `[2,1,1,1]` 6 cặp; nhóm 1 component; nhiều requirement; ngày không liên tục; S06 double/AM+PM/limit 0/scope/weight; unit hỗn hợp |
| `tests/unit/test_subject_distribution_validator.py` | Forged S05/S06 → `HARD_*` đúng IDs, mọi cặp gần; disabled; 0.2 → UNSUPPORTED; evaluate_score; cô lập import |
| `tests/unit/test_soft_compilers.py` (thêm) | Giá trị raw S05/S06 với placement cưỡng bức, không objective; range guard |
| `tests/unit/test_subject_distribution_model.py` | Cửa sổ hard ≡ định nghĩa cặp; vô nghiệm khi k vượt cycle; S06 double; range guard; model 0.1/0.2 không đổi |
| `tests/integration/test_subject_distribution_solver.py` | 1.4/Score 1.1, LEXICOGRAPHIC_OPTIMAL; hard-only; hard S06 buộc soft `(2,0,0)`; INFEASIBLE; compiler hard/soft sai → MODEL_INVALID; 0.2 vẫn 1.3 |
| `tests/integration/test_subject_distribution_cli.py` | solve→1.4→validate/evaluate (Score 1.1); forged hard → exit 2; RESULT_VERSION với Score 1.1; evaluate-score không OR-Tools/compiler |
| `tests/properties/test_subject_distribution_oracle.py` | Oracle vét cạn độc lập, 60 seeds × ordering bật/tắt, trộn S05/S06 soft/hard với S01/S03/S04; spy ordering |

Sửa test cũ có chủ ý: `test_cli.py` (enum output thêm 1.4); `test_hard_variant_contracts.py` (`0.3`
nay hợp lệ nên dùng `0.4` làm version lạ; mode matrix chỉ cho S01–S04);
`test_quality_contracts.py` (DEFINITIONS có thêm hai mã, không có mode ở 0.1). Thêm fixture `dist_case`.

## Lệnh đã chạy và kết quả

| Lệnh | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS (lock không đổi) |
| `uv run --extra solver pytest` trước khi sửa | 537 passed (baseline) |
| `uv run --extra solver pytest` | **720 passed** |
| `uv run --extra solver pytest tests benchmarks/tests` | **1085 passed, 8 skipped** |
| `uv run ruff check .`, `uv run ruff format --check src tests`, `uv run mypy` | PASS (29 source files) |
| `git diff --check` | PASS |

8 skips là test cần Windows native/opt-in như trước; không phải Windows đã chạy.

## TDD và sai khác so với kế hoạch

- Task 1–5 và hard compiler Task 6: test chạy RED trước khi sửa product code.
- Pipeline (Task 6) và CLI (Task 8): phần wiring version đã viết ở Task 1, nên test mới xanh ngay
  lần đầu. Đã kiểm chúng có tác dụng bằng cách tạm khôi phục file cũ: `cp_sat.py` cũ → 7/8 failed;
  `cli.py` cũ → 4/4 failed; khôi phục → xanh.
- D7: spy test RED khi bỏ S05/S06 khỏi allowlist, GREEN khi thêm; oracle khớp ở cả hai chế độ.
- Lộ ra khi chạy full suite: một mã đã khai báo nhưng chưa có mode nào (test `PENDING_RULE`) phải giữ
  lỗi `CUSTOM_RULE`; vì vậy dùng `since_policy` thay cho “biết mã khi có mode”.
- Oracle không dùng S02 và không có timed calendar, lock hay phòng; các trường hợp đó dựa trên unit
  tests của 2A/2B và 2C-1.

## Giới hạn

- Synthetic only: không chứng nhận k/limit thực tế của trường, chất lượng giáo vụ, hiệu năng, Windows.
- S05 soft tạo O(n²) biến theo cỡ nhóm; chưa đo trên dữ liệu lớn, không tuyên bố tốc độ.
- INFEASIBLE không chỉ ra rule nguyên nhân. Không có precheck tổng hợp cho S05/S06.
- Weight trong cùng tier cộng hai unit khác nhau (ngày thiếu và tiết); đó là trade-off caller chọn.
- Chưa build wheel/installed preflight cho source này. Hạn chế Phase 2A/2B giữ nguyên.
