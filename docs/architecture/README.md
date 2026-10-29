# Kiến trúc Scheduling Core

Mở [sơ đồ tương tác](scheduling-core.html) trực tiếp bằng trình duyệt. HTML độc lập,
không cần server; hỗ trợ tìm nút, xem quan hệ, phóng to, đổi giao diện sáng/tối và xuất ảnh.
Chọn nút để xem nguồn trích dẫn tại commit `9fa179191e35914578e094f7864470c1b4991528`.
Nội dung tiếng Việt; thanh công cụ Viewer và thuộc tính ngôn ngữ HTML dùng tiếng Anh dự phòng.

## Phạm vi và cách đọc

Sơ đồ phản ánh mã nguồn Phase 2A đang có, ở cấp module và luồng xử lý. Các cạnh có nhãn
biểu diễn truyền dữ liệu hoặc phụ thuộc; không phải mọi cạnh đều là lời gọi trực tiếp.
`solve()` điều phối preprocessing, model, CP-SAT và verification, rồi tạo `ScheduleResult`.
CLI sở hữu đọc/ghi JSON. `validate-input`, `validate-schedule`, `evaluate-score` có thể chạy
riêng; core không cần Desktop, SQLite hoặc HTTP.

- `contracts/` và `domain/`: Pydantic, ID, tham chiếu, version, fingerprint.
- `preprocessing/`: occurrence, timeline, placement domains và tiền kiểm điều kiện cần.
- `constraints/`: hard occupancy, registry S01–S04 và biểu thức soft penalty.
- `solver/`: model Boolean thưa, hard solve, tối ưu theo tier và giữ nghiệm đã kiểm định.
- `validation/`: kiểm tra hard và tính lại score từ assignments bằng Python độc lập CP-SAT.
- `benchmarks/`: generator synthetic, bundle/witness, harness và campaign Linux ngoài core.
- `tests/`: unit, integration và oracle vét cạn bài nhỏ; harness có `benchmarks/tests/` riêng.

Phải phân biệt contract hợp lệ, qua precheck, trạng thái solver và kết quả đã được
independent validator xác nhận. Input 1.0 phát output 1.1; input 1.1 phát output 1.2.
Runtime dùng Pydantic 2.14.1; OR-Tools 9.15.6755 thuộc extra `solver`.
Electron/React, SQLite, vnEdu adapter và repair tối thiểu thay đổi chưa được triển khai.
Không sửa core, fixture, dependency, nghiên cứu hoặc dữ liệu reverse engineering trong tác vụ này.

## Tái tạo

`candidate.json` là nguồn sơ đồ; HTML được lưu trong Git để mở trực tiếp mà không cần
Archify. Với kỹ năng Archify đã cài ở `$HOME/.agents/skills/archify`, chạy từ gốc
repository (điều chỉnh đường dẫn công cụ nếu cài ở nơi khác):

```sh
node "$HOME/.agents/skills/archify/bin/archify.mjs" finalize architecture docs/architecture/candidate.json docs/architecture/scheduling-core.html --repo-root "$PWD" --quality showcase --out-dir docs/architecture/review-2 --json
```

Dùng `--out-dir` mới cho mỗi lần tạo lại khi HTML đã có browser evidence.
Các file `scheduling-core.delivery.json`, `scheduling-core.finalize.json`,
`scheduling-core.finalize-summary.json` và `scheduling-core.browser-check.json` ghi nhận
kết quả kiểm tra, nguồn và nhận diện artifact của lần chạy trên máy tạo sơ đồ.
Bốn receipt này được giữ local và ignore theo đúng tên file; không cần để mở HTML.
Thư mục `review-2` trong ví dụ chưa có quy tắc ignore, cần chọn nơi lưu evidence phù hợp
trước khi tái tạo. Nguồn trích dẫn được neo theo commit; cần đối chiếu và cập nhật
candidate khi mã nguồn thay đổi.

## Kiểm chứng ngày 2026-10-27

Các lệnh dự án thực sự đã chạy:

| Lệnh | Kết quả |
| --- | --- |
| `uv sync --locked --extra solver` | Đạt, không đổi dependency |
| `uv run --extra solver pytest` | 232 passed, 4.97s |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check src tests` | 44 files already formatted |
| `uv run mypy` | Không có lỗi trong 27 source files |

Lệnh Archify ngày này dùng cùng các đối số như ví dụ trên nhưng không có `--out-dir`,
với đường dẫn tuyệt đối tới công cụ và repository trên máy tạo sơ đồ.
Validate (9/9), delivery, strict provenance check và automated browser-check đều đạt.
Không có lỗi/cảnh báo bố cục hoặc đường nối cắt nhau. Có cảnh báo locale fallback đã nêu trên.
Đã kiểm tra tự động giao diện sáng/tối và viewport desktop; chưa duyệt hình ảnh bằng mắt.
Không chạy benchmark campaign, bộ test riêng trong `benchmarks/tests/`, hoặc đo hiệu năng.
