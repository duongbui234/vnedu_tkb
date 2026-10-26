# Phase 2A Task 4 Linux — Pilot/Campaign Implementation and Execution Plan

> **For agentic workers:** Khi được duyệt phần triển khai, dùng **superpowers:executing-plans (Native)**. §6 đã được duyệt triển khai tooling/tests trong lượt tiếp theo; §7 vẫn là execution tương lai. **Snapshot lượt lập kế hoạch: chỉ khảo sát/viết plan. Lượt triển khai tiếp theo chỉ làm§6, không chạy warmup/pilot/campaign; xem§9.**

**Goal:** Chuẩn bị điều kiện chạy pilot và primary campaign Linux đúng ngân sách đã duyệt, đủ evidence và không ghi đè/đếm lại outcomes.

**Architecture:** Frozen bundle36 + installed wheel → preflight độc lập → immutable campaign plan → warmup/pilot gate →108 runs tuần tự qua `run_cli_once` → raw records và per-case verdict. Không thêm solver logic; phép tổng hợp thống kê/cross-OS thuộc Task5.

**Tech Stack:** Python3.12.3, standard library/argparse/fcntl, Pydantic/Core hiện có; OR-Tools9.15.6755 chỉ trong measured solve child. Không dependency hoặc distribution entrypoint mới.

**Spec:** [Kế hoạch vận hành đã duyệt](2026-10-26-phase-2a-operational-validation.md), [phạm vi Task3 Linux](2026-10-26-phase-2a-task3-linux-scope.md), [báo cáo Task2/3](../../phase-2a-operational-report.md), [Core First](../../VNEDU_TKB_CORE_FIRST_CODEX.md).

## Global Constraints

- Linux-only; Windows **BLOCKED**. Không dùng Linux/WSL/mocks để nghiệm thu Windows. Task2/3 hai OS còn PARTIAL không ngăn phát triển Linux tooling, nhưng không cho claim nghiệm thu toàn campaign hai OS.
- Chưa chạy benchmark trong lượt này. Code orchestration, thực hiện pilot và thực hiện primary là các phạm vi phải được người dùng cho phép; duyệt plan không tự khởi chạy chúng.
- Giữ nguyên Core, generator, guards, wheel/lock/bundle; không API/UI/SQLite, repair hoặc Phase2B/2C. Không đổi dữ liệu/profile/budget sau khi thấy kết quả.
- Native sequence: một measured Python child mỗi lần, một campaign active trong repo. Không workers4/seed sweep, không auto-retry, không drop failure để báo đẹp. Không tự tắt ứng dụng hoặc đổi cấu hình/power/caches máy.
- Không commit/merge/push tự động; giữ12 tài liệu/context chưa commit và toàn bộ raw evidence hiện có.
- Parent supervisor là standalone installed Python, không load solver-native trước solve. Preflight verify36witnesses chạy trong process riêng để không giữ domains/làm parent nặng. Rusage là process lifetime, không tự trừ parent baseline hoặc thay kernel peak bằng sampled RSS.

## Review Focus

1. Headroom host đủ nhưng cgroup ancestor thiếu/không đọc được: fail closed trước spawn, không gọi là solver OOM — Task2 tests.
2. Pilot lẫn primary hoặc resume chạy lại failure: phase/run IDs và terminal-record checks phải giữ denominator108 — Task1/4 tests.
3. Parent chết để lại active marker/partial root: không auto-kill PID cũ hoặc overwrite rồi chạy tiếp — Task2/4 tests.
4. Source/wheel/input hoặc order đổi khi resume: chặn toàn campaign, không gộp số đo khác identity — Task4 tests.
5. Harness COMPLETE nhưng solver UNKNOWN/INFEASIBLE hoặc lịch hard-valid có score sai mục tiêu: dùng per-case verdict, không coi mọi COMPLETE là pilot PASS — Task3 tests.

## 1. Rà soát điều kiện bắt đầu — snapshot thực tế

Snapshot source `main=33b8023c1125638f96faa18ba735b19c71cbcc97`; thời điểm kiểm tra `2026-10-26T17:06:33Z` = `2026-10-27 00:06:33 ICT`. Các giá trị RAM/load/disk là snapshot, không phải số đo benchmark hoặc trạng thái bảo đảm cho lần chạy sau.

