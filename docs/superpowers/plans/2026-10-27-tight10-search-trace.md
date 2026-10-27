# TIGHT10 — Minimal Search Trace Implementation Plan

> **For agentic workers:** Dùng `superpowers:executing-plans` khi người dùng yêu cầu triển khai. **Lượt hiện tại chỉ lập kế hoạch.** Task1 chuẩn bị/test không search; Task2 chỉ được thực hiện khi có yêu cầu chạy riêng trên candidate baseline đã đóng băng. Không tự chạy Task2 sau Task1.

**Goal:** Thu một feasibility trace có giới hạn để phân biệt solver còn ở presolve hay đã vào search trên `c10-tight-s101`, không thay thuật toán/budget/guards.

**Architecture:** Driver chẩn đoán ngoài Core gọi lại đúng installed `_run_stage(..., priority=None, budget=60.0)` dưới instrumentation logging tạm trong một fresh child process. Parent dùng Linux supervisor/ownership/headroom hiện có; dữ liệu/input/Core/wheel giữ nguyên, trace có identity/output riêng và không resume campaign lịch sử.

**Tech Stack:** Python3.12.3, OR-Tools9.15.6755, Pydantic2.14.1 và installed Core wheel hiện có; standard library cho logs/manifests/tests. Không dependency mới.

**Spec:** [Core First, mục4–6/9](../../VNEDU_TKB_CORE_FIRST_CODEX.md), [Phase2A](../specs/2026-10-26-phase-2-quality-design.md), [operational protocol](2026-10-26-phase-2a-operational-validation.md), [bằng chứng witness mở rộng](../../tight10-static-diagnostic-report.md).

## Global Constraints

- Nhánh `feature/phase2a-task5-linux-summary`; baseline lập kế hoạch `d6b2ee6`. Chỉ tài liệu thay đổi trong lượt này; không solver/model build/search/profiling, không gọi execution gate hoặc acquire ownership.
- Khi triển khai sau: tooling tại `benchmarks/`, không sửa `src/tkb_core`, frozen `run_benchmarks.py`/generator/uv.lock, installed site-packages hoặc input/witness/results cũ. Không UI/API/repair/2B/2C.
- Chỉ một target, một instrumented feasibility call; không warmup/pilot/repeat/seed sweep/workers sweep, hint/ablation/presolve toggle hoặc retry tự động. Không chạy quality P1/P2/P3 sau feasibility, dù còn budget.
- Giữ solver60s/workers1/seed42, relative_gap_limit=absolute_gap_limit=0; watchdog150s, observed RSS target1GiB, fresh headroom≥3GiB và disk free≥256MiB theo protocol hiện có. RSS target không được gọi là hard memory cap.
- Guards: max_slots10,000; max_occurrences10,000; max_placements100,000; max_occupancy_terms1,000,000. Không đổi solver defaults khác ngoài các logging fields được liệt kê.
- Logging làm thay đổi chi phí thực thi và có thể thay đổi kết quả dưới wall budget; trace là dữ liệu chẩn đoán, không mẫu bổ sung cho108runs hoặc benchmark so tốc độ.
- Windows BLOCKED. Không sửa machine identity cũ, tự chấp nhận drift hoặc nới gate để cho chạy.

## Identity và điều đã biết

Witness mở rộng đã thỏa4,700variable domains/1,255constraints;60rule scores khớp(0,78,0). Ba runs lịch sử UNKNOWN ngay feasibility, không có trace phân biệt presolve/branching. Điều này chưa xác định nguyên nhân gốc hoặc chứng minh optimum.

| Trường phải giữ | Giá trị |
|---|---|
| Dataset | c10-tight-s101 |
| Fingerprint | `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee` |
| input.json SHA256 | `7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735` |
| witness.json SHA256 | `f9b5274529c9d1bd4d4c301b2626336bd0128b38b57901b90627ca4be1121a57` |
| Compiled feasibility proto text SHA256 | `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083` (bytes UTF8 của str(proto),không thêm newline) |
| Historical campaign plan SHA256 | `6b8a324560b1857555f686a955f5af79468e5f80a00d830466b9253e648a9e61` |
| Core wheel SHA256 | `1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9` |
| uv.lock SHA256 | `e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084` |
| Core source SHA256 | `9869e2e55abc4869ba026e8e28a88b045e0dc1f9e1bb2ac96ea624fde1defd80` theo generator source manifest |

Target interpreter giữ nguyên installed-wheel environment:
`/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1/venv-solver/bin/python`.

