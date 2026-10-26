# Độ phủ nghiên cứu toàn bộ nhóm nghiệp vụ scheduling

**VERIFIED** trong cột bằng chứng ghi rõ loại nguồn; không đồng nhất có trang hướng dẫn, có resource hay có export symbol với đã kiểm chứng mọi nhánh runtime. [Danh tính và giới hạn](README.md), [truy vết demand và sổ bằng chứng](01-demand-provenance.md).

## 1. Ma trận nghiên cứu

| Nhóm nghiệp vụ | Phát hiện VERIFIED và nguồn cụ thể | Chưa biết / phần cần làm |
|---|---|---|
| Module/công nghệ | Inventory cũ: 10 EXE/DLL native, không CLI .NET; STKB.exe có MFC và engine, Common.dll chia sẻ state; `reverse-engineering/reports/STKB-module-inventory.md`, `evidence/module-inventory.json`. | Không dịch ngược toàn bộ các thư viện mạng/in/SSL; không cần cho solver. |
| Tạo TKB/học kỳ | Wizard 4 bước trong help `Chuong3/3.2.2...:2–24`; PE dialogs 111–114, title offsets 4971022/4971630/4970334/4969942. | Every handler/default runtime chưa khép kín; giữ metadata header opaque. |
| Danh mục/nhóm/chương trình | Help `Chuong4/4.2.1...:4–27`, `4.2.2...:14–16`, `4.2.5...:3–15`: khối, CTĐT, nhóm GV, môn; lớp có địa điểm. | Không nhập giới hạn tên cũ vào opaque vnEdu IDs; không tự coi nhóm GV là resource cần chiếm đồng thời. |
| Định mức/override | Help 4.4.1/4.4.2, dialogs 162/163, wizard Excel 445/447/449 và vùng code bảng chuẩn B3–B5 báo cáo 01. | Exact toàn bộ default binary theo cấp/khối/chương trình, precedence mọi lệnh còn UNKNOWN. |
| PCGD/sync | Staging JSON `sub_69c9a0` → `sub_41a960`; chuyển sang demand tại vùng 6a3c30; các editor và TST/ĐX trong STKB50_News:97–127. | Không xác nhận raw so_tiet là demand; chưa đối chứng UI thực khi merge/overwrite dữ liệu. |
| Tiết đơn/đôi và placement | Native `Xep_DaiTra:0x6beec0`, `Xep` 0x6bee10; help `Chuong5/5.4...:9–17`, `5.5...:10–22`. | Block cứng khác preference có một/hai cặp; full flag→duration mapping chưa đủ. |
| 2b/2B | STKB50_News:9–96 mô tả 2 PCGD theo buổi và 1 PCGD cả ngày, chuẩn riêng; dialogs 162/163 đồng hiện trong binary. | Chưa xác minh mọi lệnh đồng bộ 3 view; không hardcode 10 tiết/ngày hoặc điều kiện toàn trường vào core mới. |
| Tuần/học kỳ | Clone1/2 cho lịch biến thể trong help STKB20_News:6–14, Clone_View:3–14; Semester init 9.9:7–34. | Không có proof generator multiweek hay conversion annual→weekly đầy đủ; mẫu1.5 không là duration0.5. |
| Slot bận/nghỉ/họp | Help `4.5.1...:9–19`: phân biệt Họp/Bận/Nghỉ/Hạn chế/Rỗi; native checkers lớp/GV/phòng 0x6da5a0/6da320/6da650. | Họp được help gọi hard, song getter Hop còn có score. Chưa chứng minh toàn bộ stage đều bảo toàn hard; không suy từ weight1000. |
| Tải/gaps/nghỉ | Help 4.5.1 và native GetValue_MaxTietBuoi/Ngay, MaxEmpty/TotalEmpty/SoBuoiNghi/SoNgayNghi; [30 coefficients](06-score-defaults.md). | Đơn vị/penalty và precedence cụ thể phải chọn cho vnEdu; không lấy công thức nào chỉ dựa tên hàm. |
| Ràng buộc nhóm/trường | Help `4.5.2...:3–13`, `4.5.3...:10–24`; options `7.7.6...:18–21`. | Help có câu mâu thuẫn về override/min-max; ghi conflict, không giả chọn đúng một phiên bản. |
| Thuộc tính môn | Help `4.5.4...:4–9` nói15 tính chất1ca và2 tính chất2ca; native30 getter thể hiện nhiều nhóm. | Chưa map mọi mã lưu, field UI, getter/checker/penalty; 30getter không phải30mã constraint độc lập. |
| Phòng bộ môn/đa năng | Help `4.3.2...:2–10`, `4.3.4...:2–10`, `4.3.5...:7–18`: eligibility môn×khối, phòng mặc định có thể thay tương đương; native CheckRoom và room-compatible trong function catalog. | Khác optional room/required room; RAD hậu kỳ không được coi là model phòng hoàn chỉnh của Core. |
| RAD/phòng truyền thống | Help `Chuong11/11.3.1...:8–27`, `11.3.2...:2–5`: gán phòng cho lớp đặc biệt, dùng phòng rỗi; dữ liệu song song với TKB chính. | Chưa trace binary toàn RAD; giữ capacity/eligibility đúng trước khi cân nhắc hậu xử lý. |
| Điểm trường/travel | Help `4.5.1...:23–31`: số địa điểm/buổi/ngày và khoảng nghỉ chuyển điểm; API có2điểm trường. | Chưa có travel matrix/calendar hay exact native enforcement; cần policy thực của trường. |
| Tổ hợp/chuyên đề | Help `4.9...`, `4.9.1...`, `4.9.2...`, `4.9.3...`: chọn tổ hợp, phân môn/chuyên đề theo lớp. | Association môn tổ hợp không chứng minh mọi học sinh cùng lịch; cần nhóm học và demand theo thành phần. |
| SH/chào cờ/KHONGHOC | Help5.3:3–14,5.9:2–11: có đối tượng chào cờ/không học riêng; SH trong catalogue có ngữ nghĩa GVCN. | Trang cũ/mới xung đột khả năng xóa chào cờ; API-2 không tự tạo demand. Sự kiện toàn trường không mặc định chiếm mọi GV/phòng. |
| Xếp toàn bộ/stop/kết thúc | `Xep:0x6bee10`: kiểm tra→đại trà→hoàn thiện→kết thúc→tối ưu; `TestSuccessfulTKB:0x6c8790`. Help5.5:3–26 có cho phá một số yêu cầu và Stop. | Đủ tiết không đồng nghĩa valid; trạng thái partial sau Stop chưa runtime-check. |
| Đổi/chuyển/repair | FPR `0x6d9f90`, DPR `0x6dc7e0`; help7.7.7:4–9 chọn thuật toán, khóaSH/cặp; TOP6.12.3:4–11/6.12.5:2–13 mô tả transaction preview. | Không coi một local move thành công là full global-valid; không copy FPR/DPR implementation. |
| Score/chất lượng | 30getter+constructor, mapping assembly ở báo cáo06. Help `6.8.3...:3–25` 12 QMA/CMA, `6.8.5...:3–25` thresholds/delta tùy chọn. | Đây là nhiều thang đánh giá; runtime score và các chế độ hiển thị không tự bằng nhau. |
| Khóa/undo | Help `7.6.1...:2–9`, `7.6.2...:2–8`, `7.5...:2–11`: khóa theo resource/ô, undo-redo trên màn hình tinh chỉnh. | Không hứa undo nhập dữ liệu/API; scope lock và identity cần thiết kế mới. |
| Lưu phương án | Help `9.1.Ghi_phuong_an:2–3`:5phương án chỉ lưu TKB, không lưu dữ liệu gốc/ràng buộc; Clone1/2 là view khác. | Sản phẩm mới phải version cả input/rules, không lặp giới hạn snapshot thiếu context. |
| Import Excel | Help4.2.7:4–24 mô tả mode GV;4.4.3:4–16 PCGD cần lịch chưa xếp và ánh xạ vùng; PE wizard chuẩn Excel445/447/449. | Hai layout PCGD có phần chỉ nằm trong ảnh; chưa OCR/đối chứng parser runtime. |
| Export/in/báo cáo | HelpChuong10, đặc biệt10.9:2–18: báo cáo tải theo PCGD hoặc khoảng ngày trừ nghỉ; HTML/Excel/in theo đối tượng. | Chưa kiểm byte payload updateTkb/upload; print/UI không thuộc Core, không tự triển khai adapter. |
| Kiểm tra/khắc phục lỗi | Help8.3.1/8.3.2 phân biệt kiểmPCGD/lịch;8.5:2–12 có sửa dữ liệu lỗi và ErrorLogic.log. | Không phải validator độc lập; không chạy chức năng sửa lỗi trên file gốc. |

