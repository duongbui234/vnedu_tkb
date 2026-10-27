# TIGHT10 — witness, hard model và compiled auxiliaries

**Cập nhật mới nhất: witness mở rộng thỏa 4,700variable domains và toàn1,255constraints của đúng model `c10-tight-s101`; score khớp độc lập(0,78,0). Không có search/profiling hoặc solver status mới; nguyên nhân UNKNOWN còn mở, Windows BLOCKED. Task1/Task2 phía dưới là lịch sử; kết quả kiểm auxiliary ở phần cuối.**

## Phạm vi và identity

Thực hiện chỉ Task1 của [kế hoạch chẩn đoán tĩnh](superpowers/plans/2026-10-27-tight10-static-diagnosis.md), trên nhánh `feature/phase2a-task5-linux-summary`, HEAD trước probe `cbde2450fe7a5c4cc53aadb68011adde926fb2e9`. Probe one-off và asserts được giữ ngoài package trong evidence ignored; không tạo module/CLI/tests sản phẩm hoặc sửa Core/dependencies.

- Campaign lịch sử `linux-pilot-20261027-v1`, plan SHA256 `6b8a324560b1857555f686a955f5af79468e5f80a00d830466b9253e648a9e61`; chỉ3primary receipts của `c10-tight-s101` được kiểm lại, không gọi campaign execution.
- Fingerprint `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee`.
- input.json SHA256 `7d023d04f762aac06a237f48c7e05e462e54de62c928be7ecd91d3c3a36c8735`; witness.json SHA256 `f9b5274529c9d1bd4d4c301b2626336bd0128b38b57901b90627ca4be1121a57`; manifest.json SHA256 `901cc5860091d7499733a3e3d0a1a6864bc2dbbe228772f95adac66b0266a804`.
- Current Core/generator/uv.lock hashes khớp frozen manifest; seal/plan/environment và input/witness hashes khớp. OR-Tools9.15.6755.
- Options giữ60s/workers1/seed42, guards10,000slots/10,000occurrences/100,000placements/1,000,000occupancy terms; watchdog150s và RSS target1GiB chỉ được đọc, không áp dụng cho execution mới.
- Hash trước/sau xác nhận **26raw files và65tracked source/test/tooling/config files** không đổi. Không kiểm lại toàn684file inventory của Task5 hoặc runtime/máy hiện tại.

## Cấm search và cách thực hiện

Probe patch `ortools.sat.python.cp_model.CpSolver` bằng mock với `side_effect=AssertionError("SEARCH_FORBIDDEN")` trước import helpers và dựng model; số lần constructor bị gọi bằng0. Không import solver entry module `tkb_core.solver.cp_sat` hoặc `tkb_core.solver.objectives`; không gọi solve, run_quality, _run_stage, CLI solve, presolve, callback, profiler hoặc hint. Không dùng timer hoặc phát sinh phép đo hiệu năng.

Chỉ gọi `prepare`, `build_model`, `compile_soft`, independent validator/scorer, `model.validate()` và `model.model_stats()`. Hai hàm model cuối chỉ structural validation/thống kê cấu trúc, không chạy solver. Compile đúng một lần trong probe thành công; không minimize/maximize hoặc thêm constraints để ép witness/penalty.

Hai lần probe trước chưa hoàn tất được giữ logs: lần đầu thiếu repo root trên `sys.path`, dừng trước build; lần sau pybind repeated constraints không hỗ trợ slice, dừng sau compile. Sửa riêng import path và truy cập constraints bằng integer indices trong script tạm rồi chạy build-only lại với output directory mới. Không phải solver failures; không sửa model/Core/limits để qua kiểm tra. Bản evidence thành công không ghi đè hai lần chưa hoàn tất.

## Witness mapping và hard model

Independent hard validator PASS; independent scorer OK, đúng baseline `(0,78,0)`. Đủ260occurrences/assignments, gồm220single và40double =300tiết. Từng witness assignment khớp đúng một placement theo occurrence/start/room; mapped vào một Boolean đã chọn, các Boolean khác bằng0.

