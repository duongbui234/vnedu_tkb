# Phase 2A — Báo cáo triển khai và kiểm chứng

Ngày 2026-10-26. Nhánh `feature/phase2a-quality`, base `7f58f710a9901fe2c0457573feaad272e713d7a1`.

## Kết quả và phạm vi

**VERIFIED:** đã triển khai S01–S04 soft, registry metadata/typed parameters, input 1.1/policy0.1, output1.2, ưu tiên lexicographic P1–P3, Python independent score evaluator và CLI evaluate-score. Input1.0/hash/serialization và hard-feasibility path giữ tương thích Phase1. Không sửa API, SQLite, Desktop hoặc dữ liệu nghiên cứu gốc.

Các điểm kiểm chứng chính:

- Demand, single/double footprint, availability, locks và room constraints luôn giữ. Soft không prune placements; limit0 khi bật được thực thi.
- Penalty tính theo teaching_periods: ô tránh, vượt tải/buổi, vượt tải/ngày và ngoài khung tiết. Không lấy mặc định max3 hoặc API so_tiet làm policy.
- Mỗi candidate giữ lại phải pass independent hard validation, rồi score evaluator tự expand occurrences/footprints và loads; đối chiếu raw/weighted/tier expressions, mismatch không xuất lịch.
- Chỉ tier đã chứng minh OPTIMAL mới được cố định. UNKNOWN hoặc hết budget ở tier sau giữ incumbent đã xác nhận, top-level FEASIBLE; INFEASIBLE sau incumbent được báo lỗi nội bộ.
- Fingerprint 1.1 canonical hóa known sets/rules; raw arrays unknown disabled và split order giữ nguyên. Legacy fingerprint fixture vẫn `77851bfa1fa34e4155969ee7749117415de0fd90e6de743fd7267f5ec194eee1`.
- CLI không tin điểm/validation tự khai, kiểm stale fingerprint và tính lại. evaluate-score chạy bằng wheel không cài OR-Tools; solve thiếu extra được phân loại SOLVER_NOT_INSTALLED.

## File thay đổi

| Nhóm | File chính |
|---|---|
| Domain/contracts/registry | `domain/models.py`, `domain/rule_parameters.py`, `contracts/input.py`, `contracts/output.py`, `contracts/score.py`, `contracts/capabilities.py`, `constraints/registry.py` |
| Tính điểm và model | `validation/score_evaluator.py`, `constraints/soft.py`, `solver/objectives.py`, `solver/cp_sat.py` |
| CLI | `cli.py` |
| Tests | `test_quality_contracts`, `test_quality_results`, `test_score_evaluator`, `test_soft_compilers`, `test_quality_stages`, `test_quality_solver`, `test_quality_cli`, `test_quality_oracle`; cập nhật conftest/schema/packaging assertions |
| Fixtures | `quality/teacher_preferences.json`, `quality/priority_tradeoff.json`, `quality/weighted_tradeoff.json` — toàn bộ synthetic |
| Docs | README, domain-model, solver-design, constraint-catalog, approved spec/implementation plan và báo cáo này |

Không thay solver dependencies hoặc uv.lock. `pyproject.toml` chỉ thêm report vào allowlist sdist cùng packaging test; hard occupancy/precheck algorithm và defaults không thay.

## Lệnh đã chạy

