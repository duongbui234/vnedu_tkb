# Đọc collection API vnEdu và tác động tới Scheduling Core

Ngày: 2026-10-25. Nguồn: [stkb (s19).postman_collection.json](<../stkb (s19).postman_collection.json>). Báo cáo này ghi lại bước đọc file ban đầu. Sau đó đã gọi API đọc theo cho phép của người dùng; xem [kết quả kiểm chứng trực tiếp](vnedu-api-live-findings.md). Các UNKNOWN bên dưới mô tả tình trạng tại bước đọc file, được cập nhật bởi báo cáo live. Không thay đổi collection.

## 1. Những gì đã xác nhận trong file

**VERIFIED — cấu trúc collection:** Postman collection v2.1, 21 request; 14 request nhóm API hiện có và 7 request nhóm lọc phân hiệu/điểm trường. Cả 21 request có mảng saved responses rỗng. Không có response schema/example để xác nhận kiểu dữ liệu và các field bắt buộc của record phân công.

**VERIFIED — mô tả trong collection:** có các ghi chú về hành vi API cũ/mới, deployment và dữ liệu thật. Những ghi chú này là tài liệu người dùng cung cấp; **UNKNOWN:** server hiện tại có đúng hành vi đó không, nhóm New đã deploy chưa, response/error thực tế ra sao. Không thực hiện các hướng dẫn deploy/xóa cache trong description.

## 2. Inventory theo vai trò

Mọi tên `call`, HTTP method và query/body dưới đây được xác nhận từ file. Vai trò nghiệp vụ lấy từ tên/mô tả; chưa xác minh response runtime.

| Nhóm | call trong collection | Method | Tác dụng đối với ứng dụng |
|---|---|---|---|
| Xác thực | `thoikhoabieu.dangnhap` | GET | Xác định ngữ cảnh trường; không in/log các query chứa credential |
| Trường | `thoikhoabieu.getThongTinTruongHoc` | GET | Metadata trường; không dùng thông tin hạn dịch vụ làm ràng buộc xếp lịch |
| Lớp | `thoikhoabieu.getDanhSachLopHoc`, `getDanhSachLopHocNew` | GET | Resource lớp; bản New được mô tả có thông tin điểm trường |
| Môn | `thoikhoabieu.getDanhSachMonHoc`, `getDanhSachMonHocNew` | GET | Danh mục môn; không coi mọi ID âm là demand dạy học thông thường |
| Giáo viên | `thoikhoabieu.getDanhSachGiaoVien`, `getDanhSachGiaoVienNew` | GET | Resource giáo viên, phải dùng ID thống nhất xuyên điểm trường |
| Phân công | `thoikhoabieu.getPhanCongChuyenMon`, `getPhanCongChuyenMonNew` | GET | Nguồn liên kết lớp–môn–giáo viên; chưa biết field định mức tiết từ response |
| Điểm trường | `thoikhoabieu.getDanhSachDiemTruong` | GET | Đơn vị/cơ sở; chưa có thời gian di chuyển hay calendar từ request này |
| Tổ chuyên môn | `thoikhoabieu.getDanhSachToBoMon`, `getDanhSachToBoMonNew` | GET | Tổ/nhóm giáo viên; không tự suy thành lịch họp cố định |
| Giáo viên theo tổ | `thoikhoabieu.getGiaoVienByToBoMon`, `getGiaoVienByToBoMonNew` | GET | Scope danh sách giáo viên; chưa phải availability |
| Danh sách TKB | `thoikhoabieu.getDSThoikhoabieu` | GET | Tìm phiên bản/file TKB đã có |
| Tải file | `thoikhoabieu.downloadFile` | GET | Mô tả nói trả file trực tiếp; chưa có sample để xác định format |
| Tạo TKB | `thoikhoabieu.uploadFile` | POST multipart | Ghi dữ liệu; body có file key `file_upload`, chưa có file mẫu |
| Cập nhật TKB | `thoikhoabieu.updateTkb` | POST multipart | Ghi dữ liệu; query dùng `hoc_ky_id`, khác tên `hocKy` ở các request khác |
| Xuất dữ liệu TKB | `thoikhoabieu.uploadTkbData` | POST multipart | Mô tả nói đẩy TKB đã xếp về hệ thống; không tự coi format giống uploadFile |
| Xóa TKB | `thoikhoabieu.deleteTkb` | **GET** | Thao tác ghi/xóa dù dùng GET; tuyệt đối không phân loại read-only chỉ theo method |

