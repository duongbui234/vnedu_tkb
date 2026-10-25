# Scheduling Core — dự thảo đầu vào và ràng buộc

Ngày: 2026-10-25. Trạng thái: **DRAFT**, chưa phải đặc tả được giáo vụ xác nhận hoặc thiết kế model CP-SAT hoàn chỉnh. Tài liệu cụ thể hóa bước tiếp theo sau nghiên cứu; không triển khai solver, adapter, database hoặc UI.

Bản thiết kế kết hợp sau nghiên cứu: [Scheduling Core STKB/FET/CP-SAT](../superpowers/specs/2026-10-25-scheduling-core-design.md). Tài liệu đó đề xuất kiến trúc, encoding, tối ưu, repair và worker; các UNKNOWN nghiệp vụ ở đây vẫn cần xác nhận.

**VERIFIED** = bằng chứng đã quan sát; **INFERRED** = đề xuất thiết kế; **UNKNOWN** = còn thiếu xác nhận. Mọi field và cách xử lý đề xuất dưới đây là INFERRED trừ khi ghi khác. Không tự bật rule hoặc đặt ngưỡng cho trường chỉ vì STKB/FET có hỗ trợ.

## 1. Các quyết định đã có và khoảng thiếu

**VERIFIED — quyết định của người dùng:** Electron + React/TypeScript, Python + Google OR-Tools CP-SAT chạy local, SQLite và API vnEdu. Tạm dừng nghiên cứu tkb.com.vn; không đưa mô tả marketing của trang đó thành ràng buộc đã xác minh.

**VERIFIED — dữ liệu quan sát:** [API đọc](vnedu-api-live-findings.md) trả 38 lớp, 109 GV, 20 môn, 527 phân công, 2 điểm trường. Cả 527 giá trị `so_tiet` bằng chuỗi `"0"`; 5 dòng phân công không tìm thấy GV tương ứng. [Tám file STKB](../../reverse-engineering/reports/STKB-file-format-analysis.md) đọc được phần danh mục và nối ID với API; chưa đọc được demand, incumbent hoặc rule đầy đủ.

**UNKNOWN:** số tiết thực và đơn vị, calendar, lý do thiếu GV, quy tắc trường, ý nghĩa hai nhóm lớp trong file, yêu cầu phòng, thời gian di chuyển, ngân sách chạy và mức chất lượng chấp nhận được.

Nghiên cứu đủ để đề xuất domain/rules. Dữ liệu hiện tại **chưa đủ tạo job xếp lịch trường thực hợp lệ**. Không cần khôi phục hết mã STKB để hoàn thành domain; dữ liệu có thể đến từ API, file hoặc cấu hình giáo vụ đã xác nhận, có nguồn rõ ràng.

## 2. Ranh giới core và phương án tiếp cận

Giữ CP-SAT theo quyết định đã có. Giai đoạn đầu tập trung tìm lịch đủ demand và thỏa hard, sau đó mới tối ưu chất lượng. Chưa triển khai lại FET recursive swapping hoặc STKB FPR/DPR; chỉ cân nhắc heuristic/repair bổ sung khi có benchmark chỉ ra vấn đề.

Core nhận một snapshot bất biến, không gọi API vnEdu, không đọc cấu hình ngầm từ máy người dùng, không đồng bộ kết quả lên server. Adapter chịu trách nhiệm chuyển dữ liệu nguồn thành domain; serializer STKB là một nguồn nhập có thể bổ sung, không phải mô hình dữ liệu nội bộ của solver.

Đề xuất scope mỗi job là tập lớp được chọn cùng **mọi tài nguyên/lịch bận liên quan**, gồm GV dùng chung ngoài scope. Xếp riêng điểm trường vẫn phải tránh lịch GV ở nơi khác. Chưa khẳng định phiên bản đầu bắt buộc xếp toàn trường hoặc có đủ dữ liệu để xếp phòng.

## 3. Contract đầu vào đề xuất

Tên field là domain đề xuất, không phải field API đã tồn tại.

