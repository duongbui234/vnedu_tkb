# 07 — Benchmark FET CLI trên máy local

## Phương pháp và giới hạn

**VERIFIED:** build nguyên source FET 7.12.0 bằng qmake Qt5 5.15.13 + GCC 13.3.0, flags release `-O2 -std=gnu++1z -DFET_COMMAND_LINE`; không sửa source, không cài thư viện. CMake upstream yêu cầu Qt6 6.10 nên dùng tuyến qmake được source hỗ trợ. Xem [`src-cl.pro:1`](../../../research/fet/fet-7.12.0/src/src-cl.pro#L1), [`src-cl.pro:39`](../../../research/fet/fet-7.12.0/src/src-cl.pro#L39), [build.log](evidence/build.log).

**VERIFIED:** máy x86_64 Intel Core i7-12700H, 20 logical CPUs, RAM tổng khoảng 38 GiB. Đây là máy đang dùng chung, không pin CPU/frequency, không kiểm soát cold cache. CLI generator chạy serial trong mỗi process; không chạy nhiều benchmark song song. Số CPU logical không có nghĩa một solve sử dụng cả 20 threads. Dữ liệu máy đầy đủ: [environment.json](evidence/environment.json).

**VERIFIED:** 14 lượt generate, 4 dataset × 3 seeds và 2 diagnostic dataset × 1 seed. Seeds tương ứng sáu thành phần MRG32k3a: (1,2,3,4,5,6), (11,12,13,14,15,16), (21,22,23,24,25,26). Commands và hashes giữ theo từng lượt. `/usr/bin/time -v` ghi user/system CPU và peak RSS; `perf_counter` ghi wall time gồm khởi động, parse, precompute, search và export. Budget FET chỉ áp dụng search theo giây, không phải toàn bộ wall time; [`generate.cpp:9044`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L9044).

Tắt bốn layout HTML, giữ XML, conflicts và CSV để đo/kiểm tra; export warning không phải warning generator bỏ constraint. CSV export có thể không biểu diễn đầy đủ mọi constraint và split activity; XML activity-level cùng source là căn cứ checker. Không sửa bundled dataset hoặc unlock các khóa để làm kết quả dễ hơn.

**VERIFIED:** exit code cả 14 lượt đều 0 nhưng chỉ 6 lượt complete. Trạng thái dưới đây đọc từ `logs/result.txt`, không suy từ process return code. Script: [run-benchmark.py](evidence/run-benchmark.py); raw summary: [benchmark-results.json](evidence/benchmark-results.json). Full stdout/stderr/resource logs và timetables nằm dưới `reverse-engineering/fet/benchmark/`.

## Dữ liệu

| Nhãn | Active activities | Tổng duration | Mode / ngày × giờ | Fixed starts | Ý nghĩa |
|---|---:|---:|---|---:|---|
| standby | 40 | 40 | Official / 10 × 4 | 0 | Ví dụ nhỏ, không khóa start |
| pocht | 511 | 511 | Official / 5 × 7 | 511 | Toàn bộ giờ đã khóa: locked replay, không phải xếp mới |
| german589 | 589 | 630 | Official / 5 × 6 | 1 | Chỉ một start khóa, xếp mới khó hơn |
| ma582 | 582 | 647 | Mornings_Afternoons / 10 × 5 | 12 | Hai buổi, nhiều ràng buộc, 12 start khóa |
| impossible5 | 5 | 5 | Official / 5 × 12 | 5 | Tên file ghi impossible; không dùng tên làm chứng minh UNSAT |
| large1517 | 1517 | 1610 | Official / 10 × 13 | 0 | Diagnostic budget 2s, không phải performance target |

Đường dẫn và SHA-256 từng input nằm trong summary JSON; [example-inventory.json](evidence/example-inventory.json) ghi các ví dụ nguồn. Không coi số activities là số tiết: duration có thể lớn hơn 1.

## Từng lượt đo

| Dataset | Seed set | Budget search s | Status | Wall s | CPU user s | CPU system s | Peak RSS KiB | FET placed current / highest | Fitness ở highest hoặc full |
|---|---:|---:|---|---:|---:|---:|---:|---|---:|
| standby | 1 | 10 | COMPLETE | 0.033936 | 0.00 | 0.00 | 18488 | 40 | 0.0 |
| standby | 2 | 10 | COMPLETE | 0.016081 | 0.00 | 0.00 | 19480 | 40 | 0.0 |
| standby | 3 | 10 | COMPLETE | 0.015939 | 0.00 | 0.00 | 18528 | 40 | 0.0 |
| pocht | 1 | 10 | COMPLETE | 0.064538 | 0.04 | 0.00 | 22792 | 511 | 9.93 |
| pocht | 2 | 10 | COMPLETE | 0.064377 | 0.05 | 0.00 | 22768 | 511 | 9.93 |
| pocht | 3 | 10 | COMPLETE | 0.064193 | 0.04 | 0.00 | 23088 | 511 | 9.93 |
| ma582 | 1 | 10 | TIME_LIMIT | 9.089438 | 9.06 | 0.00 | 24012 | 536 / 581 | 20019.0 |
| ma582 | 2 | 10 | TIME_LIMIT | 9.995416 | 9.97 | 0.00 | 24104 | 547 / 579 | 60029.0 |
| ma582 | 3 | 10 | TIME_LIMIT | 9.994793 | 9.98 | 0.00 | 23372 | 577 / 580 | 40023.0 |
| impossible5 | 1 | 2 | TIME_LIMIT | 2.019552 | 1.97 | 0.00 | 18856 | 5 / 4 | 20000.0 |
| large1517 | 1 | 2 | TIME_LIMIT | 2.070376 | 2.02 | 0.01 | 37776 | 1496 / 1496 | 420019.95 |
| german589 | 1 | 10 | TIME_LIMIT | 9.943670 | 9.89 | 0.01 | 23228 | 573 / 573 | 320025.3 |
| german589 | 2 | 10 | TIME_LIMIT | 9.995268 | 9.95 | 0.00 | 23756 | 357 / 380 | 4180328.6 |
| german589 | 3 | 10 | TIME_LIMIT | 9.986226 | 9.94 | 0.00 | 23208 | 582 / 582 | 140012.75 |

**VERIFIED:** full standby có soft score 0; full Pocht có soft score 9.93. Pocht xếp 511 activities khoảng 0.064s nhưng **511/511 fixed-start**, không dùng con số này làm tuyên bố hiệu năng xếp từ đầu. Các trial khác seed trả cùng assignment hash ở dataset khóa này không chứng minh seed không ảnh hưởng engine.

**VERIFIED:** German 589 và M-A 582 đều timeout trong 10s ở ba seeds. Highest/current khác nhau do ejection/repair. Seed ảnh hưởng completion; đây là quan sát cục bộ, chưa đủ phân phối thống kê cho mọi trường học. Highest được chọn theo completion, không score; German seed 3 có cùng 582 time-assigned ở current/highest nhưng current conflicts 140010.75 thấp hơn highest 140012.75.

**VERIFIED:** fitness của partial chứa penalty unallocated 10000 từ time hoặc space, cộng constraint violations khác; [`timeconstraint.cpp:9447`](../../../research/fet/fet-7.12.0/src/engine/timeconstraint.cpp#L9447), [`spaceconstraint.cpp:2999`](../../../research/fet/fet-7.12.0/src/engine/spaceconstraint.cpp#L2999). Không gọi nó là pure soft objective, không so trực tiếp với score của lịch complete hoặc model OR-Tools khác. Chưa biết optimum/bound.

**VERIFIED:** file `test-liviu-2-impossible.fet` trả TIME_LIMIT, current có 5 time-assigned trong XML và stdout ghi 5 scheduled, nhưng conflict report xác nhận activity 6 chưa allocate room, phạt 10000. Highest-stage được ghi là 4. Room XML trống không phân biệt được unallocated với unspecified; export count không đủ để xác nhận completion. Không báo “5/5 thành công”, và không báo FET đã chứng minh vô nghiệm.

## Kiểm tra đầu ra độc lập

**VERIFIED:** [check-benchmark.py](evidence/check-benchmark.py) đọc activity-level XML và source dataset; kiểm duration không vượt ngày, trùng teacher/subgroup/physical room theo footprint, time availability 100% của teacher/student và breaks, ID/time assignment uniqueness. Có self-check cố ý collision để xác nhận checker từ chối clash. Tất cả output full/current/highest của 14 lượt pass **phần kiểm tra đã triển khai**.

**UNKNOWN:** checker này không xác nhận toàn bộ 357 constraints, capacity, mọi room preference/building, virtual-room assignment hoặc optimality. Nó không được dùng làm implementation Scheduling Core. Số `time_assigned` trong summary không đồng nghĩa fully scheduled khi room chưa allocate. Full status yêu cầu FET log complete và số time-assigned đủ; partial được giữ là partial.

## Cancel smoke test

**VERIFIED:** ma582 chạy với budget 30s, gửi SIGTERM sau khoảng 0.25s; process trả 0, log `Generation interrupted` và ghi hai bộ current/highest. Thời gian đầu cuối khoảng 0.282s trong lần đo này. [cancel-smoke.json](evidence/cancel-smoke.json), [`fetcl.cpp:209`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L209), [`fetcl.cpp:4760`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L4760). Không dùng một phép đo để hứa upper bound cancel latency. SIGINT không được thử; help nói có thể dừng mà không ghi kết quả.

## Tái lập

Build từ thư mục repo, không cài đặt hệ thống:

```sh
mkdir -p reverse-engineering/fet/build
cd reverse-engineering/fet/build
qmake ../../../research/fet/fet-7.12.0/src/src-cl.pro
make -j4
```

Từ repo root:

```sh
python3 docs/research/fet/evidence/run-benchmark.py
python3 docs/research/fet/evidence/check-benchmark.py
```

Script giữ các run đã có trong summary; muốn đo lại, chọn output root mới trong bản thử nghiệm và giữ run ID khác, không xóa/ghi đè kết quả cũ. `command.json` từng run chứa toàn bộ flags chính xác. Build log gốc có flags directory override ban đầu, nhưng `.pro` đặt output thực theo đường dẫn tương đối; xem [01](01-source-overview.md).

## Điều chưa được kết luận

**UNKNOWN:** FET nhanh/chậm hơn CP-SAT, chất lượng so với CP-SAT, khả năng giải đúng quy mô vnEdu và performance Windows/Electron. Chưa xây model OR-Tools theo giới hạn nhiệm vụ. Không có benchmark tương đương để kết luận các điều này. Chỉ số hiện tại mô tả build/data/budget được ghi, không phải SLA.
