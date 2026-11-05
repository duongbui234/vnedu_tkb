# Phase 3A — báo cáo triển khai repair

Ngày 2026-11-05. Base `84d1b28` trên `main`. Người dùng duyệt P3-1 đến P3-12 và ủy quyền Task 1–8.
**Trạng thái: TECHNICAL SYNTHETIC — người dùng duyệt commit và push ngày 2026-11-05.**

Phạm vi: [đặc tả Phase 3](superpowers/specs/2026-11-05-phase-3-repair-diagnostics-design.md),
[kế hoạch 3A](superpowers/plans/2026-11-05-phase-3a-repair.md). Không sửa `benchmarks/`, tooling
v1/v2, gate, budget hay pins. Không sửa `solver/`, `preprocessing/`, `constraints/`, validator hay score
evaluator: hành vi `solve()` không đổi. Không chạy benchmark hay campaign. Campaign Phase 2 v2 vẫn ghim
`86f624d` (P3-1).

## Đã triển khai

| Task | File | Nội dung |
|---|---|---|
| 1 | `contracts/repair.py` | `PreviousSchedule`, `RepairRequest`, `ChangeScope`, `RepairChange`, `ChangeStage`, `RepairReport`, `RepairResult` (1.0). Fingerprint canonical; validator kiểm số học của report |
| 2 | `validation/repair_evaluator.py` | `evaluate_repair` và `check_report`: tính lại matched, new, dropped, changed, slot/room, frozen, vi phạm vùng và giới hạn. Không import solver, compiler hay preprocessing |
| 3 | `repair/matching.py` | Ghép theo `occurrence_id` với domain đã chuẩn bị; phân loại `forced` (`LOCK`/`DOMAIN`), new, dropped, frozen; frozen có target invalid → `REPAIR_FROZEN_TARGET_INVALID` |
| 4 | `repair/compiler.py` | `Σ(1 − x[l,p₀]) + forced`; cố định frozen; `max_changes`; hint lịch trước |
| 5 | `repair/pipeline.py` | `repair()`: giai đoạn `BEFORE`/`AFTER`, budget chung, fallback có kiểm, kiểm độc lập ba lớp, envelope |
| 6 | `tests/properties/test_repair_oracle.py` | Oracle vét cạn 60 seed × 2 thứ tự |
| 7 | `cli.py` | Lệnh `repair` và `evaluate-repair`; đọc JSON tách thành `_load_json` (mã lỗi cũ giữ nguyên) |
| 8 | Tài liệu | README, domain model, solver design, constraint catalog, báo cáo này, trạng thái đặc tả/kế hoạch |

## Tests mới

| File | Số test | Nội dung |
|---|---:|---|
| `tests/unit/test_repair_contracts.py` | 25 | Roundtrip, field bắt buộc, giá trị sai, số học report, envelope bọc output 1.2–1.5, `from_result` |
| `tests/unit/test_repair_evaluator.py` | 8 | Diff tính tay, chỉ đổi phòng, tiết đôi, scope/giới hạn, lịch thiếu, `check_report`, import guard |
| `tests/unit/test_repair_matching.py` | 6 | Target, new, dropped; forced do availability, calendar, block không vừa, phòng; khóa thắng; vùng |
| `tests/unit/test_repair_compiler.py` | 5 | Raw count với placement cưỡng bức = evaluator; forced là hằng; `max_changes`; frozen; hint |
| `tests/integration/test_repair_solver.py` | 13 | 0 thay đổi; 1 thay đổi bắt buộc; INFEASIBLE do giới hạn; INPUT_INVALID do vùng; khóa thắng; đánh đổi BEFORE/AFTER tính tay; hint; new/dropped; compiler sai → MODEL_INVALID; input 1.0; budget rất nhỏ; version theo policy |
| `tests/properties/test_repair_oracle.py` | 121 | 60 seed × 2 thứ tự (có S01–S04, S08, S11, khóa, GV bận, giới hạn, vùng, hint) + kiểm độ đa dạng (45 OPTIMAL, 7 INFEASIBLE, 8 INPUT_INVALID) |
| `tests/integration/test_repair_cli.py` | 7 | solve → repair → validate-schedule → evaluate-repair; file `PreviousSchedule`; report giả/stale; request lỗi; trùng output; input 1.0; evaluate-repair không cần OR-Tools |

