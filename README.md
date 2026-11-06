# vnEdu TKB — Scheduling Core

Phase 2A: Python core độc lập, hard-feasibility CP-SAT cho tiết đơn/đôi và tối ưu
S01–S04 theo ưu tiên P1–P3, có independent hard validator và score evaluator.
Input 1.0 giữ hành vi/hash Phase 1 và phát output 1.1; input 1.1/policy 0.1 phát output 1.2.
Phase 2B (synthetic): input 1.1/policy 0.2 thêm hard variants S01–S04 explicit và phát output 1.3.
Phase 2C-1 (synthetic): policy 0.3 thêm phân phối môn S05/S06 (soft và hard), phát output 1.4
với ScoreReport 1.1. Phase 2C-2 (synthetic): policy 0.4 thêm S07–S11 (ô hạn chế, tiết trống,
ngày/buổi rảnh, buổi một tiết; chỉ soft) và `occupied_work`, phát output 1.5 với ScoreReport 1.2.
Output reader đọc 1.0–1.5. Phase 3A (synthetic): lệnh `repair` xếp lại khi dữ liệu đổi, giữ lịch
trước nhiều nhất có thể, và `evaluate-repair` kiểm lại độc lập; kết quả là envelope `RepairResult`
1.0 bọc output hiện có, không thêm version output mới. Phase 3B (synthetic): lệnh `explain` chẩn đoán
input vô nghiệm (phản chứng đếm hoặc một tập xung đột), `check-explanation` kiểm lại độc lập. Không có
Electron, React, SQLite, HTTP hoặc vnEdu adapter.

## Chạy local