Phải chạy identity capture trong **chính interpreter đó**, không lấy `sys.executable/sys.prefix` từ editable `.venv` ở checkout để gọi là runtime match. Tooling repo được import tường minh từ đường dẫn đã kiểm hash; `tkb_core.__file__` vẫn phải là installed site-packages và khớp wheel qua `_runtime_identity`.

## Instrumentation tối thiểu, không sửa Core

1. Tái dùng installed `prepare`, `build_model`, `compile_soft`; đối chiếu input/fingerprint/proto hash và model.validate trước search. Không chép `_run_stage` hoặc compiler vào driver.
2. Driver lưu original `cp_model.CpSolver`, tạm patch constructor trong child bằng factory chỉ cho phép **một** instance. Factory tạo original solver và chỉ thêm:
   - `parameters.log_search_progress=True`;
   - `parameters.log_to_stdout=False`;
   - `parameters.log_to_response=False` để không giữ toàn log trong response;
   - `solver.log_callback` ghi nguyên từng chunk vào UTF8 `trace.log` mở mới, flush sau write. Không parser/tính score trong callback, không solution/bound callback.
3. Gọi `_run_stage(prepared,built,compiled,options,None,60.0)` đúng một lần. Hàm hiện có clear_objective,set60s/workers1/seed42/gap0 và decode assignments. Factory/patch chỉ tồn tại trong child và được khôi phục bằng context manager; không gọi `run_quality`, public solve hoặc CLI solve.
4. Ghi parameter snapshot và instrumentation flags; dùng fake solver tests để khóa việc `_run_stage` truyền đúng budget/options và không có constructor/solve thứ hai. Không đặt stop_after_first_solution,max_deterministic_time,search strategy,presolve flags hoặc hint; model/proto phải khớp trước call.
5. Ghi stage start/end monotonic và native response fields khi có response: raw status,wall/user/deterministic time,num_branches,num_conflicts,num_booleans,num_binary/num_integer_propagations,num_restarts; lưu `str(response_proto)` và `response_stats()` nguyên bản. Stage elapsed gồm validate/setup/decode, không gọi nó là thời gian thuần search.
6. Log write/callback failure phải giữ raw stdout/stderr và báo trace incomplete/capture error; không coi thiếu log là presolve-only hoặc tự chạy lại. Crash/kill có thể không có response: fields giữ null+reason, không gán0 hay INFEASIBLE.

Đã đối chiếu instrumentation với package source cài local: `cp_model.py` constructor/solve tại1744–1773 có log_callback và đăng ký qua SolveWrapper; properties response/counters tại1870–1946; `cp_model_helper.pyi` có log_search_progress/log_to_stdout/log_to_response và response counters. Đây là xác nhận API/source, **chưa kiểm live logging trên native solver**.

### Cách đọc trace

- Đọc raw log trước, chỉ trích các phase boundary có thông báo/timestamp rõ ràng trên phiên bản này; lưu nguyên marker và vị trí trong file. Không xây parser đa phiên bản hoặc giả marker luôn tồn tại. Fake log tests kiểm cả thiếu/truncated/reordered markers.
- Marker vào search rõ hoặc num_branches>0 là evidence đã vào search. num_branches=0 một mình không chứng minh bị kẹt ở presolve; có thể model đã giải/hết thời gian trước branching hoặc log thiếu.
- Nếu có presolve→search boundary, ghi native elapsed tới boundary, gọi đúng tên `elapsed_to_search_marker`; không đánh đồng toàn khoảng startup/loading/presolve với CPU presolve time. Không cộng wall của các presolve substeps có thể chồng nhau.
- Log bị ngắt/thiếu markers hoặc response không có thì kết luận UNDETERMINED và nêu phần evidence thiếu. Không biến “không thấy marker” thành “solver chưa vào search”.
- Không đo TTF bằng callback ở kế hoạch tối thiểu này: giữ null/NOT_INSTRUMENTED. Không biến first callback/log arrival,feasibility solver wall hoặc native solution marker thành TTF end-to-end.

## Execution identity gate — giữ gate cũ, đóng băng baseline chẩn đoán riêng

Đọc trực tiếp `/proc/meminfo` trong lượt lập kế hoạch: hiện `40745236kB` so với frozen `40745240kB`, vẫn lệch4KiB; nguyên nhân chưa xác minh. **Chưa chạy `_check_campaign_identity` hoặc current runtime gate** trong lượt này. Không dùng editable interpreter để giả full gate PASS.

