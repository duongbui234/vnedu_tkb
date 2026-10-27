# TIGHT10 Task 1 — build-only witness, hard occupancy và compiler bounds

**Task 1: PASS trong phạm vi các phép kiểm dưới đây. Không có search/profiling hoặc solver status mới. Chưa xác nhận witness thỏa mọi compiled equality; nguyên nhân UNKNOWN còn mở. Task 2 chưa thực hiện, Windows BLOCKED.**

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