## Lệnh đã chạy và kết quả

| Lệnh | Kết quả |
|---|---|
| `uv run --extra solver pytest tests benchmarks/tests` trước khi sửa | 1352 passed, 8 skipped (baseline đã lưu ở `f873126`, cùng source) |
| `uv run --extra solver pytest tests benchmarks/tests` | **1537 passed, 8 skipped** (+185) |
| `uv run ruff check .`, `uv run ruff format --check src tests benchmarks`, `uv run mypy` | PASS (mypy 36 source files) |
| `git diff --check` | PASS |
| `git diff -- src/tkb_core/solver src/tkb_core/preprocessing src/tkb_core/constraints <validator> <score evaluator> benchmarks` | Rỗng: đường `solve()` và tooling không đổi |

8 skip vẫn là test Windows native/opt-in như trước.

## Kiểm installed wheel từ `0d318d1`

Bổ sung sau commit `0d318d1` (gồm bản sửa F1–F3 của [rà soát](phase-3a-review.md)). Chỉ Linux, mỗi lệnh
chạy một lần (n = 1), input synthetic. Đây không phải benchmark và không đo hiệu năng.

- Wheel `vnedu_tkb_core-0.2.0-py3-none-any.whl`, SHA256
  `786e647e3df1e3cb9547b27b5a2d8e84b41665340fecbaab28a1a21316802cf9`, build bằng `uv build --wheel` từ
  tree sạch tại `0d318d1`. **Wheel không được commit**; nó chỉ nằm trong scratchpad của phiên cloud.
- Python 3.12.3; OR-Tools 9.15.6755; Pydantic 2.14.1. Dependencies từ `uv export --frozen` (lock không
  đổi) vào hai venv sạch, có hash: `venv-solver` (có OR-Tools) và `venv-core` (không OR-Tools). Wheel cài
  `--no-deps`.
- 36/36 file `tkb_core/*.py` đã cài khớp byte với `src/` tại HEAD ở cả hai venv, gồm 6 file repair mới.
- Mọi lệnh chạy bằng `python -I -m tkb_core.cli` từ một thư mục ngoài repo.

| Lệnh (venv) | Exit | Kết quả |
|---|---:|---|
| solver: `solve old.json --time-limit 10 --workers 1 --seed 42 --output solved.json` | 0 | 1.5 OPTIMAL, Score `[0,0,0]` |
| solver: `repair new.json solved.json --request request.json --output repaired.json` | 0 | 1.5 OPTIMAL; 1 thay đổi (forced 1, `r::3`), `min_changes_proved=true`; Score `[1,0,0]` |
| solver: `validate-schedule new.json result-only.json` | 0 | 1.5 SCHEDULE_VALID |
| solver / core: `evaluate-repair new.json solved.json repaired.json` | 0 / 0 | OK, `changed=1` |
| core: `evaluate-repair … --request request.json` | 0 | OK |
| core: `evaluate-repair … --request request-other.json` | 2 | INPUT_INVALID / RESULT_REQUEST_MISMATCH (F1) |
| core: `evaluate-repair old.json solved.json repaired.json` | 2 | INPUT_INVALID / STALE_RESULT |
| solver: `repair … --request request-after.json` | 0 | 1.5 OPTIMAL; 2 thay đổi, `min_changes_proved=true`; Score `[0,0,0]` |
| core: `evaluate-repair … repaired-after.json --request request-after.json` | 0 | OK, `changed=2` |
| solver: `repair … --request request-zero.json` | 3 | 1.5 INFEASIBLE / REPAIR_MAX_CHANGES_BELOW_FORCED (`r::3`), `solver_executed=false` (F2) |
| solver: `repair legacy.json …` (input 1.0) | 2 | 1.1 UNSUPPORTED_FEATURE / REPAIR_INPUT_VERSION |
| core: `repair new.json solved.json …` | 2 | 1.5 UNSUPPORTED_FEATURE / SOLVER_NOT_INSTALLED |
| solver: `solve old.json …` (lần hai) | 0 | 1.5 OPTIMAL, Score `[0,0,0]`; đường `solve` vẫn chạy |

Các input dùng trong bảng:

- `old.json`: 1 lớp, 1 GV, 2 ngày × 2 buổi × 4 tiết, requirement `[2,1,1]`, S08 `TEACHER_TOTAL_GAPS` P1,
  policy 0.4.