| Kiểm tra | Kết quả trước review cuối |
|---|---|
| `uv sync --locked --extra solver` | PASS, lock không đổi |
| Baseline `uv run --extra solver pytest -q` | 143 passed trước thay đổi |
| Suite Phase2A `uv run --extra solver pytest -q` | 225 passed, 5.19s |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` | PASS, 44 files formatted |
| `uv run mypy` | PASS, 27 source files |
| `uv build` | PASS sdist + wheel; package version vẫn0.2.0, schema versions độc lập package version |
| Installed wheel full-extra | solve → validate-schedule → evaluate-score PASS |
| Installed wheel chỉ Pydantic | evaluate-score PASS; solve exit2/SOLVER_NOT_INSTALLED như mong đợi |

Đã quan sát RED→GREEN cho contract/version, report types, evaluator, compilers, orchestration, public API, CLI, optional-import isolation và lỗi syntactic objective overflow ở nhiều alternatives. Property/oracle bổ sung pass ngay khi implementation đã tồn tại; không làm code sai để tạo RED giả.

## Đối chứng correctness

- 10 seeds tiny exhaustive oracle, độc lập model/validator/evaluator helpers; so feasibility và optimum vector.
- Priority fixture: hai lịch hard-valid, baseline slot B có vector `(1,0,0)`; tối ưu chọn A với `(0,5,0)` vì P1 quan trọng hơn P2.
- Cùng tier: weighted fixture chọn B với `(1,0,0)`, thay vì A có `(3,0,0)`.
- Timer/status tests dùng fake stage outcomes và clock, không dựa tốc độ máy: FEASIBLE/UNKNOWN fallback, không gọi tier thấp khi chưa proof, later INFEASIBLE và mismatch.
- Timed aliases khác session, double second period, room alternatives, locked high penalties và caller mutation được đối chiếu qua public APIs.

## Measurement smoke — không phải benchmark production

Một lần solve fixture priority, 1 occurrence, 2 placements, 2 rules; workers1, seed42, budget5s, OR-Tools9.15.6755. CPU Intel Core i7-12700H; Linux x86_64/glibc2.39; Python3.12.3; RAM hệ thống41,723,121,664bytes.

| Chỉ số | Giá trị quan sát |
|---|---|
| End-to-end solve | 0.20838s, gồm first-use import/initialization |
| Tổng solver wall time | 0.001611s |
| CPU process delta | 2.083486 CPU-seconds; gồm native initialization/threads, không phải một CPU-core wall time |
| Peak process RSS | 104,992 KiB; high-water mark của process, không phải RAM riêng solver hoặc delta |
| Feasibility | OPTIMAL, 0.001161s; không quality proof |
| P1 | OPTIMAL, value0/bound0, 0.000246s |
| P2 | OPTIMAL, value5/bound5, 0.000204s |
| Hard checker / score recomputation | PASS / MATCH |

Không đo time-to-first-feasible bằng callback. Không so FET/STKB hoặc kết luận hiệu năng trường thật từ fixture nhỏ này. Số đo và kết luận chính được lưu trong báo cáo này; logs đo/wheel smoke/ledger được chuyển sang thư mục evidence trong môi trường smoke tạm `/tmp/tkb-phase2a-3c459ia4/` trước khi dọn workspace của plan, không vào package. Thư mục tạm không phải nơi lưu trữ lâu dài.

## Quyết định triển khai và giới hạn

- Metadata V12 đặt cạnh SolverRunMetadata trong output.py để tránh circular dependency; không đổi wire schema được duyệt.
- Registry lưu static metadata/parameter models/capabilities; compiler và evaluator dispatch riêng theo typed parameters trong modules của chúng, thay vì hai accessor registry không có caller. Không có shared arithmetic hoặc import OR-Tools qua registry.
- Không hints/callback mới trong2A; giữ incumbent qua stage results, proof chỉ dựa exact OPTIMAL với gap tolerances0.
- Worktree riêng chứa copy approved docs/context chưa commit của checkout gốc; không tự stage research hoặc AGENTS thay đổi của người dùng. Chưa merge/push main.

**UNKNOWN/giới hạn:** chưa hiệu chỉnh weight/ngưỡng với giáo vụ, chưa benchmark trên Windows/máy trường hoặc dữ liệu trường thật. Chưa hard variants2B, S05–S12/spacing/gaps2C, repair, travel, đồng giảng/lớp ghép, tuầnA/B hoặc adapter. Hoàn thành2A không đồng nghĩa hoàn thành toàn Phase2.

## Review cuối

Reviewer độc lập đã rà range `7f58f71..c885fd5`, tự chạy 225 tests pass và chỉ ra hai Important; không có Critical:

1. Input1.1 lỗi options/mutated/model-constructed data đôi khi trả result1.1. Đã nhận diện schema trước bước validation có thể fail; result1.2/NOT_EVALUATED được giữ, không xuất assignments và không bỏ revalidation.
2. Proved tier incumbent_value có thể mâu thuẫn với score. Đã thêm guard đối chiếu exact score của prefix; parser và cả hai CLI commands bác payload mâu thuẫn.

Cả hai có tests đã quan sát RED→GREEN. Test forged score cũ được giữ structurally coherent để tiếp tục kiểm nhánh independent RESULT_SCORE_MISMATCH thay vì chỉ parser rejection.

**Sau lượt sửa duy nhất:** `uv run --extra solver pytest -q`: **229 passed, 4.63s**; ruff check PASS; format check PASS (44 files); mypy PASS (27 files). Wheel được rebuild và chạy smoke lại sau sửa. Không dispatch reviewer lần hai; dùng regression tests và toàn suite để kiểm chứng lượt sửa theo executing-plans.

**Minor đã xử lý trong lượt bổ sung:** `RuleDefinition.supported_modes` mặc định `()`; chỉ S01–S04 được khai báo `("soft",)` tường minh. Entry mới không tự nhận capability, kể cả dùng lại parameter model đã có implementation. Không mở hard mode hoặc Phase 2B/2C.

**Các điểm reviewer đã cân nhắc:**

- Nghi vấn S01 giao ngày khác đã rút lại: timeline dùng phút từ gốc cycle và public gates chặn day ranges chồng nhau. Không nhận local-clock minutes của từng ngày như thể cùng gốc.
- Proof từ file ngoài không được chứng nhận tối ưu lại; chỉ kiểm hard/score và structural consistency. Không dùng metadata đã chỉnh sửa như chứng chỉ tối ưu mới.
- Production performance, Windows và 2B/2C ngoài phạm vi kiểm chứng; không suy từ synthetic2A.

Nhánh đã giữ lại để người dùng review/tích hợp; chưa merge/push. Checkout gốc vẫn giữ tài liệu/AGENTS chưa commit. Các quyết định và hệ quả trước tích hợp: giữ copy context ngoài commit code (cần đối chiếu docs khi merge), metadataV12 ở output.py (giữ correlation schema), registry dispatch riêng (thêm rule phải cập nhật hai implementation paths).

## Bổ sung — đóng capability mặc định

Đã quan sát RED→GREEN: entry mới trước sửa mặc nhiên có soft và không bị capability guard từ chối; sau sửa mặc định không có mode. Thêm ba regression tests: default đóng, bốn entry hiện có soft tường minh, và entry pending dùng lại MaxDayParameters bị solve/evaluate_score/validate_schedule từ chối. Solve không chạy CP-SAT hoặc xuất assignments/score cho entry pending bật; declaration tắt không tạo penalty.

Kiểm chứng bổ sung: `uv sync --locked --extra solver`; full pytest **232 passed**; ruff check, format check, mypy và build sdist/wheel đều được chạy. Không đổi schema, fingerprint, dependency/uv.lock, compiler/evaluator hoặc các rule nghiệp vụ. Commit bản sửa chỉ gồm registry, hai file regression tests và báo cáo này; chưa push. AGENTS và báo cáo nghiên cứu chưa commit được giữ nguyên.

## Rà soát nghiệm thu Phase 2A — snapshot main 30a6c55

**Kết luận: ĐẠT mốc kỹ thuật Phase 2A trên dữ liệu synthetic theo đặc tả đã duyệt.** Đây là kết luận nghiệm thu có phạm vi, không phải nghiệm thu vận hành cho trường thật hoặc hoàn thành toàn Phase 2. Chưa triển khai 2B/2C.

Căn cứ: [đặc tả, mục 9–10](superpowers/specs/2026-10-26-phase-2-quality-design.md#9-nghiệm-thu-và-fixture-kế-hoạch), source và tests tại commit `30a6c55b0871c8212dd858e3fd8d165728186390`; chạy lại các kiểm tra bên dưới trong lượt rà này. Những số 225/229 tests và trạng thái chưa merge/push ở các phần trên là lịch sử triển khai, không phải trạng thái nghiệm thu mới nhất.

### Đối chiếu điều kiện ra mốc

| Tiêu chí | Kết quả | Bằng chứng cụ thể |
|---|---|---|
| Contract migration, legacy không đổi | ĐẠT | `contracts/input.py::ScheduleInput`, `contracts/output.py::ScheduleResult`; [test_v10_hash_and_payload_unchanged](../tests/unit/test_quality_contracts.py#L12), test_v11_config_roundtrip; legacy/hash và output roundtrip tests |
| Registry có params strict, scope và capability guard | ĐẠT | [RuleDefinition và bốn entry](../src/tkb_core/constraints/registry.py#L22); default modes rỗng, soft explicit S01–S04; test_new_rule_definitions_start_without_capabilities, test_phase2a_rules_explicitly_support_soft_only, test_pending_rule_reusing_known_parameters_is_rejected_before_solving |
| S01 tránh ô mong muốn | ĐẠT | `soft.py::compile_soft`, `score_evaluator.py::_evaluate_validated`; test_hand_calculated, test_public_two_period_cases, test_timed_alias_is_counted_once_and_room_choices_do_not_multiply; phạt toàn footprint, không nhân theo room alternatives/alias |
| S02 vượt tải buổi / S03 vượt tải ngày | ĐẠT | Các compiler/evaluator tính excess theo đúng bucket và unit tiết dạy; literal expected trong test_hand_calculated/test_public_two_period_cases, exact expressions không cần objective trong test_exact_expression_without_objective; oracle có cả hai rule |
| S04 ngoài window inclusive | ĐẠT | Compiler/evaluator kiểm mọi covered period; test_public_two_period_cases có double qua biên window và session không áp dụng |
| Hard validity, split/locks/phòng không bị soft phá | ĐẠT | Hard model/checker Phase 1 giữ nguyên; full regression suite, test_soft_limits_do_not_remove_locked_teaching, room/timed/block integration tests; bài soft không đạt vẫn có thể hard-valid và điểm dương |
| Evaluator độc lập, model mismatch không xuất lịch | ĐẠT | [evaluate_score](../src/tkb_core/validation/score_evaluator.py#L106) tự dựng footprint/loads, không import compiler/preprocessing/OR-Tools; test_mismatch_and_budget và test_evaluate_score_without_solver_imports; đối chiếu raw/weighted/tier tại run_quality |
| Tối ưu weighted sum trong tier, P1→P3 theo thứ tự | ĐẠT | [run_quality](../src/tkb_core/solver/objectives.py#L104); test_small_quality_matches_exhaustive_oracle trên 10 seeds, test_fixed_baseline_improvement. Priority `(0,5,0)` thắng `(1,0,0)`; cùng tier chọn weighted sum nhỏ hơn |
| Budget/status/proof và incumbent không nhập nhằng | ĐẠT | test_stage_proof_and_fallback, test_mismatch_and_budget, test_unproved_second_tier_stops_before_third: FEASIBLE/UNKNOWN dừng tier thấp, hết budget giữ incumbent, later INFEASIBLE/prefix sai là lỗi nội bộ; gap tolerances 0 |
| Kết quả/CLI từ chối stale hoặc claim mâu thuẫn | ĐẠT | test_solve_score_and_forged_score, test_proof_value_must_match_scored_prefix, test_recognized_v11_validation_errors_still_emit_v12; validate-schedule/evaluate-score recompute, không chứng nhận lại optimality từ metadata bên ngoài |
| An toàn số học, packaging và optional solver | ĐẠT | test_objective_bound_guard, test_exact_bound_with_many_alternatives, packaging allowlist tests; installed-wheel smoke ở hai venv độc lập được chạy lại |

ĐẠT ở bảng trên có nghĩa source hiện tại và các tests/thử nghiệm tương ứng đáp ứng tiêu chí; không có nghĩa đã bao phủ mọi tổ hợp đầu vào hoặc có chứng minh correctness tổng quát cho toàn bộ implementation. Oracle chỉ xác nhận tối ưu của các bài nhỏ đã enumerate.

### Kết quả chạy mới

| Lệnh/thử nghiệm | Kết quả trong lượt rà |
|---|---|
| `uv sync --locked --extra solver` | PASS, lock không đổi |
| `uv run --extra solver pytest -q` | **232 passed, 4.42s** |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` | PASS, 44 files |
| `uv run mypy` | PASS, 27 source files |
| `uv build` | PASS, sdist và wheel |
| Wheel cài trong venv có solver | solve → validate-schedule → evaluate-score PASS, priority vector `(0,5,0)` |
| Wheel cài trong venv không có solver | evaluate-score PASS cùng vector; solve exit2/SOLVER_NOT_INSTALLED đúng như contract |

