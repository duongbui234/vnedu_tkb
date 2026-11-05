# Phase 2 hiệu năng v2 — runbook bước D (sinh bundle + preflight) trên Linux

Ngày 2026-11-05. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-05; chưa chạy.** Dùng cho bước D của
[kế hoạch v2](superpowers/plans/2026-11-05-phase-2-linux-performance-v2.md) (§5 bước 1–2, §8). Mã nguồn:
commit `15d7578` trên `main`, trùng với nhánh `work/phase2a-operational-completion`.

Bước D **chỉ** gồm hai việc: sinh bundle 72 dataset, rồi chạy preflight trên wheel đã cài. Không có bước
nào ở đây gọi `prepare`, seal, warmup, pilot hay primary. Duyệt runbook này không phải ủy quyền chạy các
bước đó. Mọi output nằm dưới `benchmarks/artifacts/` (đã được `.gitignore`); không commit chúng.

## 1. Điều kiện máy

| Yêu cầu | Lý do / nguồn |
|---|---|
| Linux x86_64 native (không WSL), cùng máy dự định chạy campaign (G9) | `preflight` từ chối nền tảng khác Linux; số đo P sau này phải trên cùng máy |
| Python 3.12 (`.python-version`) qua `uv`; cloud đã dùng `uv 0.11.32` | `preflight` đòi đúng 3.12 |
| `git` có trong PATH; repo là clone git, **working tree sạch** tại `15d7578` | Probe so từng byte wheel đã cài với `src/` và ghi `git rev-parse` |
| Mạng tới PyPI | Hai venv cài dependency từ `uv export --locked` với `--require-hashes --only-binary :all:` |
| Đĩa trống ≥ 3 GiB | Bundle, hai venv, wheel, log |
| Không chạy workload nặng khác trong lúc chạy | Preflight không phải phép đo, nhưng máy nên ở trạng thái như khi chạy campaign |

## 2. Lệnh

Chạy từng lệnh từ thư mục gốc của repo. Không đổi tham số; mỗi lần chạy lại phải dùng thư mục output mới.

1. Lấy đúng mã nguồn:

```bash
git fetch origin main
```

```bash
git checkout --detach 15d7578
```

```bash
git status --porcelain
```

Lệnh cuối phải không in gì. Nếu có in, dừng lại (§4).

2. Đồng bộ môi trường dev theo lock:

```bash
uv sync --locked --extra solver
```

3. Sinh bundle (không solve; bản cloud mất khoảng 2 phút):

```bash
uv run --extra solver python -m benchmarks.generate_phase2 --output benchmarks/artifacts/phase2-v2/bundle
```

Kỳ vọng: exit 0 và một dòng JSON `{"status": "DATASETS_VERIFIED", "protocol": "phase2-linux-v2", "datasets": 72, ...}`.

4. Ghi hash bundle:

```bash
sha256sum benchmarks/artifacts/phase2-v2/bundle/manifest.json
```

5. Chạy preflight. Bước này tự build wheel từ `15d7578`, tạo hai venv (có và không OR-Tools), chạy
   smoke 0.4 và kiểm lại bundle dưới import guard:

```bash
uv run --extra solver python -m benchmarks.run_phase2 --phase preflight --bundle benchmarks/artifacts/phase2-v2/bundle --output benchmarks/artifacts/phase2-v2/preflight-1
```

Kỳ vọng: các dòng `CHECK <tên>` rồi `{"status": "PREFLIGHT_PASS", "protocol": "phase2-linux-v2"}`, exit 0.
Thứ tự check: core-tests, benchmark-tests, lint, format, types, wheel, rồi export, venv, dependencies,
install, pip-check, identity cho từng venv, tiny-solve, policy04-solve, policy04 validate/evaluate cho
từng venv, bundle-verification. Mỗi bước có timeout riêng (1 800 s cho test suite và kiểm bundle). Trên
cloud, riêng full suite mất khoảng 3,5 phút. Thời gian trên máy anh/chị chưa biết và không phải phép đo.

6. Ghi hash wheel và manifest:

```bash
sha256sum benchmarks/artifacts/phase2-v2/preflight-1/distribution/*.whl benchmarks/artifacts/phase2-v2/preflight-1/preflight-manifest.json
```

## 3. Gửi lại để kiểm

Gửi các file và output sau (dán nội dung, hoặc nén thành một file):

- Toàn bộ stdout của lệnh 3 và lệnh 5, cùng exit code (`echo $?` ngay sau mỗi lệnh).
- Output của lệnh 4 và lệnh 6.
- `benchmarks/artifacts/phase2-v2/bundle/manifest.json`.
- Trong `benchmarks/artifacts/phase2-v2/preflight-1/`:
  - `preflight-manifest.json`
  - `environment-solver.json` và `environment-no-solver.json`
  - `smoke/policy04/input.json` và `smoke/policy04/result.json`
  - các file `logs/*.command.json`
  - `.stdout`/`.stderr` của bước bị lỗi, nếu có.

Không cần gửi venv, wheel hay toàn bộ bundle. Các file environment và log chứa đường dẫn máy (tên người
dùng trong home) và phiên bản package; xem trước nếu anh/chị không muốn chia sẻ chi tiết đó.

Tôi sẽ kiểm:

- manifest có `protocol = phase2-linux-v2`, `linux_status = PASS`, `policy04_smoke = PASS` (output 1.5,
  Score 1.2);
- `git_commit` là `15d7578…`; bundle có 72 dataset;
- hash wheel và bundle khớp với output lệnh 4 và 6;
- log không có check nào bị timeout hay exit khác 0.

Kết quả sẽ được ghi vào tài liệu báo cáo khi anh/chị cho phép.

## 4. Điều kiện dừng

Dừng, giữ nguyên thư mục và gửi lại log khi gặp bất kỳ trường hợp nào sau đây:

- `git status --porcelain` có in ra gì, hoặc HEAD khác `15d7578`.
- `uv sync --locked` báo lock lệch, hoặc không tải được dependency.
- Lệnh 3 không ra `DATASETS_VERIFIED` với 72 dataset (ví dụ `DATASET_GENERATION_FAILED`).
- Lệnh 5 in `{"status": "BLOCKED", ...}`, exit khác 0, hoặc một `CHECK` bị treo quá timeout.
- Bất kỳ test nào fail trong core-tests hoặc benchmark-tests.

Khi dừng, **không** sửa code, lock, pins hay test để qua bước, không đổi seed, budget hay đường dẫn để né
lỗi. Không xóa thư mục output bị lỗi; lần chạy lại (nếu tôi đề nghị sau khi xem log) dùng thư mục mới,
ví dụ `preflight-2`, và báo cả hai lần.

## 5. Ngoài phạm vi bước D

- **Không chạy** `--phase prepare`, `warmup`, `pilot` hay `primary`. Các bước đó (E, F) cần ủy quyền riêng
  sau khi preflight được kiểm.
- Preflight PASS chỉ nói rằng tooling, wheel và bundle nhất quán trên máy này. Nó không phải số đo hiệu
  năng, không chứng nhận Windows, không chấp nhận chất lượng lịch.
- Nếu Core hoặc generator thay đổi sau `15d7578`, bundle cũ hết hiệu lực (kiểm bằng sinh lại) và phải sinh
  lại từ đầu.

## 6. Kiểm tra khi soạn runbook

Chỉ đọc source và kiểm `--help` của `benchmarks.generate_phase2` và `benchmarks.run_phase2` trên cloud.
Chưa chạy lệnh 3–6 ở bất kỳ đâu. Thời lượng nêu trên là số quan sát trên container cloud, không phải phép
đo trên máy anh/chị.
