# TIGHT10 Native Feasibility CPU Measurement Implementation Plan

> **For agentic workers:** Dùng `superpowers:executing-plans` khi user yêu cầu triển khai, theo từng task và checkboxes. Lượt lập kế hoạch này chỉ docs. Task 1 tương lai: instrumentation/fake tests/build-only prepare, chặn CpSolver. Task 2 tương lai: cần approval mới cho đúng một attempt/run-ID/root/candidate hash. Không tự chuyển Task 1→Task 2.

**Goal:** Đo CPU user+system trong boundary của đúng một native feasibility call và lưu final native work counters kể cả UNKNOWN; tách khỏi kernel accounting toàn child đã có.

**Architecture:** Mở rộng `checked_solve` của `benchmarks/trace_tight10.py` ngay quanh bound `native_solve(model)` sau parameter/model/callback guards. Dùng Linux `resource.getrusage(RUSAGE_SELF)` và monotonic_ns, không sửa Core. Một profile cố định logging OFF, single-run envelope/approval mới; tái dùng installed identity/build checks, shared owner, headroom/disk/AC admission và Linux supervisor. Không tạo profiler, polling thread hoặc benchmark matrix.

**Tech Stack:** Python3.12.3, pinned OR-Tools9.15.6755/Pydantic2.14.1, standard library hiện có; không dependency mới.

**Spec:** [Core First](../../VNEDU_TKB_CORE_FIRST_CODEX.md), [accounting audit và khoảng trống](../../tight10-accounting-audit-report.md), [evidence synthesis](../../tight10-evidence-synthesis.md), [frozen trace protocol](2026-10-27-tight10-search-trace.md), [logging pair policy](2026-10-27-tight10-logging-pair.md). Yêu cầu mới của user chỉ cho phép lập kế hoạch; những đoạn “đã chạy” trong sources là lịch sử.

## Global Constraints

- Nhánh `feature/phase2a-task5-linux-summary`, baseline `4d56a2e`. Hiện tại không implementation/tests mới, capture runtime/context, build/compile/prepare/candidate hoặc solver/search/profiling. Chỉ thêm plan và link từ audit report.
- Target duy nhất `c10-tight-s101`; không thay input/witness/fingerprint/Core/wheel/solver defaults, hints, locks, presolve, reorder hoặc quality tiers. Không Phase2B/2C/research/integration; Windows **BLOCKED**.
- Mỗi future attempt giữ native wall budget **60s**, workers **1**, seed **42**, gap tolerances **0**; watchdog **150s**, RSS observed target **1GiB**, không OS hard cap. Guards **10,000 slots /10,000 occurrences /100,000 placements /1,000,000 occupancy terms**. Admission headroom≥**3GiB**, disk≥**256MiB**, observed AC_ON trước parent spawn/child solve.
- Đúng **một fresh child, tối đa một native call**, không pair/repeat/warmup/pilot/retry/resume, không đổi budget sau outcome. Thêm CPU clock không biến wall budget thành CPU budget hoặc gia hạn đến khi có UNKNOWN/nghiệm.
- Logging fixed **OFF**: log_search_progress=false, log_callback=None, log_to_stdout=false, log_to_response=false; không solution/bound callback. Đây là quyết định thiết kế cho phép đo mới, không thay default của Core hoặc historical single/pair APIs.
- Three historical repeats, single trace và pair giữ nguyên identities/status/nulls/receipts; mọi approval trước đã tiêu thụ, không cấp quyền run mới. Legacy gate không sửa hoặc normalize MemTotal−4KiB.

## Identity cần giữ và snapshot mới

| Field | Giá trị giữ nguyên |
|---|---|
| Input fingerprint | `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee` |
| Input SHA256 | `7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735` |
| Witness SHA256 | `f9b5274529c9d1bd4d4c301b2626336bd0128b38b57901b90627ca4be1121a57` |
| Compiled feasibility proto SHA256 | `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083` |
| Core wheel SHA256 | `1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9` |
| uv.lock SHA256 | `e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084` |

