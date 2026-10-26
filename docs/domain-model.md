# Domain contracts v1 — Phase 0

Input vẫn version 1.0. Những mô tả “chưa có solver/validator” bên dưới là mốc Phase 0;
behavior Phase 1 xem [solver-design](solver-design.md). Output solver mới 1.1 có
SolverRunMetadata riêng (solver_executed, seed, num_workers, time_limit_seconds,
solver_wall_time). Output 1.0 vẫn dùng RunMetadata cũ đúng bốn field; không thêm
metadata mới dưới nhãn 1.0. Parser đọc cả 1.0/1.1, solver phát 1.1.

Package `tkb_core` import được mà không cần OR-Tools. Pydantic JSON models nằm trong
`domain/models.py`, input/output versioned nằm trong `contracts/`.

```python
from pathlib import Path
from tkb_core.contracts.input import ScheduleInput
from tkb_core.contracts.output import ScheduleResult

problem = ScheduleInput.model_validate_json(
    Path("tests/fixtures/feasible_small.json").read_text(encoding="utf-8")
)
fingerprint = problem.fingerprint()
result = ScheduleResult(
    schema_version="1.0", status="NOT_RUN", input_fingerprint=fingerprint
)
assert not result.valid_schedule  # Parsing is not solving.
```

Input JSON tin cậy có thể dùng Pydantic trực tiếp như ví dụ. Đối với file chưa tin
cậy, CLI còn từ chối key JSON trùng và hằng NaN/Infinity; không dùng parser mặc định
để âm thầm lấy key cuối. API model_validate_json của Pydantic không có bảo đảm
duplicate-key tương đương CLI.

## Đầu vào

| Model / field | Bắt buộc | Ý nghĩa |
|---|---|---|
| `ScheduleInput.schema_version` | Có | Literal `1.0`, không có default |
| `school` / `SchoolContext` | Có | school_id, academic_year, term; timezone có default |
| `time_slots` / `TimeSlot` | Có | id/day/session/period; can_teach=true; minutes tùy chọn |
| `classes` / `ClassGroup` | Có | id; size, source_reference, available_slot_ids tùy chọn |
| `teachers` / `Teacher` | Có | id; source_reference và availability tùy chọn |
| `subjects` / `Subject` | Có | id và source_reference tùy chọn |
| `rooms` / `Room` | Không, mặc định [] | id, room_type/capacity/availability tùy chọn |
| `teaching_requirements` / `TeachingRequirement` | Có | id, class_ids, subject_id, teacher_ids, periods_per_cycle |
| `block_durations` của requirement | Không | Split dương bảo toàn tổng tiết; null nghĩa toàn tiết đơn |
| `room_required`, `required_room_type` | Không | false/null; loại phòng chỉ được khai báo nếu yêu cầu phòng |
| `manage_rooms` | Không, mặc định false | Boolean thật, không chấp nhận chuỗi `"false"` |
| `locked_assignments` / `LockedAssignment` | Không, mặc định [] | occurrence_id, slot_id và/hoặc room_id |
| `constraint_config` | Không, hard/soft [] | Rule code/scope/parameters/enabled; soft cần weight nguyên dương |

IDs là string không rỗng/không toàn khoảng trắng, không tự strip/chuyển số. Danh mục
không được trùng ID trong cùng loại. Availability, participants và scope không được
trùng ID; mọi ID tham chiếu phải tồn tại. Numeric counts/indices dùng integer thật,
không tự nhận bool, float hoặc chuỗi số. JSON arrays chuyển thành tuples trong model.

Mỗi lock tham chiếu đúng occurrence của requirement hiện tại, ordinal nằm trong
occurrence_count, slot/room đã khai báo. Mỗi occurrence chỉ có một lock record; muốn
khóa cả giờ và phòng dùng cùng record. Clash/eligibility/feasibility thuộc Phase 1.

