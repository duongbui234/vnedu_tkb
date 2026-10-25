# vnEdu TKB — Core-First Engineering Specification for Codex

> **Mục đích:** Đây là đặc tả triển khai dành cho Codex. Ưu tiên tuyệt đối xây dựng, kiểm thử và benchmark **Scheduling Core** trước khi làm Desktop UI, SQLite hoặc tích hợp API vnEdu.
>
> **Ngữ cảnh đã chốt:** Ứng dụng cuối là **Electron + React + TypeScript** trên Windows. **Python + Google OR-Tools CP-SAT chạy LOCAL** trên máy người dùng, không cần server solver. **SQLite LOCAL** chỉ phục vụ dữ liệu riêng của TKB. Dữ liệu giáo dục lấy từ **API vnEdu hiện có**, kết quả hoàn chỉnh đồng bộ lại qua API vnEdu. Core **không phụ thuộc** những thành phần tích hợp này.

## 0. Chỉ thị cho Codex — đọc trước khi thực hiện

Bạn là kỹ sư tối ưu tổ hợp, Python architect và software engineer phụ trách xây dựng Scheduling Core chất lượng production cho phần mềm xếp thời khóa biểu trường phổ thông Việt Nam.

**Nhiệm vụ ngay bây giờ:** Chỉ thực hiện **Phase 0 → Phase 3** được mô tả bên dưới, theo từng bước nhỏ và có kiểm thử. Không tự ý làm Electron, React, FastAPI, SQLite, kết nối vnEdu thật, UI hay đóng gói installer. Không tự ý sửa schema MySQL hoặc suy đoán cấu trúc API vnEdu.

Trước khi viết code:
1. Khảo sát repository hiện tại; tóm tắt các thành phần sẵn có và nguy cơ ghi đè.
2. Đọc `AGENTS.md`, `README`, cấu hình Python, test và convention nếu tồn tại.
3. Đề xuất kế hoạch thực thi ngắn, liệt kê file dự kiến tạo/sửa.
4. Nếu thiếu dữ liệu hoặc đặc tả nghiệp vụ bắt buộc, dùng giả định **được ghi rõ và có thể cấu hình**, không coi giả định là quy định của vnEdu.
5. Triển khai incrementally, chạy test sau mỗi bước, báo cáo rõ **đã chạy / chưa chạy / chưa kiểm chứng**.

**Không được:**
- Hardcode ID môn, lớp, trường, giáo viên hoặc quy tắc đặc thù từ dữ liệu chưa được cung cấp.
- Tuyên bố solver luôn tìm được nghiệm tối ưu, hoặc tuyên bố hiệu năng khi chưa benchmark.
- Đánh đồng `UNKNOWN`/`FEASIBLE`/`OPTIMAL`/`INFEASIBLE`.
- Tự thêm dependency nặng nếu không có lý do; không thêm microservices.
- Truy cập hoặc sửa dữ liệu vnEdu thật trong giai đoạn Core.
- Dùng thông tin cá nhân thật của học sinh/giáo viên trong fixture và log.

## 1. Mục tiêu sản phẩm và phạm vi

### 1.1 Mục tiêu

- Xếp thời khóa biểu cho trường phổ thông Việt Nam, có khả năng cấu hình nhiều cấp học và mô hình tổ chức khác nhau.
- Bảo đảm **hard constraints**; tối ưu **soft constraints** theo trọng số được cấu hình.
- Tạo lịch từ đầu, giữ tiết khóa, kiểm tra lịch thủ công, hỗ trợ xếp lại khi thay đổi phân công hoặc lịch cũ.
- Phát hiện dữ liệu đầu vào thiếu/sai trước khi gọi solver; giải thích các lỗi rõ ràng.
- Cung cấp core độc lập, deterministic ở mức có thể kiểm soát bằng seed, dễ benchmark và tái sử dụng khi tích hợp Desktop.

### 1.2 Ngoài phạm vi hiện tại

- Không xây dựng ứng dụng Electron/React, SQLite schema, vnEdu API adapter thật, hệ thống đăng nhập, đồng bộ, triển khai Kubernetes.
- Không reverse engineer hay sao chép mã độc quyền STKB. Có thể tham khảo FET ở mức ý tưởng và đối chiếu kết quả khi có bộ test hợp lệ; tuân thủ giấy phép nếu tái sử dụng mã.
- Không hỗ trợ mọi biến thể nghiệp vụ ngay MVP; phải thiết kế extension points và nêu rõ loại nào chưa hỗ trợ.

