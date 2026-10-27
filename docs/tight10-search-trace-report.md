# TIGHT10 — một feasibility trace đã được duyệt

**Đã thực hiện đúng một attempt, không retry. Harness COMPLETE/measurement OK; solver tìm được260assignments hard-valid và score khớp(12,77,4). Native OPTIMAL chỉ thuộc bài feasibility không objective chất lượng; quality_proved=false,optimal_prefix=[].**

Log ghi vào search tại0.15s và tìm nghiệm ở marker55.92s; native wall55.924939301s dưới budget60s. Điều này xác nhận **lần trace này đã vào search và tìm được nghiệm**, không chứng minh đã sửa nguyên nhân của3historical UNKNOWN hoặc đạt performance/quality production.

## Authorization và identity

Thực hiện Task2 của [kế hoạch](superpowers/plans/2026-10-27-tight10-search-trace.md), trên nhánh `feature/phase2a-task5-linux-summary`, source HEAD trước execution `7dd16d4`.

- User chấp thuận rõ candidatev2 SHA256 `802f1f06ab5565d5b09c994fe1cb8c7044c8469096a2e130ce1be53ab9d77006`,run-ID `tight10-trace-20261027-v2`,đúng output_root trong candidate và snapshot MemTotal−4KiB.
- Candidate/driver bytes được kiểm trước run; ghi `authorization.json` strict schema và nguyên văn scope tại `user-authorization.txt` bằng exclusive create. Không có START/attempt trước lời gọi run; không tự tạo authorization cho root/hash khác.
- Fresh parent checks rồi lease/headroom/disk checks PASS; child kiểm authorization,lease và exact runtime/machine/model/input/driver identity trước native solve. Installed Core/wheel/version/path,sources,options,logging đều khớp approved candidate.
- Driver SHA256 giữ `b9d430eedd169ca5c92e344be45eff3d2d6dac3969ce62d924c307af8a9838c8`;input fingerprint `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee`;model SHA256 `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083`.
- Parent headroom tại admission:13,764,210,688bytes available so với3,221,225,472bytes required. Driver chỉ có thể ghi START/spawn sau disk≥256MiB và các gate nàyPASS. Context timestamp `2026-10-27T07:29:22.722418+00:00` là thời điểm ghi workload/admission,không là TTF hoặc timestamp chính xác của solve entry.
- Legacy exact gate vẫn **MACHINE_DRIFT** sau execution; frozen MemTotal40,745,240KiB so với approved/current40,745,236KiB. Không sửa legacy seal/gate/identity hoặc ghi lần này vào108runs lịch sử.

Budget giữ60s/workers1/seed42/gap tolerances0;guards10,000slots/10,000occurrences/100,000placements/1,000,000occupancy terms;watchdog150s và observed RSS target1GiB. Chỉ thêm logging flags/callback theo candidate; không hints,presolve toggles,quality tiers hoặc thay solver defaults khác.

## Kết quả và metrics thực đo

| Chỉ số | Giá trị |
|---|---:|
| Native constructors /solve calls | 1 /1 |
| Native status | OPTIMAL (feasibility) |
| Trace complete /error | true /null |
| Native wall time | 55.924939301s |
| Stage elapsed | 55.935546618s,bao gồm validate/setup/decode |
| Launch→exit child | 56.913798120s |
| Kernel CPU user+system | 58.514631CPU-seconds,toàn child/threads |
| Native user_time | 55.924939330s,native response field,không thay kernel CPU measurement |
| Kernel peak RSS | 150,020KiB =153,620,480bytes ≈146.504MiB |
| Sampled peak | 154,652,672bytes;1,130samples,giữ riêng kernel measurement |
| Deterministic_time native | 46.392866308,không diễn giải như wall/CPU time |
| Branches | 1,150,007 |
| Conflicts | 25,380 |
| Binary /integer propagations | 13,216,444 /13,426,438 |
| Restarts /LP iterations | 87 /374,745 (LP từ raw response) |
| Return code /wait status /stop reason | 0 /0 /null |
| Owner sau reap | IDLE |

Không watchdog/resource stop hoặc unconfirmed reap. Peak/kernel và sampled values đều dưới1GiB; không gọi target là OS hard cap. Kernel CPU có thể lớn hơn wall vì gồm startup/native threads,không suy CP-SAT đã dùng workers>1.

## Phase evidence từ raw log

Trace14,976bytes,SHA256 `5f892f90a097490df21038849f61167a86303b90f6c5a82691f8b6a98108623d`. Các callback chunks được ghi nguyên văn,nên nhiều thông báo nối trên một dòng; không sửa raw log để format lại.

| Marker chính xác | Dòng | Byte offset UTF8 (zero-based) |
|---|---:|---:|
| `Starting presolve at 0.00s` | 49 | 1,190 |
| `Starting search at 0.15s with 1 workers.` | 71 | 11,306 |
| `#1      55.92s main` | 71 | 11,378 |

Marker search cùng1,150,007branches là evidence dương đã vào search. Khoảng lớn của native wall nằm sau mốc search trong lần này;0.15s là elapsed tới native search marker,**không phải CPU time riêng presolve**. Không cộng các presolve substep times hoặc coi số lượng branch/conflict/LP là phép chứng minh bottleneck cụ thể.

Native `#1`55.92s chỉ là solution marker trong solver log. **TTF end-to-end vẫnnull/NOT_INSTRUMENTED**; không thay nó bằng marker,first callback,stage elapsed hoặc native wall.

## Independent validity và quality

Driver xuất260assignments; hard validatorPASS,scorerOK; raw/weighted/per-tier model values khớp independent score. Sau run đã revalidate/recompute lại từ saved assignments bằng installed Core với native constructor chặn; cùng kết quả(12,77,4),không gọi search.

