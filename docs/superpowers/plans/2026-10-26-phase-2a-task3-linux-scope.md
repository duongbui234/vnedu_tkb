# Task 3 Linux — điều kiện bắt đầu và phạm vi resource supervisor

Ngày khảo sát: 2026-10-26. Snapshot `main=71b9ad8f1b67fff8dec598029ea363bed3960046`. **Phạm vi đã được người dùng duyệt trong phiên; chưa triển khai.** Tài liệu này cụ thể hóa phần Linux của [Task 3 trong kế hoạch đã duyệt](2026-10-26-phase-2a-operational-validation.md#task-3--resource-supervisor), không thay đổi ngân sách hoặc mở campaign.

## 1. Kết luận điều kiện bắt đầu

**VERIFIED:** Các prerequisite để phát triển/kiểm thử supervisor trên Linux hiện còn đủ. **INFERRED:** Có thể triển khai riêng phần Linux sau khi người dùng duyệt phạm vi này; không cần đợi Windows để viết và kiểm thử Linux. Task 2 hai OS vẫn PARTIAL; Task 3 hai OS chưa thể nghiệm thu. **Windows BLOCKED** và không được giả bằng WSL/mocks.

| Điều kiện | Kết quả kiểm tra lần này |
|---|---|
| Task 1 đã merge/push | Snapshot main71b9ad8 có generator và witness/manifest tests |
| Linux installed-wheel preflight | PASS theo [báo cáo và raw evidence](../../phase-2a-operational-report.md) đã lưu; lần này không rerun smoke |
| Integrity evidence | Đối chiếu lại đủ52 SHA-256 trong preflight-manifest, tất cả khớp |
| Core tree hiện tại so với preflight | Khớp `1efd459b2514f448dcf4ac297989de09eb76a3a1`; HEAD mới chỉ thêm tài liệu |
| Lock hiện tại | SHA `e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084` khớp |
| Frozen wheel | Còn tại `preflight-linux-v1/distribution/`; SHA `1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9` khớp |
| Bundle36 datasets | Root SHA `a278a02dd9e10fedc7c5fcf44ef81d038d7712eba929d881a0f6193fc97cc93d` khớp; không regenerate |
| Installed Python | `preflight-linux-v1/venv-solver/bin/python` còn tồn tại; lần này không chạy solve |
| Linux APIs | Có `posix_spawn`, file actions DUP2/CLOSE, `wait4`, WNOHANG, waitstatus_to_exitcode và kill; đọc được `/proc/self/statm` |
| Supervisor/runner | Chưa có `benchmarks/run_benchmarks.py`; chưa có số đo hoặc test native resource probe |

Các path evidence ở trên đều dưới worktree `.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/`, đang giữ trên branch `feature/phase2a-task3-linux-scope`. Khả dụng API chỉ chứng minh có thể gọi, chưa chứng minh phép đo/watchdog đúng. Trước triển khai phải kiểm lại package path/versions bằng preflight đã có; trước campaign phải kiểm lại headroom, workload và toàn bộ gates riêng.

## 2. Lựa chọn cách triển khai — đề xuất, chưa được nghiệm thu

Hai cách giữ một process con trực tiếp:

- `Popen` cùng `wait4`: quen thuộc nhưng dễ có hai nơi reap; `poll()`, `wait()`, context manager hoặc cleanup có thể gọi waitpid trước. Muốn dùng phải sở hữu toàn vòng đời, không vá private methods hoặc gán returncode trái public contract.
- **Đề xuất Linux: `os.posix_spawn` + một owner `os.wait4(pid, WNOHANG)`**. argv là list, executable là absolute installed Python, stdout/stderr qua file actions. Không có Popen destructor/waiter cạnh tranh; thêm một ít quản lý file descriptors nhưng nằm gọn trong supervisor Linux. Không dùng fork/preexec callback hoặc thêm dependency.

**VERIFIED từ docs/source:** wait4 trả PID, wait status và per-child rusage; WNOHANG cho phép kiểm deadline mà không chặn đến lúc child exit. Linux ru_maxrss có đơn vị KiB. `subprocess.Popen._internal_poll` trong Python3.12.3 thực cài tại `/usr/lib/python3.12/subprocess.py:1973` gọi waitpid; context exit tại dòng1092 gọi wait. [Python os](https://docs.python.org/3.12/library/os.html#os.wait4), [posix_spawn/file actions](https://docs.python.org/3.12/library/os.html#os.posix_spawn), [Popen lifecycle](https://docs.python.org/3.12/library/subprocess.html#popen-objects), [Linux getrusage](https://man7.org/linux/man-pages/man2/getrusage.2.html).

**INFERRED — thiết kế:** Tách hàm giám sát process/thu số đo và hàm đọc/kiểm CLI result trong cùng script. Tests đo kernel dùng child Python rất nhỏ; tests outcome kiểm result contract riêng. Chưa cần campaign CLI, plugin, multiprocessing pool hoặc framework adapter đa OS.

## 3. Phạm vi triển khai Linux đề xuất

1. **Một lần chạy, một child được sở hữu.** Dùng installed Python tuyệt đối, `-I -m tkb_core.cli solve`, input/output paths tuyệt đối; không shell/uv wrapper. Parent dùng cùng installed Core để verify; kiểm path/versions, wheel/lock/input identity trước spawn. Core/guards/budgets không đổi. Fixture child dùng Python standard library; không giải các bộ10/20/40 lớp trong Task3 tests.
2. **Một owner reap.** Chỉ supervisor gọi wait4 với đúng PID; không wait(-1), không thêm thread/callback reap và không RUSAGE_CHILDREN tích lũy. Đọc status/rusage khi child kết thúc; chuyển wait status bằng waitstatus_to_exitcode. File handles/fds phải đóng trên cả nhánh lỗi.
3. **Watchdog.** Monotonic timer bắt đầu ngay trước spawn; vòng lặp kiểm reap trước rồi kiểm deadline/telemetry. Khi quá hạn: ghi stop reason, signal đúng child chưa reap, TERM trước; grace đề xuất1giây, rồi KILL nếu còn chạy, luôn thu hồi bằng owner wait4. Thời gian cleanup tính trong launch-to-reap, không được hứa deadline tuyệt đối nếu kernel không đáp ứng. Đề xuất1giây là policy tooling để duyệt, không thay budget CP-SAT/watchdog campaign.
4. **Memory và CPU.** `peak_resident_bytes=ru_maxrss*1024`, kèm native field/value/unit và method Linux wait4; CPU là ru_utime+ru_stime. RSS sampled từ `/proc/<pid>` mỗi50ms chỉ dùng telemetry/best-effort resource stop, không thay kernel peak; phải ghi sampled method/unit và giới hạn bỏ lỡ spike. Nếu đổi pages→bytes, dùng page size hệ thống. Không tracemalloc làm oracle native RAM và không coi RAM host là RAM child.
5. **Probe failure.** Thiếu quyền, rusage mất, PID không thuộc owner, JSON hỏng hoặc measurement unavailable phải có reason; metric thiếu để null. Không giả peak0, không suy OOM chỉ từ SIGKILL/UNKNOWN. `/proc` mất do child vừa thoát phải kiểm wait4 để phân biệt exit bình thường với lỗi probe; child quá ngắn vẫn có kernel peak khi reap. Không signal PID sau khi đã reap hoặc mất xác nhận ownership.
6. **Output và cleanup.** Redirect stdout/stderr vào files, không giữ PIPE có thể đầy. Thư mục run mới, tạo độc quyền, không overwrite inputs/records cũ; result chỉ được coi là lịch xuất hợp lệ sau contract/fingerprint/independent hard+score validation. Giữ raw files khi timeout/crash; không auto-retry với input dễ hơn. `finally` xử lý child thuộc run khi parent có exception/KeyboardInterrupt; parent bị SIGKILL không có bảo đảm cleanup, phải ghi giới hạn này. Không quét/kill process của phiên khác.

Task này chỉ đo process Python trực tiếp (OR-Tools/native allocations trong process); không phát triển đo toàn cây descendants hoặc hard memory cap/cgroups. Test fixtures không được sinh process con cháu để lẫn nghĩa phép đo.

## 4. Outcome contract cần giữ tách biệt

Record tooling version1.0, ngoài ScheduleResult; giữ nguyên input/output schemas của Core. Có PID, argv, paths/checksums, configured limits, monotonic elapsed, raw wait status/exit/signal, stop reason, CPU/kernel peak/sampled peak, measurement status/reason và output verification. Các trường không đo được là null+reason; TTF vẫn null/NOT_INSTRUMENTED. Parent verification time tách khỏi child time.

| Tình huống | Harness outcome đề xuất |
|---|---|
| Exit0, result hợp lệ và independent hard/score khớp | COMPLETE, valid_schedule=true |
| Exit3+INFEASIBLE hoặc exit4+UNKNOWN, JSON/contract/fingerprint nhất quán | COMPLETE với solver_status tương ứng; không gọi là crash |
| Exit2+INPUT_INVALID/UNSUPPORTED_FEATURE hoặc exit5+MODEL_INVALID, contract phù hợp | COMPLETE như kết quả lỗi của Core; không đánh dấu lịch hợp lệ hoặc performance PASS |
| Exit0/2/3/4/5 nhưng payload hỏng, thiếu, stale hoặc không khớp exit/status | OUTPUT_INVALID; thiếu output không tự thành INFEASIBLE |
| Native signal/unrecognized exit, không có stop request từ supervisor | CRASH; giữ signal, không đoán nguyên nhân OOM |
| Watchdog stop hoặc resource stop | WATCHDOG_TIMEOUT / RESOURCE_STOP, không publish schedule dù file đã xuất hiện |
| Spawn/prerequisite không đáp ứng | ENVIRONMENT_BLOCKED; child metrics null nếu chưa spawn |
| Kernel/proc probe thực lỗi, không lấy được metric bắt buộc | MEASUREMENT_BLOCKED; giữ exit/raw result riêng, không báo RAM đạt |
| Parent KeyboardInterrupt/exception cần dừng child | Ghi stop reason PARENT_INTERRUPTED; đề xuất CANCELLED cho harness, không thêm vào SolveStatus |

Một run có thể có cả lỗi output và measurement: lưu riêng `measurement_status`, `output_validation` và stop reason để không mất evidence. Ưu tiên primary harness status: parent stop/watchdog/resource stop → native crash → measurement blocked → output invalid → COMPLETE. Prerequisite fail trước spawn là ENVIRONMENT_BLOCKED. Đối với unexpected parent exception, giữ error reason, cleanup và không giả COMPLETE. CANCELLED là đề xuất bổ sung tooling cần duyệt; không thay Core enum.

**VERIFIED từ source:** `src/tkb_core/cli.py::main` dòng253–255 map INFEASIBLE→3, UNKNOWN→4, MODEL_INVALID→5, valid→0, lỗi còn lại→2. Result contract tại `contracts/output.py::ScheduleResult`; không phải mọi lỗi CLI đều có full ScheduleResult, phải nhận đúng error envelope rồi giữ nó là lỗi, không giả lịch.

## 5. Tests nghiệm thu Linux — chỉ triển khai sau khi duyệt

TDD: viết tests fail trước, rồi implement tối thiểu trong files đã có trong kế hoạch:

- `benchmarks/run_benchmarks.py`: chỉ primitives giám sát một run và output verification; chưa matrix/sweep/resume/aggregation.
- `benchmarks/tests/test_run_benchmarks.py`: bounded tiny subprocesses + native Linux tests; không đưa vào product wheel/sdist.
- Cập nhật `docs/phase-2a-operational-report.md` khi có kết quả thực; artifacts mới vào root ignored mới, giữ evidence Task1/2.

| Test bắt buộc | Điều chứng minh |
|---|---|
| Tiny child exit ngay, child kết thúc giữa hai lần sampling | wait4 thu peak/exit đúng; không cần bắt được RSS sample để có kernel peak |
| Child allocate/touch rồi release trước exit | kernel peak giữ spike; sampled peak chỉ là lower bound |
| Child memory lớn rồi nhỏ trong cùng parent | không lấy peak tích lũy/của child trước; fixtures bounded, không ép máy OOM |
| Literal KiB1024 → bytes1048576; pages dùng page size | không lẫn đơn vị hoặc hệ số1000 |
| Child sleep vượt watchdog; child bỏ qua TERM | đúng stop reason, KILL sau grace khi cần; reap, không zombie |
| Resource threshold bị vượt; parent interruption | chỉ dừng child thuộc run, cleanup và không phát lịch |
| Unrelated child cùng parent | không reap/signal nhầm PID, không lấy RAM/exit của nó |
| Exit3/4 hợp contract; exit2/5 lỗi hợp lệ | COMPLETE đúng nghĩa execution, không đồng nghĩa successful schedule |
| Exit hỏng/signal, missing/malformed/stale result, forged score | CRASH/OUTPUT_INVALID đúng nhánh, không chuyển thành INFEASIBLE |
| wait4 lỗi/ECHILD, proc permission failure, PID mismatch, exit/proc race | null+reason hoặc reap đúng; không metric0 giả hoặc signal PID không còn sở hữu |
| stdout/stderr lớn hơn pipe capacity; output root tồn tại | không deadlock/overwrite; raw evidence giữ nguyên |
| Một tiny CLI solve/validate/score qua installed Python | supervisor nối đúng package, exit/contract/hard/score; không dùng dữ liệu trường |

Các tests timing dùng child sleep dài hơn deadline có biên; RSS dùng pages thực được touch, so các khoảng đủ rộng thay vì exact bytes; harness test timeout ngoài ngăn suite treo. Đây là tests phép đo có giới hạn, **không campaign benchmark** hoặc số liệu hiệu năng sản phẩm.

Điều kiện nghiệm thu phần Linux: tests supervisor native Linux pass; full Core+generator suite, lint/format/mypy pass; installed wheel/hash và frozen inputs không đổi; metric provenance rõ, không đổi crash/timeout/probe error thành infeasible. Toàn Task3 vẫn PARTIAL_WINDOWS_BLOCKED cho đến khi có native Windows tests; không có adapter giả Windows rồi tick PASS.

## 6. Những việc chưa được phép trong lượt này

- Chưa tạo/sửa Python code, tests hoặc runner; chưa chạy tests child memory/sleep/native resource probe của supervisor hoặc solve các bộ10/20/40 lớp; chưa benchmark. Regression Core có các tiny solve/probe của Core cũ, không phải nghiệm thu supervisor.
- Chưa thực hiện Task3 implementation, Task4/5, campaign108runs, optional workers/seed sweep, summary statistics hoặc performance tuning.
- Chưa sửa Core, generator, dependency, guards, API/UI/SQLite, AGENTS hoặc nghiên cứu; chưa commit/merge/push tài liệu này.
- Đã đọc repository, đối chiếu52 evidence hashes + lock/bundle/core tree, kiểm API presence và đối chiếu tài liệu OS. Đã chạy `uv sync --locked --extra solver`, `uv run --extra solver pytest -q` (**232 passed,4.37s**), `uv run ruff check .`, `uv run ruff format --check src tests` (**44files**) và `uv run mypy` (**27files**), đều PASS. Không chạy build/benchmark hoặc thêm tests mới; kết quả270tests của lượt merge trước là lịch sử, không phải test run lượt này.

**Phạm vi đã duyệt:** Linux-only, posix_spawn+wait4, TERM grace1s và CANCELLED tooling status; giữ Windows BLOCKED. [Implementation plan](2026-10-26-phase-2a-task3-linux-implementation.md) được viết riêng để duyệt trước khi triển khai. Chưa cho phép chạy benchmark hoặc mở Task4.
