# Nguồn số tiết: STKB, FET và dữ liệu vnEdu

> Cập nhật: demand/incumbent đã đọc được ở [07](07-file-demand-recovery.md); suffix đã đọc tớiEOF và map thêm ràng buộc/khóa ở [08](08-suffix-constraints-and-locks.md). Các UNKNOWN về vị trí đầy đủ trong file dưới đây giữ bối cảnh nghiên cứu trước.

Danh tính artifact và quy ước VERIFIED/INFERRED/UNKNOWN: [README](README.md). VA là địa chỉ tĩnh trong STKB.exe, không phải offset file hoặc địa chỉ runtime cố định. Các tên `sub_...` là nhãn phân tích, không phải tên source khôi phục được.

## 1. Trả lời các câu hỏi nghiệp vụ

| Câu hỏi | Kết quả và mức xác minh | Bằng chứng |
|---|---|---|
| Khởi tạo số tiết từ đâu? | **VERIFIED tài liệu:** số tiết chuẩn tự gán theo loại trường, sửa được; dùng mặc định khi nhập PCGD. **VERIFIED binary:** có đường sao chép dữ liệu catalogue vào bảng chuẩn và đường lấy bảng chuẩn để tạo bộ đếm xếp. Exact bộ mặc định lúc khởi tạo từng trường còn UNKNOWN. | D1, D2, B3–B5 |
| Sửa ở giao diện nào? | **VERIFIED tài liệu:** Nhập dữ liệu → Số tiết chuẩn của môn học; bảng PCGD cũng có lệnh đổi chuẩn, có chọn cập nhật PCGD đã nhập. **VERIFIED resource:** dialog 162/163, và wizard nhập chuẩn Excel 445/447/449. Việc mở UI thực chưa kiểm thử. | D1–D3, B1 |
| Theo môn/lớp/khối/cấp học? | **VERIFIED tài liệu:** chuẩn theo môn × khối × chương trình đào tạo × buổi; override từng lớp khi nhập PCGD. Cấp học là đầu vào tạo bảng, không đủ để suy số tiết mọi lớp. Có chuẩn 2B riêng. **INFERRED:** bảng đa chiều trong binary tương ứng các trục đó, cần thêm setter/reader để xác nhận mọi index. | D1–D4, B3–B5 |
| Lưu ở đâu? | **VERIFIED:** `.STKB` nhị phân có marker 84 và length, chuỗi length-prefix UTF-16LE, danh mục nối được với ID API. INI chỉ có in/ngày nghỉ. **UNKNOWN:** offset/schema đầy đủ chuẩn, demand, constraints, lịch đã xếp của layout thực. Không xuất demand từ offset đoán. | F1, B6, A1 |
| Khi nào thành tiết cần xếp? | **VERIFIED binary:** staging PCGD → bảng phân công và remaining counters; `InitVars` tạo working records; `Xep_DaiTra` làm việc trên số tiết còn lại. **VERIFIED Core/FET:** occurrences/components được dựng trước solver. | B2–B5, B7, FET1, C1 |
| Đơn/đôi/cố định? | **VERIFIED:** STKB có đặt cặp, khóa và các bước xếp trước; Core Phase 1 nhận split duration 1/2 và explicit lock. **UNKNOWN:** một ánh xạ đầy đủ mọi flag STKB thành split/lock. Cặp ưu tiên/thuộc tính môn không đồng nhất block cứng. | D5, B7, C1; [đối chiếu ràng buộc](../stkb-fet-vnedu-comparison.md) |
| Tuần khác nhau? | **VERIFIED tài liệu:** Clone1/2 cho lịch biến thể, ví dụ tuần lẻ/chẵn; mức trung bình 1.5 tiết có ví dụ chia HK1/HK2. **UNKNOWN:** mọi routine chuyển số tiết năm→tuần hoặc generator nhiều tuần tự động. | D6 |
| vnEdu có gì / thiếu gì? | **VERIFIED snapshot:** danh mục lớp/GV/môn/điểm trường và PCGD; so_tiet toàn 0, 5 record thiếu tham chiếu GV, 38 record môn -2. **UNKNOWN:** đơn vị so_tiet, calendar, phòng, bận/rảnh, định mức chuẩn/override, split, locks và rule policy từ collection này. Thiếu trong collection không chứng minh backend không có endpoint khác. | V1–V3 |

## 2. Binary: từ `so_tiet` đến dữ liệu xếp

**VERIFIED B2:** chuỗi `so_tiet` tại VA `0x824ce8`; xrefs gồm `0x69d2f4`. Trong `sub_69c9a0`, vùng `0x69d2f4–0x69d323` lấy JSON field, đổi chuỗi bằng `atoi` và giữ integer. Vùng `0x69d369–0x69d3be` tạo record 20 byte: ba CString ở +0/+4/+8, integer số tiết ở +0xC và học kỳ ở +0x10. `sub_41a960` thêm vào staging array thuộc đối tượng qua IAT `0x7d21b4`, offset `0x22c` (data pointer +0x230, size +0x234). Không có kiểm tra đơn vị trong đoạn này.

