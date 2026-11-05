# Phase 2 hiệu năng v2 — báo cáo diễn tập E0 trên cloud

Ngày 2026-11-05. Thuộc K1 của [kế hoạch bước E](superpowers/plans/2026-11-05-phase-2-linux-performance-step-e.md).

**Trạng thái: DIỄN TẬP KỸ THUẬT, KHÔNG PHẢI EVIDENCE; báo cáo đã được người dùng duyệt ngày 2026-11-05.** Diễn tập chạy trên một container cloud dùng chung,
có shim headroom, và mỗi biến thể chỉ có n = 1. Không số nào ở đây được dùng cho trục P, Q hay benchmark
zero, và không thay thế pilot trên máy đích. Evidence thô nằm trong scratchpad của phiên (ngoài repo,
không commit) và sẽ mất khi container bị thu hồi. Báo cáo này chỉ là bản tóm tắt và hash.

## 1. Mục đích và kết luận

Mục đích duy nhất: chạy thử end-to-end tooling v2 với wheel đã cài trước khi chạy trên máy đích, để bắt
lỗi tích hợp.

- Toàn bộ đường đi đã chạy được: sinh bundle → preflight → prepare → warmup → 2 pilot → aggregate.
  Không lỗi nào do bản thân tooling v2, ngoài R1.
- **R1 (đã sửa ở `f873126`):** prepare bị từ chối để lại thư mục output và owner marker `NEEDS_REVIEW`,
  nên không chạy lại được.
- **R2 (đã đưa vào runbook):** gate headroom chỉ chấp nhận cgroup2. Container này dùng cgroup v1, nên
  phải đi tiếp bằng shim.
- **Tín hiệu cần chú ý (không phải lỗi):** cả hai pilot có lịch đúng hard và nằm trong giới hạn, nhưng
  P1 vẫn khác 0, P2 và P3 không được tối ưu (NOT_RUN). Pilot HARD dành khoảng 46 s trong 60 s chỉ để tìm
  lịch khả thi.

## 2. Môi trường

| Mục | Giá trị |
|---|---|
| Máy | Container cloud, Linux `6.18.44-fc-v236` x86_64, 4 logical CPU (Intel Xeon @ 2.10GHz), MemTotal 16 472 088 kB, workload dùng chung không kiểm soát |
| cgroup | v1 cho memory (`/sys/fs/cgroup` không phải cgroup2) |
| Python / OR-Tools / Pydantic | 3.12.3 / 9.15.6755 / 2.14.1 |
| Mã nguồn | `main` tại `812b0b6` (tooling v2 sau F1–F5), tree sạch; riêng campaign-03 dùng `run_phase2.py` đã sửa R1, trùng nội dung với `f873126` |
| Wheel | `vnedu_tkb_core-0.2.0-py3-none-any.whl`, SHA256 `cdd3428264bc92db0e5aadb2704cc277d46f405bebc7c062c6d0786abbda35d1` (giống wheel đã kiểm ở 2C-2, vì `src/` không đổi) |

## 3. Các bước và kết quả

| Bước | Lệnh (rút gọn) | Exit | Kết quả |
|---|---|---:|---|
| Sinh bundle | `uv run --extra solver python -m benchmarks.generate_phase2 --output …/bundle` | 0 | `DATASETS_VERIFIED`, 72 dataset, 2 phút 11 giây |
| Preflight | `uv run --extra solver python -m benchmarks.run_phase2 --phase preflight …` | 0 | `PREFLIGHT_PASS`, cả 25 check qua: core tests 906 passed; benchmark tests 443 passed, 8 skipped; ruff/format/mypy; wheel; 2 venv; tiny solve; smoke 0.4 ra 1.5 / Score 1.2 ở cả hai venv; kiểm bundle dưới import guard |
| Prepare `rehearsal-01` (không shim) | `venv-solver/bin/python -m benchmarks.run_phase2 --phase prepare …` | 2 | `PREPARE_HEADROOM_BLOCKED` (`HEADROOM_UNKNOWN`, cgroup v1). Để lại output và marker `NEEDS_REVIEW` → **R1** |
| Prepare `rehearsal-02` (shim) | `venv-solver/bin/python rehearsal_shim.py --phase prepare …` | 2 → 0 | Lần đầu `STALE_ACTIVE_MARKER_NEEDS_REVIEW` (do R1). Sau khi dời marker của `rehearsal-01` sang scratchpad (không xóa; campaign đó chưa có run nào) → `PREPARED`, 216 + 2, 3 phút 44 giây |
| Warmup (shim) | `… --phase warmup --plan …/campaign-02/plan.json …` | 0 | `COMPLETE`; fixture tiny OPTIMAL, có lịch hợp lệ |
| Pilot (shim) | `… --phase pilot --plan …/campaign-02/plan.json …` | 0 | `COMPLETE`, 2/2 terminal, `failed: 0`, tổng 1 phút 54 giây |
| Aggregate | `venv-solver/bin/python -m benchmarks.aggregate_phase2 …` | 0 | `SUMMARIZED`: 216 planned / 0 terminal / 216 missing → H và P INCOMPLETE, zero `MISSING: 216`; mục pilot đọc đúng |
| Kiểm bản sửa R1: `rehearsal-03` không shim, rồi có shim | `… --phase prepare …` | 2 → 0 | Không shim: `PREPARE_HEADROOM_BLOCKED:HEADROOM_UNKNOWN:ValueError`, **không** tạo output, marker IDLE. Ngay sau đó có shim: `PREPARED` với cùng campaign ID |

