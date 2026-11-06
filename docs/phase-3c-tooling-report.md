# Phase 3C — báo cáo tooling benchmark repair

Ngày 2026-11-06. Base `ffd5c38` trên `main`. Người dùng duyệt C1–C10 của
[kế hoạch 3C](superpowers/plans/2026-11-06-phase-3c-repair-benchmark.md) và ủy quyền Task 1–5 (bước B).
**Trạng thái: tooling + smoke trên máy Linux; chưa chạy campaign (bước D–F cần ủy quyền riêng).**

Không sửa `src/`, tooling v1 hay v2. Smoke dưới đây **không phải số đo**: budget thu nhỏ, chỉ để kiểm
đường chạy end-to-end.

## Đã làm

| Task | File | Nội dung |
|---|---|---|
| 1 | `benchmarks/generate_phase3c.py` | Chọn 18 dataset s101 và 18 UNSAT; nhiễu N1–N4 xác định theo seed (dataset, nhiễu, ứng viên); precheck 3B gắn `EXPECTED_INFEASIBLE`, thử tối đa 10 ứng viên; request tường minh |
| 2 | `benchmarks/run_phase3c.py` | `prepare` (seal 1: bước S, X), `run --stage S|R|X`, `derive` (seal 2: bước R); supervise bằng v1; bước S dùng `run_cli_once` và verdict v2; repair/explain kiểm độc lập trong venv không OR-Tools; journal + receipt theo từng stage |
| 3 | `benchmarks/judge_phase3c.py` | Verdict H/P/C/Q/X và gate dừng |
| 4 | `benchmarks/aggregate_phase3c.py` | Bảng theo ô (part/quy mô/profile/biến thể/nhiễu), cặp hint/không hint, cặp BEFORE/AFTER, censored |
| 5 | Test + smoke | 4 file test mới; smoke end-to-end (mục dưới) |

## Sai khác so với kế hoạch

1. **Seal hai tầng.** C3 (lịch trước giải trong campaign) và §2.3 (N1 chọn ngày GV *đang dạy*, N4 chọn ô
   *khác vị trí cũ*) chỉ thỏa được khi input nhiễu sinh **sau** bước S. Vì vậy `prepare` seal `plan.json`
   (bước S và X), còn `derive` seal `derived.json` (bước R) sau khi S COMPLETE; `seal-derived.json` móc
   vào hash của `plan.json`, và mỗi lịch trước được ghi kèm SHA256. Mọi input vẫn được băm trước khi run
   của chính nó bắt đầu, nhưng không phải trước seal đầu tiên như §2.3 viết.
2. **Explain cho repair INFEASIBLE** (C8) chạy như một child supervise riêng trong thư mục `explain/`
   của chính run repair đó, không phải một hàng X riêng; kết quả nằm trong `verdict.explain`.
3. **Không có resume.** Mỗi stage chạy một lần; journal của stage đã tồn tại → BLOCKED
   (`STAGE_ALREADY_STARTED`). Bị admission gate chặn cũng cần campaign ID mới. v2 có `--resume` cho
   trường hợp gate; 3C chưa có.
4. **Thứ tự stage cố định** S → (derive) → R → X; X đòi R COMPLETE.
5. **`prepare` không smoke đòi `--reference-plan`** (plan campaign-02) để kiểm C2 trùng byte; smoke bỏ qua.
6. **Smoke** (`--smoke`): 2 dataset 10 lớp BASE (SOFT, HARD), 1 UNSAT; R1 = N1 có hint; không R2; budget
   5 s, watchdog 60 s. Plan smoke tự đánh dấu `smoke=true`.

## Tests mới

