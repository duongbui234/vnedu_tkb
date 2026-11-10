# Spike: Tauri 2 gọi Scheduling Core đóng gói bằng PyInstaller

**Đây là spike, không phải code sản phẩm.** Kế hoạch:
[2026-11-09-tauri-sidecar-spike.md](../../docs/superpowers/plans/2026-11-09-tauri-sidecar-spike.md)
(đã duyệt TS1–TS6). Không sửa `src/`.

## Thành phần

| Đường dẫn | Vai trò |
|---|---|
| `core/pyinstaller_entry.py` | Entry PyInstaller. Chạy giống `python -m tkb_core.cli`; thêm lệnh `self-check` để kiểm import OR-Tools |
| `src-tauri/` | App Tauri 2 (Rust). Command `run_core`, `cancel_core`, `core_info`; chế độ đo `--auto` |
| `ui/` | Giao diện HTML/JS thuần (TS1), dùng API global của Tauri, không bundler |
| `build.ps1` | Build Core (onedir và onefile) rồi build installer Tauri cho từng kiểu |
| `measure.ps1` | Cài, đo, gỡ từng bản; ghi `results\results-<máy>.json` |

**Cách app gọi Core:**

- Core nằm trong thư mục resource `core\` của bản cài:
  - bản onedir: `core\tkb-core.exe` và `core\_internal\`;
  - bản onefile: chỉ `core\tkb-core.exe`.
- Rust chạy `tkb-core.exe <tham số>` không hiện cửa sổ console (`CREATE_NO_WINDOW`). Input và output là
  file JSON, như CLI.
- Nút Dừng gọi `taskkill /T /F` cho cả cây process. Bản onefile chạy Core trong một process con của
  bootloader, nên phải dừng cả cây.

**Chế độ đo** (`measure.ps1` dùng):

```
"TKB Sidecar Spike.exe" --auto <ket-qua-chay.json> [--cancel-after <giây>] -- <tham số tkb-core>
```

App mở cửa sổ như bình thường, chạy Core một lần, ghi `{exit_code, wall_ms, cancelled, ...}` rồi tự
đóng.

## Chuẩn bị máy Windows 10/11

Cài một lần:

1. **Visual Studio 2022 Build Tools**, workload "Desktop development with C++".
2. **Rust**: `rustup` (toolchain `stable-x86_64-pc-windows-msvc`).
3. **Node.js** LTS (có `npm`).
4. **uv**: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`.
   uv tự cài Python 3.12 theo `uv.lock`.
5. **WebView2 Runtime**: có sẵn trên Windows 11 và Windows 10 đã cập nhật.
6. **Git**, rồi clone repo (nhánh `main`).

Nếu PowerShell chặn script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Chạy

```powershell
cd <repo>\spikes\tauri-sidecar
.\build.ps1                       # khoảng 10–20 phút lần đầu (tải crate Rust, build 2 lần)

# Chép thư mục input (đã ẩn danh, không có trong repo) từ máy Linux:
#   benchmarks/artifacts/real/tauri-spike-inputs/  ->  C:\tkb\inputs\
.\measure.ps1 -Inputs C:\tkb\inputs -Repo <repo>
```

`measure.ps1` chạy lần lượt từng job, không chạy song song: mục tiêu là đo một app trên một máy trường, và
chạy song song sẽ làm sai số RAM và thời gian.

Với 4 worker và 180 s mỗi lần xếp, tổng thời gian khoảng 40–50 phút: 2 bản × 3 trường hợp × (chạy trực
tiếp + qua app), cộng 3 lần chạy từ source. Muốn nhanh hơn thì thêm `-TimeLimit 60`. Bỏ `-Repo` nếu
không cần so với chạy từ source.

Gửi lại hai file `results\results-<máy>.json` và `out\build-info.json`. Không gửi file trong `C:\tkb\`
hay `%TEMP%\tkb-spike-runs\`, vì chúng chứa thời khóa biểu.

## Đo những gì

| Mục trong `results-*.json` | Ý nghĩa |
|---|---|
| `installer_mb` | Kích thước NSIS `.exe` và MSI |
| `installed` | Dung lượng sau khi cài: vỏ, Core, và trong Core là ortools / numpy / pandas / python / khác (bản onedir) |
| `startup_validate_input_ms` | 5 lần `tkb-core validate-input`, đo thời gian khởi động Core |
| `runs[]` | TR38 solve, TR13 solve, TR13 repair; mỗi trường hợp chạy `direct` (exe Core) và `app` (qua Tauri). Gồm thời gian, RAM theo nhóm `shell` / `webview` / `core`, kết quả và mã thoát kiểm tra độc lập |
| `same_as_direct` | Kết quả qua app có cùng status và điểm với chạy Core trực tiếp không |
| `idle_mb` | RAM của app lúc rảnh, gồm cả các process `msedgewebview2.exe` |
| `vietnamese_path` | Chạy với file trong thư mục `Thử nghiệm TKB` (có dấu và dấu cách) |
| `cancel` | Dừng sau 5 s; `core_processes_left` phải bằng 0 |
| `source_cli` | Cùng ba trường hợp chạy bằng `uv run tkb-core` từ source |
| `defender` | Các phát hiện của Windows Defender trong lúc đo (cần quyền đọc) |

**Đơn vị RAM:**

- `sampled_peak_mb`: đỉnh của tổng RAM, lấy mẫu mỗi 0,5 s.
- `process_peak_sum_mb`: tổng đỉnh riêng của từng process.

**Lưu ý:**

- CP-SAT nhiều worker không tất định. Ở mức chưa chứng minh tối ưu, điểm có thể khác giữa hai lần chạy
  dù cùng seed. Khi so kết quả, xem `optimal_prefix`: chỉ các mức đã chứng minh tối ưu mới phải trùng
  nhau.
- Kiểu đóng gói: PyInstaller 6.16.0, chỉ gom những gì Core import, cộng metadata của `ortools` và
  `pydantic`. Nếu `self-check` lỗi, `build.ps1` tự build lại với `--collect-all ortools` và ghi vào
  `build-info.json`. Trên Linux, bản gọn nặng 173 MB, bản `--collect-all` nặng 249 MB. Trên Windows 11,
  bản gọn không tìm được DLL của OR-Tools, nên cả hai kiểu đều phải dùng `--collect-all`
  ([báo cáo](../../docs/tauri-sidecar-spike-report.md)). PyInstaller
  6.11.1 không chạy được với numpy 2.5.