| Phép kiểm | Kết quả |
|---|---|
| Domain mapping | 260/260 khớp; full footprint duration được giữ |
| Placement variables | 260tuples,4,386Boolean variables; variable domains đều[0,1] |
| ExactlyOne thực trong hard proto | 260/260 thỏa witness; membership khớp tuples của builder |
| AtMostOne thực trong hard proto | 681/681 thỏa witness; membership khớp index resource/token |
| Resource/token buckets dựng từ domains | 683buckets:306class,317teacher,60room; mỗi bucket selected_sum≤1 |
| Occupancy terms | 10,231;683buckets có2singleton buckets nên681AtMostOne có10,229literals |
| Selected resource/token sums | 634 =300class+300teacher+34room; không collision |
| Locks | 52; independent validator kiểm locks và domain vẫn giữ room alternatives hợp lệ |
| Structural validation hard model | `model.validate()==""` |

Probe không chỉ tính occupancy từ lịch riêng: đã đối chiếu **actual hard proto constraints** với index resource/token và đánh giá các literal ExactlyOne/AtMostOne trên selected Boolean mapping. Không có enforcement literals, negative literals hoặc hard constraint type ngoài hai loại trên trong model này. Đây là kiểm chứng hard Boolean assignment cho đúng bài mẫu, không là generic CP-SAT evaluator.

## Compiler bounds và cấu trúc sau compile

Compile60rules =15GV×4families S01–S04, active priorities1/2/3. Đối chiếu từng rule_id/priority với independent score; **60/60 raw penalties và60/60 weighted penalties đều không vượt corresponding upper bounds**. JSON giữ đủ từng rule, không suy bound đúng trên mọi lịch từ một witness.

| Tier | Witness value | Compiled upper bound | Check |
|---|---:|---:|---|
| P1 | 0 | 2,035 | PASS |
| P2 | 78 | 1,194 | PASS |
| P3 | 0 | 18 | PASS |

P2=78 là penalty hợp lệ, không ép về0 hoặc bằng bound. Đây là **upper bounds** do compiler công bố; không đổi chúng thành lower bound/proof. Conditional P2 lower bound60 của manifest không được kiểm attainable trong Task1.

| Cấu trúc | Hard model | Sau compile / sau clear_objective |
|---|---:|---:|
| Variables | 4,386 | 4,700 |
| Constraints tổng | 941 | 1,255 |
| ExactlyOne | 260 | 260 |
| AtMostOne | 681 | 681 |
| LinMax | 0 | 254 |
| Linear equality | 0 | 60 |
| Objective hiện diện | Không | Không |
| Structural validation | Chuỗi rỗng | Chuỗi rỗng cả trước/sau clear |

Thêm314auxiliary variables và314constraints (254max-equalities+60raw equalities). Hard constraints giữ nguyên text/order và membership; domains giữ nguyên toàn bộ sau compile. `compile_soft` không đặt objective; sau `clear_objective()` objective tiếp tục rỗng, số biến/ràng buộc không đổi. Không có bằng chứng runtime hoặc nguyên nhân UNKNOWN từ các số đếm này.

**Giới hạn bắt buộc:** structural validation chỉ kiểm model hợp lệ về cấu trúc, không chứng minh feasibility. Việc witness thỏa hard model và penalties nằm trong declared bounds **chưa xác nhận witness thỏa mọi compiled equality/max relation**. Task1 không đánh giá auxiliary assignments hoặc xây generic proto evaluator, không tuyên bố đã loại trừ mọi compiler bug.

## Đối chiếu metadata lịch sử

Cả3receipts/hash, input identity, options/limits đều khớp; raw UNKNOWN, solver_executed=true, quality NOT_EVALUATED, score=null, mọi quality tier NOT_RUN. Không sửa hoặc đổi tên statuses thành kết quả probe.

| Repeat | Feasibility wall lịch sử (s) | Tier P1/P2/P3 |
|---|---:|---|
| 1 | 60.001373317 | NOT_RUN/NOT_RUN/NOT_RUN |
| 2 | 60.002091255 | NOT_RUN/NOT_RUN/NOT_RUN |
| 3 | 60.001277716 | NOT_RUN/NOT_RUN/NOT_RUN |

Đây là số lịch sử trong result files, không số đo mới, TTF hoặc thời gian riêng search. Không có branch/conflict/presolve trace để kết luận cơ chế nào gây UNKNOWN. Không chạy search để lấp dữ liệu thiếu.

## Evidence, lệnh thực tế và kiểm chứng

Evidence local tại `.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-static-v1/`:

