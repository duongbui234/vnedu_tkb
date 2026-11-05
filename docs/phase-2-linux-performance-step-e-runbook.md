# Phase 2 hiệu năng v2 — runbook bước E (prepare, warmup, pilot) trên Linux

Ngày 2026-11-05. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-05; chưa chạy.** Đây là phần thao tác của
[kế hoạch bước E](superpowers/plans/2026-11-05-phase-2-linux-performance-step-e.md) (E1–E4; K1–K7 đã
duyệt). Chỉ dùng sau khi [bước D](phase-2-linux-performance-step-d-runbook.md) đã PASS trên chính máy này
và kết quả đã được kiểm.

**Mã nguồn: commit ghim `86f624d`** (`86f624df1600f95f1222bc6c7e81f96b43e6c8e1`), giống bước D (P3-1 của
[đặc tả Phase 3](superpowers/specs/2026-11-05-phase-3-repair-diagnostics-design.md)). Không checkout
`main` mới hơn giữa bước D và F. Đọc runbook này từ `main` trên GitHub, vì file trong thư mục làm việc ở
`86f624d` là bản cũ.

Bước E chỉ gồm prepare (không solve), warmup (một bài tiny, không tính là mẫu) và đúng 2 pilot. **Không
chạy `--phase primary`.** Primary (bước F) cần ủy quyền riêng sau khi xem kết quả pilot. Mọi output nằm
dưới `benchmarks/artifacts/` (đã `.gitignore`); không commit chúng.

## 1. Kiểm trước khi chạy

Chạy từ thư mục gốc repo, cùng clone đã dùng ở bước D:

```bash
git rev-parse HEAD
```

```bash
git status --porcelain
```

```bash
stat -fc %T /sys/fs/cgroup
```

```bash
grep MemAvailable /proc/meminfo
```

```bash
ls benchmarks/artifacts/phase2-v2/
```

```bash
cat .git/tkb-campaign-owner/active.json
```

Điều kiện để đi tiếp:

- `git rev-parse HEAD` in **`86f624df1600f95f1222bc6c7e81f96b43e6c8e1`** (commit ghim, trùng bước D).
- `git status --porcelain` không in gì.
- `stat` in `cgroup2fs`.
- `MemAvailable` ≥ 4 194 304 kB (4 GiB). Trước khi chạy, đóng bớt ứng dụng nặng.
- `ls` thấy `bundle`, `preflight-1` và **không** có `campaign-01`.
- Lệnh `cat` báo file không tồn tại, **hoặc** có `"state": "IDLE"`. Trạng thái khác (`RUNNING`,
  `NEEDS_REVIEW`) → dừng, gửi lại nội dung file, không tự xóa.

Máy: cắm sạc; không cập nhật hệ thống từ bước D tới hết bước F (K5). Máy ngủ giữa pilot sẽ làm hỏng run.

## 2. Lệnh

Cả ba lệnh dùng **Python của venv solver đã cài** ở bước D, không dùng `uv run`. Chạy lần lượt, chỉ chạy
lệnh sau khi lệnh trước ra đúng kết quả kỳ vọng (K3). `<tên-máy>` là một tên ngắn tự đặt (chữ, số,
`-`, `_`; bắt đầu bằng chữ hoặc số; tối đa 64 ký tự; không chứa tên thật). Ghi lại tên đó, vì nó nằm trong plan.

**E1 — Prepare** (không solve; kiểm lại bundle nên mất vài phút):

```bash
benchmarks/artifacts/phase2-v2/preflight-1/venv-solver/bin/python -m benchmarks.run_phase2 --phase prepare --bundle benchmarks/artifacts/phase2-v2/bundle --preflight-dir benchmarks/artifacts/phase2-v2/preflight-1 --output benchmarks/artifacts/phase2-v2/campaign-01 --campaign-id phase2-v2-linux-01 --machine-id <tên-máy>; echo "exit=$?"
```

Kỳ vọng: `{"status": "PREPARED", "primary_planned": 216, "pilots": 2}` và `exit=0`.

```bash
sha256sum benchmarks/artifacts/phase2-v2/campaign-01/plan.json benchmarks/artifacts/phase2-v2/campaign-01/seal.json
```