Điểm tra cứu trong JSON: login dòng 14; phân công cũ dòng 219; upload dòng 263; download dòng 310; danh sách TKB dòng 347; xóa dòng 383; uploadTkbData dòng 415; update dòng 462; nhóm điểm trường dòng 608; phân công New dòng 796. Số dòng thuộc file hiện tại.

## 3. Các lưu ý trực tiếp cho adapter và mô hình

| Thông tin được ghi trong collection | Bằng chứng file | Đề xuất xử lý — INFERRED |
|---|---|---|
| `mon_hoc_id = -2` là dòng chủ nhiệm | Description request phân công cũ, dòng 219 | Tách chủ nhiệm khỏi demand môn thường. Không xóa luôn thông tin chủ nhiệm; cần để gắn sinh hoạt/hoạt động khi có quy tắc xác nhận. Không suy ra mọi ID âm đều cùng loại |
| API môn có môn hệ thống ID âm; `count` cũ có thể nhỏ hơn `aRoot.length`; start/limit có thể bị bỏ qua | Description danh mục môn, dòng 134; bản New dòng 699 | Không lấy `count` làm điều kiện đủ để dừng mọi parser/paginator; xử lý riêng contract từng endpoint, deduplicate theo ID và kiểm tra coverage |
| API giáo viên cũ bỏ qua `namHoc`; bản New được mô tả có xét năm học | Description dòng 174 và 745 | Ưu tiên bản New **sau khi xác minh**. Không trộn teacher của năm hiện tại với phân công một năm khác mà vẫn coi snapshot hợp lệ |
| Bộ New có `diemTruongId` nhưng filter đang disabled | Query và description nhóm B | Tôn trọng disabled state khi đọc collection. Chỉ bật lọc khi scope job được chọn rõ, không coi tham số xuất hiện là đang có hiệu lực |
| New teacher list được mô tả bao gồm giáo viên có phân công/chủ nhiệm ở lớp của đơn vị | Description dòng 745 | Kiểm tra referential integrity: mọi GV được phân công phải có trong danh mục đã tải; không chỉ tin vào ghi chú |
| Lớp New có thông tin điểm trường; 0 là chưa gán | Description dòng 643 | Giữ trạng thái chưa biết/chưa gán; không tự gán cơ sở chính hoặc đoán vị trí vật lý |
| Tổ bộ môn New vẫn có scope cả trường; chỉ thành viên được lọc | Description dòng 846 | Không suy scope của mọi endpoint giống nhau chỉ vì chúng nhận cùng diemTruongId |
| Danh sách TKB có `object[0]` là chuỗi JSON | Description dòng 347 | Decoder theo endpoint, validate envelope trước rồi parse chuỗi nếu đúng kiểu; không áp dụng double-parse cho tất cả response |
| Một số endpoint trả mảng trực tiếp hoặc file thay vì aRoot | Description tổ bộ môn và download | Tách decoder danh mục/array/file; không tạo một hàm unwrap giả định duy nhất |
| Collection cảnh báo New có thể trả 200 với body rỗng khi method chưa deploy | Description cấp collection | Empty body là capability/data error chưa xác định, không phải thành công với danh sách 0. Không tự fallback cũ nếu làm sai năm học/scope |
| upload/update/export đều multipart file_upload, chưa có file mẫu | Request 7/11/12 | Có route ghi chưa đủ để triển khai sync. Cần biết định dạng, field mapping, cách replace/merge và response lỗi trước khi tạo payload |

**UNKNOWN:** các lỗi/hành vi được ghi chú còn tồn tại trên server hiện tại hay không. Không sửa API hoặc tự chọn một biến thể endpoint như thể đã được kiểm thử.

