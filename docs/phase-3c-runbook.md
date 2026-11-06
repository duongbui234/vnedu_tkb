# Phase 3C — runbook campaign benchmark repair trên Linux (`phase3c-linux-01`)

Ngày 2026-11-06. Trạng thái: **DRAFT — chờ người dùng duyệt; chưa chạy.** Đây là phần thao tác (bước C)
của [kế hoạch 3C](superpowers/plans/2026-11-06-phase-3c-repair-benchmark.md) (C1–C10 đã duyệt). Tooling và
sai khác: [báo cáo tooling 3C](phase-3c-tooling-report.md).

**Mã nguồn: commit ghim `1ab0764`** (`1ab076400fe39d3b53b7eb45a7759ccb55bf8674`).
Đọc runbook này từ `main` trên GitHub; worktree chạy ở commit ghim không có bản runbook này.

Duyệt runbook **không** phải cho phép chạy. Mỗi bước D, E, F cần một lệnh cho phép riêng. Mọi output nằm
dưới `benchmarks/artifacts/` (đã `.gitignore`); không commit chúng.

## 0. Tóm tắt

| Bước | Nội dung | Thời gian ước lượng | Cần cho phép |
|---|---|---|---|
| D | Worktree sạch ở commit ghim, sinh bundle v2, preflight v2 | 15–25 phút | Có |
| E | Pilot harness: campaign smoke `phase3c-linux-01-pilot` (budget 5 s) trên chính máy đo | 5–10 phút | Có |
| F | Campaign đầy đủ `phase3c-linux-01`: prepare → S → derive → R → X → aggregate | **7–12 giờ liền** | Có, sau khi xem E |

**Sai khác so với kế hoạch §8 (bước E):** tooling không có chế độ pilot với budget thật. Bước E chạy chế độ
`--smoke` (2 dataset 10 lớp, 2 run R1, 2 run X, budget 5 s) trên máy đo để kiểm harness, identity và gate.
Giống pilot v2, đây là phép kiểm harness, **không** phải mẫu đo; kết quả E không vào báo cáo số liệu.

## 1. Bước D — chuẩn bị (chạy từ thư mục gốc của checkout chính)

### D1. Worktree sạch ở commit ghim

```bash
git fetch origin
```

```bash
git worktree add .worktrees/phase3c-run 1ab0764
```

```bash
cd .worktrees/phase3c-run && git rev-parse HEAD && git status --porcelain
```

Điều kiện đi tiếp: `rev-parse` in đúng `1ab076400fe39d3b53b7eb45a7759ccb55bf8674`, `status --porcelain` không in
gì. Từ đây **mọi lệnh chạy trong `.worktrees/phase3c-run`**.

### D2. Kiểm máy

```bash
stat -fc %T /sys/fs/cgroup
```

```bash
grep MemAvailable /proc/meminfo
```

```bash
df -h benchmarks
```

```bash
cat "$(git rev-parse --git-common-dir)/tkb-campaign-owner/active.json"
```

```bash
command -v tmux systemd-inhibit
```

Điều kiện: `cgroup2fs`; `MemAvailable` ≥ 6 291 456 kB (cỡ 40 lớp: target 4 GiB + reserve 2 GiB); đĩa trống
≥ 2 GiB; owner `"state": "IDLE"`; có cả `tmux` và `systemd-inhibit`.

### D3. Bundle và preflight

```bash
uv sync --locked --extra solver
```

```bash
uv run --extra solver python -m benchmarks.generate_phase2 --output benchmarks/artifacts/phase3c/bundle; echo "exit=$?"
```

```bash
uv run --extra solver python -m benchmarks.run_phase2 --phase preflight --output benchmarks/artifacts/phase3c/preflight --bundle benchmarks/artifacts/phase3c/bundle; echo "exit=$?"
```

Kỳ vọng: bundle `exit=0`; preflight in `{"status": "PREFLIGHT_PASS", "protocol": "phase2-linux-v2"}` và
`exit=0` (chạy lại toàn bộ test, build wheel, dựng hai venv, kiểm bundle; khoảng 10–20 phút).

```bash
sha256sum benchmarks/artifacts/phase3c/preflight/distribution/*.whl benchmarks/artifacts/phase3c/bundle/manifest.json benchmarks/artifacts/phase3c/preflight/preflight-manifest.json
```

Wheel kỳ vọng `7ae89efc8453ac279026fc249f7e1da22d4623e2356441ca837db94697563b98` (cùng `src/` với lúc smoke).
Khác hash thì dừng và gửi lại, không chạy tiếp.

Gửi lại sau D: output của D1–D3 và dòng `sha256sum`.

## 2. Bước E — pilot harness (smoke trên máy đo)

```bash
PY=benchmarks/artifacts/phase3c/preflight/venv-solver/bin/python
```