- `_check_campaign_identity` cũ so chính xác seal/bundle/source/preflight/runtime/machine. Campaign108/108 giữ nguyên COMPLETE lịch sử; drift không được bỏ qua, clamp, thêm tolerance hoặc sửa environment/seal cũ. Không resume/retry campaign cũ để thu trace.
- Task1 tương lai tạo **candidate diagnostic baseline**, không cấp quyền chạy: cùng frozen input/witness/model/wheel/lock/controller/generator và runtime policy; ghi machine snapshot thực tế,source/driver hashes,logging settings,options/limits,legacy comparison với mọi differing fields. Driver hash riêng, không thay frozen `tooling_source_sha256` của runner.
- Nếu source/input/model/wheel/versions/path không khớp: BLOCKED, dừng để điều tra; không tự rebaseline những thay đổi đó. Nếu khác machine identity: giữ legacy gate BLOCKED_MACHINE_DRIFT và candidate NOT_AUTHORIZED; không coi4KiB là hợp lệ ngầm. Muốn chạy trên máy hiện tại cần người dùng duyệt riêng **hash của candidate baseline mới cùng drift đã công bố**.
- Authorization phải gắn approved baseline hash với một run ID và một output root mới cụ thể; START tồn tại thì không chạy lại,không dùng cùng authorization cho root khác. Approval mới chỉ cho phép diagnostic run trên exact approved snapshot, không sửa verdict legacy gate hoặc chứng nhận tương đương benchmark. Không có approval/hash cụ thể → không spawn search child; elapsed time không là approval.
- Sau approval, so toàn bộ captured runtime/machine/input/model/driver/options/logging với baseline mới **exactly**, không tolerance; bất kỳ drift mới nào →BLOCKED. Không ghi đè baseline; thay đổi code/artifact đòi candidate mới và duyệt lại, không tự retry.
- Parent precheck và child recheck dùng `_runtime_identity`/`_machine_identity` trong target installed interpreter; source/model/runtime hashes phải khớp. Child build/recheck chỉ sau baseline approval nhưng trước constructor solver. Machine gate được kiểm lại ngay trước `_run_stage` để tránh gap giữa prepare và run.

## Process ownership và output

Parent dùng lại `_repository_owner_root`/`_campaign_owner` với **cùng repository-wide owner scope**, fresh `check_headroom(1GiB)`,Linux `supervise_linux(argv,run_dir,RunLimits(150.0,1GiB))`. Không gọi `run_cli_once` vì hàm đó cố định CLI solve không có instrumentation. Giữ semantics NEEDS_REVIEW nếu PID/reap/ownership không xác nhận, không xóa marker stale hoặc signal PID khác để mở gate.

Prepare phải tạo output root mới ngoài campaign/bundle/preflight/Task1/auxiliary evidence và ghi candidate exclusive. Run chỉ tiêu thụ đúng prepared root đã được duyệt,ghi authorization/START mới rồi tạo subdirectory `attempt/` chưa tồn tại cho `supervise_linux`; không yêu cầu xóa prepared root để chạy. START hoặc attempt/ tồn tại thì từ chối chạy lại,không overwrite hoặc auto resume. Parent được launch bằng target installed Python, `-I`, driver path tuyệt đối đã freeze; prepare capture chạy trực tiếp trong parent này. Child dùng cùng interpreter và private subcommand `_child`; entry này phải tự kiểm authorization/baseline hash,approved output root/run ID và lease RUNNING của parent đúng PID,không là đường bypass khi gọi trực tiếp. Root marker/lease còn hiệu lực tới khi child được reap và artifacts đã ghi; gate/admission checks phải ở trong lease trước spawn. Missing child-reap confirmation không được giải phóng ownership thành IDLE.

Output tương lai dưới `benchmarks/artifacts/phase2a/tight10-trace-<unique-id>/`: candidate/authorization,identity-before-run và final manifest ở root; artifacts của child/supervisor trong `attempt/` mới.

| File | Nội dung |
|---|---|
| candidate-baseline.json / authorization.json | Exact snapshot+legacy drift; scope approval/hash riêng, không tự phát authorization khi prepare |
| identity-before-run.json / child-identity.json | Rechecks,headroom/disk/workload/power,các source/input/model hashes |
| trace.log / stdout.json / stderr.txt | Native callback chunks và supervisor raw streams, không trộn log vào stdout JSON |
| parameters.txt / response.txt / response-stats.txt | Applied solver parameters và native response khi thực có |
| execution.json / trace-result.json | Harness status/measurements tách raw solver status,stage boundaries/counters/phase evidence |
| assignments.json / independent-checks.json | Chỉ ghi assignments nếu có nghiệm; hard validator,scorer và model-expression comparison |
| manifest.json | Hash inventory,run ID,approved baseline hash,driver/source identities; missing fields/files nêu reason |

