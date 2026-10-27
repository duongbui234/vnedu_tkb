# TIGHT10 — One approved native feasibility CPU measurement

**Task 2 hoàn tất:** một parent attempt, đúng **một native call**, không retry. Harness COMPLETE, measurement OK; feasibility OPTIMAL với260assignments hard-valid và score(12,77,4). CPU trong native-call boundary = **46.008923000 CPU-s**, elapsed boundary = **46.036537386s**, ratio **0.999400163705**. Không quality proof hoặc kết luận nguyên nhân ba UNKNOWN lịch sử.

Thực hiện trên `feature/phase2a-task5-linux-summary`, source baseline `56e0881`; theo [native CPU plan](superpowers/plans/2026-10-27-tight10-native-cpu.md). Windows **BLOCKED**; không Phase2B/2C. Không sửa Core/driver/legacy gate/options/budget/guards/dependencies sau candidate freeze, không profiling hoặc native attempts thêm.

## Approval, identity và gates

- User duyệt exact candidate `5585a43eee2ac961591f320b56e743347efe449a976fbed78c7ad620631c2499`, run-ID `tight10-native-cpu-20261027-v1`, output root `/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1`, snapshot MemTotal40745240KiB khớp legacy, workload/power limits và tối đa một native call.
- [Authorization](../benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1/cpu-authorization.json) action RUN_ONE_NATIVE_CPU_FEASIBILITY và [nguyên văn approval](../benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1/user-authorization.txt) ghi exclusive trước run. Không tái dùng single/pair approval.
- Candidate/driver digests giữ nguyên; driver SHA256 `b5dad92f52d972a8bd38de2538c17526fd16be5429d9abbae1f31aa210bea479`. Parent/child common identity, OFF profile và native_cpu_v1 policy exact-match approved candidate; START/CHILD-START/terminal/manifest bind hash/run-ID/parentPID. Child PID **276069**, parent PID **276034**.
- Source/input/witness/model/wheel/runtime gates và admission owner/headroom/disk/AC PASS trong preflight rồi parent/child. Legacy exact gate nguyên bản **PASS**, machine differences={}; MemTotal current/legacy40745240KiB. Đây khác prior diagnostic snapshot40745236KiB; không sửa/normalize baseline hoặc quy status cho4KiB.
- Fixed feasibility wall budget60s, workers1, seed42, gaps0; watchdog150s/RSS observed target1GiB; guards10,000slots /10,000occurrences /100,000placements /1,000,000occupancy terms; headroom≥3GiB/disk≥256MiB. Logging OFF: progress=false, stdout/response logging=false, log/solution/bound callbacks absent; không trace.log, trace_complete=null với LOGGING_DISABLED.
- Fingerprint `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee`; model SHA256 `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083`. Full input/witness/Core/wheel/lock identity xem immutable candidate, không gộp với execution identity khác.

## Native-call measurement và whole-child accounting

| Metric | Giá trị |
|---|---:|
| Clock scope | resource.getrusage(RUSAGE_SELF), mọi child threads trong interval |
| CPU start user /system (s) | 2.490777 / 0.046863999999999996 |
| CPU end user /system (s) | 48.488577 / 0.057987 |
| Native-boundary user delta (CPU-s) | 45.997800000 |
| Native-boundary system delta (CPU-s) | 0.011123000 |
| Native-boundary CPU sum (CPU-s) | 46.008923000 |
| Monotonic start /end (ns) | 20205642352089 / 20251678889475 |
| Native-boundary elapsed (s) | 46.036537386 |
| Native-boundary CPU/elapsed | 0.999400163705 |
| Native response wall (s) | 46.033664557 |
| Instrumented stage elapsed (s) | 46.045073669 |
| Whole child launch→exit (s) | 46.808505258 |
| Whole child wait4 user+system (CPU-s) | 48.614788 |
| Whole child CPU/child-wall | 1.038588772105 |
| Kernel peak RSS | 152572KiB = 156233728bytes = 148.99609375MiB |
| Sampled peak RSS | 156463104bytes, 931samples |

Raw arithmetic được audit lại từ saved samples: user=end−start, system=end−start, sum=user+system, elapsed=(end_ns−start_ns)/1e9, ratio=sum/elapsed; đều khớp. CPU ngoài boundary theo chênh hai CPU measurements toàn child−boundary ≈**2.605865000 CPU-s**; đây là accounting còn lại ngoài interval, không phân bổ thành compiler/decode/BLAS hoặc nguyên nhân cụ thể. Không lấy wall overhead trừ vào CPU seconds.

