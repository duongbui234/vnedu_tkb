# Phase 2A Windows/Linux Operational Validation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans khi được người dùng cho phép triển khai. Checkboxes là công việc tương lai; lượt hiện tại chỉ tạo kế hoạch, không viết generator/runner, không tạo dữ liệu lớn hoặc chạy benchmark.

**Goal:** Kiểm chứng correctness, score, thời gian và RAM của Phase 2A trên Windows/Linux với dữ liệu synthetic 10/20/40 lớp, không thêm scheduling rules.

**Architecture:** Một bộ dữ liệu bất biến và witness đã kiểm chứng → cùng wheel Core trên hai OS → mỗi solve trong process riêng → đo resource đúng PID → independent validation/score → kết quả từng run và báo cáo tổng hợp. Benchmark tooling đứng ngoài `src/tkb_core`; không thêm callback hoặc sửa solver để lấy số đo.

**Tech Stack:** Core Python >=3.12; Pydantic 2.14.1, OR-Tools 9.15.6755 và `uv.lock` hiện tại. Tooling tương lai ưu tiên Python standard library và OS process accounting; không thêm dependency runtime.

**Spec:** [Phase 2A đã duyệt](../specs/2026-10-26-phase-2-quality-design.md), [nghiệm thu synthetic](../../phase-2a-report.md#rà-soát-nghiệm-thu-phase-2a--snapshot-main-30a6c55), [Core First, testing/benchmark](../../VNEDU_TKB_CORE_FIRST_CODEX.md). Snapshot code lập kế hoạch: `30a6c55b0871c8212dd858e3fd8d165728186390`.

## Global Constraints

- Chỉ lập kế hoạch trong lượt này. Không sửa Core/tests/dependency, cấu hình máy, API, AGENTS hoặc dữ liệu nghiên cứu; không commit/push.
- Khi triển khai sau: chỉ tooling kiểm chứng Phase 2A; không Phase 2B/2C, repair, UI, SQLite hoặc vnEdu adapter.
- Input 1.1/policy0.1, output1.2, S01–S04 soft; hard built-ins, một GV/một lớp và duration1/2 như hiện tại. Không suy schema vnEdu hoặc dùng PII/file trường làm fixture.
- Mọi lựa chọn dataset, ngân sách và ngưỡng pilot bên dưới là **INFERRED — đề xuất để duyệt**, không phải chính sách trường, SLA sản phẩm hay số đo đã có.
- **VERIFIED từ source:** Core có stage times/score/proof nhưng chưa có public progress callback để đo time-to-first-feasible từ lúc launch; default guards là 10,000 slots, 10,000 occurrences, 100,000 placements, 1,000,000 occupancy terms; workers1, seed42, budget60s.
- Giữ nguyên guards trong campaign chính, không nới để che resource failures. Input phải có confirmed demand/split/calendar trước solve; soft không được làm thiếu tiết hoặc phá locks.
- **UNKNOWN:** hiệu năng/độ ổn định trên Windows và quy mô trường. Chưa có môi trường Windows được xác nhận; Windows preflight phải thực hiện trên Windows thật, không thay bằng WSL hoặc Linux cross-build.

## Review Focus

1. Witness có thể không còn khớp sau thêm availability/locks/phòng: luôn kiểm lại trên input cuối và fingerprint; Task1/2.
2. Trọng số/độ khó khác nhau làm so score khác input vô nghĩa: chỉ so đúng fingerprint, profile, budget và tier order; Task2/5.
3. RSS đo nhầm runner/uv hoặc tích lũy qua nhiều child: target đúng PID, đo riêng từng run và công bố method/unit; Task3.
4. Hết budget/probe lỗi/process chết không phải INFEASIBLE: giữ trạng thái harness riêng với solver status; Task3/4.
5. Ba lần lặp không đủ cho P95/SLA, OS khác phần cứng không cô lập được hiệu ứng OS: nêu sample count và giới hạn; Task5.

## 1. Môi trường và khả năng so sánh

| Yếu tố | Campaign chính |
|---|---|
| OS | Windows x64 native và Linux x64 native; mốc đề xuất Windows11 và Ubuntu24.04 LTS, ghi đúng edition/build/kernel khi chạy |
| Máy tham chiếu | Ưu tiên dual-boot cùng máy, RAM16GiB trở lên, CPU ít nhất4 logical cores; ghi CPU model/topology/P-E cores, RAM, swap/pagefile, power/AC state |
| Python | 3.12 theo `.python-version`; ghi exact patch. So hiệu ứng OS chỉ khi patch và hardware khớp; nếu không, báo là hai deployment khác nhau |
| Core | Cùng wheel SHA-256; ghi git commit/core-tree hash, wheel hash, uv.lock hash và dependencies thực cài. Binary wheels phụ thuộc platform được phép khác hash, phiên bản phải khớp |
| Cài đặt | Venv riêng, install Core wheel với solver extra. Không dùng source checkout/PYTHONPATH thay installed package trong run đo |
| Song song | Mỗi máy một run tại một thời điểm, workers1, seed42; không chạy hai OS campaign cùng VM host hoặc cạnh workload nặng |
| Cache | Mỗi run là Python process mới; không gọi là cold-cache. Không drop OS caches/reboot/chỉnh cấu hình máy tự động; ghi run index và các workload/power bất thường |

Setup/import failure trên Windows là ENVIRONMENT_BLOCKED, không suy ra solver chậm/vô nghiệm; không tự đổi pin hoặc build lại OR-Tools từ source để qua preflight. [Google có hướng dẫn cài package Python riêng theo platform](https://developers.google.com/optimization/install/python); hướng dẫn đó không chứng minh các pin cụ thể của repo đã chạy trên Windows.

## 2. Dataset và witness chuẩn

### 2.1 Quy mô cố định

| Quy mô | GV synthetic | Môn | Calendar/cycle | Demand | Split/occurrences | Phòng khi bật |
|---|---:|---:|---|---:|---|---:|
| 10 lớp | 15 | 9 | 6 ngày ×2 buổi ×5 tiết =60 slots | 300 tiết | 4 doubles +22 singles/lớp =26 occurrences/lớp; tổng260 | 2 |
| 20 lớp | 30 | 9 | 60 slots | 600 tiết | tổng520 occurrences | 4 |
| 40 lớp | 60 | 9 | 60 slots | 1,200 tiết | tổng1,040 occurrences | 8 |

Đây là profile thử nghiệm, không phải định mức vnEdu. Mỗi lớp có năm môn4tiết, hai môn3tiết, hai môn2tiết: `[4,4,4,4,4,3,3,2,2]`. Hai môn4tiết split `[2,1,1]`, hai môn3tiết split `[2,1]`, còn lại singles. Một requirement/môn/lớp, cùng GV cho mọi component của requirement, không alternative splits.

Lịch witness ban đầu đặt 30 tiết vào 36 slots thuộc periods2–4 của 12 buổi; double luôn liền nhau và cùng buổi. Gán GV theo lớp và môn, ví dụ `(class_index + floor(subject_index * teacher_count / 9)) % teacher_count`: cùng môn/times ở các lớp có GV khác nhau; các môn ban đầu ở các times disjoint. Đây là cách tạo witness, không phải thuật toán scheduling mới trong Core.

GV phải nối nhiều lớp/môn, không chia workload lớn thành các bản sao10 lớp độc lập. Để tránh witness mọi lớp quá giống nhau, thử `5 × class_count` swaps có seed giữa components cùng duration; chỉ giữ swap nếu toàn resource footprint vẫn hợp lệ, giữ assignment GV/môn và phòng của occurrence. Ghi số swaps thử/thành công; không đổi seed hoặc làm profile dễ hơn nếu chưa đạt mong muốn. Generator failure là DATASET_GENERATION_FAILED.

Khi bật phòng: một requirement/lớp cần phòng, class.size=32, room.capacity=40; mỗi nhóm10 lớp có một room_type và hai phòng cùng type. Chọn môn cần phòng luân phiên theo class_index%9, rồi chỉ giữ witness/swaps khi phòng vẫn không trùng. Room candidates tối đa2/requirement; ghi tỷ lệ room periods và occurrences thực, không mặc định bằng tỷ lệ requirements.

### 2.2 Bốn profiles trên mỗi quy mô

| ID | Ground truth | Cấu hình ngoài demand |
|---|---|---|
| BASE | Feasible, witness score0 | Symbolic calendar; không phòng/locks; resources khả dụng toàn calendar; soft profile Z bên dưới |
| MIXED | Feasible, witness score0 | Timed calendar; mỗi lớp42available slots bao gồm30 witness periods; teacher availability chứa witness và ít nhất6 ô khác, tối thiểu36 slots nếu có; time locks10%occurrences; có phòng; soft Z |
| TIGHT | Feasible, witness và score đã biết, optimum chưa biết | Timed; lớp32available slots chứa witness, GV gồm witness+2ô khác; locks20%; có phòng; soft C buộc có penalty dương |
| UNSAT_CAPACITY | Infeasible bằng điều kiện cần | Từ BASE: một lớp demand30 chỉ còn29available slots; không locks/phòng. Input hợp lệ; không tạo khóa xung đột để rồi nhầm INPUT_INVALID thành INFEASIBLE |

Timed mode: `day_offset=(day−1)*1440`, AM bắt đầu420phút, PM780phút; mỗi period45phút, trong buổi liền nhau. Giữ cycle-wide origin và không trộn symbolic/timed trong một input. Tất cả profiles có 60slots can_teach=true; availability xử lý theo resource, không nhân các slot ID theo lớp.

Availability/locks được thêm **sau** khi witness hợp lệ; mọi tập phải giữ toàn footprint witness. Locks chọn theo occurrence, không khóa riêng nửa double; include time-only và ít nhất một time+room lock nếu dataset có room occurrences. Đối với UNSAT, giữ witness trước mutation chỉ làm provenance, **không** đính nhãn witness hợp lệ cho input sau mutation.

Ước lượng trước availability: BASE40 có ≤1,040×60=62,400placements; room requirements tối đa4occurrences/lớp, mỗi occurrence thêm tối đa60choices → MIXED/TIGHT40 ≤72,000placements. Đây là upper estimate, phải ghi actual counts bằng prepare ngoài run đo. Guard hit được báo RESOURCE_LIMIT, không tự tăng max_placements.

### 2.3 Soft profile và baseline

Mỗi GV có bốn rule instances, IDs duy nhất, scope teacher cụ thể; số declarations60/120/240. Không global+personal overlap cùng family. Mọi weight=1 explicit; priorities S01=P1, S02=P1, S03=P2, S04=P3 để thực sự kiểm ba tiers. Đây là cấu hình benchmark, không đổi default policy của application.

**Z — witness đạt0:** S01 chọn2available slots ngoài teaching footprint witness của GV; S02 limit là max teaching load/buổi trong witness; S03 limit là max teaching load/ngày trong witness (cả hai dùng0 nếu GV không có demand); S04 window[2,4] ở AM/PM. Baseline phải được evaluator xác nhận `(0,0,0)`; vì penalty không âm, biết trước optimum vector là0.

**C — preference có xung đột:** S01/S02/S04 như Z; S03 limit của GV là `max(0,ceil(total_teacher_periods/6)−1)`. Với demand dương, có lower bound P2 `sum_t max(0,D_t−6*limit_t)`; teacher không demand đóng góp0. Đây là lower bound, **không mặc định là attainable optimum** khi đã giữ P1/hard. Witness là upper bound khả thi; tính đầy đủ vector baseline bằng independent evaluator.

Mỗi dataset có một artifact witness riêng: `benchmark_schema_version='1.0'`, input_fingerprint, raw assignments, construction metadata; không chế ScheduleResult/solver_executed cho lịch do generator tạo. Parent API validate_schedule/evaluate_score kiểm witness bằng input cuối. Mọi required reference, split, room và rule đều phải qua contract/capability trước mass runs.

## 3. Ma trận chạy và lưu vết

- Generator seeds101/102/103; ba quy mô ×bốn profiles ×ba seeds = **36 datasets**. Generate một lần, truyền cùng bytes sang cả hai OS; kiểm file SHA-256 và input fingerprint trước chạy.
- Campaign chính: workers1, solver seed42, ba repeats mỗi dataset = **108 runs/OS, 216 runs cho hai OS**. Preflight/smoke không tính vào mẫu đo. Chạy tuần tự; order được shuffle cố định seed2026 theo từng repeat và lưu execution order.
- Sau campaign chính, tùy chọn chẩn đoán: workers4 nếu máy đủ logical cores, seed42, 12datasets dùng generator seed101, ba repeats →36runs/OS; seed sweep43/44 trên TIGHT/seed101 mỗi quy mô một lần →6runs/OS. Không gộp optional runs vào baseline workers1/seed42.
- Run ID gồm campaign, OS/machine, dataset hash, workers, solver seed, repeat. Mỗi run có thư mục riêng chứa input reference/hash, stdout, stderr, result nếu có, verification, metrics. Không ghi đè artifact của run trước hoặc input.
- Dữ liệu shape cần ghi: lớp/GV/môn/phòng, demand periods, occurrences, slots/tokens, placements, occupancy terms, số rules theo tier, teacher loads, availability density, lock counts và room share. Số lớp riêng lẻ không mô tả độ khó.

Core suite/preflight dùng dev environment riêng; installed-wheel venv dùng cho runs đo và verification API, kiểm `tkb_core.__file__` thuộc venv/site-packages, không trỏ editable checkout.

Không bảo đảm ba repeats cho cùng seed sinh lịch giống nhau; không đòi Windows/Linux trả cùng assignments, runtime hoặc optimum proof status. **Cùng assignments/input phải có cùng hard validity và score trên hai OS**: trao đổi result hoàn chỉnh của các run thành công để cross-validate/recompute, không chạy lại search cho bước này.

## 4. Correctness và score: tiêu chí nghiệm thu

| Tình huống | Quyết định |
|---|---|
| BASE/MIXED/TIGHT trả lịch | Bắt buộc contract đúng, fingerprint khớp, đầy đủ occurrences/duration/demand, validator pass và evaluator raw/weighted/tiers khớp result; sai một mục là correctness FAIL |
| Known-feasible trả INFEASIBLE | FAIL nếu witness trên đúng input cuối vẫn hard-valid; không gọi là bài quá khó |
| Known-feasible trả UNKNOWN/RESOURCE_LIMIT | Chưa có nghiệm trong ngân sách/guard, performance NOT_MET; không kết luận vô nghiệm |
| UNSAT_CAPACITY | Phải INFEASIBLE, không assignments/quality score; expected precheck không cần CP-SAT. INPUT_INVALID/UNKNOWN không được tính như pass |
| Profile Z | Nếu claim LEXICOGRAPHIC_OPTIMAL thì vector phải0; FEASIBLE có score>0 là quality chưa đạt, không là hard correctness failure |
| Profile C | Score≥lower bound có điều kiện theo prefix; không ép score bằng bound chưa chứng minh attainable. OPTIMAL không được lexicographically tệ hơn valid witness; FEASIBLE tệ hơn witness được ghi WORSE, không giả là đã cải thiện |
| Proof/status | Chỉ tiers OPTIMAL mới trong prefix, không skip active tier; exact proved values khớp final score; no optimality claim do feasibility-only OPTIMAL; CLI chỉ kiểm consistency, không tái chứng nhận proof từ file ngoài |
| Timeout/crash/watchdog | Không publish partial/invalid schedule. Harness status riêng; crash/kill không được chuyển thành solver INFEASIBLE |

Không yêu cầu mọi run quy mô trường chứng minh optimum; đúng status và hard-valid incumbent quan trọng hơn một claim tối ưu sai. Không có oracle exhaustive ở 10/20/40 lớp; oracle tiny hiện tại vẫn là preflight correctness, không được mô tả thành chứng minh optimum của trường lớn.

Core hiện chưa nhận witness như warm start/baseline. Vì vậy không đặt điều kiện blanket `final_score <= witness_score` cho mọi FEASIBLE run giới hạn thời gian. Phân loại quality: BETTER/EQUAL/WORSE/NO_SCHEDULE theo vector trên đúng fingerprint, đồng thời ghi proof prefix. Không so tổng scalar gộp tiers, không so raw score giữa hai datasets khác nhau.

## 5. Thời gian và RAM: phép đo, ngưỡng pilot

### 5.1 Ngân sách đề xuất — chưa phải SLA

| Quy mô | CP-SAT budget/run | Launch-to-exit watchdog | Target peak child memory |
|---|---:|---:|---:|
| 10 lớp | 60s | 150s | ≤1GiB |
| 20 lớp | 120s | 210s | ≤2GiB |
| 40 lớp | 180s | 270s | ≤4GiB |

Watchdog thêm90s cho startup/preprocessing/validation/I/O; không đồng nghĩa Core cam kết end-to-end bằng solver budget. Các giá trị là engineering pilot cần người dùng duyệt; không điều chỉnh sau khi thấy kết quả mà giữ nguyên campaign ID. Tổng budget cấp cho108runs/OS là3.6giờ CP-SAT theo cấu hình, không là ước lượng duration campaign; UNSAT thường dừng ở precheck, overhead không nằm trong phép cộng này.

Để đánh dấu **pilot performance đạt**: tất cả known-feasible BASE/MIXED/TIGHT runs phải có lịch hard-valid trong budget/watchdog và memory target; Z đạt vector0. TIGHT/C không bắt buộc prove optimum, nhưng luôn công bố tỷ lệ BETTER/EQUAL/WORSE so witness; chưa đặt SLA cải thiện score khi chưa có số đo. Không đạt ngưỡng là NOT_MET để phân tích, không tự nới budget hoặc hạ độ khó.

Trước mỗi run cần đủ available memory cho target cộng ít nhất2GiB headroom; thiếu thì ENVIRONMENT_BLOCKED, không chạy rồi gọi thất bại là solver OOM. RAM target là gate quan sát; không khẳng định đã có hard memory cap. Nếu monitor phát hiện vượt target, dừng run thử nghiệm có kiểm soát và ghi RESOURCE_STOP, không kết luận infeasible.

### 5.2 Định nghĩa thời gian

- `launch_to_exit_seconds`: monotonic timer ngay trước spawn Python child đến exit/reap; gồm interpreter/import, Core, output I/O; parent verification đo riêng.
- `core_wall_time`: metadata.wall_time của Core; `solver_wall_time`: tổng solver calls; `feasibility_solver_wall_time` và tier run wall/bound/proof lấy đúng metadata hiện có.
- `parent_verification_seconds`: đọc result, contract/fingerprint, independent hard/score; không cộng ngầm vào solver time.
- `first_feasible_elapsed_seconds=null`, reason NOT_INSTRUMENTED trong campaign này. Không đổi tên feasibility solver wall time thành TTF; muốn TTF thực cần yêu cầu instrumentation riêng, không sửa Core trong kế hoạch này.
- CPU time nếu thu được là process user+system qua mọi threads; có thể lớn hơn wall time. Missing measurement là null+reason, không0 giả.

### 5.3 Đo đúng memory của Python child

Spawn trực tiếp đường dẫn Python trong installed-wheel venv với `-m tkb_core.cli solve`, không đo process `uv`, shell hoặc toàn runner. stdout/stderr redirect sang files để không deadlock khi payload lớn; subprocess arguments là list, không nối shell command. Workers CP-SAT là threads trong child; vẫn đo cả Python/native allocations của process, không chỉ solver.

| Platform | Method dự kiến | Chuẩn hóa và điều kiện |
|---|---|---|
| Linux | `os.wait4(child_pid,...)` lấy per-child rusage.ru_maxrss; chỉ một owner wait/reap | Linux ru_maxrss có đơn vị KiB, nhân1024 ra bytes. Không lấy RUSAGE_CHILDREN tích lũy của runner nhiều jobs |
| Windows | Giữ process handle, query GetProcessMemoryInfo/PROCESS_MEMORY_COUNTERS.PeakWorkingSetSize đến khi hoàn tất, trước đóng handle | Field native là bytes. Phải có probe test process ngắn/spike rồi release; không chấp nhận số cuối0 hoặc mất peak do đọc quá muộn |

Ghi `peak_resident_bytes`, native field/value/unit, method, PID và measurement_status. Peak RSS Linux và peak working set Windows là hai phép đo gần tương ứng nhưng không hoàn toàn đồng nhất accounting; dùng làm gate theo OS, không khẳng định mức chênh nhỏ là solver dùng RAM hơn trên OS đó.

Lấy max sampled current RSS mỗi50ms chỉ làm telemetry/best-effort stop; không thay kernel peak mà không ghi `SAMPLED_LOWER_BOUND`. RAM probe lỗi → MEASUREMENT_BLOCKED, không được coi memory đạt. OOM/native crash giữ exit status/signal và resource evidence; không suy OOM chỉ từ UNKNOWN.

## 6. Metadata và cách tổng hợp

Mỗi record benchmark riêng version1.0, không đổi ScheduleResult:

- Identity: campaign/protocol version, input SHA/fingerprint, witness hash/score, generator seed/commit, core commit/tree/wheel hash, lock hash, exact installed package versions.
- Environment: OS/build/kernel, arch, Python exact version, CPU/logical cores, total/available RAM, swap/pagefile/power/workload note, child thread-related env vars nếu có.
- Run: workers/solver seed/repeat/order, configured guards, CP budget/watchdog/RAM target, timestamps, elapsed/CPU/memory methods/status.
- Outcome: harness_status, process_exit_code/signal, solver_status nếu có, valid_schedule, recomputed validation/score, active tiers, per-rule raw/weighted penalty, vector, prefix, each tier bound/proof/wall, resource diagnostics.
- Missing: trường đo không có phải null+reason. Harness statuses ít nhất COMPLETE/WATCHDOG_TIMEOUT/RESOURCE_STOP/CRASH/ENVIRONMENT_BLOCKED/MEASUREMENT_BLOCKED/OUTPUT_INVALID; không nhét các giá trị này vào Core SolveStatus.

CLI exit3/INFEASIBLE và exit4/UNKNOWN là outcomes bình thường nếu JSON/status khớp, vẫn harness COMPLETE rồi áp verdict riêng; không gọi mọi nonzero exit là crash. Exit0/2/3/4/5 phải khớp contract CLI khi có JSON hợp lệ; known exit với output lỗi → OUTPUT_INVALID, native signal/unrecognized exit → CRASH. Input/unsupported do thiếu môi trường/config phải được phân loại và dừng đúng nguyên nhân, không tính như solver timeout.

Một hàng tổng hợp cho mỗi OS/machine +size/profile/input hash+workers+solver seed, n=3: min/median/max, số có nghiệm/proved/unknown/failed, score từng run và peak memory. Summary theo size/profile có thể ghi9runs từ ba generator seeds, nhưng không gọi đó là9lần lặp cùng bài. Không tính P95 hoặc suy SLA từ3samples; không trộn OS/workers/budgets hoặc loại timeout để số đẹp hơn.

Time-to-solution của timeout là censored/unknown, không gán watchdog là thời gian tìm nghiệm. Nếu hiển thị median wall của successful runs, nêu rõ conditional-on-success và đếm riêng failures. Khi máy/patch khác nhau, kết luận deployment-level, không quy chênh lệch cho OS. Giữ raw records để tái tổng hợp.

## 7. Trình tự và file dự kiến khi được phép triển khai

Hiện chưa có thư mục benchmark triển khai cho Core. Giữ tooling nhỏ, hai scripts, tests tách khỏi distribution product; không tạo service, database hoặc public Core API mới.

| File tương lai | Trách nhiệm |
|---|---|
| `benchmarks/generate_synthetic.py` | Generate input+witness+manifest theo protocol; deterministic IDs/seeds, verify trước xuất |
| `benchmarks/run_benchmarks.py` | Preflight, spawn/monitor từng run, OS accounting, verification và tổng hợp JSON/CSV/Markdown |
| `benchmarks/tests/test_generate_synthetic.py` | Demand/split/witness/profile/manifest invariants |
| `benchmarks/tests/test_run_benchmarks.py` | Timers/status/units/watchdog/measurement errors/aggregation bằng tiny subprocesses |
| `benchmarks/artifacts/phase2a/<campaign>/` | Inputs/manifests/run records/raw stdout/stderr/results; ignored, không tự upload |
| `docs/phase-2a-operational-report.md` | Báo cáo thực sau chạy, phân biệt từng OS/cỡ/profile và blockers |

Future .gitignore chỉ thêm artifacts path nếu cần; không thêm benchmarks vào wheel/sdist allowlist hoặc thay runtime dependency. Không tạo các file này trong lượt lập kế hoạch.

**Giao diện tooling dự kiến, chưa tồn tại — không chạy trong lượt này:** `generate_synthetic.py --output <bundle>` xuất đúng36datasets +witnesses +manifest; `run_benchmarks.py --bundle <bundle> --python <installed-python> --campaign-id <id> --output <root> --matrix primary` chạy108jobs theo protocol. Giá trị matrix khác chỉ `workers4` hoặc `seed-sweep` như mục3; không flag tự đổi rule/budget âm thầm. Runner xác định OS hiện tại, không có flag giả Windows trên Linux. Output root phải mới; resume chỉ chạy các run ID chưa complete với cùng manifest/settings, không overwrite kết quả.

### Task 1 — Fixture/witness generator

Consumes protocol mục2; produces input1.1, WitnessArtifact và manifest có SHA/fingerprint/baseline truth.

- [x] Viết tests trước: mỗi lớp30periods/26occurrences, số GV15/30/60, không duplicate ID; W validate đúng trên BASE/MIXED/TIGHT; UNSAT chỉ29class slots và contract vẫn valid.
- [x] Test cùng seed ra cùng bytes/hash; đổi generator seed có khác dataset hash; altered split/availability/room/lock làm witness sai phải dừng, không đánh nhãn feasible.
- [x] Implement generator tối thiểu, `5*C` swap attempts có thống kê và profile stages như mục2; ghi actual model dimensions/guard result.
- [x] Run `uv run pytest benchmarks/tests/test_generate_synthetic.py -q`; expected PASS trước xuất36datasets. Không tạo dataset cho benchmark khi chưa được người dùng cho phép implementation.

### Task 2 — Preflight Windows/Linux

Consumes cùng wheel, lock và dataset bundle; produces environment manifests và preflight status.

- [ ] Cài venv theo platform, verify đúng wheel/lock/input hashes; chạy full Core suite + installed-wheel mini solve/validate/score và no-solver scorer smoke. **Linux PASS (2026-10-26); Windows BLOCKED**, chưa nghiệm thu hai OS.
- [x] Test ready/non-ready registry, malformed/stale result, invalid locks và unknown custom hard bằng tiny cases đã có; không đưa các case invalid vào latency feasible.
- [ ] Validate/evaluate mọi W bằng input cuối trước run đo; xác nhận Z=0 và C positive lower bound; UNSAT có bằng chứng30>29. Bất kỳ generator/hard mismatch thì dừng campaign. **Linux installed-wheel PASS đủ36 datasets; Windows BLOCKED.**
- [x] Windows unavailable/install/probe fail → BLOCKED rõ ràng. Không chạy Linux thay rồi đánh dấu Windows pass.

### Task 3 — Resource supervisor

Consumes installed Python path + CLI args/budget; produces one run record/artifact directory.

- [x] Tests fail trước cho subprocess sleep quá watchdog, child allocate spike rồi release, child ngắn, exit3/INFEASIBLE hoặc4/UNKNOWN hợp lệ, native exit bất thường, output hỏng, PID/resource probe error; expected không bao giờ đổi crash/timeout thành INFEASIBLE hoặc missing RSS thành0.
- [ ] Implement two OS probes trong runner, normalize units, owner wait/reap riêng; direct child và file redirection. Test KiB→bytes bằng literal1024, Windows bytes giữ nguyên; compare kernel peak với sampled telemetry, không tự thay metric.
- [ ] Test một child memory lớn rồi child nhỏ: run thứ hai không mang peak tích lũy run thứ nhất. Linux/Windows native probe test phải chạy thật trên OS tương ứng; mocked Windows adapter trên Linux chưa nghiệm thu Windows.
- [x] `uv run pytest benchmarks/tests/test_run_benchmarks.py -q` PASS và logs chỉ rõ method/status trước mass measurement.

**Execution snapshot:** Linux implementation/tests PASS (82 supervisor tests, full352 PASS); Windows **BLOCKED**, Task3 overall **PARTIAL**. Chỉ Linux backend, chưa triển khai hai OS/campaign. Xem [báo cáo Task3](../../phase-2a-operational-report.md#task-3-linux--resource-supervisor-triển-khai-sau-task-2).

### Task 4 — Campaign tuần tự

Consumes36verified datasets; produces108run records/OS.

- [ ] Run setup warmup không đo; chạy BASE10 một lần đo để phát hiện harness lỗi, rồi mới campaign theo order đã lưu; pilot run chỉ vào mẫu nếu đúng reserved run ID/settings, không đếm hai lần.
- [ ] Mỗi case cùng guards/budget, seed42/workers1 và ba fresh-process repeats; không chạy đồng thời. Ghi progress theo run, không in fake solver percent.
- [ ] Watchdog/resource stop chỉ dừng child thuộc run, giữ evidence; không sửa input, publish schedule hoặc tự retry với cấu hình dễ hơn. Run hỏng không bị xóa khỏi báo cáo.
- [ ] Cross-validate results giữa OS sau khi thu; optional workers4/seed sweep là campaign phụ có nhãn, chỉ sau baseline.

**Implementation snapshot 2026-10-27:** Task4 Linux orchestration/tests đã được triển khai trên nhánh feature, **416tests PASS**, lint/format/mypy/build PASS; một fresh review và một lượt sửa Important đã hoàn tất; chưa thực hiện prepare/warmup/pilot/primary thực tế, chưa commit/merge/push. Các execution checkboxes bên trên giữ unchecked. Windows BLOCKED, Task5 chưa bắt đầu. [Chi tiết tooling/runbook](2026-10-27-phase-2a-task4-linux-pilot-campaign.md), [báo cáo](../../phase-2a-operational-report.md#task-4-linux--orchestration-và-tests-chưa-chạy-campaign).

### Task 5 — Tổng hợp và quyết định

Consumes raw records; produces report với correctness verdict và pilot performance verdict tách biệt.

- [ ] Test aggregator với COMPLETE/UNKNOWN/CRASH/MEASUREMENT_BLOCKED hỗn hợp: denominator giữ đủ, vectors chỉ cho valid schedules, null metrics không thành0, không median-gộp khác fingerprints.
- [ ] So mọi gate mục4/5; correctness FAIL thì không công bố ready; performance NOT_MET thì mô tả đúng bottleneck và phạm vi, không tự tăng budgets/giảm profile.
- [ ] Báo riêng Z exact-known optimum, C witness comparison/lower bound/proof; không khẳng định FET/STKB nhanh/chậm hơn vì không có bài tương đương.
- [ ] Đề nghị quyết định tiếp sau số đo: tiếp tục2A performance fix có testcase tái hiện hoặc chấp nhận pilot; không tự mở2B/2C.

## 8. Điều kiện kết thúc và giới hạn lượt hiện tại

Kế hoạch có thể chuyển sang implementation tooling khi người dùng duyệt dataset/profile, ngưỡng pilot, máy/OS sẽ dùng và cho phép tạo generator/runner. Thành công của campaign phải có cả hai OS thật, đầy đủ manifests/raw outcomes, correctness pass và verdict performance theo thresholds đã freeze; Linux-only hoặc missing native RAM probe là incomplete/blocked, không kết luận tương đương Windows.

Đã tự rà protocol với source metadata/guards/CLI hiện tại và nguồn OS bên dưới. **Chưa tạo scripts, fixtures10/20/40, chưa chạy benchmark, chưa chạy lại pytest/lint/build trong lượt chỉ viết Markdown này.** Không có số đo mới hay claim thời gian/RAM thực. Không sửa Core/tests/dependency; tài liệu nghiệm thu và AGENTS đang thay đổi từ trước giữ nguyên; chưa commit/push.

### Nguồn đo đạc đã đối chiếu

- [Python os.wait4](https://docs.python.org/3.12/library/os.html#os.wait4): per-child PID/status/rusage, Unix availability; không dùng như Windows API.
- [Python resource](https://docs.python.org/3.12/library/resource.html#resource.getrusage) và [Linux getrusage](https://man7.org/linux/man-pages/man2/getrusage.2.html): resource fields và Linux ru_maxrss KiB; RUSAGE_CHILDREN tích lũy không phải metric riêng từng run.
- [Microsoft PROCESS_MEMORY_COUNTERS](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters): PeakWorkingSetSize bytes; Windows method vẫn cần probe test thật, đọc tài liệu không thay thử nghiệm.
- Local: `solver/options.py::SolveOptions`, `contracts/output.py::SolverRunMetadataV12`, `contracts/score.py::StageRun`, `solver/objectives.py::run_quality`, `domain/models.py::TimeSlot`, `cli.py::main` tại snapshot đã nêu. Kiểm chứng nguồn là VERIFIED; dataset/thresholds là INFERRED; hiệu năng thực là UNKNOWN.

## Ghi nhận thực thi Task 1 — 2026-10-26

Người dùng đã duyệt triển khai **chỉ Task 1**; các câu “chỉ lập kế hoạch” phía trên mô tả lượt lập kế hoạch ban đầu. Task 1 generator/tests đã triển khai trong worktree `feature/phase2a-synthetic-generator`; 270 tests pass (232 Core + 38 generator), lint/type-check/build pass. Xuất và verify lại 36 datasets, không solve/search hoặc đo latency/RAM cho chúng. Xem [báo cáo Task 1](../../phase-2a-generator-report.md). Task 2–5 còn nguyên chưa triển khai; chưa commit/merge/push.

Review độc lập Task 1 hoàn tất: Ship within Task 1 scope, không Critical/Important/Minor findings. Windows/installed-wheel/performance và filesystem thù địch chưa được kiểm chứng; giới hạn và rulings ghi trong báo cáo Task 1.

## Ghi nhận Task 2 Linux — 2026-10-26

Người dùng duyệt thực hiện phần Linux. Hai clean venv dùng cùng wheel/lock, installed-package path/source check,232 Core tests,13 CLI smoke cases, registry pending-rule/no-solver guard và verify36datasets đều PASS. Windows **BLOCKED**, Task2 overall **PARTIAL**; không bắt đầu Task3-5, không benchmark hoặc2B/2C. Xem [báo cáo preflight](../../phase-2a-operational-report.md). Chỉ report/kế hoạch thay đổi; chưa commit/merge/push Task2.

## Ghi nhận Task 5 Linux — 2026-10-27

Task5 **phần Linux** đã triển khai aggregator read-only riêng tại `benchmarks/aggregate_linux.py` để giữ source identity của runner đã freeze. Đã tổng hợp108primary, kiểm110receipts và recheck hard/score trên kết quả lưu; không chạy lại campaign search. [Báo cáo](../../phase-2a-task5-linux-report.md): performanceNOT_MET (27NO_SCHEDULE +36ZERO_TARGET_NOT_MET); correctness không FAIL quan sát được nhưng coverageINCOMPLETE do27UNKNOWN. Denominator108được giữ đủ; statistics chỉ trong từng dataset/fingerprint, không P95/SLA từ3repeats. Đã đề xuất điều tra TIGHT10, chưa thực hiện tuning/2B/2C/repair. WindowsBLOCKED nên Task5/toàn campaign **hai OS** cònPARTIAL; checkboxes mục Task5 phía trên không phải tuyên bố nghiệm thu hai OS.

Nghiệm thu Task5 **Linux-only**: [x] regression aggregator hỗn hợp/null/fingerprint; [x] đối chiếu gates và phân rã63not-qualified; [x] báo riêng Z/C/UNSAT và proof; [x] đề xuất điều tra TIGHT10, chưa thực thi. Full suite439PASS, lint/format/mypyPASS; fresh review không findings. Đây không đánh dấu Windows hoặc toàn Phase2 đã đạt.
