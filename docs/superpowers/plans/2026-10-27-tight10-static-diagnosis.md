# TIGHT10 — Minimal Static Diagnostic Plan

> **For agentic workers:** Khi người dùng yêu cầu thực hiện kế hoạch này, dùng `superpowers:executing-plans`. Lượt hiện tại chỉ lập kế hoạch và kiểm tra tĩnh để xác định baseline; các checkbox bên dưới là công việc chưa thực hiện. Không tự chuyển sang search/profiling hoặc sửa thuật toán.

**Goal:** Khoanh vùng UNKNOWN của `c10-tight-s101` giữa dữ liệu/domain, hard model và auxiliary soft encoding, trước khi cân nhắc đo search riêng.

**Architecture:** Frozen input+witness+3raw results → independent validator/scorer và `prepare` → đối chiếu hard occupancy → kiểm cấu trúc model/soft bounds bằng build-only ở bước được yêu cầu sau. Chỉ dùng one-off probe có asserts và JSON evidence ngoài package; không tạo framework chẩn đoán hoặc sửa Scheduling Core.

**Tech Stack:** Python3.12, Core hiện tại, Pydantic2.14.1; OR-Tools9.15.6755 chỉ được import ở bước build-only tương lai, không khởi tạo `CpSolver` hoặc gọi solve.

**Spec:** [Core First, mục4–6 và9](../../VNEDU_TKB_CORE_FIRST_CODEX.md), [Phase2A](../specs/2026-10-26-phase-2-quality-design.md), [Task5 Linux](../../phase-2a-task5-linux-report.md).

## Global Constraints

- Nhánh `feature/phase2a-task5-linux-summary`, baseline `fd03070`. Lượt lập kế hoạch chỉ thêm tài liệu và evidence tĩnh ignored; không đổi source/tests/config/dependency/uv.lock hoặc research.
- Không chạy `solve`, `_run_stage`, `run_quality`, CLI solve, campaign prepare/warmup/pilot/primary, callback, profiler, presolve/search riêng hoặc hint experiment. Không regenerate input/witness; không thay metadata lịch sử.
- Giữ options lịch sử60s/workers1/seed42; watchdog150s/RSS1GiB và guards hiện tại. Không nới budget hoặc thêm2B/2C/repair/UI/API.
- Đây là dữ liệu synthetic; không suy chính sách trường từ domain hoặc witness. Không gọi API/đọc dữ liệu thật.
- Windows BLOCKED. Machine drift4KiB MemTotal từ audit trước vẫn chưa giải thích; static audit không mở execution gate. Search/profiling mới cần yêu cầu và execution policy riêng.
- Hashes/receipts là consistency evidence local, không chứng chỉ chống chỉnh sửa có chủ đích. `READY`/domain không rỗng không chứng minh feasibility; witness hợp lệ mới là bằng chứng có lịch cho đúng input.

## Baseline đã kiểm trong lượt lập kế hoạch

### Identity và phạm vi kiểm tra

Campaign `linux-pilot-20261027-v1`, plan SHA256 `6b8a324560b1857555f686a955f5af79468e5f80a00d830466b9253e648a9e61`.

Dataset root (local, không commit raw):
`/home/ddevtk/code/vnedu_tkb/.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/task1-v1/c10-tight-s101/`.

| Identity | Giá trị |
|---|---|
| Input fingerprint | `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee` |
| input.json SHA256 | `7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735` |
| witness.json SHA256 | `f9b5274529c9d1bd4d4c301b2626336bd0128b38b57901b90627ca4be1121a57` |
| manifest.json SHA256 | `901cc5860091d7499733a3e3d0a1a6864bc2dbbe228772f95adac66b0266a804` |

Đã kiểm seal→plan, manifest/input/witness hashes, fingerprint và3receipts của TIGHT101; cùng các kiểm tra tương ứng cho BASE101/MIXED101 làm bối cảnh. Không kiểm lại toàn684file inventory trong lượt này; Task5 đã ghi lần kiểm đó.

### Witness và domains