| Hạng mục | Bằng chứng/trạng thái |
|---|---|
| Task1–3 Linux | Đã merge/push; historical full352tests và installed-wheel tiny smoke PASS |
| Preflight Task2 | Kiểm lại52 file hashes, nguyên vẹn |
| Task3 evidence | Kiểm lại8 hashes, source/test SHA khớp code hiện tại |
| Bundle | Kiểm root manifest +36 dataset manifests +mọi input/witness/provenance SHA, đều khớp |
| Runtime installed hiện tại | Gọi read-only `_runtime_identity` bằng venv solver, xác nhận package/site-packages, versions và27source files khớp wheel; không gọi solve |
| Core tree | `1efd459b2514f448dcf4ac297989de09eb76a3a1`, không đổi |
| Wheel SHA | `1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9` |
| Lock SHA | `e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084` |
| Bundle root SHA | `a278a02dd9e10fedc7c5fcf44ef81d038d7712eba929d881a0f6193fc97cc93d` |
| RAM khả dụng snapshot |27,235,225,600 bytes; đủ headroom3/4/6GiB **tại thời điểm đọc** |
| Cgroup nhìn thấy | cgroup2 mount root `/`; đọc6 scopes/ancestors tới host root, các memory.max đều `max`; không thấy finite cap trong hierarchy đã đọc |
| Disk snapshot |121,683,992,576 bytes free; không có cam kết không đầy khi chạy sau |
| Load snapshot |1.604/1.508/1.281; power/workload không kiểm soát, không coi là idle chuẩn |
| Campaign CLI/plan journal/headroom gate | **CHƯA CÓ**: script hiện chỉ cung cấp one-run APIs |
| Windows, quy mô trường, latency/RAM/quality | BLOCKED hoặc UNKNOWN/NOT_RUN |

**VERIFIED:** frozen artifacts và Linux one-run prerequisites còn nguyên. **INFERRED:** sẵn sàng triển khai lớp orchestration/test. **Chưa đủ điều kiện bắt đầu measured pilot/campaign** vì còn thiếu các phần bên dưới và chưa có authorization chạy. Read-only evidence: `.superpowers/task4-readiness-2026-10-27.json` trong worktree `.worktrees/phase2a-generator`, branch `feature/phase2a-task4-linux-plan`.

## 2. Ngân sách freeze — không thay SLA

| Classes | SolveOptions.time_limit_seconds | RunLimits.watchdog_seconds | Max resident bytes | Effective available tối thiểu trước run |
|---|---:|---:|---:|---:|
|10|60.0|150.0|1,073,741,824 (1GiB)|3,221,225,472 (3GiB)|
|20|120.0|210.0|2,147,483,648 (2GiB)|4,294,967,296 (4GiB)|
|40|180.0|270.0|4,294,967,296 (4GiB)|6,442,450,944 (6GiB)|

Tất cả primary/pilot: workers1, solver seed42; default guards slots10000, occurrences10000, placements100000, occupancy terms1000000. Generator seeds101/102/103, order seed2026. Không cấp budget riêng60s cho từng tier: `solver/objectives.py::run_quality` chia cùng budget qua feasibility và các tiers bằng remaining time; preprocessing/startup/validation do watchdog bao phủ.

RAM target là ngưỡng quan sát, không hard cap. Sampling50ms có thể bỏ lỡ spike; kernel peak cuối vượt target vẫn NOT_MET dù chưa có RESOURCE_STOP. Watchdog dừng bằng TERM +grace1s/KILL; launch-to-reap có cleanup nên không phải hard upper bound đúng150/210/270s. TTF vẫn null/NOT_INSTRUMENTED; CPU có thể lớn hơn wall.

108 configured solver budgets có tổng trần cấu hình12,960s=3.6h; watchdog ceilings cộng22,680s=6.3h. **Không phải dự báo duration hoặc deadline tổng**;27 UNSAT prechecks không dùng CP-SAT khi hoạt động đúng, parent verification/setup/cleanup không nằm hết trong phép cộng. Không tự tăng budgets hoặc bỏ40lớp nếu run khó.

