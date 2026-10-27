# TIGHT10 — Logging On/Off Matched Pair Implementation Plan

> **For agentic workers:** Dùng `superpowers:executing-plans` khi được yêu cầu triển khai. Lượt hiện tại **chỉ lập kế hoạch**, không sửa tooling/Core hoặc chạy prepare/build/solver. Task1 tương lai chỉ implement/test/prepare không search; Task2 cần approval riêng cho đúng hai run trong candidate mới. Không tự chuyển từ Task1 sang Task2.

**Goal:** Thu một cặp feasibility runs để mô tả chênh lệch khi bật/tắt logging trên cùng bài, cùng solver settings và cùng môi trường; chưa nhằm chứng minh causal overhead hay sửa UNKNOWN.

**Architecture:** Mở rộng driver single-target hiện có bằng hai logging profiles cố định và pair envelope riêng; common identity/hash chỉ có một bản cho cả cặp. Parent giữ một repository-wide lease, chạy lần lượt hai fresh child processes với cùng installed Core và `_run_stage`; mọi model/budget/guards giữ nguyên. Không tạo benchmark matrix hoặc chép solver/compiler vào tooling.

**Tech Stack:** Python3.12.3, OR-Tools9.15.6755, Pydantic2.14.1 và standard library hiện có; không dependency mới.

**Spec:** [Core First, mục4–6/9](../../VNEDU_TKB_CORE_FIRST_CODEX.md), [trace protocol](2026-10-27-tight10-search-trace.md), [trace đã đo và giới hạn](../../tight10-search-trace-report.md), [witness/model checks](../../tight10-static-diagnostic-report.md).

## Global Constraints

- Nhánh `feature/phase2a-task5-linux-summary`, baseline lập kế hoạch `5d17874`. Lượt này chỉ docs; không solver/search/profiling/model build, không tạo pair candidate/authorization hoặc sửa Core.
- Target duy nhất `c10-tight-s101`, input1.1/policy0.1 và cùng witness synthetic. Không API, dữ liệu thật,2B/2C, repair, hints, presolve toggle, variable reorder hoặc quality optimization tiers.
- Mỗi run: native budget60s, workers1, seed42, gap tolerances0; watchdog150s và observed RSS target1GiB. Guards10,000slots/10,000occurrences/100,000placements/1,000,000occupancy terms. Headroom≥3GiB, disk free≥256MiB được kiểm mới trước mỗi child. RSS target không phải OS hard memory cap.
- **Tối đa hai native solve calls**, mỗi mode một call; không warmup, pilot, repeats, automatic retry/resume hoặc thay budget sau khi thấy kết quả. Đây là hai budget60s riêng, không nâng budget của một solve thành120s.
- Source Core, runner/generator, dependencies và installed wheel không đổi. Chỉ benchmark driver/tests được sửa khi Task1 được yêu cầu; không sửa site-packages hoặc artifacts cũ.
- Candidatev2/single-trace approval đã dùng cho một run; không được dùng làm một nửa cặp mới hoặc cấp quyền thêm run. Legacy exact gate vẫn giữ nguyên, Windows BLOCKED.

## Vì sao cần candidate mới

Trace trước đã có nghiệm ở55.924939301s, score(12,77,4), trong khi3runs lịch sử UNKNOWN ở60s. Chỉ một trace bật logging, khác thời điểm/approved machine snapshot và không có counters cũ nên chưa thể quy chênh lệch cho logging hoặc throughput. Không dùng số đo trước làm số liệuON của cặp này.

Hai run mới phải chia sẻ:

| Trường | Frozen identity |
|---|---|
| Fingerprint | `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee` |
| Input SHA256 | `7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735` |
| Witness SHA256 | `f9b5274529c9d1bd4d4c301b2626336bd0128b38b57901b90627ca4be1121a57` |
| Compiled feasibility proto SHA256 | `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083` |
| Core wheel SHA256 | `1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9` |
| uv.lock SHA256 | `e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084` |

Installed interpreter giữ `/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1/venv-solver/bin/python` với `-I`; repo tooling import từ path đã freeze, Core phải từ installed site-packages khớp wheel. Driver mới có source hash mới chung cho cả cặp; model hash phải khớp cả trước mỗi solve.

## Treatment và thứ tự đã chốt trước kết quả

**Thứ tự cố định: OFF → ON**, mỗi run một fresh Python process, trên cùng machine snapshot. Freeze thứ tự này trong candidate trước approval; không đổi thứ tự sau UNKNOWN hoặc chọn mode thuận lợi chạy trước.

| Profile | log_search_progress | log_callback | log_to_stdout | log_to_response |
|---|---|---|---|---|
| logging_off | false | None | false | false |
| logging_on | true | raw UTF8 chunks, flush mỗi write như trace trước | false | false |

