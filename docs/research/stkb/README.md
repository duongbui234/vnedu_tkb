# STKB × FET × vnEdu — nghiên cứu nghiệp vụ và Scheduling Core

Ngày 2026-10-26. Tiếp nối nghiên cứu trước, không nghiên cứu lại từ đầu. Core đối chiếu tại commit `7f58f710a9901fe2c0457573feaad272e713d7a1`; không thay đổi implementation.

## Đọc kết quả

1. [Nguồn số tiết và bằng chứng binary](01-demand-provenance.md).
2. [Độ phủ nghiệp vụ và các phần chưa xác minh](02-business-coverage.md).
3. [Gap Analysis với Phase 1](03-phase1-gap-analysis.md).
4. [Kiến trúc đề xuất](04-proposed-architecture.md).
5. [Roadmap và tiêu chí hoàn thành](05-roadmap.md).
6. [30 hệ số khởi tạo và 15 selector thuộc tính môn STKB](06-score-defaults.md).
7. [Khôi phục demand và lịch chính từ tám file — kết quả mới nhất](07-file-demand-recovery.md).
8. [Đọc hết suffix, map ràng buộc và khóa tiết — cập nhật mới nhất](08-suffix-constraints-and-locks.md).
9. [Bộ hard/soft đề xuất vnEdu — policy0.1 và thứ tự triển khai](09-vnedu-hard-soft-policy.md).

**VERIFIED**: xác nhận điều cụ thể từ source, byte/assembly, file hoặc API snapshot. **INFERRED**: suy luận/đề xuất từ bằng chứng. **UNKNOWN**: chưa đủ bằng chứng. VERIFIED tài liệu chỉ xác nhận tài liệu nói gì; không thay cho kiểm thử phần mềm. Phân loại này độc lập với nhãn độ phủ full/partial/absent/change-required/unknown của Core.

## Kết luận quan trọng

- **VERIFIED — tài liệu và resource binary:** STKB có bảng số tiết chuẩn, giao diện sửa và bộ chuẩn 2B riêng. Tài liệu mô tả mặc định theo môn/khối/chương trình/buổi, override từng lớp và lựa chọn có lan truyền thay đổi sang PCGD hay không. Xem D1–D4/B1–B3 ở báo cáo 01.
- **VERIFIED — binary, phạm vi một nhánh:** PCGD JSON có `so_tiet` được đọc vào staging; đường chuyển staging sang bảng xếp tại vùng `0x6a3c30–0x6a4183` lấy số từ bảng chuẩn nội bộ và thay số tra bằng 0 thành 1. Không có căn cứ để dùng fallback này cho sản phẩm mới hoặc mọi nhánh STKB.
- **VERIFIED — API snapshot:** 527 PCGD đều có chuỗi `so_tiet="0"`; ngữ nghĩa/đơn vị trường này vẫn **UNKNOWN**. Không ánh xạ thẳng sang demand đã xác nhận.
- **VERIFIED — binary:** đã nối 30 getter tính điểm với 30 trường hệ số khởi tạo trong constructor `CAlgAutoSFNew(CWnd*, int)`, có đối chiếu assembly. Chưa đồng nghĩa mọi mã ràng buộc/default runtime hoặc mọi engine đều đã được giải mã.
- **VERIFIED — source FET:** demand/components được tạo trước generator. FET dùng recursive swapping, không phải CP-SAT; weight FET không tương đương trọng số CP-SAT.
- **INFERRED:** ưu tiên tiếp theo là đặc tả dữ liệu định mức có nguồn gốc + completeness gate, rồi mở rộng rule/quality/repair trên Phase 1. Không cần viết lại nền feasibility đang có.

## Danh tính và độ tin cậy

STKB.exe SHA-256 `29fee192c60d2bd009103713bf22441b418a7b872d2087443551b2bdff4e6525`, native PE32 x86. PE VERSIONINFO tại file offset `5204232`: file/product version **4.5.0.0**. Help mang các mục STKB 5.0 nhưng giữ nội dung nhiều bản cũ; version resource không đủ kết luận phần mềm là bản giả/cũ, và tên thư mục không chứng minh mọi hướng dẫn áp dụng đúng binary. Dùng hash để định danh.

FET 7.12.0: bản nguồn đã có, danh tính/license/nguồn chính thức tại [FET source overview](../fet/01-source-overview.md). Không tải lại, không sao chép implementation FET/STKB vào Core.

Bằng chứng đầy đủ giữ local trong `reverse-engineering/reports/full-study/` (được `.gitignore` bảo vệ), gồm REA Evidence JSON, pseudocode, objdump, bản đồ PE resources, corpus help và các báo cáo chi tiết. API collection/file thực cũng không đưa vào Git. Những báo cáo Markdown này chỉ chứa phân tích, mã vị trí và số liệu tổng hợp.

## Phạm vi thực sự hoàn thành / chưa hoàn thành

Đã mở rộng nghiên cứu sang toàn bộ nhóm nghiệp vụ phục vụ scheduling: init, danh mục, chuẩn/override, PCGD, lịch/buổi/tuần, ràng buộc, phòng/địa điểm, solve, sửa/khóa, phiên bản và đồng bộ. Có ma trận độ phủ và kiến trúc đề xuất.

**Cập nhật sau khi tiếp tục:** demand và primary timetable của cả8file đã khôi phục, đối chiếu từng phân công và lịch lớp/GV0lỗi; xem báo cáo07. Kết luận “chưa đọc được demand/lịch” ở các báo cáo cũ là trạng thái lịch sử.

**Cập nhật báo cáo08:** đã đọc đúngEOF của8file, map slotconstraint997/998/999 và nhóm mãHọp1000..1006, cờ khóaslot, max tảiGV và khung tiết; xác định classDataBase/DataS10 cùng compatibilityswitch tĩnh. Probe suffix cũ đã sửa lỗi đếm số buổiRAD, không còn blocker vượtEOF.

**UNKNOWN:** ngữ nghĩa mọi field/cấu hình kế thừa, hai view phụ, tên mọi legacyselector, auto-lock theo đối tượng và runtimeWindows. Savedplans có dữ liệu/phòng có dữ liệu chưa được đối chứng. Không tuyên bố đã dịch ngược toàn bộ mọi lệnh của ứng dụng. Không phân tích kích hoạt/bản quyền, không chạy EXE/DLL, không gọi API ghi/xóa, không sửa Core.

## Kiểm chứng lượt tiếp tục

**VERIFIED thử nghiệm helper:** parser resource đọc292strings/294dialogtemplates, xác nhận tên dialog162/163; mapper kiểm30getter và15selector bằng assembly; reader prefix chạy trên8file thực, hashkhớpmanifest;26relativeMarkdownlinks hợp lệ. SHA-256 EXE không đổi, `git diff -- src tests pyproject.toml uv.lock` rỗng. Chưa chạy lại pytestCore hoặc benchmarkWindows trong lượt nghiên cứu này.

REA đã export47Evidence records và đóng binary; hồ sơ chi tiết/bước tiếp theo ở local `reverse-engineering/reports/full-study/PROGRESS.md`. Snapshot Evidence không phải database Hopper; không hứa sẽ tự khởi chạy khi quota reset.

**Kiểm chứng bổ sung báo cáo07:**5synthetictests pass;8file thực demand conservation theo từng phân công và primaryclass/teacher mirror0issues;8hashkhôngđổi;29relative links hợp lệ. Parser/filethực và helpertests nằm local trong `reverse-engineering/`; không tự thêm dữ liệu thật vào Git.