## 2. Kiến trúc Core — độc lập I/O

```text
vnedu-tkb/
├── AGENTS.md                        # Quy tắc làm việc cho coding agents (nếu chưa có)
├── pyproject.toml                   # Dependency, tooling, CLI entrypoint
├── README.md
├── docs/
│   ├── assumptions.md              # Giả định và câu hỏi nghiệp vụ
│   ├── domain-model.md
│   ├── constraint-catalog.md
│   ├── solver-design.md
│   └── benchmark-report.md
├── src/tkb_core/
│   ├── __init__.py
│   ├── domain/
│   │   ├── models.py               # Pure domain models
│   │   ├── enums.py
│   │   └── errors.py
│   ├── contracts/
│   │   ├── input.py                # Versioned input schema
│   │   └── output.py               # Versioned output schema
│   ├── preprocessing/
│   │   ├── normalize.py
│   │   └── feasibility.py
│   ├── constraints/
│   │   ├── hard.py
│   │   ├── soft.py
│   │   └── registry.py
│   ├── solver/
│   │   ├── model_builder.py
│   │   ├── cp_sat.py
│   │   ├── objectives.py
│   │   └── statuses.py
│   ├── validation/
│   │   └── independent_validator.py
│   ├── repair/
│   │   └── repair_solver.py
│   ├── reporting/
│   │   └── diagnostics.py
│   └── cli.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── properties/
│   └── fixtures/
│       ├── feasible_small.json
│       ├── infeasible_teacher.json
│       └── locked_lessons.json
└── benchmarks/
    ├── generate_synthetic.py
    └── run_benchmarks.py
```

Điều chỉnh cấu trúc nếu repository đã có convention tương đương; không tạo thư mục trùng lặp vô ích.

**Luồng dữ liệu:** `JSON fixture / API adapter (sau này)` → `Versioned Input` → `Normalize` → `Precheck` → `Model Builder` → `CP-SAT` → `Independent Validator` → `Versioned Result` → `JSON / Desktop adapter (sau này)`.

Core **không biết** SQLite, Electron, HTTP, hay tên bảng vnEdu. Không để ORM model lọt vào solver.

## 3. Domain model và hợp đồng dữ liệu

### 3.1 Các khái niệm bắt buộc

- `SchoolContext`: school ID, năm học, học kỳ, múi giờ, cấu hình tuần học.
- `TimeSlot`: thứ/ngày trong chu kỳ, buổi, tiết; có thứ tự và cờ có thể học.
- `ClassGroup`: lớp hành chính hoặc nhóm học; có thể mở rộng lớp ghép/nhóm tách.
- `Teacher`: định danh giáo viên, thời gian không thể dạy.
- `Subject`: môn học, thông tin phân phối và yêu cầu đặc thù.
- `Room`: phòng học, loại phòng, năng lực, thời gian khả dụng (tùy chọn).
- `TeachingRequirement`: một yêu cầu giảng dạy có `requirement_id` duy nhất, tập lớp/nhóm, môn, giáo viên được phân công (có thể nhiều người), số tiết mỗi chu kỳ, yêu cầu phòng, tiết liên tiếp nếu có.
- `LessonOccurrence`: từng đơn vị cần xếp từ `TeachingRequirement`; có định danh ổn định để khóa, sửa và so sánh.
- `HardConstraintConfig`, `SoftConstraintConfig`: loại, scope, tham số, trọng số, bật/tắt; có kiểm tra schema.
- `LockedAssignment`: occurrence được cố định vào slot/phòng.
- `PreviousSchedule`: lịch cũ phục vụ repair.
- `ScheduleAssignment`: occurrence → slot + room + giáo viên/lớp tương ứng.

**Quan trọng:** Không chỉ dùng `(class_id, subject_id, teacher_id)` làm khóa duy nhất vì có thể tồn tại nhóm học, đồng giảng, nhiều phân công cùng môn, tiết đôi. Chỉ tạo model cho nghiệp vụ được xác nhận; trường hợp chưa hỗ trợ phải báo lỗi `UNSUPPORTED_FEATURE` rõ ràng, không silently ignore.

### 3.2 Contract và validation

