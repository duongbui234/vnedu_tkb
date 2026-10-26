# Khôi phục demand và lịch chính từ tám file STKB

Ngày 2026-10-26, tiếp nối lượt parser bị gián đoạn. **VERIFIED — đã đọc được demand và lịch chính trên cả8file**, có đối chiếu tổng từng phân công và lịch lớp/GV hai chiều. Chưa phải bộ giải mã đầy đủ toàn bộ định dạng, toàn bộ ràng buộc hay validator mọi nghiệp vụ STKB.

> Cập nhật tiếp nối: [báo cáo08](08-suffix-constraints-and-locks.md) đã sửa công thức kích thướcRAD và đọc hết suffix đúngEOF trên8file; các đoạn bên dưới nói suffix/probe chưa đạt là trạng thái của lượt07, không phải blocker hiện tại.

## 1. Nguyên nhân lỗi cũ và cách sửa

**VERIFIED — lỗi chọn layout:** writer ứng viên `sub_463ca0` khớp phần đầu của các file nhưng không đủ để suy toàn bộ schema. Đặc biệt, writer đó ghi block môn24byte/record, còn native reader `sub_443310` đọc record môn gồm **39byte số/cờ và12chuỗi length-prefix UTF-16LE**. Dùng24byte làm bước nhảy đã đặt bảng kế tiếp sai vị trí. Kết luận cũ “writer phù hợp toàn artifact” là quá rộng; chỉ phần prefix đã được đối chứng khi đó.

**VERIFIED — lỗi đếm view:** lịch GV lưu **3record12byte cho mỗi slot**, không phải1record. Native assembly `0x4445cc–0x444628` có3lệnh đọc tương ứng; sau khi sửa record môn và đếm đủ3view, bảng demand phía sau căn chỉnh chính xác trên8file.

Đây là vấn đề truy vết/triển khai reader chưa xong, không phải bằng chứng file bị mã hóa hay cần thêm tài khoản/API. Không chạy STKB hoặc sửa file gốc để khắc phục.

## 2. Bằng chứng và danh tính

- **VERIFIED binary:** STKB.exe SHA-256 `29fee192c60d2bd009103713bf22441b418a7b872d2087443551b2bdff4e6525`; REA/Hopper `procedure_pseudo_code(0x443310)` Evidence ID `ev_f280be3cb1e6181180da021257eb37b2fe0e52cb0f21b8dd4c00d3772f34a802`. Full JSON local: `reverse-engineering/reports/full-study/evidence/data-reader-443310.json`; assembly `data-reader-443310.objdump.txt`.
- **VERIFIED binary:** record môn nằm trong vùng reader `0x443f89–0x444124`: reads3byte,5u32,2string,4u32,10string. Pseudocode cũ giữ tại `reverse-engineering/reports/evidence/file-read-legacy.hopper-pseudocode.txt:1861–1897`. Tên file “legacy” là nhãn nghiên cứu cũ, không tự chứng minh schema không phù hợp file thực.
- **VERIFIED binary:** chuẩn môn: reader `0x444429–0x4444a3` duyệt2buổi ×12khối ×sốmôn ×sốCTĐT, đọc u32. Native demand initializer `0x6a3f67–0x6a3f99` tra cùng vùng quaIAT`0x7d2148`+`0x20cb58`; xem [nguồn định mức](01-demand-provenance.md).
- **VERIFIED binary:** lịch lớp `0x4444a5–0x444571`, lịchGV `0x444572–0x44464a`:2buổi, entity,7day-indices,5period-indices; mỗi slot3triples interleaved. Chỉ primary view được audit; danh tính/ngữ nghĩa2view bổ sung còn UNKNOWN.
- **VERIFIED binary:** demand `0x44464b–0x4446b0`, thứ tự buổi→môn→lớp, mỗi record12byte, vào vùng `var2+0x359a00` với index. `TStietPCGD` VA`0x6c7900` dùng GV ở+4 và tổng ở+8; remaining dùng field đầu, đối chiếu thực tế xác nhận.
- **VERIFIED thử nghiệm:** `schedule-recovery.json` và `schedule-recovery-summary.json` lưu offsets/tổng/audit; hash8file khớp manifest download, file gốc không đổi.

Mốc vùng bao gồm cả loop bounds/nhảy; dùng assembly đã lưu để xác định từng instruction, không coi pseudocode là source gốc.

## 3. Cấu trúc đã đọc thêm

Reader nghiên cứu [inspect_stkb_schedule.py](../../../reverse-engineering/scripts/inspect_stkb_schedule.py) tái sử dụng reader prefix đã có, rồi đọc tuần tự từ vị trí dừng:

| Section | Kích thước/thứ tự VERIFIED trong reader | Ngữ nghĩa |
|---|---|---|
| Cờ/lớp/GV trước properties |12byte +GV×nhómGV byte +2arrayu32 theo class-session | Width/order xác nhận; chưa đặt nghĩa mọi field |
| Class properties |11u32+2string mỗi class-session | Chưa map đủ11field |
| Teacher properties |33byte,4string,1byte,1string | Chưa map đủ constraint fields |
| Subject properties |23byte,2string,16byte,10string | Cấu trúc39byte+12string; từng field chưa map đủ |
| Phòng/eligibility | Catalogue3string, các matrix/properties theo counts, GVgroup×môn byte |8file đều0phòng; nhánh phòng chưa được đối chứng bằng file có phòng |
| CTĐT và chuẩn | Catalogue1string;2×12×môn×CTĐT u32 |8file đều1CTĐT;174giá trị chuẩn khác0; đây là giá trị lưu trong file, không tự là default khởi tạo mọi trường |
| Class slots | Class-session×7×5×3triples | Primary gồm môn/GV/trườngphòng, với special markers ngoài miền môn |
| Teacher slots |2×GV×7×5×3triples | Primary đối chiếu lớp/môn/trườngphòng với class view |
| Demand | Class-session×môn×3int | remaining, teacher-index, total; các chỉ số nối với catalogue cùng snapshot |

Không lấy7storageindices làm kết luận trường học7ngày. Trong các lịch có tiết, chỉ indices1–6 có ordinary lessons; index7 không có ordinary lesson. Marker255 được ghi riêng, chưa tự diễn giải thành KHONGHOC/chào cờ/khóa.

## 4. Kết quả thực tế

| File | Phân công có tổng>0 | Tổng tiết | Đã xếp | Còn lại | Lỗi đối chiếu |
|---|---:|---:|---:|---:|---:|
| test.STKB |494|886|0|886|0|
| TKBlychinhthang.STKB |715|1283|0|1283|0|
| TUSUA.STKB |222|505|372|133|0|
| MOISH.STKB |205|488|488|0|0|
| MOI19.STKB |205|488|488|0|0|
| TKB199.STKB |211|506|506|0|0|
| DOT2.STKB |211|506|506|0|0|
| test test.STKB |494|886|0|886|0|

**VERIFIED:** mọi phân công thỏa `placed + remaining = total`, teacher-index hợp lệ, GV của tiết khớp phân công; không thấy double-bookingGV trong cùng session/day/period; class và teacher primary views khớp hai chiều. Không chỉ kiểm tổng toàn file: đối soát theo từng class-session×subject.

**VERIFIED:** ba file test/TKBlychinhthang/testtest có demand dương nhưng primary timetable chưa có ordinary lessons. Không suy file trống demand từ lịch chưa xếp. Hai fileTKB199/DOT2 có cùng hash từ manifest cũ.

**VERIFIED:** các snapshot có demand khác nhau (505/488/506), nên không coi chúng là các nghiệm của cùng một bài toán để đánh giá chất lượng/thuật toán. **UNKNOWN:** vì sao giáo vụ thay phân công qua các file; không tự suy là engine xóa17tiết hoặc tự tối ưu định mức.

**INFERRED:** hiện có thể dùng file làm nguồn bằng chứng demand/incumbent độc lập với APIso_tiet=0. Muốn đưa vào sản phẩm vẫn cần người dùng chọn snapshot/chu kỳ, kiểm entitymapping và policy, phân biệt dữ liệu lịch sử với nhu cầu hiện hành. Không tự đổi Core hoặc viết APIadapter trong lượt này.

## 5. Kiểm tra đã chạy và giới hạn

```sh
python3 -m unittest discover -s reverse-engineering/scripts -p test_inspect_stkb_schedule.py
python3 reverse-engineering/scripts/inspect_stkb_schedule.py reverse-engineering/downloads/vnedu-tkb/*.STKB
```

**VERIFIED:**5synthetic tests passed: variable-lengthsubject+3teacherviews, demandtruncated bị từ chối, countguard, phát hiện demand/mirror bị sửa sai và GV bị xếp trùng. Tám file thực audit0issues; tests không chứa dữ liệu thật. Có kiểm SHA-256 với downloadmanifest. Core/fixtures/dependencies không thay đổi; chưa chạy lại pytestCore vì không sửa Core.

**UNKNOWN còn lại:** phần suffix sau demand (142.431byte ở5file377.599byte;294.499byte ở2filetest;301.027byte ởfile756.192byte), mọi mãconstraint/khóa, nghĩa2view phụ, phòng có dữ liệu, policy/score và runtimeWindows. Helper`probe_suffix.py` là thử nghiệm chưa đạt: áp toàn suffix của reader ứng viên bị vượtEOF ở đoạn whole-dayteacher, nên **không** tích hợp nhánh đó vào parser hay coi các field suffix là VERIFIED. Cần khép kín versiondispatch/schema trước khi đọc tiếp.

`audit0issues` xác nhận tính nhất quán các bảng đã đọc, không chứng minh lịch hard-valid theo mọi ràng buộc trường, không kiểm spacing/gaps/khóa/travel. File dùng cấu trúc khác hoặc count ngoài profile phải bị từ chối, không fallback đoán layout.