```bash
PF=benchmarks/artifacts/phase3c/preflight
```

```bash
$PY -m benchmarks.run_phase3c prepare --bundle benchmarks/artifacts/phase3c/bundle --preflight-dir $PF --output benchmarks/artifacts/phase3c/pilot --campaign-id phase3c-linux-01-pilot --machine-id "$(hostname)" --smoke && $PY -m benchmarks.run_phase3c run --plan benchmarks/artifacts/phase3c/pilot/plan.json --preflight-dir $PF --stage S && $PY -m benchmarks.run_phase3c derive --plan benchmarks/artifacts/phase3c/pilot/plan.json --preflight-dir $PF && $PY -m benchmarks.run_phase3c run --plan benchmarks/artifacts/phase3c/pilot/plan.json --preflight-dir $PF --stage R && $PY -m benchmarks.run_phase3c run --plan benchmarks/artifacts/phase3c/pilot/plan.json --preflight-dir $PF --stage X && $PY -m benchmarks.aggregate_phase3c --campaign benchmarks/artifacts/phase3c/pilot --preflight-dir $PF --output benchmarks/artifacts/phase3c/pilot-summary; echo "exit=$?"
```

Kỳ vọng: lần lượt `PREPARED` (4 hàng), ba dòng state `"status":"COMPLETE"`, `DERIVED` (2 hàng),
`SUMMARIZED`, `exit=0`.

```bash
cat benchmarks/artifacts/phase3c/pilot-summary/summary.md
```

Điều kiện để xin mở F: mọi run H PASS hoặc NOT_APPLICABLE (không FAIL), không có `OUTPUT_INVALID`, `CRASH`,
`MEASUREMENT_BLOCKED` hay `ENVIRONMENT_BLOCKED`. Gửi lại `summary.md` và toàn bộ output lệnh trên.

## 3. Bước F — campaign đầy đủ

Chỉ khi E đạt **và** anh/chị cho phép bằng một lệnh riêng.

### F1. Điều kiện máy (giống runbook F của v2)

- cắm sạc; tắt ứng dụng nặng; không dùng máy cho việc nặng suốt thời gian chạy;
- không cập nhật hệ thống; không đóng nắp nếu cấu hình đóng nắp là ngủ;
- kiểm lại D2 ngay trước khi chạy (owner IDLE, RAM, đĩa).

### F2. Prepare (ngoài tmux được, vài phút)

`--reference-plan` trỏ tới plan của campaign-02 trong **checkout chính** (đường dẫn tuyệt đối), để kiểm
36 dataset (18 gốc + 18 UNSAT) trùng byte với bundle v2 đã đo (C2). Nếu mở terminal mới, đặt lại `PY` và
`PF` như ở bước E.

```bash
$PY -m benchmarks.run_phase3c prepare --bundle benchmarks/artifacts/phase3c/bundle --preflight-dir $PF --output benchmarks/artifacts/phase3c/campaign-01 --campaign-id phase3c-linux-01 --machine-id "$(hostname)" --reference-plan /home/ddevtk/code/vnedu_tkb/benchmarks/artifacts/hard-feasibility-no-lp/campaign-02/plan.json; echo "exit=$?"
```

Kỳ vọng: `{"status": "PREPARED", "rows": 54, "smoke": false}` (18 S + 36 X) và `exit=0`. Reference plan có
SHA256 `cf9c5b82cb25997144683b5f22924aff5cb3f432815024671870d466f871e99e`; `REFERENCE_INPUT_DRIFT` → dừng.

### F3. Chạy (tmux + systemd-inhibit)

Mở phiên `tmux` chạy **bash** (lệnh dưới dùng `PIPESTATUS` của bash; zsh không có biến này):

```bash
tmux new -s phase3c bash
```

Trong phiên đó (một dòng, dừng ngay khi một bước không COMPLETE):

```bash
cd ~/code/vnedu_tkb/.worktrees/phase3c-run && PY=benchmarks/artifacts/phase3c/preflight/venv-solver/bin/python && PF=benchmarks/artifacts/phase3c/preflight && C=benchmarks/artifacts/phase3c/campaign-01 && systemd-inhibit --what=idle:sleep --why="phase3c-linux-01" bash -c "$PY -m benchmarks.run_phase3c run --plan $C/plan.json --preflight-dir $PF --stage S && $PY -m benchmarks.run_phase3c derive --plan $C/plan.json --preflight-dir $PF && $PY -m benchmarks.run_phase3c run --plan $C/plan.json --preflight-dir $PF --stage R && $PY -m benchmarks.run_phase3c run --plan $C/plan.json --preflight-dir $PF --stage X" 2>&1 | tee benchmarks/artifacts/phase3c/campaign-01.out; echo "exit=${PIPESTATUS[0]}"
```