So với witness trên cùng input `(0,78,0)`,lịch này **WORSE theo lexicographic order** vì P1=12>0. P2=77<78 không làm tổng thể tốt hơn; các tiers không được cộng thành scalar để so sánh. Đây là lịch hard-valid từ feasibility stage,không tối ưu chất lượng;không gọi P1/P2/P3 dù còn khoảng4s solver budget.

Native log summary ghi objective/best_boundNA cho satisfaction model;API response-stats có placeholders0. Không dùng các số0 này làm quality objective/proof. `quality_proved=false` và `optimal_prefix=[]` được giữ;không tạo ScheduleResultOPTIMAL để giả quality tối ưu.

## So với3UNKNOWN lịch sử

| Repeat lịch sử | Native feasibility wall (s) | Status |
|---|---:|---|
| 1 | 60.001373317 | UNKNOWN |
| 2 | 60.002091255 | UNKNOWN |
| 3 | 60.001277716 | UNKNOWN |
| Diagnostic trace mới | 55.924939301 | OPTIMAL,hard-valid incumbent |

Đây không phải kết quả cải thiện thuật toán: Core/model/options không đổi,logging và approved machine snapshot khác legacy;old runs không có native counters/phase trace để so cùng lượng công việc. Workload vẫn UNCONTROLLED/competing workloadUNKNOWN;admission load averages2.734375/1.4169921875/1.1484375 và AC online là quan sát,không là kiểm soát throughput/CPU frequency.

Chỉ một diagnostic sample nên không suy reproducibility,logging làm nhanh/chậm hơn,MemTotal4KiB gây đổi status hoặc60s luôn đủ. Không coi UNKNOWN cũ là sai hoặc đổi failed=63/statistics/receipts lịch sử. Root cause của các lần UNKNOWN còn mở.

## Evidence và kiểm chứng sau run

Root được duyệt giữ nguyên:
`.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-trace-prepare-v2/`.

- `authorization.json`,`user-authorization.txt`,`START.json`,`identity-before-run.json` và `attempt/child-identity.json` lưu approval/gates/context.
- `attempt/trace.log`,`stdout.json`,`stderr.txt`,`trace-result.json`,`parameters.txt`,`response.txt`,`response-stats.txt`,`assignments.json`,`independent-checks.json`;`execution.json` ởroot.
- `manifest.json` SHA256 `9bc17b8c08073608196df21198659411a579a8f6ba7625b64a1a577447d0d2bf`,17file digests đã kiểm lại. `candidate-baseline.json` vẫn hash802f1f06…;17inventory entries đều khớp và107protected historical/source/evidence hashes giữ nguyên.
- Audit phụ ngoài run root tại `benchmarks/artifacts/phase2a/tight10-trace-v2-audit/`: parent stdout/stderr và `audit.json` ghi markers/offsets/digests. Không sửa manifest/raw files sau execution để làm đẹp kết quả.

Lệnh run được gọi **một lần**:

```sh
/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1/venv-solver/bin/python -I \
  /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/trace_tight10.py run \
  --root /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-trace-prepare-v2 \
  --authorization /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-trace-prepare-v2/authorization.json
```

Parent stdout TERMINAL/harnessCOMPLETE/measurementOK,exit0;child stdoutTRACE_COMPLETE,stderr0bytes. Không retry hoặc native solve ngoài attempt này.

| Kiểm tra thực chạy sau execution | Kết quả |
|---|---|
| Installed read-only audit vớiCpSolver chặn | 17digestsPASS,107protected hashesPASS;hard-valid260assignments vàscore(12,77,4) recompute khớp;legacy gateMACHINE_DRIFT;ownerIDLE |
| `uv sync --locked --extra solver` | PASS,lock không đổi |
| `uv run --extra solver pytest benchmarks/tests/test_trace_tight10.py -q` | 34passed,0.41s,FakeSolver/native constructor bị chặn |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests benchmarks` | PASS54files |
| `uv run mypy` | PASS27Core files |

Không chạy full pytest vì các fixture native khác sẽ vượt authorization một feasibility trace;test subset trên không native search. Không sửa Core/driver/legacy gate/dependencies,hints hoặc budget/guards. Windows BLOCKED;đây không là nghiệm thu vận hành hai OS hoặc toànPhase2.

## Đúng một đề xuất tiếp theo, chưa thực hiện

**Lập kế hoạch một cặp đối chứng logging bật/tắt** trên cùng `c10-tight-s101`/compiled model/seed42/workers1/budget60s/guards,thu final native counters ở cả hai mode và ghi workload/power trước mỗi run. Mục đích là có căn cứ đánh giá độ nhạy với instrumentation/wall budget trước khi chọn tuning,không suy nguyên nhân từ một lần thành công. Mode tắt logging cần tooling/snapshot được duyệt riêng;không dùng candidatev2 hiện tại để bypass logging policy hoặc chạy thêm. Lượt này không lập/chạy cặp đối chứng đó.

## Review cuối và trạng thái bàn giao

Fresh reviewer không findings. Reviewer tự kiểm17manifest digests,candidate/driver hashes,107protected hashes,parent/child identity snapshots,raw markers/byte offsets/counters/metrics; tự recompute260assignments hard-valid vàscore(12,77,4) bằng installed Core dưới guardCpSolver. Không rerun tests/runtime gate/model construction/search;test-command results dựa trên evidence tác giả đã chạy. Không có deferred findings hoặc fix pass,không đổi source sau approval.

Báo cáo/plan chronology được lưu trên nhánh hiện tại,chưa merge/push. Đã dùng quyền user cấp cho đúng một native solve;mọi trace/thí nghiệm tiếp theo cần yêu cầu riêng và snapshot/policy tương ứng. Các artifacts/raw results/candidate lịch sử không bị viết lại.