- `probe.py`, stdout/stderr và logs hai lần chưa hoàn tất; `execution-manifest.json` bảo toàn hashes.
- `summary.json`: SHA256 `45ee0ab14b070450dfcca6a6f9529e749f76a086b2215a1ed9141276dc7b6411`.
- `probe.py`: SHA256 `6c2a9c2bb212360a69c48e71f105fb001bed9ef6b3bc9c4931a230708d73392e`.
- `witness-mapping.json`:260mapping records; `hard-buckets.json`:683buckets cùng selected sums và variable membership; `rule-bounds.json`:60per-rule score/bounds; `historical-stages.json`:3receipts/stages; `protected-hashes.json`:raw/source snapshots.
- `hard-model-stats.txt`, `compiled-model-stats.txt`, `cleared-model-stats.txt`, artifact manifest. Raw inputs/results vẫn ở frozen paths trong plan, không copy vào package hoặc commit.

| Lệnh | Kết quả thực tế |
|---|---|
| `uv sync --locked --extra solver` | PASS; lock không đổi |
| `uv run --extra solver python .superpowers/sdd/2026-10-27-tight10-static-diagnosis/probe.py` | Probe cuối exit0, asserts PASS; hai attempts chưa hoàn tất ghi rõ ở trên |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` | PASS44files |
| `uv run mypy` | PASS27source files; scope mypy hiện tại chỉ Core |

Đây là assert-based one-off diagnostic, không phải tests cho production change. **Không chạy `uv run --extra solver pytest`** vì suite chứa solve và yêu cầu hiện tại cấm search;439PASS của Task5 là lịch sử, không trình bày như chạy lại. Không build wheel, đo benchmark, thay Core/controller/generator/AGENTS/dependency hoặc mở2B/2C.

Chỉ ghi kết quả các phép kiểm Task1; Task2 chốt hướng điều tra chưa được thực hiện. Kết quả không mở execution gate, không giải thích machine drift4KiB hoặc xác nhận Windows/current runtime readiness.

### Kiểm chứng cuối và review

Đã đối chiếu lại15hashes trong execution manifest,260mapping records,683buckets,60rule bounds và các snapshot26raw/65tracked files bằng script read-only có asserts; tất cảPASS. Các links của report/plan tồn tại; `git diff --check` PASS. Ruff/format/mypy được chạy lại và vẫnPASS; không gọi lại build/search khi kiểm evidence.

Fresh reviewer kết luận không actionable findings trong Task1. Reviewer đọc probe và connected builder/compiler/helper paths; tự kiểm hashes,26raw/65tracked snapshots, counts, per-rule/tier bounds,3historical statuses và model stats. Reviewer không rerun probe/build, tests hoặc search/profiling; kết quả guard/log là evidence trong workflow local, không phải phép chứng minh độc lập về mọi hoạt động quá khứ. Không có Critical/Important/Minor cần sửa hoặc deferred findings.

Hai rulings về phạm vi: dùng asserts/build-only thay full pytest vì lệnh cấm search của người dùng; chỉ kiểm actual hard Boolean constraints và auxiliary bounds, không thêm generic proto evaluator. Hệ quả: không có regression suite mới hoặc xác nhận toàn bộ auxiliary equalities. Giữ nhánh/worktree để review; chưa merge/push và chưa thực hiện Task2.

## Task 2 — Tổng hợp evidence và chốt một bước điều tra tiếp theo

**Đã thực hiện phần tổng hợp Task2 trên nhánh `feature/phase2a-task5-linux-summary`, baseline `790d4b9`.** Các câu “Task2 chưa thực hiện” ở phần Task1 phía trên và trong artifacts là snapshot lịch sử tại thời điểm Task1; raw evidence được giữ nguyên.

### Kết luận theo ba nhánh của kế hoạch

**Chọn nhánh: static checks pass trong phạm vi Task1, nhưng nguyên nhân UNKNOWN còn mở.** Không phát hiện identity/witness mismatch hoặc hard-model/bound mismatch trong các phép kiểm đã có; không suy rằng toàn bộ compiler hoặc solver đã được chứng minh đúng.

| Bằng chứng đã có | Kết luận được phép |
|---|---|
| Identity/hashes và260witness mappings khớp | Không thấy stale witness hoặc mất placement trên đúng input này |
| Witness thỏa260ExactlyOne/681AtMostOne của actual hard proto | Witness thỏa hard Boolean model đã kiểm, gồm full resource/token occupancy |
| 60raw/weighted bounds và3tier bounds chứa giá trị(0,78,0) | Không thấy bound được kiểm loại witness; chưa đánh giá các auxiliary equalities |
| Structural validation rỗng, objective rỗng sau compile | Model có cấu trúc hợp lệ;254LinMax+60Linear vẫn hiện diện trong feasibility |
| Ba raw UNKNOWN ở feasibility, mọi quality tier NOT_RUN | Chưa tìm được nghiệm trong các lần lịch sử; không chứng minh vô nghiệm hoặc chỉ ra presolve/branching là nguyên nhân |

Task1 chưa cung cấp valuation của314auxiliary variables để đối chiếu254max-equalities và60raw equalities. Vì vậy chưa thể kết luận witness có phần mở rộng thỏa **toàn model sau compile**, cũng chưa đủ căn cứ chuyển nguyên nhân sang search difficulty, symmetry hay môi trường. Số314constraints thêm vào không tự chứng minh chúng làm solver chậm.

### Đúng một bước tiếp theo được đề xuất — chưa thực hiện

**Kiểm chứng tĩnh phần mở rộng auxiliary của witness trên đúng314constraints sau compile của `c10-tight-s101`.** Đây là one-off probe dành riêng cho model mẫu này, không là generic CP-SAT proto evaluator, API hoặc module sản phẩm.

Phạm vi của bước đề xuất: giữ input/fingerprint/source/options như Task1; dựng model build-only mới dưới guard cấm `CpSolver`; gán4,386placement Booleans theo260witness mappings, tính các auxiliary values từ đúng expressions được emit trong proto rồi kiểm variable domains và toàn254max-relations/60raw equalities. Đối chiếu60per-rule raw/weighted values và3tier values với independent score `(0,78,0)`. Chỉ xử lý các expression forms thực sự được xác nhận trên model này; gặp dạng khác thì dừng với reason, không mở rộng thành interpreter tổng quát. Không ghi giá trị ngược vào model hoặc ép penalty về0 để làm kiểm tra pass.

Đầu ra mong muốn: evidence lưu mapping auxiliary values và từng phép so với constraint/domain/per-rule score, kèm báo cáo PASS/mismatch/không đủ dữ liệu trên đúng fingerprint. Nếu mismatch: chỉ nêu constraint/rule/variable gây sai và giá trị dự kiến/thực tính, chưa sửa Core; mọi fix sau đó cần testcase tái hiện. Nếu tất cảpass: chỉ xác nhận có witness mở rộng thỏa model đã kiểm, không suy optimality, tốc độ hoặc nguyên nhân UNKNOWN. Đây là tiêu chí đọc kết quả của **cùng một** bước, không phải authorization cho bước sửa hoặc search sau đó.

**Lý do chọn:** đóng khoảng trống hữu hạn còn lại giữa witness hard-valid và model có compiled auxiliaries trước khi đề nghị phép đo search. Chưa đề xuất hint, gỡ soft/locks, nới budget, đổi workers/seeds hoặc benchmark matrix. Bước kiểm chứng mới chưa được thực hiện trong Task2.

### Kiểm chứng và ranh giới của lượt Task2

Đã đọc lại plan/report và saved JSON; script standard-library read-only có asserts kiểm15hashes trong execution manifest,26raw files/65tracked protected files không đổi, các counts260/683/60 và ba historical UNKNOWN. Không import Core/OR-Tools, rerun probe, dựng model, compile, validator/scorer hoặc tạo phép đo/status mới trong bước đối chiếu này.

Các lệnh thực chạy: Git branch/status/log; read-only Python hash/count assertions PASS; `uv sync --locked --extra solver` PASS/lock không đổi; `uv run ruff check .` PASS; `uv run ruff format --check src tests` PASS44files; `uv run mypy` PASS27source files. Không chạy pytest vì suite có solve và yêu cầu hiện tại cấm search; kết quả439PASS của Task5 vẫn chỉ là lịch sử. Chỉ bổ sung báo cáo này; không sửa Core/tests/config/dependency/budget, không chỉnh artifacts hoặc mở2B/2C. Không cập nhật checkbox plan vì Task2 chỉ định thay đổi duy nhất report; phần này ghi nhận hoàn tất Task2.

Windows vẫnBLOCKED, machine drift4KiB/execution eligibility chưa được xác nhận. Không bypass gate hoặc thực hiện search/profiling; mọi yêu cầu search trace sau này phải được tách riêng theo policy của kế hoạch. Hiện chưa có kết luận root cause hoặc hiệu năng mới.

Kiểm chứng cuối Task2: links/scope và `git diff --check` PASS, chỉ report này thay đổi. Fresh reviewer không actionable findings; xác nhận kết luận nhánh thứ ba, đúng một đề xuất chưa thực thi và các giới hạn/provenance được giữ rõ. Reviewer chỉ đọc diff/plan/report/saved evidence, không chạy scripts/tests/build/solver hoặc tự lặp hash/tooling checks. Không deferred findings; chưa merge/push.

## Kiểm chứng phần mở rộng auxiliary của witness — build-only

Người dùng đã yêu cầu thực hiện phép kiểm được Task2 đề xuất; lượt này chỉ kiểm model mẫu và cập nhật báo cáo, không sửa Core/budget hoặc triển khai search trace. Nhánh `feature/phase2a-task5-linux-summary`, baseline `f5e9b9da39d907b21062888a90b15eb6dd7834e2`; giữ cùng input/witness/source/options và fingerprint `126305e097cb33eb0fc9803061b9817c70127c4a1bfd2085cb006a2c2428b0ee`.

### Phương pháp kiểm riêng cho model này

Probe one-off mới đặt ở scratch, không thêm module/API/evaluator sản phẩm. Chặn `cp_model.CpSolver` trước import helpers/build; số constructor calls bằng0, không import solver entry modules `tkb_core.solver.cp_sat`/`objectives` hoặc gọi solve/presolve/profiling. Không có timer, hints, equality cố định witness hoặc constraint/bound mới để làm kiểm tra pass.

1. Đối chiếu15hashes từ Task1 execution manifest, manifest đó và26raw/65tracked source/test/tooling/config files: **107protected files** đều khớp trước/sau. Core/generator/lock khớp frozen sources,3receipts giữ UNKNOWN. Tái chạy independent hard validator/scorer trên witness; kết quảhard-valid và(0,78,0) khớp baseline.
2. Dựng hard model và compile một lần; model stats khớp snapshot Task1,structural validation rỗng,objective rỗng. Gán4,386placement Booleans theo260witness mappings; mapping indices/start/room/full footprint khớp Task1,260Booleans bằng1.
3. Với254LinMax, chỉ chấp nhận target một biến auxiliary,coefficient1/offset0 và hai operands `[0, Boolean-load−limit]`; load dùng placement indices với coefficients1/2 vàoffset≤0. Tính target bằng max của hai operands từ **actual proto expressions**. Không dùng score độc lập để chọn giá trị auxiliary.
4. Với60Linear, chỉ chấp nhận equality domain[0,0],một raw variable chưa gán với coefficient±1 và các biến còn lại đã biết. Tính raw từ equality. Đây là phép thế số trên dạng đã xác nhận, không vòng tìm kiếm hoặc interpreter tổng quát; dạng/reification/reference/domain khác làm probe dừng bằng assert.
5. Sau khi có đủ4,700giá trị, duyệt lại **toàn bộ actual constraints** và variable domains bằng valuation cố định. Flatten actual compiled raw/weighted/tier expressions qua `FlatIntExpr` để tính giá trị và so với independent scorer. Snapshot proto và domains trước/sau valuation phải giữ nguyên.

### Kết quả

| Phép kiểm | Kết quả |
|---|---|
| Auxiliary values tính được | 314 =254max targets+60raw values |
| Max equalities trong proto | 254/254 target bằngmax(operands) |
| Raw equalities trong proto | 60/60 linear sums thuộc[0,0] |
| Variable domains | 4,700/4,700 giá trị nằm trong declared domains |
| Hard constraints kiểm lại | 260/260ExactlyOne và681/681AtMostOne thỏa |
| Constraints tổng | **1,255/1,255 thỏa**, không enforcement literals hoặc unsupported types |
| Rule score | 60/60raw và60/60weighted expressions khớp independent score |
| Tier score | Cả3tiers khớp **(0,78,0)** |
| Model/domains | Không đổi khi gán valuation trong dictionary Python |
| Search/profiling/status mới | Không có; không tạo hoặc ghi đè ScheduleResult |

**Kết luận có phạm vi:** có một valuation đầy đủ mở rộng từ witness, thỏa mọi variable domain và constraint của model cụ thể sau compile/clear_objective đã kiểm. Vì vậy, trên đúng model/witness/fingerprint này, compiled auxiliary equations và domains **không loại witness**. Khoảng trống “chưa kiểm mọi compiled equality” của Task1/Task2 đã được đóng cho mẫu này; các phần trước và artifacts cũ giữ đúng lịch sử kiểm tra.

Điều này không chứng minh compiler đúng cho mọi input/lịch hoặc witness tối ưu, không tạo solver OPTIMAL/FEASIBLE claim và không thay ba historical UNKNOWN. Chưa có trace để phân biệt presolve, branching, symmetry hoặc môi trường; việc có witness thỏa model không giải thích vì sao các lượt tìm kiếm chưa thấy nghiệm trong60s.

### Self-checks và evidence

Đã quan sát RED khi probe chưa tồn tại, sau đó5scratch `unittest` self-checks PASS: arithmetic với offsets/coefficients,unknown/negative references,max targets/raw equalities bị đổi sai,domain endpoints và unsupported domain/equality forms. Không có Core/tests sản phẩm được thêm/sửa. Replay saved JSON không import Core/OR-Tools kiểm lại4,700domains/1,255constraints/60rule scores/3tiers; hai phép thử đổi sai một max auxiliary và một raw auxiliary đều bị checker từ chối.107protected file hashes vẫn khớp.

Evidence local tại `.worktrees/phase2a-task5/benchmarks/artifacts/phase2a/tight10-auxiliary-v1/`:

- `summary.json`: SHA256 `56feb4152f5d37ac8b4b327b0259cd680211dc1ac7be2138c3cd70a7f52ec400`; result nội bộ `SATISFIED_BY_EXTENDED_WITNESS`,không là SolveStatus.
- `probe.py`: SHA256 `ab2e29c558b5e52363d8c5109911f2f03ac25896688c4f658eed9dd53c3eef14`; có5self-checks trong `test_probe.py`,replay `verify_saved.py`,stdout/stderr và execution manifest.
- `variables.json`, `constraints.json`, `auxiliary-derivations.json`: đầy đủvaluation,actual expressions/coefficients/domains và kết quả từng constraint. `rule-scores.json`, `tier-scores.json`, `independent-score.json`: actual expression arithmetic và independent comparison.
- `model-proto.txt`: SHA256 `f8c390bc03b2ac6d1d176461c142d59bd0b869c189b0b230efd6f6f04b858083`; `protected-hashes.json` giữ107snapshot hashes. Evidence mới không ghi đè Task1/Task5/raw campaign và không commit/upload dữ liệu generated.

| Lệnh thực chạy | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS,lock không đổi |
| `uv run --extra solver python .superpowers/sdd/tight10-auxiliary-witness/test_probe.py` | 5tests PASS sau RED import probe chưa có |
| `uv run --extra solver python .superpowers/sdd/tight10-auxiliary-witness/probe.py` | Exit0,asserts PASS,solver guard calls0 |
| `uv run --extra solver python .superpowers/sdd/tight10-auxiliary-witness/verify_saved.py` | Replay/mutation checks và107hashes PASS |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` | PASS44files |
| `uv run mypy` | PASS27Core source files |

