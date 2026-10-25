# 05 — FET native, CP-SAT và hybrid

Đối chiếu FET 7.12.0 có source pin ở [01](01-source-overview.md). Các lựa chọn kiến trúc dưới đây là **INFERRED — đánh giá/đề xuất**, không phải kết quả benchmark tương đương.

## Những điều đã xác nhận

**VERIFIED từ FET:** recursive swapping có depth/call limits [`generate.cpp:9044`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L9044), stochastic enforcement [`generate.cpp:4287`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L4287), ordering [`generate_pre.cpp:26500`](../../../research/fet/fet-7.12.0/src/engine/generate_pre.cpp#L26500), partial/highest-stage và stop conditions [`generate.cpp:9461`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L9461), [`generate.cpp:9595`](../../../research/fet/fet-7.12.0/src/engine/generate.cpp#L9595). `Solution::fitness` có conflict report nhưng tuyến generate không chứng minh global optimality [`solution.cpp:137`](../../../research/fet/fet-7.12.0/src/engine/solution.cpp#L137).

**VERIFIED từ OR-Tools documentation:** CP-SAT là tuyến giải mô hình ràng buộc nguyên, có các trạng thái `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID`, `UNKNOWN` và cung cấp objective/bound. Timeout không đồng nghĩa vô nghiệm. Đây là bảo đảm của solver đối với **mô hình đã encode**, không phải bảo đảm dữ liệu vnEdu đã được mô hình hóa đúng. [Tài liệu CP-SAT](https://developers.google.com/optimization/cp/cp_solver).

**VERIFIED từ API:** có Boolean/integer/interval variables, no-overlap, hints, assumptions và callback/stop interfaces. Hint không phải khóa cứng. [Python cp_model API](https://or-tools.github.io/docs/pdoc/ortools/sat/python/cp_model.html). Solver có tham số liên quan search/LNS trong [sat_parameters.proto](https://github.com/google/or-tools/blob/stable/ortools/sat/sat_parameters.proto); hybrid bên ngoài cần chứng minh lợi ích trước khi thêm một lớp heuristic khác.

## Đánh giá ba hướng

| Tiêu chí | FET native algorithm | Python + CP-SAT | Hybrid: CP-SAT + repair/heuristic |
|---|---|---|---|
| Tính đúng | Engine trưởng thành, có các check chuyên biệt; validator vẫn cần cho adapter/export | Constraint rõ và có solver status/bound; sai model vẫn cho nghiệm sai nghiệp vụ | Mọi move phải validate hoặc repair bằng hard model; nhiều ranh giới để sai |
| Khả năng chứng minh | Không complete search/proof trong tuyến được đọc | Có thể chứng minh infeasible/optimal nếu hoàn tất; không hứa hoàn tất trong budget | Proof chỉ áp dụng model/subproblem thực sự đã solve |
| Hiệu năng | Rất phụ thuộc density và các nhóm constraint; benchmark bundled ở [07](07-benchmark.md) | **UNKNOWN** trên dữ liệu vnEdu; phụ thuộc encoding/domain và workers | **UNKNOWN** lợi ích thêm; repair neighborhood nhỏ có thể giảm chi phí nhưng tăng orchestration |
| Chi phí triển khai | Tái dùng executable cần adapter + license assessment; viết lại recursive engine rất lớn | Hợp kiến trúc Python đã chốt; vẫn cần compiler/validator cho từng rule | Tốn thêm neighborhood selection, freeze boundary, rollback và budget accounting |
| Mở rộng constraint | Thêm class/fitness chưa đủ, cần sửa precompute và branches generator | Thêm rule compiler cùng validator/fixtures, hoặc đổi encoding khi cần | Mỗi rule phải tồn tại trong hard checker và ảnh hưởng neighborhood |
| Xếp lại một phần | Có fixed-time/fixed-space và generation tiếp theo; chưa chứng minh minimal-change objective có sẵn | Freeze equality ngoài vùng sửa; hints cho incumbent; objective minimize changes | Mở vùng theo conflict graph, re-solve có khóa; phải phân biệt infeasible vùng và infeasible toàn bài |
| Soft semantics | Probability enforcement và fitness riêng; nhiều constraints chỉ nhận 100% | Objective/violation là đại lượng đặc tả tường minh | Có thể giữ objective chung nhưng không mặc định tương đương FET |
| Chất lượng nghiệm | Full placement có thể còn soft penalty; highest là số đặt được | Có objective và bound để đánh giá khi tối ưu | Cần cùng evaluator để tránh heuristic và solver dùng hai định nghĩa chất lượng |
| Giấy phép | Source FET AGPLv3, điều kiện phân phối/tích hợp phải đánh giá | Không cần đưa mã FET vào sản phẩm nếu triển khai độc lập từ đặc tả | Phụ thuộc mã thực sự được dùng; tên “hybrid” không giải quyết license |

## Đề xuất trong kiến trúc đã chốt

**INFERRED:** giữ Python + OR-Tools CP-SAT làm nguồn kiểm tra/giải chính, học kỹ thuật của FET ở tầng đặc tả và tiền xử lý: canonical resource IDs, flatten overlapping student groups, shrink domains, fail-fast necessary checks, conflict explanations, fixed placements, reproducible seeds và incumbent snapshots.

Không xây lại FET trong Python. Bản đầu chỉ cần full hard model và mục tiêu mềm có kiểm chứng; từ kết quả đo mới quyết định cần greedy hint hoặc external repair. Một greedy hint thiếu ràng buộc không được publish trước khi validator xác nhận. CP-SAT vốn đã có search heuristics; thêm heuristic ngoài không mặc nhiên nhanh hơn.

**INFERRED:** repair sau này có thể đóng băng lịch ngoài neighborhood, mở các activity liên đới qua teacher/class/room, ưu tiên giảm số thay đổi trước soft quality. Nếu subproblem không có nghiệm, mở rộng vùng hoặc báo vùng khóa mâu thuẫn; không thông báo “cả trường không xếp được”. Đây là hướng thiết kế mới, không tuyên bố FET đang dùng CP-SAT/LNS theo cách này.

## Điều kiện so sánh hiệu năng công bằng

**UNKNOWN:** không có model OR-Tools tương đương trong nhiệm vụ này. Không kết luận FET nhanh/chậm hơn CP-SAT. Benchmark công bằng phải dùng cùng activities/durations/resource sets, khóa, allowable starts/rooms, hard/soft semantics, mục tiêu và budget; ghi toolchain, CPU/threads, seed và preprocessing/export riêng. Không so file FET khóa 511 giờ với bài CP-SAT xếp từ đầu.

So tối thiểu: time-to-first-complete-feasible, tỷ lệ complete ở nhiều seeds, hard violations được checker độc lập đếm, objective cùng thang điểm, bound/gap nếu có, time-to-target-quality, số activity bị thay đổi khi repair và peak RSS. Không dùng tổng FET conflicts có penalty unallocated để so với objective CP-SAT chỉ tính preference.
