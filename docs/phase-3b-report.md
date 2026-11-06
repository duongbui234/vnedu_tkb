# Phase 3B — báo cáo triển khai chẩn đoán vô nghiệm

Ngày 2026-11-06. Base `c9d06e3` trên `main`. Người dùng duyệt B1–B10 (đặc tả) và B11 (từ spike), ủy quyền
Task 1–9. **Trạng thái: TECHNICAL SYNTHETIC — commit `f3b2c94` (đã push); sửa F1–F5 sau tự rà soát.**

Phạm vi: [đặc tả 3B](superpowers/specs/2026-11-06-phase-3b-infeasibility-diagnostics-design.md),
[kế hoạch 3B](superpowers/plans/2026-11-06-phase-3b-infeasibility-diagnostics.md). Không sửa
`solver/`, `preprocessing/`, `constraints/`, `repair/` hay `benchmarks/`: hành vi `solve()` và `repair()`
không đổi. Không chạy benchmark hay campaign.

## Đã làm

| Task | File | Nội dung |
|---|---|---|
| 1 | `contracts/diagnostics.py` | `InfeasibilityReport` 1.0, `ExplainOptions`, `GroupRef`, `PrecheckProof`, `Evidence`; kiểm nhất quán status ↔ trường |
| 2 | `diagnostics/groups.py` | Danh mục nhóm theo `MODEL`/`FULL`, thứ tự (kind, id) |
| 3 | `diagnostics/domains.py`, `diagnostics/prechecks.py`, `validation/precheck_verifier.py` | Domain gắn nhãn vi phạm; 8 precheck `PC_*` liệt kê hết; verifier độc lập |
| 4 | `diagnostics/model.py` | Model có literal theo nhóm, nhóm lọc-domain qua `x ⇒ ¬a`, B11 |
| 5 | `diagnostics/pipeline.py`, `diagnostics/__init__.py` | `explain_infeasibility()`: precheck → core → xác nhận → deletion → witness |
| 6 | `validation/independent_validator.py` | Tham số `relaxed_groups` (keyword, mặc định rỗng) |
| 7 | `tests/properties/test_diagnostics_oracle.py` | Oracle vét cạn mọi tập con nhóm, so có/không B11 |
| 8 | `cli.py` | Lệnh `explain`, `check-explanation` |
| 9 | Tài liệu | README, domain model, solver design, constraint catalog, báo cáo này, trạng thái đặc tả/kế hoạch |

## Sai khác so với đặc tả (đã ghi vào tài liệu)

1. **Kind availability tách ba:** `CLASS_AVAILABILITY`, `TEACHER_AVAILABILITY`, `ROOM_AVAILABILITY` thay vì
   một kind `AVAILABILITY`, để ID lớp/GV/phòng không lẫn nhau.
2. **Phần tử `subset` chỉ có `{kind, id}`,** không có `label`: input không có tên hiển thị ngoài ID.
3. **`PrecheckProof` thêm `resource_kind`** (`CLASS`, `TEACHER`, `ROOM`, `ROOM_TYPE`, `ROOM_ALL`,
   `CLASS_SUBJECT`) và một phép đếm phòng toàn cục (`ROOM_ALL`) khi có từ hai loại phòng trở lên.
4. **Khóa sai:** `solve()` vẫn trả `INPUT_INVALID / LOCK_CONFLICT`; `explain` coi đó là xung đột cần chẩn
   đoán (`PC_EMPTY_DOMAIN`, `PC_LOCK_OVERLAP` hoặc nhóm `LOCK`). Lỗi input/capability khác giữ nguyên mã.
5. **Có thêm một lời gọi xác nhận:** core từ `sufficient_assumptions_for_infeasibility()` được giải lại
   riêng để có status INFEASIBLE trực tiếp cho đúng tập đó (đặc tả §7). Xác nhận ra FEASIBLE →
   `MODEL_INVALID`; UNKNOWN → trả core với `minimal_proved=false`, mọi phần tử vào `unresolved`.
6. **Witness được kiểm với mọi nhóm khác tắt:** lịch witness của phần tử g thỏa đúng `subset \ {g}`; mọi
   nhóm ngoài subset cũng tắt. Validator nhận `relaxed_groups` = mọi nhóm trừ `subset \ {g}`.

## Tests mới

