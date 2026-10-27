# TIGHT10 — Native feasibility CPU preparation

Task 1 của [native CPU plan](superpowers/plans/2026-10-27-tight10-native-cpu.md) hoàn tất trên `feature/phase2a-task5-linux-summary`, baseline `67cb7eb`. User yêu cầu triển khai full kế hoạch; tooling/dispatch đã được kiểm bằng fakes và candidate mới đã prepare. **Chưa thực hiện Task 2**, chưa tạo authorization/START/attempt hoặc native measurement; plan yêu cầu user duyệt actual candidate/hash/snapshot mới trước bước đó. Không sửa Core/budget/guards, legacy gate, dependencies hoặc Phase2B/2C. Windows **BLOCKED**.

## Instrumentation đã triển khai

- `measure_native_call` dùng resource.getrusage(RUSAGE_SELF) user/system và monotonic_ns ngay quanh bound native_solve, sau parameter/model/callback guards, trước response/decode/independent validation/file writes. Lưu raw clock snapshots, deltas, units/scope, ratio/reason, entered/returned/raw code/original exception. Đây là CPU mọi child threads chạy trong interval, không CPU riêng thread CP-SAT; không tự trừ overhead.
- Optional `measure_cpu=False` giữ old single/pair không timing; CPU profile fixed logging OFF. Giữ counters/response cuối khi UNKNOWN/early return và native outcome khi lỗi post-clock; pre-clock lỗi chặn native entry. Raw native return object không bị thay đổi. Invalid/nonfinite clocks/negative deltas/ratio overflow bị BLOCKED với null/reason, không phát JSON NaN/Infinity hoặc clamp0.
- Strict CpuCandidate/CpuAuthorization với action RUN_ONE_NATIVE_CPU_FEASIBILITY; exact hash/run-ID/root, fixed OFF/measurement/admission policy, runtime/source/model guards riêng. Old single/pair approvals bị reject. Shared owner, exclusive START/CHILD-START, supervised child, reap/NEEDS_REVIEW semantics giữ nguyên.
- CPU-only parent/child dispatch đã kiểm bằng fakes, tối đa một native call; actual native entry khác wrapper solve attempt. Kill trước final capture giữ explicit null counters/response/CPU và reasons; không backfill native CPU từ wait4. Final counters chỉ chụp khi return, không thêm polling hoặc hứa snapshot chính xác t=60.000s.
- Parent pre/post workload/power và child pre-admission nằm ngoài measured interval. UNKNOWN không bị gọi infeasible hoặc dropped; independent validation và score vẫn bắt buộc khi có lịch. No quality proof.

## Candidate mới

| Field | Giá trị |
|---|---|
| Status | **PREPARED_NOT_AUTHORIZED** |
| Candidate SHA256 | `5585a43eee2ac961591f320b56e743347efe449a976fbed78c7ad620631c2499` |
| Driver SHA256 | `b5dad92f52d972a8bd38de2538c17526fd16be5429d9abbae1f31aa210bea479` |
| Run-ID | `tight10-native-cpu-20261027-v1` |
| Output root | `/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1` |
| Legacy gate | **PASS** |
| Legacy differences | `{}` |
| Current MemTotal | `MemTotal:       40745240 kB` |
| Native constructor calls lúc prepare | **0** |

[CPU candidate](../benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1/cpu-candidate.json) và [preparation result](../benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1/preparation-result.json) là đúng hai files trong root mới. Không authorization, lease acquisition, START hoặc attempt. Hash được tính từ actual candidate bytes sau source freeze/review/tests, không phải hash của plan; old approvals đã tiêu thụ không áp dụng.

**Snapshot thay đổi so với pair trước:** MemTotal40745236→40745240 KiB (**+4KiB**), hiện khớp legacy40745240; full legacy machine diff rỗng, gate nguyên bản PASS. Không normalize/sửa snapshot hoặc giải thích nguyên nhân thay đổi; không suy MemTotal gây status nào. Full machine comparison với previous pair chỉ khác mem_total. Driver hash khác vì instrumentation mới, được freeze riêng; các fixed input/witness/model/Core/wheel/lock/options không đổi. Snapshot này cần được duyệt chính nó, không mô tả sai là vẫn −4KiB.