- Independent hard validator PASS; scorer OK, khớp baseline `(0,78,0)`. Đây không phải optimum proof; P2 lower bound60 khi P1=0 chưa được chứng minh attainable.
- 260assignments =220single+40double, tổng300tiết; 260/260 có **đúng một** placement khớp occurrence/start_slot/room trong `prepare`. Toàn footprint duration và resource/token occupancy của witness khớp, không collision.
- Precheck READY; 4,386placements/10,231occupancy terms, dưới guards100,000/1,000,000. Domain sizes1–48,44occurrences có một placement và8có hai placements. Có52time locks, trong đó1time+room lock; không đồng nhất52locks với52singleton vì room alternatives còn có thể tồn tại.
- Mỗi lớp demand30/32available slots; mỗi GV demand18–23, availability đúng demand+2. Đây là slack theo slots, không là số lựa chọn độc lập hoặc chứng minh nguyên nhân khó.
- Đối chiếu trực tiếp fixed resource/token locks thấy1,442/4,386placements xung đột với locks của occurrence khác; sau bỏ chúng trong phép tính tĩnh còn2,944placements, không domain nào rỗng. **Không sửa `PreparedProblem` hoặc model.** Đây không phải presolve measurement: CP-SAT có thể đã loại chúng tự động, nên không kết luận pruning thủ công sẽ nhanh hơn.

| Dataset riêng | Placements | Locks | Class slots | GV availability | Feasibility solver wall3repeats (s) |
|---|---:|---:|---:|---|---|
| c10-base-s101 | 15,120 | 0 | 60 | 60 | 6.562 /5.452 /5.066, raw OPTIMAL |
| c10-mixed-s101 | 6,797 | 26 | 42 | 36 | 3.701 /3.108 /3.142, raw OPTIMAL |
| c10-tight-s101 | 4,386 | 52 | 32 | demand+2 | 60.001 /60.002 /60.001, raw UNKNOWN |

Không pooling latency hoặc score giữa3fingerprints. BASE/MIXED khác TIGHT đồng thời ở availability, locks, calendar/room scope và soft parameters; đây không phải thí nghiệm một biến. Ít placements hơn không bảo đảm tìm nghiệm nhanh hơn.

### Stage metadata và đường đi source

| Repeat TIGHT101 | Feasibility solver wall (s) | Core wall (s) | Launch→exit (s) | Status |
|---|---:|---:|---:|---|
| 1 | 60.001373317 | 60.570369095 | 60.970566616 | UNKNOWN |
| 2 | 60.002091255 | 60.522405356 | 60.879143864 | UNKNOWN |
| 3 | 60.001277716 | 60.529675074 | 60.895198964 | UNKNOWN |

Cả3:solver_executed=true,quality NOT_EVALUATED,score=null,optimal_prefix=[],P1/P2/P3 NOT_RUN,stderr0bytes; không có branch/conflict/presolve trace. Đây là wall time của toàn feasibility call, **không phải TTF** hoặc riêng search time. Hết60s không phân biệt thời gian presolve với branching.

Source trace đã đọc:

1. `preprocessing/normalize.py::normalize` revalidate/capabilities/tokens → `preprocessing/feasibility.py::prepare` domains/necessary capacity checks.
2. `solver/model_builder.py::build_model`: ExactlyOne/occurrence; `constraints/hard.py::add_occupancy`: AtMostOne/resource/token, dùng đủ duration và room.
3. `solver/cp_sat.py:163` gọi `compile_soft` **trước** `run_quality`; `constraints/soft.py:149` thêm exact max-equalities và raw equalities/bounds.
4. `solver/objectives.py:52`: feasibility chỉ `clear_objective()`, không gỡ auxiliary soft constraints. `run_quality` tính budget theo elapsed stage; UNKNOWN đầu tiên không có incumbent nên trả UNKNOWN và không chạy tier sau.
5. Witness chỉ được dùng ở tooling/validator, không có `add_hint` trong solver path đã đọc. Không suy việc chưa dùng witness là nguyên nhân UNKNOWN hoặc phải thêm hint.

**Giới hạn đã khoanh:** không thấy witness mất khỏi candidate domains, lỗi hard occupancy của witness hoặc resource guard chặn ở preprocessing trên mẫu này. Chưa kiểm witness thỏa **toàn bộ mô hình CP-SAT sau compile**; independent validator và candidate membership không đủ loại trừ lỗi encoding. Dữ liệu hiện tại chưa chỉ ra nguyên nhân gốc trong solver.