- Dùng Pydantic v2 hoặc dataclass + validation nhất quán; ưu tiên Pydantic ở ranh giới JSON.
- Có `schema_version` ở input/output.
- ID nguồn là opaque string; không giả định số nguyên liên tục.
- Validate uniqueness, tham chiếu ID, số tiết không âm, slot hợp lệ, khóa tiết không xung đột, phòng/giáo viên hợp lệ.
- Giữ `source_reference` hoặc metadata tùy chọn để adapter vnEdu sau này mapping lại ID, không chứa bí mật xác thực.
- Mỗi kết quả có `input_fingerprint` (hash từ dữ liệu đã chuẩn hóa) để kiểm tra lịch có còn khớp dữ liệu nguồn hay không.

### 3.3 JSON minh họa (KHÔNG phải schema vnEdu)

```json
{
  "schema_version": "1.0",
  "school": {"school_id": "demo-school", "academic_year": "2026-2027", "term": "1"},
  "time_slots": [
    {"id": "mon-am-1", "day": 1, "session": "AM", "period": 1},
    {"id": "mon-am-2", "day": 1, "session": "AM", "period": 2}
  ],
  "classes": [{"id": "10A1"}],
  "teachers": [{"id": "T001"}],
  "subjects": [{"id": "MATH"}],
  "rooms": [],
  "teaching_requirements": [
    {"id": "R001", "class_ids": ["10A1"], "subject_id": "MATH", "teacher_ids": ["T001"], "periods_per_cycle": 1}
  ],
  "locked_assignments": [],
  "constraint_config": {"hard": [], "soft": []}
}
```

Codex cần hoàn thiện schema chính thức, sinh fixture hợp lệ theo schema đó và ghi rõ trường bắt buộc/tuỳ chọn; không coi ví dụ trên là contract bất biến.

## 4. Thuật toán CP-SAT — yêu cầu kỹ thuật

### 4.1 Mô hình biến

Cho mỗi occurrence `l` và slot hợp lệ `s`, biến Boolean `x[l,s]` cho biết tiết `l` có được xếp vào `s` hay không. Nếu cần phòng, có thể dùng biến `x[l,s,r]` hoặc liên kết biến phòng tùy kích thước mô hình. **Không tạo biến cho tổ hợp bị cấm từ đầu** để giảm không gian tìm kiếm.

Cân nhắc `AddExactlyOne` cho mỗi occurrence; dùng `AddAtMostOne` trên tập occurrence chia sẻ lớp, giáo viên hoặc phòng trong cùng slot. Xây index theo resource/slot để tránh vòng lặp pairwise O(n²) không cần thiết.

### 4.2 Hard constraints — MVP bắt buộc

1. Mỗi occurrence được xếp **đúng một lần**.
2. Một lớp/nhóm không có hai occurrence trùng slot (trừ mô hình đồng giảng được biểu diễn là **một occurrence**).
3. Một giáo viên không được tham gia hai occurrence cùng slot.
4. Một phòng không được phục vụ hai occurrence cùng slot, nếu bài toán có quản lý phòng.
5. Chỉ xếp vào slot hợp lệ của lớp, giáo viên và phòng.
6. Đúng tổng số tiết theo mỗi `TeachingRequirement`.
7. Các tiết khóa giữ nguyên; khóa sai phải được phát hiện trước hoặc trả infeasible có giải thích phù hợp.
8. Yêu cầu phòng chuyên dụng phải được thỏa mãn khi bật quản lý phòng.
9. Hỗ trợ phân biệt ca sáng/chiều, lịch học khác nhau theo lớp qua tập slot khả dụng.

**Sau MVP / khi xác nhận nghiệp vụ:** tiết đôi liên tiếp, không vượt số tiết môn mỗi ngày, quy tắc phân phối theo ngày, giáo viên chủ nhiệm, tiết chào cờ/sinh hoạt, lớp ghép, giáo viên đồng giảng, tuần A/B. Không tự gán mọi quy tắc này thành hard mặc định.

### 4.3 Soft constraints — từng bước

- Hạn chế tiết trống trong lịch giáo viên.
- Hạn chế môn bị dồn trong một ngày.
- Ưu tiên tiết/buổi mong muốn của giáo viên.
- Phân bố tiết hợp lý trong tuần.
- Khi repair: tối thiểu hóa số occurrence bị thay đổi so với lịch cũ.

