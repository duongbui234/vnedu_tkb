# Phase 2 hiệu năng v2 — kế hoạch bước F (primary 216 run)

Ngày 2026-11-05. Trạng thái: **DRAFT — M1–M7 ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT theo đề xuất ngày 2026-11-05; chưa chạy. Chạy primary vẫn cần ủy quyền riêng sau khi bước E đạt.** Thuộc bước F của
[kế hoạch v2](2026-11-05-phase-2-linux-performance-v2.md) (§5 bước 5–6, §8). Bước F tiếp sau
[bước E](2026-11-05-phase-2-linux-performance-step-e.md); tham khảo thêm
[báo cáo diễn tập E0](../../phase-2-linux-performance-rehearsal-e0-report.md).

Tài liệu chỉ là kế hoạch. Lượt soạn không sửa code, không chạy lệnh nào, không commit hay push. Duyệt kế
hoạch không phải ủy quyền chạy primary.

## 0. Điều kiện trước

| Điều kiện | Trạng thái hiện tại |
|---|---|
| Bước D PASS trên máy đích và đã được kiểm | **Chưa có** |
| Bước E trên máy đích: prepare `PREPARED`, warmup `COMPLETE`, **cả hai pilot đạt** (H PASS, có lịch, P MET); kết quả đã được kiểm | **Chưa có** |
| Người dùng xem tóm tắt pilot và ủy quyền chạy primary bằng một lệnh riêng (K6) | **Chưa có** |
| Máy, commit, bundle, preflight và plan không đổi kể từ prepare | Kiểm khi chạy; tooling tự chặn nếu drift |

Tooling cũng tự chặn: primary trả `BLOCKED: PREREQUISITE_NOT_PASSED` nếu warmup hoặc một pilot chưa đạt.

## 1. Hành vi đã xác minh trong source (VERIFIED)

- **Thứ tự:** 216 run chạy tuần tự theo thứ tự đã đóng băng (seed 2026, ba lượt lặp, mỗi lượt 72 dataset
  xáo trộn). Không chạy song song, workers 1, seed 42, guard mặc định.
- **Budget theo cỡ:** 10 lớp 60 s / watchdog 150 s / 1 GiB; 20 lớp 120 s / 210 s / 2 GiB; 40 lớp
  180 s / 270 s / 4 GiB. Trước mỗi run cần reserve 2 GiB.
- **Trước mỗi run:** kiểm lại identity (seal, sources, bundle, preflight, runtime, machine), kiểm headroom
  (cgroup2) và kiểm đĩa trống ≥ 256 MiB. Không đạt → ghi `GATE_BLOCKED` và dừng **trước** khi run bắt
  đầu.
- **Run không làm dừng campaign:** P NOT_MET — tức UNKNOWN, `RESOURCE_LIMIT`, `WATCHDOG_TIMEOUT` hoặc
  `RESOURCE_STOP` khi measurement đủ. Score khác 0, WORSE so witness hay zero NOT_APPLICABLE cũng không
  dừng. Các trường hợp này được ghi lại rồi chạy tiếp.
- **Run làm dừng campaign:**
  - **STOPPED:** H FAIL (gồm UNSAT sai và `OUTPUT_INVALID`), CRASH, MEASUREMENT_BLOCKED,
    ENVIRONMENT_BLOCKED, measurement không OK.
  - **NEEDS_REVIEW:** exit/wait status thiếu, `REAP_UNCONFIRMED`.
  - **CANCELLED:** người dùng ngắt.
- **Ngắt giữa chừng thực tế kết thúc campaign:**
  - Ctrl-C ghi run hiện tại là CANCELLED. Khi resume, run CANCELLED đã có kết quả lại kích hoạt điểm dừng
    `TERMINAL_STOP_RETAINED`, nên **không thể chạy tiếp qua nó**.
  - Mất điện hay máy ngủ giữa run để lại START mà không có TERMINAL → `UNFINISHED_START`, NEEDS_REVIEW.
  - Như v1, chỉ một lần gate chặn *trước* khi run bắt đầu (`GATE_BLOCKED`, ví dụ headroom) mới cho phép
    `--resume` chạy tiếp.