## 4. Điều chỉnh kết luận đối chiếu STKB/FET

**INFERRED:** collection đã giúp chốt được **đường lấy danh mục và phân công**, cùng ranh giới trường/năm/học kỳ/điểm trường. Chưa đủ để encode chính xác demand và đồng bộ kết quả.

- **C01 đủ phân công:** lấy từ PCGD; tách dòng chủ nhiệm -2. Chưa biết field nào là số tiết/tuần, field nào chỉ định mức/năm hoặc thông tin phụ.
- **C02 giáo viên không trùng:** một teacher ID phải giữ thống nhất giữa các điểm trường. Chạy riêng từng cơ sở có thể làm trùng giáo viên dùng chung; phải có chung horizon/occupancy hoặc lịch bận từ các scope liên quan.
- **C03 lớp:** lớp và điểm trường cần map đúng theo scope đã tải. Không suy lớp ghép/atomic student groups từ danh sách lớp thường.
- **C04/C09 phòng:** chưa thấy endpoint danh mục phòng trong 21 request. Đây là khoảng thiếu của collection, không chứng minh vnEdu không có dữ liệu phòng. Nếu cần xếp phòng, phải bổ sung nguồn dữ liệu; nếu chưa xếp phòng, ghi rõ phạm vi này.
- **C05/C08 lịch và block:** chưa thấy API khung ngày/buổi/tiết hoặc tiết đôi. Cần dữ liệu từ nguồn khác hoặc cấu hình local, không đoán dựa trên STKB/FET.
- **C06/C10–C20 ràng buộc:** chưa thấy endpoint availability, họp, giới hạn tải, preference, travel time hoặc room equipment. Danh sách tổ chuyên môn không tự cung cấp giờ họp.
- **C07/C22 incumbent/khóa:** có list/download TKB nhưng format chưa xác minh. Lịch hiện có không đồng nghĩa toàn bộ lesson đều bị khóa; cần chính sách khóa local rõ ràng.
- **C21 chủ nhiệm/sinh hoạt:** record chủ nhiệm là đầu mối dữ liệu, chưa chứng minh số tiết hoặc giờ sinh hoạt cố định. Không tự sinh thêm một tiết/tuần chỉ từ mã -2.

Liên hệ: [ma trận 22 ràng buộc](stkb-fet-vnedu-comparison.md). Các nhận định ở báo cáo cũ rằng chưa có adapter/schema vẫn đúng ở mức implementation/response schema; nay đã có collection request và mô tả để định hướng tiếp.

## 5. Các phần còn thiếu để chốt contract

**VERIFIED:** description dẫn tới `docs/api.md` và `docs/chay-local-voi-db-product.md`, nhưng hai file này không có ở đường dẫn tương ứng trong workspace lúc đọc. Không coi nội dung của chúng là đã được cung cấp.

Ưu tiên đọc tiếp khi có dữ liệu:

1. Response thành công và lỗi của lớp, môn, giáo viên, PCGD và điểm trường, ưu tiên đúng nhóm endpoint đã deploy. Mẫu đã ẩn tên/thông tin cá nhân vẫn phải giữ tên field, kiểu và quan hệ ID.
2. Trong PCGD: cách biểu diễn số tiết/tuần, học kỳ/năm, chủ nhiệm, môn đặc biệt, lớp ghép và đồng giảng nếu có. Đây là phần trực tiếp quyết định C01.
3. Response list TKB, một file download mẫu và định dạng file được upload/update/uploadTkbData chấp nhận; xác định ba tuyến có chung format hay không.
4. Nguồn khung thời gian, availability, phòng và rule của trường: API khác hay cấu hình local. Không yêu cầu collection phải có những endpoint vốn không phục vụ các dữ liệu này.

Bước đọc contract ban đầu không gọi network. Bước kiểm chứng tiếp theo đã gọi API đọc: xem [kết quả live](vnedu-api-live-findings.md), gồm field `so_tiet` toàn 0 và 5 dòng thiếu tham chiếu GV. Chưa thực hiện thao tác tạo, cập nhật, export hoặc xóa.