- `new.json`: như `old.json`, nhưng GV bận ô `1-AM-2` mà lịch cũ đặt `r::3`.
- `request.json`: `BEFORE_QUALITY`, không giới hạn, không vùng, có hint.
- `request-after.json`, `request-other.json` (`max_changes 5`) và `request-zero.json` (`max_changes 0`)
  khác `request.json` đúng ở field ghi trong tên.
- `legacy.json`: `tests/fixtures/feasible_small.json` (input 1.0).

Đánh đổi `BEFORE` so với `AFTER` thấy rõ trên cùng dữ liệu: giữ lịch cũ nhất (1 thay đổi, P1 = 1) so với
không còn tiết trống (2 thay đổi, P1 = 0). Chưa kiểm sdist, Windows, phòng hay timed calendar qua wheel.

## TDD và mutation check

- Mỗi task chạy test RED trước, vì module chưa tồn tại (Task 1–5, 7). Task 6 là oracle chạy trên
  pipeline đã có. Lần chạy đầu, oracle bắt được bộ ca thiếu trường hợp INFEASIBLE; đã chỉnh bộ sinh
  (lỗi của test, không phải product code).
- Một test Task 5 đỏ lúc đầu vì so tập `ScheduleAssignment` (không hash được); đó là lỗi của test.
- Mutation check, mỗi lần tạm sửa một chỗ rồi khôi phục; cả năm đều làm test đỏ:
  - bỏ ràng buộc `max_changes`;
  - bỏ cố định frozen;
  - bỏ tầng thay đổi sau P1–P3 (`AFTER`);
  - bỏ đẳng thức số thay đổi trước P1–P3 (`BEFORE`);
  - gộp lý do forced `LOCK` thành `DOMAIN`.

## Sai khác so với đặc tả/kế hoạch

- **Lịch trước tham chiếu slot hoặc phòng không còn tồn tại** được coi là `forced/DOMAIN` (lịch đổi
  calendar là chuyện bình thường), không phải `PREVIOUS_SCHEDULE_INVALID`. Mã lỗi đó chỉ dùng khi file
  vi phạm contract (trùng occurrence, field lạ…).
- **`capabilities.py` không đổi.** Module này không có danh sách tính năng; kiểm version input nằm trong
  pipeline (`REPAIR_INPUT_VERSION`).
- **`RepairResult.previous_fingerprint` và `request`** cho phép `null` khi chính file đó không hợp lệ;
  bắt buộc có khi có lịch.
- **`AFTER_QUALITY`:** `ScheduleResult.status/quality` mô tả P1–P3 như `solve()`, nên status có thể là
  `OPTIMAL` trong khi `min_changes_proved=false` (hết budget ở tầng thay đổi). Bằng chứng về thay đổi chỉ
  nằm trong `RepairReport`.
- **`metadata.feasibility_run`** là lần solve native đầu tiên: tầng thay đổi khi `BEFORE` hoặc không có
  preference; feasibility của `run_quality` khi `AFTER`.
- **Ordering interchangeable tắt cho repair** (đổi nhãn bị tính là thay đổi), nên model repair có thể
  chậm hơn `solve()` trên cùng input. Chưa đo.
- **Pipeline dùng `_hint` (private) của `solver/objectives.py`** để không sao chép logic hint.
- **Oracle** chấm điểm bằng validator và score evaluator độc lập (không tự viết lại công thức S01–S11),
  tự đếm thay đổi, và chỉ dùng tập S01–S04, S08, S11. Không có phòng hay timed calendar.

## Giới hạn

- Synthetic only. Chưa đo hiệu năng repair (thuộc 3C, sau campaign Phase 2 v2). Không Windows.
- `evaluate-repair` không tính lại lý do `forced` hay `min_changes_proved` (đó là claim của solver; trường
  thứ hai được in ra với tên `declared_min_changes_proved`).
- Ghép chỉ theo `occurrence_id`: upstream đổi ID thì sẽ thấy `new`/`dropped`, không có ghép theo nội dung.
- Chưa có 3B (chẩn đoán vô nghiệm) và 3C (benchmark repair). Installed wheel mới kiểm trên Linux, n = 1,
  synthetic (mục trên).
- Tự kiểm trong cùng phiên; chưa có review người thứ hai (P3-12, S3).