Nếu có nghiệm: dùng public hard validator/scorer và so raw/weighted/tier với StageOutcome như `run_quality` đang làm; mismatch→correctnessFAIL,không publish valid schedule. Feasibility raw OPTIMAL không là quality optimum; không phát optimal_prefix/quality proof. Nếu UNKNOWN không assignments; nếu INFEASIBLE trong cùng verified model đã có witness thì báo contradiction cần điều tra,không nhận input vô nghiệm hoặc tự nới budget.

## Review Focus

- Editable interpreter hoặc model/driver/wheel drift phải chặn trước search; MemTotal4KiB không tự miễn gate.
- Log write fail/truncated log hoặc0branches không được phân loại presolve-only.
- Một constructor/call,priorityNone,budget60/logging-only changes; không lỡ gọi các quality tiers.
- Owner/PID/reap/headroom thất bại phải giữ evidence và không kill nhầm process/retry.
- FeasibilityOPTIMAL,UNKNOWN,score recomputation và harness errors phải được báo riêng, không giả optimality/TTF.

## Task 1 — Triển khai prepare/instrumentation và tests không search, ĐÃ PREPARE KHÔNG SEARCH

**Files tương lai:** Create `benchmarks/trace_tight10.py`, `benchmarks/tests/test_trace_tight10.py`; chỉ docs bổ sung nếu cần. Đọc/tái dùng runner helpers và installed `_run_stage`, không sửa chúng.

**Interfaces:** `capture_identity() -> dict[str,JsonValue]` chạy trong installed interpreter; `compare_identity(expected: dict[str,JsonValue], actual: dict[str,JsonValue]) -> tuple[str,...]` trả differing field paths; `trace_feasibility(prepared: PreparedProblem,built: BuiltModel,compiled: CompiledSoft,options: SolveOptions,log_path: Path) -> dict[str,JsonValue]` gọi một stage chỉ khi parent/child run authorization gates đã PASS. CLI hai mode public tường minh `prepare` và `run`, không default execution; private `_child` chỉ là entry của supervised child theo lease/authorization protocol trên. Prepare không gọi trace_feasibility. Unknown flags/schema fields/version bị từ chối.

- [x] Viết failing tests với constructor thật bị chặn,inject FakeSolver/FakeStage: `test_prepare_never_constructs_solver`; `test_runtime_or_model_drift_blocks`; `test_legacy_memtotal_drift_needs_explicit_new_baseline`; `test_approved_snapshot_new_drift_blocks`; `test_only_one_feasibility_call_and_parameters_unchanged`; `test_callback_error_and_truncated_log_remain_incomplete`; `test_zero_branches_is_not_presolve_proof`; `test_missing_approval_or_owner_prevents_spawn`; `test_direct_child_requires_matching_parent_lease_and_authorization`; `test_unknown_and_feasibility_optimal_have_no_quality_proof`; `test_no_schedule_on_independent_mismatch`. Test stage flags/gaps/options,exclusive output và callback patch restoration cả khi exception.
- [x] Chạy `uv run --extra solver pytest benchmarks/tests/test_trace_tight10.py -q` để quan sát RED; chưa có module/tests ở lượt hiện tại. Các tests mới phải hoàn toàn fake/no-search,không gọi native tiny solve để làm smoke logging.
- [x] Implement minimum single-target driver theo protocol trên. Strict manifests dùng schema_version1.0 và key validation; serialize bằng helper hiện có,không thêm frameworks hoặc benchmark matrix. Tests gate/reap/cancel mô phỏng supervisor boundary; reuse semantics hiện có,không reimplement signaling.
- [x] Chạy lại tests mới GREEN, `uv sync --locked --extra solver`,ruff check,format src/tests+benchmarks,mypy; không full pytest có solve nếu scope vẫn cấm search.
- [x] Chạy **chỉ prepare không search** bằng target installed interpreter để tạo candidate mới,verify hashes/build-only và ghi exact legacy/current identity. Giữ constructor thật bị chặn trong prepare. Output phải tự mô tả PREPARED_NOT_AUTHORIZED hoặc BLOCKED có reason; không in READY_FOR_SEARCH chỉ vì tests green. Giao candidate hash/drift và dừng,chưa thực hiện Task2.

