# Phase 2A — Task 2: preflight Linux

Ngày: 2026-10-26. Phạm vi được duyệt: **chỉ phần Linux của Task 2** trong [kế hoạch vận hành](superpowers/plans/2026-10-26-phase-2a-operational-validation.md#task-2--preflight-windowslinux).

| Phần | Trạng thái |
|---|---|
| Linux preflight | **VERIFIED — PASS** trong môi trường dưới đây |
| Windows preflight | **BLOCKED** — chưa có môi trường Windows native được cung cấp/chạy |
| Task 2 tổng thể hai OS | **PARTIAL — WINDOWS BLOCKED** |
| Benchmark, latency/RAM, Windows/Linux cross-validation | **NOT RUN** |

Không viết runner, không chạy solve cho datasets 10/20/40 lớp, không đo benchmark, không Phase 2B/2C. Không thay đổi Core, tests cũ, generator, dependency hoặc lock. Không gọi API, dùng dữ liệu thật hoặc sửa nghiên cứu. Chưa commit/merge/push lượt Task 2.

## Môi trường và nguồn thực tế

- OS: Ubuntu 24.04.5 LTS, x86_64, kernel `7.0.0-38-generic`.
- Python: 3.12.3; uv 0.11.14. Không thấy WSL kernel marker hoặc `/.dockerenv`; không suy từ hai dấu hiệu này rằng mọi hình thức ảo hóa đều đã bị loại trừ.
- CPU: 12th Gen Intel(R) Core(TM) i7-12700H; 20 logical CPUs. P/E topology, power và workload không kiểm soát; không kết luận hiệu năng.
- Snapshot `/proc/meminfo`: total 41,723,125,760 bytes, available 30,543,351,808 bytes, swap 8,589,930,496 bytes. Đây là RAM hệ thống tại lúc đọc, **không phải peak RSS của solver**.
- Source commit: `4cfa643148b967ad7baf674fe6439699afbe51e2`; Git Core tree: `1efd459b2514f448dcf4ac297989de09eb76a3a1`.
- Cả hai venv cài **cùng wheel** `vnedu_tkb_core-0.2.0-py3-none-any.whl`, không editable.
- Wheel SHA-256: `1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9`.
- Lock SHA-256: `e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084`.
- Bundle Task 1 SHA-256: `a278a02dd9e10fedc7c5fcf44ef81d038d7712eba929d881a0f6193fc97cc93d` — dùng nguyên bundle đã xuất, không regenerate hay thay profile.

Đã export dependencies từ `uv.lock --locked`, cài với `--require-hashes --only-binary :all:` rồi cài Core wheel `--no-deps`. Solver extra được yêu cầu tường minh ở venv solver. Không cập nhật pin hoặc build OR-Tools từ source. `uv pip check` pass cho cả hai venv.

Runtime thực của venv solver:

```json
{
  "pydantic-core": "2.50.1",
  "typing-extensions": "4.16.0",
  "six": "1.17.0",
  "pandas": "3.1.0",
  "typing-inspection": "0.4.4",
  "python-dateutil": "3.0.0",
  "pydantic": "2.14.1",
  "immutabledict": "4.3.1",
  "vnedu-tkb-core": "0.2.0",
  "annotated-types": "0.8.0",
  "tzdata": "2026.5",
  "protobuf": "6.33.6",
  "absl-py": "2.5.1",
  "numpy": "2.5.4",
  "ortools": "9.15.6755"
}
```

Venv không solver chỉ có Core cùng 5 dependency Pydantic; `find_spec('ortools') is None`. Mọi distribution/version đã được so với `uv.lock`. Đã so **27 source .py files** giữa checkout, wheel ZIP và package thực đã import, nội dung bằng nhau. `tkb_core.__file__` ở `venv-*/lib/python3.12/site-packages/tkb_core/__init__.py`; các lệnh chạy `python -I`, không dùng PYTHONPATH/source checkout để thay Core installed.

## Kiểm chứng đã chạy

| Kiểm tra | Kết quả |
|---|---|
| `uv run --extra solver pytest` | **232 passed**, 4.34s; thời gian test suite, không benchmark |
| Build wheel + sdist | PASS |
| Hai venv sạch; install từ requirements có hash và cùng Core wheel | PASS; `uv pip check` cả hai PASS |
| Mini input schema 1.1, 3 occurrences, đủ S01–S04, tiers 1/2/3 | CLI solve valid; output 1.2, solver_executed=true |
| Independent validate và score | PASS, recompute bằng declared score; vector **(1,1,2)** |
| No-solver CLI evaluate-score và validate-schedule | PASS, cùng vector |
| No-solver guard chặn OR-Tools/preprocessing/soft compiler/model builder/solver imports | PASS, evaluate-score vẫn OK |
| Ready registry S01–S04 | PASS, supported_modes=(soft,) tường minh |
| Pending rule có known parameter shape nhưng supported_modes=() | Capabilities, solve, score và validator đều từ chối; solver_executed=false, không assignments |
| Pending rule bị disable | Lịch tiny hợp lệ, quality NOT_REQUESTED, không áp preference |
| Malformed result | evaluate-score và validate-schedule trả INPUT_INVALID/exit2 |
| Stale result hợp contract | Cả hai CLI trả STALE_RESULT/exit2 |
| Khóa hai occurrences trùng lớp/GV/slot | INPUT_INVALID, solver_executed=false |
| Unknown custom hard và known rule yêu cầu hard mode | UNSUPPORTED_FEATURE, solver_executed=false |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests benchmarks` | PASS, 47 files |
| `uv run mypy` và `uv run mypy src/tkb_core benchmarks/generate_synthetic.py` | PASS, lần lượt 27 và 28 files |
| Diff Core/tests/generator/lock/pyproject | Không thay đổi |

Tổng **13 ca CLI** gồm 6 ca valid và 7 ca từ chối; registry/guard probes riêng. Full Core suite cũng bao phủ các regressions tương ứng. Không thêm test trùng implementation hoặc mã production vì đây là thao tác preflight trên APIs có sẵn.

Trong lần dựng probe đầu, stale fixture chỉ đổi outer fingerprint nên contract đã chặn bằng SCHEMA_VALIDATION_FAILED do fingerprint trong nested score không khớp. Đã sửa **dữ liệu thử** cho hai fingerprint nhất quán rồi xác nhận STALE_RESULT. Không sửa Core hoặc bỏ cổng validation để làm probe pass.

### Kiểm chứng bundle bằng installed Core

`verify-installed-bundle.py` nạp duy nhất tooling generator từ checkout qua importlib; Core được import trước và kiểm đường dẫn thuộc site-packages. Import guard chặn OR-Tools và solver/model builder trong suốt bước này.

- **27 feasible datasets**: witness trên input cuối hard-valid và evaluator score khớp manifest.
- BASE/MIXED: **18 datasets** vector zero, known optimum zero do penalty không âm.
- TIGHT: **9 datasets** witness P1=P3=0, **P2 ≥ lower bound** 60/120/240 theo quy mô. P2 witness thực nằm trong khoảng78–83 /158–166 /320–335 tương ứng10/20/40 lớp; **các witness này chưa đạt bound, không tuyên bố optimum attainable**.
- **9 UNSAT_CAPACITY**: valid input, demand30 > slots29, precheck INFEASIBLE; provenance witness thuộc BASE, không gán cho input vô nghiệm; không có baseline score của target.
- Mọi fingerprint, artifact SHA, source identity, dimensions và guard result khớp. Root manifest trước/sau không đổi. Không chạy search ở quy mô trường.

## Evidence và cách tái kiểm tra

Worktree: `.worktrees/phase2a-generator` trên branch **feature/phase2a-linux-preflight**; thư mục được tái sử dụng từ Task 1, không tự đổi tên hoặc xóa bundle/tài liệu đang giữ.

Evidence cục bộ (ignored): `benchmarks/artifacts/phase2a/preflight-linux-v1/`. Các file chính:

- `preflight-manifest.json`: status theo OS, hashes wheel/lock/bundle và SHA từng evidence file ngoài venv.
- `environment-solver.json`, `environment-no-solver.json`: package path, phiên bản thực, OS/CPU/RAM snapshot và source/wheel checks.
- `requirements-solver.txt`, `requirements-no-solver.txt`, `distribution/`: dependencies đã export và chính wheel đã dùng. Giữ wheel này nếu kiểm chứng Windows sau, không build lại rồi gọi là cùng wheel.
- `logs/core-pytest.txt`, `smoke-summary.json`, `smoke/*.stdout.json`, `smoke/*.stderr.txt`: test output, exit codes và stdout/stderr CLI.
- `registry-summary.json`, `no-solver-guard-score.json`, `bundle-verification.json`: kết quả API probes và danh sách36 input hashes/fingerprints.
- `installation-probe.py`, `smoke-checks.py`, `registry-probe.py`, `no-solver-guard.py`, `verify-installed-bundle.py`: one-off commands lưu làm bằng chứng tái lập, không thêm vào package hoặc benchmark runner.

Lệnh chính đã thực hiện từ worktree root (P là `benchmarks/artifacts/phase2a/preflight-linux-v1`):

```bash
uv sync --locked --extra solver
uv build --out-dir "$P/distribution"
uv export --locked --extra solver --no-dev --no-emit-project --format requirements.txt --output-file "$P/requirements-solver.txt"
uv export --locked --no-dev --no-emit-project --format requirements.txt --output-file "$P/requirements-no-solver.txt"
uv venv --python .venv/bin/python "$P/venv-solver"
uv venv --python .venv/bin/python "$P/venv-no-solver"
uv pip install --python "$P/venv-solver/bin/python" --require-hashes --only-binary :all: -r "$P/requirements-solver.txt"
uv pip install --python "$P/venv-no-solver/bin/python" --require-hashes --only-binary :all: -r "$P/requirements-no-solver.txt"
uv pip install --python "$P/venv-solver/bin/python" --no-deps "$P/distribution/vnedu_tkb_core-0.2.0-py3-none-any.whl[solver]"
uv pip install --python "$P/venv-no-solver/bin/python" --no-deps "$P/distribution/vnedu_tkb_core-0.2.0-py3-none-any.whl"
uv pip check --python "$P/venv-solver/bin/python"
uv pip check --python "$P/venv-no-solver/bin/python"
uv run --extra solver pytest
uv run python "$P/smoke-checks.py" "$PWD"
"$P/venv-solver/bin/python" -I "$P/installation-probe.py" "$PWD" solver
"$P/venv-no-solver/bin/python" -I "$P/installation-probe.py" "$PWD" no-solver
"$P/venv-solver/bin/python" -I "$P/registry-probe.py" "$PWD"
"$P/venv-no-solver/bin/python" -I "$P/no-solver-guard.py" "$P/smoke/input.json" "$P/smoke/result.json"
"$P/venv-solver/bin/python" -I "$P/verify-installed-bundle.py" "$PWD"
```

Lệnh ở trên chuẩn hóa path bằng P cho dễ đọc; transcript trong smoke-summary giữ argv thật. Các checks pass được xác nhận từ exit status + JSON/assertions, không chỉ dựa vào việc có file output. Không chạy lại vào cùng root để thay evidence cũ khi thực hiện đợt mới; chọn root mới.

## Quyết định và giới hạn

1. Tái sử dụng worktree đã cô lập, chuyển branch từ merged Task 1 sang Linux preflight; giữ nguyên dirty context/AGENTS/research/main. Chi phí: khi review/commit chỉ lấy report này và cập nhật kế hoạch.
2. Chạy thao tác preflight bằng existing APIs/tests và one-off evidence probes, không thêm permanent tooling/Core code. Chi phí: chưa có runner tự động hóa campaign; Task 3 còn nguyên.
3. Giữ root bundle gốc và source hashes; dùng installed Core để verify, không generate profile dễ hơn. Tiny solve chỉ để kiểm import/native backend/CLI/quality, không đại diện trường thật.
4. Windows BLOCKED và Task 2 overall PARTIAL; không giả Windows bằng WSL hoặc Linux cross-build. Chưa cross-validate results giữa OS.
5. Chưa kiểm peak memory native probe, watchdog, time-to-first-feasible, time/RAM/quality benchmark, headroom/power/workload và P/E topology. Không chứng minh Linux performance readiness hoặc deployment Windows.

Các hash chỉ kiểm integrity/tái lập, không phải chữ ký nguồn. Evidence ignored cần lưu kèm wheel/lock/bundle khi chuyển máy; git checkout chỉ chứa báo cáo/kế hoạch, không chứa venv hoặc raw artifacts. Báo cáo không phải kết quả nghiệm thu đầy đủ Task 2 hai OS.

## Review độc lập

Reviewer đã đối chiếu report với raw evidence và source: không Critical/Important findings. Một minor về câu mô tả lower bound đã được làm rõ trong báo cáo bằng dấu ≥ và ranges thực; không đổi evidence/Core hoặc chạy thêm search. Không có verdict Windows/performance. Reviewer không rerun probes/tests; bằng chứng thực thi do tác giả chạy và lưu ở các file đã nêu.

## Task 3 Linux — resource supervisor (triển khai sau Task 2)

**VERIFIED — Linux implementation/tests PASS**, sau lượt sửa Important findings từ review. **Windows BLOCKED; Task3 hai OS vẫn PARTIAL.** Không thực hiện Task4/5, campaign, tuning, benchmark hoặc2B/2C. Core/tree, dependency/lock và generator giữ nguyên.

### Files và APIs

- `benchmarks/run_benchmarks.py`: strict tooling contracts version1.0, `kib_to_bytes`, `supervise_linux`, `verify_cli_output`, `classify_run`, `run_cli_once`.
- `benchmarks/tests/test_run_benchmarks.py`:82 tests, gồm native Linux, fault injection và explicit installed-wheel tiny smoke.
- Cập nhật report này, Task3 checklist trong plan vận hành và execution checklist trong implementation plan; scope/plan đã viết trước vẫn giữ làm context.

Chỉ có helper cho **một run**; tên file theo kế hoạch nhưng chưa có command chạy matrix/campaign, resume/sweep hoặc aggregation. Không thêm Core API, CLI entrypoint, model adapter hoặc package dependency. Chưa commit/merge/push lượt này; worktree `phase2a-generator`, branch `feature/phase2a-task3-linux-supervisor`.

### Hành vi đã kiểm chứng

Một installed Python child trực tiếp qua `posix_spawn`, stdin `/dev/null`, stdout/stderr vào files bằng POSIX_SPAWN_OPEN. File actions OPEN thay DUP2/CLOSE vì regression cho parent đóng fd0/1 đã chứng minh cách DUP2 có thể trộn streams; regression mới pass. Output root mới tạo độc quyền, root/sentinel có sẵn giữ nguyên.

Chỉ owner `wait4(pid,WNOHANG)` reap. `waitid(...WNOWAIT)` chỉ kiểm child relationship trước signal, không reap; thiếu API → blocked. SIGINT được mask tạm trong critical interval spawn/reap, mask gốc truyền cho child và khôi phục parent; cả injection ngay sau spawn và SIGINT thật trong standalone driver đều cleanup/reap đúng, mask không đổi sau run.

Watchdog/resource stop đi qua TERM, grace1s và KILL nếu cần; RSS sampling mỗi50ms là best effort. Exit/status/signal, CPU và ru_maxrss được ghi riêng; `ru_maxrss*1024` là kernel peak bytes. Probe mất khi child vừa exit được recheck bằng wait4; probe thật lỗi giữ BLOCKED/null+reason cho phần thiếu. Không dùng peak tích lũy của tất cả children, không lấy RAM host/uv/parent làm metric thay thế.

Verification reuse CLI hiện có để kiểm hard/score/proof metadata; parser từ chối malformed/duplicate/nonfinite JSON, stale/version mismatch, stdout/result khác nhau, score/proof sai. Các payload giả mới trước hết **được ScheduleResult.model_validate xác nhận hợp schema**, sau đó vẫn bị CLI độc lập từ chối; không chỉ dựa vào schema rejection. Proof metadata chỉ được kiểm consistency, không tái chứng minh tối ưu bằng một file bên ngoài.

Identity lấy từ một captured byte buffer có hash đối chiếu expected sau runtime preflight, dùng chính buffer đó để parse/fingerprint; recheck trước spawn và trước/sau verification. Test thay A→B trong preflight rồi trả A ngay trước spawn bị chặn, không có record thành công gắn fingerprint B cho run A.

Harness status tách khỏi Core solver status. Native signal/unrecognized exit là CRASH, exit3/INFEASIBLE và4/UNKNOWN có payload hợp lệ là COMPLETE nhưng không có lịch hợp lệ. Stop/cancel/measurement failure không bật RunRecord.valid_schedule dù raw result có thể hard-valid. Evidence process/measurement/output đều giữ riêng khi nhiều lỗi đồng thời.

### Commands và kết quả thật

| Kiểm chứng | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS, không đổi lock |
| `TKB_PREFLIGHT_DIR=... timeout 120s uv run --extra solver pytest tests benchmarks/tests -q` | **352 passed,40.36s**;232 Core +38 generator +82 supervisor; installed smoke không SKIP |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests benchmarks` | PASS,49files |
| `uv run mypy` | PASS,27 Core files |
| `uv run mypy src/tkb_core benchmarks/generate_synthetic.py benchmarks/run_benchmarks.py` | PASS,29files |
| `uv build` | PASS; packaging test xác nhận benchmark tooling/research không vào wheel/sdist |
| Persistent installed-wheel tiny smoke | COMPLETE, hard-valid,4 rule scores, vector(1,1,2), kernel measurement OK |
| Recheck52 hashes của evidence Task2, lock và source/tree | PASS, không thay inputs/wheel/Core |

Các thời gian trên là thời gian chạy tests, **không phải benchmark**. Kernel RSS/CPU trong tiny-run là kiểm chứng phép đo, không đại diện hiệu năng trường thật. Không solve bất kỳ bộ10/20/40 lớp nào.

### Review, RED→GREEN và các lần gate chưa đạt

Một fresh independent reviewer đọc toàn bộ code/tests và nêu4 Important findings; không có Critical/Minor. Tác giả sửa trong một lượt và chạy lại suite:

1. Cleanup chưa bảo vệ đoạn initialization sau spawn: regression one-shot KeyboardInterrupt quan sát RED→GREEN, native SIGINT test pass.
2. Input identity TOCTOU giữa hash/read: regression A→B→A quan sát RED→GREEN; hash/parse nay dùng cùng checked snapshot.
3. Tests giả score/proof cũ chỉ sai schema: bổ sung2 regression hợp schema. Hai test mới pass với verifier hiện có; đây là coverage gap, không giả rằng production fix đã RED→GREEN.
4. RuntimeError lặp ở poll có thể bỏ qua signal và busy-loop: regression quan sát RED→GREEN; normal loop nhường cleanup ngay, không phụ thuộc một ordinary poll thành công khác.

Các checkpoint riêng trước review đã pass73 tests; suite tổng đầu tiên **1 failed,342 passed** vì test so RSS large/small chạy trong parent pytest nặng, hai kernel peaks đều156725248bytes. Đã đưa cả hai runs vào **cùng fresh lightweight parent**, không tăng cap hoặc trừ/đổi số kernel. **INFERRED:** RSS trước exec/lifetime baseline của parent có thể chi phối phép đo child; cần giữ parent supervisor nhẹ và luôn công bố method.

Một lượt tổng tiếp theo exit130 tại test SIGINT gửi vào shared pytest parent, trong khi test riêng pass. Đã cô lập ca SIGINT thật trong fresh standalone driver không load solver-native ở parent. Không sửa/override signal handlers của host hoặc thay đổi Core để làm test xanh. Nguyên nhân tương tác signal context/native libraries là suy luận, chưa quy kết thành lỗi OR-Tools. Supported execution là standalone parent kiểm chứng, không phải arbitrary long-lived host đã có custom/native signal handlers.

Final suite352 PASS là gate sau các sửa này. Review không được chạy lại sau fix; các fixes được kiểm chứng bằng regressions + suite xanh, không tự tuyên bố reviewer đã ký verdict mới.

### Evidence và giới hạn còn lại

- Final evidence: `benchmarks/artifacts/phase2a/task3-linux-v2/`, gồm `tiny-run/run.json`, stdout/stderr/result, installed-smoke driver/output và `logs/full-final-pytest.txt`. Source SHA trong tiny-run khớp code supervisor hiện tại.
- Giữ cả `task3-linux-v1/` và logs các gate chưa đạt; không xóa thất bại để làm đẹp kết quả. Frozen `task1-v1/` và `preflight-linux-v1/` giữ nguyên.
- Nếu wait4 backend hỏng vĩnh viễn, không thể chứng nhận đã reap. Sau stop attempts, record **BLOCKED/REAP_UNCONFIRMED**, không bịa peak/exit hay publish schedule, không spin vô hạn. Regression khôi phục native backend để test owner thu hồi child; trong tình huống thật có thể cần external recovery. Đây không phải cleanup-success claim.
- Khi mất ownership (ECHILD/PID mismatch), không signal PID không còn xác nhận. Không đo descendant tree, không hard memory cap, không bảo đảm cleanup khi parent bị SIGKILL hoặc kernel không đáp ứng. Sampling có thể bỏ lỡ spike.
- Windows/native Windows measurement, time-to-first-feasible và school-size latency/RAM/quality vẫn UNKNOWN/NOT_RUN. Chưa đáp ứng nghiệm thu hai OS hoặc pilot performance.

Các quyết định có tác động: OPEN file actions để tránh fd holes; WNOWAIT để kiểm ownership trước signal; mask SIGINT chỉ trong critical region; isolated lightweight/SIGINT drivers để kiểm đúng supported context; permanent-backend-failure được báo unconfirmed thay vì cam kết điều bất khả thi. Không có deferred minor; giới hạn reviewer chưa kiểm là execution/docs mới/Windows/performance, execution do tác giả chạy và lưu evidence, Windows/performance vẫn blocked/not run.
