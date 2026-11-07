# Tiếp nhận thời khóa biểu thật từ DB công ty

Ngày 2026-11-07. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-07 (RD2–RD9 theo đề xuất); RD1
(quyền dùng dữ liệu) chờ người dùng xác nhận sau khi hỏi công ty.** Chưa nhận hay xử lý dữ liệu nào;
bước B (schema DB) dự kiến ngày 2026-11-08. Base `b99fcaa` trên `main`.

**Bối cảnh:** người dùng dừng spike S1-b″ ngày 2026-11-07, vì kiểm kỹ trên dữ liệu synthetic là quá mức
so với nhu cầu hiện tại. Người dùng sẽ lấy thời khóa biểu của các trường từ DB công ty để đối chiếu. Đã
tìm trên mạng: không có bộ dữ liệu thời khóa biểu trường Việt Nam công khai ở dạng máy đọc được.

**Mục tiêu:** trả lời bằng dữ liệu thật ba câu hỏi:

1. Core có đọc được dữ liệu của trường thật không? Tính năng nào còn thiếu?
2. Lịch trường đang dùng có chất lượng ra sao khi chấm bằng evaluator độc lập?
3. Với cùng dữ liệu và cùng thang chấm, lịch Core xếp có hợp lệ, có tốt bằng lịch thật không, và mất bao
   lâu?

Kết quả dùng để quyết định:

- có cần tiếp tục hướng search S1 không;
- ngưỡng của quality profile v1;
- tính năng nào cần bổ sung trước Phase 4.

Tài liệu chỉ là kế hoạch. Lượt soạn không sửa code, không truy cập DB, không chạy gì. Duyệt kế hoạch
không phải ủy quyền nhận hay xử lý dữ liệu.

## 1. Nguyên tắc

- **Dữ liệu cá nhân không rời công ty ở dạng định danh.** Tên GV, tên trường và mọi định danh cá nhân
  được thay bằng mã trước khi vào repo hoặc máy chạy (§3). Tuân thủ quy định nội bộ của công ty và pháp
  luật về bảo vệ dữ liệu cá nhân (Luật Bảo vệ dữ liệu cá nhân 2025 có hiệu lực từ 2026-01-01, thay
  Nghị định 13/2023/NĐ-CP; bộ phận pháp chế của công ty xác nhận yêu cầu cụ thể). Người dùng xác nhận đã
  được phép dùng dữ liệu cho mục đích này (RD1).
- **Dữ liệu thật không bao giờ vào git.** Mọi file (thô, đã ẩn danh, input sinh ra, kết quả) nằm dưới
  `benchmarks/artifacts/real/`, thư mục đã có trong `.gitignore`. Báo cáo commit lên repo chỉ chứa số
  liệu tổng hợp và mã trường, không chứa bảng thời khóa biểu.
- **Không sửa product code** (`src/`). Công cụ chuyển đổi và chấm điểm là tooling mới ngoài Core, giống
  `benchmarks/`.
- **Không đoán quy tắc trường.** Cái gì không có trong DB được ghi là UNKNOWN, không tự điền.
- **Thang chấm chốt trước khi mở dữ liệu** (§5), để không chọn ngưỡng vừa khít lịch thật.
- **Chỉ đọc.** Không ghi gì vào DB công ty. Không kết nối DB production từ máy này; người dùng xuất file.

## 2. Dữ liệu cần lấy (định dạng)

Bước đầu, **trước khi xuất dữ liệu**: người dùng gửi **schema** (tên bảng, tên cột, kiểu, khóa ngoại)
của phần DB liên quan đến thời khóa biểu, không kèm dữ liệu. Tôi sẽ đối chiếu schema với bảng dưới đây và
viết câu truy vấn xuất cụ thể (RD2).

Mỗi trường, mỗi học kỳ, xuất CSV UTF-8 (hoặc Excel), một file cho mỗi bảng:

