# Spike Tauri 2 + Core PyInstaller: báo cáo đo trên Windows 11

Ngày 2026-11-10. Bước S3 và S4 của [kế hoạch spike](superpowers/plans/2026-11-09-tauri-sidecar-spike.md)
(TS1–TS6 đã duyệt), **mới đo trên một máy Windows 11**. Kết luận: **trên máy này, app chạy được Core,
kết quả giống chạy CLI, không có vướng mắc nào chặn việc dùng thật.** Để đạt được thì phải sửa một lỗi
của Core (§4.1), và phải gom đủ OR-Tools khi đóng gói (§4.2). Chưa đo trên Windows 10 hay trên máy có cấu
hình giống máy trường. Số đo n = 1, chỉ để định hướng Phase 4, không phải benchmark.

## 1. Cách đo

- **Máy:** i5-12500 (6 nhân, 12 luồng), RAM 15,7 GB, Windows 11 Home build 26300, chế độ điện Balanced,
  WebView2 157.0.4341.42.
- **Build:** commit `8aeb8e5` (`repo_dirty = false`), Rust 1.99.1, Node 26.13.0, tauri-cli 2.12.4,
  PyInstaller 6.16.0. Core trong bản đóng gói: Python 3.12.16, OR-Tools 9.15.6755, pydantic 2.14.1.
- **Lệnh:** `spikes/tauri-sidecar/build.ps1`, rồi `measure.ps1 -Inputs C:\tkb\inputs -Repo <repo>`. Lần
  đo dùng trong báo cáo bắt đầu lúc 2026-11-10 09:28.
- **Cấu hình Core:** 4 worker, 180 s, seed 42. Chạy từng job một: cách chạy này đo đúng một app trên một
  máy, nên không chạy song song.
- **Input:** TR38 solve, TR13 solve và kịch bản A repair của TR13, đã ẩn danh. Input và lịch kết quả để
  ngoài repo. File kết quả đo (`results-DESKTOP-U1KS2B6.json`, `build-info.json`) cũng không commit.
- Lần chạy từ source (`uv run tkb-core`) bỏ biến `PYTHONIOENCODING` khỏi môi trường, để giống một
  terminal bình thường.

## 2. Số đo

| | onedir | onefile |
|---|---|---|
| Bộ cài NSIS / MSI | **45,7** / 62,0 MB | 71,1 / 71,4 MB |
| Dung lượng sau khi cài | 203,9 MB (vỏ 3,1; Core 200,8) | **73,5 MB** (vỏ 3,2; Core 70,3) |
| Thời gian cài im lặng (NSIS) | 5,9 s | 5,6 s |
| Khởi động Core (`validate-input`, trung vị 5 lần) | **0,32 s** | 2,97 s |
| RAM app lúc rảnh (vỏ + WebView2) | 330 MB (23 + 307) | 329 MB (24 + 305) |

Bên trong Core bản onedir: ortools 79,6 MB, pandas 12,9 MB, Python 9,3 MB, numpy 6,3 MB, phần khác
79,0 MB.

**Thời gian và RAM khi xếp** (lấy từ bản onedir; bản onefile chênh dưới 25 MB RAM và vài giây):

| Trường hợp | Chạy exe trực tiếp | Chạy qua app | RAM đỉnh qua app (Core / WebView2 / vỏ) | Kết quả |
|---|---|---|---|---|
| TR38 solve | 183,1 s, 417 MB | 183,4 s, 749 MB | 403 / 320 / 33 MB | FEASIBLE |
| TR13 solve | 187,9 s, 635 MB | 187,8 s, 969 MB | 627 / 329 / 31 MB | FEASIBLE |
| TR13 repair | 61,6 s, 762 MB | 45,3 s, 1106 MB | 758 / 316 / 31 MB | OPTIMAL `[2,6,193]` |

- Chạy qua app **không chậm hơn** chạy trực tiếp. RAM tăng thêm khoảng 340 MB, gần như toàn bộ là
  WebView2.
- TR13 repair chạy mất 45–111 s tùy lần (cả hai lần đo). CP-SAT dừng ngay khi chứng minh được tối ưu, nên
  thời gian dao động.
- Chạy từ source: 183,7 s / 188,3 s / 98,5 s, RAM tương đương bản đóng gói.

**Kết quả có đúng không:** cả 12 lần chạy đóng gói (2 bản × 3 trường hợp × trực tiếp/qua app) và 3 lần
chạy từ source đều cho lịch hợp lệ. `validate-schedule` chạy độc lập đều trả mã 0. Status qua app luôn
trùng với chạy trực tiếp. Mức P3 (chưa chứng minh tối ưu) khác nhau giữa các lần, từ 6 đến 38, vì CP-SAT
nhiều worker không tất định. Các mức đã chứng minh tối ưu (P1, P2) và toàn bộ điểm repair đều trùng
nhau.

**Vướng mắc khi dùng thật:**

| Kiểm tra | Kết quả |
|---|---|
| Đường dẫn `Thử nghiệm TKB` (có dấu và dấu cách) | ✅ cả hai bản, mã 0 |
| Nút Dừng sau 5 s (`taskkill /T /F`) | ✅ còn 0 process Core, cả bản onefile (bootloader + process con) |
| Cửa sổ console bật lên | Chưa kiểm: không đo tự động và không ai ghi nhận khi quan sát. App gọi Core với `CREATE_NO_WINDOW` |
| Windows Defender | Không có phát hiện nào trong lúc đo (`Get-MpThreatDetection` rỗng) |
| SmartScreen | Chưa kiểm: bộ cài chạy im lặng bằng script, không tải qua trình duyệt |

