# Spike: Tauri 2 gọi Core đóng gói bằng PyInstaller trên Windows

Ngày 2026-11-09. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-09 (TS1–TS6 theo đề xuất).** Base `02250f2`
trên `main`. S2–S4 đã làm trên một máy Windows 11 ngày 2026-11-10:
[báo cáo](../../tauri-sidecar-spike-report.md). Chưa đo Windows 10 hay máy giống máy trường.

**Bối cảnh:** người dùng chọn Tauri 2 thay Electron
([đặc tả Core First §1.3](../../VNEDU_TKB_CORE_FIRST_CODEX.md)). Máy ở trường chạy Windows 10/11.
Spike này kiểm cách tích hợp trước khi lên kế hoạch Phase 4, và lấy số đo thật.

## 1. Câu hỏi

1. Core đóng gói bằng PyInstaller có chạy được trên Windows 10/11 như sidecar của Tauri 2 không? Kết quả
   có giống hệt khi chạy CLI từ source không?
2. Bộ cài và bản cài nặng bao nhiêu? Phần nào chiếm nhiều nhất: vỏ Tauri, Python hay OR-Tools?
3. Tốn bao nhiêu RAM:
   - vỏ ứng dụng lúc rảnh, tính cả các process WebView2;
   - lúc Core đang xếp một trường lớn.
4. Chạy qua app có chậm hơn chạy CLI trực tiếp không? Khởi động Core mất bao lâu?
5. Có vướng gì khi dùng thật không: antivirus chặn, cửa sổ console bật lên, đường dẫn có dấu tiếng Việt
   hoặc dấu cách, dừng job giữa chừng?

Ngoài phạm vi: UI thật, SQLite, API vnEdu, ký số, tự cập nhật, so sánh với Electron.

## 2. Cách làm

**App spike** (thư mục mới `spikes/tauri-sidecar/`, không phải code sản phẩm):

- Tauri 2 với giao diện HTML/TypeScript thuần, không React. Giao diện chỉ để đo phần vỏ, React thêm rất
  ít.
- Một màn hình gồm: chọn file input, nút Xếp, nút Dừng, nhãn trạng thái và thời gian.
- Rust có hai command:
  - `solve`: chạy sidecar `tkb-core solve <input> --output <file> --workers 4 --time-limit 180 --seed 42`
    và trả về status cùng điểm;
  - `cancel`: dừng sidecar cùng các process con.
- Sidecar khai báo qua `bundle.externalBin`, chạy không hiện cửa sổ console.

**Core đóng gói:**

- PyInstaller, entry `tkb_core.cli`.
- Gom toàn bộ thư viện native của OR-Tools (`--collect-all ortools`).
- Build hai kiểu để so sánh:
  - `--onedir`: một thư mục, khởi động nhanh;
  - `--onefile`: một file, nhưng mỗi lần chạy phải giải nén vào thư mục tạm.
- Pin đúng phiên bản trong `uv.lock`.

**Input** (đã ẩn danh, chép sang máy Windows; không commit):

- TR38 (18 lớp) và TR13 (47 lớp), lấy từ `benchmarks/artifacts/real/stkb-v5-soft/`;
- thêm một repair: kịch bản A của TR13.

**Đo trên mỗi máy Windows:**

| Số đo | Cách đo |
|---|---|
| Dung lượng bộ cài (NSIS `.exe`, MSI) | Kích thước file |
| Dung lượng sau khi cài | Tổng thư mục cài, tách riêng vỏ, Python runtime và OR-Tools |
| RAM vỏ lúc rảnh | Tổng working set của app cùng mọi `msedgewebview2.exe` con, 30 s sau khi mở |
| RAM đỉnh lúc xếp | Peak working set của sidecar; RAM vỏ trong lúc chạy |
| Thời gian | Wall time qua app so với `tkb-core` chạy từ source (`uv run`) và chạy exe đóng gói trực tiếp |
| Khởi động Core | Thời gian chạy `tkb-core validate-input` (onedir so với onefile) |
| Đúng kết quả | Status, điểm `[P1, P2, P3]` và `validate-schedule` của kết quả qua app so với chạy CLI |
| Vướng mắc | Windows Defender/SmartScreen, console, đường dẫn tiếng Việt có dấu cách, nút Dừng có dừng hết process không |

Script PowerShell `measure.ps1` chạy toàn bộ phép đo và ghi `results.json`, kèm thông tin máy: phiên bản
Windows, CPU, số luồng, RAM, phiên bản WebView2.

## 3. Các bước

| Bước | Việc | Ai làm |
|---|---|---|
| S1 | Viết app spike, script build `build.ps1` và `measure.ps1`, kèm hướng dẫn cài công cụ. Kiểm build được trên Linux nếu làm được | Tôi |
| S2 | Cài Rust, Node, Python 3.12/uv, VS Build Tools trên máy Windows; chạy `build.ps1` | Người dùng |
| S3 | Chạy `measure.ps1` trên 1–2 máy: Windows 10 và Windows 11, tốt nhất có một máy giống máy trường (4–8 luồng, 8 GB RAM). Gửi lại `results.json` | Người dùng |
| S4 | Báo cáo ngắn: số đo, vướng mắc, chọn onedir hay onefile, việc cần làm trước Phase 4 | Tôi |

## 4. Đạt khi

- App chạy được Core trên Windows 10/11 và ra kết quả giống hệt CLI: cùng status, cùng điểm, lịch hợp
  lệ.
- Ghi được đủ số đo ở §2.
- Không có vướng mắc nào chặn việc dùng thật. Nếu có, ghi rõ cách xử lý.

Không đặt ngưỡng dung lượng hay RAM. Số đo dùng để lên kế hoạch Phase 4.

## 5. Rủi ro

- **PyInstaller + OR-Tools:** OR-Tools có thư viện native (DLL). Thiếu `--collect-all` thì exe lỗi lúc
  import. Nếu PyInstaller không gom được thì thử Nuitka; ghi lại nếu phải đổi.
- **Antivirus:** exe PyInstaller chưa ký hay bị Defender nghi ngờ, nhất là bản onefile. Spike chỉ ghi
  nhận, chưa ký số.
- **RAM của WebView2:** nằm ở các process `msedgewebview2.exe` riêng. Nếu chỉ đo process app thì số RAM
  thấp giả.
- **Một máy, n = 1:** số đo chỉ để định hướng, không phải benchmark.

## 6. Quyết định cần duyệt

| # | Quyết định | Đề xuất |
|---|---|---|
| TS1 | Giao diện spike | HTML/TS thuần (React để Phase 4) |
| TS2 | Kiểu đóng gói | Build và đo cả onedir lẫn onefile |
| TS3 | Cấu hình Core | 4 worker, 180 s, seed 42; input TR38, TR13 và một repair của TR13 |
| TS4 | Nơi để code spike | `spikes/tauri-sidecar/`, commit lên `main`, ghi rõ là spike. Input thật không commit |
| TS5 | Ký số, tự cập nhật | Không làm trong spike |
| TS6 | Máy đo | Máy Windows của người dùng; thêm một máy cấu hình giống máy trường nếu có |