Installed interpreter giữ `/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1/venv-solver/bin/python`, invoke `-I` và absolute driver path; Core phải từ installed site-packages khớp wheel, không editable .venv. Driver source hash sẽ thay đổi khi Task 1 triển khai; không tái dùng candidate568c… hoặc802f… có hash driver cũ.

## Boundary và measurement contract

**Chọn clock:** `getrusage(RUSAGE_SELF)` trả user/system của **mọi thread trong child hiện tại**, lấy delta ngay quanh bound native call. `RUSAGE_CHILDREN` ở parent/wait4 vẫn là whole-child accounting, không thay phép đo này; `thread_time` chỉ đo calling thread nên không dùng. `process_time_ns` có thể cho tổng CPU nhưng không tách user/system; không thêm clock thứ ba khi rusage đủ contract.

Thứ tự cố định trong `checked_solve`: mọi policy/model/callback guards → lấy wall_start bằng monotonic_ns → lấy CPU_start → gọi bound native_solve(model) một lần → lấy CPU_end ngay khi return/exception → lấy wall_end trong finally → đọc response/counters và decode/validate như hiện có. Không build/hash/serialize/I/O hoặc lấy operational context giữa CPU_start và native entry, hoặc giữa native exit và CPU_end. Exception bookkeeping chỉ giữ loại lỗi/return code; không bỏ post-read khi native raise.

- CPU delta user/system/sum có units **CPU-seconds**, wall delta từ nanoseconds có units **elapsed seconds**. Lưu cả raw start/end values và clock/scope/boundary policy version `native_cpu_v1`.
- Khoảng wall bao ngoài hai rusage reads; CPU delta có overhead clock/bookkeeping rất nhỏ quanh boundary và mọi child threads chạy trong khoảng đó. Ghi giới hạn, không tự trừ estimated overhead hoặc tuyên bố zero perturbation. Không calibrated benchmark mới trong Task 1.
- Loại khỏi CPU interval: Python/model setup, parameter/model/callback guards, compiler, response extraction, decode, independent validation/scoring và ghi files sau return. Kernel wait4 vẫn gồm toàn child; parent admission/verification không thuộc child.
- Không thể tách riêng CP-SAT thread CPU khỏi background library threads trong cùng child hoặc suy frequency/cache/thermal/CPU instructions từ CPU seconds. Ratio CPU/native-boundary wall có thể>1; không suy solver worker count/idle từ ratio.

Result mới có `native_solve_measurement`: `measurement_status=OK|BLOCKED|NOT_ENTERED`, `reason`, `call_entered`, `call_returned`, `native_return_code`, `native_exception`, `wall_start_ns/end_ns`, `cpu_start/end={user_seconds,system_seconds}`, `user_seconds`, `system_seconds`, `cpu_seconds`, `wall_elapsed_seconds`, `cpu_wall_ratio` và `ratio_reason`. Thiếu số đo thì null+reason; CPU=0 là giá trị hợp lệ, không nhầm với missing. Delta âm/nonfinite hoặc wall≤0→BLOCKED, không clamp về0. Cần phân biệt wrapper solve attempts hiện có với **actual native entry**; CPU-specific report đếm native_call_count từ record, không coi wrapper attempt=1 là proof đã enter.

**Failure contract:** pre-clock read lỗi→measurement_status=BLOCKED,call_entered=false, không native call; vẫn giữ available parameter/callback snapshot. Post-clock read lỗi→BLOCKED nhưng giữ raw native return code/exception và available response/counters; nếu native trả code thì cho `_run_stage` hoàn tất decode/validation để giữ evidence, không thay return code bằng lỗi clock. Native exception được re-raise sau cố gắng đo end, không bị lỗi clock trong finally che mất. Timing có thể OK khi call raised nhưng harness vẫn fail. Parent chỉ công nhận complete measurement khi native returned, timingOK, response/counters contract và independent checks nếu có lịch đều đạt; giữ evidence khi blocked, không retry.

## Counters tại kết thúc/deadline