## 3. Chọn onedir hay onefile

**Quyết định: dùng onedir cho Phase 4.** Người dùng đã duyệt ngày 2026-11-10. Lý do:

- Mỗi lần gọi Core khởi động nhanh hơn khoảng 2,6 s. App sẽ gọi Core cho cả `validate-input` và kiểm tra
  kết quả, không chỉ để xếp.
- Bộ cài NSIS nhỏ hơn (45,7 so với 71,1 MB).
- Đổi lại, sau khi cài nặng 204 MB so với 74 MB. Dung lượng đĩa này không đáng ngại với máy trường.
- Bản onefile mỗi lần chạy phải giải nén vào thư mục tạm. Cách này cũng dễ bị antivirus nghi ngờ hơn,
  dù lần đo này Defender không báo gì.

## 4. Phát hiện và việc đã làm

### 4.1 Lỗi Core: stdout không phải UTF-8 trên Windows (đã sửa)

- **Triệu chứng:** mọi lần xếp thành công qua app đều trả mã **2**, dù file kết quả đầy đủ và hợp lệ.
  Chạy Core trực tiếp trong console thì trả mã 0.
- **Nguyên nhân:** app nối stdout của Core vào `NUL`. Trên Windows, khi stdout không phải console,
  Python dùng bảng mã ANSI (cp1252). Core ghi xong file rồi mới `print` JSON có tên tiếng Việt, và lệnh
  in này gây `UnicodeEncodeError`. Đây là một dạng `ValueError`, nên khối xử lý lỗi báo nhầm thành
  `INVALID_INPUT` với mã 2.
- Đặt `PYTHONIOENCODING` không cứu được bản đóng gói, vì PyInstaller không đọc biến môi trường này.
- Lỗi không xuất hiện trên Linux. Nó cũng bị che trong terminal của Claude Code, vì terminal này tự đặt
  `PYTHONIOENCODING=utf-8`.
- **Sửa:** commit `3a24656`. `main()` chuyển stdout sang UTF-8 trước khi in. Có test hồi quy
  `test_solve_prints_utf8_when_stdout_is_not_utf8`, test này ép stdout dùng cp1252 nên chạy được trên mọi
  hệ điều hành.
- **Kết quả đo lại:** cả 8 lần chạy thành công qua app (2 bản × TR38, TR13, repair, đường dẫn tiếng
  Việt) trả mã 0; trước khi sửa đều là 2. Các số đo khác gần như không đổi.
- Còn lại, chưa sửa: nếu việc in ra stdout lỗi vì lý do khác (ví dụ pipe bị đóng) sau khi đã ghi file,
  Core vẫn sẽ báo `INVALID_INPUT`.

### 4.2 Phải gom đủ OR-Tools khi đóng gói

- Bản gọn (chỉ gom những gì Core import) không qua `self-check` trên Windows ở cả hai kiểu đóng gói.
  PyInstaller không tìm thấy `ortools.dll`, `abseil_dll.dll` và `libprotobuf.dll`.
- `build.ps1` tự build lại với `--collect-all ortools`, và bản này chạy được. Trên Linux thì bản gọn
  chạy được.
- Với Phase 4: dùng `--collect-all ortools`, hoặc khai báo đúng các DLL kia rồi đo lại dung lượng.

### 4.3 Đóng cửa sổ app khi Core đang chạy

- Ở lần đo đầu, người dùng đóng cửa sổ app giữa chừng. App thoát nhưng **Core vẫn chạy ngầm**: đến khi
  bị dừng bằng tay, một process còn giữ khoảng 570 MB RAM.
- Spike chỉ dừng Core khi bấm nút Dừng. App thật phải dừng cả cây process Core khi đóng cửa sổ, hoặc
  hỏi lại người dùng trước khi đóng.
- Lần đo đó bị hỏng và đã bỏ. Các số trong báo cáo lấy từ lần đo lại.

### 4.4 Môi trường build và test trên Windows

- Cài bằng winget: VS 2022 Build Tools 17.14 (C++ và Windows SDK 10.0.26100), rustup 1.29.3 (stable
  MSVC), uv 0.13.7.
- `pytest` trên Windows: 1522 passed, 14 skipped, 2 failed. Hai test hỏng là
  `test_output_must_not_overwrite_input[symlink]` và `test_cyclic_output_symlink_is_a_structured_error`.
  Cả hai cần tạo symlink, mà Windows không cho khi không có quyền admin hoặc Developer Mode
  (`WinError 1314`). Hai test này cũng hỏng trên `ad0142b`, trước khi có bản sửa.

## 5. Chưa làm

- Đo trên Windows 10, và trên máy giống máy trường (4–8 luồng, 8 GB RAM). Ngày 2026-11-10, người dùng
  quyết định **không đo Windows 10** ([kế hoạch không làm](superpowers/plans/2026-11-10-tauri-sidecar-win10-remeasure.md)).
  Rủi ro này được chấp nhận và chuyển sang Phase 4. Với RAM 8 GB, đỉnh khoảng 1,1 GB khi repair TR13 qua
  app vẫn chưa được đo trên máy yếu.
- Kiểm SmartScreen khi tải bộ cài qua trình duyệt; bộ cài chưa ký số (TS5).
- Kiểm có cửa sổ console bật lên khi app gọi Core hay không.
