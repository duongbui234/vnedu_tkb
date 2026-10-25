# Kế hoạch nghiên cứu FET

Ngày: 2026-10-25. Người dùng đã cung cấp source ở `research/fet/fet-7.12.0/` và archive ở `research/fet/fet-7.12.0.tar.xz`; dùng trực tiếp, không tải lại/copy/move source. Không có mã Scheduling Core/Electron/SQLite trong workspace hiện tại. Không thấy AGENTS.md áp dụng trong các thư mục đã khảo sát.

## Phạm vi và thứ tự

1. Đối chiếu phiên bản/archive SHA-256 với trang tác giả; kiểm tra source tree khớp archive, license và tác giả. Không coi GitHub mirror là nguồn chuẩn.
2. Lần theo CLI/GUI entry → Rules::computeInternalStructure → Generate::precompute → Generate::generate/randomSwap; đọc các cấu trúc Activity/Rules/Solution, preprocess và conflict repair.
3. Lập catalog toàn bộ concrete TimeConstraint/SpaceConstraint; với các nhóm quan trọng đọc cả fitness, preprocessing và enforcement ở generate.cpp. Không đồng nhất weightPercentage với objective CP-SAT.
4. Ghi cụ thể randomization, ordering, retry/recursion limits, partial/highest-stage, timeout/cancellation và giới hạn kết luận infeasible.
5. Build CLI bằng toolchain có sẵn vào `reverse-engineering/fet/build/`, giữ nguyên source. Benchmark ví dụ bundled với seed/budget ghi rõ; lưu logs, CPU/RSS/wall time, số activity xếp được và fitness. Không so tốc độ OR-Tools khi chưa có model/dataset tương đương.
6. Viết bảy báo cáo yêu cầu dưới `docs/research/fet/`; dẫn file/class/function và số dòng từ source có hash cố định. Đánh nhãn VERIFIED / INFERRED / UNKNOWN cho các kết luận.
7. Tổng hợp hướng native/CP-SAT/hybrid và thiết kế đề xuất Python + OR-Tools chạy local, không triển khai.

## Kiểm chứng đầu ra

- Bảy báo cáo tồn tại, dẫn chứng trỏ đúng source và có manifest hash.
- Catalog concrete classes được đếm/đối chiếu với header; phân biệt đầy đủ danh mục và phân tích sâu chọn lọc.
- Benchmark giữ lệnh, seed, exit status, dữ liệu máy, build flags và raw output; timeout không bị gọi là chứng minh vô nghiệm.
- Source tree vẫn khớp archive sau build/thử nghiệm; không sao chép implementation FET vào sản phẩm.
