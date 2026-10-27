# Phase 2A Task 4 — primary campaign Linux

**VERIFIED — thu thập COMPLETE108/108**, pending0, ownerIDLE. Đây là hoàn tất execution của Task4 Linux, không phải mọi quality/performance gate đều đạt. **WINDOWS BLOCKED; Task5 và Phase2B/2C chưa triển khai.**

## Identity và phạm vi

- Campaign: `linux-pilot-20261027-v1`; dùng nguyên plan đã prepare/warmup/pilot PASS.
- Frozen plan SHA256: `6b8a324560b1857555f686a955f5af79468e5f80a00d830466b9253e648a9e61`.
- Git HEAD khi freeze: `5b13ca419984ff2ade23e40c3dbf9e6b36a9094c`; HEAD khi launch primary: `914e62a` (chỉ thêm tài liệu, source hashes không đổi).
- Primary chạy đúng108IDs/order:36datasets×3fresh-process repeats; warmup/pilot tách ngoài108. Không regenerate input/order, không retry hoặc thay failed attempt bằng lần khác.
- Budget giữ nguyên:10lớp60s/150s/1GiB;20lớp120s/210s/2GiB;40lớp180s/270s/4GiB (solver/watchdog/observed RSS target); workers1/seed42. Headroom reserve2GiB ngoài target, kiểm từng run.
- START đầu: `2026-10-26T18:31:08.154225+00:00` = 2026-10-27 01:31:08 ICT. TERMINAL cuối: `2026-10-26T21:07:26.396141+00:00` = 2026-10-27 04:07:26 ICT. Đây là mốc journal, không TTF hoặc latency statistic.

## Checkpoint và cách đọc trạng thái

| Trường persisted state | Giá trị | Ý nghĩa |
|---|---:|---|
| status | COMPLETE | Toàn bộ108rows đã có terminal outcome |
| attempted/completed |108/108 | Giữ đủ denominator, không loại UNKNOWN hoặc NOT_MET |
| pending |0 | `pending_cases=[]`; không có partial/unstarted primary cases |
| failed |63 | Số ca không đạt `_qualified`, **không phải63correctness failures** |
| owner state |IDLE | Không còn campaign giữ ownership marker |

Không có verdict correctnessFAIL hoặc safety stop trong108receipts đã kiểm. UNKNOWN giữ correctnessNOT_ASSESSED/NO_SCHEDULE, không bị đổi thành vô nghiệm hoặc PASS. Lịch hard-valid nhưng chưa đạt zero target vẫn giữ đúng FEASIBLE/score và performanceNOT_MET. Các ca UNSAT đúng kỳ vọng giữ INFEASIBLE, quality/performanceNOT_APPLICABLE, không dùng như feasible-search latency hay score0.

`failed=63` cần giữ nguyên đúng contract qualification của runner; không đổi tên trong raw `campaign-state.json`. Các số raw theo từng ca có trong coverage để Task5 tương lai đọc. Không tính median/P95, success ratios theo profile, bottleneck ranking, hoặc so FET/STKB/Windows trong lượt này.

## Kiểm chứng sau execution

- `primary.stdout.json` trùng persisted `campaign-state.json`; plan/seal/environment/source/controller/generator/lock/preflight/runtime vẫn khớp các identities được kiểm.
- Dùng lại `_events`, `_read_terminals`, `_receipt`:110receipts gồm108primary+warmup+pilot hợp lệ; tất cả artifacts được băm trong receipts vẫn khớp, không duplicate START/TERMINAL hoặc missing terminal.
-108primary START/TERMINAL IDs đúng thứ tự frozen plan;108state rows đều TERMINAL. Guards/options/limits của từng run bằng planned case; admission headroom của từng START là PASS.
-108measurement records OK, có raw wait status; `_stop_status` không yêu cầu stop đối với bất kỳ completed outcome nào. Không có correctnessFAIL trong per-case verdicts.
- Dùng lại `check_case` trên108raw outcomes cho đúng verdict đã lưu. Đây là recomputation classification/witness/target checks; không chạy lại solver, không tái tuyên bố optimality từ metadata. Independent hard checker/scorer đã chạy trong `run_cli_once` cho từng valid schedule tại execution; receipts bảo toàn bằng chứng đó.
- Không rerun416tests vì không sửa code; regression sau merge gần nhất vẫn là416PASS/133,58s, không trình bày nó như test chạy lại trong lượt audit.

## Khác biệt máy ở thời điểm kiểm tra lại

**VERIFIED — gate cho execution hiện tại báo MACHINE_DRIFT.** `MemTotal` hiện tại là40745236kB, frozen40745240kB: lệch4KiB. Runtime/package/source vẫn khớp. Chưa xác minh nguyên nhân biến động này.

Giữ nguyên frozen machine identity, không sửa source/env/plan để ép gate pass, không resume/retry bất kỳ run nào. Audit lịch sử chỉ kiểm immutable evidence và kết quả đã hoàn tất; không gọi đó là current execution identity PASS. Khác biệt hiện tại được lưu trong coverage/manifest và không ghi đè state COMPLETE lịch sử. Bất kỳ yêu cầu execution mới phải xử lý identity gate theo policy riêng, không dùng báo cáo này làm giấy phép bypass.

## Evidence lưu ở local

Raw: `benchmarks/artifacts/phase2a/pilot-linux-20261027-v1/` (plan,environment,journal,campaign-state,108run directories).

Driver logs/audit: `benchmarks/artifacts/phase2a/pilot-linux-20261027-v1-logs/`:

- `primary.stdout.json`, `primary.stderr.txt`: kết thúc CLI phase.
- `primary-authorization.json`: phạm vi thực hiện được duyệt.
- `primary-coverage.json`:108rows theo frozen order, trạng thái/metrics/score/verdict/receipt digest và pending list rỗng; không là Task5 aggregator.
- `primary-verification-manifest.json`: source identity, current-machine drift, receipt checks và hash inventory.

Raw artifacts được Git ignore, giữ nguyên trên máy; chỉ tài liệu kết quả được publish. Các snapshot primaryNOT_RUN ở báo cáo pilot/tooling là lịch sử. Không sửa Core/runner/generator/dependencies, chưa mở Task5 hoặc Phase2B/2C; Windows vẫnBLOCKED.