Tên rút gọn `...` trong bảng trỏ đúng các file đã liệt kê đầy đủ trong `reverse-engineering/reports/full-study/auxiliary/DEMAND-WORKFLOW.md` và `citation-map.json`; corpus local giữ tên HTML gốc và dòng. Không suy logic từ ảnh chưa đọc.

## 2. FET bổ sung điều gì?

**VERIFIED source:** activity/group/subgroup membership, duration/split, tách time/space constraints, preprocessing và occupancy cache; generator recursive swapping, seed, rollback, current/highest snapshots và cancellation. Đường dẫn/function/dòng chi tiết tại [algorithm](../fet/02-scheduling-algorithm.md), [constraint catalog](../fet/03-constraint-catalog.md), [conflicts](../fet/04-heuristics-and-conflicts.md). Catalogue source đã kiểm kê357classes,275time/82space; không coi mỗi class là một tính năng độc lập và không hứa hỗ trợ toàn bộ trong vnEdu.

**INFERRED:** học cấu trúc activity rõ ràng, atomic participant conflicts, chuẩn bị miền hợp lệ và giải thích vi phạm từ FET; học workflow chuẩn/override/phân công/khóa/tinh chỉnh gắn giáo vụ từ STKB. Dùng CP-SAT để biểu diễn các semantics đã chốt và independent validator làm cổng correctness. Không lấy recursive swapping làm lời giải thích sai cho CP-SAT.

## 3. Những gì còn UNKNOWN sau lượt này

1. Demand/constraints/incumbent đầy đủ của8file thực; offset còn sau prefix chưa được parser xác minh.
2. Mọi rule ID, precedence, default bị override lúc chạy, và các engine ngoài constructor SFNew đã kiểm.
3. Runtime Windows/UI thao tác thật; phiên bản resource4.5/help5.0 hỗn hợp và các trang mâu thuẫn.
4. School policy được giáo vụ xác nhận: quota từng lớp, cách chia tiết, tuần/học kỳ, travel, ưu tiên chất lượng.
5. Chất lượng/hiệu năng so sánh STKB/FET/CP-SAT cùng dữ liệu và semantics. Không có benchmark tương đương để xếp hạng tốc độ.

Các unknown trên không ngăn viết kiến trúc có ranh giới đúng; chúng ngăn tuyên bố đã nhập được nhu cầu thực hoặc đã làm sản phẩm tương đương STKB.
