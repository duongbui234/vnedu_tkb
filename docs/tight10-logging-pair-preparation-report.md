# TIGHT10 — Logging pair Task 1 preparation report

Task 1 của [logging pair plan](superpowers/plans/2026-10-27-tight10-logging-pair.md) đã triển khai trên `feature/phase2a-task5-linux-summary`, từ baseline `2796543`. Chỉ instrumentation, fake tests và build-only prepare; **Task 2 chưa chạy, candidate chưa được duyệt**. Không chạy native solver/search/profiling, sửa Core, đổi budget/guards hoặc mở Phase 2B/2C. Windows **BLOCKED**.

## Thay đổi và phạm vi

- Mở rộng `benchmarks/trace_tight10.py` tại driver hiện có; single-trace caller mặc định vẫn ON. Strict pair candidate/authorization tách khỏi single-trace schema, reject unknown version/fields, sai modes/order/IDs/root/options/limits.
- OFF không callback/file log, `trace_complete=null`, `trace_capture_status=DISABLED`, reason `LOGGING_DISABLED`; stage/response/counters vẫn được thu, lịch và per-rule/tier score vẫn phải kiểm độc lập. ON giữ raw callback UTF8 flush và regression xử lý close/read/write errors. Missing counters giữ null kèm reason. Không cài solution/bound callback; kiểm actual callback state ngay trước native solve và lưu trong trace-result.
- Pair dispatch đã được kiểm bằng fakes: một lease, OFF→ON, hai fresh supervised children, một constructor/solve mỗi member, recheck common identity/model/profile, headroom/disk/AC trong parent và child. Terminal/START/manifest gắn candidate hash, pair-ID, index/mode/run-ID, parent PID; ON kiểm binding OFF terminal. Direct child/re-entry, stale owner và unconfirmed reap đều bị chặn hoặc giữ NEEDS_REVIEW.
- UNKNOWN hợp lệ được giữ, không gọi là infeasible/correctness failure; crash/watchdog/resource/capture/correctness failure dừng cặp, pending NOT_STARTED, không retry/resume. Dispatch chỉ được **kiểm bằng fakes**, chưa kiểm bằng native execution ở lượt này.
- Không sửa `src/`, frozen runner/generator, dependencies, artifacts lịch sử hoặc legacy gate. 123 file được chụp hash trước thay đổi và đối chiếu sau prepare đều nguyên vẹn; gồm Core/source và TIGHT10 static/auxiliary/single-trace evidence hiện có. Scope không phải kiểm lại toàn bộ campaign 108 lượt.

## Candidate đã prepare

- Trạng thái: **PREPARED_NOT_AUTHORIZED**.
- Pair-ID: `tight10-logging-pair-20261027-v1`.
- Run-IDs: `tight10-logging-pair-20261027-v1-off`, `tight10-logging-pair-20261027-v1-on`.
- Thứ tự: `logging_off → logging_on`.
- Output root: `/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1`.
- [pair-candidate.json](../benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1/pair-candidate.json).
- [preparation-result.json](../benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1/preparation-result.json).
- **Candidate SHA256:** `568c69099aae15a2688a4f23f02b6cf1885f8a55e3b6a4c943d3b742f4059da0`.
- **Frozen driver SHA256:** `e09760bdcc217edfabb9dfa9b18252543eb352c4ee634aa0ea1d1355d9e48169`.
- Root mới chỉ có hai file trên; không authorization, lease acquisition, PAIR-START/START, runs/attempt hoặc native output. Build/prepare chặn `CpSolver` constructor bằng `SEARCH_FORBIDDEN`; capture và prepare đều assert guard không được gọi. Owner shared hiện vẫn IDLE của single trace trước.

Common descriptor là exact validated identity trừ field logging; hai fixed profiles lưu riêng, không nới legacy `Identity` validator. Source thay đổi sau snapshot làm gate block và cần candidate/hash mới. Native model chỉ được build/compile/hash; không solve.

| Identity | SHA256 |
|---|---|
| Fingerprint | `c10-tight-s101` / `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee` |
| Input | `7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735` |
| Witness | `f9b5274529c9d1bd4d4c301b2626336bd0128b38b57901b90627ca4be1121a57` |
| Compiled feasibility model | `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083` |
| Core wheel | `1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9` |
| uv.lock | `e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084` |

Mỗi member giữ native budget **60s**, workers **1**, seed **42**, relative/absolute gaps **0**; watchdog **150s**, observed RSS target **1GiB** (không phải OS hard cap). Guards 10,000 slots / 10,000 occurrences / 100,000 placements / 1,000,000 occupancy terms; admission headroom≥3GiB và disk≥256MiB. Không cộng hai budget thành một solve 120s.

## Drift, workload và power

Legacy exact gate chạy nguyên bản và trả **BLOCKED_MACHINE_DRIFT**. Full diff duy nhất:

| Field | Legacy | Candidate | Delta |
|---|---|---|---|
| machine.mem_total | `MemTotal:       40745240 kB` | `MemTotal:       40745236 kB` | −4 KiB = −4096 bytes |

Không có runtime/source/input/model drift khác được gate phát hiện. Candidate hiện có cùng MemTotal với single-trace v2, nhưng approval cũ đã dùng cho một run và **không cấp quyền cặp này**. Nguyên nhân thay đổi MemTotal chưa xác định; không sửa hoặc normalize legacy snapshot.

Prepare context tại `2026-10-27T08:23:29.987724+00:00`: load averages 1/5/15min `[0.740234375, 1.3466796875, 1.20166015625]`, load_status OBSERVED; AC Mains online=1, USB online=1/status Charging, BAT0 Full/capacity 100. Đây là snapshot lúc prepare, không phải pre-run admission hoặc bằng chứng máy idle. `workload_control=UNCONTROLLED`, `competing_workload=UNKNOWN`.

Policy mới freeze AC_ON: re-observe trước từng member, thiếu/UNKNOWN/offline thì block member đó. Persist pre/post raw context, actual callback/profile/parameters và process CPU/RSS; power đổi/UNKNOWN sau run giữ result và comparability LIMITED. Không kill apps, đổi power/governor/affinity/env hoặc thu process command lines. Load không có threshold chọn mẫu. Hai snapshots không chứng minh power/nhiệt/frequency ổn định trong solve.

## Approval cần trước Task 2

Chưa tạo approval. User cần duyệt **exact candidate hash**, snapshot/drift trên, pair-ID, hai run-IDs/root/thứ tự OFF→ON và scope đúng một feasibility call/mode. Action riêng `RUN_ONE_LOGGING_PAIR`; single-run action `RUN_ONE_FEASIBILITY_TRACE` bị reject. Chỉ được chạy khi fresh parent/child gates, owner, headroom/disk/power đều PASS; drift mới block, không tự rebaseline/retry. Snapshot approval không biến legacy gate thành PASS.

## Kiểm chứng thực chạy

| Lệnh/kiểm tra | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS, lock/dependencies không đổi |
| `uv run --extra solver pytest benchmarks/tests/test_trace_tight10.py -q` | **64 PASS** (0.58s ở final pre-prepare run), native constructor bị chặn autouse; chỉ FakeSolver được phép |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests benchmarks` | PASS, 54 files |
| `uv run mypy` | PASS, 27 Core source files; không tuyên bố type-check toàn bộ benchmark driver |
| `git diff --check` | PASS |
| Standard-library artifact/hash/link/scope assertions | PASS: candidate hash và driver hash khớp, đúng hai prepare files, 123 protected hashes nguyên vẹn |

Lệnh prepare thực chạy, một lần, exit 0:

```sh
/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1/venv-solver/bin/python -I /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/trace_tight10.py prepare-pair --root /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-logging-pair-20261027-v1 --pair-id tight10-logging-pair-20261027-v1
```

TDD: original 34 tests giữ GREEN; batch pair tests RED vì API/profile chưa có. Hai ca CLI/null-reason RED→GREEN tiếp theo. Review độc lập tìm thiếu binding receipt/manifest và actual callback evidence; năm regression cases RED→GREEN, final **64/64**. Sửa thêm missing-log reason NOT_STARTED khi OFF chưa chạy; đây là sửa tính đúng của evidence. Không còn finding được hoãn.

**Ruling:** không chạy `uv run --extra solver pytest` toàn bộ vì suite có native solves trái scope user. Chỉ dedicated fake suite và static checks; các native integration paths không được kiểm lại. Không tạo dependency hoặc profiler mới.

## Phân biệt kết luận và giới hạn

- **Correctness:** kiểm contract/gates và validation/score paths bằng fakes; candidate build-only model/witness checks PASS. Chưa có lịch native mới để chấm correctness.
- **Performance:** chưa đo cặp; không có wall/CPU/RSS/throughput mới từ solver. Không suy overhead từ thời gian prepare hoặc fake tests.
- **Quality:** chưa có native score mới, không quality optimization/proof. UNKNOWN và trace trước giữ nguyên trong [báo cáo single trace](tight10-search-trace-report.md), không tái dùng làm member ON/OFF.
- Một cặp n=1/mode, order cố định, workload/thermal/cache chưa kiểm soát chỉ cho mô tả thăm dò; không P95/median/SLA/causal claim. Ba repeats của campaign cũ giữ riêng, không bổ sung hoặc gộp với hai treatments mới.

Task 1 dừng tại PREPARED_NOT_AUTHORIZED. Bước kế tiếp là review candidate/hash/drift và điều kiện Task 2; chưa chạy tự động.
