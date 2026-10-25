# Kiểm chứng API đọc vnEdu bằng collection

Ngày kiểm tra: 2026-10-25 (Asia/Ho_Chi_Minh). Phạm vi: trường/năm học/học kỳ có sẵn trong [collection](<../stkb (s19).postman_collection.json>), sau khi người dùng cho phép gọi API lấy dữ liệu. Kết quả là snapshot tại thời điểm kiểm tra, không bảo đảm mọi năm học/trường có cùng hành vi.

## Phạm vi và bằng chứng

**VERIFIED:** đã gọi đăng nhập một lần và các tuyến đọc theo allowlist tên `call`. Không gọi `uploadFile`, `updateTkb`, `uploadTkbData`, `deleteTkb`; đặc biệt `deleteTkb` dùng GET vẫn bị loại. Không sửa collection hoặc cấu hình server. Không chạy script Postman. Không lưu raw response, mật khẩu, token hay giá trị thông tin cá nhân vào các bằng chứng mới.

Bằng chứng lưu cấu trúc/kiểu dữ liệu và số lượng:

- [Schema của 14 request đầu](vnedu-api-live-schema.json): một request đăng nhập và 13 request đọc, gồm API cũ/New, trường, điểm trường, tổ bộ môn và danh sách TKB.
- [Đối chiếu dữ liệu và điểm trường](vnedu-api-live-observations.json): 12 request đọc bổ sung; kiểm tra khóa tham chiếu, số tiết, trùng phân công và scope điểm trường.
- [Kiểm tra định dạng danh sách TKB](vnedu-api-timetable-format.json): một request đọc bổ sung; không trích được JSON envelope hoàn chỉnh bằng JSON decoder.

Tổng cộng 27 request: một đăng nhập và 26 lượt đọc. Login trả HTTP 200, `success:false`; không đoán mật khẩu hoặc thử đăng nhập lại. Các API đọc dùng nguyên ngữ cảnh trường có sẵn trong collection vẫn trả `success:true`. **UNKNOWN:** nguyên nhân login thất bại và chính sách xác thực server; thành công của request đọc không chứng minh đăng nhập đã thành công.

## Danh mục và phân công

**VERIFIED — nhóm New, toàn trường:**

| Dữ liệu | Số record trả về | Kiểu đáng chú ý |
|---|---:|---|
| Lớp | 38 | `id`, `nam_hoc`, `khoi`, `diem_truong_id` là chuỗi |
| Giáo viên | 109 | Có cả `gv_id` và `giao_vien_id`, đều chuỗi |
| Môn | 20 | `id`, `stt`, `khoi_hoc` là chuỗi |
| Phân công chuyên môn | 527 | Toàn bộ sáu field bên dưới là chuỗi |
| Điểm trường | 2 | `id`, `type`, `dtc`, `parent_id` là chuỗi; `so_lop` là số nguyên |

Các danh mục/PCGD New nằm trong `object[0].aRoot`. Giá trị `count` sau chuyển số khớp số record trả về trong bốn bộ lớp/GV/môn/PCGD; không suy ra mọi API đều phân trang đúng. `count` lớp/GV là chuỗi, môn/PCGD là số nguyên. Bộ cũ cũng trả 38 lớp, 109 GV, 20 môn, 527 phân công trong snapshot này; không chứng minh chúng xử lý năm học giống New.

Field PCGD xác nhận từ response:

```text
gv_id: string
giao_vien_id: string
hoc_ky: string
mon_hoc_id: string
so_tiet: string
lop_id: string
```

**VERIFIED:** cả 527 dòng có `so_tiet`, đều là chuỗi `"0"`. Không có giá trị trống hoặc không phải số; cũng không có dòng nào có số tiết dương. **UNKNOWN:** lý do bằng 0, nguồn định mức tiết thật và đơn vị tuần/học kỳ/năm. Không diễn giải 0 thành không cần xếp và không tự áp số tiết chương trình.

**VERIFIED:** không có khóa trùng `(lop_id, mon_hoc_id, gv_id, giao_vien_id, hoc_ky)`. Toàn bộ tham chiếu lớp/môn tồn tại. Có 5 dòng không tìm được giáo viên trong danh mục trả về khi đối chiếu riêng theo `gv_id`, và cũng 5 dòng khi đối chiếu riêng theo `giao_vien_id`. Đây là số dòng tham chiếu, không phải số giáo viên duy nhất. **UNKNOWN:** đó là phân công chưa gán, mã đặc biệt hay thiếu danh mục; không tự tạo giáo viên thay thế.

**VERIFIED:** 38 dòng phân công có `mon_hoc_id=-2`; không có mã môn âm khác trong PCGD snapshot. **VERIFIED — tài liệu collection:** -2 là chủ nhiệm. **INFERRED:** giữ record này riêng, không tự chuyển thành 38 tiết sinh hoạt hoặc demand môn thông thường.

## Điểm trường và tổ bộ môn

**VERIFIED:** bật tham số `diemTruongId` với từng ID trong response danh mục điểm trường trả:

| Scope | Lớp | GV | PCGD | PCGD thiếu tham chiếu GV |
|---|---:|---:|---:|---:|
| Điểm trường thứ nhất | 21 | 60 | 288 | 5 |
| Điểm trường thứ hai | 17 | 48 | 239 | 0 |

