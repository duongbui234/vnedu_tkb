# Phase 2 hiệu năng v2 — rà soát tooling `42d0ccd..d23124f`

Ngày 2026-11-05. Phạm vi: commit `d23124f` (8 files, +3637/−1). Đối chiếu với
[kế hoạch v2](superpowers/plans/2026-11-05-phase-2-linux-performance-v2.md) và
[acceptance v2](phase-2a-acceptance-v2-draft.md). Không sửa code; không sinh bundle, không chạy
preflight, pilot hay campaign. Người rà soát là cùng phiên với người triển khai, nên đây là **tự kiểm lại**
bằng đọc code và red probe, không phải review của người thứ hai.

**Kết luận: 0 finding P1; 1 finding P2; 4 finding P3; 4 quan sát.**
**Cập nhật: F1–F5 đã sửa theo TDD (xem dòng "Đã sửa" ở từng finding và mục cuối).** Không finding nào làm một lịch sai được
tính là đạt, hay làm campaign chạy tiếp qua gate an toàn: các run bị ảnh hưởng vẫn bị dừng. Lỗi nằm ở
nhãn verdict và phần tổng hợp, nên nên sửa trước khi có evidence thật.

## Finding

### F1 (P2) — Output sai của Core trên dataset known-feasible được ghi H NOT_APPLICABLE, không phải FAIL

Khi Core trả một lịch nhưng output không qua bộ kiểm độc lập, harness ghi `OUTPUT_INVALID`. Ví dụ là
score nhúng trong result lệch với evaluator. Lúc đó `judge_case` đi vào nhánh "không có lịch" và gán
`hard = NOT_APPLICABLE`, `quality = NO_SCHEDULE`. Theo acceptance v2 H4 ("score/proof sai là lỗi kỹ thuật")
thì đây phải là H FAIL.

- Gate dừng vẫn hoạt động: `stop_status` trả STOPPED vì `OUTPUT_INVALID`. Campaign không chạy tiếp.
- Tuy vậy, aggregator chỉ thấy H NOT_APPLICABLE cùng các run còn thiếu, nên tóm tắt ghi **H INCOMPLETE**
  thay vì **H FAIL**. Một lỗi tính đúng của Core sẽ hiện ra như thiếu coverage.
- v1 có hành vi tương tự (correctness NOT_ASSESSED), nên đây không phải hồi quy. Nhưng v2 tách trục H
  riêng, nên nhãn này quan trọng hơn.
- Red probe `test_output_invalid_is_h_fail`: sửa `raw_penalty`, `weighted_penalty` và tier cho nhất quán
  → `OUTPUT_INVALID` → verdict `hard='NOT_APPLICABLE'` (FAILED).
- Đề xuất: với dataset known-feasible, `OUTPUT_INVALID` → H FAIL, kèm lý do `OUTPUT_INVALID:<diagnostic>`.
  Không đổi CRASH, MEASUREMENT_BLOCKED hay ENVIRONMENT_BLOCKED thành H FAIL, vì đó là lỗi môi trường
  hoặc đo đạc, không phải bằng chứng Core sai.
- **Đã sửa:** `judge_case` trả H FAIL với lý do `OUTPUT_INVALID:<diagnostics>` cho mọi dataset (cả UNSAT);
  lỗi đo vẫn là NOT_APPLICABLE/INCOMPLETE. Regression `test_output_invalid_on_known_feasible_is_h_fail`
  và `test_measurement_failure_is_not_h_fail`.

### F2 (P3) — Bộ đếm zero của aggregator không phủ hết mẫu số

`summarize` chỉ cộng các run thiếu vào `zero.NOT_APPLICABLE` khi **không có verdict nào**. Khi chỉ một phần
bị thiếu, tổng MET + NOT_MET + NOT_APPLICABLE nhỏ hơn số run đã lập kế hoạch. Red probe
`test_zero_counts_cover_the_denominator`: 4 planned, 1 missing → tổng 3 (FAILED). Đề xuất: thêm nhãn
`MISSING` riêng, không gộp vào NOT_APPLICABLE.
**Đã sửa:** `zero` có thêm `MISSING`; tổng luôn bằng số run kế hoạch (`test_zero_counts_cover_the_denominator`).

### F3 (P3) — Run UNSAT chưa hoàn tất làm campaign P thành NOT_MET thay vì INCOMPLETE

Aggregator coi mọi UNSAT có `hard != "PASS"` là NOT_MET, kể cả `NOT_ASSESSED` (ví dụ MEASUREMENT_BLOCKED).
Theo §4 của kế hoạch, thiếu outcome hoặc measurement là INCOMPLETE. Red probe
`test_incomplete_unsat_execution_is_not_p_not_met` (FAILED). Đề xuất: chỉ UNSAT `hard == FAIL` mới làm P
NOT_MET; `NOT_ASSESSED` → INCOMPLETE.
**Đã sửa:** UNSAT FAIL → P NOT_MET; UNSAT chưa đánh giá → P INCOMPLETE và H INCOMPLETE (coverage H
chưa đủ). Regression `test_incomplete_unsat_execution_is_p_incomplete`.

### F4 (P3) — `run_cli_once` bỏ lần kiểm hash input cuối cùng trước khi spawn

v1 kiểm `_sha(input_path)` thêm một lần ngay trước khi spawn, sau khi dựng identity
(`run_benchmarks.py:645`). Bản v2 chỉ kiểm bytes đã đọc (`run_phase2.py:583`). Hai lần kiểm sau run vẫn
còn, nên một thay đổi input vẫn bị phát hiện, chỉ là muộn hơn. Đề xuất: khôi phục đúng lần kiểm của v1.
**Đã sửa:** thêm lần kiểm hash ngay trước spawn; input đổi → ENVIRONMENT_BLOCKED
`INPUT_CHANGED_BEFORE_SPAWN`, không spawn (`test_input_changed_after_capture_is_never_spawned`).

