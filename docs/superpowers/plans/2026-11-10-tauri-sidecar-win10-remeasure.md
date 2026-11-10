# Spike: đo lại Tauri 2 + Core onedir trên máy Windows 10 giống máy trường

Ngày 2026-11-10. Trạng thái: **KHÔNG LÀM.** Ngày 2026-11-10, người dùng quyết định không đo trên
Windows 10, nên W1–W7 không được duyệt. Kế hoạch được giữ lại để tham khảo nếu sau này cần đo máy
khác. Base `2176d86` trên `main`.

**Bối cảnh:** [spike lần đầu](2026-11-09-tauri-sidecar-spike.md) mới đo trên một máy Windows 11 mạnh
(i5-12500, 12 luồng, 16 GB RAM). Kết quả nằm trong [báo cáo](../../tauri-sidecar-spike-report.md). Đóng
gói onedir đã được duyệt cho Phase 4. Báo cáo còn để ngỏ bốn việc:

- đo trên Windows 10;
- đo trên máy giống máy trường (4–8 luồng, 8 GB RAM);
- kiểm SmartScreen;
- kiểm cửa sổ console.

Kế hoạch này chỉ làm bốn việc đó, không đổi Core hay app.

## 1. Câu hỏi

1. Trên Windows 10 và máy cấu hình thấp, bản onedir có cho kết quả như Windows 11 không: cùng status,
   lịch hợp lệ, các mức đã chứng minh tối ưu trùng nhau?
2. Với 8 GB RAM, đỉnh khoảng 1,1 GB khi repair TR13 qua app có gây thiếu RAM hay dùng swap không? Lúc
   đó máy còn bao nhiêu RAM trống?
3. Với 4–8 luồng, 4 worker của Core cộng với app và WebView2 làm thời gian và chất lượng thay đổi thế
   nào?
4. Khởi động Core (`validate-input`) và RAM app lúc rảnh trên máy yếu là bao nhiêu?
5. Bộ cài chưa ký số, khi tải qua trình duyệt, SmartScreen báo gì? Người dùng ở trường vượt qua được
   không?
6. Khi app gọi Core, có cửa sổ console nào bật lên không?

Ngoài phạm vi:

- Ký số, tự cập nhật, UI thật.
- Bản onefile.
- Sửa lỗi Core vẫn chạy khi đóng cửa sổ app (báo cáo §4.3). Việc này để cho Phase 4.

## 2. Cách làm

**Build một lần, trên máy Windows 11 đã có công cụ.** Máy đo không cần Rust, Node, VS Build Tools hay
uv.

- Chạy `build.ps1` trên `main` hiện tại, bản có sửa lỗi stdout UTF-8.
- Mang sang máy Windows 10 cả thư mục `spikes/tauri-sidecar/`, trừ `build/`, `node_modules/` và
  `src-tauri/target/`. Thư mục này gồm `measure.ps1`, `out/onedir/` và `out/build-info.json`.
- Mang thêm 5 file input đã ẩn danh, như lần trước.
- Bộ cài không chứa dữ liệu trường, nên chuyển qua kênh nào cũng được.

**Đo trên máy Windows 10:**

```powershell
.\measure.ps1 -Inputs C:\tkb\inputs -Variants onedir
```

- Giữ nguyên 4 worker, 180 s và seed 42 (TS3), để so được với Windows 11.
- Bỏ `-Repo`: máy trường không có source, và lần trước đã so với chạy từ source rồi.
- Thời gian ước tính: khoảng 25–30 phút.

**Bổ sung vào `measure.ps1`** (chỉ sửa code spike, không đụng `src/`):

| Số đo mới | Cách đo |
|---|---|
| RAM trống của máy | `FreePhysicalMemory` và commit charge (`Win32_OperatingSystem`), lấy mẫu cùng lúc với RAM của app. Ghi giá trị thấp nhất trong mỗi lần chạy |
| Page fault | Tổng `PageFaults/sec` của cây process Core, để biết có dùng swap không |
| Cửa sổ console | Trong lúc chạy qua app, tìm các process `conhost.exe` / `cmd.exe` / `tkb-core.exe` trong cây có cửa sổ hiện lên (`MainWindowHandle` khác 0 và `IsWindowVisible`). Ghi `console_windows_seen` |

Trước khi mang sang máy Windows 10, thử `measure.ps1` đã sửa trên máy Windows 11 bằng **Windows
PowerShell 5.1** (`powershell.exe`). Windows 10 mặc định chỉ có bản này, mà lần trước script chạy bằng
PowerShell 7.