- **Kết quả đã ghi** (terminal receipt có hash) không bị ghi đè hay chạy lại.
- **Dung lượng:** mỗi run khoảng 0,15–1 MB. Cả campaign ước khoảng 50–150 MB, chưa kể bundle (khoảng
  42 MB) và preflight.

## 2. Thời lượng (cấu hình, không phải ước lượng hiệu năng)

| Mục | Giá trị |
|---|---|
| Tổng budget CP-SAT của 162 run known-feasible | 54 × (60 + 120 + 180) s = 19 440 s ≈ **5,4 h** |
| Trần watchdog của 162 run feasible | 54 × (150 + 210 + 270) s = 34 020 s ≈ **9,45 h** |
| 54 run UNSAT | Thường dừng ở precheck (vài giây mỗi run) |
| Overhead mỗi run | Kiểm identity, verify, ghi receipt; trong diễn tập khoảng 1 s |

Diễn tập E0 cho thấy pilot dùng gần hết budget (51–61 s ở cỡ 10). Nên chuẩn bị một khoảng chạy liền
**khoảng 6–10 giờ**. Đây không phải dự báo cho máy đích.

## 3. Lệnh (chỉ chạy khi được ủy quyền bước F)

Chạy từ thư mục gốc repo, trong `tmux` hoặc `screen`, để đóng terminal không làm ngắt campaign. Dùng
`systemd-inhibit` để chặn máy ngủ trong lúc chạy:

```bash
tmux new -s phase2-primary
```

```bash
systemd-inhibit --what=idle:sleep --why="phase2-v2 primary" benchmarks/artifacts/phase2-v2/preflight-1/venv-solver/bin/python -m benchmarks.run_phase2 --phase primary --plan benchmarks/artifacts/phase2-v2/campaign-01/plan.json --preflight-dir benchmarks/artifacts/phase2-v2/preflight-1 2>&1 | tee benchmarks/artifacts/phase2-v2/primary-01.out; echo "exit=${PIPESTATUS[0]}"
```

Kỳ vọng nếu chạy hết: `CampaignState` với `"status": "COMPLETE"`, `"completed": 216`, exit 0. `failed`
có thể lớn hơn 0 (run có P NOT_MET); đó không phải lỗi của lệnh.

Xem tiến độ từ một terminal khác (chỉ đọc, không ảnh hưởng campaign):

```bash
cat benchmarks/artifacts/phase2-v2/campaign-01/campaign-state.json
```

```bash
wc -l benchmarks/artifacts/phase2-v2/campaign-01/journal.jsonl
```

Sau khi lệnh primary kết thúc (COMPLETE hay dừng), tổng hợp ra một thư mục mới, nằm ngoài campaign:

```bash
benchmarks/artifacts/phase2-v2/preflight-1/venv-solver/bin/python -m benchmarks.aggregate_phase2 --campaign benchmarks/artifacts/phase2-v2/campaign-01 --preflight-dir benchmarks/artifacts/phase2-v2/preflight-1 --output benchmarks/artifacts/phase2-v2/summary-01
```

Gom file gửi lại (toàn bộ campaign đã nén, khoảng vài chục MB):

```bash
tar -czf phase2-primary-01.tar.gz -C benchmarks/artifacts/phase2-v2 primary-01.out summary-01 campaign-01
```

## 4. Điều kiện dừng và xử lý

| Tình huống | Xử lý |
|---|---|
| Lệnh in `BLOCKED` trước run đầu tiên (prerequisite, identity) | Gửi lại output; không sửa gì |
| `GATE_BLOCKED` giữa chừng (headroom/đĩa) | Gửi `campaign-state.json` và `journal.jsonl`. Chỉ khi tôi xác nhận là gate chặn trước run thì mới giải phóng RAM/đĩa rồi chạy lại cùng lệnh, thêm `--resume` |
| `STOPPED` hoặc `NEEDS_REVIEW` | Campaign kết thúc tại đó. Không resume, không retry, không xóa. Vẫn chạy aggregate và gửi lại; các run đã có là evidence kèm mẫu số đầy đủ (phần còn lại là MISSING) |
| Ctrl-C, mất điện, máy ngủ | Campaign kết thúc (§1). Gửi lại như trên. Muốn chạy lại phải dùng campaign ID mới `phase2-v2-linux-02`, prepare mới, pilot mới và ủy quyền mới |
| Nhiều run P NOT_MET (ví dụ HARD ở 20/40 lớp) | Không dừng, không nới budget. Đây là kết quả cần đo |

