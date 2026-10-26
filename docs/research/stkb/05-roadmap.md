# Roadmap ưu tiên — chưa triển khai

**INFERRED — đề xuất thứ tự và tiêu chí**, dựa trên [Gap Analysis](03-phase1-gap-analysis.md). Phase1 feasibility hiện có giữ nguyên. Không tự chuyển sang coding Phase2 khi chỉ hoàn thành nghiên cứu.

| Ưu tiên | Công việc | Điều kiện nghiệm thu | Phụ thuộc/điểm dừng |
|---|---|---|---|
| P0.1 — Chốt nguồn demand | Xác nhận curriculum/local override và đơn vị theo cycle; worksheet unresolved/confirmed-zero/positive; đối soát API association với5GVthiếu và môn-2 | Có mẫu5tiết và patternđơn/đôi đã được giáo vụ xác nhận; không association nào bị tự biến thành0/1; lưu được nguồn và quyết định từng demand | Có thể làm bằng cấu hình/JSON ngoài core; không cần APIghi hoặc UI mới |
| P0.2 — Đóng phần schema STKB cần nhập thật | Theo reader/writer đúng layout84, căn chỉnh từ parsed prefix, map chuẩn/PCGD/remaining/lịch/locks bằng code+offset; độc lập kiểm occupancy và tổng của8file | Reader có boundary checks và fixtures tổng hợp; số liệu trích nhất quán với getters/serializer, không quét đoán offset và gọi là demand | Hiện UNKNOWN. Không hứa importerSTKB thực trước gate này; không để chặn trường nhập định mức đã xác nhận bằng nguồn khác |
| P0.3 — Đối chứng runtime nếu cần | Trên bản sao dữ liệu: tạo mới → chuẩn mặc định → sửa chuẩn/override → importPCGD → lưu → split/lock → generate → reload; lưu before/after diff theo từng thao tác | Chứng minh UI handler được gọi, default runtime/precedence và tác động vào file; tách bản5help/resource4.5 | Chưa có runtime trong nghiên cứu. Chỉ Windows hợp lệ có sẵn, không bypass/activation; không sửa file gốc hay server |
| P0.4 — Chốt policy trường | Lịch ngày/buổi/break, mô hình2buổi, eligibilityphòng, travel, hard/soft, scope và penaltyunit | Rule catalogue có ví dụ đúng/sai nhỏ, precedence không mâu thuẫn; UNKNOWN không thành rule bật mặc định | Không tự lấy95%FET hoặc hệ sốSTKB làm policy |
| P1.1 — Compiler và cấu hình demand | Thiết kế versioned upstream snapshot/worksheet → ScheduleInput, bảo toàn demand/split, mapping IDs/locks; persistence ngoài core được duyệt riêng | Roundtrip input đã xác nhận,5tiết sinh đúng5footprints; sửa pattern phát hiện stale lock; toàn0unknown bị chặn upstream | Không thêm vnEdu schema vào `src/tkb_core`; không cần viết lại normalize hiện có |
| P1.2 — Baseline thực tế có kiểm soát | Dùng input đã xác nhận, Phase1solve+independentvalidator; đoprepare/domain/solve/RAM/status, kiểm lịch với giáo vụ | Đủdemand, hard-valid, không xung đột; ghi phiên bản/inputhash và những rule chưa hỗ trợ; không quảng cáo lịch đủ nghiệp vụ khi customrules chưa bật | Fixtures ẩn danh/tổng hợp; chỉ dùng dữ liệu thật theo phạm vi được phép, không đưa PII vào Git |
| P2 — Rule/quality theo thứ tự nghiệp vụ | Bắt đầu maxmôn/ngày, spacing, tảiGV/ngày/buổi, gaps và sốbuổi/ngàynghỉ theo policy đã chốt; registry/compiler/evaluator độc lập | Mỗi rule có truth table/vét cạn nhỏ, hardreject chính xác, penaltyunit/breakdown đúng; kết quả tốt hơn baseline theo tiêu chí cụ thể trong budget | Vẫn phải test hard-valid sau tối ưu; không gom mọi ruleFET vào một đợt |
| P2.x — Capability mở khi cần | Multi-teacher/lớpghép/subgroups, multiweek, event chung, break profile/alternative split theo nhu cầu đã xác minh | Contract version/capability, prepare/model/validator cùng semantics, backwards tests; không chỉ bỏ guard | Nhu cầu nào chưa có evidence giữ disabled; thứ tự có thể lên trước quality nếu trường thực sự cần |
| P3 — Repair/ít xáo trộn | PreviousSchedule, occurrence remap, neighborhood, hardlocks, objective thayđổi, diff/preview | Giữ lịch ngoài vùng khi có thể, toàn lịch validatorpass; locked-infeasible khác full-infeasible; snapshot cũ không ghi đè snapshot mới | Có stableidentity và ruleboundary trước; mở vùng theo budget |
| P3.b — Benchmark/hybrid | Synthetic và dataset được phép, nhiều seed/size; soCP-SATbaseline với hints/repair và FET khi có semantics tương đương | Có CPU/OS/RAM/workers/budget, thời gianfirst-valid/best, peakRAM, completion/hardviolations/penalty; tính cả timeout | Không xếp hạng nhanh/chậm nếu input/policy/objective khác; chọn tối ưu dựa số đo |
| P4 — Application integration | Worker/cancel/draft/history/SQLite/IPC/Desktop và APIadapter khi được yêu cầu riêng | Input/config/resultversion đi cùng nhau; stale/cancel/crash không publish; export/sync có đối soát và validationgate | Chưa nằm trong lượt này; không APIupdate hiện tại |

## Những kỹ thuật đáng áp dụng

**INFERRED — áp dụng sớm:** STKB có bảng chuẩn→override→PCGD, preview ảnh hưởng cấu hình và thao tác giữ lịch; FET có activities/components rõ, preprocessing/domain, membership-conflict và chẩn đoán vi phạm. Kế thừa Phase1 hard occupancy, sparse placements, capability guard và validator độc lập. Thêm provenance/completeness trước quality.

**INFERRED — sau benchmark:** difficulty ordering làm hint/chọn vùng sửa, cache gia tăng, neighborhoodrepair và LNS/hybrid. Không tự can thiệp searchCP-SAT chỉ để giống thứ tự FET; không viết lại recursive swapping hoặc FPR/DPR trong sản phẩm.

**INFERRED — tránh:** rawso_tiet=0→zero/1; suy định mức từ số PCGD hoặc lịch cũ chưa đủ; tổng weightedscore lấn hard constraints; partial schedule được gọi hoàn chỉnh; inheritdefaultFET/STKB không qua xác nhận; chia bài toán theođiểmtrường khiGV/rules còn chéo.

## Kết thúc lượt nghiên cứu này

**VERIFIED:** Core/fixtures/dependencies không thay đổi; các helper nghiên cứu đọc resource, map30hệsố và kiểm prefix có assert/self-check, kết quả lưu local. Không chạy lại143testsPhase1 trong lượt này, không dùng số test lịch sử làm benchmark mới. Bản đo/test implementation mới chỉ thực hiện khi có code thay đổi hoặc mục tiêu kiểm chứng cụ thể.

**UNKNOWN tiếp tục nghiên cứu:** fullschema `.STKB`, mọi runtimeoverride/precedence, các engine khác SFNew và hiệu năng dữ liệu thật. Chúng có checklist P0.2/P0.3; không che thành tuyên bố REA toàn bộ ứng dụng đã hoàn tất.
