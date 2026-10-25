# Hard constraint catalog — Phase 1

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