Boundary sau policy/model/callback guards và trước response extraction/decode/independent validation/file writes. CPU interval vẫn gồm mọi child threads/background library activity trong khoảng đó và overhead lấy clock/bookkeeping sát boundary; không phải CPU riêng CP-SAT threads, không calibration/trừ overhead. Ratio≈0.9994 mô tả đúng lượt thành công này, không chứng minh exclusive core hoặc không có scheduling gap. Whole-child ratio≈1.0386 khác boundary ratio là bằng chứng cần giữ hai scopes riêng; không suy workers>1 từ ratio>1.

## Outcome và final counters

call_entered=true, call_returned=true, measurement_status=OK, reason/ratio_reason/native_exception=null; constructor1 /wrapper solve1 /actual native entry1. Native return_code **4 là CP-SAT OPTIMAL**, còn process exit_code0/raw_wait_status0; không nhầm code4 này với **CLI exit4 cho UNKNOWN** của receipts lịch sử.

| Final counter/field | Giá trị |
|---|---:|
| deterministic_time | 46.39286630778822 |
| num_binary_propagations | 13216444 |
| num_booleans | 2796 |
| num_branches | 1150007 |
| num_conflicts | 25380 |
| num_integer_propagations | 13426438 |
| num_lp_iterations | 374745 |
| num_restarts | 87 |
| user_time | 46.033664592 |
| wall_time | 46.033664557 |

Counter snapshot lấy khi native call return sớm, dưới60s; không chờ đủ deadline, không có polling hoặc snapshot đúng t=60.000s. termination_cause=null/NOT_EXPOSED; không tự gán TIME_LIMIT hoặc CPU budget. Deterministic_time và native response user_time không thay CPU rusage; TTF end-to-end vẫn null/NOT_INSTRUMENTED. Không native progress markers vì fixed logging OFF.

Hard independent validation PASS260assignments, scorerOK với score(12,77,4), per-rule/tier values được instrumentation đối chiếu model values trước xuất lịch. Audit saved assignments/score bằng installed Core với CpSolver guard cho cùng kết quả; không compile/build/native call thêm. Full assignments/score và available work counters khớp single trace và cả pair members (LP374745 khớp pair, đã có trong single raw response); không suy toàn bộ search trajectory giống nhau.

Feasibility OPTIMAL không là soft optimum; quality_proved=false, optimal_prefix=[]. Witness(0,78,0) tốt hơn theo lexicographic order vì P1=0<12; không cộng tiers hoặc gọi kết quả quality improvement.

## Đối chiếu lịch sử — không pool identities

| Execution group/member | Status | Native wall (s) | Native-boundary CPU (CPU-s) | Whole-child CPU (CPU-s) | Scope/identity |
|---|---|---:|---|---:|---|
| Legacy r1 | UNKNOWN | 60.001373317 | null / NOT_INSTRUMENTED | 62.792184 | identity đã lưu của từng row |
| Legacy r2 | UNKNOWN | 60.002091255 | null / NOT_INSTRUMENTED | 62.733361 | identity đã lưu của từng row |
| Legacy r3 | UNKNOWN | 60.001277716 | null / NOT_INSTRUMENTED | 62.704237 | identity đã lưu của từng row |
| Single ON | OPTIMAL | 55.924939301 | null / NOT_INSTRUMENTED | 58.514631 | identity đã lưu của từng row |
| Pair OFF | OPTIMAL | 49.772831433 | null / NOT_INSTRUMENTED | 52.364844 | identity đã lưu của từng row |
| Pair ON | OPTIMAL | 52.574590097 | null / NOT_INSTRUMENTED | 55.129688 | identity đã lưu của từng row |
| CPU v1 OFF | OPTIMAL feasibility | 46.033664557 | 46.008923000 | 48.614788 | new candidate / native_cpu_v1 / legacy MemTotal |

Các raw identities và accounting6rows trước được giữ trong [accounting audit](tight10-accounting-audit-report.md); row mới là candidate riêng, không thành repeat thứ4/5 của campaign hoặc pair. Native-boundary CPU của các runs cũ **chưa được instrument**, không suy từ whole-child ratio, response user_time hoặc deterministic_time và không fill null bằng0. Ba UNKNOWN/status/score-null/quality-NOT_RUN/failed63 và toàn108campaign receipts giữ nguyên; không median/P95/SLA/speed-up/causal claim.

