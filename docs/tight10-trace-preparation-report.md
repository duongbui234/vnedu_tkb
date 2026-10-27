# TIGHT10 search trace — Task 1 preparation

**PREPARED_NOT_AUTHORIZED.** Đã triển khai prepare/instrumentation và kiểm thử không search; tạo candidate bằng installed-wheel interpreter. **Legacy gate BLOCKED_MACHINE_DRIFT**, chưa tạo authorization hoặc chạy Task2/solver/search/profiling. Windows BLOCKED.

## Phạm vi

Task1 của [kế hoạch trace](superpowers/plans/2026-10-27-tight10-search-trace.md), baseline `ec15c52`, nhánh `feature/phase2a-task5-linux-summary`. Thêm `benchmarks/trace_tight10.py` và tests riêng; không sửa Core,frozen runner/generator,uv.lock,config,site-packages hoặc historical artifacts.

- `prepare` chặn `CpSolver` trong toàn phần capture/build và legacy comparison; không cấp approval/acquire search lease hoặc spawn child.
- Capture dùng installed `_runtime_identity`/`_machine_identity`, cùng frozen input/witness/model/sources; tạo strict version1.0 candidate và report mới, không overwrite file/directory cũ.
- Instrumentation gọi lại `_run_stage` đúng một lần,priorityNone,budget60.0; chỉ logging fields khác normal stage. Guard trước solve so exact parameter snapshot và model hash. Tests dùng FakeSolver; native constructor bị chặn trong cả test suite chạy dưới đây.
- Driver `run`/private `_child` có authorization/current identity/root/run-ID/START/parent lease/admission guards và tái dùng owner/supervisor hiện có; các nhánh này chỉ kiểm bằng fake/no-search boundaries trong Task1. Không thực thi run/_child thật hoặc live native logging.
- UNKNOWN không schedule; feasibilityOPTIMAL không quality proof. Independent validator/scorer và exact model-expression comparison chặn publish schedule sai. Log error/missing response giữ incomplete/null+reason;0branches không suy presolve-only.

## Candidate baseline đã tạo

Path local trong worktree `.worktrees/phase2a-task5`:
`benchmarks/artifacts/phase2a/tight10-trace-prepare-v2/candidate-baseline.json`.

**Candidate SHA256:** `802f1f06ab5565d5b09c994fe1cb8c7044c8469096a2e130ce1be53ab9d77006`.

| Trường | Giá trị |
|---|---|
| Status | PREPARED_NOT_AUTHORIZED |
| Run ID dự kiến, chưa thực thi | tight10-trace-20261027-v2 |
| Driver SHA256 | `b9d430eedd169ca5c92e344be45eff3d2d6dac3969ce62d924c307af8a9838c8` |
| Input fingerprint kiểm build-only | `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee` |
| Compiled model SHA256 | `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083` |
| Runtime/input/witness/controller/generator/lock | Khớp legacy frozen identity/source hashes |
| Legacy gate | BLOCKED_MACHINE_DRIFT |
| Authorization/search/attempt directory | Chưa có/false/chưa có |

Sole differing field được báo là `machine.mem_total`:

| Frozen | Current trong installed interpreter | Delta |
|---|---|---:|
| `MemTotal:       40745240 kB` | `MemTotal:       40745236 kB` | −4KiB |

Không clamp/tolerance hoặc sửa seal/environment cũ. Legacy `_check_campaign_identity` được chạy thật trong installed environment và vẫn BLOCKED; candidate snapshot hiện tại không biến gate đó thànhPASS. Nguyên nhân MemTotal khác4KiB chưa được xác minh. Runtime/wheel/source mismatch khác sẽ chặn prepare thay vì tự rebaseline.

Options giữ60s/workers1/seed42; guards10,000slots/10,000occurrences/100,000placements/1,000,000occupancy terms; future watchdog150s/RSS target1GiB. Headroom/disk/lease là admission gate cần kiểm mới khi có run được duyệt, không được gọi là đã PASS từ prepare. Trace chỉ có thể được xem xét sau approval riêng gắn candidate hash,run-ID và đúng output root; drift mới tiếp tục bị chặn.

## Commands thực chạy và kết quả

