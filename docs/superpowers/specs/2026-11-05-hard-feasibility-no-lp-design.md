# Thiết kế thử cải thiện hard-only feasibility

Ngày 2026-11-05. **Thiết kế đã được người dùng duyệt; triển khai đang chờ duyệt
diff/commit. Chưa đo candidate trên pilot/campaign.** Phần mô tả dưới đây ghi
quyết định thiết kế; kết quả triển khai ở `docs/hard-feasibility-no-lp-commit-review.md`.
Không cho phép preflight/pilot/campaign, owner recovery hoặc commit/merge/push.

## 1. Quyết định đề xuất

Thử đúng một thay đổi search: đặt `linearization_level = 0` cho **native call
hard-only feasibility đầu tiên của public `solve` có quality, workers=1**.
Giữ nguyên mọi native parameter còn lại. Không áp cho expression verification,
zero probe, P1/P2/P3, legacy hard-only solve, workers>1 hoặc repair.

Đây là lựa chọn đã được người dùng duyệt để kiểm chứng; chưa có bằng chứng cải
thiện tốc độ. Không cam kết hết 30 UNKNOWN.

Theo [SatParameters của OR-Tools v9.15](https://github.com/google/or-tools/blob/v9.15/ortools/sat/sat_parameters.proto#L1456-L1460),
level 0 không dùng LP relaxation; mặc định là 1. Đây là thay đổi thuật toán tìm
kiếm, không phải bỏ hard linear constraints khỏi CpModelProto. Hiệu quả trên
dataset của dự án là giả thuyết cần đo; LP cũng có thể giúp propagation và việc
tắt nó có thể làm kết quả xấu hơn.

## 2. Bằng chứng và ranh giới suy luận

Source đang soạn: `120058e5a75d15c11280b126ac364684d5470605` trên main.
Source campaign: `86f624df1600f95f1222bc6c7e81f96b43e6c8e1`, trong worktree
`.worktrees/phase2-step-d-20261105-v1`.

Baseline là phần đã hoàn tất của `phase2-v2-linux-01`; không phải campaign PASS:

- 104/216 primary có terminal: 47 lịch hợp lệ, 30 UNKNOWN, 27 UNSAT đúng.
- 1 run dở dang khi người dùng tắt máy, 111 chưa bắt đầu. Không retry/resume.
- Plan SHA256 `02fc5ef6be90fd320bf46b5a9f0349f23849f2ce4bac56185c25e99c77bc1d6f`.
- Wheel SHA256 `cdd3428264bc92db0e5aadb2704cc277d46f405bebc7c062c6d0786abbda35d1`.
- OR-Tools `9.15.6755`; lock SHA256
  `fe404cb126bce893368517318d4982b5f7842990429467d2a793af066c2e4c3b`.

| Cỡ | UNKNOWN / known-feasible terminal SOFT | HARD |
|---|---:|---:|
| 10 | 0/14 | 0/12 |
| 20 | 5/12 | 9/13 |
| 40 | 5/14 | 11/12 |

VERIFIED từ trace của 30 UNKNOWN:

- Chỉ có call 1, priority null, mode default, không hint, trả native UNKNOWN.
- P1/P2/P3 NOT_RUN; chưa có incumbent để mất khi đổi tier.
- Budget c20/c40 lần lượt 120/180s; elapsed chỉ vượt khoảng 2–41 ms.
- Harness COMPLETE, measurement OK, không watchdog/resource stop; RSS 150–392 MiB.
- Response có 73.347–539.563 LP iterations; không có số thời gian riêng cho LP.
- 19 dataset tạo ra 30 UNKNOWN; 11 dataset có hai kết quả lặp đều UNKNOWN.
- TIGHT c20/c40 là 18/18 UNKNOWN. BASE/MIXED SOFT không UNKNOWN trong phần đã đo.
- Kiểm không-solver ở lượt phân tích trước: 47 lịch valid và score khớp; witness
  của cả 19 dataset UNKNOWN valid và score khớp manifest. Witness chỉ là oracle
  độc lập, không được đọc làm hint/đáp án trong child solver.

Lượt soạn này kiểm lại seal/plan, hash các file trong terminal receipts, số
104/30 và byte của objectives/cp_sat/model_builder giữa main và source đã đo:
khớp. Main có thêm Phase 3 repair/CLI; không được coi cả hai Core tree là một.
Journal thiếu TERMINAL đã biết vẫn là lỗi completion, không được sửa để aggregate.

INFERRED: LP có thể tốn công nhưng ít giúp tìm lịch đầu tiên trong các nhóm này.
Không chứng minh LP chiếm phần lớn runtime, rule S05/S06 gây lỗi, symmetry sai,
hay bug upstream. Trace summary không thay profiler/presolve/search timeline.

## 3. Các phương án đã cân nhắc

| Phương án | Tradeoff | Quyết định |
|---|---|---|
| Một feasibility call, linearization_level=0 | Thay đổi nhỏ, không chia budget hoặc thêm model; có thể mất propagation hữu ích | Chọn làm candidate đầu tiên |
| Chia budget thành default rồi no-LP/interleave | Có thêm cơ hội search nhưng phải chia deadline, xử lý nhiều raw status, khởi động/presolve lại | Chưa chọn; không thêm fallback trong candidate này |
| Heuristic dựng lịch/decision strategy từ input | Có thể phù hợp cấu trúc lịch hơn, nhưng phạm vi lớn: availability, duration, room, locks và hard variants | Chưa chọn; chỉ xem xét sau kết quả candidate |

Sửa tie-break incumbent hay P1/P2 không giải quyết đường UNKNOWN này. Không
đồng thời sửa model, symmetry, presolve, branching, seed hoặc workers để tránh
không biết thay đổi nào tạo hiệu ứng. Không dùng input ID/profile/cỡ làm selector.

## 4. Thiết kế thay đổi tối thiểu dự kiến

### Đường gọi

1. `solver/objectives.py`: mở rộng search mode nội bộ với `feasibility_no_lp`.
   `_stage_parameters` chỉ thêm `linearization_level=0` cho mode đó; các mode
   default/slice/interleave giữ nguyên dictionary hiện tại.
2. `run_quality` nhận keyword-only `initial_feasibility_search`, mặc định
   `default`, chỉ chấp nhận `default` hoặc `feasibility_no_lp` bằng type hint nội
   bộ. Chỉ call `measure(None, model=feasibility_model)` đầu tiên dùng mode này.
   `measure` có keyword search mặc định default; không suy ra mode từ priority
   null vì expression verification cũng có priority null.
3. `solver/cp_sat.py`: chỉ ở nhánh quality đang có active priorities, truyền
   `feasibility_no_lp` khi workers=1; trường hợp khác truyền/giữ default.
4. `repair/pipeline.py`: hai caller hiện tại không truyền keyword mới, tiếp tục
   default. Không dùng cờ public, environment override hoặc lựa chọn theo dataset.

Không thêm native call, không clone thêm model, không thêm hint trước feasibility.
Thứ tự vẫn là hard clone → feasibility → độc lập validate/score → expression
verification → các tier theo logic cũ. Giữ nguyên ngân sách monotonic dùng chung;
không bắt đầu stage mới nếu remaining <= 0 và không cấp lại toàn budget cho tier.

### Status và semantics bắt buộc giữ

- UNKNOWN đầu tiên: không assignments, không score, tiers NOT_RUN; không retry.
- INFEASIBLE là proof cho hard model đầy đủ; MODEL_INVALID không được che thành
  FEASIBLE/UNKNOWN. Không proof laundering từ restricted probe.
- Feasibility có nghiệm: validate/score độc lập trước khi dùng incumbent; later
  UNKNOWN giữ lịch đã kiểm theo logic hiện có. OPTIMAL ở bài satisfaction không
  chứng minh vector soft tối ưu; không tự freeze tier.
- Không đổi CpModelProto, placement domains, constraints, occupancy, ordering,
  hard semantics hoặc objective expressions. Cùng seed không bảo đảm cùng lịch
  sau đổi search; regression không đòi assignments/score bằng baseline từng byte.
- Không đổi schema, CLI, SolveOptions, registry/capabilities, lock hoặc pins.

### File dự kiến chạm khi được duyệt triển khai

| File/nhóm | Việc cần làm |
|---|---|
| `src/tkb_core/solver/objectives.py` | Mode nội bộ và chọn mode cho duy nhất call đầu |
| `src/tkb_core/solver/cp_sat.py` | Opt-in từ public quality solve single worker |
| `tests/unit/test_stage_parameters.py` | Exact parameter delta, các mode cũ không rò setting |
| `tests/unit/test_hard_feasibility_stage.py`, `test_quality_stages.py` | Fake-stage dispatch, statuses, incumbent, remaining budget |
| `tests/integration/test_hard_feasibility_native.py` | Native tiny tests và capture model/params tại biên solve |
| `tests/integration/test_repair_solver.py` hoặc test seam tương đương | Repair BEFORE/AFTER vẫn default |
| `docs/solver-design.md` | Cập nhật phạm vi, giả thuyết, giới hạn sau khi triển khai |

Không thêm fixture school-size: dùng input synthetic đã đóng băng cho phép đo;
regression nhỏ tái dùng fixtures và oracle hiện có. Trace wrapper hiện ghi đầy đủ
parameters/mode/response stats, không cần sửa harness v1/v2 để quan sát candidate.

## 5. Regression bắt buộc trước phép đo

1. **Parameter isolation:** no-LP chỉ khác default ở `linearization_level=0`.
   workers/seed/gaps/budget không đổi; slice giữ deterministic cap 12, interleave
   giữ setting cũ. Expression verification giữ fix-hint, không nhận no-LP.
2. **Dispatch bằng fake stages:** public quality workers1 opt-in; workers>1,
   legacy hard-only, cả hai repair order không opt-in. Chặn native solve trong
   fake tests để bảo đảm chúng không chạy solver ngầm.
3. **Budget/status:** clock fake cho first UNKNOWN/INFEASIBLE/MODEL_INVALID và
   first solved sát deadline; không thêm call, không cấp lại budget. Later
   UNKNOWN vẫn FEASIBLE với incumbent đã kiểm; tier metadata giữ đúng raw status.
4. **Model không đổi:** capture serialized hard CpModelProto ngay trước native
   call, so default/no-LP cùng input và cùng phiên bản source. Bytes giống nhau,
   objective rỗng, hint rỗng ở initial call; parameter chỉ khác đúng một field.
   So với proto trước compile_soft, không đòi trùng soft model đầy đủ.
5. **Semantics native tiny:** chạy feasible và UNSAT nhỏ với cả hai mode, bao
   gồm duration>1, rooms, locks và S02/S03/S05/S06. Cả hai giữ truth; mọi lịch
   native trả về được validator/evaluator độc lập kiểm. Không đòi cùng optimum
   soft khi native chưa có proof; tái dùng tiny oracle hiện có cho proof cases.
6. **Repair regression:** suite Phase 3 vẫn pass, default parameter path không
   đổi. Nếu test seam phát hiện keyword mới lan sang repair thì dừng sửa phạm vi.

Khi được duyệt triển khai, chạy đủ `uv sync --locked --extra solver`,
`uv run --extra solver pytest`, benchmark tests liên quan, `uv run ruff check .`,
`uv run ruff format --check src tests` (thêm benchmarks nếu có sửa tooling),
`uv run mypy`. Lượt thiết kế hiện tại không chạy các lệnh này hay native tests.

## 6. Phép kiểm pilot chẩn đoán hữu hạn — đề xuất, chưa được chạy

Đây là suite chẩn đoán ngoài primary, không sửa danh sách pilot/plan/gate v2.
Tối đa 6 public CLI solves, n=1/case, tuần tự, không baseline rerun, không retry.
Thứ tự và baseline được chốt trước khi xem kết quả candidate:

| Thứ tự | Dataset | Vai trò | Solver / watchdog / RSS |
|---|---|---|---|
| 1 | c10-base-s101-soft | Control đã có lịch | 60s / 150s / 1 GiB |
| 2 | c10-base-s101-hard | Control đã có lịch | 60s / 150s / 1 GiB |
| 3 | c20-tight-s101-soft | UNKNOWN, TIGHT không custom hard | 120s / 210s / 2 GiB |
| 4 | c20-base-s102-hard | UNKNOWN, BASE với custom hard | 120s / 210s / 2 GiB |
| 5 | c40-tight-s101-soft | UNKNOWN, TIGHT lớn | 180s / 270s / 4 GiB |
| 6 | c40-mixed-s103-hard | UNKNOWN, MIXED với custom hard | 180s / 270s / 4 GiB |

Input SHA256 tương ứng, để so bundle mới với input gốc:

```text
c10-base-s101-soft a53d4d10c014c3d240e5b759e5357bb86bed41945186f452d9fd1e7ad0eff1e6
c10-base-s101-hard 7df253dcde4e7fb3752fea8842f84b462aa685c23432ae92d44c09347f4d081c
c20-tight-s101-soft b4ce8df9182bebb3ad8268ffb73bfcaf104243c358f44c59d130966e33489c84
c20-base-s102-hard 62846a882dcd87e26617c1793ad921996cc873c0b6c9811e1a6c1db6ee783c66
c40-tight-s101-soft 7813b025cb49e98148e9563725b384af0002c2474b713e6f757245f87a8f039e
c40-mixed-s103-hard 84bf5d4026a29ea180f3e6b9373c2068e641db8da75efe221f8e26c2eca4e46b
```

### Gates trước và trong phép kiểm

- Cần ủy quyền mới cho product changes và cho phép kiểm này; duyệt thiết kế
  không tự mở solver. Không dùng candidate trên evidence campaign-01.
- Giữ campaign-01 kết thúc do tắt máy. Owner dùng chung trong common Git dir
  còn RUNNING: phải có recovery được duyệt riêng, xác minh không process/run
  đang hoạt động, lưu nguyên marker cũ và audit recovery. Không tự xóa/reset,
  không né bằng worktree/owner root khác. Gate này chưa giải quyết thì BLOCKED.
- Source candidate phải sạch và được định danh tại commit đã duyệt, như runbook
  D. Sau triển khai/regression phải trình diff để duyệt commit riêng trước
  preflight/pilot; không tự commit, giấu diff, hoặc bỏ Git-clean/HEAD gate.
- Sinh bundle mới và chạy installed-wheel preflight mới từ candidate, giữ nguyên
  generator/lock/OR-Tools. Kiểm selected input hashes như trên; manifest mới có
  source IDs mới, không sửa manifest cũ để giả khớp candidate.
- Dùng artifact driver mới trong evidence mới, import supervisor/trace,
  `run_phase2.run_cli_once` và `judge_case` hiện có. Giữ owner lock/headroom,
  installed runtime identity, worker1/seed42 và resource guards mặc định.
  Không gọi `execute_campaign --phase primary`, không sửa frozen plan.
- Reserve 2 GiB trước mỗi run; cần ít nhất 6 GiB effective headroom cho c40,
  Linux cgroup2, sạc điện, disk và các gate hiện có đều PASS.
- Deadline riêng phần 6-case diagnostic: **1.500s**, gồm admission, launch,
  verification và report, không gồm build/preflight; tổng watchdog 1.260s.
  Trước run mới, thiếu thời gian cho watchdog của nó cộng 60s cleanup/report
  thì dừng INCOMPLETE trước START. Deadline không reset budget native.
- Dừng ngay khi identity/integrity, resource/measurement hoặc H gate thất bại;
  UNKNOWN/không lịch/P NOT_MET cũng dừng suite chẩn đoán như pilot v2.
  Không retry/resume/tune sau khi thấy kết quả. Không tự chuyển lại default.

### Bảng diễn giải đã chốt

| Kết quả | Kết luận và bước xử lý |
|---|---|
| Gate thất bại hoặc run dở dang | BLOCKED/INCOMPLETE, giữ evidence; không đánh giá tốc độ, không chạy tiếp |
| Control mất lịch, H FAIL hoặc P NOT_MET | Candidate không qua pilot; dừng, không campaign |
| Case cũ UNKNOWN vẫn UNKNOWN | Candidate chưa đạt tiêu chí đề xuất; dừng, giữ nguyên budget |
| Đủ 6 lịch valid, H PASS/P MET | Tín hiệu cải thiện trên 4 case cũ UNKNOWN; chưa chứng minh tổng thể hoặc LP là root cause |
| Có lịch nhưng score kém witness/control | Q REVIEW_REQUIRED, báo vector; không đổi quality gate hoặc đòi zero |

Điều kiện đề nghị xem xét campaign mới: regression/preflight PASS, cả 6 case có
lịch valid, H PASS, P MET, identity/trace đúng, không resource failure. Đây là
tiêu chí chọn candidate cho diagnostic mới, **không thay gate campaign v2**.
Ngay cả khi đạt, campaign mới vẫn cần người dùng duyệt riêng; không mở tự động.

Báo cáo phép kiểm phải ghi raw status, mode, parameter delta, model/hint counts,
feasibility time, remaining budget, từng native call, response stats, native và
sampled RSS, launch-to-exit, independent validity/score, H/Q/P/zero, đối chiếu
baseline đúng input. So sánh lịch sử là quan sát không đồng thời, không phải
A/B có kiểm soát hay bằng chứng thống kê; n=1 không suy ra SLA/P95.

## 7. Kết quả của lượt soạn thiết kế (trước triển khai)

Đã thực hiện: đọc caller/tests/trace, kiểm receipt/hash không-solver, đối chiếu
source measured/current và tài liệu parameter upstream. Chỉ thêm tài liệu này.
Chưa thực hiện: product changes, regression/native tests, build/install/preflight,
pilot, campaign, owner recovery hoặc bất kỳ commit/merge/push nào.