| File | Số test | Nội dung |
|---|---:|---|
| `tests/unit/test_diagnostics_contracts.py` | 23 | Roundtrip, field lạ, không có `assignments`, nhất quán theo status, `ExplainOptions` bắt buộc |
| `tests/unit/test_diagnostics_groups.py` | 3 | Input 1.0, policy 0.3 có phòng/availability/rule hard, thứ tự độc lập input |
| `tests/unit/test_diagnostics_prechecks.py` | 17 | Từng `PC_*` có ca dương và ca biên vừa đủ; liệt kê hết; verifier khớp trên mọi fixture; report giả/stale; import guard; precheck `solve()` giữ `LOCK_CONFLICT` |
| `tests/unit/test_validator_relaxed_groups.py` | 5 | Mặc định = kiểm đầy đủ; DEMAND cho thiếu không cho thừa; occupancy/lock/availability/rule theo đúng nhóm; nền cố định không nới; kind lạ bị từ chối |
| `tests/integration/test_diagnostics_solver.py` | 19 | Tam giác lớp–GV–phòng (MODEL, FULL); S05 + khóa (MODEL khác FULL); precheck không gọi solver; có lịch → `NOT_INFEASIBLE`; lỗi input; `RESOURCE_LIMIT`; UNKNOWN giữa deletion/đầu tiên; budget rất nhỏ; lặp lại xác định; status model chẩn đoán = `solve()` trên mọi fixture |
| `tests/integration/test_diagnostics_cli.py` | 10 | `explain` → `check-explanation` (core và precheck); thiếu tham số; option sai; report giả/stale/sai contract; chạy khi chặn import OR-Tools; lệnh cũ giữ hành vi |
| `tests/properties/test_diagnostics_oracle.py` | 121 | 60 seed × MODEL/FULL + kiểm đa dạng |

Oracle: ba loại bài (mẫu tam giác, mẫu S05 + khóa, ngẫu nhiên), có nhiễu; tối đa 8 nhóm để vét cạn
256 tập con. Lần chạy cuối: 27 `CORE_SUBSET` (cả 27 `minimal_proved` và đều là MUS thật theo tham chiếu),
63 `NOT_INFEASIBLE`, 17 `PRECHECK_PROOF`, 13 bỏ qua vì quá 8 nhóm. Trên **mọi** tập con của mọi ca, model
có B11 cho cùng status với model không B11.

**TDD:** chỉ Task 1 có lần chạy RED quan sát được (thiếu module). Task 2–8 viết test cùng lúc hoặc ngay sau
code, không chạy riêng bước RED; vài test được sửa vì kỳ vọng của chính test sai (lớp cũng bị giới hạn khi
chỉ có tiết của GV đó; fixture thiếu `manage_rooms`; tổng block phải bằng số tiết), không vì code sai.

## Lệnh đã chạy và kết quả