## 3. Phases, order và sample membership

**Đề xuất chốt pilot tách khỏi mẫu primary**, thay vì dùng reserved primary ID; tránh đổi thứ tự shuffle hoặc đếm pilot hai lần. Đây là lựa chọn được phép bởi plan gốc, cần duyệt cùng tài liệu này.

| Phase | Số lần/inputs | Settings và điều kiện tiếp tục |
|---|---|---|
| VALIDATE/PREPARE | Không solve | Recheck identities, verify36 final witnesses/proofs bằng installed Core trong process riêng; freeze plan/order trước measured run |
| WARMUP |1 tiny input3occurrences từ Task2 smoke |10s/workers1/seed42, watchdog15s/cap256MiB theo tiny smoke Task3; chỉ setup, loại khỏi mẫu và mọi thống kê performance; metadata timing vốn có của Core vẫn giữ raw, không báo thành số đo pilot |
| PILOT |1 BASE10, generator seed101 |60s/150s/1GiB, phase/run ID riêng; cần hard/score pass, vector0 và đủ metrics/headroom |
| PRIMARY |108 cases |36 datasets ×3 repeats; mỗi child fresh, tuần tự; pilot/warmup không nằm trong108 |

Số lần solve quy mô trường tối đa dự kiến: **1 pilot +108 primary**; không kể1tiny warmup. Primary gồm81 known-feasible và27 capacity-infeasible cases. Ba repeats không đủ cho P95/SLA. Không so tốc độ FET/STKB hoặc suy Windows từ kết quả Linux.

Order được freeze bằng algorithm `sequential-rng-2026-v1`: bắt đầu từ36dataset IDs đã sort; một `random.Random(2026)`, lần lượt shuffle bản copy36IDs cho repeat1,2,3; concatenate và lưu108rows cùng SHA. Không regenerate order khi resume. Một run ID nằm trong namespace campaign/phase/OS/machine, chứa dataset_id + **full input SHA** +workers1/seed42/repeat; pilot repeat0/phasePILOT, primary repeat1..3, không collision.

Giữ cùng assignments/input để cross-validate giữa OS sau khi có Windows; hiện chưa thực hiện. Không đòi cùng seed phải trả cùng lịch/runtime/proof status giữa runs.

## 4. Gates và chính sách dừng/tiếp tục

Trước **mỗi** measured run: recheck source/wheel/lock/input hashes; installed package prefix/versions; input confirmed profile; effective headroom; output parent writable/free bytes; ghi timestamp/load/power/workload và whitelist thread env variables (không dump toàn env/credentials). Không có fake OS flag. Nếu Python/Core/source khác, dừng chứ không đổi pin để qua gate.

Headroom = min(host MemAvailable, mọi finite ancestor memory.max−memory.current đọc được), so target+2GiB. Với cgroup2 phải resolve mount root/path thực, xét mọi visible ancestor; `max` là unbounded, root host không có memory.max là trường hợp đã biết. Không suy `không thấy file` là `unlimited` cho một scope không đọc/resolve được. Cgroup1/namespace không xác minh được → ENVIRONMENT_BLOCKED cho measured run đến khi có probe được kiểm chứng; không đổi cấu hình máy. Đây là admission estimate, không reservation hoặc bảo đảm không OOM. Ngữ nghĩa hierarchy/current/max đối chiếu [Linux kernel cgroup2 memory interfaces](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory-interface-files).

Campaign giữ advisory lock trong repo artifact root; launcher từ chối campaign thứ hai cùng repo. Đây không phải khóa mọi process/clone trên máy; workload khác vẫn cần ghi nhận. Lock được OS giải phóng nếu parent chết nhưng active marker còn RUNNING/NEEDS_REVIEW thì không tự coi máy đã an toàn. Không tự kill PID cũ do có thể đã tái sử dụng.

### Per-case checks (không phải aggregator Task5)