Lấy response proto/stats **sau native return/exception**, ngoài measured interval; giữ raw response/parameters/callback snapshots. Snapshot các fields đã có: wall_time, native user_time, deterministic_time, num_branches/conflicts/booleans/binary_propagations/integer_propagations/restarts/LP_iterations. Field không có=null+FIELD_NOT_AVAILABLE; không có response=null+NO_RESPONSE. Không dùng native user_time hoặc deterministic_time thay CPU rusage.

- Return sớm với FEASIBLE/OPTIMAL: lưu final counters ngay lúc return; không tiếp tục chạy đến60s.
- UNKNOWN gần budget: lưu final counters/CPU của return đó, score=null, không đổi thành INFEASIBLE/correctnessFAIL. Ghi configured wall budget60s, native response wall và measured boundary wall riêng. Không tự ghi termination_cause=TIME_LIMIT chỉ từ UNKNOWN/elapsed; nếu API không cung cấp cause thì null+NOT_EXPOSED. Counters là số tích lũy khi return, không phải snapshot đồng bộ đúng t=60.000s.
- Watchdog/resource/signal kill trước child persistence: không có post-clock/final counters thì null+CHILD_TERMINATED_BEFORE_FINAL_CAPTURE; chỉ dùng saved partial fields nếu thật sự có. Parent wait4/RSS receipt được giữ riêng, không backfill thành native CPU. Nếu actual native entry không quan sát được sau crash thì native_call_count=null+NOT_OBSERVABLE, không bịa0 hoặc1 từ START marker.
- Không thêm polling/callback/stop_search ngoài logging profile hoặc thay watchdog để ép capture. Không hứa tái hiện UNKNOWN. Một attempt dù result gì cũng dừng; giữ harness stop/correctness contradiction và mọi samples không đạt.

## Candidate, approval và run protocol mới

Task 1 tương lai tạo exclusive root mới `benchmarks/artifacts/phase2a/tight10-native-cpu-<id>/`, ngoài mọi old evidence/campaign/input/preflight roots. `cpu-candidate.json` strict schema_version1.0, kind=`tight10_native_cpu`, status PREPARED_NOT_AUTHORIZED, hoặc preparation-result BLOCKED có reason. **Lượt lập kế hoạch chưa có candidate SHA256**: hash chỉ tính từ actual bytes sau triển khai/tests/source freeze/prepare, không dùng hash của plan làm execution approval.

Candidate freeze run-ID (existing CampaignId), absolute output_root, common_identity exact (Identity canonical ON validate rồi exclude logging, như pair), fixed OFF profile, `measurement_policy` (rusage/self/user+system, monotonic_ns, boundary order/native_cpu_v1, max_native_calls1, return-only counters/missing rules), options/limits, admission/power policy, runtime/source/driver hashes và full legacy diff. Không nới old Identity/Candidate/PairCandidate/approval schemas hoặc deserialize CPU envelope bằng old schema.

Approval mới strict `CpuAuthorization`: action **RUN_ONE_NATIVE_CPU_FEASIBILITY**, approved=true, schema_version1.0, exact candidate SHA256/run-ID/root. User cần chấp thuận actual snapshot/drift/power/workload limitations được Task 1 công bố. Previous single/pair action bị reject; không tạo approval trong prepare. Source/policy/root drift sau freeze cần candidate mới và approval mới; không rebaseline tự động.

Parent/child đều exact-check common runtime/machine/source/input/model/driver + fixed OFF/measurement policies; fresh admission owner/headroom/disk/AC. Giữ shared git-common owner lease, exclusive START/child-start chống direct child/re-entry, bind candidate hash/run-ID/parent PID vào receipts và final manifest; Linux supervisor/reap semantics không đổi. Unconfirmed reap→NEEDS_REVIEW; chỉ IDLE sau reap+receipt persistence. Không retry/resume sau START hoặc thay root để chạy tiếp cùng approval.

Lưu pre/post workload/power ở parent và child pre-admission bằng helper hiện có **ngoài native interval**. Preserve UTC/load/status/raw sysfs power, workloadUNCONTROLLED/competingUNKNOWN; missing/offline AC pre-block, post powerchange/UNKNOWN→comparabilityLIMITED, không bỏ sample. Không đổi governor/affinity/env, kill apps hoặc thu process command lines. Raw/cpu result, independent checks/assignments nếu có, wait4 execution và manifest giữ rõ provenance; parent stdout/audit ngoài sealed run root.