| File | Nội dung tối thiểu | Ánh xạ Core | Bắt buộc |
|---|---|---|---|
| `school.csv` | mã trường (đã ẩn danh), cấp học, năm học, học kỳ, số buổi học/ngày | `school` | Có |
| `periods.csv` | thứ, buổi, tiết, giờ bắt đầu/kết thúc (nếu có), tiết có dạy hay không | `time_slots` | Có |
| `classes.csv` | mã lớp, khối, buổi học chính | `classes` | Có |
| `teachers.csv` | mã GV (đã ẩn danh), tổ chuyên môn | `teachers` | Có |
| `subjects.csv` | mã môn, tên môn | `subjects` | Có |
| `assignments.csv` | lớp, môn, GV, số tiết/tuần, số tiết đôi (nếu DB có) | `teaching_requirements` | Có |
| `timetable.csv` | lớp, thứ, buổi, tiết, môn, GV, phòng (nếu có). Đây là **lịch trường đang dùng** | assignments của lịch thật | Có |
| `teacher_unavailable.csv` | GV, ô không thể dạy | `availability` (hard) | Nếu DB có |
| `fixed_lessons.csv` | chào cờ, sinh hoạt lớp, tiết khóa | requirement + `locked_assignments` | Nếu DB có |
| `rooms.csv` | phòng, loại phòng, môn cần phòng | `rooms`, `required_room_type` | Nếu DB có |
| `rules.csv` | quy tắc hoặc tham số xếp lịch phần mềm hiện tại đang dùng | tham khảo cho §5 | Nếu DB có |

Nên lấy cả **lịch đã công bố cuối cùng**, và nếu được, cả **lịch sau các lần sửa giữa kỳ** (để đánh giá
repair sau này).

Phạm vi lần đầu: **3–5 trường** khác nhau về cấp (THCS/THPT) và quy mô (nhỏ dưới 20 lớp, vừa 20–40,
lớn trên 40), một học kỳ mỗi trường (RD3). Đủ để thấy vấn đề mà không tốn công xử lý.

## 3. Ẩn danh hóa

- **Làm tại công ty, trước khi chép file ra.** Script `pseudonymize.py` (tooling mới, §6) thay:
  - tên GV → `GV001`, `GV002`… theo thứ tự ổn định trong từng trường;
  - tên và mã trường → `SCH01`, `SCH02`…;
  - xóa mọi cột cá nhân khác (ngày sinh, điện thoại, email, CCCD, địa chỉ).

  Mã lớp, tên môn và tên phòng giữ nguyên, vì chúng không định danh cá nhân và cần cho việc đọc kết quả.
- **Bảng đối chiếu mã ↔ tên chỉ nằm tại công ty**, không chép ra, không vào repo. Không dùng hash không
  khóa (dễ dò ngược từ danh sách tên): mã là số thứ tự, bảng đối chiếu giữ tại chỗ.
- Script tự kiểm sau khi chạy: không còn cột nào ngoài danh sách cho phép, và không ô nào khớp mẫu
  điện thoại, email hay CCCD. Có lỗi thì không xuất.
- Mỗi gói dữ liệu kèm `manifest.json`: SHA256 từng file, ngày xuất, phiên bản script. Không có tên thật.

## 4. Ánh xạ sang input Core

Công cụ `convert_real.py` đọc gói đã ẩn danh và tạo hai thứ:

- `input.json`: input 1.1, policy 0.4;
- `real-assignments.json`: lịch thật dưới dạng danh sách assignment (cùng kiểu `PreviousSchedule` của
  repair).

Quy tắc chuyển:

| Core | Từ | Ghi chú |
|---|---|---|
| `time_slots` | `periods.csv` | `id` = `thứ-buổi-tiết`; tiết không dạy → `can_teach = false` |
| `classes`, `teachers`, `subjects` | các bảng tương ứng | |
| `teaching_requirements` | `assignments.csv` | Mỗi dòng (lớp, môn, GV) là một requirement; `periods_per_cycle` = số tiết/tuần |
| `block_durations` | Số tiết đôi trong `assignments.csv`, nếu có. Nếu không có, **suy từ lịch thật** (RD4) | Hai tiết liền nhau cùng lớp, môn, GV trong một buổi là một block 2 tiết |
| `locked_assignments` | `fixed_lessons.csv` | Chào cờ, sinh hoạt: requirement riêng và khóa ô |
| availability của GV | `teacher_unavailable.csv` | Hard. Không có thì để trống (mọi ô dạy được) |
| phòng | `rooms.csv` | Lần đầu `manage_rooms = false`, trừ khi dữ liệu phòng đầy đủ (RD6) |
| lịch thật | `timetable.csv` | Mỗi ô (lớp, ô) → occurrence `requirement::i`, gán theo thứ tự thời gian; block 2 tiết → một occurrence |

**Đối chiếu nhất quán trước khi chấm** (lỗi dữ liệu khác với lỗi của lịch):

- Tổng số tiết trong lịch thật của mỗi (lớp, môn, GV) so với `periods_per_cycle`. Lệch thì ghi dòng đó,
  không tự sửa.
- Ô trong lịch thật có môn hoặc GV không có trong bảng phân công.

**Tính năng Core chưa hỗ trợ** (đồng giảng, lớp ghép, chia nhóm, block trên 2 tiết, tuần A/B):