Không chạy benchmark quy mô trường trong lượt rà; không sử dụng số smoke fixture một occurrence làm kết luận hiệu năng. Không truy cập API hoặc sửa Core/tests/dependency. AGENTS và nghiên cứu chưa commit giữ nguyên; bản rà này chỉ bổ sung báo cáo, chưa commit/push.

### Phần chưa được nghiệm thu và ranh giới

- **UNKNOWN — vận hành:** Windows, máy người dùng, peak RAM/thời gian/timeout ở quy mô trường, ảnh hưởng workers/seeds và các bài khó. Linux synthetic pass không thay kiểm chứng này.
- **UNKNOWN — policy trường:** ngưỡng và trọng số chưa được giáo vụ hiệu chỉnh; nguồn demand/split/calendar phải được upstream xác nhận. Không suy `so_tiet` API thành demand hoặc tự phân loại mã STKB Bận/Họp.
- **Ngoài Phase 2A:** custom hard variants (2B), S05–S12/phân phối môn/gaps (2C), repair, đồng giảng/lớp ghép, travel, tuần A/B, adapter/UI/persistence. Capability hiện tiếp tục từ chối phần chưa hỗ trợ.
- Không còn minor `supported_modes` mặc định mở: đã xử lý trong `30a6c55`. Hai Important từ review trước cũng đã có regression và nằm trong suite hiện tại. Lượt này không phải một audit toàn repository để tuyên bố không còn mọi loại lỗi.

### Một bước tiếp theo được đề xuất, chưa thực hiện

**INFERRED — lập kế hoạch kiểm chứng vận hành Phase 2A trên Windows/Linux và dữ liệu synthetic gần quy mô trường**, trước khi quyết định bổ sung rule.

Kế hoạch nên định nghĩa dữ liệu 10/20/40 lớp với demand/split rõ ràng; nhiều session, mức khóa/availability và room scope khác nhau; các case feasible, khó và infeasible đã biết. Đặt tiêu chí cứng là hard checker pass, score recomputation khớp và status/proof trung thực; ghi thời gian đến nghiệm đầu nếu thực sự instrument, total wall/solver time, peak process memory, từng tier score/bound/proof và timeout behavior. Lưu CPU/RAM/OS/Python/OR-Tools/seed/workers/budget; chọn ngưỡng hiệu năng chấp nhận sau khi có số đo và nhu cầu máy đích, không đoán SLA.

Đầu ra của bước tiếp theo là kế hoạch/dataset specification có thể review, không thêm solver rules, adapter hoặc Phase 2B/2C. Việc triển khai benchmark hay xác nhận chính sách trường là yêu cầu riêng sau khi kế hoạch được chấp thuận.