Python 3.12+ và [uv](https://docs.astral.sh/uv/) được yêu cầu.

```sh
uv sync --locked --extra solver
uv run python -m tkb_core.cli validate-input tests/fixtures/feasible_small.json
uv run tkb-core validate-input tests/fixtures/feasible_small.json
uv run --extra solver tkb-core solve tests/fixtures/feasible_double.json --time-limit 5 --output /tmp/tkb-result.json
uv run tkb-core validate-schedule tests/fixtures/feasible_double.json /tmp/tkb-result.json
uv run --extra solver pytest
uv run ruff check .
uv run ruff format --check src tests
uv run mypy
uv build
```

`uv.lock` pin runtime/dev và extra `solver` (OR-Tools 9.15.6755). Contract và validator
không import OR-Tools; `solve` cần extra solver. Defaults 60 giây, 1 worker, seed 42
là cấu hình thử nghiệm, không phải cam kết hiệu năng.

Source distribution dùng allowlist; không chứa nghiên cứu, file STKB hay collection
Postman. Integration test kiểm tra nội dung cả sdist và wheel.
`[tool.uv] cache-keys` gồm `pyproject.toml`, `README.md` và `src/**/*.py`, nên cài
non-editable lại từ cùng thư mục sẽ build lại khi source đổi, không dùng wheel cũ.

Contract là schema nội bộ synthetic, **không phải schema API vnEdu**. `validate-input` chỉ
xác nhận cấu trúc/tham chiếu, không chứng minh lịch có thể xếp được. Mọi fixture dùng ID giả.

## Tài liệu

- [Đặc tả Core First](docs/VNEDU_TKB_CORE_FIRST_CODEX.md).
- [Thiết kế tổng thể](docs/superpowers/specs/2026-10-25-scheduling-core-design.md).
- [Giả định và giới hạn](docs/assumptions.md).
- [Domain contract v1](docs/domain-model.md).
- [Thiết kế Phase 1 đã duyệt](docs/superpowers/specs/2026-10-26-phase-1-design.md).
- [Đặc tả Phase 2A — S01–S04](docs/superpowers/specs/2026-10-26-phase-2-quality-design.md).
- [Implementation plan Phase 2A](docs/superpowers/plans/2026-10-26-phase-2a.md).
- [Model và trạng thái solver](docs/solver-design.md).
- [Danh mục hard constraints](docs/constraint-catalog.md).
- [Kết quả Phase 2A](docs/phase-2a-report.md).
- [Kết quả Phase 1](docs/phase-1-report.md), [lịch sử Phase 0](docs/phase-0-report.md).

Một block đôi là một assignment chiếm hai period liền nhau cùng buổi. Không qua slot
nghỉ hoặc gap dương trong timed calendar. Tuyến input 1.0 vẫn không có objective chất lượng:
OPTIMAL của bài feasibility không có nghĩa lịch đẹp nhất. Nghiệp vụ chưa hỗ trợ
(nhiều GV/lớp, block >2, mọi custom hard/soft ngoài S01–S04, hard trên policy 0.1) bị từ chối rõ ràng.
Input 1.0 tiếp tục từ chối mọi enabled custom rule.

Nghiên cứu trước nằm trong `docs/research/`, `research/`, `reverse-engineering/` và được
giữ riêng với package. Không dùng dữ liệu thật từ đó làm fixture, không sao chép mã engine.

## Quality Phase 2A

```sh
uv run --extra solver tkb-core solve tests/fixtures/quality/priority_tradeoff.json --time-limit 5 --workers 1 --seed 42 --output /tmp/tkb-quality.json
uv run tkb-core validate-schedule tests/fixtures/quality/priority_tradeoff.json /tmp/tkb-quality.json
uv run tkb-core evaluate-score tests/fixtures/quality/priority_tradeoff.json /tmp/tkb-quality.json
```

S01 tránh ô mong muốn, S02 vượt tải/buổi, S03 vượt tải/ngày, S04 ngoài khung tiết.
Mỗi penalty tính theo tiết dạy trên toàn block, có weight và priority explicit.
Hard không được nới; chỉ tier có proof OPTIMAL mới được giữ cố định trước tối ưu tier sau.
Timeout giữ incumbent đã hard-validate và score đúng; quality report tách điểm khỏi proof.
Evaluator/CLI evaluate-score không cần OR-Tools. Chưa có spacing/gaps hoặc repair.

## Hard variants Phase 2B

Policy `0.2` cho phép đặt S01–S04 trong `constraint_config.hard` (không weight/priority):
S01 không dạy ô tránh (timed: cả alias giao phút), S02/S03 tải ≤ limit, S04 mọi tiết trong
khung. Policy 0.1 vẫn từ chối mọi enabled hard. Rule cùng family không được overlap bất kể
mode. INFEASIBLE không chỉ ra rule gây vô nghiệm. Core không có ngưỡng mặc định; xem
[đặc tả 2B](docs/superpowers/specs/2026-11-05-phase-2b-hard-variants-design.md) và
[báo cáo 2B](docs/phase-2b-report.md).

## Phân phối môn Phase 2C-1

Policy `0.3` thêm `SUBJECT_COMPONENT_DAY_SPREAD` (S05: nhóm `requirement_ids` explicit, mỗi cặp
component phạt `max(0, k − |day_i − day_j|)` ngày thiếu; hard: mọi cặp cách ≥ k ngày) và
`CLASS_SUBJECT_MAX_PERIODS_PER_DAY` (S06: số tiết lớp+môn+ngày vượt `limit`; hard: ≤ limit).
Khoảng cách theo giá trị `day`; không có k/limit mặc định. Policy 0.1/0.2 coi hai mã này là
unknown. Xem [đặc tả 2C-1](docs/superpowers/specs/2026-11-05-phase-2c-subject-distribution-design.md)
và [báo cáo 2C-1](docs/phase-2c-report.md).

## Tiết trống và thời gian rảnh Phase 2C-2

Policy `0.4` thêm S07 `TEACHER_RESTRICTED_SLOTS`, S08 `TEACHER_TOTAL_GAPS`, S09 `TEACHER_MAX_GAP_RUN`,
S10 `TEACHER_MIN_FREE_TIME` và S11 `TEACHER_SINGLE_PERIOD_SESSION` (chỉ soft, teacher scope), cùng
`constraint_config.occupied_work` cho lịch họp đã xác nhận (phải nằm ngoài availability). Ô
`can_teach=false` và ô họp không phải tiết trống. Xem
[đặc tả 2C-2](docs/superpowers/specs/2026-11-05-phase-2c-gaps-design.md) và
[báo cáo 2C-2](docs/phase-2c-gaps-report.md).

## Repair Phase 3A

`repair <input> <previous> --request <request>` nhận input mới (1.1), lịch trước (`PreviousSchedule`
1.0 hoặc một `ScheduleResult` hợp lệ) và `RepairRequest` 1.0 khai báo tường minh: thứ tự
(`BEFORE_QUALITY` hoặc `AFTER_QUALITY`), `max_changes` (hard hoặc `null`), `change_scope` (lớp, GV, môn,
ngày; ngoài scope giữ nguyên) và `use_previous_as_hint`. Đơn vị: một occurrence đổi slot hoặc phòng là
một thay đổi. `evaluate-repair <input> <previous> <repair-result>` tính lại hard, score và mọi bộ đếm
thay đổi, chạy được khi không cài OR-Tools.

```sh
uv run --extra solver tkb-core repair new.json previous.json --request request.json --output repaired.json
uv run tkb-core evaluate-repair new.json previous.json repaired.json
```

Xem [đặc tả Phase 3](docs/superpowers/specs/2026-11-05-phase-3-repair-diagnostics-design.md) và
[báo cáo 3A](docs/phase-3a-report.md).

## Chẩn đoán vô nghiệm Phase 3B

`explain <input> --time-limit S --seed N --granularity MODEL|FULL` trả `InfeasibilityReport` 1.0 (ba
tham số đều bắt buộc). Trước hết chạy mọi precheck đếm (`PC_*`); có phản chứng thì dừng với
`PRECHECK_PROOF`. Không có thì giải CP-SAT với một assumption cho mỗi nhóm ràng buộc và thu nhỏ core:
`CORE_SUBSET` là **một** tập xung đột, không phải nguyên nhân duy nhất. `minimal_proved` chỉ đúng khi
bỏ bất kỳ phần tử nào cũng có lịch, và mỗi lịch đó được validator độc lập kiểm. `MODEL` chẩn đoán demand,
occupancy và rule hard trong model; `FULL` thêm khóa, availability và S01/S04 hard. Report không chứa
lịch. `check-explanation <input> <report>` tính lại mọi phản chứng đếm, chạy được khi không cài OR-Tools;
tập xung đột vẫn là bằng chứng của solver.

```sh
uv run --extra solver tkb-core explain input.json --time-limit 30 --seed 42 --granularity FULL --output report.json
uv run tkb-core check-explanation input.json report.json
```

Xem [đặc tả 3B](docs/superpowers/specs/2026-11-06-phase-3b-infeasibility-diagnostics-design.md) và
[báo cáo 3B](docs/phase-3b-report.md).