| Lệnh | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS,lock không đổi |
| `uv run --extra solver pytest benchmarks/tests/test_trace_tight10.py -q` | **34passed,0.59s**; native constructor bị chặn, chỉ FakeSolver/FakeStage |
| Guarded `pytest.main` cho test_trace_tight10,test_campaign_linux,test_aggregate_linux | **121passed,38.21s**, constructor thật bị patch `NATIVE_SEARCH_FORBIDDEN`,assert_not_called PASS |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests benchmarks` | PASS54files |
| `uv run mypy` | PASS27Core files; benchmark module ngoài scope mypy hiện có |
| `git diff --check` | PASS |

Observed RED→GREEN: module chưa tồn tại; bổ sung regression giữ ownerNEEDS_REVIEW khi REAP_UNCONFIRMED và missing response fields null+reason đều fail trước sửa,pass sau sửa. Tests khác khóa policy/schema/drift,approval/lease/headroom/exclusivity,callback errors/patch restoration,multiple constructors,extra solver parameters,phase interpretation và independent mismatch.

Prepare cuối cùng (không search):

```sh
/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1/venv-solver/bin/python -I \
  /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/trace_tight10.py prepare \
  --root /home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-trace-prepare-v2 \
  --run-id tight10-trace-20261027-v2
```

Cả hai lần preparev1/v2 exit0,stderr rỗng; lệnh trên làv2. Stdout JSON ghi search_executed=false và authorization_created=false. Constructor thật bị chặn trong prepare; chỉ build/validate model,không solve/presolve/profiling. Guarded regression command dùng `unittest.mock.patch.object(cp_model,"CpSolver",side_effect=AssertionError("NATIVE_SEARCH_FORBIDDEN"))` quanh `pytest.main([...])`; không chạy installed-wheel solve hoặc full Core suite.439PASS trước đây vẫn là lịch sử,không có benchmark/trace native mới.

## Giới hạn bàn giao

Candidate/prepare report và logs là local ignored evidence,không commit generated data hoặc approval file. Chưa có trace.log,response native hoặc kết luận presolve/branching/root cause. Instrumentation trên native solver,signal/cleanup cùng trace child thực và chất lượng log thực vẫn chưa được kiểm trong Task1. Tests không search không thay live execution verification.

Không tự mở Task2. Một thay đổi driver/model/runtime/machine/options sau prepare làm candidate mất khớp; cần chuẩn bị snapshot mới theo policy thay vì sửa candidate cũ. Windows/current execution eligibility và MemTotal drift không được giải quyết bằng việc tests pass.

## Review và candidate cũ

Fresh reviewer rà driver/tests/plan/candidate và tự chạy32tests trước lượt sửa,phát hiện1P2: lỗi flush/close hoặc read log có thể thoát mà mất structured incomplete result. Đã thêm2regression giả quan sátRED→GREEN và sửa handler bao quanh logging lifecycle/read; response/parameters có sẵn được giữ lại,trace_complete=false và phaseUNDETERMINED. Sau sửa34tests riêngPASS;guarded regression121PASS/38.21s;ruff/format/mypyPASS. Không dispatch re-review sau lượt sửa duy nhất; dùng regressions và suite không search để kiểm chứng. Không có deferred findings khác; live native path vẫn chưa chạy.

Candidatev1 tại `tight10-trace-prepare-v1/`,hash `ca4817b0bc09447fc67cd4239002f49d7f2652a726290ed547f6d7f4dfde7a78`,được giữ nguyên. Nó freeze driver cũ nên **không còn khớp source hiện tại**,không dùng để duyệt execution. Không sửa status/hash trongv1 để giả còn hợp lệ; chỉ preparev2 mới phản ánh driver đã sửa. Candidatev2 cũng chưa được cấp quyền chạy; approval chỉ có thể được xem xét cho đúng hash/run-ID/output root của nó.

Kiểm chứng cuối: candidatev2/driver SHA khớp,không authorization/START/attempt trong cảv1/v2;107historical input/source/evidence hashes vẫn nguyên. Scope tracked chỉ new tooling/tests và docs,không Core/frozen runner/generator/lock. Thay đổi được giữ trên nhánh/worktree hiện tại,chưa merge/push.
