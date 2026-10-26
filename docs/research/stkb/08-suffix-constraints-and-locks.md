# Phần đuôi STKB: đọc hết file, ràng buộc và khóa tiết

Ngày2026-10-26. Tiếp nối [khôi phục demand/lịch](07-file-demand-recovery.md), giữ nguyên Core và file gốc. **VERIFIED: parser đã đọc đến đúng EOF của cả8file, không thừa/thiếu byte.** Điều này xác nhận cấu trúc của profile quan sát, không tự xác nhận ngữ nghĩa mọi field hoặc mọi file STKB khác.

## 1. Vì sao trước đó còn lệch?

**VERIFIED lỗi triển khai:** sau bảng demand, phần RAD duyệt2buổi, rồi mỗi buổi duyệt lớp của buổi đó và toàn bộGV. Đặt `N = lớp_buổi0 + lớp_buổi1`, kích thước đúng là:

`35 × (N + 2×số_GV) × 8 byte`

Probe cũ dùng thêm hệ số2 trước35, đếm số buổi hai lần cho phần lớp đã cộng tổng. Lỗi này đẩy các bảng phía sau đi quáEOF. Sửa đúng công thức từ vòng lặp native reader/writer khiến tất cả bảng sau căn chỉnh, gồm các bảng chuỗi có count14/33 và các cache2B, tới đúng byte cuối của8file. Không có bằng chứng cần giải mã mật mã để đọc payload này.

Nguồn: `DataBase` reader VA`0x443310`, pseudocode local `file-read-legacy.hopper-pseudocode.txt:2393–2434`; writer VA`0x445330`, `data-writer-445330.pseudo.txt:899–940`. Tất cả evidence nằm dưới `reverse-engineering/reports/` hoặc `full-study/evidence/` như mục6.

## 2. Dispatch: phân biệt DataBase, DataS10 và compatibility selector

**VERIFIED binary/RTTI:** PE chứa hai class serialization khác nhau. Mapping dưới đây lấy trực tiếp từ vtable và MSVC RTTI, không đoán tên từ địa chỉ:

| Class RTTI | Vtable | Method offset | Target và vai trò đã đối chứng |
|---|---|---|---|
| `.?AVDataBase@@` |`0x7ebd64`|`+0x0c`|`0x445330`: ghi payload tương ứng với reader |
| cùng class |cùng vtable|`+0x10`|`0x443310`: đọc payload đã khớp8file tớiEOF |
| cùng class |cùng vtable|`+0x14`/`+0x18`|`0x442e70`/`0x4425a0`: writer/reader header; giữ các trường opaque ngoài mục tiêu nghiệp vụ |
| cùng class |cùng vtable|`+0x1c`|`0x447200`: dispatcher có selector4..23 |
| `.?AVDataS10@@` |`0x7ebfd8`|`+0x0c`/`+0x10`|`0x463ca0`/`0x462710`: cặp khác, không được ghép toàn layout với DataBase |

**VERIFIED:** dispatcher`0x447200` trừ4 khỏi argument, kiểm range0..19, dùng byte table`0x4472e8` và jump table`0x4472b8`. Các selector đi tới:

| Selector | Reader đích |
|---|---|
|4|`0x45e280`|
|5|`0x45b590`|
|6|`0x458850`|
|7|`0x456020`|
|8|`0x454170`|
|9,10|`0x4521c0`|
|11|`0x4500f0`|
|12|`0x44e5e0`|
|20|`0x44c930`|
|21|`0x44aa20`|
|23|`0x448a60`|

13–19 và22 về nhánh trả0. Ngoài range cũng trả0. **UNKNOWN:** tên phiên bản/format người dùng tương ứng mọi selector và mọi caller runtime. Không gọi4..23 là version STKB thương mại khi chưa có bằng chứng.

**VERIFIED về phạm vi:** marker đầu file84 không phải argument có thể đưa thẳng vào dispatcher4..23. Tám file dùng cùng marker nhưng còn phải chọn đúng class/layout. Cách gọi “version84” trong parser cũ chỉ là nhãn profile; không có bằng chứng nó là version ứng dụng hoặc toàn bộ điều kiện dispatch. DataS10 cũng không được tự suy là “bản1.0/10.0” từ tên.

