# Phase 2 hiệu năng v2 — runbook bước F (primary 216 run) trên Linux

Ngày 2026-11-05. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-05; chưa chạy.** Đây là phần thao tác của
[kế hoạch bước F](superpowers/plans/2026-11-05-phase-2-linux-performance-step-f.md) (M1–M7 đã duyệt).

**Mã nguồn: commit ghim `86f624d`** (`86f624df1600f95f1222bc6c7e81f96b43e6c8e1`), giống bước D và E (P3-1 của
[đặc tả Phase 3](superpowers/specs/2026-11-05-phase-3-repair-diagnostics-design.md)). Đọc runbook này
từ `main` trên GitHub, vì file trong thư mục làm việc ở `86f624d` là bản cũ.

Chỉ dùng khi **cả ba** điều kiện sau đều đúng (M1):

- [bước E](phase-2-linux-performance-step-e-runbook.md) đã chạy trên chính máy này;
- cả hai pilot đạt;
- anh/chị đã xem tóm tắt pilot và cho phép chạy primary bằng một lệnh riêng.

Duyệt runbook không phải cho phép chạy.

Primary chạy 216 run tuần tự, cần **khoảng 6–10 giờ liền**. Ngắt giữa chừng thực tế là kết thúc campaign
(M2), nên mọi chuẩn bị ở mục 1 nhằm để chạy một mạch. Mọi output nằm dưới `benchmarks/artifacts/` (đã
`.gitignore`); không commit chúng.

## 1. Chuẩn bị

Chạy từ thư mục gốc repo, cùng clone đã dùng ở bước D và E.