Treatment là **gói native progress logging + Python callback/file flush**, không tách được overhead của từng thành phần từ cặp này. Các solver parameters khác, model và wrapper measurement/validation giống nhau; ghi full applied parameter snapshots để kiểm chỉ log_search_progress khác và callback state đúng profile. Không cài solution/bound callback ở cả hai mode.

Sau khi OFF được reap và artifacts persisted, ghi post-context rồi pre-context/gates mới cho ON và chạy tiếp nếu đủ điều kiện. Không script cooldown hoặc warmup; ghi actual inter-run gap. Fresh process không có nghĩa cold OS cache; OFF→ON có thể chịu thứ tự/cache/nhiệt máy khác nhau. **n=1/mode nên chỉ exploratory**, không median/P95/SLA hoặc kết luận causal logging làm nhanh/chậm hơn.

## Snapshot và approval

Task1 tạo root mới `benchmarks/artifacts/phase2a/tight10-logging-pair-<id>/` với `pair-candidate.json` mở exclusive. Root này nằm ngoài mọi campaign/trace/preflight/input/evidence cũ. Pair envelope strict `schema_version="1.0"`, kind=`tight10_logging_pair`; không mở rộng hoặc sửa candidatev2 cũ.

Candidate phải freeze pair-ID (≤60chars), root tuyệt đối, run-IDs `<pair-id>-off`/`<pair-id>-on`, order `[logging_off,logging_on]` và paths cố định `runs/01-off`/`runs/02-on`; common identity, profiles bảng trên, options/limits, workload/power policy, source/driver hashes, installed runtime và full legacy drift comparison. Reject unknown fields/version, modes, extra members, path escape, changed budgets hoặc profile khác bảng.

Tái dùng `capture_identity()` và model/wheel checks. Common descriptor là exact identity **trừ field logging**; validate bằng existing `Identity` với canonical loggingON rồi tách field đó, không nới validator cũ để cho arbitrary logging. Profile settings được freeze riêng và gắn vào effective child identity. Cả hai current common snapshots phải exact-match approved common descriptor; khác biệt được phép giữa hai profiles chỉ là bảng treatment.

Prepare chặn constructor thật, không lease/search; status `PREPARED_NOT_AUTHORIZED` hoặcBLOCKED có reason. Không tạo authorization. MemTotal hiện tại phải capture trong installed interpreter, kèm so với legacy; không mặc định sẽ vẫn−4KiB hoặc tái dùng acceptance trước.

Approval mới cần **pair-candidate SHA256, pair-ID, exact root, hai run-IDs/thứ tự và scope một call/mode**; action riêng `RUN_ONE_LOGGING_PAIR`. Single-run authorization `RUN_ONE_FEASIBILITY_TRACE` không hợp lệ. Người dùng phải chấp thuận snapshot/drift được công bố; được duyệt baseline mới không biến legacy gate thànhPASS.

Parent/child recheck common runtime/machine/source/input/model/driver và effective profile ngay trước từng solve. Bất kỳ drift mới hoặc thay source sau freeze → BLOCKED; không sửa candidate hoặc tự rebaseline. Manifest/START/receipt bind pair hash+mode+index+parentPID và run-ID; direct child không được bypass lease/authorization. Approval không được tái dùng với root khác hoặc run đã START.

## Workload/power: ghi gì và kiểm gì

Dùng lại `_operational_context()` trước/sau **mỗi** run, cùng UTC timestamp, load averages1/5/15min, load_status, raw `/sys/class/power_supply` fields(type/online/status/capacity). Giữ raw `workload_control=UNCONTROLLED` và `competing_workload=UNKNOWN` nếu chưa có bằng chứng khác. Nếu user khai báo đã dừng known heavy jobs, lưu riêng declaration+provenance, không đổi observation thành VERIFIED_IDLE.

Điều kiện power đề xuất để freeze trong candidate của máy laptop hiện tại: **AC online được quan sát trước mỗi run**; không xác nhận được hoặc observed battery-only thì BLOCKED trước run tương ứng, giữ pending member. Sau run nếu power khác pre-state hoặcUNKNOWN, đánh dấu comparabilityLIMITED; không xóa result hoặc thử lại. Hai snapshots không chứng minh AC/governor/temperature ổn định suốt native solve.

Load averages là observations, không đặt ngưỡng load tùy tiện để chọn mẫu đẹp. Ghi workload/power và kernel CPU/RSS của cả hai run; không tự kill ứng dụng, đổi affinity/governor/power mode/thread environment, tắt turbo, drop cache hoặc reboot để ép gate/so sánh. Không thu profiler hoặc danh sách command lines của các process.