**SmartScreen** (kiểm bằng tay, có ảnh chụp màn hình):

1. Đưa `out/onedir/*-setup.exe` lên một nơi tải được qua trình duyệt, ví dụ Google Drive riêng tư của
   người dùng.
2. Trên máy Windows 10, tải bằng Edge, rồi chạy file.
3. Ghi lại:
   - cảnh báo của trình duyệt khi tải;
   - hộp thoại "Windows protected your PC";
   - các bước cần bấm để cài ("More info" → "Run anyway");
   - Defender có chặn hay xóa file không.
4. Gỡ app sau khi kiểm, rồi mới chạy `measure.ps1`. Script tự cài lại bộ cài trong `out/`, file này
   không mang Mark-of-the-Web.

**WebView2:** bộ cài dùng `downloadBootstrapper`. Nếu máy Windows 10 chưa có WebView2 Runtime, trình
cài sẽ tải nó về, nên lúc cài máy cần có mạng. Ghi lại phiên bản WebView2 trước khi cài. Nếu phải tải
WebView2 trong lúc cài, ghi luôn thời gian cài.

## 3. Các bước

| Bước | Việc | Ai làm |
|---|---|---|
| W-S1 | Thêm 3 số đo mới vào `measure.ps1`. Thử bằng PowerShell 5.1 và 7 trên máy Windows 11 với `-Variants onedir -TimeLimit 30`. Build lại onedir | Tôi |
| W-S2 | Đóng gói thư mục mang sang máy đo, kèm hướng dẫn ngắn (tiếng Việt) | Tôi |
| W-S3 | Trên máy Windows 10: kiểm SmartScreen, chạy `measure.ps1`, gửi lại `results-<máy>.json` và ảnh chụp SmartScreen | Người dùng |
| W-S4 | Bổ sung báo cáo spike: bảng so sánh Windows 11 và Windows 10, trả lời §1 | Tôi |

## 4. Đạt khi

- Bản onedir trên Windows 10 ra kết quả hợp lệ ở cả 3 trường hợp, trực tiếp lẫn qua app. Mã thoát qua
  app là 0, riêng lần thử Dừng là 1. Không còn process Core sót lại.
- Ghi được đủ số đo ở §2, cộng thêm RAM trống thấp nhất và page fault.
- Kiểm được SmartScreen và cửa sổ console. Nếu có vướng mắc, ghi rõ cách xử lý.

Không đặt ngưỡng thời gian hay RAM. Nếu RAM trống xuống dưới khoảng 500 MB, hoặc page fault tăng mạnh,
thì ghi đó là rủi ro cho Phase 4. Không tự giảm worker hay thời gian để chạy cho lọt.

## 5. Rủi ro

- **Không có máy Windows 10 giống máy trường.** Khi đó dùng máy Windows 10 bất kỳ, hoặc máy Windows 11
  cấu hình thấp, và ghi rõ máy nào thiếu ý nào (W6).
- **Máy đo đang chạy việc khác** (antivirus quét, Windows Update) làm sai số RAM và thời gian. Cắm sạc,
  đóng các app khác, ghi chế độ điện. Script đã tự ghi chế độ điện.
- **4 worker trên máy 4 luồng** chiếm hết CPU, nên giao diện app có thể giật. Đây đúng là điều cần đo,
  không đổi cấu hình.
- **n = 1 mỗi máy:** số đo chỉ để định hướng, không phải benchmark.
- **Ảnh chụp SmartScreen:** chỉ chụp hộp thoại, không chụp thư mục hay màn hình có dữ liệu trường.

## 6. Quyết định cần duyệt

| # | Quyết định | Đề xuất |
|---|---|---|
| W1 | Bản đo | Chỉ onedir |
| W2 | Nơi build | Máy Windows 11 hiện tại; máy Windows 10 chỉ cài và đo |
| W3 | Cấu hình Core | Giữ 4 worker, 180 s, seed 42; cùng TR38, TR13 và repair TR13 |
| W4 | Sửa `measure.ps1` | Thêm RAM trống, page fault, phát hiện cửa sổ console; thử cả PowerShell 5.1 |
| W5 | SmartScreen | Kiểm bằng tay qua Edge, có ảnh chụp; không ký số |
| W6 | Máy đo | Windows 10, 4–8 luồng, 8 GB RAM; nếu không có thì dùng máy gần nhất và ghi rõ |
| W7 | Chạy từ source | Bỏ (`-Repo` để trống) trên máy Windows 10 |