- Harness COMPLETE chỉ nói execution/output nhất quán; phải kiểm ground truth của dataset. Known-feasible trả INFEASIBLE → correctness FAIL, dừng campaign. Core INPUT_INVALID/UNSUPPORTED_FEATURE/MODEL_INVALID trên input đã preflight hợp lệ là technical/correctness gate FAIL, dừng để điều tra, không đưa vào latency như thành công. Expected UNSAT phải INFEASIBLE, không assignments/score, solver_executed=false; không được dùng thời gian precheck để quảng cáo tốc độ feasible search.
- Mọi lịch phải hard-valid/score/proof consistency qua Task3. Z claim LEXICOGRAPHIC_OPTIMAL phải vector0; Z FEASIBLE score>0 là chất lượng NOT_MET, không là hard failure.
- TIGHT so vector lexicographic với witness cùng fingerprint: BETTER/EQUAL/WORSE, không tổng scalar. FEASIBLE WORSE vẫn là incumbent hợp lệ, phải ghi thật; chưa có gate bắt buộc thắng witness. LEXICOGRAPHIC_OPTIMAL WORSE witness là correctness FAIL; chỉ so prefix được chứng minh với witness khi các tiers cao hơn bằng nhau. Khi P1=0 và xét P2, score dưới declared lower bound là correctness FAIL; không ép score phải bằng bound hoặc gọi bound là attainable optimum.
- Peak kernel >target, watchdog/resource stop hoặc known-feasible UNKNOWN → performance NOT_MET, không đổi thành vô nghiệm. Missing/broken measurements → NOT_ASSESSED/BLOCKED, không0 giả. Không có lịch thì quality NO_SCHEDULE; UNSAT quality/performance NOT_APPLICABLE.

Pilot chỉ PASS nếu prerequisites +harness COMPLETE +hard/score pass +vector0 +kernel peak≤1GiB +launch elapsed≤150s +không missing measurement. Pilot UNKNOWN/timeout/score>0/vượt RAM → NOT_MET và **không tự mở primary**; giữ outcome, báo nguyên nhân và để người dùng quyết định. Đây là pilot gate, không tự tăng budget hoặc sửa profile.

Primary có performance NOT_MET thông thường (UNKNOWN/RESOURCE_STOP hoặc Z chưa đạt0) thì giữ row và tiếp tục các cases còn lại nếu owner/measurement còn an toàn. Correctness FAIL, identity drift, CRASH/OUTPUT_INVALID, probe lỗi, CANCELLED hoặc REAP_UNCONFIRMED → dừng, giữ tất cả raw và pending cases. Không chạy tiếp khi child chưa xác nhận kết thúc. Không retry run hỏng trong cùng ID.

Nếu người dùng đã cho phép cả pilot và primary, pilot PASS có thể tự tiếp tục primary theo plan, không hỏi lại từng run. Lượt lập kế hoạch này **không cho phép chạy bất kỳ phase đo nào**.

## 5. Data và resume contract đề xuất

Không đổi RunRecord1.0/ScheduleResult. Thêm các model tooling strict/version1.0 trong `benchmarks/run_benchmarks.py`: `PlannedCase`, `CampaignPlan`, `HeadroomCheck`, `CaseVerdict`, `CampaignState`. Mỗi row liên kết Task3 run.json bằng SHA; giữ raw result/score/stages trong run dir, không ghi đè chúng bằng verdict.

Campaign plan chứa phase membership/order/run IDs, dataset/input/witness SHA+fingerprint, ground truth/baseline/lower-bound references, budgets/guards/seeds, actual machine/OS/Python/package versions, Core/wheel/lock/generator/supervisor/controller source hashes, Git HEAD và dirty flags thực. Không dùng HEAD thay code SHA nếu code chưa commit. Freeze plan trước chạy; source thay đổi cần campaign mới hoặc chặn, không sửa manifest cũ để hợp kết quả.

`CaseVerdict`: correctness=PASS/FAIL/NOT_ASSESSED; performance=MET/NOT_MET/NOT_ASSESSED/NOT_APPLICABLE; quality=BETTER/EQUAL/WORSE/NO_SCHEDULE/NOT_APPLICABLE, reasons. UNKNOWN không bị gọi correctness FAIL chỉ vì chưa có lịch. Task5 mới tổng hợp medians/ratios; Task4 chỉ lưu per-case evidence và progress counts.