Rời phiên: `Ctrl-b` rồi `d`; vào lại: `tmux attach -t phase3c`. **Không bấm Ctrl-C** (run đang chạy thành
CANCELLED, campaign kết thúc).

Kỳ vọng khi xong: state S `COMPLETE` (18), `DERIVED` (số hàng R = 144 + 48 nếu không loại dataset nào;
dataset không có lịch ở S bị loại cùng mọi hàng của nó), state R `COMPLETE`, state X `COMPLETE` (36),
`exit=0`.

| Phần | Run | Trần budget | Trần watchdog |
|---|---:|---:|---:|
| S | 18 | 0,6 h | 1,05 h |
| R (R1 + R2, chưa tính explain theo sau run INFEASIBLE) | 192 | 5,6 h | 10,4 h |
| X | 36 | thường dừng ở precheck | 2,1 h |

### F4. Xem tiến độ (chỉ đọc, terminal khác)

```bash
ls benchmarks/artifacts/phase3c/campaign-01/
```

```bash
cat benchmarks/artifacts/phase3c/campaign-01/state-*.json
```

```bash
grep -c '"TERMINAL"' benchmarks/artifacts/phase3c/campaign-01/journal-R.jsonl
```

Không mở, sửa hay xóa file trong `S/`, `R/`, `X/`, `derived/`.

### F5. Sau khi lệnh kết thúc (dù COMPLETE hay dừng sớm)

```bash
$PY -m benchmarks.aggregate_phase3c --campaign benchmarks/artifacts/phase3c/campaign-01 --preflight-dir $PF --output benchmarks/artifacts/phase3c/summary-01; echo "exit=$?"
```

Kỳ vọng `SUMMARIZED`, `exit=0` (aggregate chỉ đọc các stage đã có receipt).

```bash
tar -czf phase3c-campaign-01.tar.gz -C benchmarks/artifacts/phase3c campaign-01.out summary-01 campaign-01
```

```bash
sha256sum phase3c-campaign-01.tar.gz benchmarks/artifacts/phase3c/campaign-01/plan.json benchmarks/artifacts/phase3c/campaign-01/derived.json benchmarks/artifacts/phase3c/summary-01/summary.json
```

Gửi lại: output F2, dòng cuối và `exit=` của F3 và F5, `summary.md`, output `sha256sum`. Gói tar giữ ở máy
cho tới khi tôi yêu cầu.

## 4. Khi có sự cố

| Tình huống | Làm gì |
|---|---|
| `prepare` in `BLOCKED` (preflight thiếu 3B, `REFERENCE_INPUT_DRIFT`, headroom) | Dừng; gửi lại output; không sửa gì |
| Một stage in `"status":"BLOCKED"` với `ADMISSION_GATE_BLOCKED` | Campaign kết thúc tại đó (3C **không có** `--resume`). Chạy F5, gửi lại. Chạy lại cần ID mới `phase3c-linux-02` và cho phép mới |
| `STOPPED`, `NEEDS_REVIEW`, `CANCELLED` | Không chạy lại, không xóa. Chạy F5, gửi lại |
| `IDENTITY_OR_ORDER_BLOCKED` (drift nguồn, preflight, máy) | Dừng; gửi lại; không sửa file |
| Nhiều repair INFEASIBLE ở TIGHT, hoặc UNKNOWN/watchdog ở 40 lớp | Bình thường với phép đo này (P NOT_MET / NOT_APPLICABLE). Không dừng, không nới gì |
| Ctrl-C, máy ngủ, mất điện | Campaign kết thúc. Chạy F5 (có thể báo lỗi journal), gửi lại |

Không bao giờ sửa code, input, budget, plan hay `derived/`; không chạy riêng từng run bằng tay; không chạy
hai campaign cùng lúc (owner lock dùng chung với v2).

## 5. Sau khi gửi lại

Tôi kiểm toàn vẹn (seal hai tầng, receipts, journal), rồi soạn báo cáo 3C theo §4 của kế hoạch khi được
cho phép (bước G). Phạm vi kết luận theo C10: repair synthetic, một máy Linux, n = 1 mỗi ô; không P95/SLA,
không Windows, Q vẫn REVIEW_REQUIRED.

## 6. Kiểm tra khi soạn runbook

Chỉ đọc tooling ở `1ab0764`, báo cáo tooling và smoke `phase3c-smoke-20261106`. Mọi lệnh trên đã chạy được
trong smoke với `--smoke` (trừ `--reference-plan`, `git worktree add` và việc chạy dưới `tmux` +
`systemd-inhibit`, chưa thử). Thời gian F là ước lượng từ budget, chưa đo. Đường dẫn `--reference-plan` lấy
từ checkout hiện tại; hash của nó đã kiểm khi soạn.