Không chạy full pytest vì suite có solve;439PASS của Task5 vẫn là lịch sử. Không đo benchmark, sửa Core/config/dependencies, thay60s/workers1/seed42/guards hoặc mở2B/2C/repair. Windows BLOCKED và current execution eligibility/machine drift4KiB chưa được giải quyết bằng static check.

**Đúng một bước tiếp theo được đề xuất, chưa thực hiện:** lập kế hoạch thu search trace tối thiểu cho `c10-tight-s101` để phân biệt presolve với branching, giữ nguyên60s/workers1/seed42 và guards; xác định instrumentation/output/measurement method và cách xử lý execution identity gate trước khi xin thực hiện. Lượt này chưa lập/chạy campaign trace, profiling hoặc tuning.

### Kiểm chứng cuối phép kiểm auxiliary

15entries của execution manifest khớp hashes; summary,report links và report-only tracked diff đã được đối chiếu bằng asserts, `git diff --check` PASS. Ruff/format/mypy được chạy lại và vẫnPASS. Không cần sửa probe hoặc Core sau kiểm chứng.

Fresh reviewer không actionable findings. Reviewer tự replay saved data và hai mutation checks, kiểm107protected hashes và script copies; đặc biệt deserialize **saved model-proto.txt** dưới guard `CpSolver` rồi đối chiếu từng variable definition và constraint payload với JSON (4,700variables/1,255constraints), xác nhận không objective và guard calls0. Reviewer đọc arithmetic/derivation/independent scoring/immutability; không chạy lại probe, build model, solver/search/profiling hoặc full suite. Không có deferred findings.

Phạm vi còn lại: đây là một satisfying witness extension cho đúng model đã lưu, không là chứng minh tối ưu/correctness tổng quát hoặc lời giải thích UNKNOWN. Báo cáo được giữ trên nhánh hiện tại; chưa merge/push hoặc thực hiện đề xuất trace.