Lượt mới thành công khi MemTotal khớp legacy nên không cần snapshot−4KiB để có diagnostic success này; vẫn không chứng minh MemTotal không có ảnh hưởng hoặc giải thích historical UNKNOWN. Workload/context/wrapper/time khác; native CPU≈wall ở lượt này không cho biết native CPU của các UNKNOWN. Root cause về frequency/thermal/scheduling/search progress lịch sử vẫn chưa xác định; không quy compiler/rules/symmetry từ counters.

## Workload/power và operational limits

| Snapshot | UTC | Load average1/5/15min |
|---|---|---|
| Parent pre | 2026-10-27T16:21:55.742469+00:00 | [0.0869140625, 0.314453125, 0.5595703125] |
| Parent post | 2026-10-27T16:22:42.553820+00:00 | [0.89501953125, 0.50390625, 0.61376953125] |

Child pre-admission riêng tại2026-10-27T16:21:56.402002+00:00; raw context trong child-identity.json. AC Mains online1, USB online1/statusCharging, BAT0 Full100 ở available snapshots, power_changed_or_unknown=false. Giữ workloadUNCONTROLLED/competingUNKNOWN, comparabilityLIMITED; load là rolling observation, không VERIFIED_IDLE, watts hoặc proof frequency/thermal/power ổn định suốt interval. Không đổi power/affinity/env, kill jobs hoặc profiler.

Không watchdog/resource stop/signal hoặc unconfirmed reap; child exit0, raw wait0, measurementOK; owner shared **IDLE** sau persist/reap. Không retry kể cả result không UNKNOWN. N=1 không chứng minh reproducibility hoặc hứa60s luôn đủ.

## Artifacts và lệnh thực chạy

- [CPU result](../benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1/cpu-result.json), [terminal](../benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1/terminal.json), [manifest](../benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1/manifest.json), [native trace-result](../benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1/attempt/trace-result.json), raw parameters/response/assignments/independent checks trong attempt.
- Manifest **19 file entries**, SHA256 `075a5dadd25ae2c6b5879dd8664041ebaab9362874f0bc7bf31a8116fb5539b5`; exact membership và mọi hashes khớp. Candidate/driver hash không đổi; **168protected hashes** trước implementation giữ nguyên, old artifacts không bị ghi lại.
- [Preflight](../benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1-audit/preflight.json), [verification](../benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1-audit/verification.json), parent stdout/stderr ở audit root ngoài sealed run root. Read-only preflight-before-approval được giữ riêng; không dùng nó thay fresh gates sau approval.

Một lần native parent invocation, exit0 (stdout/stderr redirect vào audit root):

```sh
/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1/venv-solver/bin/python -I /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/trace_tight10.py run-cpu --root /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1 --authorization /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-native-cpu-20261027-v1/cpu-authorization.json
```

Installed `python -I -` scripts ghi approval/preflight và audit saved results với native constructor guard, additional native calls0; audit không rebuild model. Kiểm arithmetic/raw bindings/identities/options/callbacks/assignments-score/protected hashes PASS.

| Kiểm tra sau run | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS |
| `uv run --extra solver pytest benchmarks/tests/test_trace_tight10.py -q` |109PASS,0.73s,FakeSolver only/native constructor blocked |
| `uv run ruff check .` |PASS |
| `uv run ruff format --check src tests benchmarks` |PASS54files |
| `uv run mypy` |PASS27Core source files |
| `git diff --check` |PASS |
| Saved-artifact audit |19manifest entries +168protected hashes PASS |

Review độc lập cuối lượt không phát hiện vấn đề trọng yếu; reviewer tự kiểm19manifest digests/membership, candidate/driver hashes, START/CHILD-START/terminal/manifest bindings, exact parent/child identities và CPU arithmetic. Reviewer không chạy native/model/pytest; hard/score và protected168 được review từ audit đã lưu. Không deferred findings.

Không chạy full pytest vì có native solves ngoài one-call approval; những integration paths khác không được chạy lại. Không source/Core/budget/guard/dependency/legacy gate changes hoặc Windows validation. No quality proof, profiler hoặc measurement attempts thêm.

## Đúng một bước tiếp theo — chưa thực hiện

Cập nhật bản tổng hợp TIGHT10 với evidence native-boundary CPU mới, chốt điều đã chứng minh và phần historical UNKNOWN không thể suy ngược từ accounting hiện có. Đây là bước tổng hợp saved evidence, không authorization cho native measurement/tuning thêm.
