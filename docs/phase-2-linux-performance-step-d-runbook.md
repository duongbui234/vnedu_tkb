# Phase 2 hiệu năng v2 — runbook bước D (sinh bundle + preflight) trên Linux

Ngày 2026-11-05. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-05; chưa chạy.** Dùng cho bước D của
[kế hoạch v2](superpowers/plans/2026-11-05-phase-2-linux-performance-v2.md) (§5 bước 1–2, §8).

**Mã nguồn: ghim commit `86f624d`** (`86f624df1600f95f1222bc6c7e81f96b43e6c8e1`) theo P3-1 của
[đặc tả Phase 3](superpowers/specs/2026-11-05-phase-3-repair-diagnostics-design.md). Commit này có đủ
tooling v2 và bản sửa R1, chưa có code Phase 3. Không dùng `origin/main` mới nhất, vì từ khi Phase 3 bắt
đầu `main` sẽ có thay đổi trong `src/`, làm số đo lẫn code mới. D, E, F phải cùng commit này. Mọi chỗ
dưới đây gọi đó là "commit ghim". Các bản trước của runbook ghi `15d7578` (thiếu R1), rồi `origin/main`
(không còn đúng sau P3-1).

Đọc runbook này từ `main` trên GitHub. Sau `git checkout --detach 86f624d`, file runbook trong thư mục
làm việc là bản cũ, chưa có đoạn ghim commit này.

Bước D **chỉ** gồm hai việc: sinh bundle 72 dataset, rồi chạy preflight trên wheel đã cài. Không có bước
nào ở đây gọi `prepare`, seal, warmup, pilot hay primary. Duyệt runbook này không phải ủy quyền chạy các
bước đó. Mọi output nằm dưới `benchmarks/artifacts/` (đã được `.gitignore`); không commit chúng.

## 1. Điều kiện máy

| Yêu cầu | Lý do / nguồn |
|---|---|
| Linux x86_64 native (không WSL), cùng máy dự định chạy campaign (G9) | `preflight` từ chối nền tảng khác Linux; số đo P sau này phải trên cùng máy |
| Python 3.12 (`.python-version`) qua `uv`; cloud đã dùng `uv 0.11.32` | `preflight` đòi đúng 3.12 |
| `git` có trong PATH; repo là clone git, **working tree sạch** tại commit ghim | Probe so từng byte wheel đã cài với `src/` và ghi `git rev-parse` |
| Mạng tới PyPI | Hai venv cài dependency từ `uv export --locked` với `--require-hashes --only-binary :all:` |
| Đĩa trống ≥ 3 GiB | Bundle, hai venv, wheel, log |
| **cgroup v2**: `stat -fc %T /sys/fs/cgroup` in ra `cgroup2fs` (R2) | Gate headroom của prepare/run (bước E) chỉ chấp nhận cgroup2 có memory controller; diễn tập E0 trên cloud (cgroup v1) bị chặn ở đây. Bước D không cần, nhưng kiểm ngay để không phí công |
| Không chạy workload nặng khác trong lúc chạy | Preflight không phải phép đo, nhưng máy nên ở trạng thái như khi chạy campaign |

## 2. Lệnh

Chạy từng lệnh từ thư mục gốc của repo. Không đổi tham số; mỗi lần chạy lại phải dùng thư mục output mới.

1. Lấy đúng mã nguồn:

```bash
git fetch origin main
```

```bash
git checkout --detach 86f624d
```

```bash
git rev-parse HEAD
```

```bash
git status --porcelain
```

```bash
stat -fc %T /sys/fs/cgroup
```

`git rev-parse HEAD` phải in `86f624df1600f95f1222bc6c7e81f96b43e6c8e1`. `git status
--porcelain` phải không in gì. Lệnh `stat` phải in `cgroup2fs`. Sai bất kỳ điều nào thì dừng lại (§4).

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

5. Chạy preflight. Bước này tự build wheel từ commit ghim, tạo hai venv (có và không OR-Tools), chạy
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
- `git_commit` trùng commit ghim; bundle có 72 dataset;
- hash wheel và bundle khớp với output lệnh 4 và 6;
- log không có check nào bị timeout hay exit khác 0.

Kết quả sẽ được ghi vào tài liệu báo cáo khi anh/chị cho phép.

## 4. Điều kiện dừng

Dừng, giữ nguyên thư mục và gửi lại log khi gặp bất kỳ trường hợp nào sau đây:

- `git status --porcelain` có in ra gì, HEAD khác `86f624d…`, hoặc `/sys/fs/cgroup` không phải
  `cgroup2fs`.
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
- Nếu Core hoặc generator thay đổi sau commit ghim, bundle cũ hết hiệu lực (kiểm bằng sinh lại) và phải sinh
  lại từ đầu.

## 6. Kiểm tra khi soạn runbook

Chỉ đọc source và kiểm `--help` của `benchmarks.generate_phase2` và `benchmarks.run_phase2` trên cloud.
Chưa chạy lệnh 3–6 ở bất kỳ đâu. Thời lượng nêu trên là số quan sát trên container cloud, không phải phép
đo trên máy anh/chị.