| Lệnh | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS, lock không đổi |
| `uv run --extra solver pytest tests benchmarks/tests` | **1749 passed, 21 skipped** (195 s). Trước: 1564 passed, 8 skipped. 13 skip mới là ca oracle quá 8 nhóm; 8 skip cũ vẫn là Windows/opt-in |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` | PASS (106 file) |
| `uv run mypy` | PASS (44 source file) |
| `git diff --check` | PASS |
| `git diff -- src/tkb_core/solver src/tkb_core/preprocessing src/tkb_core/constraints src/tkb_core/repair benchmarks` | Rỗng |
| So validator mới (mặc định) với bản `HEAD` (script ngoài repo) | Cùng `ValidationReport` trên **2 843** lịch: 43 lịch `solve()` + lịch ngẫu nhiên (thiếu/trùng/sai slot/phòng) trên 70 input (fixture + oracle) |

Vì solver/preprocessing/constraints/repair không đổi và validator mặc định cho cùng kết quả, output của
`solve()`, `repair()` và `validate-schedule` trên fixture cũ không đổi. Không có phép so hash file output
riêng ngoài lập luận này và test hiện có.

## Hạn chế

- **Chưa đo ở quy mô thật.** Chỉ có bài tí hon và spike B9 (147 nhóm, khoảng 3 s). Thời gian ở 20/40 lớp,
  nhất là `FULL`, chưa biết (B10: thuộc 3C hoặc lát sau).
- **Phía vô nghiệm là bằng chứng của solver.** Không có proof độc lập cho "tập này vô nghiệm"; chỉ
  minimality và phản chứng đếm được kiểm độc lập. `check-explanation` không kiểm lại minimality vì report
  không chứa witness.
- **B11 dựa trên lập luận đối xứng và oracle trên bài tí hon** (≤ 8 nhóm), không phải chứng minh hình thức.
- **Logic bucket S02/S03/S05/S06 được sao lại** trong `diagnostics/model.py` thay vì dùng chung với
  `constraints/hard.py` (để không đổi đường `solve()`); test đối chiếu status trên fixture, nhưng hai bản có
  thể lệch nếu sau này chỉ sửa một bên.
- Chưa kiểm installed wheel; chưa review người thứ hai (S3); synthetic; Linux.

## Sửa sau tự rà soát

[Tự rà soát](phase-3b-review.md) tìm 5 finding (F1–F5); cả 5 đã sửa cùng ngày theo TDD. Thay đổi hành vi:
precheck luôn chạy trên domain sạch trước khi dựng domain `FULL`; `check-explanation` chấp nhận
`RESOURCE_LIMIT` và từ chối nhóm không tồn tại (`UNKNOWN_GROUP`); `explain` trả exit 5 cho
`MODEL_INVALID`; hết budget trước lời gọi đầu → `UNKNOWN`. Thêm property test đối chiếu với `solve()`
(200 seed). Sau sửa: **1967 passed, 22 skipped**.

## Kiểm installed wheel từ `c1a49e1`

Bổ sung sau commit `c1a49e1` (gồm bản sửa F1–F5). Chỉ Linux, mỗi lệnh chạy một lần (n = 1), input
synthetic. Đây không phải benchmark và không đo hiệu năng.

- Wheel `vnedu_tkb_core-0.2.0-py3-none-any.whl`, SHA256
  `bea79eee30b81a18ffec0b5f80ce209429b2cc67273dca774aa7afc3ebbb5c79`, build bằng `uv build --wheel` từ
  `git archive` của `c1a49e1` (tree sạch, không lẫn file chưa track). **Wheel không được commit**; nó chỉ
  nằm trong scratchpad của phiên làm việc.
- Python 3.12.3; OR-Tools 9.15.6755; Pydantic 2.14.1; `uv.lock` SHA256
  `fe404cb126bce893368517318d4982b5f7842990429467d2a793af066c2e4c3b` (không đổi). Dependencies từ
  `uv export --frozen` cài `--require-hashes` vào hai venv sạch: `venv-solver` (có OR-Tools) và
  `venv-core` (không OR-Tools). Wheel cài `--no-deps`.
- 44/44 file `tkb_core/*.py` đã cài khớp byte với `src/` tại `c1a49e1` ở cả hai venv, gồm 6 file
  `diagnostics/`, `contracts/diagnostics.py` và `validation/precheck_verifier.py`.
- Mọi lệnh chạy bằng `python -I -m tkb_core.cli` từ một thư mục ngoài repo.

| Lệnh (venv) | Exit | Kết quả |
|---|---:|---|
| solver: `explain infeasible_teacher.json --granularity MODEL` | 0 | `PRECHECK_PROOF`, 2 × `PC_RESOURCE_CAPACITY`, 0 lời gọi solver |
| solver: `explain triangle.json` MODEL / FULL | 0 / 0 | `CORE_SUBSET`, `minimal_proved`, 6 nhóm (DEMAND r1–r3, CLASS c1, TEACHER t1, ROOM lab); 8 lời gọi |
| solver: `explain spread.json` MODEL | 0 | `CORE_SUBSET`, `minimal_proved`: DEMAND r, DEMAND r3, HARD_RULE spread, TEACHER t1; 7 lời gọi |
| solver: `explain spread.json` FULL | 0 | Như MODEL, thêm `LOCK r3::1`; 8 lời gọi |
| solver: `explain feasible_small.json` FULL (input 1.0) | 0 | `NOT_INFEASIBLE`, 1 lời gọi |
| solver / core: `check-explanation` cho 5 report trên | 0 / 0 | `OK` (precheck: 2 phản chứng tính lại khớp, `ARITHMETIC`; core: `SOLVER`) |
| core: `check-explanation spread.json r-forged.json` (đổi `DEMAND r` thành `ghost` ở subset và witness) | 2 | `EXPLANATION_MISMATCH / UNKNOWN_GROUP` (F2) |
| core: `check-explanation triangle.json r-spread-full.json` | 2 | `STALE_RESULT` |
| solver: `solve triangle.json` | 3 | 1.4 `INFEASIBLE`; đường `solve` vẫn chạy |
| core: `solve triangle.json` | 2 | 1.4 `UNSUPPORTED_FEATURE / SOLVER_NOT_INSTALLED` |
| core: `explain triangle.json --granularity MODEL` | **1** | **Traceback `ModuleNotFoundError: No module named 'ortools'`, không có JSON** — finding mới F6 |

Input: `infeasible_teacher.json`, `feasible_small.json` lấy từ `tests/fixtures`; `triangle.json` và
`spread.json` giống fixture `triangle_case`/`spread_case` trong `tests/conftest.py`.

**F6 (mở, chưa sửa):** khi không cài OR-Tools, `explain` crash thay vì trả lỗi có cấu trúc như `solve`/
`repair` (`UNSUPPORTED_FEATURE / SOLVER_NOT_INSTALLED`, exit 2). Ngay cả input chỉ cần precheck (không cần
solver) cũng crash, vì `diagnostics.pipeline` import `ortools` lúc nạp module. Ghi ở
[rà soát](phase-3b-review.md#f6--explain-crash-khi-không-cài-or-tools). Chưa kiểm sdist, Windows hay timed
calendar qua wheel.

## Bước sau cần duyệt

Sửa F6; review người thứ hai (S3). 3C (benchmark repair) là lát tiếp theo theo P3-10. 3C (benchmark repair) là lát
tiếp theo theo P3-10.