**VERIFIED B3:** vùng native `0x6a3c30–0x6a4183` đọc lại chính array đó, bước mỗi record `0x14` byte tại `0x6a4145`. Code so khớp các CString lớp/môn/GV ở +0/+4/+8. Vùng `0x6a3f67–0x6a3f99` tra bảng qua con trỏ IAT `0x7d2148`, byte offset `0x20cb58`, với nhiều index và một offset theo lớp ở `0x1f7e40`. Khi giá trị tra bằng 0, `cmove edx,eax` thay bằng 1. Sau đó ghi GV và số vào state qua IAT `0x7d214c`, offsets `0x359a04` và `0x359a08`; copy số này sang working/remaining region ở `0x6a3fe1–0x6a3ffc`.

**VERIFIED, phạm vi giới hạn:** trong đường ghi demand vừa nêu, giá trị đến từ bảng nội bộ, không phải trường integer +0xC đã đọc từ API. Đây là bằng chứng cụ thể rằng ít nhất một tuyến có thể đồng bộ association rồi tự khởi tạo số tiết theo dữ liệu local. **UNKNOWN:** tuyến đó có được UI gọi trong mọi tình huống, overwrite hay merge theo những option nào, và các tuyến import khác xử lý số tiết ra sao. Static xref entry hiện có là data/vtable tại `0x83dc30`, không phải direct caller.

**VERIFIED B4:** `sub_625380`, vùng `0x625844–0x6258b3`, đọc dữ liệu catalogue float từ array `0x8ab910`, record stride `0x1b8`; dùng `cvttss2si` rồi ghi vào cùng vùng chuẩn `+0x20cb58`. Bản thân thao tác truncate không đủ chứng minh đây là conversion số tiết năm→tuần. `sub_634b80` cũng có nhánh chuyển float và bù phần lẻ có điều kiện; ý nghĩa chính xác mọi selector/cờ còn UNKNOWN.

**VERIFIED B5:** `sub_50d6e0` mở dialog qua `DoModal`; chỉ khi kết quả IDOK mới ghi giá trị chuẩn và có nhánh tùy chọn lan truyền qua các phân công. Assembly có store vào `+0x20cb58` tại `0x50d82c`. **INFERRED:** khớp thao tác đổi chuẩn/lan truyền được help mô tả; chưa ánh xạ đầy đủ handler với mọi control ID và mọi nhánh giảm số tiết đã xếp.

**VERIFIED B7:** `CAlgAutoSFNew::TStietPCGD` VA `0x6c7900` cộng các số tại state `+0x359a08` nếu phân công có GV; `TStietPcgdGv` `0x6c0090` lọc GV. `InitVars` `0x6be310` gọi `Init_TKB`, đọc phân công và số còn lại để tạo working records. `Xep_DaiTra` `0x6beec0` xử lý remaining counters; `TestSuccessfulTKB` `0x6c8790` chủ yếu kiểm còn tiết chưa xếp. Không dùng thành công kiểu này thay independent validator.

**Giới hạn decompiler:** Hopper chia thân hàm dài tại `0x6a3cf0`/`0x6a4040`; pseudocode query entry `0x6a3c30` không bao phủ toàn nhánh. Các kết luận B3 ưu tiên objdump toàn vùng. Những địa chỉ trông như global `0x13b5688` trong pseudocode là cách provider diễn giải import; bằng chứng chính dùng IAT + byte offset theo assembly, không hứa runtime address đó tồn tại.

## 3. Mô hình demand nên dùng — INFERRED / đề xuất

Giữ ba khái niệm khác nhau: association ai dạy gì/lớp nào; định mức đã chốt theo cycle; và các block/occurrence cần đặt. Tải quy đổi giáo viên còn có hệ số môn, không được lấy thay demand.

Trong ứng dụng tương lai, raw value giữ nguyên cùng nguồn, snapshot, đơn vị và trạng thái xác minh. `unresolved`, `confirmed_zero`, `confirmed_positive` khác nhau; không dùng 0 làm sentinel cho cả ba. Một record chưa rõ định mức hoặc thiếu GV chưa đủ điều kiện biên dịch thành ScheduleInput.

Thứ tự giải quyết đề xuất: override đã xác nhận của phân công/lớp → bảng chương trình đã chọn đúng năm/khối/chương trình/buổi → còn thiếu thì unresolved. Giá trị API chỉ tham gia khi ngữ nghĩa/đơn vị/ưu tiên đã xác minh; khác nhau phải báo đối soát. Không tự fallback 1 theo binary STKB. Sửa mặc định không âm thầm đổi phân công đã xác nhận: phải có preview phạm vi ảnh hưởng và tạo version mới.