| File | Số test | Nội dung |
|---|---:|---|
| `benchmarks/tests/test_generate_phase3c.py` | 11 | Chọn dataset; N1–N4 xác định và hợp lệ; N1 bỏ đúng một ngày GV đang dạy; N2 đổi đúng một requirement; N3 +1/−1 tiết, occurrence bị bỏ là ordinal cuối; N4 khóa 2 occurrence khác vị trí cũ; input luôn vô nghiệm → `EXPECTED_INFEASIBLE` sau 10 ứng viên; request tường minh |
| `benchmarks/tests/test_judge_phase3c.py` | 7 | Repair có lịch trong/vượt giới hạn; lịch cho input đã chứng minh vô nghiệm → H FAIL, STOPPED; INFEASIBLE/UNKNOWN không dừng; watchdog → P NOT_MET; output sai → STOPPED; explain trên UNSAT (PRECHECK_PROOF đạt, NOT_INFEASIBLE → FAIL) |
| `benchmarks/tests/test_run_phase3c.py` | 10 | Tooling v2 trùng byte với `f58f257`; plan smoke đúng thành phần và budget; plan đầy đủ đòi đủ thành phần; budget/run ID không đổi được; R1 = 144, R2 = 48; derive băm input/lịch trước/request, xác định, ghi loại trừ; `Derived3C` từ chối thiếu hàng |
| `benchmarks/tests/test_aggregate_phase3c.py` | 3 | Đếm và censored; cặp hint và cặp BEFORE/AFTER; markdown nêu n = 1, không P95 |

**TDD:** test của Task 1–4 viết trước và chạy RED (thiếu module) trước khi viết code. Hai test được sửa
vì kỳ vọng sai: N3 với requirement có tiết đôi (số occurrence khác số tiết), và fixture repair INFEASIBLE
tự dựng sai contract output 1.5 (thay bằng repair INFEASIBLE thật).

Chạy thử generator trên 18 dataset thật (witness làm lịch trước tạm, ngoài test): 62/72 input nhiễu
`GROUND_TRUTH_UNKNOWN`, 10 `EXPECTED_INFEASIBLE`, tất cả ở profile TIGHT với N1/N2 (TIGHT dựng sát giới
hạn). Mất khoảng 80 s, chủ yếu để sinh dataset 40 lớp.

## Smoke trên máy Linux (không phải số đo)

Máy của người dùng (i7-12700H, cgroup2), không kiểm soát tải. Thư mục
`benchmarks/artifacts/phase3c-smoke-20261106/` (local, ignored).

1. `python -m benchmarks.generate_phase2 --output …/bundle` → exit 0 (bundle v2 đầy đủ 72 dataset).
2. `python -m benchmarks.run_phase2 --phase preflight --output …/preflight --bundle …/bundle` → `PREFLIGHT_PASS`.
   Wheel SHA256 `7ae89efc8453ac279026fc249f7e1da22d4623e2356441ca837db94697563b98` (trùng wheel đã kiểm khi
   sửa F6 của 3B; cùng `src/`).
3. Bằng `preflight/venv-solver/bin/python`:

| Lệnh | Exit | Kết quả |
|---|---:|---|
| `run_phase3c prepare --smoke --campaign-id phase3c-smoke-01` | 0 | `PREPARED`, 4 hàng; kiểm bundle bằng sinh lại; plan ghi HEAD `ffd5c38` với working tree chưa commit |
| `run … --stage S` | 0 | COMPLETE 2/2; lịch trước FEASIBLE `[9,71,252]` (HARD) và `[48,144,210]` (SOFT); H PASS, P MET |
| `derive` | 0 | `DERIVED`, 2 hàng, không loại dataset; N1 bỏ ngày 6 của T001 (HARD), ngày 4 của T005 (SOFT) |
| `run … --stage R` | 0 | COMPLETE 2/2; repair OPTIMAL, `changed = forced` (2 và 1), `min_changes_proved`; 3 kiểm độc lập (validate, score, evaluate-repair) OK |
| `run … --stage X` | 0 | COMPLETE 2/2; `PRECHECK_PROOF` (MODEL, FULL), 0 lời gọi solver; `check-explanation` OK |
| `aggregate_phase3c --campaign …` | 0 | `SUMMARIZED`; bảng theo ô như kỳ vọng |
| `run … --stage S` lần hai | 1 | BLOCKED `STAGE_ALREADY_STARTED` |
| Sửa 1 byte một input đã derive rồi `check_derived` | — | `DERIVED_INPUT_DRIFT` (khôi phục file, kiểm lại nguyên vẹn) |