- Bộ chuyển đếm và liệt kê từng trường hợp.
- Lần đầu: tách ra khỏi input, kèm danh sách rõ ràng (RD7), và báo cáo nêu tỉ lệ tiết bị loại.
- Không giả lập tính năng mà Core chưa có.

## 5. Thang chấm chung (chốt trước khi mở dữ liệu, RD5)

DB có thể không lưu nguyện vọng của GV, nên chấm theo một **thang đo chung**: tập rule soft với tham số
lấy từ quy định và thông lệ đã khảo sát
([phiếu trả lời tham khảo](../../school-questionnaire-reference-answers-draft.md)), không lấy từ dữ liệu.
Cả lịch thật và lịch Core đều chấm bằng thang này.

| Rule | Tham số | Priority | Nguồn |
|---|---|---|---|
| S06 môn/lớp/ngày | ≤ 2 tiết | P1 | Câu 21 (thông lệ) |
| S02 tải GV/buổi | ≤ 4 tiết | P1 | Bảng nguyện vọng (thông lệ) |
| S03 tải GV/ngày | ≤ 5 tiết | P2 | Bảng nguyện vọng (thông lệ) |
| S09 chuỗi tiết trống của GV | ≤ 1 | P2 | Bảng nguyện vọng (thông lệ) |
| S05 giãn ngày giữa các tiết cùng môn | `min_day_gap = 1` | P2 | Đề xuất |
| S08 tổng tiết trống, S11 buổi chỉ một tiết | không ngưỡng | P3 | Chỉ ghi nhận |

- Mỗi rule là một instance cho mỗi GV (hoặc toàn trường với S06), weight 1, đúng cách dataset v2.
- Thang này **không phải quality profile**. Nó chỉ là thước đo để so lịch thật với lịch Core. Lịch thật
  vi phạm thang này không có nghĩa trường làm sai, vì trường có thể không đặt các quy tắc đó.
- Nếu `teacher_unavailable.csv` hoặc `rules.csv` có dữ liệu thật, chúng được thêm thành hard hoặc soft
  theo đúng nghĩa trong DB. Báo cáo tách riêng kết quả có và không có chúng.

## 6. Công cụ và cách chấm

Tooling mới, đặt trong `tools/real_data/` (ngoài `src/`), có test với dữ liệu giả nhỏ. Không có dữ liệu
thật trong test.

| File | Việc |
|---|---|
| `pseudonymize.py` | §3; chạy tại công ty |
| `convert_real.py` | §4; ra `input.json`, `real-assignments.json`, `conversion-report.json` (lệch, tính năng chưa hỗ trợ, số tiết bị loại) |
| `score_real.py` | Gọi thẳng `validate_schedule` và `evaluate_score` (hàm độc lập, không dùng solver) trên lịch thật. Không dựng giả kết quả solver |
| `compare_real.py` | Chạy `tkb_core.cli solve` trên cùng `input.json` (budget theo quy mô 60/120/180 s, 1 worker, seed 42), chạy `validate-schedule` và `evaluate-score` độc lập, rồi so với lịch thật |

**Mỗi trường được báo cáo:**

- **Đọc được:** số lớp, GV, requirement và tiết; số dòng lệch; tỉ lệ tiết bị loại vì tính năng chưa hỗ
  trợ.
- **Lịch thật:** hard có hợp lệ không (nếu không, là lỗi dữ liệu hay xung đột thật); vector `[P1,P2,P3]`
  và breakdown theo rule; GV có nhiều vi phạm nhất (mã).
- **Lịch Core:** status, thời gian, RSS, hard có hợp lệ không, vector và breakdown.
- **So sánh:** từng rule, Core tốt hơn, bằng hay kém lịch thật. Không cộng các tier thành một số; so theo
  thứ tự từ điển và theo từng rule.

**Không làm trong lần đầu:**

- Không chỉnh tham số solver theo dữ liệu thật.
- Không chạy repair, trừ khi có lịch sửa giữa kỳ và RD8 đồng ý.
- Không chạy campaign lặp; mỗi trường chạy n = 1, và nói rõ trong báo cáo.

## 7. Các bước và ranh giới phê duyệt

| Bước | Việc | Ai làm | Cần duyệt riêng |
|---|---|---|---|
| A | Duyệt kế hoạch, RD1–RD9 | Người dùng | Có (lượt này dừng ở đây) |
| B | Gửi schema DB (không dữ liệu) | Người dùng | — |
| C | Đối chiếu schema, viết truy vấn xuất và `pseudonymize.py` (TDD) | Tôi | Có |
| D | Xuất và ẩn danh tại công ty; chép gói sang máy chạy | Người dùng | — |
| E | Viết `convert_real.py`, `score_real.py`, `compare_real.py` (TDD với dữ liệu giả) | Tôi | Có |
| F | Chạy trên 3–5 trường | Tôi | Có |
| G | Báo cáo tổng hợp (không có dữ liệu định danh), đề xuất hướng tiếp | Tôi | Có, khi commit |