| Thành phần | Dữ liệu tối thiểu | Điều kiện hợp lệ |
|---|---|---|
| Snapshot | `schema_version`, `snapshot_id`, `school_id`, `academic_year`, `semester`, `source_refs`, `input_hash` | Phạm vi và nguồn nhất quán; không ghép file tháng 9 với API tháng 10 mà không reconciliation |
| Calendar | Ngày trong horizon, buổi, slot ID, thời điểm bắt đầu/kết thúc, break, điểm trường áp dụng | Slot có thứ tự và thời gian thật; không đồng nhất tiết 1 sáng với tiết 1 chiều; cùng số tiết ở hai cơ sở có thể lệch giờ |
| Giáo viên | ID nội bộ ổn định, ánh xạ ID nguồn | Tên không làm khóa; giữ riêng alias `gv_id`/`giao_vien_id` cho tới khi xác minh namespace |
| Người học | Lớp/nhóm ID, quan hệ thành viên hoặc tập nhóm học sinh không giao nhau | Lớp thường có một resource; lớp ghép/tách chỉ bật khi dữ liệu biểu diễn đúng giao nhau |
| Môn và cơ sở | ID môn, ID điểm trường, quan hệ lớp–điểm trường | Không tự suy điểm trường từ nhóm sáng/chiều hoặc tên lớp |
| Demand | ID phân công, môn, nhóm học, GV tham gia, tổng tiết, đơn vị/horizon, nguồn | Tổng tiết được xác nhận; không mặc định `so_tiet=0` hiện tại là demand hoàn chỉnh |
| Cách chia demand | Danh sách block duration và quan hệ với demand | Tổng duration bằng tổng tiết; ví dụ 5 tiết gồm `[2,1,1,1]` nếu yêu cầu một block đôi |
| Availability | Resource ID, khoảng thời gian, lý do và loại cấm/preference | Cấm thật khác mong muốn tránh; phải khai báo coverage, không coi response thiếu là rảnh cả tuần |
| Hoạt động cố định | ID ổn định, participants, time, duration, yêu cầu phòng, liên kết demand nếu có | Chào cờ/sinh hoạt không bị sinh hai lần; không chặn GV không tham gia |
| Phòng, nếu thuộc scope | ID, cơ sở, capacity/equipment đã biết, availability | Không có phòng khác với không xếp phòng; yêu cầu phòng bắt buộc thiếu dữ liệu là lỗi |
| Incumbent/khóa, nếu dùng | Occurrence ID, vị trí cũ, `lock_time`, `lock_room` riêng | Ánh xạ cùng demand/version hoặc migration rõ; hint không phải khóa |
| Rules | ID, loại, scope, tham số, hard/soft, đơn vị penalty, priority, nguồn/version | Mọi rule bật có đủ tham số và evaluator; không dùng trọng số ngầm lấy từ STKB/FET |
| Run request | Mode xếp mới/sửa, budget, seed, workers, scope và phiên bản model | Repair cần incumbent hợp lệ; budget cụ thể còn UNKNOWN |

**Đơn vị đề xuất:** horizon cơ sở là một tuần điển hình; demand tính theo tiết trong tuần đó. Đây là lựa chọn cần xác nhận, **không phải kết luận về đơn vị `so_tiet` API**. Nếu các khối/cơ sở có giờ tiết khác nhau, duration tính tiết và overlap tính phút thật; phải chọn placement có chuỗi slot phù hợp.

Một occurrence có tập GV và tập nhóm người học cùng tham gia. Đồng giảng dùng nhiều GV trong cùng occurrence; chia số tiết cho hai GV là các demand/occurrence khác nhau. Lớp ghép không được nhân đôi duration hoặc sức chiếm phòng. Các chức năng này có thể chưa bật ở bản đầu, nhưng không gắn cứng domain vào đúng một GV và một tên lớp.

## 4. Quy tắc hợp lệ nền tảng

