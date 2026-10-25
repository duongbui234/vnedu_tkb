# Phase 0 — giả định, quyết định và giới hạn

**Lịch sử Phase 0:** nội dung dưới ghi lại giới hạn tại mốc đó. Phase 1 đã bổ sung
solver/prechecks/validator theo [solver-design](solver-design.md) và [catalog](constraint-catalog.md);
không diễn giải các câu “chưa có” bên dưới là hiện trạng sau Phase 1.

Ngày: 2026-10-26. Đây là contract synthetic của core, **không phải schema vnEdu**.
Yêu cầu hiện tại chỉ Phase 0; [Core First](VNEDU_TKB_CORE_FIRST_CODEX.md) ưu tiên hơn
phạm vi rộng của [thiết kế tổng thể](superpowers/specs/2026-10-25-scheduling-core-design.md).

## Quyết định kỹ thuật

- Python 3.12+; môi trường phát triển được chọn bằng `.python-version` (3.12).
- Pydantic v2 dùng chung cho domain và ranh giới JSON; không nhân đôi dataclass/DTO.
- Schema input/output hiện chỉ `1.0`; không tự migrate version lạ, không bỏ field lạ.
- Pydantic instances có thể thay đổi; chưa là immutable solver snapshot. Fingerprint
  tính mới mỗi lần, không cache. Phase 1 phải validate lại khi nhận input và tạo snapshot
  riêng trước khi normalize/solve, không giữ tham chiếu data caller có thể sửa.
- Không tạo sẵn các module solver/repair/registry rỗng hoặc stub trả kết quả giả.
- OR-Tools 9.15.6755 được pin ở extra `solver`, metadata package công bố Python >=3.9;
  chưa cài/chạy extra này nên chưa chứng nhận tương thích thực nghiệm với solver.
- `uv.lock` pin dependency runtime/dev/optional. Dependency tải trong Phase 0 chỉ phục
  vụ contract, test, lint, type-check; không thêm framework web.

## Ý nghĩa dữ liệu trong contract v1

- `day` là chỉ số ngày dương trong chu kỳ; `session` là nhãn opaque. Không mặc định
  6/7 ngày, hai buổi hoặc 5 tiết. `(day, session, period)` phải duy nhất.
- `start_minute/end_minute`, nếu có, là khoảng nửa mở dùng cùng gốc đầu chu kỳ;
  phải có đủ cặp và end > start. Phase 0 chưa kiểm overlap/thứ tự theo thời gian thật.
- `timezone` mặc định `Asia/Ho_Chi_Minh` cho fixture; có thể truyền nhãn khác. Phase 0
  chưa xác minh timezone bằng IANA hoặc diễn giải timestamp/DST.
- `available_slot_ids=null` hoặc không có field = không hạn chế thêm ngoài các slot
  được phép học; `[]` = không có slot khả dụng. Đây là quy ước của input synthetic;
  adapter tương lai không được lấy response API thiếu coverage để suy ra rảnh toàn chu kỳ.
- `periods_per_cycle` là số nguyên không âm do caller xác nhận, không phải tiết/tuần
  suy từ chương trình môn học. Zero và danh sách demand rỗng hợp lệ về cấu trúc;
  không chứng minh dữ liệu trường thực đã đầy đủ.
- Không khai báo split thì mỗi occurrence có duration 1. Nếu có `block_durations`,
  từng duration >0, tổng bằng demand; thứ tự block quyết định occurrence ordinal.
- ID occurrence là `<requirement_id>::<ordinal>` với ordinal thập phân 1-based, không
  có zero đầu. Requirement ID có `::` vẫn được đọc bằng delimiter cuối. Không tạo
  occurrence thực trong Phase 0; đổi split/demand cần reconciliation ở phase repair.
- `manage_rooms=false` loại phòng khỏi scope solve tương lai. Demand room_required
  hoặc lock phòng yêu cầu manage_rooms=true. Contract chưa chứng minh có đủ phòng,
  capacity/room type phù hợp hoặc thời gian phòng/GV khả dụng.
- Nhiều teacher/class IDs và rule declarations có thể biểu diễn trong contract.
  **Chấp nhận cấu trúc không đồng nghĩa engine đã hỗ trợ nghiệp vụ đó.** Phase 1 phải
  enforce hoặc trả UNSUPPORTED_FEATURE; không silently ignore. Chưa có student
  subgroup membership, điểm trường, travel matrix hay tuần A/B trong schema v1.

## Những gì Phase 0 chưa kiểm

Không kiểm khả thi, tổng tải so với slot, clash giữa các khóa, khóa vào giờ bận,
khả năng đặt block qua break, xung đột lịch hoặc chất lượng. Không có independent
schedule validator. Result contract chỉ chặn những khai báo tự mâu thuẫn; một report
`valid=true` do caller cung cấp không phải bằng chứng rằng lịch đã được kiểm.

CLI chỉ trả `INPUT_VALID` với `checked=contract` và `solver_executed=false`; không
dùng OPTIMAL/FEASIBLE hoặc valid_schedule=true cho việc validate fixture.

## Câu hỏi nghiệp vụ giữ mở

Nguồn demand/số tiết thật; khung ngày/buổi/tiết và break; coverage lịch bận; nghĩa
hoạt động chung; lớp ghép/tách/đồng giảng có thuộc MVP không; phòng/travel; hard/soft,
ngưỡng và ưu tiên chất lượng; cách giữ lịch cũ. Không quyết định các câu trả lời bằng
dữ liệu STKB/API chưa giải mã. Các câu hỏi này không chặn kiểm chứng contract synthetic.

## Ranh giới giai đoạn

Phase 1 mới thêm normalize, prechecks, model, solve và independent validator.
Phase 2 mới tối ưu soft; Phase 3 mới repair/benchmark. Không cài Electron/React,
SQLite/FastAPI, kết nối vnEdu hoặc mở file dữ liệu thật trong Phase 0.
