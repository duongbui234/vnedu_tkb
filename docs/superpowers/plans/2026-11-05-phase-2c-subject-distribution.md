# Phase 2C-1 — kế hoạch triển khai S05/S06

Ngày 2026-11-05. Trạng thái: **DRAFT — CHỜ DUYỆT; CHƯA CÓ ỦY QUYỀN TRIỂN KHAI.**
Đặc tả: [2026-11-05-phase-2c-subject-distribution-design.md](../specs/2026-11-05-phase-2c-subject-distribution-design.md).
Base `7e83fd349772412289b34864d89199c200e3ffdf` trên `main`.

Kế hoạch giả định D1–D7 được duyệt như đề xuất; nếu chọn khác thì cập nhật đặc tả và các task bị ảnh
hưởng trước khi viết code. Mỗi task theo TDD: viết test, chạy xác nhận RED, sửa tối thiểu, GREEN. Không
sửa `benchmarks/`, gate, budget hay pins; không witness hint; không pilot/campaign; không commit trong
các task. Toàn bộ Task 1–8 nằm trong một working tree, nên capability chỉ được phát hành ở commit cuối.

## Ranh giới phê duyệt

| Bước | Cần duyệt riêng |
|---|---|
| A. Duyệt đặc tả + D1–D7 | Có — lượt này dừng ở đây |
| B. Triển khai Task 1–8 trong working tree, chạy checks | Có (product code) |
| C. Docs + checks + commit + push (+ PR nếu muốn) | Có, gộp một lần |

## Task 1 — Contract policy 0.3, output 1.4, ScoreReport 1.1 (D1, D2)

Files: `domain/models.py`, `contracts/score.py`, `contracts/output.py`, `solver/cp_sat.py`, `cli.py`,
`tests/unit/test_subject_distribution_contracts.py` (mới), `tests/integration/test_cli.py`.

1. RED: 0.3 parse/roundtrip; 0.4 reject; output 1.4 ↔ 0.3 ↔ ScoreReport 1.1, mọi cặp sai reject;
   ScoreReport 1.0 từ chối unit `day_gap_shortfall`; hash của fixtures 0.1/0.2 không đổi.
2. Mở literal; `QUALITY_POLICY` thêm `"1.4": "0.3"`; ScoreReport version chọn theo policy;
   `solve`/CLI chọn 1.4 và `RESULT_VERSION` cho 0.3. Policy 0.3 kế thừa capability S01–S04 của 0.2.

## Task 2 — Registry, parameters, scope và overlap (D3, D5)

Files: `domain/rule_parameters.py` (`DaySpreadParameters`, `SubjectDayLimitParameters`),
`constraints/registry.py`, `contracts/input.py` (reference `requirement_ids`, sort set khi fingerprint),
`contracts/capabilities.py`, tests trong file mới ở Task 1.

1. RED: `min_day_gap ≥ 1`, requirement lạ/trùng; S05 có scope → RULE_SCOPE; S06 teacher/room scope →
   RULE_SCOPE; 0.1/0.2 enabled → UNKNOWN_RULE; overlap S05 chung requirement, S06 giao lớp×môn, mọi mode.
2. Registry: hai `RuleDefinition` mới, `soft_policies=("0.3",)`, `hard_policies=("0.3",)`, unit
   theo code; scope check theo family thay vì “chỉ teacher”.
3. Fingerprint: sort `requirement_ids` như các known sets khác.

## Task 3 — Independent evaluator (soft)

Files: `validation/score_evaluator.py`, `tests/unit/test_subject_distribution_score.py` (mới).

1. RED: ví dụ §3.1 (k=2, ngày 1,1,3 → 2); split `[2,1,1,1]` 6 cặp; nhóm 1 component = 0; nhiều
   requirement; ngày không liên tục; S06 double = 2, AM+PM cộng, limit 0, scope rỗng/lọc.
2. Hiện thực độc lập, unit đúng trong `RuleScore`.

## Task 4 — Independent hard checker

Files: `validation/independent_validator.py`, `tests/unit/test_subject_distribution_validator.py` (mới).