Output root mới, canonical plan.json +environment.json +append-only journal +campaign-state.json; từng phase có directory riêng. `run.json` là Task3 record, `case-verdict.json` là wrapper; update state dùng temp+atomic replace, append journal trước/sau run, không sửa terminal artifacts.

Resume chỉ khi người dùng gọi rõ `--resume`, plan/settings/machine/source hashes khớp. Terminal records **bao gồm cả failure/NOT_MET** được giữ và skip, không rerun để thay số. Headroom fail trước spawn lưu gate event, chưa tạo run dir, case vẫn NOT_STARTED_GATE_BLOCKED để lần resume recheck. Run dir có START nhưng thiếu/malformed terminal record hoặc owner/cleanup chưa rõ → NEEDS_REVIEW, không tự chạy lại/overwrite. Failed attempt cần thử lại phải có campaign/attempt identity mới, giữ linkage; không gộp nó thành repeat thay thế âm thầm.

Giữ108 planned rows dù campaign dừng; ghi attempted/completed/failed/pending rõ. Không lấp missing bằng0 hoặc xóa row. Progress là case count/run ID; không giả % solver. Không hứa tự resume sau reset quota; checkpoints cho phép tiếp tục có kiểm chứng.

## 6. Implementation tasks trước khi được phép đo

Giữ cấu trúc hai scripts đã duyệt, mở rộng `benchmarks/run_benchmarks.py` bằng functions theo trách nhiệm; không refactor supervisor đã kiểm chứng. Tests mới ở `benchmarks/tests/test_campaign_linux.py` để tách matrix/state cases khỏi82 lifecycle tests. Report cập nhật sau có kết quả thật; không đổi packaging/lock/Core. Các API dưới đây đã được triển khai trong lượt tooling tiếp theo; chưa gọi chúng trên campaign thực tế.

### Task 1 — Frozen matrix và phase membership

**Interfaces:** `build_campaign_plan(bundle_dir: Path, campaign_id: str, machine_id: str) -> CampaignPlan`; `PlannedCase` mang phase/repeat/IDs/dataset digest/options/limits. Consumes Task1 bundle; no solve/prepare call.

- [x] Viết tests `test_matrix_counts_budgets_and_ids`, `test_seeded_order_is_frozen`, `test_pilot_is_excluded_from_primary`:108unique primary IDs,81/27 truth split,36cases/size, repeat1..3 mỗi dataset, budgets đúng bảng; pilot repeat0, không primary ID nào trùng.
- [x] RED: `uv run pytest benchmarks/tests/test_campaign_linux.py -q -k 'matrix or order or pilot_is'`; expected missing API.
- [x] Implement strict models/pure matrix/order, plan SHA và explicit phase membership; không construct CP-SAT hoặc call run_cli_once.
- [x] Run lại GREEN; cùng seed/source/bundle cho cùng plan bytes ngoài metadata thời gian được freeze một lần. Các default budgets không configurable qua flag nới âm thầm.

### Task 2 — Runtime/headroom/ownership gates

**Interfaces:** `check_headroom(memory_target_bytes: int) -> HeadroomCheck`; campaign-root owner lock/marker. Reuse Task3 runtime identity checks; preflight witnesses chạy process riêng bằng installed Core, controller không import generator/preprocessing/model_builder.

- [x] Tests `test_headroom_uses_tightest_ancestor`, `test_unknown_scope_blocks`, `test_gate_failure_starts_no_child`, `test_second_campaign_cannot_acquire_owner`, `test_stale_active_marker_needs_review`: host10GiB/group3GiB remaining với target2GiB+2GiB → BLOCKED; unknown không thành unlimited; không child/raw run dir khi gate fail.
- [x] RED: `uv run pytest benchmarks/tests/test_campaign_linux.py -q -k 'headroom or scope or gate_failure or owner or stale_active'`.
- [x] Implement validated snapshots/lock/journal; không sửa SIGCHLD/power/caches/system limits. Recheck trước từng measured run, không tái dùng snapshot plan này làm headroom permit.
- [x] GREEN; tests chỉ synthetic filesystem values và bounded lock processes, không allocate RAM/solve bộ trường. Missing controller/permission phải có reason.

### Task 3 — Case verdict và pilot gate