## Giả thuyết có thứ tự và phép phân biệt

| Ưu tiên | Giả thuyết, chưa kết luận | Kiểm chứng tối thiểu tiếp theo | Điều không được suy |
|---|---|---|---|
| 1 | Hard/compiler encoding hoặc bound không bảo toàn witness dù domain/validator đúng | Build-only, đối chiếu selected Boolean mapping, hard buckets và per-rule upper bounds với witness | `model.validate()==""` chỉ là structural validation, không chứng minh witness thỏa model |
| 2 | Availability+locks+blocks/phòng tạo bài tìm nghiệm khó | Nếu bước1không phát hiện mismatch: giữ các domain/lock/slack facts và ghi cần dữ liệu search riêng |1,442candidate xung đột lock không chứng minh presolve kém; không gỡ lock/giảm profile để thử |
| 3 | Auxiliary soft constraints ảnh hưởng feasibility dù objective rỗng | Đếm cấu trúc trước/sau compile, kiểm raw/weighted/tier bounds; giữ H2/H3 UNKNOWN nếu chỉ có counts | Không vô hiệu soft rồi gọi là cùng fingerprint; không suy constraint count là runtime |

Symmetry, presolve, branching và tác động hint chỉ là câu hỏi chưa có trace; không lập benchmark matrix, chọn fix hay đổi kiến trúc ở kế hoạch này.

## Review Focus

- Witness/manifest/input khác fingerprint hoặc source thay đổi phải dừng, không tự regenerate.
- Double/time-only lock phải giữ room alternatives và full token footprint, không đếm một khóa là một Boolean.
- `clear_objective` không xóa compiled equalities; positive penalty78 hợp lệ và không được ép về0.
- Structural validity/bounds đúng không loại trừ mọi compiler bug hoặc chứng minh hiệu năng.
- Không gọi solver từ helper, test hoặc CLI gián tiếp; evidence thiếu vẫn UNKNOWN, không tự chạy để lấp khoảng trống.

## Task 1 — Kiểm build-only witness/bounds, đã kiểm build-only

**Files:** Đọc các source paths ở trace; không sửa chúng. One-off probe ở scratch ignored; tạo local `benchmarks/artifacts/phase2a/tight10-static-v1/` mới và `docs/tight10-static-diagnostic-report.md`. Không thêm CLI, module hoặc dependency.

**Interfaces:** Consumes frozen `ScheduleInput`, `SolveOptions`, witness assignments, `prepare(problem, options) -> PreparedProblem`, `build_model(prepared) -> BuiltModel`, `compile_soft(prepared, built) -> CompiledSoft`, `evaluate_score(problem, assignments) -> ScoreReport`. Produces JSON evidence về mapping/counts/bounds và Markdown kết luận có giới hạn.

- [x] **1. Khóa baseline:** kiểm branch/source hashes/input/witness/manifest/3receipts như identity trên; xác nhận260domain members,score(0,78,0),durations và occupancy. Đối chiếu baseline tĩnh đã có, không lặp campaign. Mismatch→dừng và báo cụ thể, không chỉnh input.
- [x] **2. Cấm search trong probe:** patch `ortools.sat.python.cp_model.CpSolver` để mọi constructor call raise `AssertionError("SEARCH_FORBIDDEN")`. Không import/call `solve`, `_run_stage` hoặc `run_quality`. Không timer, profiler, solver status mới hoặc thay options. Probe chỉ có asserts, không cần chạy regression suite có solve.
- [x] **3. Dựng hard model:** `build_model(prepared)`; assert260variable-tuples và4,386Boolean choices; mapping witness chọn đúng1Boolean/occurrence và sum trong mỗi resource/token bucket≤1. Lưu `model.validate()` và `model.model_stats()` trước compile. API hai hàm đã được đối chiếu với source package9.15.6755 đang cài; không phải lệnh solve.
- [x] **4. Đối chiếu compiler bounds:** compile một lần trên hard model này; assert60rules với đủ4families×15GV, active tiers1/2/3. Với từng rule so independent `raw_penalty ≤ raw_upper_bound`, `weighted_penalty ≤ weighted_upper_bound`; từng tier so score≤`upper_bounds[priority]`. Không ép equality với bound, không ép penalty78=0. Lưu validation/model_stats sau compile rồi `clear_objective()` theo feasibility path; kiểm objective rỗng. Đối chiếu domains trước/sau không đổi.
- [x] **5. Báo kết quả:** lưu snapshot hashes, từng assert/violation, source identity và evidence của cả3repeats; báo riêng structural validation, witness/domain, hard bucket check, auxiliary-bound check. Nếu phát hiện mismatch: chỉ chỉ ra rule/occurrence/resource liên quan, chưa sửa Core. Nếu tất cảpass: ghi **chưa xác nhận witness thỏa mọi compiled equality**, không tuyên bố lỗi compiler đã được loại trừ hoặc nguyên nhân đã rõ. Không tự viết generic CP-SAT proto evaluator để lấp giới hạn này.

