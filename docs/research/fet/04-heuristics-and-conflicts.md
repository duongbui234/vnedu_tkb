# 04 — Heuristic, conflicts, retry và trạng thái kết thúc

FET 7.12.0; provenance tại [01](01-source-overview.md).

## Phân biệt ba loại “weight”/“conflict”

**VERIFIED:** `weightPercentage` được generator sử dụng qua `Generate::skipRandom` [`generate.cpp:4287`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L4287). Giá trị âm là constraint không có; ≥100 không skip; giữa 0 và 100 so PRNG draw với threshold suy từ phần trăm. Xấp xỉ probability apply = weight/100, có lượng tử hóa số nguyên. Không có nghĩa “FET bảo đảm đúng 95% lần” hay “nghiệm cuối thỏa 95% constraint”.

**VERIFIED:** `Solution::fitness` [`solution.cpp:137`](../../../research/fet/fet-7.12.0/src/engine/solution.cpp#L137) cộng penalty từ từng constraint. Công thức thường là `weightPercentage / 100 * units_broken`; đơn vị vi phạm phụ thuộc loại, không phải luôn “số tiết”. Ví dụ `ConstraintTeacherMaxHoursDaily::fitness` [`timeconstraint.cpp:13695`](../../../research/fet/fet-7.12.0/src/engine/timeconstraint.cpp#L13695) đếm ngày vượt ngưỡng, trong khi `ConstraintActivityPreferredTimeSlots::fitness` [`timeconstraint.cpp:21020`](../../../research/fet/fet-7.12.0/src/engine/timeconstraint.cpp#L21020) đếm giờ của activity ngoài allowed footprint.

**VERIFIED:** `nConflActivities[slot]` trong search là số **activity phải đẩy/sửa** tại candidate đó; không phải weighted fitness. Sort candidate tăng dần conflict count [`generate.cpp:10200`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L10200), [`generate.cpp:39840`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L39840). Không dùng nhầm ba đại lượng này khi thiết kế objective mới.

**VERIFIED:** 100% mang nghĩa bắt buộc trong generator, nhưng nhiều loại không hỗ trợ phần trăm thấp hơn 100 dù class fitness có công thức tổng quát. `computeTeachersMinHoursDaily` [`generate_pre.cpp:10046`](../../../research/fet/fet-7.12.0/src/engine/generate_pre.cpp#L10046), `computeTeachersMaxGapsPerWeekPercentage` [`generate_pre.cpp:13750`](../../../research/fet/fet-7.12.0/src/engine/generate_pre.cpp#L13750), teacher/student availability [`generate_pre.cpp:16390`](../../../research/fet/fet-7.12.0/src/engine/generate_pre.cpp#L16390), student max gaps [`generate_pre.cpp:15680`](../../../research/fet/fet-7.12.0/src/engine/generate_pre.cpp#L15680) có rejection cụ thể. Ngược lại restriction max-hours-daily cũ yêu cầu 100 đã nằm trong comment, và code hiện tại lưu percentages; [`generate_pre.cpp:8022`](../../../research/fet/fet-7.12.0/src/engine/generate_pre.cpp#L8022). Phân tích bằng grep mà không loại comment sẽ kết luận sai.

## Tạo và sửa conflict

**VERIFIED:** teacher và subgroup phải rảnh trong mọi slot của duration; nếu ô có activity khác có thể di chuyển, thêm activity đó vào ejection set. Activity fixed-time hoặc đã swapped khiến time candidate bị loại; [`generate.cpp:10524`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L10524). Quy tắc room checks tương tự nhưng activity fixed time vẫn có thể đổi room nếu chưa fixed-space; [`generate.cpp:7200`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L7200). Đây là lý do cần phân biệt khóa time/space.

**VERIFIED:** conflicts còn đến từ ràng buộc tổng hợp: quá số giờ, gaps, min-days, building changes, activity tags, selected-slot occupancy. Các nhánh generator tính daily counters trên trạng thái tạm rồi tìm activity có thể bỏ để sửa mức vi phạm. Không có một generic predicate solver duy nhất áp dụng toàn bộ catalog.

**VERIFIED:** `minDaysBetweenActivities` có semantic phụ ngoài percentage: `consecutiveIfSameDay` buộc placement cùng ngày theo điều kiện adjacency; từ version 6.4 có xử lý không quá hai subactivities cùng (real) day trong nhánh liên quan. Code tại [`generate.cpp:10635`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L10635), fitness tại [`timeconstraint.cpp:11729`](../../../research/fet/fet-7.12.0/src/engine/timeconstraint.cpp#L11729). Vì vậy mapping thành mỗi `abs(day_i-day_j)>=k` sẽ thiếu điều kiện.

**INFERRED:** cách thiết kế hữu ích là tách conflict do dùng chung resource khỏi preference và khỏi điều kiện tổng hợp, để giải thích tại sao move không hợp lệ. Không cần tái tạo mọi nhánh FET trong Python để nhận được lợi ích này.

## Randomization và tránh cycling

**VERIFIED:** slot scan shuffle tại [`generate.cpp:10252`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L10252), room list shuffle tại [`generate.cpp:8560`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L8560). Room tie-breaking còn xét số removals, thứ tự và random choice. Random state MRG32k3a được sở hữu bởi generator; CLI nhận 6 thành phần seed [`fetcl.cpp:320`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L320), ghi state trước generate [`fetcl.cpp:4793`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L4793).

**VERIFIED:** root fallback so sánh lexicographic `minWrong`, `nWrong`, số conflicts, `minIndexAct`, rồi chọn ngẫu nhiên trong tập đồng hạng [`generate.cpp:39915`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L39915). `triedRemovals` ghi lịch sử activity/time; tabu dùng circular buffer để giảm lặp lại. Depth, call-budget và tabu là heuristic khống chế tìm kiếm, không phải chứng minh không còn đường khác.

**INFERRED:** học cách ghi seed, stable IDs, canonical input order và lịch sử thay đổi có giá trị hơn việc sao chép hằng depth=14. **UNKNOWN:** depth/call-budget tốt nhất cho vnEdu; chưa có benchmark tham số tương đương.

## Timeout, pause, cancel, restart

**VERIFIED:** `generate(maxSeconds,...)` đo search elapsed bằng `time/difftime`, trừ paused time, so với maxSeconds ở vòng root [`generate.cpp:9044`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L9044). Đây là budget cho search, không phải deadline cứng bao gồm parse/precompute/export. Resolution theo giây; thời gian đầu cuối benchmark khác budget. Một số nhánh dài không kiểm timeout tại mọi instruction.

**VERIFIED:** khi root không có candidate, có vòng retry level-0. Hằng `MAX_RETRIES_FOR_AN_ACTIVITY_AT_LEVEL_0` là **2,000,000,000** [`generate.cpp:133`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L133), không phải giá trị 400,000 ở dòng comment cũ. Trong nhánh này cứ 10,000 retries cập nhật thời gian/progress và kiểm budget [`generate.cpp:39847`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L39847). Có cờ abort/restart và pause handling; `activityRetryLevel0TimeExceeded` được ưu tiên trước `impossibleActivity` [`generate.cpp:9464`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L9464).

**VERIFIED:** CLI cài handler SIGTERM (và SIGBREAK trên Windows) [`fetcl.cpp:4760`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L4760); `terminate` đặt `abortOptimization=true` [`fetcl.cpp:209`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L209). Tài liệu help phân biệt SIGINT dừng ngay, không hứa ghi kết quả [`fetcl.cpp:936`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L936). GUI có semaphore/mutex signaling và pause/restart flags; không được coi cancel đồng nghĩa terminate tiến trình cưỡng bức.

**VERIFIED thử nghiệm:** SIGTERM gửi khi ma582 đang chạy sau khoảng 0.25s: CLI ghi `Generation interrupted`, export current + highest và thoát 0. Evidence [cancel-smoke.json](evidence/cancel-smoke.json). Đây là smoke test một trường hợp, không bảo đảm latency tối đa mọi constraint.

## Kết quả partial, highest và trường hợp khó

**VERIFIED:** full/timeout/impossible/interrupted đi các nhánh export khác nhau trong [`fetcl.cpp:4795`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L4795), [`fetcl.cpp:4951`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L4951), [`fetcl.cpp:5099`](../../../research/fet/fet-7.12.0/src/cl/fetcl.cpp#L5099). Current có thể kém highest về số placed vì đang ở giữa ejection chain. Highest là kỷ lục completion, không bảo đảm ít soft conflicts nhất.

**VERIFIED:** CLI giữ `difficultActivities`, precompute messages, maximum-placed log và conflict reports. Khi `impossibleActivity` set, `generate` điền activity ID và phát `impossibleToSolve` [`generate.cpp:9499`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L9499). **INFERRED:** phải diễn giải như chẩn đoán failure của heuristic/current data, không tự coi là proof toàn bộ bài toán UNSAT. Lỗi cấu trúc hoặc một điều kiện cần mâu thuẫn có thể chứng minh một lỗi cụ thể; điều đó khác chứng minh infeasible của mọi nhánh search.

**VERIFIED benchmark:** file bundled có tên `test-liviu-2-impossible.fet` trả **Time exceeded** trong budget 2s, không trả chứng minh vô nghiệm. Cả complete và timeout đều có exit code 0. Current XML và CSV export count đều ghi 5 activity có time, nhưng một activity chưa allocate room; conflict report vẫn phạt basic compulsory space 10000. Highest-stage được ghi là 4. Ngay cả từ “scheduled” trong export count cũng không đủ để khẳng định lịch current hoàn chỉnh. Room XML trống không đủ để phân biệt unspecified-room hợp lệ với unallocated-space. Chi tiết [07](07-benchmark.md).

**INFERRED — áp dụng:** API solver mới cần status có nghĩa rõ (complete-feasible, partial, cancelled, time-limit, invalid-input và infeasible chỉ khi có căn cứ), completion count, score/bound và diagnostics riêng; không suy status từ exit code, không publish một partial timetable như lịch hoàn chỉnh.
