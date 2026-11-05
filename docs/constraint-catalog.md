# Hard constraint catalog — Phase 1

Chính sách nghiệp vụ tương lai được chốt ở [vnEdu policy0.1](research/stkb/09-vnedu-hard-soft-policy.md), kèm [Gap Analysis](research/stkb/03-phase1-gap-analysis.md). Đó là đề xuất cho các phase tiếp theo, không tự bật toàn bộ danh mục. S01–S04 được thực thi trong Phase2A như mục cuối tài liệu; bảng dưới giữ mô tả built-in hard Phase1. Đặc biệt, raw mã998Nghỉ/999Bận của STKB không được tự coi là hard availability.

Tất cả built-in dưới đây luôn bật. Compiler nằm trong preprocessing và
`constraints/hard.py`; evaluator độc lập là `validation/independent_validator.py`.
Các checks về danh mục/split/refs còn được kiểm ở contract input 1.0.

| Điều kiện | Compiler/precheck | Validator độc lập |
|---|---|---|
| Đúng mỗi occurrence một lần, đủ demand | Normalize split bảo toàn tổng; ExactlyOne | Parse IDs/ordinal, uniqueness, count mỗi requirement |
| Đúng lớp/GV phân công | Chỉ tạo assignment từ requirement | So class_ids/teacher_ids với requirement, không tin result |
| Không trùng lớp/GV | Indexed AtMostOne trên resource/token | Occupancy theo slot hoặc sweep physical intervals |
| Calendar/availability | Loại placement chạm can_teach=false hoặc ngoài available slots | Tự dựng footprint và kiểm từng slot/resource |
| Tiết đôi | Một Boolean chiếm hai slots cùng buổi/period liên tiếp | Reconstruct duration từ demand/split và kiểm boundary/break |
| Khóa giờ/phòng | Giới hạn thành phần placement; phát hiện lock conflicts | So start/room với lock và tự kiểm toàn footprint |
| Phòng không trùng | Room token occupancy, null không là resource | Occupancy phòng vật lý, không chiếm room cho null |
| Phòng phù hợp | Room type, capacity >= class size, availability toàn block | Tự kiểm assigned room/type/capacity và availability |

Không có mặc định “một môn không quá 2 tiết/ngày”, cách môn, gaps, nguyện vọng mềm,
minimal-change hoặc travel. Rule declaration enabled chưa hỗ trợ trả
UNSUPPORTED_FEATURE. Các rule disabled vẫn tham gia fingerprint nhưng không enforce.

Room metadata cần đủ cho mọi phòng có thể xét sau type/room-lock filtering; phòng
không thể được chọn không làm input invalid. Tắt manage_rooms chỉ bỏ phạm vi phòng,
không tự bỏ hard time/GV/lớp. Không tạo room ảo để lấy lịch hợp lệ giả.

Symbolic calendar coi slot IDs khác nhau là thời điểm khác nhau; ngày/buổi/period
được khai báo, không suy giờ thật. Timed calendar dùng cùng gốc phút đầu chu kỳ,
mọi slot phải có minutes; overlap vẫn bị bắt dù slot IDs khác nhau. Block timed
chỉ liền khi end trước bằng start sau, không mặc định qua gap chuyển tiết/giờ nghỉ.

Các scope chưa hỗ trợ: nhiều class/GV trên một requirement, membership nhóm chồng,
duration >2, cơ sở/travel, tuần A/B, PreviousSchedule và sửa ít thay đổi. Phase 2/3
chưa thực hiện; không dùng thuật ngữ FET/STKB làm bằng chứng về feature chưa có.

## Phase 2A — các soft rules đã hỗ trợ trên input 1.1

| Code | Parameters | Raw penalty (unit teaching_periods) |
|---|---|---|
| TEACHER_AVOID_SLOTS | slot_ids nonempty | Covered periods giao ô tránh; timed aliases đếm một lần/covered period |
| TEACHER_MAX_PERIODS_PER_SESSION | limit≥0, session_ids nonempty | Tổng max(0,load−limit) theo GV/ngày/buổi |
| TEACHER_MAX_PERIODS_PER_DAY | limit≥0 | Tổng max(0,load−limit) theo GV/ngày, cộng mọi buổi |
| TEACHER_PREFERRED_PERIOD_WINDOW | first_period≤last_period, session_ids nonempty | Covered periods ngoài window inclusive |

Mỗi rule có ID, weight>0, priority1–3 explicit; unit theo tiết, double có thể phạt2.
Soft không loại placements, hard/locks luôn giữ. Input 1.0 vẫn không hỗ trợ custom rules.
S05–S12 và repair chưa có; hard variants S01–S04 chỉ có trên policy 0.2 (mục dưới). Không tự chuyển raw STKB hoặc API thành rule.
Ngưỡng/trọng số của trường phải được xác nhận upstream; không áp max3 toàn trường.

## Phase 2B — hard variants S01–S04 trên input 1.1/policy 0.2

Chỉ teacher scope; cùng parameters/footprint/bucket như soft. Không weight/priority, không là
penalty lớn, không bị nới khi timeout. Rule cùng family không được overlap bất kể mode.

