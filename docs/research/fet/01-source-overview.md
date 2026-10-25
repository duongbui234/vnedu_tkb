# 01 — Source FET, provenance và phạm vi

Nghiên cứu ngày 2026-10-25. Mọi số dòng trong bảy báo cáo thuộc **FET 7.12.0**, archive SHA-256 `ff3d1e0be7708a648f6c4a5078f49d0b0926283c065791105229753c7b697cd4`.

Quy ước: **VERIFIED** = đọc trực tiếp implementation hoặc có kết quả thử nghiệm lưu lại; **INFERRED** = diễn giải/đề xuất có căn cứ; **UNKNOWN** = chưa đủ bằng chứng. VERIFIED không tự động có nghĩa đã kiểm thử hết mọi tổ hợp constraint.

## Source đã có và nguồn chính thức

- **VERIFIED:** người dùng đã có `research/fet/fet-7.12.0/` và `research/fet/fet-7.12.0.tar.xz`. Dùng trực tiếp, không tải lại, không sao chép/di chuyển cây source. `reverse-engineering/fet/` chỉ chứa build và benchmark mới.
- **VERIFIED:** trang [Download của tác giả](https://lalescu.ro/liviu/fet/download.html) công bố bản source 7.12.0, ngày 14/10/2026, 9,321,936 byte và SHA-256 nêu trên. [Homepage](https://lalescu.ro/liviu/fet/) liên kết trang tải này. URL archive chính thức: `https://lalescu.ro/liviu/fet/download/fet-7.12.0.tar.xz`.
- **VERIFIED:** local archive có đúng hash đó; 897 regular files trong archive đều khớp byte với source tree người dùng cung cấp. Có manifest từng file ở [source-manifest.json](evidence/source-manifest.json). Không dùng GitHub mirror làm nguồn chuẩn.
- **VERIFIED:** `VERSION:1` và [`README:1`](../../../research/fet/fet-7.12.0/README#L1) xác nhận 7.12.0; [`ChangeLog:1`](../../../research/fet/fet-7.12.0/ChangeLog#L1) ghi các thay đổi mới. Đây là release archive, không phải Git checkout có commit identity. **UNKNOWN:** commit Git tương ứng; không suy ra commit từ số phiên bản.
- **UNKNOWN:** detached GPG signature chưa được xác minh; đây là kiểm tra hash đối chiếu trang HTTPS, không phải kiểm tra chữ ký.

## License và ranh giới tái sử dụng

**VERIFIED:** [`README:5`](../../../research/fet/fet-7.12.0/README#L5), [`generate.cpp:14`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L14) và [`COPYING:1`](../../../research/fet/fet-7.12.0/COPYING#L1) công bố GNU Affero General Public License version 3. Header engine nêu version 3; không tự thêm “or later”. Tài liệu có giấy phép riêng như `COPYING.FDL`, thư mục `licenses/` chứa thông tin thành phần khác.

**INFERRED — quyết định thiết kế:** chỉ dùng nghiên cứu này để viết đặc tả độc lập bằng Python/OR-Tools; không đưa implementation C++ FET vào sản phẩm. Nếu sau này phân phối FET, liên kết/thay đổi FET hoặc cung cấp dịch vụ dùng bản sửa đổi, phải đánh giá điều kiện cụ thể trước. [`COPYING:540`](../../../research/fet/fet-7.12.0/COPYING#L540) có điều khoản tương tác qua mạng. Chạy qua subprocess không tự chứng minh mọi hình thức đóng gói được miễn điều kiện giấy phép. **UNKNOWN:** nghĩa vụ của bản phân phối vnEdu cuối cùng khi chưa có phương án tích hợp và đánh giá license riêng; đây không phải kết luận pháp lý cho sản phẩm.

## Bản đồ source

| Vùng | Vai trò đã xác nhận | Điểm vào |
|---|---|---|
| CLI | Đọc dữ liệu, tính internal structure, precompute, generate, export | [`fetcl.cpp:1186`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L1186), [`fetcl.cpp:4731`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L4731), [`fetcl.cpp:4773`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L4773), [`fetcl.cpp:4795`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L4795) |
| GUI | Chuẩn bị và khởi chạy generator trên thread | [`timetablegenerateform.cpp:177`](../../../research/fet/fet-7.12.0/src/interface/timetablegenerateform.cpp#L177), [`timetablegenerateform.cpp:112`](../../../research/fet/fet-7.12.0/src/interface/timetablegenerateform.cpp#L112) |
| Rules | Registry dữ liệu, internal indexes và internal constraints | [`rules.h:92`](../../../research/fet/fet-7.12.0/src/engine/rules.h#L92), [`rules.h:252`](../../../research/fet/fet-7.12.0/src/engine/rules.h#L252), [`rules.cpp:6418`](../../../research/fet/fet-7.12.0/src/engine/rules.cpp#L6418) |
| Activity | Duration, split group, teachers và subgroups | [`activity.h:79`](../../../research/fet/fet-7.12.0/src/engine/activity.h#L79), [`activity.h:109`](../../../research/fet/fet-7.12.0/src/engine/activity.h#L109), [`activity.h:130`](../../../research/fet/fet-7.12.0/src/engine/activity.h#L130), [`activity.h:174`](../../../research/fet/fet-7.12.0/src/engine/activity.h#L174), [`activity.h:198`](../../../research/fet/fet-7.12.0/src/engine/activity.h#L198) |
| Solution | times, rooms, realRoomsList, cache và fitness | [`solution.h:39`](../../../research/fet/fet-7.12.0/src/engine/solution.h#L39), [`solution.h:66`](../../../research/fet/fet-7.12.0/src/engine/solution.h#L66), [`solution.cpp:137`](../../../research/fet/fet-7.12.0/src/engine/solution.cpp#L137) |
| Preprocessing | Tạo lookup structures, kiểm tra dữ liệu và initial order | [`generate_pre.cpp:1632`](../../../research/fet/fet-7.12.0/src/engine/generate_pre.cpp#L1632), [`generate_pre.cpp:26500`](../../../research/fet/fet-7.12.0/src/engine/generate_pre.cpp#L26500) |
| Generate | Candidate placement, conflict lists, recursive repair, room selection | [`generate.cpp:8806`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L8806), [`generate.cpp:10229`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L10229), [`generate.cpp:7100`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L7100) |
| Constraint implementations | Tính penalty, mô tả, internal mapping và mode compatibility | [`timeconstraint.h:484`](../../../research/fet/fet-7.12.0/src/engine/timeconstraint.h#L484), [`spaceconstraint.cpp:2290`](../../../research/fet/fet-7.12.0/src/engine/spaceconstraint.cpp#L2290) |
| Export | Ghi current/highest/final và conflict reports | [`fetcl.cpp:4813`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L4813), [`fetcl.cpp:5099`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L5099) |

**VERIFIED:** generator hiện tại có 40,128 dòng; preprocessing 27,334; time constraints 88,352; space constraints 27,647. Các file trong `doc/algorithm/` giải thích thuật toán nhưng có bản thử nghiệm lịch sử; bằng chứng hành vi lấy từ `src/engine/` hiện tại, không lấy file “theoretically better” năm 2018 làm code đang chạy.

## Build và dữ liệu tạo mới

**VERIFIED:** CMake yêu cầu Qt6 ≥ 6.10 tại [`CMakeLists.txt:50`](../../../research/fet/fet-7.12.0/CMakeLists.txt#L50). Máy có Qt5 5.15.13; qmake CLI cho phép Qt5 ≥ 5.15 tại [`src-cl.pro:1`](../../../research/fet/fet-7.12.0/src/src-cl.pro#L1), nên build qua tuyến này, không patch requirement CMake. Release flags `-O2`, C++17, chỉ QtCore; [`src-cl.pro:39`](../../../research/fet/fet-7.12.0/src/src-cl.pro#L39) và [build.log](evidence/build.log). Binary ở `reverse-engineering/fet/fet-cl`; objects/generated moc ở `reverse-engineering/fet/tmp/cl/`. Không chạy `make install`, không cài dependency.

Các flags DESTDIR/OBJECTS_DIR truyền ban đầu bị assignment trong `.pro` ghi đè; vị trí thực tuân theo [`src-cl.pro:43`](../../../research/fet/fet-7.12.0/src/src-cl.pro#L43). Toàn bộ vẫn nằm ngoài source. Toolchain và binary hash nằm ở [environment.json](evidence/environment.json).

Đầu ra nghiên cứu: [02 thuật toán](02-scheduling-algorithm.md), [03 catalog](03-constraint-catalog.md), [04 heuristic/conflicts](04-heuristics-and-conflicts.md), [05 so sánh](05-fet-vs-ortools.md), [06 vnEdu](06-vnedu-applicability.md), [07 benchmark](07-benchmark.md). Không tạo Scheduling Core/Electron/React/SQLite; không sửa báo cáo STKB để suy diễn FET.