`LessonOccurrence` là shape record cho normalization Phase 1, chưa có hàm sinh lịch.
`PreviousSchedule` và model repair chưa triển khai; input v1 không nhận field này.
Rule parameters là JSON chưa được compile/evaluate; code rule được lưu, không có
registry tự nhận là đã hỗ trợ. Model từ chối field lạ ở mọi lớp khai báo.

## Fingerprint

`ScheduleInput.fingerprint()` trả SHA-256 của model_dump JSON đã canonical hóa:
sort object keys, danh mục theo ID, locks theo occurrence, participant/availability
và rule-scope IDs theo giá trị; materialize defaults, không đổi caller model. Thứ tự block giữ
nguyên vì ảnh hưởng identity; thứ tự rule và parameter arrays cũng được giữ nguyên.
Nguồn, context và configuration đều tham gia hash. Không dùng hash để chứng minh
dữ liệu đúng hoặc bí mật. Models còn mutable; hãy validate lại đầu vào ở boundary
trước khi dùng làm snapshot. Chưa có normalization phục vụ solver.

## Đầu ra

`ScheduleResult` cần schema_version và status. `SolveStatus` phân biệt NOT_RUN,
OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, MODEL_INVALID, INPUT_INVALID,
UNSUPPORTED_FEATURE. NOT_RUN là trạng thái core, không phải status OR-Tools.

- `input_fingerprint`: SHA-256 lowercase hoặc null nếu chưa có input hợp lệ.
- `valid_schedule`: mặc định false; true yêu cầu status FEASIBLE/OPTIMAL, fingerprint
  và ValidationReport.valid=true, không có violations.
- `assignments`: occurrence_id/slot_id/class_ids/teacher_ids/room_id; chỉ được có
  assignments khi valid_schedule=true. Phase 0 không tạo kết quả lịch.
- `diagnostics`: code/message/resource_ids/slot_ids/occurrence_ids.
- `validation`: shape report valid/violations; **chưa phải validator chạy thật**.
- `metadata`: solver_version/wall_time/objective_value/best_bound, nullable vì chưa
  có solver thực thi. Result serialization không tự chạy hoặc xác minh solver.

`INPUT_VALID` là status riêng của CLI kiểm tra contract, không nằm trong SolveStatus.
Output JSON Schema có thể lấy bằng `ScheduleInput.model_json_schema()` và
`ScheduleResult.model_json_schema()`; không lưu bản JSON Schema trùng lặp phải sửa tay.

## CLI và exit codes

`tkb-core validate-input PATH` và `python -m tkb_core.cli validate-input PATH`:
exit 0 = INPUT_VALID, exit 2 = INPUT_INVALID hoặc UNSUPPORTED_FEATURE; stdout một
JSON object, không in raw input hoặc traceback. `--help` giữ help text chuẩn argparse.
Lệnh solve/validate-schedule/benchmark chưa có. Fixture tên feasible_small là bài
nhỏ được chuẩn bị cho Phase 1, chưa phải kết luận của solver hiện tại.

## Bổ sung Phase 2A

Input 1.1 yêu cầu constraint_config.policy_version=0.1 và rule IDs duy nhất; priority nguyên1–3, weight nguyên dương, params strict. Input 1.0/hash/serialization không đổi.
Bốn codes được hỗ trợ: TEACHER_AVOID_SLOTS, TEACHER_MAX_PERIODS_PER_SESSION,
TEACHER_MAX_PERIODS_PER_DAY, TEACHER_PREFERRED_PERIOD_WINDOW. Chỉ teacher scope;
empty teacher set là global; effective scopes cùng family không được overlap.
Unknown enabled trả UNSUPPORTED_FEATURE, unknown disabled giữ raw JSON; known params sai luôn bị từ chối.
Fingerprint 1.1 sort known sets/rules, giữ unknown array order và split order.
Output 1.2 có quality/ScoreReport và từng stage proof/measurements; không scalar hóa vector.
Xem [đặc tả](superpowers/specs/2026-10-26-phase-2-quality-design.md) và [nghiệm thu](phase-2a-report.md).