**Interfaces:** `check_case(run_dir: Path, dataset_manifest: Path) -> CaseVerdict`; đọc RunRecord và ScheduleResult hiện có, không tái implement penalty hoặc recertify proof.

- [x] Tests `test_complete_is_not_pilot_pass`, `test_expected_unsat_and_false_infeasible`, `test_zero_target_and_tight_witness`, `test_kernel_peak_over_cap_without_sample_stop`: valid UNKNOWN/COMPLETE không pilot pass; false infeasible FAIL; UNSAT đúng không quality0; TIGHT FEASIBLE worse ghi WORSE; declared optimum worse witness FAIL; sampled không bắt spike nhưng kernel vượt cap vẫn NOT_MET.
- [x] RED theo các test names; implement verdict +machine-readable reasons, gate tự động theo§4, không đổi solver status trong raw RunRecord.
- [x] GREEN với fixture records hợp contract; failure payloads không giả schedule hoặc số đo. Không median/P95/cross-OS aggregator.

### Task 4 — Journal, safe resume và tuần tự orchestration

**Interfaces:** `execute_campaign(plan_path: Path, preflight_dir: Path, *, phase: str, resume: bool=False) -> CampaignState`; gọi `run_cli_once` tuần tự sau gate, không sửa API này. CLI required phase=prepare/warmup/pilot/primary, không default tự đo; entrypoint qua absolute installed Python `-I /abs/benchmarks/run_benchmarks.py`.

- [x] Tests `test_campaign_persists_rows_in_plan_order`, `test_resume_skips_failed_terminal_runs`, `test_partial_run_is_not_overwritten`, `test_changed_identity_blocks_resume`, `test_cancel_or_unconfirmed_reap_stops_next_case`, `test_pilot_not_met_never_starts_primary`.
- [x] RED, rồi implement orchestration/state writes/CLI. Unit tests dùng typed synthetic execution boundary; assertions vào persisted journal/rows/hash/order/denominator, không chỉ mock call count. Không thực hiện108solves trong tests.
- [x] GREEN; explicit primary phải có pilot PASS cùng frozen identity, warmup/setup ready; thông báo run count, không giả solver progress. Output roots mới hoặc resume hợp lệ duy nhất, không tự overwrite/retry.
- [x] Chạy full Core/generator/supervisor/new-campaign unit suite +lint/format/mypy/build và installed tiny integration, một fresh Native final review. Tooling source SHA đã đổi nên tạo evidence validation mới, giữ Task3-v2 frozen; không claim certificate cũ bao phủ code mới.

### CLI contract đã triển khai — chưa chạy phase thực tế

Parent interpreter chính là installed venv Python; không thêm flag giả OS/Python khác. Primary matrix cố định trong plan, chưa optional matrices. Cần `--phase` tường minh, không có default khởi chạy đo. Ví dụ sau khi đã implement/review và được phép execution:

```text
<installed-python> -I <repo>/benchmarks/run_benchmarks.py --phase prepare --bundle <task1-v1> --preflight-dir <preflight-linux-v1> --campaign-id <id> --machine-id <opaque-id> --output <new-root>
<installed-python> -I <repo>/benchmarks/run_benchmarks.py --phase warmup --plan <root>/plan.json --preflight-dir <preflight-linux-v1>
<installed-python> -I <repo>/benchmarks/run_benchmarks.py --phase pilot --plan <root>/plan.json --preflight-dir <preflight-linux-v1>
<installed-python> -I <repo>/benchmarks/run_benchmarks.py --phase primary --plan <root>/plan.json --preflight-dir <preflight-linux-v1>
```

`--resume` chỉ hợp lệ cho execution phase trên sealed plan cùng identity; prepare không overwrite root cũ. Machine ID là opaque label do người chạy chọn, không thay actual OS/CPU/environment evidence. Headroom gate/source gate không bị tắt qua flag. Không auto-run code khi import module.

## 7. Runbook tương lai — chỉ sau authorization chạy