Trong hai scope, không có lớp ngoài điểm trường yêu cầu, không có PCGD thiếu tham chiếu lớp. Tổng lớp/PCGD khớp toàn trường; tổng GV hai scope là 108 trong khi toàn trường là 109. **UNKNOWN:** ý nghĩa đầy đủ của chênh lệch teacher coverage; chưa chứng minh giao của hai tập GV hoặc giáo viên không có phân công. Không dùng tổng này để khẳng định hai điểm trường độc lập.

**VERIFIED:** tổ bộ môn cũ/New đều trả 11 phần tử trực tiếp trong `object`, không theo `aRoot`. Tổ đầu tiên có danh sách `mon_hoc` rỗng ở bản cũ và 4 phần tử ở New. Đây là khác biệt quan sát được, chưa kết luận nguyên nhân hoặc mọi tổ đều sai ở bản cũ.

## Các phần chưa dùng được

**VERIFIED:** `getDSThoikhoabieu` trả HTTP 200, body 2829 byte nhưng không parse được bằng JSON decoder chuẩn. Có marker `"success"`, không thấy HTML doctype hay marker PHP notice trong phép kiểm tra giới hạn. Lần chẩn đoán tiếp theo không tìm được envelope hoàn chỉnh. **UNKNOWN:** nguyên nhân/định dạng chính xác; không gọi đó là danh sách rỗng hay login thành công/thất bại chỉ dựa trên HTTP 200.

Ở bước kiểm tra ban đầu chưa tải file TKB vì chưa có danh sách/file ID hợp lệ. Sau đó người dùng cung cấp danh sách; đã tải thành công như phần bổ sung dưới đây. Chưa gọi giáo viên theo tổ, chưa xác minh phòng, availability, khung tiết, giờ di chuyển hay định dạng upload. Không có thử nghiệm ghi/xóa.

## Tác động tới đối chiếu STKB/FET và Scheduling Core

**INFERRED — đề xuất từ dữ liệu thật:**

1. Đã có nguồn danh mục và liên kết lớp–môn–GV; ưu tiên New có thông tin điểm trường, nhưng vẫn validate schema và quan hệ ID mỗi snapshot.
2. Chưa đạt điều kiện nhập solver: C01 còn thiếu nhu cầu tiết dương và C02 còn 5 dòng tham chiếu GV chưa giải thích. Chặn tạo job kèm lỗi theo dòng; không âm thầm bỏ dòng hoặc coi toàn bộ lịch rỗng là nghiệm hợp lệ.
3. Chuẩn hóa ID dạng chuỗi, giải mã envelope theo endpoint, kiểm tra `success` và body thay vì chỉ HTTP status/content type. Không tự xem trường vắng mặt là danh sách rỗng.
4. Ràng buộc không trùng GV xuyên điểm trường vẫn cần occupancy chung như phân tích STKB/FET; scope API là bộ lọc dữ liệu, không chứng minh các bài toán độc lập.
5. Muốn sửa một phần/khóa lịch theo kỹ thuật FET và STKB, cần đọc được incumbent từ file TKB; hiện phần này chưa đủ contract. Không triển khai solver, adapter hoặc giao diện trong lượt kiểm tra này.

## Bổ sung: tải file STKB từ danh sách người dùng cung cấp

**VERIFIED — thử nghiệm:** dùng tám `file_id` trong response do người dùng cung cấp, gọi đúng `GET thoikhoabieu.downloadFile` theo collection. Cả tám trả HTTP 200, `application/octet-stream`; đã lưu tổng 4.065.503 byte và kiểm tra lại SHA-256 sau ghi. Không gọi tuyến ghi/xóa. Response danh sách người dùng dán không được coi là chứng minh body API có JSON chuẩn: phép kiểm tra trước vẫn ghi nhận lỗi parse.

File nằm tại [thư mục tải](../../reverse-engineering/downloads/vnedu-tkb/); [manifest](../../reverse-engineering/downloads/vnedu-tkb/manifest.json) ghi từng file ID, tên gốc, đường dẫn, dung lượng, hash và thời điểm tải. Tên local có tiền tố file ID để tránh đè file trùng tên. `TKB199.STKB` và `DOT2.STKB` có cùng SHA-256; giữ cả hai theo danh sách nguồn.

**VERIFIED — xác nhận của người dùng:** đây là các file dữ liệu STKB sử dụng và collection là các API STKB 5.0 đang dùng. Đây là nguồn xác nhận từ người dùng; chưa phải bằng chứng quan sát network của process STKB.

**UNKNOWN:** định dạng nội bộ và mapping record của file. Công cụ `file` chỉ nhận dạng là `data`; chưa giải mã, chưa mở bằng STKB, chưa xác minh có chứa số tiết thật, ràng buộc hoặc incumbent đầy đủ. Nguồn này cho phép nghiên cứu tiếp đối chiếu serializer/deserializer STKB với response API; chưa triển khai solver hoặc adapter.

**Cập nhật sau phân tích tĩnh:** đã đọc phần danh mục của tám file và xác nhận ID lớp/môn/GV với ba API New; xem [báo cáo định dạng lượt 1](../../reverse-engineering/reports/STKB-file-format-analysis.md). Số tiết, record lịch và ngữ nghĩa block ràng buộc vẫn chưa xác minh; chưa coi parser là bộ đọc đầy đủ.