Mỗi soft constraint phải có: `code`, `scope`, `weight`, `penalty`, cách tính rõ ràng, unit tests riêng. **Không dùng trọng số tùy tiện không tài liệu hóa.** Chuẩn hóa thang penalty hoặc nêu rõ tradeoff. Trước hết tìm lịch hợp lệ, sau đó mới tối ưu; có thể dùng giải theo giai đoạn/lexicographic objective khi cần.

### 4.4 Trạng thái và kết quả

Phân biệt tối thiểu:
- `OPTIMAL`: đã chứng minh tối ưu cho mô hình và objective hiện tại.
- `FEASIBLE`: có lịch hợp lệ, chưa chứng minh tối ưu.
- `INFEASIBLE`: đã chứng minh vô nghiệm.
- `UNKNOWN`: chưa chứng minh có/không có nghiệm trong giới hạn.
- `MODEL_INVALID`: model không hợp lệ.
- `INPUT_INVALID`: dữ liệu đầu vào sai, chưa gọi solver.
- `UNSUPPORTED_FEATURE`: yêu cầu vượt phạm vi solver hiện tại.

Không trả lịch khi chưa có nghiệm hợp lệ. Nếu timeout nhưng có nghiệm, trả `FEASIBLE` và metadata thích hợp. Bao gồm `wall_time`, `objective_value`, `best_bound` (khi có), `solver_version`, `seed`, `num_workers`, `time_limit_seconds`, `diagnostics`, `assignments`.

### 4.5 Cấu hình chạy

- `max_time_in_seconds` cấu hình được; default ban đầu đề xuất 60 giây cho fixture nhỏ, không phải cam kết production.
- `num_search_workers` cấu hình được; benchmark 1, 2, 4, 8 tùy máy. Không giả định nhiều worker luôn nhanh hơn.
- `random_seed` cấu hình được; lưu lại trong kết quả. Lưu ý đa luồng và version solver có thể ảnh hưởng tính tái lập.
- Chạy solver trong process riêng khi tích hợp Electron sau này; core không phụ thuộc cơ chế IPC.
- Hỗ trợ callback báo nghiệm trung gian hoặc progress ở mức solver có thể cung cấp, không giả lập % hoàn thành chính xác.

## 5. Independent Validator — bắt buộc

Viết validator **độc lập với model CP-SAT**, duyệt assignments và kiểm tra lại toàn bộ hard constraints bằng logic Python thuần.

- Validator trả `valid`, danh sách `violations` gồm `code`, `message`, `resource_ids`, `slot_ids`, `occurrence_ids`.
- Không tin nghiệm solver mà bỏ qua validator.
- Kiểm thử validator bằng lịch được cố ý làm sai: trùng giáo viên, trùng lớp, trùng phòng, thiếu tiết, sai tiết khóa, slot bị cấm.
- Chỉ xuất `valid_schedule=true` khi independent validator xác nhận.

## 6. Feasibility prechecks và diagnostics

Trước khi gọi CP-SAT, kiểm tra tối thiểu:
- Tổng nhu cầu tiết của mỗi lớp so với số slot khả dụng.
- Tổng nhu cầu tiết của mỗi giáo viên so với số slot có thể dạy.
- Phòng chuyên dụng thiếu hoặc quá ít so với nhu cầu cơ bản.
- Locked assignments trùng resource hoặc ngoài slot hợp lệ.
- ID tham chiếu không tồn tại, số tiết không hợp lệ, slot trùng.

Đây là **điều kiện cần**, không phải phép chứng minh lịch khả thi. Nếu CP-SAT trả `INFEASIBLE`, không tự khẳng định nguyên nhân duy nhất khi chưa có bằng chứng; cung cấp chẩn đoán hữu ích, có thể nghiên cứu assumption literals/unsat core trong giai đoạn sau.

## 7. Repair và khóa tiết

Thiết kế API `solve(problem, options)` và `repair(problem, previous_schedule, locked_assignments, options)`.

- MVP: khóa một số occurrence; giải lại phần còn lại.
- Phase tiếp: tối ưu penalty cho số tiết thay đổi, hỗ trợ giới hạn số thay đổi và vùng xếp lại.
- Lịch cũ phải được validate và so khớp `input_fingerprint` hoặc nêu rõ mapping thay đổi dữ liệu nguồn.
- Nếu thay đổi phân công khiến tiết cũ không hợp lệ, báo diagnostics; không âm thầm giữ nguyên.

## 8. CLI để kiểm thử trước khi có UI

Tạo CLI với các lệnh tương đương:

```bash
python -m tkb_core.cli validate-input tests/fixtures/feasible_small.json
python -m tkb_core.cli solve tests/fixtures/feasible_small.json --time-limit 60 --workers 4 --seed 42 --output /tmp/tkb-result.json
python -m tkb_core.cli validate-schedule tests/fixtures/feasible_small.json /tmp/tkb-result.json
python -m tkb_core.cli benchmark --dataset synthetic-small --repeat 3
```

Lệnh chỉ là contract mong muốn; implement CLI bằng argparse hoặc Typer (ưu tiên ít dependency). Mọi lệnh có exit code hợp lý, JSON output parse được, stderr dành cho log; không in log làm hỏng stdout JSON.

## 9. Testing và benchmark

### 9.1 Unit tests

- Domain validation và versioned JSON contract.
- Mỗi hard constraint: một fixture hợp lệ và một fixture vi phạm.
- Mỗi soft penalty: kiểm tra tính toán độc lập.
- Status mapping và timeout.
- Locked assignments, invalid reference, empty requirements, duplicate IDs.

### 9.2 Integration tests

- Fixture nhỏ có nghiệm và validator xác nhận.
- Fixture cố tình vô nghiệm do trùng khóa hoặc thiếu slot.
- Một lịch có nhiều môn, nhiều giáo viên, nhiều lớp.
- Repair giữ các occurrence khóa, giảm thay đổi khi có thể.
- Serialize → deserialize không mất thông tin.

### 9.3 Property-based / randomized tests

- Sinh dữ liệu synthetic hợp lệ theo seed; so sánh tổng số tiết, uniqueness, resource collision.
- Nếu dùng Hypothesis, giới hạn kích thước để CI chạy nhanh.
- Không dùng dữ liệu học sinh/giáo viên thật trong repo.

### 9.4 Benchmark

Tạo generator cho các cỡ **tham khảo**: 10/20/40/60/100 lớp; cấu hình số giáo viên, số slot, mật độ phân công, số ràng buộc, mức độ khóa tiết. Không suy ra tốc độ chỉ từ số lớp.

Ghi lại: CPU model, RAM, OS, Python version, OR-Tools version, số lớp/giáo viên/occurrences/slots, workers, seed, time limit, solver status, time-to-first-feasible (nếu đo được), wall time, objective/bound, validator pass/fail, peak memory (nếu đo được).

Không viết kết luận kiểu “60 lớp mất 2 phút” nếu chưa chạy benchmark thật. Có thể lưu CSV/JSON benchmark, không cần dựng dashboard.

## 10. Phases và điều kiện hoàn thành

### Phase 0 — Khảo sát và dựng skeleton

- Khảo sát repo và ghi nhận kiến trúc hiện có.
- Thiết lập `pyproject.toml`, lint/type-check/test, cấu trúc package.
- Viết `docs/assumptions.md` và `docs/domain-model.md`.
- Xây schema input/output versioned và fixture nhỏ.

**Done khi:** Import package được, validate fixture thành công, test và lint cơ bản chạy được.

### Phase 1 — Scheduling MVP (hard constraints)

- Implement normalize, prechecks, CP-SAT model builder.
- Hỗ trợ lớp, giáo viên, môn, phân công, slot, tiết khóa; phòng học nếu được bật.
- Implement solver statuses, result serialization.
- Implement independent validator.

**Done khi:** Có thể chạy CLI solve trên fixture có nghiệm; tất cả hard constraints được validator xác nhận; fixture vô nghiệm được xử lý đúng; unit/integration tests pass.

### Phase 2 — Quality optimization

- Implement soft constraint registry, penalty và weighted objective.
- Hỗ trợ nguyện vọng giáo viên, phân phối môn, giảm tiết trống theo đặc tả đã thống nhất.
- Tài liệu hóa trọng số, tránh objective sai hoặc penalty đếm trùng.

**Done khi:** Có fixture chứng minh soft score được cải thiện so với baseline mà không vi phạm hard constraints; test pass.

### Phase 3 — Repair + Benchmark

- Implement locked lessons và repair so với lịch trước.
- Synthetic dataset generator; benchmark nhiều kích thước và CPU settings.
- Hoàn thiện diagnostics, tài liệu hạn chế, profiling và các bottleneck chính.

**Done khi:** Repair test pass, benchmark report có số liệu thực, validator độc lập pass trên mọi nghiệm trả về.