Không được thử trong smoke: repair trả INFEASIBLE (explain theo sau), UNKNOWN/watchdog thật, admission
gate chặn, R2, dataset 20/40 lớp. Các đường này chỉ có unit test hoặc chưa có.

## Sửa sau sự cố `phase3c-linux-01` (2026-11-07)

Campaign `phase3c-linux-01` (commit ghim `1ab0764`) dừng ở stage R, run 43/192
`R1-c10-tight-s101-soft-N2-hint1`. S COMPLETE 18/18, derive 192 hàng, X chưa chạy. Raw evidence ở máy,
`phase3c-campaign-01.tar.gz` có SHA256 `fa4061c9…5a93d7`.

- **Nguyên nhân.** Nhiễu N2 (ứng viên 9) giao `REQ-C006-S03` cho T011. Requirement này có khóa
  `::4` ở `d06-am-p02`, nhưng T011 không rảnh ô đó. Precheck 3B coi đây là bằng chứng vô nghiệm
  (`PC_LOCK_OVERLAP`, `PC_EMPTY_DOMAIN`) nên gắn nhãn `EXPECTED_INFEASIBLE`. Còn `prepare` của core
  trả `INPUT_INVALID / LOCK_CONFLICT`. Judge xếp trạng thái này vào `UNEXPECTED_STATUS`, ra H FAIL rồi
  `STOPPED`. Core làm đúng; lỗi nằm ở tooling.
- **Sửa generator.** `derive_noise` bỏ qua ứng viên mà `prepare` của core từ chối (`core_rejection`:
  `INPUT_INVALID`/`UNSUPPORTED_FEATURE`). INFEASIBLE và UNKNOWN từ `prepare` không bị coi là từ chối.
- **Sửa judge.** `judge_repair` xử lý `INPUT_INVALID`/`UNSUPPORTED_FEATURE` thành nhánh riêng: H và P
  `NOT_APPLICABLE`, reasons `CORE_REJECTED_INPUT` kèm mã diagnostic, không dừng campaign.
- **Test.** Thêm 2 test hồi quy, tái hiện bằng dataset `c10-tight-s101-soft`/N2 và verdict
  `INPUT_INVALID`; cả hai RED trước khi sửa.
- **Kiểm trên dữ liệu thật.** Sinh lại 72 input nhiễu từ 18 lịch stage S của campaign-01, ngoài
  campaign, khoảng 133 s. Chỉ `c10-tight-s101-soft/N2` đổi (ứng viên 9 → 8, vẫn `EXPECTED_INFEASIBLE`
  với `PC_RESOURCE_CAPACITY`); 71 input còn lại trùng. Input cũ là input duy nhất bị core từ chối.
- **Checks.** `pytest tests benchmarks/tests` 2002 passed, 22 skipped; ruff, format và mypy đều PASS.
  `src/` và tooling v1/v2 không đổi so với `1ab0764`.

Chạy lại cần commit ghim mới, cập nhật runbook và campaign ID mới (`phase3c-linux-02`).

## Lệnh kiểm tra

| Lệnh | Kết quả |
|---|---|
| `uv run --extra solver pytest tests benchmarks/tests` | **2000 passed, 22 skipped** (trước: 1969/22); 31 test mới |
| `uv run ruff check .`, `uv run ruff format --check src tests benchmarks` | PASS (141 file) |
| `uv run mypy` | PASS (44 file; mypy chỉ quét `src/`, như trước) |
| `git diff f58f257 --` tooling v1/v2 (5 file) | Rỗng |
| `git diff ffd5c38 -- src` | Rỗng |

## Hạn chế

- Tooling chưa có `--resume`; bị gate chặn giữa chừng thì phải dùng campaign ID mới.
- Thời lượng thật chưa biết; ước lượng của kế hoạch (≈ 6,2 h budget, ≈ 11,5 h trần watchdog) chưa được
  kiểm. Bước S và derive ở 40 lớp tốn thêm vài phút sinh nhiễu.
- Nhiễu N1/N2 trên TIGHT thường sinh input vô nghiệm; báo cáo campaign phải tách các ô đó.
- Không có runbook D/E/F cho 3C trong lượt này (bước C của kế hoạch).