Không bao giờ sửa input, budget, guard, code hay plan để chạy cho qua. Không đổi thứ tự, không chạy riêng
từng dataset bằng tay, không chạy hai campaign cùng lúc.

## 5. Sau campaign

Tôi sẽ kiểm và tóm tắt:

- seal và receipts toàn vẹn, journal đúng thứ tự;
- mẫu số đầy đủ (216);
- H theo từng run và toàn campaign;
- P campaign: đạt khi 162/162 known-feasible có lịch hard-valid trong giới hạn và 54/54 UNSAT đúng;
  ngoài ra là NOT_MET hoặc INCOMPLETE;
- breakdown theo biến thể, cỡ và profile; thời gian conditional-on-success; số run censored; peak RSS;
- Q REVIEW_REQUIRED kèm phân bố BETTER/EQUAL/WORSE và vector score;
- zero NOT_APPLICABLE.

Báo cáo `docs/phase-2-linux-performance-report.md` chỉ được viết khi anh/chị cho phép (K7/M6), với phạm
vi kết luận theo acceptance v2 §7.5: "P campaign Linux v2 trên máy X". Không phải nghiệm thu hai OS,
không phải chất lượng được giáo vụ chấp nhận, không phải SLA hay P95.

## 6. Quyết định cần duyệt

- [x] **M1 — Chỉ chạy F sau khi E đạt trên máy đích** và anh/chị đã xem tóm tắt pilot. *(Đề xuất: chọn.)*
- [x] **M2 — Một phiên liền mạch** trong `tmux` với `systemd-inhibit`. Ngắt giữa chừng kết thúc campaign;
  chạy lại cần ID mới `-02`, prepare và pilot mới, và ủy quyền mới. *(Đề xuất: chọn.)*
- [x] **M3 — Điều kiện máy:** cắm sạc, không dùng máy cho việc nặng trong khoảng 6–10 giờ, không cập nhật
  hệ thống. Campaign vẫn ghi `workload_control = UNCONTROLLED`. *(Đề xuất: chọn.)*
- [x] **M4 — Xem tiến độ chỉ bằng cách đọc** `campaign-state.json` hoặc `journal.jsonl`; không mở hay sửa
  file trong thư mục run. *(Đề xuất: chọn.)*
- [x] **M5 — Không retry, không chạy lại từng run.** STOPPED hay NEEDS_REVIEW thì giữ nguyên làm evidence
  và phân tích trước. *(Đề xuất: chọn.)*
- [x] **M6 — Báo cáo** chỉ viết khi được cho phép, theo phạm vi §5. Evidence thô không commit; báo cáo ghi
  hash summary, plan và seal. *(Đề xuất: chọn.)*
- [x] **M7 — Không đổi gì giữa chừng dù kết quả xấu.** Nếu HARD 20/40 hoặc nhiều dataset P NOT_MET, mọi
  hướng tiếp (phân tích model, giảm số biến, Phase 3) là nhiệm vụ riêng, không áp vào campaign đang chạy.
  *(Đề xuất: chọn.)*

## 7. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Laptop ngủ hoặc mất điện làm hỏng campaign nhiều giờ | `systemd-inhibit`, cắm sạc, `tmux`. Nếu xảy ra: evidence vẫn giữ, dùng ID mới |
| Một run CRASH hay OUTPUT_INVALID dừng campaign sớm | Đúng thiết kế (gate an toàn/tính đúng); phân tích run đó trước |
| Headroom thiếu khi chạy cỡ 40 lớp (cần 4 + 2 GiB) | Đóng ứng dụng khác trước khi chạy. Gate chặn trước run, có thể `--resume` |
| Đọc kết quả thành SLA | Báo cáo theo §5: n = 3 mỗi fingerprint, conditional-on-success, không P95 |
| Kết quả xấu dẫn tới muốn nới budget | M7 |
