# Solver Phase 1 — cách chạy và giới hạn

Thiết kế được duyệt: [Phase 1](superpowers/specs/2026-10-26-phase-1-design.md).
Implementation độc lập, không sao chép FET/STKB; không có API, SQLite hoặc UI.

## Pipeline

`solve(problem, options)` revalidate/copy models mutable, tính input fingerprint,
normalize IDs/duration và timeline; capability/room metadata/khóa/prechecks; tạo
eligible placement domains; CP-SAT hard feasibility; validator độc lập; result.

- `normalize`/`prepare` có thể raise CoreError classified, không import OR-Tools.
- `solve` bắt boundary/preflight lỗi và trả ScheduleResult, không tự nới hard.
- `validate_schedule(problem, assignments)` trả ValidationReport, không import
  preprocessing/model/OR-Tools; không dùng cached domains hoặc solver variables.
- Validator tự dựng occurrence cardinality, footprint/availability và resource
  occupancy. Chấp nhận JSON/result shape không chứng minh lịch đã hợp lệ.

## Biến và occupancy

Một Boolean mỗi eligible start/room placement; ExactlyOne mỗi occurrence.
Block đôi dùng cùng Boolean trên cả hai slots. Index `(kind, resource_id, token)`
tạo AtMostOne; không tạo tất cả tổ hợp bị cấm rồi mới loại.

Ở symbolic mode token là slot. Ở timed mode token là đoạn giữa hai biên phút liên
tiếp của calendar; không dùng một biến cho mỗi phút và không chỉ so start slot.
Validator timed dùng interval sweep riêng; hai cách tính không chung footprint helper.

## Run config và trạng thái

SolveOptions: time_limit_seconds=60, num_workers=1 (1..64), seed=42 (0..2^31-1),
max_slots=10,000, max_occurrences=10,000, max_placements=100,000,
max_occupancy_terms=1,000,000. Tất cả cấu hình được; guards là giới hạn vận hành,
không phải giới hạn nghiệp vụ. Chạm guard → UNKNOWN + RESOURCE_LIMIT, không cắt miền.

| Trạng thái | Ý nghĩa |
|---|---|
| INPUT_INVALID | Contract/options/timeline/metadata/explicit lock conflict lỗi |
| UNSUPPORTED_FEATURE | Capability hoặc extra solver chưa cài |
| INFEASIBLE | Domain/load necessary proof hoặc CP-SAT chứng minh vô nghiệm |
| UNKNOWN | Chưa có bằng chứng nghiệm/vô nghiệm, gồm budget/guard |
| FEASIBLE | Có lịch đã được independent validator chấp nhận, chưa complete proof |
| OPTIMAL | CP-SAT hoàn tất bài hiện tại; không có objective nên chỉ là feasibility |
| MODEL_INVALID | Model/solver lỗi hoặc independent validator bác kết quả |

Empty/zero-demand synthetic input trả FEASIBLE sau checker, EMPTY_PROBLEM và
solver_executed=false. Đây không phải chứng nhận nhu cầu trường thực đầy đủ.
Nếu chưa gọi solver, không chế solver_wall_time/version. Nếu không có nghiệm đã
validate, assignments rỗng và valid_schedule=false. Không có partial publish.

Output mới schema 1.1; input/hash vẫn 1.0. RunMetadata 1.1 thêm execution/seed/workers/
budget và solver_wall_time; wall_time đo toàn lời gọi core, chưa gồm CLI ghi file.
time_limit chỉ giới hạn CP-SAT, không hứa giới hạn toàn preprocessing/validation.
objective/best_bound null vì Phase 1 không có mục tiêu chất lượng.

## CLI

```sh
uv sync --locked --extra solver
uv run --extra solver tkb-core solve tests/fixtures/feasible_double.json --time-limit 5 --workers 1 --seed 42 --output /tmp/tkb-result.json
uv run tkb-core validate-schedule tests/fixtures/feasible_double.json /tmp/tkb-result.json
```

validate-input vẫn contract-only. validate-schedule kiểm fingerprint rồi tự tính
toàn bộ validity, không tin validation report trong file. File stale hoặc giả
valid bị từ chối. Solve stdout/result file cùng một JSON; output ghi atomic và
không được trùng input qua path/symlink/hardlink. Errors không echo raw data.

Exit 0 valid; 2 input/unsupported/stale/invalid schedule/write errors;
3 infeasible; 4 unknown/guard; 5 model error. Help vẫn là text argparse.
CLI input/usage errors dùng envelope 1.0 như Phase 0; solver results dùng 1.1.

## Giới hạn

Chỉ một class/GV mỗi requirement và block 1/2 đã khai báo split. Chưa có tự chọn
split, soft objective, repair, travel, callback progress public hoặc worker IPC.
Không benchmark tốc độ so STKB/FET, không chứng nhận Windows hoặc dữ liệu trường thật.
Giờ nghỉ phải khai báo đúng; timed block bảo thủ không vượt bất kỳ gap dương nào.