Bước C và E có thể làm song song với B và D. Một trường 40 lớp chạy Core khoảng 3 phút, nên bước F chỉ
khoảng 15–30 phút máy.

## 8. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Lộ dữ liệu cá nhân | Ẩn danh tại công ty; bảng đối chiếu không ra khỏi công ty; kiểm tự động; dữ liệu chỉ dưới đường dẫn gitignore |
| Schema DB khác nhiều so với dự kiến | Bước B (xem schema trước) |
| DB không có số tiết đôi hay ô không thể dạy | Suy từ lịch thật (RD4) hoặc ghi UNKNOWN; báo cáo nói rõ |
| Lịch thật không hợp lệ hard theo Core | Phân loại: lỗi chuyển đổi, lỗi dữ liệu, hay quy tắc trường khác Core. Không "sửa" lịch thật |
| Nhiều trường dùng đồng giảng hoặc chia nhóm, Core chưa hỗ trợ | Đếm tỉ lệ; nếu lớn, đó là ưu tiên tính năng trước Phase 4 |
| Thang chấm §5 không phản ánh điều trường quan tâm | Thang chỉ để so sánh; profile v1 cần câu trả lời §13 từ trường |
| Suy block từ lịch thật làm lợi cho lịch thật | Ghi rõ nguồn block cho từng trường; ưu tiên dữ liệu tiết đôi trong DB |

## 9. Quyết định cần duyệt

- [ ] **RD1 — Quyền dùng dữ liệu:** người dùng xác nhận được phép dùng thời khóa biểu từ DB công ty cho
  mục đích này, theo quy định nội bộ. *(Người dùng xác nhận.)* **Chờ xác nhận; chưa xử lý dữ liệu thật
  nào trước khi có RD1.**
- [x] **RD2 — Xem schema trước:** gửi schema (không dữ liệu) để tôi viết truy vấn xuất, thay vì xuất cả
  DB. *(Đề xuất: chọn.)*
- [x] **RD3 — Phạm vi lần đầu:** 3–5 trường khác cấp và quy mô, mỗi trường một học kỳ. *(Đề xuất:
  chọn.)*
- [x] **RD4 — Block khi DB không có số tiết đôi:** suy từ lịch thật và ghi rõ. *(Đề xuất: chọn.
  Phương án khác: mọi tiết là tiết đơn.)*
- [x] **RD5 — Thang chấm chung §5,** chốt trước khi mở dữ liệu. *(Đề xuất: chọn các tham số trong
  bảng.)*
- [x] **RD6 — Phòng:** lần đầu không quản lý phòng, trừ khi dữ liệu phòng đầy đủ. *(Đề xuất: chọn.)*
- [x] **RD7 — Tính năng chưa hỗ trợ:** lần đầu tách khỏi input và báo cáo tỉ lệ, không mở rộng Core.
  *(Đề xuất: chọn.)*
- [x] **RD8 — Repair:** không chạy trong lần đầu; xét lại khi có lịch sửa giữa kỳ. *(Đề xuất: chọn.)*
- [x] **RD9 — Vị trí:** tooling trong `tools/real_data/`, dữ liệu dưới `benchmarks/artifacts/real/`
  (gitignore). Báo cáo chỉ có số liệu tổng hợp và mã trường. *(Đề xuất: chọn.)*

## 10. Kiểm tra khi soạn

- Đối chiếu field của `ScheduleInput`, `TimeSlot`, `TeachingRequirement`, `LockedAssignment`
  (`src/tkb_core/contracts/input.py`, `src/tkb_core/domain/models.py`) và cách đặt mã occurrence
  `requirement::i` (`src/tkb_core/preprocessing/normalize.py`).
- `validate-schedule` và `evaluate-score` qua CLI đòi một `ScheduleResult` có fingerprint
  (`src/tkb_core/cli.py`). Vì vậy `score_real.py` gọi thẳng hai hàm độc lập trên assignment của lịch
  thật, không dựng giả kết quả solver.
- `/benchmarks/artifacts/` có trong `.gitignore`.
- Bảng §2 đối chiếu với phần B của [phiếu khảo sát](../../school-questionnaire-draft.md); tham số §5 lấy
  từ [phiếu trả lời tham khảo](../../school-questionnaire-reference-answers-draft.md).
- Không truy cập DB, không chạy code; không sửa file nào khác.