### Phase 4 — Sau này, KHÔNG thực hiện lúc này

- vnEdu API adapters (fetch dữ liệu + sync kết quả, auth và đối soát).
- SQLite local (nháp, constraint config, lịch sử, sync log).
- Electron/React UI, worker process IPC, đóng gói Python binary.
- Installer, auto-update, Windows benchmark, triển khai sản phẩm.

## 11. Tiêu chuẩn code và chất lượng

- Python 3.12+ (kiểm tra tương thích phiên bản OR-Tools được pin).
- Type hints đầy đủ ở public API; module có docstrings và lỗi nghiệp vụ rõ ràng.
- `pytest`, `ruff`; có thể dùng `mypy` hoặc `pyright` nếu repo đã cấu hình.
- Pin dependency qua lockfile phù hợp; tách dependencies dev và runtime.
- Không log dữ liệu cá nhân hoặc token; fixtures dùng ID giả.
- Tối ưu đúng trước khi tối ưu nhanh; tránh xây toàn bộ Cartesian product không cần thiết.
- Public API phải ổn định và độc lập với transport/storage.
- Mọi thay đổi thuật toán cần test regression để không làm hỏng lịch hợp lệ trước đó.

## 12. Mẫu báo cáo sau mỗi phase

Codex phải phản hồi theo mẫu:

```text
PHASE: ...
Implemented:
- ...
Files changed:
- ...
Commands executed:
- ...
Test results:
- PASS/FAIL + số lượng test
Benchmark results:
- Chỉ số đo được hoặc "not run"
Known limitations:
- ...
Open business questions:
- ...
Next proposed step:
- ...
```

Không nói “hoàn thành” khi còn test thất bại hoặc chưa chạy. Nếu thiếu công cụ/dependency thì báo rõ, không giả lập kết quả.

## 13. Các câu hỏi nghiệp vụ cần giữ mở

Không được tự quyết định thay người dùng:

1. Trường tiểu học, THCS, THPT có cùng một bộ quy tắc hay khác nhau?
2. Số ngày/tuần, số buổi/ngày, số tiết/buổi có thể cấu hình theo lớp không?
3. Các tiết chào cờ, sinh hoạt, hoạt động trải nghiệm được biểu diễn như môn, occurrence đặc biệt hay quy tắc cố định?
4. Có giáo viên đồng giảng, lớp ghép, học theo nhóm, phòng bộ môn hay không?
5. Có yêu cầu tiết đôi, tiết liên tiếp, môn không học 2 lần/ngày, khoảng cách giữa các tiết không?
6. Phân công có nhiều giáo viên cho cùng một môn/lớp không?
7. Lịch được xếp theo tuần cố định, tuần A/B hay theo chu kỳ khác?
8. Nguyện vọng giáo viên và tiêu chí chất lượng nào là bắt buộc, tiêu chí nào là ưu tiên?
9. Cần sửa lịch giữ nguyên tối đa các tiết đã công bố hay chỉ giữ tiết đã khóa?
10. API vnEdu trả về những ID và trường dữ liệu nào? **Chỉ giải quyết ở Phase 4 khi có contract thật.**

## 14. PROMPT KHỞI ĐỘNG CHO CODEX

Sau khi thêm file này vào repo, dùng prompt sau:

> Đọc toàn bộ `VNEDU_TKB_CORE_FIRST_CODEX.md` và các quy tắc trong `AGENTS.md` nếu có. Dự án là TKB Desktop vnEdu, nhưng hiện tại **chỉ xây dựng Scheduling Core Python + OR-Tools CP-SAT độc lập**. Hãy khảo sát repository, trình bày kế hoạch ngắn, rồi thực hiện **Phase 0 và Phase 1** theo đặc tả, bao gồm versioned domain contracts, preprocessing, hard constraints, solver, independent validator, CLI và pytest fixtures. Không viết Electron, React, SQLite, FastAPI hay vnEdu API adapter. Không tự suy đoán schema vnEdu. Chạy test thực tế, báo cáo file thay đổi, kết quả test và giới hạn còn lại. Chỉ bắt đầu Phase 2 sau khi Phase 1 đạt tiêu chí nghiệm thu.

---

**Định hướng cốt lõi:** Đầu tiên phải chứng minh engine xếp được một thời khóa biểu **đúng**, sau đó mới tối ưu để xếp **đẹp**, rồi mới xây ứng dụng Desktop và kết nối vnEdu.