Bằng chứng: `native-dispatch.json`, `compat-dispatch.objdump.txt`, REA xrefs`0x443310` tại`0x7ebd74` và`0x43d79a`. Lượt này xác định được dispatch tĩnh; không có runtime traceWindows.

## 3. Mã ràng buộc theo slot và khóa tiết

**VERIFIED binary:** ngay sau demand, mỗi teacher-slot được đọc2u32 theo thứ tự:

1. Mã yêu cầu theo slot, được nạp vào vùng qua IAT`0x7d214c`, offset gốc`0xc5700` cộng index.
2. Cờ khóa tiết, được nạp vào cùng vùng, offset gốc`0xc5704` cộng index.

Reader`0x4446b1–0x44475b`: thứ tự buổi0/1 → GV1..N → day-index1..7 → period1..5; mỗi cặp8byte. Không nhầm đây là record lịch chính12byte.

**VERIFIED:** `CAlgSupportBase::IsLocking`, VA`0x6bca20`, kiểm đúng địa chỉ trường thứ2 và trảtrue khi giá trị **bằng1**. `CheckTeacher` VA`0x6da320` dùng vùng khóa đó để quyết định các thao tác; không coi mọi mode/caller có behavior giống nhau chỉ từ predicate. File offset cờ khóa thứ`i` trong section này bằng `section_offset + 8×i + 4`.

| Mã slot | Ý nghĩa đã nối với binary | Chứng cứ |
|---:|---|---|
|997|Hạn chế|`GetValue_Hanche`,VA`0x6c46c0`, so sánh`0x3e5`|
|998|Nghỉ|`GetValue_Nghi`,VA`0x6c4300`, so sánh`0x3e6`|
|999|Bận|`GetValue_Ban`,VA`0x6c4580`, so sánh`0x3e7`|
|1000..1006|Các mã được `CSCN::IsHop` nhận là Họp|Common.dll VA`0x100073c0–0x10007403` so sánh đúng7mã này|
|0|Không có mã yêu cầu tại field này trong dữ liệu quan sát|Không tự đồng nhất với demand0 hoặc khóa0|

Getter`GetValue_Hop` còn có kiểm`>=1000` trong ngữ cảnh tính điểm; không vì thế diễn giải mọi số lớn bất kỳ là một mã họp đã biết. Những mã khác giữ UNKNOWN. Binary chỉ số và mã cố định không phải vnEdu IDs.

## 4. Thuộc tính GV đã nối nghĩa

**VERIFIED:** một record thuộc tính sốGV dài96byte; reader`0x4447cf–0x444809` nạp vào vùng quaIAT`0x7d214c`, base`0x409038 + 96×teacher_index`. Trong buffer file nối tiếp, record đầu tiên làGVindex1, nên parser dùng offset`96×(teacher_index−1)`.

| Offset trong record | Ngữ nghĩa VERIFIED | Consumer |
|---|---|---|
|byte`+1`|Bật max tiết/buổi|`GetValue_MaxTietBuoi` `0x6c5510`|
|i32`+24`|Giới hạn số tiết/buổi|cùng getter; số vượt được nhân hệ số tính điểm|
|byte`+2`|Bật max tiết/ngày|`GetValue_MaxTietNgay` `0x6c55b0`|
|i32`+28`|Giới hạn số tiết/ngày|cùng getter, cộng cả2buổi trong logic đã đọc|
|byte`+3`, i32`+32/+36`|Bật và hai đầu khung tiết buổi0|`GetValue_FromT1toT2` `0x6c5a40`|
|byte`+4`, i32`+40/+44`|Bật và hai đầu khung tiết buổi1|cùng getter|

Các trường khác được đọc/định vị nhưng chưa gán hết tên. Không đặt byte+3/+4 là MaxEmpty/TotalEmpty chỉ theo thứ tự giả định: consumer thực cho thấy đây là khung giờ. Ngữ nghĩa min/max/override giữa GV/nhóm/trường vẫn cần đối chiếu từng getter.

## 5. Kết quả trên dữ liệu thực

**VERIFIED:** cả8file đọc đúngEOF, hash gốc không đổi; primary timetable/demand vẫn audit0lỗi như lượt trước. Kết quả khác với “đã thỏa mọi yêu cầu”:

| File | Mã998:Nghỉ | Mã1000:Họp | Cờ khóa=1 | GV bật max tiết/buổi |
|---|---:|---:|---:|---:|
|test / testtest / TKBlychinhthang / TUSUA|0|0|0|0|
|MOISH / MOI19 / TKB199 / DOT2 — mỗi file|321|5|0|44|

Trong4file sau, max tiết/buổi được cấu hình:30GV có mức3,13GV mức4,1GV mức2;3GV không bật, giá trị lưu0. **Không** dùng giá trị0 khi cờ disabled như một hard limit0.

**VERIFIED quan sát giao nhau:** MOISH có25tiết nằm trên slotGV mang mã998 và13teacher-sessions vượt mức max/buổi đã bật, tổng vượt13tiết. MOI19/TKB199/DOT2:27tiết trên mã998,16teacher-sessions vượt mức, tổng vượt16. Không có ordinary lesson trên mã họp trong những snapshot này.

**INFERRED:** không được mặc định Nghỉ và max/buổi của STKB luôn là hard constraints bất khả phá. Các snapshot lưu đủ tiết vẫn có vi phạm những yêu cầu này. Đây không chứng minh mọi chế độ STKB cho phá chúng, hoặc người dùng đã chọn những option nào. Core mới phải có hard/soft policy rõ, và independent evaluator báo số vi phạm riêng với completion.

**VERIFIED:** cả8file không có cờ khóaslot bằng1 tại field đã map. **UNKNOWN:** auto-lockSH/cặp tiết, khóa theo lớp/GV/môn và mọi chế độ chỉnh lịch. Không suy từ0explicit locks rằng ứng dụng không có cơ chế khóa khác. Trường hợp khóa dương được kiểm bằng predicate binary và fixture tổng hợp; chưa roundtripWindows với một file thật có khóa dương.

## 6. Deliverables và kiểm thử

- [Reader suffix](../../../reverse-engineering/scripts/inspect_stkb_suffix.py): width/order, yêu cầuEOF, trả slotcodes/locks và thuộc tínhGV đã map. Nhánh saved-plan bật hiện bị từ chối rõ ràng;8file thực đều có5planflags0. Đây là giới hạn profile, không lỗi bị bỏ qua.
- [Reader toàn file](../../../reverse-engineering/scripts/inspect_stkb_schedule.py): giữ các kiểm tra demand/lịch chính, bổ sung suffix và thống kê yêu cầu; không viết `.STKB`.
- Tests `reverse-engineering/scripts/test_inspect_stkb_schedule.py`, `test_inspect_stkb_suffix.py`: **10tests passed**, gồm RAD không đếm buổi hai lần, variable tables, exactEOF, truncated/trailing data, unsupportedplan, demand/mirror/doublebooking, quan sát preference không gọi nhầm hard-validity.
- Evidence local `full-file-recovery.json`, `native-dispatch.json`, `locking-predicate.json/.objdump.txt`, `locking-two-sessions.json`, `common-is-hop.objdump.txt`, `data-writer-445330.json/.pseudo.txt`, `data-reader-443310.json/.objdump.txt`; các getter ở`evidence/criteria/` theo [mapping30hệsố](06-score-defaults.md).

Lệnh tái lập: `python3 -m unittest discover -s reverse-engineering/scripts -p 'test_inspect_stkb_*.py'`; `python3 reverse-engineering/scripts/inspect_stkb_schedule.py reverse-engineering/downloads/vnedu-tkb/*.STKB`.

Kiểm tra cuối:8hashfile vàhashEXEkhôngđổi; primaryaudit0issues;38relativeMarkdownlinks hợp lệ; `git diff -- src tests pyproject.toml uv.lock` rỗng. REAexport9Evidence records vào`rea-suffix-locks-evidence.json` và đã đóng target. Không chạy lại pytestCore, không gọi API mới.

**Phần đã xong của yêu cầu này:** cấu trúc suffix trên8file, phân biệt hai serializer/compatibilityswitch, vị trí slotconstraint và khóa, một số thuộc tínhGV với số liệu thực và kiểm thử. **UNKNOWN còn lại:** ngữ nghĩa mọi field, mọi legacyselector, policy runtime/precedence, savedplans có dữ liệu/phòng có dữ liệu và auto-locks. Không đổi tên các unknown này thành “chưa đọc được phần đuôi”: cấu trúc đã đọc hết, phần diễn giải nghiệp vụ còn giới hạn rõ.