| Code (hard) | Compiler | Validator độc lập |
|---|---|---|
| TEACHER_AVOID_SLOTS | Loại placement có covered slot trùng ô tránh (symbolic theo ID, timed theo giao phút) trong `prepare` (`constraints/hard_variants.py`) | `HARD_AVOID_SLOT` |
| TEACHER_MAX_PERIODS_PER_SESSION | `Σ duration·x ≤ limit` theo GV/ngày/buổi đã chọn (`constraints/hard.py`) | `HARD_SESSION_LIMIT` |
| TEACHER_MAX_PERIODS_PER_DAY | `Σ duration·x ≤ limit` theo GV/ngày | `HARD_DAY_LIMIT` |
| TEACHER_PREFERRED_PERIOD_WINDOW | Loại placement có covered period ngoài [first,last] ở session đã chọn | `HARD_PERIOD_WINDOW` |

S01 hard khác availability: nó cấm cả slot alias giao phút với ô tránh. Lock trái S01/S04 hard
→ INPUT_INVALID/LOCK_CONFLICT; domain rỗng → INFEASIBLE/EMPTY_DOMAIN. Các lock cùng nhau vượt
hard S02/S03 (mỗi lock tự nó hợp lệ) → INFEASIBLE từ solver, không phải LOCK_CONFLICT. INFEASIBLE nghĩa là vô
nghiệm với built-ins cộng hard variants đã khai báo, không chỉ ra rule nguyên nhân. Ngưỡng hard
thực tế (H10) phải được trường xác nhận upstream; Core không tự nâng soft thành hard.

## Phase 2C-1 — phân phối môn S05/S06 trên policy 0.3

| Code | Parameters / scope | Soft raw (unit) | Hard | Compiler | Validator |
|---|---|---|---|---|---|
| SUBJECT_COMPONENT_DAY_SPREAD (S05) | `requirement_ids` (tập không rỗng), `min_day_gap` k≥1; scope phải rỗng | Σ cặp component `max(0,k−|day_i−day_j|)` (`day_gap_shortfall`) | mọi cặp ≥ k ngày | Soft: `AddAbsEquality`+`AddMaxEquality` từng cặp; hard: mỗi cửa sổ k ngày ≤ 1 component | `HARD_DAY_SPREAD` |
| CLASS_SUBJECT_MAX_PERIODS_PER_DAY (S06) | `limit`≥0; scope `class_ids`/`subject_ids` (rỗng = tất cả), không teacher/room | Σ `max(0, tiết lớp+môn+ngày − limit)` (`teaching_periods`) | tiết ≤ limit | Bucket (lớp, môn, ngày) theo start slot × duration | `HARD_SUBJECT_DAY_LIMIT` |

Component là một occurrence (block đôi là một component nhưng 2 tiết khi tính S06). Ngày lấy từ
start slot, khoảng cách theo giá trị `day` (không thứ hạng, không vòng tuần). S05 không ngầm thêm cap
cùng ngày hay điều kiện liên tiếp. Overlap: S05 chung requirement, S06 giao lớp×môn, bất kể mode.
Không có precheck tổng hợp; lock tổ hợp vượt hard → INFEASIBLE. Không có k/limit mặc định.

## Phase 2C-2 — S07–S11 trên policy 0.4 (chỉ soft)

| Code | Parameters | Raw penalty (unit) |
|---|---|---|
| TEACHER_RESTRICTED_SLOTS (S07) | `slot_ids` | Tiết dạy trên ô hạn chế, như S01 (`teaching_periods`) |
| TEACHER_TOTAL_GAPS (S08) | `session_ids` | Σ ô idle theo GV/ngày/buổi (`idle_periods`) |
| TEACHER_MAX_GAP_RUN (S09) | `limit`≥0, `session_ids` | Σ `max(0, chuỗi idle dài nhất − limit)` (`idle_periods`) |
| TEACHER_MIN_FREE_TIME (S10) | `unit` day/session, `target`≥1 | Σ GV `max(0, target − số ngày/buổi rảnh)` (`free_days`/`free_sessions`) |
| TEACHER_SINGLE_PERIOD_SESSION (S11) | `session_ids` | Số (GV, ngày, buổi) dạy đúng 1 tiết (`single_period_sessions`) |

**Ô idle:** `can_teach=true`, nằm giữa tiết dạy đầu và cuối của GV trong buổi, GV không dạy và không
thuộc `occupied_work` của GV. **Chuỗi idle:** các ô idle liền kề theo thứ tự period của calendar buổi;
ô `can_teach=false` hoặc ô họp cắt chuỗi. **Rảnh:** ngày/buổi có ít nhất một ô dạy được, GV không dạy
và không có ô họp. `occupied_work` (policy 0.4) phải nằm ngoài availability (availability `null` bị
từ chối), không cộng tải và không là lock. S01 và S07 cùng GV với ô giao nhau bị từ chối như overlap;
S10 hai unit cùng GV cũng vậy. S08–S11 bị từ chối (`GAP_TIMELINE`) khi hai buổi cùng ngày giao phút.
Không có hard mode và không có ngưỡng mặc định. Key `occupied_work` ở policy 0.1–0.3 bị từ chối kể cả
khi rỗng. Lưu ý S10: ngày/buổi GV chỉ *không thể dạy* (unavailable, không có occupied work) vẫn được
tính là rảnh; muốn không tính, upstream phải khai báo occupied work cho ngày/buổi đó.
