# Phase 2A Task 4 — Linux prepare, warmup và pilot

Ngày thực hiện: 2026-10-27 (ICT). **VERIFIED — PILOT PASS** trên một bộ BASE10 synthetic; **PRIMARY NOT RUN**, **WINDOWS BLOCKED**. Không bắt đầu Task5 hoặc Phase2B/2C; không thay Core, generator, dependency hoặc ngân sách.

User cho phép commit/push tài liệu đang có trước, rồi thực hiện prepare → warmup → pilot theo [runbook](superpowers/plans/2026-10-27-phase-2a-task4-linux-pilot-campaign.md).12file tài liệu đã được push tại `5b13ca4` trước mọi phase thực tế. Đây là báo cáo per-case, không tổng hợp thống kê campaign.

## Identity và bằng chứng

- Campaign: `linux-pilot-20261027-v1`; machine label `linux-local-01`.
- Git HEAD khi prepare: `5b13ca419984ff2ade23e40c3dbf9e6b36a9094c`; worktree sạch khi freeze.
- Controller SHA256: `39368612cc89f61905733bf47b32f8dedcd032d319e2458ec224d6627482efc4`.
- Frozen plan SHA256: `6b8a324560b1857555f686a955f5af79468e5f80a00d830466b9253e648a9e61`.
- Dùng installed Python của frozen `preflight-linux-v1/venv-solver`, chạy `-I` và controller ở main; không editable Core.
- Giữ nguyên Task1 bundle36 và preflight wheel/lock đã kiểm chứng. Prepare worker xác minh toàn bộ witnesses/proofs trong process riêng; không solve ở bước này.
- Raw artifacts local, được Git ignore: `benchmarks/artifacts/phase2a/pilot-linux-20261027-v1/`; driver logs và hash inventory: `benchmarks/artifacts/phase2a/pilot-linux-20261027-v1-logs/execution-summary.json`. Không đổi paths/provenance trong raw records.

Cả ba CLI phase trả exit0. Không gọi `--phase primary`, không tạo primary directory, không retry/resume hoặc thay budgets. Owner marker cuối cùng **IDLE**, child đã có kernel reap evidence; receipts và source hashes sau chạy đều khớp.

## Kết quả thực tế

| Phase | Kết quả | Giới hạn và ý nghĩa |
|---|---|---|
| Prepare | VERIFIED — PASS;36datasets verified | Headroom PASS; verification worker18,175s, measurementOK/exit0; giới hạn150s/1GiB. Thời gian này là setup, không feasible-search performance. |
| Warmup | VERIFIED — COMPLETE; hard-valid, score(1,1,2) | Tiny3occurrences; budget10s/watchdog15s/256MiB. Loại khỏi mẫu primary và mọi performance summary. |
| Pilot | VERIFIED — COMPLETE, correctnessPASS/performanceMET/qualityEQUAL | BASE10/seed101/repeat0; hard-valid và vector(0,0,0), solverOPTIMAL, qualityLEXICOGRAPHIC_OPTIMAL, proved prefix(1,2,3). |

Pilot có10lớp,15GV,9môn,90teaching requirements,260occurrences tương ứng300tiết,60slots;15120placements/34080occupancy terms. BASE này không có rooms/locks; chưa kiểm trường hợp MIXED/TIGHT/UNSAT bằng execution campaign.

| Đại lượng pilot | Đo được | Ngưỡng/nguồn |
|---|---:|---|
| Launch-to-reap wall | 58.460999s | ≤150s watchdog target; bao gồm startup/child xử lý/cleanup, không phải TTF |
| Child CPU | 60.104142s | Linux wait4, CPU có thể lớn hơn wall; không suy từ đó num_workers khác cấu hình |
| Peak resident | 175108096bytes (166.996MiB) | ≤1073741824bytes (1GiB); ru_maxrss171004KiB×1024, measurementOK |
| Solver configuration |60s / workers1 / seed42 | Cùng budget qua feasibility và các tiers; không cấp60s cho từng tier |
| Priority vector |(0,0,0) | Khớp zero target và witness;60rule scores đều0 |

`run_cli_once` đã gọi independent schedule validator và score evaluator; sau pilot còn chạy lại installed CLI `validate-schedule` → SCHEDULE_VALID và `evaluate-score` → OK/(0,0,0), cùng input fingerprint. Đây là recomputation correctness/score; không dùng CLI để tái chứng nhận optimality từ metadata. Các claim OPTIMAL/prefix là solver proof metadata của chính run này, nhất quán với score và zero lower bound.

## Phạm vi và giới hạn

- **VERIFIED:** prepare36, warmup1 và pilot1 thành công trên môi trường Linux đã ghi trong environment.json; pilot nằm ngoài108primary IDs. Primary vẫn **0/108 attempted**, không dùng pending0 của state pilot làm coverage cả campaign.
- **INFERRED:** pilot gate cho phép đề xuất chạy primary theo frozen plan sau authorization; không chứng minh108cases sẽ đạt.
- **UNKNOWN:** hiệu năng20/40lớp, profile khó, variation giữa repeats, máy người dùng và Windows. Một số đo không phải SLA/P95 hoặc so sánh với FET/STKB.
- RAM gate chỉ admission estimate và observed target; sampling có thể bỏ spike, kernel peak được kiểm sau reap. Headroom/load/power/workload observations trong START, không khẳng định máy đã được kiểm soát tải.
- TTF vẫn NOT_INSTRUMENTED; không suy thời gian có nghiệm đầu từ total wall hoặc các tier wall.
- Giữ nguyên Minor: khi identity gate đầu hàm chặn resume, counters trả về có thể0/NOT_STARTED dù có lịch sử; xem journal/state lịch sử. Không chỉnh Core/tooling trong lượt execution để sửa hoặc né gate này.

Chỉ chạy3phase CLI và2lệnh independent validation/scoring nói trên; không rerun toàn416tests vì không có thay đổi code. Full regression sau merge gần nhất:416PASS/133,58s; đây là kết quả trước lượt execution, không giả là đã chạy lại sau pilot. Tài liệu mới được kiểm diff/nguồn số đo; không ghi dữ liệu vnEdu thật vào artifacts.