## Task 2 — Một trace đã được duyệt, ĐÃ THỰC HIỆN MỘT ATTEMPT ĐƯỢC DUYỆT

**Files tương lai:** Tooling Task1 và fresh trace evidence; report `docs/tight10-search-trace-report.md`. Không sửa Core/historical artifacts.

- [x] Chỉ sau yêu cầu rõ cho **một run** trên approved candidate hash,ghi authorization scope. Chạy gate/lease/headroom/installed identity rechecks rồi một supervised child; không auto warmup,repeat hoặc gọi lại sau bất kỳ failure.
- [x] Giữ native logs,response và harness metadata,validate mọi assignments/score nếu có; diễn giải phase boundaries/counters với missing-data limits đã nêu. Không cần profiler hoặc second run để hoàn tất báo cáo nếu trace thiếu.
- [x] Báo trạng thái observed presolve/search/UNDETERMINED cùng raw evidence,logging overhead/comparability limits và đúng một đề xuất tiếp sau. Không tự tuning,budget increase hoặc kết luận root cause từ một trace.

## Kiểm chứng lượt chỉ lập kế hoạch

Đã đọc Core First,AGENTS,report và source `_run_stage`,runtime/machine/campaign identity,ownership/headroom/Linux supervisor; đọc pinned local OR-Tools Python/pyi API,không import/khởi tạo solver. Đọc riêngMemTotal thấy drift4KiB; chưa chạy full execution gate hoặc kiểm current installed runtime readiness. Không chạy prepare/build/model validation/solver/search/profiling,không tạo driver/tests/data trace trong lượt này.

Self-review: hai task tách no-search preparation khỏi separately authorized execution; giữ budget/guards,định nghĩa logging changes,strict identity và ownership/output. Lệnh checks thực chạy sẽ ghi bổ sung sau khi hoàn tất tài liệu. Không có số đo/benchmark mới hoặc claim gatePASS/Windows support.

Kiểm tra tài liệu thực chạy: `uv sync --locked --extra solver` PASS/lock không đổi; `uv run ruff check .` PASS; `uv run ruff format --check src tests` PASS44files; `uv run mypy` PASS27source files; link/scope/plan self-review và `git diff --check` PASS. Không chạy pytest vì suite có solve,không chạy model build/driver/preflight/runtime gate hoặc native logging smoke. Các đoạn API lấy từ pinned local source/pyi,không thay thế kiểm chứng live trace; các task vẫn unchecked.

## Ghi nhận thực hiện Task1

Task1 đã triển khai prepare/instrumentation và34fake-only tests; guarded no-search regression121PASS,ruff/format/mypyPASS. Installed-wheel prepare tạo candidate `802f1f06ab5565d5b09c994fe1cb8c7044c8469096a2e130ce1be53ab9d77006`,statusPREPARED_NOT_AUTHORIZED;legacy gateBLOCKED_MACHINE_DRIFT chỉ fieldMemTotal−4KiB. Không authorization/search/Task2. [Báo cáo Task1 và candidate](../../tight10-trace-preparation-report.md). Các câu “chỉ lập kế hoạch” phía trên mô tả lượt viết kế hoạch trước đó;không thay quyền chạy Task2.

Fresh reviewTask1 có1P2log close/read error; đã sửa bằng2regressionsRED→GREEN,guarded121testsPASS. Candidatev1 giữ lịch sử nhưng stale driver; finalcandidatev2 ở `tight10-trace-prepare-v2/` giữ PREPARED_NOT_AUTHORIZED,không authorization/Task2.

## Ghi nhận Task2 — một trace đã được user duyệt

User duyệt riêng candidatev2 hash802f1f06ab5565d5b09c994fe1cb8c7044c8469096a2e130ce1be53ab9d77006,run-ID/root vàMemTotal−4KiB. Đã chạy đúng1native feasibility attempt,khôngretry:search marker0.15s,rawOPTIMAL ở55.924939301s,260hard-valid assignments,score(12,77,4),không qualityproof. HarnessCOMPLETE/measurementOK,ownerIDLE,17artifact hashes và107protected hashes khớp. Legacy gate vẫnMACHINE_DRIFT. [Báo cáo Task2/giới hạn/đề xuất](../../tight10-search-trace-report.md). Các câu Task2chưađượcphépchạy ở phần lịch sử ghi nhận Task1 không thay approval riêng của lượt này.