Sau khi tổng N được chốt, cấu hình split phải bảo toàn tổng. Ví dụ N=5, `[2,1,1,1]` tạo 4 occurrences chiếm 5 slots. Fixed event khóa occurrence hoặc dựng sự kiện chiếm đúng tập resources. Không tự tạo SH từ association chủ nhiệm -2. Không đổi 1.5 tiết thành duration phân số; cần kế hoạch tuần/semester có đơn vị rõ.

## 4. Sổ bằng chứng tái lập

Các file B* nằm dưới `reverse-engineering/reports/full-study/evidence/`:

- **B1** `pe-resources.json`, `pe-text.json`, `inspect_pe_text.py`: dialog 162 title offset `5002782`, 163 `5002398`, control “Cập nhật từ CTGD mới” `5003172`; 445/447/449 title offsets `5202966`/`5203462`/`5203878`.
- **B2** `pcgd-download.json/.pseudo.txt`, `api-assignment-store.json/.pseudo.txt`; `so_tiet` xrefs retained in earlier query evidence/search.
- **B3** `api-pcgd-to-demand.objdump.txt`, `api-pcgd-to-demand.json`, `demand-from-curriculum2.json`; địa chỉ thật và vùng body như mục 2.
- **B4** `standard-periods-catalog-copy.json/.pseudo.txt`, `standard-periods-import.json/.pseudo.txt`; `stkb.objdump.txt` chứa các store tương ứng.
- **B5** `standard-periods-edit.json/.pseudo.txt`; store `0x50d82c`.
- **B6** báo cáo cũ `reverse-engineering/reports/STKB-file-format-analysis.md`; writer `sub_463ca0`, reader `sub_461ec0`, Common.dll `CSCN::FReadString` `0x100061d0`, `FWriteString` `0x100062b0`.
- **B7** `demand-class.json`, `demand-teacher.json`, `auto-init-demand.json/.pseudo.txt`; thuật toán cũ trong `reverse-engineering/reports/STKB-algorithm-analysis.md` và function catalog.
- **A1** `auxiliary/inventory.json`, `auxiliary/findings.md`: INI và 11 sample, không giải mã demand từ tên file.

D* là dòng bản text sinh từ HTML trong `reverse-engineering/reports/full-study/auxiliary/help-text/`; manifest ghi hash HTML:

- **D1** `Chuong4/4.4.1.Thong_tin_so_tiet_chuan_mon_hoc.txt:2–7`.
- **D2** `Chuong3/3.2.2.Tao_1_tep_STKB_moi.txt:2–24`; `Chuong1/1.4.2.Danh_sach_mon_hoc_va_phan_bo_tiet_chuan_cho_cac_cap_hoc.txt:2–85` (bảng tham khảo của tài liệu, không coi là quy định hiện hành).
- **D3** `Chuong4/4.4.2.Nhap_du_lieu_bang_PCGD.txt:2–4,64–86`.
- **D4** `WhatNew/STKB50_News.txt:9–96` (2b/2B và chuẩn riêng).
- **D5** `Chuong5/5.4.Lenh_xep_mon_hoc.txt:9–17`; `Chuong7/Options/7.7.7.Xep_TKB.txt:4–9`; `WhatNew/STKB50_News.txt:97–127`.
- **D6** `WhatNew/STKB20_News.txt:6–14`; `Chuong6/Views/6.10.TKB_Clone_View.txt:3–14`; chú thích định mức THCS trong D2.

**FET1** `research/fet/fet-7.12.0/src/interface/addactivityform.cpp`, `AddActivityForm::addActivity:688,838–895`; `src/engine/rules.cpp`, `Rules::addSplitActivityFast:11453–11525`; `src/interface/importinterface.cpp:1100–1147` (total/split). Đọc cùng [source FET](../fet/02-scheduling-algorithm.md) và báo cáo local `full-study/fet-vnedu/FET-VNEDU-DEMAND-RECONCILIATION.md`.

**V1** [API observations](../vnedu-api-live-observations.json), `so_tiet:29–39`; **V2** [API findings](../vnedu-api-live-findings.md):19–46; **V3** collection local `docs/stkb (s19).postman_collection.json`, descriptions PCGD cũ dòng 219/New 796; không chứa mô tả đơn vị tiết/tuần. Không có request live mới ở lượt tiếp tục.

**C1** `src/tkb_core/domain/models.py`, `TeachingRequirement:90–113`; `src/tkb_core/preprocessing/normalize.py`, `normalize:31–61`; `src/tkb_core/contracts/capabilities.py`, `check_capabilities:7–28`.