## Review Focus

- Gọi clocks/serialize sai boundary làm measurement trở lại whole-child; tests phải chặn build/decode/validation lọt interval.
- Native return/exception gặp clock failure vẫn giữ raw evidence/original error; không mask hoặc retry.
- UNKNOWN, missing counters và killed child không được đổi thành infeasible/zero/exact-deadline snapshot.
- CPU approval không tái dùng single/pair approval; policy/source/mode/root/budget drift phải chặn trước native call.
- CPU mọi threads trong native boundary khác CPU riêng CP-SAT; report không quy cause/SLA/quality optimum từ một run.

## Task 1 — Implement, fake tests và build-only prepare; đã hoàn tất prepare-only

**Files:** Modify `benchmarks/trace_tight10.py`, `benchmarks/tests/test_trace_tight10.py`; create `docs/tight10-native-cpu-preparation-report.md` và ignored new prepare root. Không sửa frozen runner/generator, Core, dependencies hoặc old artifacts. Không refactor toàn driver/thêm generic timing framework.

**Interfaces:** thêm `measure_native_call(call: Callable[[], CpSolverStatus], sample: dict[str, JsonValue]) -> CpSolverStatus` (type alias từ pinned cp_model, annotation qua TYPE_CHECKING), dùng resource/time standard library; giữ nguyên return object cho Core, chỉ `int(raw_return)` khi lưu JSON; mutate sample kể cả exception để evidence không mất, không inject clocks qua production API (tests monkeypatch). Thêm keyword `measure_cpu: bool=False` vào `trace_feasibility`; old single/pair defaults giữ hành vi không timing (`native_solve_measurement=null`, reason NOT_REQUESTED), CPU-only child truyền logging_mode="logging_off",measure_cpu=True. Tạo strict `CpuCandidate`/`CpuAuthorization`, `prepare_cpu(root: Path, run_id: str) -> dict[str, JsonValue]`, `check_cpu_authorization(root: Path, authorization: Path, *, child: bool=False)` và CPU-only parent/child dispatch. CLI `prepare-cpu --root --run-id`, `run-cpu --root --authorization`, private `_cpu-child`; reject flags/modes không thuộc scope.

- [x] **RED tests measurement:** `test_native_cpu_boundary_excludes_setup_decode_validation` (fake stage kiểm sequence guards→start→one call→end→decode); `test_native_cpu_user_system_delta_and_units` (fake CPU start10/2,end13/3 → user3,sys1,total4; wall2 → ratio2); `test_cpu_zero_missing_negative_nonfinite_and_wall_zero` (zero giữ0, còn invalid→null/reason/BLOCKED); `test_cpu_pre_clock_failure_never_enters_native`; `test_cpu_post_clock_failure_keeps_raw_return_and_response`; `test_native_exception_preserves_original_and_end_attempt`; `test_native_one_call_even_if_stage_requests_second`.
- [x] **RED tests outcomes/scope:** `test_cpu_unknown_keeps_final_counters_without_schedule`; `test_cpu_early_solution_does_not_wait_for_deadline_and_validates_score`; `test_cpu_missing_counter_and_no_response_reasons`; `test_cpu_supervisor_kill_does_not_invent_native_cpu_or_count`; `test_cpu_policy_or_identity_drift_blocks`; `test_single_and_pair_approval_cannot_authorize_cpu`; `test_cpu_owner_ac_headroom_reentry_and_reap`; `test_cpu_prepare_cannot_construct_solver_or_authorize`. Include options/profile/unknown-field/version/root-path escape variants. All autouse real CpSolver blocked; FakeSolver only.
- [x] Run `uv run --extra solver pytest benchmarks/tests/test_trace_tight10.py -q`; Expected: new tests RED because measurement/API absent, existing64 still pass. Implement smallest helpers/contracts/dispatch above; clocks mocked, no native solve. Run again; Expected: GREEN all existing+new tests, no fake clock forcing production budget change.
- [x] Run `uv sync --locked --extra solver`, dedicated fake suite, `uv run ruff check .`, `uv run ruff format --check src tests benchmarks`, `uv run mypy`, `git diff --check`; Expected PASS. Full pytest có native solves ngoài prepare scope thì không chạy, ghi limitation. Freeze source after fixes/review; code change sau candidate→new candidate.
- [x] Only after Task 1 authorized: installed interpreter `-I` invokes prepare-cpu under native constructor guard; check frozen hashes/witness/model build-only, current snapshot/legacy diff. Write candidate exclusive, actual SHA256, policy/fields/limitations vào preparation report; Expected PREPARED_NOT_AUTHORIZED/BLOCKED, no authorization/lease/START/attempt/native calls. Kiểm candidate hash/current driver/source/membership/protected evidence bằng asserts rồi dừng, không chạy Task2.