Shim `REHEARSAL_HEADROOM_SHIM` là một script nằm trong scratchpad. Nó chỉ thay `check_headroom` bằng
ước lượng `MemAvailable` từ `/proc/meminfo`, rồi gọi `run_phase2.main`. Không file nào trong repo bị sửa,
và mọi bản ghi headroom của shim đều mang nhãn đó: 3 sự kiện trong `journal.jsonl` của `rehearsal-02`.

## 4. Pilot (n = 1 mỗi biến thể, không phải evidence)

| Mục | SOFT | HARD |
|---|---|---|
| Harness / solver | COMPLETE / FEASIBLE | COMPLETE / FEASIBLE |
| Verdict | H PASS, Q REVIEW_REQUIRED, P MET, zero NOT_APPLICABLE | Như SOFT |
| Vector / witness | `[39,125,243]` / `[0,0,72]` (WORSE) | `[6,70,235]` / `[0,0,72]` (WORSE) |
| Quality | `SCORED_FEASIBLE`, optimal prefix rỗng | Như SOFT |
| Feasibility run | 2,2 s | **45,9 s** |
| Tier P1 | FEASIBLE, incumbent 39, bound 0, 46,8 s, chưa chứng minh tối ưu | UNKNOWN, không có incumbent, 14,0 s |
| Tier P2, P3 | NOT_RUN | NOT_RUN |
| Solver wall / Core wall | 49,2 s / 50,6 s | 60,0 s / 60,8 s |
| Launch-to-exit | 51,3 s (watchdog 150 s) | 61,5 s |
| Peak RSS | 238 MiB (target 1 GiB) | 194 MiB |
| CPU | 51,3 s | 61,4 s |

Đọc kết quả (chỉ là giả thuyết để xem lại khi có pilot thật):

- Gate pilot theo D2 đạt: có lịch đúng hard, nằm trong watchdog và RSS. Score khác 0 không chặn.
- Toàn bộ budget 60 s bị dùng ở feasibility và P1. P2/P3 không được chạy, nên giá trị P2/P3 chỉ là giá
  trị của incumbent, không phải kết quả tối ưu.
- Với biến thể HARD, chỉ riêng việc tìm lịch khả thi đã tốn khoảng 46 s ở cỡ 10 lớp. Cỡ 20 và 40 lớp
  (budget 120/180 s) có nguy cơ không tìm được lịch, tức P NOT_MET. Đây là đúng loại thông tin campaign
  cần đo; không được nới budget.
- Máy cloud dùng chung, CPU khác máy đích. Không suy ra thời gian trên máy đích từ các số này.

## 5. Phát hiện và xử lý

| ID | Phát hiện | Xử lý |
|---|---|---|
| R1 | Prepare bị từ chối (headroom/bundle) để lại thư mục output và owner marker `NEEDS_REVIEW` → `STALE_ACTIVE_MARKER_NEEDS_REVIEW`, không chạy lại được | **Đã sửa theo TDD** ở `f873126`: kiểm trước khi tạo output; bị từ chối thì marker về IDLE; lỗi bất ngờ vẫn `NEEDS_REVIEW`. 3 test regression; đã kiểm thật bằng `rehearsal-03` |
| R2 | Gate headroom chỉ chấp nhận cgroup2; cgroup v1 bị chặn trước mọi run | Không sửa code (gate an toàn của v1). Runbook D và kế hoạch E đòi `stat -fc %T /sys/fs/cgroup` = `cgroup2fs` |
| Q-signal | P1 khác 0, P2/P3 NOT_RUN; HARD tốn khoảng 46 s cho feasibility | Không phải lỗi. Ghi lại để so với pilot thật |

## 6. Hash (để đối chiếu nếu cần)

| File | SHA256 |
|---|---|
| `bundle/manifest.json` | `0fbb6a2e604011d92d8af332cc79be8bfe7688e0460153cc483cd5b58367ec05` |
| `preflight/preflight-manifest.json` | `9e326ffda1e1ac8eee99ef6c253b6c9fa01fff17aabacdac8fc4556f9b3989ed` |
| `campaign-02/plan.json` / `seal.json` | `dab6b594b99e5ba2c92ef0a2207d4513db072a511ffa3bb13c65ca1f435439fb` / `d5fb6ebd018b9bc085c58d9ef1fa5052580e84823d24d744b459205244ef181f` |
| `campaign-03/plan.json` / `seal.json` | `2ea3fed92294abf1fe9e4f21a5d7a35351eb34bf03bfacd85b02a6c88b800ec8` / `87621e8df943772bf32cb8452a49af34c595408dc15689c2f43e5d98555c376a` |
| `summary-02/summary.json` | `2f71b02abd24adc5280a1da5b204bebdf6bfa6efa74f5417ccc56005aa6316ec` |
| `rehearsal_shim.py` | `bd88d3b67e2763c4b2430316f3c2c9da8d11d2d9b1a9e7b255d235c1b70b26bf` |

Bundle trên máy đích sẽ có hash riêng, vì manifest ghi revision (commit HEAD) lúc sinh.

## 7. Giới hạn

- Không phải evidence P/Q/zero. Không chạy primary. Không chứng nhận Windows.
- Shim bỏ qua gate headroom thật. Trên máy đích, gate đó phải tự qua, không có shim.
- `rehearsal-03` chỉ dùng để kiểm R1: đã prepare, chưa warmup hay pilot.
- Trên cloud, owner marker `.git/tkb-campaign-owner/active.json` hiện là của `rehearsal-03`, ở trạng thái
  IDLE. Marker cũ của `rehearsal-01` được dời sang scratchpad, không xóa. Clone trên máy đích có marker
  riêng.
