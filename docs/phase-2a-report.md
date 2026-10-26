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

**Minor giữ lại:** default `RuleDefinition.supported_modes=("soft",)` không gây fail-open cho bốn rule hiện tại vì đều có compiler/evaluator; khi thêm entry tương lai cần khai báo unsupported trước. Chưa thay đổi để tránh mở rộng lượt sửa; không phải capability cho 2B/2C.

**Các điểm reviewer đã cân nhắc:**

- Nghi vấn S01 giao ngày khác đã rút lại: timeline dùng phút từ gốc cycle và public gates chặn day ranges chồng nhau. Không nhận local-clock minutes của từng ngày như thể cùng gốc.
- Proof từ file ngoài không được chứng nhận tối ưu lại; chỉ kiểm hard/score và structural consistency. Không dùng metadata đã chỉnh sửa như chứng chỉ tối ưu mới.
- Production performance, Windows và 2B/2C ngoài phạm vi kiểm chứng; không suy từ synthetic2A.

Nhánh đã giữ lại để người dùng review/tích hợp; chưa merge/push. Checkout gốc vẫn giữ tài liệu/AGENTS chưa commit. Các quyết định và hệ quả trước tích hợp: giữ copy context ngoài commit code (cần đối chiếu docs khi merge), metadataV12 ở output.py (giữ correlation schema), registry dispatch riêng (thêm rule phải cập nhật hai implementation paths).