Kiểm trạng thái:

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
df -h benchmarks/artifacts
```

```bash
cat benchmarks/artifacts/phase2-v2/campaign-01/campaign-state.json
```

```bash
cat .git/tkb-campaign-owner/active.json
```

```bash
command -v tmux systemd-inhibit
```

Điều kiện để đi tiếp:

- `git rev-parse HEAD` in **`86f624df1600f95f1222bc6c7e81f96b43e6c8e1`** (commit ghim, trùng bước D/E).
- `git status --porcelain` không in gì.
- `stat` in `cgroup2fs`.
- `MemAvailable` ≥ 6 291 456 kB (6 GiB). Cỡ 40 lớp cần target 4 GiB cộng reserve 2 GiB. Thiếu thì gate sẽ
  chặn giữa chừng.
- Đĩa trống ≥ 1 GiB.
- `campaign-state.json` là của **pilot**: `"phase":"pilot"`, `"status":"COMPLETE"`, `"failed":0`.
- Owner marker ở `"state": "IDLE"`.
- Có cả `tmux` và `systemd-inhibit`. Thiếu `tmux` thì cài trước (`sudo apt install tmux`).

Máy (M3):

- cắm sạc;
- tắt các ứng dụng nặng;
- không dùng máy cho việc nặng trong suốt thời gian chạy;
- không cập nhật hệ thống;
- không đóng nắp laptop nếu cấu hình đóng nắp là ngủ (`systemd-inhibit` bên dưới chặn idle/sleep do
  phần mềm, nhưng có thể không chặn hành động đóng nắp tùy cấu hình).

## 2. Chạy

Mở một phiên `tmux`, để đóng terminal hay mất kết nối SSH không làm ngắt campaign:

```bash
tmux new -s phase2-primary
```

Trong phiên đó, chạy primary dưới `systemd-inhibit`:

```bash
systemd-inhibit --what=idle:sleep --why="phase2-v2 primary" benchmarks/artifacts/phase2-v2/preflight-1/venv-solver/bin/python -m benchmarks.run_phase2 --phase primary --plan benchmarks/artifacts/phase2-v2/campaign-01/plan.json --preflight-dir benchmarks/artifacts/phase2-v2/preflight-1 2>&1 | tee benchmarks/artifacts/phase2-v2/primary-01.out; echo "exit=${PIPESTATUS[0]}"
```

Có thể rời phiên mà campaign vẫn chạy: bấm `Ctrl-b` rồi `d`. Vào lại bằng:

```bash
tmux attach -t phase2-primary
```

**Không bấm Ctrl-C** trong phiên này. Ctrl-C đánh dấu run đang chạy là CANCELLED và kết thúc campaign.

Kỳ vọng nếu chạy hết: một dòng JSON với `"phase":"primary"`, `"status":"COMPLETE"`, `"completed":216`,
kèm `exit=0`. `"failed"` có thể lớn hơn 0 (run không có lịch hoặc vượt giới hạn, tức P NOT_MET). Đó là kết
quả đo, không phải lỗi lệnh.

## 3. Xem tiến độ (chỉ đọc, M4)

Từ một terminal khác:

```bash
cat benchmarks/artifacts/phase2-v2/campaign-01/campaign-state.json
```

```bash
grep -c '"TERMINAL"' benchmarks/artifacts/phase2-v2/campaign-01/journal.jsonl
```

Lệnh thứ hai đếm cả warmup và 2 pilot, nên khi xong primary sẽ là 219. Không mở, sửa hay xóa file trong
`campaign-01/primary/`.

## 4. Sau khi lệnh primary kết thúc

Dù kết quả là COMPLETE hay dừng sớm, đều chạy hai lệnh sau.

Tổng hợp ra một thư mục mới, nằm ngoài campaign:

```bash
benchmarks/artifacts/phase2-v2/preflight-1/venv-solver/bin/python -m benchmarks.aggregate_phase2 --campaign benchmarks/artifacts/phase2-v2/campaign-01 --preflight-dir benchmarks/artifacts/phase2-v2/preflight-1 --output benchmarks/artifacts/phase2-v2/summary-01; echo "exit=$?"
```

Kỳ vọng: `{"status": "SUMMARIZED", ...}` và `exit=0`.

Gom file gửi lại (nén, khoảng vài chục MB, không gồm `plan.json` đầy đủ):

```bash
tar -czf phase2-primary-01.tar.gz -C benchmarks/artifacts/phase2-v2 --exclude=campaign-01/plan.json primary-01.out summary-01 campaign-01
```

```bash
sha256sum phase2-primary-01.tar.gz benchmarks/artifacts/phase2-v2/campaign-01/plan.json benchmarks/artifacts/phase2-v2/summary-01/summary.json
```

Gửi lại cho tôi:

- `phase2-primary-01.tar.gz`;
- output của các lệnh kiểm ở mục 1;
- dòng JSON cuối và `exit=` của lệnh primary và lệnh aggregate;
- output của `sha256sum`.

Nếu file quá lớn, gửi `summary-01/` và `primary-01.out` trước, phần còn lại khi tôi yêu cầu.

## 5. Khi có sự cố

| Tình huống | Làm gì |
|---|---|
| Lệnh primary in `BLOCKED` ngay từ đầu (prerequisite, identity, `PREREQUISITE_NOT_PASSED`) | Dừng; gửi lại output; không sửa gì |
| Dừng với `"status":"BLOCKED"` và lý do `ADMISSION_GATE_BLOCKED` (thiếu RAM/đĩa trước một run) | Gửi `campaign-state.json` và `journal.jsonl` trước. Chỉ khi tôi xác nhận gate chặn trước khi run bắt đầu, mới giải phóng RAM/đĩa rồi chạy lại lệnh ở mục 2 **thêm `--resume`** |
| Dừng với `STOPPED` hoặc `NEEDS_REVIEW` | Campaign kết thúc tại đó. **Không** resume, retry hay xóa. Vẫn chạy mục 4 và gửi lại |
| Lỡ Ctrl-C, máy ngủ, mất điện, treo máy | Campaign kết thúc. Không chạy lại. Chạy mục 4 (aggregate có thể báo lỗi journal, cứ gửi lại) |
| Nhiều run không có lịch hoặc vượt giới hạn | Bình thường với một phép đo. Không dừng, không nới gì (M7) |

Không bao giờ sửa code, input, budget, guard hay plan; không chạy riêng từng dataset bằng tay; không chạy
hai campaign cùng lúc. Chạy lại sau một campaign đã kết thúc phải dùng ID mới `phase2-v2-linux-02`, làm
lại prepare và pilot, và cần ủy quyền mới (M2, M5).

## 6. Sau khi gửi lại

Tôi sẽ kiểm toàn vẹn (seal, receipts, journal) và tóm tắt theo §5 của kế hoạch F. Báo cáo
`docs/phase-2-linux-performance-report.md` chỉ được viết khi anh/chị cho phép (M6). Phạm vi kết luận là
"P campaign Linux v2 trên máy này". Đó không phải nghiệm thu hai OS, không phải chất lượng được chấp nhận,
không phải SLA hay P95.

## 7. Kiểm tra khi soạn runbook

Chỉ đọc source và kế hoạch F. Lệnh primary chưa từng chạy ở đâu, kể cả diễn tập E0 (diễn tập dừng sau
pilot). Lệnh aggregate đã chạy được trên campaign diễn tập, với 0 run primary. Hành vi khi bị ngắt, resume
và gate được mô tả theo code, chưa được thử thật.