## Task 2 — Một CPU measurement attempt với approval mới; chưa được phép

**Files:** existing Task1 tooling, fresh authorized run artifacts và `docs/tight10-native-cpu-report.md`; không source/Core changes trong execution.

- [ ] Sau exact user approval mới, ghi original scope và CpuAuthorization; kiểm hash/root/ID/policy/runtime/model/owner/headroom/disk/AC mới. Expected all new gates PASS; legacy vẫn ghi riêng BLOCKED nếu MemTotal drift. Blocker thì giữ reason và dừng, không sửa gate hoặc retry.
- [ ] Invoke run-cpu **một lần**, installed fresh child, one native feasibility call maximum, giữ budget/guards. Expected terminal hoặc blocked/partial có preserved evidence; không tự chạy lại để có UNKNOWN, không extend deadline, không quality stages.
- [ ] Audit raw start/end CPU arithmetic, clock boundary/policies, full applied parameters/callbacks, response/work counters, independent hard/score nếu có lịch, whole-child wait4/RSS riêng, context/provenance/nulls và manifest/reap. Report CPU-boundary measurement vs whole-child accounting; compare từng historical identity riêng, không pool n/SLA/causal logging hoặc frequency claims. Dừng và chỉ đề xuất một bước từ evidence, không tự thực hiện thêm.

## Self-review và kiểm chứng lượt lập kế hoạch

Đã kiểm coverage: boundary clocks, direct-call counter distinction, UNKNOWN/early return/deadline semantics, pre/post-clock failures/native exceptions, kill/missing-data, strict snapshot/approval, workload/power và required tests đều có task sở hữu. Interfaces Task1 được Task2 tiêu thụ nhất quán; mọi checkboxes còn unchecked. Đây là thiết kế đề xuất để user review, không phải approval chạy solver.

Lượt này chỉ đọc AGENTS/Core First, audit report và connected driver/guards/dispatch. Chưa implementation/test mới, candidate/hash, capture clock/runtime/power hoặc build/solver/profiling. Các hashes bảng trên là identity lịch sử cần giữ; candidate mới chưa tồn tại. Lệnh thực chạy: `uv sync --locked --extra solver` PASS; `uv run ruff check .` PASS; `uv run ruff format --check src tests benchmarks` PASS (54 files); `uv run mypy` PASS (27 Core source files); `git diff --check` PASS. Standard-library asserts kiểm links, unchecked tasks, docs-only scope và123protected hashes PASS. Không chạy pytest vì chỉ thay tài liệu và full suite có native solves trái scope; không có kết quả measurement/candidate mới.

## Trạng thái triển khai

Task1 full instrumentation/109fake tests/build-only prepare hoàn tất; xem [preparation report](../../tight10-native-cpu-preparation-report.md). Candidate SHA256 `5585a43eee2ac961591f320b56e743347efe449a976fbed78c7ad620631c2499`, legacy PASS, MemTotal40745240KiB. Task2 pending exact candidate/snapshot approval, chưa native call. Yêu cầu full-plan được thực hiện tới final gate, không tự cấp approval của snapshot chưa tồn tại trước prepare.