ID C01–C22 giữ nguyên từ [ma trận đối chiếu có dẫn chứng STKB/FET](stkb-fet-vnedu-comparison.md#3-ma-trận-ràng-buộc-nên-đưa-vào-scheduling-core). Các điều kiện bên dưới là đặc tả **đề xuất**, không phải rule trường đã xác nhận.

| ID | Điều kiện đạt | Ví dụ không đạt / kiểm tra bắt buộc |
|---|---|---|
| C01 — đủ phân công | Mỗi occurrence được đặt đúng một lần; tổng duration theo demand bằng số tiết đã xác nhận; đúng participants | Demand 5 mà xếp 4 hoặc tự thay GV để né conflict; một tiết đôi chỉ được tính 2 tiết |
| C02 — GV không trùng | Hai khoảng thời gian của cùng GV không giao nhau, kể cả qua cơ sở | Hai lớp dùng cùng GV ở thời gian chồng một phần; chỉ xét số thứ tự tiết sẽ bỏ sót |
| C03 — người học không trùng | Mọi nhóm học sinh thành phần chỉ tham gia tối đa một hoạt động cùng lúc | Hai tên lớp khác nhau nhưng chung nhóm học sinh; hoạt động lớp ghép đếm một lần theo participant set |
| C04 — phòng không trùng | Khi xếp phòng, mỗi phòng thật chỉ chứa tối đa một hoạt động chồng thời gian | Hai block khác start nhưng footprint giao nhau; không tạo một phòng giả chung cho mọi tiết không cần phòng |
| C05 — calendar | Toàn bộ hoạt động nằm trong slot hoạt động đã khai báo | Ép calendar 7×5 theo layout lưu file, dùng giờ không có trong lịch trường |
| C06 — không khả dụng | Không participant/phòng nào bị chiếm trong khoảng cấm | GV đang họp vẫn được xếp; preference bị nhầm thành cấm hoặc cấm bị tự nới |
| C07 — giữ khóa | Time/room được giữ đúng theo từng loại khóa và occurrence | Khóa giờ bị đổi để cải thiện điểm; khóa phòng kéo theo khóa giờ ngoài ý muốn |
| C08 — block | Chiếm đủ duration, liền nhau theo slot hợp lệ, không vượt break/buổi/ngày nếu không cho phép | Block đôi bắt đầu tiết cuối buổi; đổi block đôi thành hai tiết rời |
| C09 — phòng phù hợp | Room-required activity đáp ứng capacity/equipment/cơ sở đã khai báo | Thiếu capacity bị coi như phòng vô hạn; không chọn được phòng nhưng báo complete |
| C21 — hoạt động chung | Participants, footprint và cách tính vào demand được khai báo một lần | Đã có sinh hoạt trong demand nhưng lại sinh thêm; chào cờ tự chiếm tất cả GV dù không được khai báo |

Không dùng objective để đánh đổi vi phạm hard. Chế độ chẩn đoán lịch thiếu tiết, nếu bổ sung, phải có nhãn và trạng thái riêng; không trả như lịch hoàn chỉnh.

## 5. Rule chất lượng và policy phải chốt

Chưa chọn trọng số hoặc ngưỡng mặc định. Với mỗi rule được bật, cần tối thiểu một ví dụ đạt, một ví dụ không đạt, công thức/đơn vị và ngoại lệ. Những rule không thuộc scope giữ trạng thái không bật; không ngầm có giá trị 0.

| ID | Nội dung cần chốt | Đơn vị penalty đề xuất khi soft |
|---|---|---|
| C10 | Trần tải ngày/buổi cho GV và người học; cộng cả hai buổi | Số tiết vượt trần |
| C11 | Giới hạn tiết liên tục, break có ngắt chuỗi không | Số tiết vượt run limit |
| C12 | Tải tối thiểu chỉ khi có dạy; xử lý buổi một tiết | Số tiết thiếu mức tối thiểu trên buổi có dạy |
| C13 | Cách môn theo ngày thật; môn nào có ngoại lệ | Số ngày khoảng cách bị thiếu theo cặp occurrence |
| C14 | Trần tiết cùng môn trên ngày/buổi | Số tiết vượt trần theo lớp–môn |
| C15 | Số block đôi bắt buộc hay ưu tiên, có tính chuỗi dài không | Số block đôi thiếu; hard nếu là cấu trúc demand bắt buộc |
| C16 | Gap GV: chỉ tính slot trống giữa hai tiết có dạy, xử lý break/lịch bận riêng | Số slot gap; gap dài nhất là metric khác |
| C17 | Gap người học và yêu cầu vào/ra buổi | Số slot gap và số slot vào muộn, tách metric |
| C18 | Gom ngày/buổi đến trường; phân biệt ngày thật với buổi | Số ngày hoặc số buổi vượt mục tiêu, tách metric |
| C19 | Khung giờ ưu tiên theo môn/GV, áp vào start hay cả block | Số tiết ngoài khung hoặc độ lệch start, phải chọn một định nghĩa |
| C20 | Thời gian di chuyển thực giữa cơ sở; yêu cầu nghỉ chuyển tiết | Hard khi là giới hạn vật lý; số lần đổi cơ sở là soft riêng |
| C22 | Sửa lịch: phần được sửa, phần đóng băng, ưu tiên giữ ngày/giờ/phòng | Số occurrence đổi giờ, đổi ngày, đổi phòng, tách metric và thứ tự |

Ưu tiên giải đủ hard trước; không chọn weighted sum khổng lồ khi chưa có bound. Nếu tối ưu theo tầng, ghi rõ mỗi tầng đã chứng minh tối ưu hay mới có nghiệm khả thi. Không coi tỷ lệ kiểm tra xác suất FET là hệ số objective tương đương của CP-SAT.

## 6. Validation, kết quả và giới hạn chẩn đoán

Trước model: kiểm tra schema/ID, đơn vị demand, coverage calendar/availability, tổng split, khóa mâu thuẫn và domain rỗng. Tổng demand so với sức chứa resource là kiểm tra cần, không chứng minh bài toán có nghiệm. Không gộp số dòng thiếu GV thành số GV thiếu duy nhất.

Kết quả cần tách ba thông tin độc lập:

- Trạng thái dừng: hoàn tất, hết budget, người dùng hủy hoặc lỗi.
- Trạng thái solver: chưa chạy, có nghiệm, đã chứng minh tối ưu, đã chứng minh vô nghiệm hoặc chưa kết luận.
- Trạng thái nghiệp vụ: có đủ lịch hợp lệ theo validator hay chưa; danh sách vi phạm hard và breakdown soft theo đơn vị.

`INVALID_INPUT` không phải `INFEASIBLE`; timeout không chứng minh vô nghiệm. Lịch hợp lệ có thể tồn tại khi hết budget hoặc bị hủy, nhưng chưa tối ưu. Không hứa luôn chỉ ra tập nguyên nhân vô nghiệm nhỏ nhất; chẩn đoán ban đầu trả các lỗi preflight và rule/resource/occurrence liên quan khi có bằng chứng.

Validator độc lập nhận snapshot và assignments, tự dựng footprint và đếm demand/vi phạm, không tin helper variable hoặc score do model tự xuất. Job gắn input/rule/model versions; chỉ nhận incumbent đã validate và không thay lịch đã đồng bộ bằng lịch thiếu hoặc kết quả job cũ.

## 7. Bộ ca chấp nhận tối thiểu trước dùng dữ liệu thật

| Ca | Kết quả mong đợi |
|---|---|
| Một lớp có 5 tiết môn A, một block đôi | Đúng tổng 5; block đôi hợp lệ; không sinh dư occurrence |
| Hai lớp, cùng GV, cùng khoảng thời gian | Bị phát hiện xung đột, kể cả khi thuộc hai cơ sở |
| Hai cơ sở lệch giờ tiết | Đánh giá overlap bằng thời gian thật; không chỉ số tiết |
| Block qua break hoặc buổi | Loại placement khi policy không cho phép |
| Hai khóa cứng xung đột | Báo lỗi rõ; không âm thầm bỏ khóa |
| Khóa giờ nhưng không khóa phòng | Giữ giờ, cho phép chọn lại phòng phù hợp |
| Cả 527 demand `so_tiet=0` chưa được giải thích | Chặn nhập demand trường thực; không trả lịch rỗng là complete |
| Phân công thiếu GV hoặc nguồn số tiết không rõ | Báo lỗi theo record/source; không tự tạo GV hoặc lấy số tiết mẫu |
| Hai nhóm file có cùng ID lớp | Giữ quan hệ nhóm, chỉ một danh tính lớp; không gán thành hai cơ sở |
| Chào cờ/sinh hoạt có sẵn trong demand | Không sinh trùng; chỉ chiếm participant đã khai báo |
| Bật lớp ghép/tách hoặc đồng giảng | Occupancy đúng tập GV/người học; thiếu dữ liệu thành viên thì từ chối chức năng |
| Cần phòng nhưng chưa có phòng | Không báo complete; khác với scope không xếp phòng |
| Repair một vùng có daily load/spacing ngoài vùng | Validator toàn lịch kiểm tra cả biên; vùng hẹp vô nghiệm không chứng minh toàn trường vô nghiệm |
| Timeout/cancel không có nghiệm hoặc có incumbent | Trả đúng trạng thái và độ đầy đủ, không làm mất lịch trước |
| Một bài nhỏ có nghiệm và một bài nhỏ chắc chắn vô nghiệm | Đối chứng bằng vét cạn hoặc expected result độc lập khi triển khai |

Đây là đặc tả ca kiểm thử, **chưa phải test đã chạy với một core tồn tại**. Benchmark FET cũ không thay thế kiểm thử core tương lai.

## 8. Các quyết định còn mở và điều kiện chuyển bước

| Quyết định | Hiện trạng | Cách giải quyết tiếp |
|---|---|---|
| Nguồn demand/số tiết và đơn vị | UNKNOWN, blocker dữ liệu thật | Tiếp tục reader STKB hoặc lấy định mức được giáo vụ xác nhận; không cần API ghi |
| 5 dòng thiếu tham chiếu GV | UNKNOWN, blocker phân công liên quan | Đối chiếu ý nghĩa ID/record với nguồn đúng scope; không tự bỏ dòng |
| Calendar và coverage availability | UNKNOWN, blocker placement thật | Chốt ngày/buổi, thời điểm tiết, nghỉ và nguồn lịch bận |
| Phạm vi phiên bản đầu | INFERRED: feasibility, phòng có điều kiện | Chốt xếp toàn trường hay scope chọn, lớp/nhóm phức tạp có thuộc bản đầu không |
| Hard/soft và chất lượng | UNKNOWN | Giáo vụ chọn policy/ngưỡng/ưu tiên từ C10–C22; không tự chép STKB/FET |
| Incumbent/khóa | UNKNOWN | Đọc được slot STKB hoặc dùng nguồn lịch khác có occurrence mapping |
| Quy mô và budget | UNKNOWN | Số lớp/GV/activity/domain thực tế, cấu hình máy và thời gian chờ chấp nhận được |

Có thể tiếp tục thiết kế interface/validator và ví dụ synthetic từ dự thảo này. Trước khi triển khai model trường thực cần giải quyết demand, ID thiếu, calendar và các hard rule được chọn. Trước khi chốt thiết kế core đầy đủ cần quyết định scope và tiêu chí chấp nhận; không cần đợi mapping mọi mã ràng buộc của STKB hoặc audit toàn bộ 357 lớp FET.

## 9. Nguồn và giới hạn kế thừa

- [Đối chiếu STKB/FET/vnEdu](stkb-fet-vnedu-comparison.md): C01–C22 và sổ bằng chứng hàm/VA/source.
- [Đề xuất áp dụng FET](fet/06-vnedu-applicability.md): domain, model ứng viên, validator và repair; chưa triển khai.
- [Kiểm chứng API](vnedu-api-live-findings.md): snapshot thực tế, schema và khoảng thiếu; HTTP 200 không thay thế kiểm tra body.
- [Định dạng file STKB lượt 1](../../reverse-engineering/reports/STKB-file-format-analysis.md): ID đã đối chứng, layout còn giới hạn; hai nhóm lớp chưa được xác nhận ý nghĩa.
- [So sánh FET/OR-Tools](fet/05-fet-vs-ortools.md): phân biệt bằng chứng và đề xuất; không có benchmark tương đương để kết luận tốc độ.

Không sao chép mã FET AGPL vào sản phẩm; thiết kế domain độc lập không tự giải quyết mọi câu hỏi giấy phép nếu sau này tái sử dụng mã. Không nghiên cứu kích hoạt/bản quyền STKB, không thay dữ liệu vnEdu và không triển khai framework trong lượt này.