### F5 (P3) — Kiểm bundle dùng interpreter dev và không có import guard

- **Preflight** chạy bước kiểm bundle bằng `sys.executable` của tiến trình preflight, tức môi trường dev
  với Core editable, không phải venv solver đã cài. Cũng không có `import_guard(scoring=False)` như
  `phase2a_preflight verify-bundle` của v1.
- **Prepare** kiểm lại bằng venv đang chạy, cũng không có guard. Khác v1, prepare không đòi
  `peak_resident_bytes` có mặt và không vượt giới hạn.
- Tác động thấp: không có search, và test `test_no_solver_imports_in_generator` đã chặn import solver
  trong generator. Nhưng bằng chứng "bundle được kiểm bằng đúng Core đã cài" yếu hơn v1.
- Đề xuất: preflight dùng `pythons["solver"]` cùng import guard; prepare thêm điều kiện peak RSS như v1.
- **Đã sửa:** `bundle_verification_argv` chạy `verify_bundle` trong `import_guard(scoring=False)` của v1,
  bằng interpreter được truyền vào: preflight dùng venv solver đã cài, prepare dùng venv đang chạy.
  `bundle_verification_passed` đòi measurement OK, exit 0, peak RSS có mặt và ≤ 2 GiB, cùng marker
  thành công. Regressions: `test_bundle_verification_is_guarded_and_bounded`,
  `test_guarded_bundle_script_runs`, `test_preflight_verifies_bundle_with_installed_solver`.

## Quan sát

- **O1 — Chưa chạy end-to-end.** `preflight`, `prepare` và `execute_campaign` (warmup, pilot, primary) chưa
  chạy với wheel đã cài. Test chỉ kiểm plan chưa seal bị chặn. Lỗi tích hợp (ví dụ đường dẫn `-m
  benchmarks.run_phase2` trong venv) chỉ lộ ra ở bước D/E.
- **O2 — Bundle gắn chặt với source Core.** `validate_dataset` so với bản sinh lại, nên mọi thay đổi Core
  hoặc generator làm bundle cũ hết hiệu lực. Điều này có chủ ý (identity), nhưng nghĩa là phải sinh bundle
  mới sau mỗi thay đổi product.
- **O3 — Test smoke dùng cùng interpreter dev** cho cả nhãn solver và no-solver. Việc tách hai venv chỉ
  được kiểm khi chạy preflight thật.
- **O4 — Rule set khác v1** (zero NOT_APPLICABLE ở 72/72; S05 bỏ khoảng một nửa requirement nhiều
  component). Đây là thiết kế đã duyệt (G2/G5) và đã ghi ở §11 của kế hoạch, không phải lỗi. Báo cáo
  campaign không được đặt cạnh số v1 như cùng bài.

## Đã kiểm, không phát hiện lỗi

| Điểm | Cách kiểm |
|---|---|
| Tooling v1 không đổi | `git diff 5d685f9 d23124f` rỗng cho `run_benchmarks.py`, `generate_synthetic.py`, `aggregate_linux.py`; test byte-identical 6 file |
| Bảng version ↔ Core | `check_version_table` khớp `QUALITY_POLICY`/`SCORE_VERSION`; bốn cặp 0.1–0.4 solve và verify thật |
| D1/D2: score nonzero không chặn P; pilot cần H PASS + lịch + P MET | Tests và mutation-check sáu gate (§11 của kế hoạch) |
| Budget, watchdog, RSS | `BUDGETS == run_benchmarks._BUDGETS`; `PlannedCase` từ chối budget hoặc pilot lệch |
| Plan 216 + 2 pilot, thứ tự seed 2026 | Test fake bundle; đổi thứ tự, bớt dòng, đảo pilot hay seal thiếu identity đều bị từ chối |
| Generator | 32 test và lần sinh trong bộ nhớ đủ 72 dataset: tham số suy từ witness cho raw 0, witness hard-valid, availability/locks trùng v1 |

## Lệnh đã chạy

| Lệnh | Kết quả |
|---|---|
| `git diff --quiet 5d685f9 d23124f -- <file v1>` | Không đổi (3 file chính) |
| `PYTHONPATH=. uv run --extra solver pytest …/review_v2/test_review_v2_red.py` | **3 failed** (F1, F2, F3), đúng lý do dự kiến |
| Đọc code | F4 (`run_benchmarks.py:645` so với `run_phase2.py:583`), F5 (`run_phase2.py:1388`) |

Probe nằm trong scratchpad của phiên (ngoài repo, mất khi container bị thu hồi). Lần chạy full suite gần
nhất là ở bước triển khai (1341 passed, 8 skipped); lượt rà soát không chạy lại.

## Sửa F1–F5 (được người dùng ủy quyền)

Test regression viết trước và chạy **8 failed** trên `d23124f`, gồm 7 test mới và test zero cũ đã cập
nhật kỳ vọng. `test_measurement_failure_is_not_h_fail` xanh ngay vì là test chặn sửa quá tay. Sau khi sửa
`run_phase2.py` và `aggregate_phase2.py`, tất cả xanh. Không sửa `src/` hay tooling v1.

| Lệnh | Kết quả |
|---|---|
| Probe rà soát trong scratchpad | 3 passed (trước đó 3 failed) |
| `uv run --extra solver pytest tests benchmarks/tests` | **1349 passed, 8 skipped** |
| `uv run ruff check .`, `uv run ruff format --check src tests benchmarks`, `uv run mypy` | PASS |
| Test byte-identical v1 | PASS (nằm trong suite) |

Các quan sát O1–O4 vẫn mở: preflight, prepare và campaign chưa chạy thật.