Common model SHA256 `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083`; fingerprint `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee`; input SHA256 `7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735`; witness SHA256 `f9b5274529c9d1bd4d4c301b2626336bd0128b38b57901b90627ca4be1121a57`. Installed wheel SHA256 `1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9`, lock `e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084`.

Budget60s **wall**, workers1, seed42, gaps0, watchdog150s, RSS observed target1GiB; guards10,000slots/10,000occurrences/100,000placements/1,000,000occupancy terms. Admission headroom≥3GiB/disk≥256MiB, AC_ON trước spawn/solve; fresh gates phải PASS lại trước Task2. Không CPU budget, không retry/resume/hints/quality tiers, không đổi host power/affinity/env hoặc kill jobs.

Prepare context `2026-10-27T16:14:28.877834+00:00`, load1/5/15min `[0.58154296875, 0.82958984375, 0.78662109375]`, AC Mains online1/USB online1, BAT0 Full100; workloadUNCONTROLLED/competingUNKNOWN. Đây là snapshot prepare, không chứng minh idle hoặc power/frequency/thermal ổn định lúc run. n=1 tương lai chỉ diagnostic, không causal throughput/logging/MemTotal claim hoặc SLA.

## TDD, review và kiểm chứng thực chạy

Initial RED17failed+18missing-API errors, old64 giữ pass; sau implementation full99 GREEN. Edge RED6 về wall NaN/Infinity/negative và ratio overflow được sửa, full109 GREEN. Fresh reviewer independently chạy109fake-only tests và không tìm material timing/gate defect; hai chi tiết provenance/null-counter thuộc contract được sửa với RED2→GREEN109: CHILD-START bind candidate/run/parent và killed result giữ normal counter/response shape/reasons. Không finding hoãn, không new product tests ngoài dedicated benchmark suite.

| Lệnh thực chạy | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS, lock không đổi |
| `uv run --extra solver pytest benchmarks/tests/test_trace_tight10.py -q` | **109 PASS**, final pre-prepare0.72s; autouse native constructor blocked, FakeSolver only |
| `uv run ruff check --fix benchmarks/trace_tight10.py benchmarks/tests/test_trace_tight10.py` | sửa2import-order errors, sau đó clean |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests benchmarks` | PASS54files |
| `uv run mypy` | PASS27Core files; không tuyên bố strict type-check toàn driver benchmark |
| `git diff --check` | PASS |
| Candidate/driver digest, exact root membership và protected hashes assertions | PASS; **168protected files** giữ nguyên |

Prepare thực chạy một lần, exit0:

```sh
/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1/venv-solver/bin/python -I /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/trace_tight10.py prepare-cpu --root /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1 --run-id tight10-native-cpu-20261027-v1
```

Installed capture/build-only guard asserts constructor0. Không chạy full pytest vì có native solves ngoài prepare scope; không profiler/calibration/warmup hoặc native CPU sample mới. Các clock values trong tests là fakes, không performance measurements.

## Điều kiện Task 2

Full-plan implementation request đã cho phép triển khai tooling; [plan, mục Candidate/approval](superpowers/plans/2026-10-27-tight10-native-cpu.md) vẫn yêu cầu “User cần chấp thuận actual snapshot/drift/power/workload limitations được Task 1 công bố” và Task2 “Sau exact user approval mới”. Actual hash/snapshot chỉ có sau prepare này.

Cần xác nhận candidate SHA256 trên, exact run-ID/output root, snapshot MemTotal khớp legacy, fixed OFF/CPU policy và giới hạn workload/power, cho **một attempt/tối đa một native feasibility call**. Không ký approval thay user hoặc dùng old hash. Sau approval, parent/child phải PASS fresh gates; drift mới block không tự rebaseline. Task2 chưa thực hiện; nếu chưa có approval thì dừng ở PREPARED_NOT_AUTHORIZED, không tuyên bố full kế hoạch đã hoàn tất.