1. RED: forged vi phạm S05/S06 hard → `HARD_DAY_SPREAD` / `HARD_SUBJECT_DAY_LIMIT` với đúng IDs; disabled
   không kiểm; `evaluate_score` → INVALID_SCHEDULE; subprocess guard chặn import compiler/solver.

## Task 5 — Soft compiler

Files: `constraints/soft.py`, `tests/unit/test_soft_compilers.py` (thêm ca).

1. RED: model nhỏ với placement cưỡng bức → giá trị `raw` đúng bằng tay cho S05/S06 **trước khi**
   tối ưu (equality, không chỉ `≥`); range guard `OBJECTIVE_RANGE`.
2. `day_o` tuyến tính; `AddAbsEquality` + `AddMaxEquality` cho từng cặp; bucket (c,s,d) cho S06.

## Task 6 — Hard compiler và pipeline

Files: `constraints/hard.py`, `solver/model_builder.py`,
`tests/unit/test_subject_distribution_model.py` (mới),
`tests/integration/test_subject_distribution_solver.py` (mới).

1. RED: hard S05 cửa sổ: cặp khoảng cách k−1 bị cấm, k hợp lệ; S06 load = limit hợp lệ, +1 bị cấm;
   INFEASIBLE khi k vượt độ dài cycle; model 0.1/0.2 không đổi (so `str(proto)`); compiler bị
   monkeypatch bỏ → MODEL_INVALID; solve 0.3 soft-only, hard-only, trộn S01–S04.
2. Thêm hard trước clone `hard_model`; soft qua `compile_soft`.

## Task 7 — Oracle vét cạn và ordering (D7)

Files: `tests/properties/test_subject_distribution_oracle.py` (mới, oracle Python tự viết).

1. ≥ 60 seeds nhỏ (≤ 4 occurrence, 2–3 ngày, 1–2 lớp/môn), trộn S05/S06 soft/hard với S01–S04.
   So FEASIBLE/INFEASIBLE và optimum vector; chạy ordering bật/tắt.
2. Nếu mọi seed khớp ở cả hai chế độ → thêm S05/S06 vào allowlist ordering; ngược lại giữ tắt, ghi rõ.

## Task 8 — CLI/package và tài liệu

Files: `tests/integration/test_subject_distribution_cli.py` (mới), `README.md`,
`docs/constraint-catalog.md`, `docs/domain-model.md`, `docs/solver-design.md`, `docs/phase-2c-report.md`
(mới), trạng thái spec Phase 2 và spec/plan 2C-1.

1. RED: solve 0.3 → 1.4 → validate/evaluate; evaluate-score không OR-Tools; forged hard → exit 2;
   1.3 cho input 0.3 → RESULT_VERSION.
2. Docs: unit `day_gap_shortfall`; khoảng cách theo giá trị day; không cap/consecutive ngầm; không mặc
   định k hoặc limit; INFEASIBLE không chỉ ra rule.

## Checks trước khi báo hoàn thành (Bước B)

```bash
uv sync --locked --extra solver
```

```bash
uv run --extra solver pytest
```

```bash
uv run --extra solver pytest tests benchmarks/tests
```

```bash
uv run ruff check .
```

```bash
uv run ruff format --check src tests
```

```bash
uv run mypy
```

```bash
git diff --check
```

Baseline tại `7e83fd3`: 902 passed, 8 skipped (full suite, đo ở `d7de450`, cùng source). Báo số thực chạy.

## Rủi ro và giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| S05 soft O(n²) cặp mỗi nhóm làm model lớn | Một nhóm mỗi rule; bound và đếm cặp trước build; guard placement/terms hiện có; không tuyên bố hiệu năng |
| Cửa sổ hard S05 sai ở biên | Test forged + oracle brute force so với định nghĩa theo cặp |
| Version tăng nhanh (0.3/1.4/Score 1.1) | Strict pairing + regression cặp sai; tài liệu bảng version |
| Unit hỗn hợp trong một tier | Breakdown theo rule giữ unit; docs nêu trade-off weight giữa ngày-thiếu và tiết |
| Ordering làm mất optimum | Chỉ bật khi oracle Task 7 đạt |