**Expected:** No solve calls; raw artifacts/source/lock không đổi. Có static report đủ để quyết định có cần phép kiểm sâu hơn về compiled expressions hay một yêu cầu search trace riêng. Không có cam kết phải tìm được nguyên nhân từ static evidence.

## Task 2 — Chốt hướng điều tra, chưa thực hiện

**Files:** Chỉ bổ sung `docs/tight10-static-diagnostic-report.md`; không code change.

- [ ] Xếp kết quả vào một trong ba nhánh: identity/witness mismatch; model/bound mismatch cụ thể; hoặc static checks pass nhưng nguyên nhân UNKNOWN còn mở.
- [ ] Chỉ đề xuất **một** bước tiếp theo từ bằng chứng mới. Mismatch cần testcase trước fix; nếu cần search trace thì lập yêu cầu riêng giữ60s/workers1/seed42, xử lý execution identity gate, output mới và ghi instrumentation/measurement method trước chạy. Kế hoạch hiện tại không cho phép thực hiện bước đó.

## Kiểm chứng lượt lập kế hoạch và giới hạn

Đã chạy Git branch/status/log; đọc Core First/source/spec/Task5; one-off Python hash/receipt checks, independent hard/score, `prepare` và witness/domain/token checks cho3datasets; assert không module `ortools` nào được import. Không build model/compile soft, không search/profiling hoặc đo thời gian mới. Artifact:
`benchmarks/artifacts/phase2a/tight10-diagnostic-plan-v1/planning-evidence.json`, SHA256 `1907e2afb7448f34427099d55f460349f33b39d6d16d8ee14a93760ddbbc94cf` trong worktree Task5.

Đây là self-check tĩnh có asserts, không phải pytest regression hoặc benchmark mới. Full pytest không chạy lại vì chỉ thay tài liệu và suite có solve;439PASS của Task5 là lịch sử. Các kiểm tra tài liệu/tooling thực chạy được ghi bổ sung khi hoàn tất; không suy tests/source correctness mới từ kế hoạch.

Kiểm tra cuối đã chạy trong lượt này: `uv sync --locked --extra solver` PASS/lock không đổi; `uv run ruff check .` PASS; `uv run ruff format --check src tests` PASS44files; `uv run mypy` PASS27source files; `git diff --check` PASS. Self-review xác nhận links tồn tại, current generator/Core/lock source hashes khớp frozen manifest và60soft rules đúng kỳ vọng; diff chỉ tài liệu. Không chạy pytest, build/compile hoặc solver; không có kết luận root cause/performance mới.

## Ghi nhận thực hiện Task1 — 2026-10-27

Người dùng đã yêu cầu chỉ Task1 build-only. Witness mapping260/260, hard proto260ExactlyOne+681AtMostOne, independent score(0,78,0) và60rule bounds PASS. Model sau compile có4,700variables/1,255constraints; structural validation rỗng và objective không có. Không có CpSolver constructor calls/search/profiling hoặc đổi Core/budget. [Báo cáo Task1 và evidence](../../tight10-static-diagnostic-report.md). **Chưa kiểm mọi compiled equality; nguyên nhân UNKNOWN còn mở. Task2 vẫn chưa thực hiện.** Các câu “chỉ lập kế hoạch” ở đầu tài liệu mô tả lượt lập kế hoạch trước đó.