Headroom/disk/runtime/lease và AC precondition được kiểm lại trong shared lease trước mỗi spawn. Điều này giảm khác biệt đã quan sát nhưng không loại hết competing workload, thermal/frequency hoặc thứ tự effects; report luôn giữ giới hạn đó.

## Kết quả OFF và xử lý lỗi

Driver hiện dùng `bool(log_text)` để nhận trace_complete; không được dùng điều kiện này làm execution success gate cho OFF.

- Cả hai profiles đều có `stage_complete`, native raw status, response/response-stats, counters, parameter snapshot, kernel process metrics và independent result validation.
- OFF: không callback/trace.log; ghi `trace_capture_status=DISABLED`,`trace_complete=null`, missing-log reason `LOGGING_DISABLED`. Stage thành công vẫn phải decode/validate/recompute score; không bị gắn incomplete vì thiếu log có chủ đích.
- ON: `trace_capture_status=COMPLETE|FAILED`; close/read/write errors giữ available response/parameters nhưng không publish schedule như valid nếu capture contract thất bại. Giữ regression fix của tracev2.
- OFF thiếu phase markers/elapsed_to_search_marker lànull+LOGGING_DISABLED. Positive branches vẫn chứng minh có branching;0branches một mình không chứng minh presolve-only. TTF end-to-end null/NOT_INSTRUMENTED ở cả hai.
- Native UNKNOWN trong60s là outcome hợp lệ của phép đo, không là correctnessFAIL/INFEASIBLE và không bị bỏ mẫu. Nếu response/harness đầy đủ và gate/power vẫn đủ thì tiếp tục member kế tiếp theo order đã freeze.
- Crash/watchdog/resource stop, capture/measurement/reap failure, independent mismatch hoặc witnessed-model contradictionINFEASIBLE/MODEL_INVALID→dừng cặp, giữ evidence và member sauNOT_STARTED. Không tự retry/resume, tăngbudget hoặc đảo thứ tự; report PARTIAL/BLOCKED thay vì bịa sample thứ hai.

Parent giữ một shared repository owner lease cho cả cặp, tái dùng Linux supervisor và signal/reap semantics; không chạy hai children đồng thời. Reap không xác nhận→NEEDS_REVIEW, không nhảIDLE; success/legitimateUNKNOWN cuối cùng chỉ nhảIDLE khi tất cả spawned children đã reap và receipts persisted.

## Artifact và cách so sánh

Root mới gồm `pair-candidate.json`,`pair-authorization.json`, pair state/order và final manifest; mỗi run có START/terminal receipt và subdir attempt mới. Giữ mọi file theo [trace protocol](2026-10-27-tight10-search-trace.md), thêm pre/post workload-power context và mode. OFF thiếu trace.log có reason trong inventory; không tạo empty fake log để giống ON. Hai effective parameter/callback snapshots và model hashes phải được đối chiếu trước báo cáo.

Report hai rows bắt buộc:status/harness, stage/native wall, CPU, deterministic_time, branches/conflicts/propagations/restarts/LP iterations, peak RSS, validity/score, pre/post load/power và inter-run gap. Metrics không thu được=null+reason; UNKNOWN giữ no-schedule/score null. Lịch có nghiệm phải hard-valid và per-rule/tier scores khớp model values; feasibilityOPTIMAL không quality proof.

Nếu cả hai có nghiệm, có thể báo chênh lệch native wall/CPU và counters như số mô tả của cặp. Nếu native work counters/deterministic_time khác, wall delta không đo riêng logging overhead. Nếu một runUNKNOWN, thời gian đến nghiệm của nó bị giới hạn quan sát; không lấy60s làm latency nghiệm hoặc tính speed-up %. Không cộng/average các tier scores. Dù counters giống nhau, n=1 và order/power/workload limits vẫn không đủ chứng minh causal overhead hoặc đề nghị đổi default.

## Review Focus

- OFF không log phải vẫn kiểm response/schedule; không biến deliberate absence thành failure hoặc0metrics.
- Pair approval khác single-run approval; nguồn/schema/mode/order/model/common identity drift phải chặn trước native call.
- UNKNOWN vẫn là mẫu; harness/correctness failure dừng cặp và giữ pending, không retry/drop run.
- Power UNKNOWN hoặc thay đổi phải giữ fact/limitations; không coi load averages là proof máyidle hoặc can thiệp hệ thống.
- Một native call/mode, hợp lệ mọi schedule/score, không qualityproof hoặc causal/SLA claim từ hai observations.

## Task 1 — Tooling và prepare không search, chưa thực hiện

**Files tương lai:** Modify `benchmarks/trace_tight10.py`, `benchmarks/tests/test_trace_tight10.py`; không sửa Core/frozen runner/generator. Create report `docs/tight10-logging-pair-preparation-report.md` và ignored pair candidate/evidence mới. Giữ existing single-mode regression suite và không rewrite artifacts cũ.