**E2 — Warmup** (vài giây):

```bash
benchmarks/artifacts/phase2-v2/preflight-1/venv-solver/bin/python -m benchmarks.run_phase2 --phase warmup --plan benchmarks/artifacts/phase2-v2/campaign-01/plan.json --preflight-dir benchmarks/artifacts/phase2-v2/preflight-1; echo "exit=$?"
```

Kỳ vọng: một dòng JSON có `"status":"COMPLETE"` và `"failed":0`, kèm `exit=0`.

**E3 — Pilot** (2 run, mỗi run tối đa 60 s solve và 150 s watchdog; trên cloud mất tổng khoảng 2 phút):

```bash
benchmarks/artifacts/phase2-v2/preflight-1/venv-solver/bin/python -m benchmarks.run_phase2 --phase pilot --plan benchmarks/artifacts/phase2-v2/campaign-01/plan.json --preflight-dir benchmarks/artifacts/phase2-v2/preflight-1; echo "exit=$?"
```

Kỳ vọng nếu đạt: `"status":"COMPLETE"`, `"completed":2`, `"failed":0`, kèm `exit=0`. Nếu pilot đầu không
đạt, tooling dừng (`STOPPED`) và không chạy pilot thứ hai. Đó là gate đúng thiết kế, không phải lỗi lệnh.

## 3. Gửi lại để kiểm

Gom file (không gồm `plan.json` đầy đủ, bundle hay venv):

```bash
tar -czf phase2-step-e.tar.gz -C benchmarks/artifacts/phase2-v2 --exclude=campaign-01/plan.json campaign-01
```

Gửi lại cho tôi:

- `phase2-step-e.tar.gz`;
- output của các lệnh ở mục 1;
- stdout và dòng `exit=` của E1, E2, E3;
- output của `sha256sum` sau E1;
- tên máy đã dùng.

`campaign-01/environment.json` chứa hostname, model CPU, dung lượng RAM và hash `/etc/machine-id`. Xem
trước nếu không muốn chia sẻ chi tiết đó.

Tôi sẽ kiểm:

- seal khớp plan và environment; journal đúng thứ tự; không run nào dở dang;
- warmup có lịch hợp lệ;
- với mỗi pilot: harness, verdict H/Q/P/zero, vector score so với witness, thời gian từng giai đoạn,
  launch-to-exit so với 150 s, peak RSS so với 1 GiB, measurement OK.

Kết luận chỉ là "pilot n = 1 mỗi biến thể" và đi kèm đề nghị có mở bước F hay không (K6).

## 4. Điều kiện dừng

Dừng ngay, **giữ nguyên** thư mục `campaign-01` và gửi lại những gì đã có khi gặp bất kỳ trường hợp nào
sau đây:

- Một điều kiện ở mục 1 không đạt.
- E1 in `BLOCKED`. Riêng `PREPARE_HEADROOM_BLOCKED`: đóng bớt ứng dụng rồi chạy lại **đúng** lệnh E1. Bản
  sửa R1 bảo đảm lần bị chặn không để lại output hay marker. Mọi `BLOCKED` khác → gửi lại.
- E2 hoặc E3 trả trạng thái khác `COMPLETE`: `BLOCKED`, `STOPPED`, `NEEDS_REVIEW` hoặc `CANCELLED`.
- Bị ngắt giữa chừng (Ctrl-C, máy ngủ, mất điện).

Khi dừng, **không** retry, không thêm `--resume`, không sửa code, input, budget hay guard, không xóa
`campaign-01`. Campaign đã STOPPED được giữ nguyên làm evidence. Lần sau, nếu có, dùng ID mới
`phase2-v2-linux-02` và cần ủy quyền mới (K4).

## 5. Kiểm tra khi soạn runbook

Chỉ đọc source và kế hoạch bước E. Các lệnh E1–E3 đã chạy được trong diễn tập E0 trên cloud (có shim
headroom do cloud dùng cgroup v1, xem [báo cáo E0](phase-2-linux-performance-rehearsal-e0-report.md)),
nhưng chưa chạy trên máy đích. Thời lượng nêu ở đây là số quan sát trên cloud, không phải dự báo cho máy
anh/chị.