- [ ] PREPARE: kiểm scope authorization; tạo root mới; frozen wheel/Core/bundle versions đúng; verify36 witnesses/proofs riêng process; freeze108case plan/order, environment và source identities. Windows ghi BLOCKED. Chưa có correctness/performance claim của trường lớn.
- [ ] WARMUP: tiny setup theo§3, lưu ngoài mẫu. Core có wall metadata tự nhiên nhưng không thu nó vào performance summary.
- [ ] PILOT: BASE10/seed101/workers1/solver42, đúng60s/150s/1GiB, fresh process; đọc raw +independent verdict. Fail/NOT_MET/BLOCKED → stop và báo, không đổi budgets.
- [ ] PRIMARY khi pilot PASS và đã được phép: thực hiện108rows theo order freeze; headroom/identity gate từng run; posthoc kernel RAM/time gate; lưu cả UNKNOWN, timeout, resource/crash và pending khi dừng. Không chạy song song.
- [ ] Hoàn tất/gián đoạn: lưu campaign state/coverage và per-case verdicts, giữ raw evidence; không nhận Task5 statistics/cross-OS đã hoàn tất. Linux-only kết quả, Windows BLOCKED. Các ngưỡng chưa đạt phải giữ NOT_MET, không sửa plan sau khi nhìn số.

Các command phase trên là giao diện sẽ được viết/review, **không phải lệnh có thể chạy ngay với code33b8023**. Khi người dùng chỉ duyệt triển khai tooling, chỉ làm§6 rồi dừng. Khi người dùng duyệt chạy cảpilot/primary, có thể thực hiện§7 liên tục nếu gates pass, không hỏi lại giữa các cases.

## 8. Tự rà và trạng thái lượt hiện tại

Budget/rules/108case membership đối chiếu plan gốc; pilot tách sample và shuffle algorithm là quyết định đề xuất ghi rõ. Interfaces nhất quán: matrix→gates→verdict→orchestrator; năm Review Focus có test tương ứng. Không thêm phase solver/Core feature hoặc report thống kê Task5.

Chỉ tạo tài liệu này và read-only readiness snapshot; không viết/sửa Python code, không generate inputs, không chạy warmup/pilot/campaign/benchmark, không commit/merge/push. Machine headroom lúc đọc không thay check trước run. Chưa có kết luận hiệu năng, pilot readiness để thực thi hoặc Windows support.

### Kiểm chứng tài liệu trong lượt lập kế hoạch

Đã thực hiện read-only integrity/runtime/headroom snapshot như§1, đọc source APIs và đối chiếu budget/gates. Đã chạy `uv sync --locked --extra solver`; `uv run --extra solver pytest -q` → **232 passed,4.66s**; `uv run ruff check .`, `uv run ruff format --check src tests benchmarks` →49files và `uv run mypy` →27files, đều PASS. Đây là regression Core có sẵn, không phải campaign hoặc tests orchestration Task4. Không rerun native resource suite/generate bundle/build/benchmark; full352 historical evidence còn khớp code. Không có code implementation thay đổi.


## 9. Snapshot triển khai tooling sau khi duyệt

Branch `feature/phase2a-task4-linux-orchestration`, base33b8023. §6 APIs/tests đã có; final review và kiểm chứng được ghi trong [báo cáo operational](../../phase-2a-operational-report.md#task-4-linux--orchestration-và-tests-chưa-chạy-campaign). Các ghi chú §8 là lịch sử lượt lập kế hoạch, không phải trạng thái source hiện tại. Không chạy §7, không Task5/2B/2C, không commit/merge/push; Windows BLOCKED. CLI contract nay đã implement, các command ví dụ chỉ chạy sau authorization execution và không dùng main33b8023 chưa chứa tooling.

Final tooling gate: **416 passed,134.04s**, gồm64campaign unit tests và existing installed tiny integration;232Core tests riêng PASS, lint/format/mypy27+29files/build PASS. Một fresh review:5Important+1Minor, đã sửa5Important và1author safety finding qua RED→GREEN; Minor progress khi identity-block được ghi rõ trong report. Full regression timeout300s là giới hạn kiểm thử, budgets campaign giữ nguyên. Bằng chứng `benchmarks/artifacts/phase2a/task4-linux-tooling-v1/verification-manifest.json`; chưa chạy§7 hoặc Task5, Windows BLOCKED.