**Interfaces:** thêm keyword `logging_mode: Literal["logging_off","logging_on"]="logging_on"` vào `trace_feasibility(...)`; existing single-mode caller mặc địnhON. Thêm `prepare_pair(root: Path,pair_id: str) -> dict[str,JsonValue]`, strict pair envelope/approval models và pair-only execution dispatch; common identity/profile guard tái dùng capture/hash/compare helpers. Không generalize datasets/modes/repeat counts.

- [ ] Viết testsRED hoàn toàn fake/native constructor bị chặn: `test_pair_exact_members_and_off_on_order`; `test_common_identity_and_model_equal_profile_difference_only`; `test_off_has_no_callback_or_log_but_validates_schedule`; `test_off_unknown_is_complete_measurement_not_infeasible`; `test_on_close_read_error_preserves_response`; `test_single_authorization_cannot_authorize_pair`; `test_pair_scope_and_started_member_cannot_be_reused`; `test_common_or_profile_drift_blocks`; `test_ac_unknown_blocks_next_member_without_retry`; `test_unknown_continues_but_crash_or_mismatch_stops_pair`; `test_power_change_and_missing_metrics_keep_limitations`; `test_prepare_pair_never_constructs_native_solver_or_approval`.
- [ ] Chạy `uv run --extra solver pytest benchmarks/tests/test_trace_tight10.py -q` quan sátRED, chỉ fakes. Implement minimal profile/result-contract và pair orchestration như trên; reuse `_run_stage`, owner/headroom/context/supervisor. Không chép algorithm hoặc tạo control-matrix framework.
- [ ] GREEN dedicated suite với real constructor chặn;`uv sync --locked --extra solver`, ruff check, format src/tests+benchmarks, mypy. Full suite có native solves ngoài scope chuẩn bị thì không chạy. Freeze code sau kiểm chứng; source đổi sau candidate phải candidate mới, không edit metadata cũ.
- [ ] Chỉ chạy pair-prepare bằng installed interpreter với constructor guard để tạo common snapshot/model/identity, pair root mới và candidatehash; ghi legacy drift cùng operational policy. Dừng ở PREPARED_NOT_AUTHORIZED/BLOCKED, không acquire run lease, tạo approval hoặc chạy bất kỳ member nào.

## Task 2 — Một cặp được duyệt riêng, chưa được phép thực hiện

**Files tương lai:** pair tooling Task1, fresh run artifacts và `docs/tight10-logging-pair-report.md`; không Core changes.

- [ ] Chỉ sau user approval exact pair hash/root/run-IDs/order/snapshot, ghi authorization và kiểm gate/lease/headroom/disk/power trướcOFF. Chạy một fresh child budget60s; persist outcome/receipt/context.
- [ ] Nếu terminal outcome hợp lệ và fresh gates/AC đủ, chạyON một lần rồi persist, reap, release lease theo protocol. Nếu có blocker/failure theo policy, giữ statePARTIAL/BLOCKED và pending, no automatic retry hoặc sửa artifacts.
- [ ] Kiểm lại hashes/identity/parameters, validate schedules/score nếu có; report cả hai member kể cảUNKNOWN/NOT_STARTED và giới hạn n=1. Chỉ đề xuất một bước tiếp theo từ evidence; không tự tuning, đổi defaults hoặc chạy thêm cặp.

## Kiểm chứng lượt chỉ lập kế hoạch

Đã đọc AGENTS/Core First, trace report và connected driver/context helpers. Xác nhận từ source rằng callback hiện chỉON vàbool(log_text) đang chi phối success; đây là yêu cầu sửa của Task1 tương lai, không phải kết quả chạyOFF. Chưa capture runtime/machine/power hiện tại, chưa tạo pair candidate, sửa tooling hoặc chạy solver/model build/profiling. Existing single trace và3UNKNOWN giữ lịch sử; không có số đo mới.

Self-review: hai profiles chỉ khác logging bundle, order cố định vàmatched common identity; missing-log OFF không chặn schedule validation; approval mới/runtimesnapshot/workload-power fields được chỉ rõ; failure/UNKNOWN phân biệt; mọi tasks vẫn unchecked. Các kiểm tra thực chạy: `uv sync --locked --extra solver` PASS; `uv run ruff check .` PASS; `uv run ruff format --check src tests benchmarks` PASS (54 files); `uv run mypy` PASS (27 source files); `git diff --check` PASS. Không chạy pytest vì lượt này chỉ thay tài liệu và full suite có native solves ngoài scope. Lệnh tự kiểm tài liệu ban đầu dùng `python` không có trong PATH; đã chạy lại bằng `python3` thành công.
