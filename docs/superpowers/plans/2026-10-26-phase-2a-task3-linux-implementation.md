# Phase 2A Task 3 Linux — Resource Supervisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (Native, kế thừa phương thức đã chọn trong phiên) để thực hiện task-by-task sau khi người dùng duyệt plan. Steps dùng checkbox; lượt tạo plan này không triển khai code.

**Goal:** Giám sát đúng một Python child trên Linux, thu peak RSS/CPU bằng wait4, dừng có kiểm soát và kiểm output độc lập, không đổi lỗi harness thành solver infeasible.

**Architecture:** `posix_spawn` khởi chạy installed Python trực tiếp; một owner `wait4(pid,WNOHANG)` quản lý cả status/rusage và cleanup. Primitives giám sát và kiểm CLI output nằm trong một script tooling, tách khỏi Core. Parent verification dùng cùng installed Core; campaign/matrix thuộc Task4, chưa xây dựng.

**Tech Stack:** Python3.12 standard library + Pydantic2.14.1/Core0.2.0 hiện có; OR-Tools9.15.6755 chỉ được child solve dùng. pytest/ruff/mypy theo uv.lock hiện tại, không thêm dependency.

**Spec:** [Phạm vi Linux đã được người dùng duyệt](2026-10-26-phase-2a-task3-linux-scope.md); [Task3 trong kế hoạch vận hành](2026-10-26-phase-2a-operational-validation.md#task-3--resource-supervisor); [Linux preflight](../../phase-2a-operational-report.md); [Core First](../../VNEDU_TKB_CORE_FIRST_CODEX.md).

## Global Constraints

- Linux-only. Windows **BLOCKED**; Task2/3 hai OS vẫn PARTIAL, không coi Linux/mocks là Windows pass.
- Không sửa `src/`, `tests/`, generator, AGENTS, dependency/lock, schema Core, guards hay dữ liệu nghiên cứu. Không API/UI/SQLite, Phase2B/2C hoặc repair.
- Không solve các bộ10/20/40 lớp, không chạy campaign, tuning, sweep/resume/aggregation hoặc công bố performance. Chỉ bounded tiny child tests và một installed-wheel tiny CLI smoke.
- TERM grace **1.0s**, sampling **0.05s**; kernel peak `ru_maxrss*1024` bytes. TTF=null/NOT_INSTRUMENTED. Sampling chỉ telemetry/best-effort stop, không thay kernel peak hoặc hard memory cap.
- Một owner reap đúng PID, không Popen/poll/wait/communicate trên child đo, không wait(-1) hoặc RUSAGE_CHILDREN. Chỉ signal child còn thuộc ownership và chưa reap.
- Raw stdout/stderr/result giữ trong root mới; không overwrite, không tự retry, không publish schedule sau stop/crash/measurement failure.
- Parent SIGKILL/uninterruptible kernel không có bảo đảm cleanup/deadline; không dựng đo cây descendants. Parent exception/KeyboardInterrupt ghi CANCELLED + nguyên nhân, không thêm enum vào Core.
- Snapshot main71b9ad8, Core tree1efd459b2514f448dcf4ac297989de09eb76a3a1; giữ frozen wheel/lock/bundle của Task2. Trước run thực kiểm lại identity/import; headroom/workload/power và campaign budgets vẫn là gates Task4, không nghiệm thu bằng tiny tests.
- Mỗi task có checkpoint xanh trong ledger; chưa tự commit/merge/push. Người dùng sẽ duyệt Git riêng như các task trước; không xóa worktree/evidence đang giữ.

## Review Focus

1. Child exit giữa wait4 và đọc proc: không gọi mất proc là probe hỏng khi đã exit; pin bằng `test_proc_disappears_on_exit` (Task3).
2. Probe lỗi đồng thời child crash hoặc stop: giữ cả hai evidence, không dùng primary status để xóa nguyên nhân; `test_compound_outcomes` (Task4).
3. Input bị sửa trong khi child chạy: không publish lịch cho identity cũ; `test_input_changes_during_run` (Task5).
4. Child từ chối TERM, KeyboardInterrupt hoặc exception giữa spawn/reap: cleanup đúng PID, không zombie/kill nhầm; native + fault tests Task3.
5. Bản result đúng schema nhưng score/proof hoặc stdout không khớp: tái kiểm bằng CLI hiện có và từ chối; tests Task4, không chỉ trust ScheduleResult.valid_schedule.

## File map và giao diện cố định

| File | Phạm vi |
|---|---|
| Create `benchmarks/run_benchmarks.py` | Tooling contracts, Linux supervisor, CLI output verification và một-run orchestration; chưa campaign CLI |
| Create `benchmarks/tests/test_run_benchmarks.py` | Unit + native Linux + installed-wheel tiny integration; tái dùng root import từ conftest hiện tại |
| Modify `docs/phase-2a-operational-report.md` sau chạy thật | Thêm kết quả Task3 Linux và blockers, giữ nguyên lịch sử Task2 |
| Modify plan vận hành, phần Task3 sau nghiệm thu | Chỉ ghi Linux PASS/Windows BLOCKED; không tick toàn bộ hai OS |
| Ignored `benchmarks/artifacts/phase2a/task3-linux-<id>/` | Root mới cho evidence; giữ nguyên task1-v1/preflight-linux-v1 |

Không tạo module adapters, public Core API, dependency hoặc distribution entrypoint mới. Các model tooling dùng `DomainModel` như generator, strict fields, extra=forbid, literal version1.0; không sửa DomainModel của Core. Float phải finite; không coerce bool/string thành số. Model trước spawn không được tự có số đo0. Import module không truy cập posix-only symbols trước runtime capability check; non-Linux phải báo blocked, không fail import vì thiếu wait4.

### Contract tooling (định nghĩa trong Task1)

| Model | Trường bắt buộc/ngữ nghĩa |
|---|---|
| `RunLimits` | `watchdog_seconds: float>0`, `max_resident_bytes: int>0`; không default budgets; TERM/sampling là constants1.0/0.05 |
| `ExecutionRecord` | `schema_version='1.0'`, argv tuple[str,...], run_dir/stdout_path/stderr_path; pid, raw_wait_status, exit_code, signal đều int\|None; stop_reason, error_type; launch_to_exit_seconds, cpu_seconds là finite float\|None; native_peak_rss_kib, peak_resident_bytes, sampled_peak_bytes là int\|None; sample_count>=0; measurement_status=OK/BLOCKED/NOT_STARTED, reason\|None |
| `OutputVerification` | status=SKIPPED/VALID_SCHEDULE/VALID_CORE_ERROR/INVALID; solver_status\|None; valid_schedule bool; score:ScoreReport\|None; diagnostics tuple[str,...] |
| `RunRecord` | schema_version1.0, harness_status, execution, output, identity (input file SHA/fingerprint, wheel/lock/core identity, actual versions/options), parent_verification_seconds; valid_schedule chỉ true nếu COMPLETE và output đã validate; first_feasible_elapsed_seconds=None, reason=NOT_INSTRUMENTED |

Các nullable fields mặc định None; measurement_status mặc định NOT_STARTED, sample_count=0 và valid_schedule=false. Nullable measurement phải giữ None+reason; sample_count=0 đi với sampled_peak_bytes=None. `launch_to_exit_seconds` đo monotonic ngay trước spawn tới lúc reap, gồm cleanup. Native unit/method lưu tường minh `ru_maxrss`, `KiB`, `linux_wait4`; bytes=KiB*1024. Signal dương và exit_code âm tương ứng; không dùng wait status như exit code. Identity giá trị thực đọc từ evidence/input/runtime, không lấy nhãn môi trường do caller tự đặt thay kiểm chứng.

Stop reasons: None, WATCHDOG, RESOURCE_LIMIT, PROBE_ERROR, PARENT_INTERRUPTED; error_type phân biệt KeyboardInterrupt với unexpected exception. HarnessStatus: COMPLETE, WATCHDOG_TIMEOUT, RESOURCE_STOP, ENVIRONMENT_BLOCKED, MEASUREMENT_BLOCKED, OUTPUT_INVALID, CRASH, CANCELLED. Measurement probe stop dùng PROBE_ERROR nên signal do supervisor gửi không bị gọi là native CRASH.

### API nội bộ tooling

```text
kib_to_bytes(value: int) -> int
supervise_linux(argv: tuple[str,...], run_dir: Path, limits: RunLimits) -> ExecutionRecord
verify_cli_output(input_path: Path, result_path: Path, execution: ExecutionRecord) -> OutputVerification
classify_run(execution: ExecutionRecord, output: OutputVerification) -> HarnessStatus
run_cli_once(*, python: Path, input_path: Path, run_dir: Path,
             preflight_dir: Path, lock_path: Path, input_sha256: str,
             limits: RunLimits, options: SolveOptions) -> RunRecord
```

`supervise_linux` tạo độc quyền run_dir và raw files; caller không tạo trước. `run_cli_once` chỉ điều phối một run, tiêu thụ `preflight_dir/{preflight-manifest.json,environment-solver.json,distribution/*.whl}`; Python phải là executable của parent installed environment, kiểm `sys.prefix`/site-packages và source bytes với wheel, không chỉ Path.resolve của venv symlinks. Recheck lock/wheel/version và hash input trước spawn; fingerprint lấy bằng ScheduleInput. Cả input/options chỉ input1.1/policy0.1 và S01–S04 hiện có; không suy schema mới.

Error root đã tồn tại phải raise FileExistsError mà không ghi/xóa; không trả record giả ghi đè root cũ. Prerequisite failure với root mới lưu ENVIRONMENT_BLOCKED, pid/metrics null. Khi child đã chạy, return record thất bại và giữ evidence; lỗi filesystem làm không lưu được record phải raise rõ, vẫn cleanup child. Việc không thể lưu record không được đổi thành COMPLETE.

## Task 1: Contracts và chuyển đơn vị

**Files:** Create script + tests trong file map.

**Interfaces:** Consumes DomainModel/ScoreReport/SolveOptions của Core; produces bốn models, `HarnessStatus`, constants và `kib_to_bytes` cho Task2–5. Import script không import OR-Tools/model_builder/cp_sat.

- [x] Step1 — Viết tests `test_strict_tooling_contracts`, `test_missing_measurements_are_null`, `test_kib_units`, `test_import_does_not_load_solver`. Fixture `empty_execution`: argv=(absolute sys.executable, "-I", "-c", "pass"), run_dir=tmp_path/"run" chưa tạo, stdout_path/stderr_path nằm trong run_dir, mọi field optional dùng defaults. Assertions chính:

```python
assert kib_to_bytes(1024) == 1048576
# model_validate phải raise ValidationError với schema_version='2.0', extra field,
# watchdog=True/'1'/NaN/inf/0; resident cap=False/0 và missing metric bị gán0 giả.
assert empty_execution.measurement_status == 'NOT_STARTED'
assert empty_execution.peak_resident_bytes is None
```

- [x] Step2 — Run `uv run pytest benchmarks/tests/test_run_benchmarks.py -q -k 'contracts or measurements or kib or import'`. Expected RED: module/API chưa tồn tại, không phải lỗi fixture.
- [x] Step3 — Implement models/constants/conversion, không spawn. `kib_to_bytes` từ chối bool/negative/non-int. Field validators kiểm cặp measurement/value và status; chưa thêm model schema linh hoạt dùng sau.
- [x] Step4 — Run lại cùng command; expected GREEN. Ledger types/nullable semantics để các task sau dùng cùng tên. Không tự commit.

## Task 2: Native spawn/reap và kernel accounting

**Files:** Modify script; tests cùng file.

**Interfaces:** Consumes RunLimits/ExecutionRecord/kib_to_bytes; produces `supervise_linux` đường natural completion. Task3 hoàn thiện timeout/failure branches trước khi nối CLI.

- [x] Step1 — Trong tests định nghĩa `child_argv(body: str) -> tuple[str,...]` bằng absolute sys.executable, `-I -c body`; fixture limit watchdog4.0s/cap256MiB. Viết `test_fast_child_has_kernel_peak`, `test_native_memory_spike`, `test_small_run_does_not_inherit_previous_peak`, `test_unrelated_child_is_not_reaped`, `test_existing_root_is_preserved`, `test_large_stdout_stderr_do_not_block`.
- [x] Step2 — Assertions: exit ngay vẫn exit_code0, pid đúng, measurement OK, peak>0 và `peak_resident_bytes == native_peak_rss_kib*1024`; CPU finite>=0, không assert CPU<=wall; unrelated child vẫn do test owner wait được. Output2MiB mỗi stream lưu đủ; root có sentinel phải giữ nguyên khi FileExistsError.
- [x] Step3 — Native RSS fixture dùng mmap/touch **64MiB** từng page rồi release trước exit; so với run tiny tiếp sau, peak large phải cao hơn small ít nhất **32MiB**, không exact bytes. Child chỉ dùng standard library, không sinh descendants; skip rõ trên non-Linux, không mock rồi claim native pass.
- [x] Step4 — Run `timeout 120s uv run pytest benchmarks/tests/test_run_benchmarks.py -q -k 'kernel or spike or previous_peak or unrelated or existing_root or stdout'`; expected RED vì execution chưa triển khai. Exit124 là test failure, không outcome benchmark.
- [x] Step5 — Implement exclusive output root + fd redirects với posix_spawn; one owner wait4 và waitstatus_to_exitcode, ru_utime+ru_stime, ru_maxrss conversion. Đóng parent fds sau spawn và mọi nhánh lỗi. Không gọi Popen hoặc waitpid để tiện poll. Normal completion chỉ là checkpoint, chưa được gọi production CLI trước Task3.
- [x] Step6 — Run lại command; expected GREEN. Kiểm test cleanup không để child/fds sau completion. Ghi ledger; không sửa guard để cho RSS test pass.

## Task 3: Watchdog, telemetry và cleanup khi lỗi

**Files:** Modify cùng script/tests.

**Interfaces:** Consumes Task2 supervisor; produces đầy đủ lifecycle của `supervise_linux`, gồm stop/error fields, cho Task4/5.

- [x] Step1 — Viết tests tên/expected trong bảng dưới; mỗi nhóm run RED trước rồi mới implement nhánh tương ứng.

| Test | Assertions bắt buộc |
|---|---|
| `test_watchdog_stops_sleeping_child` | watchdog0.10s; child sleep8s; WATCHDOG, TERM đúng PID, reap hoàn tất; elapsed có cleanup, không hứa exact deadline |
| `test_ignored_term_is_followed_by_kill` | child cài SIG_IGN rồi báo ready qua file; watchdog2.0s tính từ trước spawn, assert ready marker đã được ghi, body vẫn bounded8s; KILL chỉ sau TERM grace1.0s; signal9, không zombie |
| `test_sampled_limit_requests_resource_stop` | cap32MiB, child touch64MiB và giữ ngắn để sample; RESOURCE_LIMIT; kernel peak và sampled peak lưu riêng, không assert mọi spike đều bị sample bắt |
| `test_proc_disappears_on_exit` | ENOENT lúc child đã exit + wait4 thu được rusage → OK; không MEASUREMENT_BLOCKED giả |
| `test_live_proc_permission_failure` | lỗi thật khi còn sống → BLOCKED/null+reason cho metric thiếu, stop PROBE_ERROR + cleanup; không fallback0 |
| `test_wait4_eintr_is_retried` | EINTR một lần rồi thành công; giữ deadline và không mất rusage |
| `test_lost_ownership_never_signals_pid` | ECHILD hoặc returned PID sai → BLOCKED; không os.kill PID mất ownership; fault test không tạo real child bị bỏ lại |
| `test_parent_interrupt_and_exception_cleanup` | KeyboardInterrupt và RuntimeError sau spawn → PARENT_INTERRUPTED/error_type đúng; chỉ signal/reap owned child, unrelated process không bị ảnh hưởng |
| `test_spawn_failure_has_no_child_metrics` | executable không tồn tại → pid/exit/CPU/peak null, measurement NOT_STARTED, error_type rõ |

- [x] Step2 — Implement nonblocking owner loop: thử reap trước; nếu chưa exit thì check monotonic deadline, đọc proc RSS, xử lý stop; signal bằng os.kill trực tiếp, không convenience method có thể wait. `/proc/<pid>/statm` resident pages nhân `os.sysconf('SC_PAGE_SIZE')`; sample_count chỉ tăng khi đọc thành công. Chưa có sample thì sampled_peak=None.
- [x] Step3 — TERM gửi tối đa một lần; sau1s dùng KILL nếu vẫn owned/unreaped. `finally` cleanup cả parent exception. Khi ECHILD/mismatched PID, không đoán còn quyền sở hữu hoặc kill PID có thể đã tái sử dụng. Lỗi ghi record phải propagate sau best-effort cleanup.
- [x] Step4 — Run `timeout 120s uv run pytest benchmarks/tests/test_run_benchmarks.py -q`; expected GREEN mọi lifecycle tests hiện có. RSS/timing fixtures bounded; không vòng lặp vô hạn hoặc cấp phát để ép OOM. Kiểm không zombie bằng wait/ownership của test process, không chỉ thấy process biến mất khỏi proc.

## Task 4: CLI output verification và phân loại outcome

**Files:** Modify cùng script/tests.

**Interfaces:** Consumes ExecutionRecord; produces `verify_cli_output` + `classify_run` cho orchestration. Không viết lại evaluator/validator hoặc logic optimal-prefix.

- [x] Step1 — Tạo fixture input từ `tests/fixtures/quality/teacher_preferences.json`; failure-result factory dùng `ScheduleResult(schema_version='1.2', input_fingerprint=p.fingerprint(), status=..., metadata=SolverRunMetadataV12(solver_executed=False), quality=QualityReport(status='NOT_EVALUATED'))`. Fixture failure không giả solver proof hoặc đo performance.
- [x] Step2 — Test `test_cli_exit_status_pairs` cho0/FEASIBLE hoặc OPTIMAL/valid,3/INFEASIBLE,4/UNKNOWN,2/INPUT_INVALID hoặc UNSUPPORTED_FEATURE,5/MODEL_INVALID. Errors không assignments/valid schedule; unknown/unrecognized exit hay native signal → CRASH. Known exit sai payload → OUTPUT_INVALID.
- [x] Step3 — Test `test_malformed_stale_and_forged_outputs`: missing file; invalid UTF8/JSON, duplicate keys, NaN; wrong version/fingerprint, assignments sai hard, score forged, optimal-prefix proof/value sai; stdout và result JSON không bằng nhau. Tất cả INVALID, không publish.
- [x] Step4 — Test `test_valid_error_envelope_is_not_schedule`: exit2 có envelope1.0 của CLI với status INPUT_INVALID/UNSUPPORTED_FEATURE + diagnostics hợp lệ; cho VALID_CORE_ERROR dù không full ScheduleResult. Bất kỳ unknown/contradictory field, payload success thiếu result hoặc invalid envelope → INVALID.
- [x] Step5 — Test `test_compound_outcomes`: WATCHDOG + valid result + measurement BLOCKED giữ tất cả evidence nhưng primary WATCHDOG_TIMEOUT; PROBE_ERROR + signal do chính supervisor gửi → MEASUREMENT_BLOCKED; signal không có stop request + probe lỗi → CRASH; output sai+measurement blocked giữ cả hai, primary MEASUREMENT_BLOCKED.
- [x] Step6 — Run `uv run pytest benchmarks/tests/test_run_benchmarks.py -q -k 'cli_exit or outputs or envelope or compound'`; expected RED vì verification/classification chưa có.
- [x] Step7 — Implement strict JSON/result parse, expected input fingerprint, exit/status mapping và stdout/result consistency. Với success, gọi `tkb_core.cli.main` cho validate-schedule và evaluate-score bằng capture_stdout riêng trong parent một thread; reuse cổng score/proof hiện có, không gọi solve trong parent. Capture cả exit code và JSON. Không chạm private Core APIs. Proof chỉ được kiểm structural/value/prefix consistency như CLI, không tái chứng minh tối ưu hoặc re-solve để xác thực một file OPTIMAL. Error outcomes hợp lệ chỉ kiểm consistency, không validate empty assignments như lịch thành công.
- [x] Step8 — `classify_run`: parent interruption→CANCELLED; watchdog/resource stop→tương ứng; native crash nếu không supervisor stop→CRASH; probe stop/blocked→MEASUREMENT_BLOCKED; invalid output→OUTPUT_INVALID; còn lại COMPLETE. Spawn failure→ENVIRONMENT_BLOCKED. OutputVerification luôn giữ riêng, RunRecord.valid_schedule chỉ bật cho COMPLETE+VALID_SCHEDULE. Skipped verification không được COMPLETE.
- [x] Step9 — Run lại command rồi toàn file với timeout120s; expected GREEN. Nếu reuse CLI phát hiện behavior Core chưa hỗ trợ, báo blocker với tiny evidence, không tự sửa Core trong phạm vi này.

## Task 5: One-run integration, installed wheel và báo cáo

**Files:** Modify script/tests, operational report và Task3 checklist trong kế hoạch vận hành gốc. Không sửa scope hoặc checklist Task4/5 để giả đã xong.

**Interfaces:** Consumes tất cả APIs ở trên + frozen preflight artifacts; produces `run_cli_once(...) -> RunRecord`, không main campaign command, không resume/matrix/export summary.

- [x] Step1 — Viết `test_runtime_identity_mismatch_blocks_before_spawn`, `test_input_changes_during_run`, `test_stopped_run_never_publishes_schedule`, `test_record_json_roundtrip`, `test_installed_wheel_tiny_cli_roundtrip`.
- [x] Step2 — Fixture tiny all tiers: copy teacher_preferences input, thêm S02 global limit1 AM/PM P1; S03 global limit1 P2; S04 global window2..2 AM/PM P3; mọi weight1. Chỉ3 occurrences; positive installed smoke phải valid, có4 rule scores và vector(1,1,2), giống Task2 smoke. Options=time10s/workers1/seed42; supervisor watchdog15s/cap256MiB cho smoke, không phải campaign budget.
- [x] Step3 — Assert identity mismatch (wheel/lock/version/editable path/input SHA), non-Linux hoặc thiếu API chặn trước spawn với ENVIRONMENT_BLOCKED. Test root sentinel vẫn FileExistsError, không unlink. Input đổi sau spawn phải OUTPUT_INVALID/INPUT_CHANGED và valid_schedule=false dù child có result. Stop/measurement failure cũng không publish lịch; raw evidence vẫn giữ.
- [x] Step4 — Run nhóm mới, expected RED. Implement `run_cli_once` đúng signature: check identity/imports → spawn đo → recheck input hash → verify output → recheck hash sau verification → classify → write `run.json` cuối cùng; ghi nhận hashes/argv/limits/options thực, raw logs/result, parent verification time riêng. Nội dung run.json dùng strict model serialization finite JSON. Không ghi record COMPLETE trước khi checks xong.
- [x] Step5 — Installed test dùng env `TKB_PREFLIGHT_DIR` trỏ folder frozen Task2. Test driver chạy chính venv-solver Python với `-I`, nạp tooling bằng importlib file path (đăng ký sys.modules); Core phải thuộc site-packages và source bytes khớp wheel. Nếu thiếu artifact, test có thể SKIP trong generic CI nhưng **không nghiệm thu Linux** đến khi chạy explicit và PASS, không bị skip. Native tests đo resource phải chạy thật, không chỉ monkeypatch.
- [x] Step6 — Ghi pass/fail tests vào artifact root mới; integrity của task1-v1/preflight-linux-v1 phải giữ nguyên. Không rerun 36 solves. Chỉ đọc lại hashes/witness evidence và dùng một tiny solve để nối supervisor thực.
- [x] Step7 — Run các checks dưới đây và đọc exit/output; expected toàn bộ PASS, installed test không SKIP, không resource/identity blocker chưa giải quyết. Ghi số tests thật; không cố định total khi thêm tests.

```bash
uv sync --locked --extra solver
uv run --extra solver pytest
uv run pytest benchmarks/tests/test_generate_synthetic.py -q
TKB_PREFLIGHT_DIR="$PWD/benchmarks/artifacts/phase2a/preflight-linux-v1" timeout 120s uv run pytest benchmarks/tests/test_run_benchmarks.py -q -ra
uv run ruff check .
uv run ruff format --check src tests benchmarks
uv run mypy
uv run mypy src/tkb_core benchmarks/generate_synthetic.py benchmarks/run_benchmarks.py
uv build
```

- [x] Step8 — Xác nhận wheel/sdist allowlists vẫn loại benchmark tooling/research; Core/tree/lock không đổi. Cập nhật báo cáo: Linux Task3 PASS trong phạm vi test, Windows BLOCKED, overall Task3 PARTIAL; không latency/RAM/quality SLA hoặc tuyên bố trường lớn xếp được. Ghi measurement method/unit, failures và giới hạn parent SIGKILL/sampled RSS/process-only.
- [x] Step9 — Một fresh final review theo Native/executing-plans, tập trung Review Focus; important fixes cần RED→GREEN + suite xanh. Giữ validated diff để người dùng review/commit riêng; chưa merge/push hay Task4. Không tự sửa Core để vượt gate.

## Tự rà kế hoạch và giới hạn lượt lập kế hoạch

- Coverage: scope§1/2→preflight Task5; lifecycle/metrics→Task2/3; status/independent verification→Task4; contracts/units→Task1; installed smoke/report→Task5. Năm Review Focus đều có test được đặt tên.
- Interfaces: models Task1→supervisor Task2/3→verification Task4→orchestrator Task5; không task nào dựa vào một API campaign chưa xây dựng. Các fixture helper chỉ nằm trong test file.
- Chỉ bốn file runtime/test/report/checklist được phép thay trong triển khai; không thêm CLI product hoặc sửa Core/dependencies. Một run helper hoàn chỉnh không tự cho phép campaign. Mỗi task là checkpoint TDD, không tự Git commit.
- Lượt này chỉ tạo Markdown plan và giữ scope đã được duyệt như tài liệu lịch sử; chưa tạo runner/tests/code, chưa thực hiện native resource tests hoặc benchmark, chưa commit/merge/push. Source/evidence facts dựa trên scope/preflight và source repo tại snapshot, không phải số đo mới.

### Kiểm chứng lúc viết plan — không phải thực hiện các tasks phía trên

Đã chạy `uv sync --locked --extra solver`; `uv run --extra solver pytest -q` → **232 passed,4.35s**; `uv run ruff check .`; `uv run ruff format --check src tests` →44files; `uv run mypy` →27files; `git diff --check` và kiểm local links đều PASS. Không tạo script/tests của supervisor và không chạy build/native resource tests/benchmark. Chỉ hai Markdown scope+plan được tạo/cập nhật;12 dirty context files và main giữ nguyên, index rỗng.

## Ghi nhận thực thi sau khi người dùng duyệt

Đã triển khai Native trong branch feature/phase2a-task3-linux-supervisor, chưa commit/merge/push. Các checkbox ghi completion của phần Linux bằng nhóm tests tương đương/toàn file; không có benchmark hoặc Task4 campaign. Final352tests PASS (232+38+82), installed-wheel tiny smoke PASS, static/build checks PASS. Một fresh review nêu4Important đã được xử lý bằng tests/fix pass; chi tiết cùng giới hạn và rulings trong [report](../../phase-2a-operational-report.md#task-3-linux--resource-supervisor-triển-khai-sau-task-2). Windows BLOCKED, không nghiệm thu hai OS.

Rulings khi triển khai: POSIX_SPAWN_OPEN thay DUP2/CLOSE (đã có regressionfd holes); waitid WNOWAIT chỉ kiểm ownership, wait4 vẫn là sole reaper; mask SIGINT tạm lúc spawn/reap và khôi phục; repeated backend failure phải báo REAP_UNCONFIRMED, không cam kết reap khi backend không còn hoạt động. Hai native comparison/SIGINT tests dùng standalone lightweight driver; actual kernel metrics không bị chỉnh/trừ. Chưa thay Core/lock/generator; caller/evidence phải xem measurement status, không coi CANCELLED/blocked là thành công.
