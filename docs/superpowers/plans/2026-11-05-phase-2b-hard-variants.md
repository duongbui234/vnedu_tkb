# Phase 2B — kế hoạch triển khai hard variants S01–S04

Ngày 2026-11-05. Trạng thái: **DRAFT — CHỜ DUYỆT; CHƯA CÓ ỦY QUYỀN TRIỂN KHAI.**
Đặc tả: [2026-11-05-phase-2b-hard-variants-design.md](../specs/2026-11-05-phase-2b-hard-variants-design.md).
Base `124b89d318467421dedf421f8d1c9a6b72b6991e`, nhánh `work/phase2a-operational-completion`.

Kế hoạch giả định D1–D7 được duyệt như đề xuất. Nếu người dùng chọn khác, cập nhật đặc tả và
các task bị ảnh hưởng trước khi viết code. Mỗi task theo TDD: viết test RED, chạy xác nhận RED,
sửa tối thiểu, GREEN, rồi checks nhanh của task. Không chạy pilot/campaign, không sửa
`benchmarks/` hoặc gate/budget, không dùng witness hint, không commit/push trong các task.

## Ranh giới phê duyệt

| Bước | Cần duyệt riêng |
|---|---|
| A. Duyệt đặc tả + D1–D7 | Có — lượt này dừng ở đây |
| B. Triển khai Task 1–8 trong working tree, chạy checks | Có (thay đổi product code) |
| C. Docs cập nhật + checks + commit + local merge | Có, gộp một lần |
| D. Push + dọn branch/worktree | Có, gộp một lần |

## Task 1 — Contract policy 0.2 và output 1.3 (D1, D2)

Files: `domain/models.py`, `contracts/input.py`, `contracts/score.py`, `contracts/output.py`,
`tests/unit/test_quality_contracts.py`, `tests/unit/test_quality_results.py`.

1. RED: 0.2 parse được; 0.1 + enabled hard vẫn `CUSTOM_HARD_RULE`; policy `"0.3"` reject;
   hard có priority/weight reject; output 1.3 roundtrip; output 1.2 với policy 0.2 reject và
   ngược lại; hash 1.0/0.1 của fixtures hiện có không đổi (so hash cứng đã có trong tests).
2. Mở `policy_version: Literal["0.1","0.2"]`; `QualityReport.policy_version` cùng literal; thêm
   validator cặp output version ↔ policy version. Không đổi shape khác.
3. Fingerprint tests §2.2 của đặc tả.

## Task 2 — Registry modes theo policy và overlap mọi mode (D4)

Files: `constraints/registry.py`, `contracts/capabilities.py`, `tests/unit/test_quality_contracts.py` (hoặc file mới `tests/unit/test_hard_variant_registry.py`).

1. RED: matrix capability §3.2; overlap hard+soft, hard+hard, khác family được phép,
   disabled bỏ qua; scope class/subject/room trên hard → RULE_SCOPE; unknown enabled hard →
   UNKNOWN_RULE.
2. `RuleDefinition` thêm modes theo policy; `validate_rule_config` xét enabled hard ∪ soft
   (giữ nguyên thuật toán overlap S01 timed/S02/S04 hiện có).
3. `check_capabilities`: 0.1 giữ nhánh cũ nguyên văn; 0.2 cho phép hard khi code hỗ trợ.
   **Capability chưa được bật cho solve** đến khi Task 3–5 xong: dùng một cờ nội bộ hoặc
   giữ 0.2 hard ở UNSUPPORTED cho tới Task 6 để không có thời điểm “quảng cáo mà chưa kiểm”.

## Task 3 — Independent hard checker (D7)

Files: `validation/independent_validator.py`, `tests/unit/test_validator.py`, `tests/unit/test_score_evaluator.py`,
import-graph test hiện có cho validator.

1. RED: lịch forged vi phạm từng family (single/double, AM/PM, timed alias, limit=0, window
   tiết hai) → đúng `HARD_*` + resource/slot/occurrence; lịch hợp lệ không có vi phạm;
   rule disabled không được kiểm.
2. Hiện thực độc lập trong validator (footprint đã dựng sẵn ở đó); không import
   `constraints/*`, `preprocessing`, `solver`, `score_evaluator`.
3. `evaluate_score` trả `INVALID_SCHEDULE` khi vi phạm hard variant (test).

## Task 4 — Compiler S01/S04: lọc domain (D3)

Files mới `constraints/hard_variants.py` (không import OR-Tools); `preprocessing/feasibility.py`;
`tests/unit/test_hard_variant_domains.py`.

1. RED: placement chạm ô tránh / ngoài window bị loại; timed alias; double tiết hai;
   domain rỗng → INFEASIBLE/EMPTY_DOMAIN; lock trái hard → INPUT_INVALID/LOCK_CONFLICT;
   0.1 và input không có hard → domains byte-identical so với trước (so tuple domains).
2. Gọi predicate sau kiểm availability, trước room loop và capacity prechecks.

## Task 5 — Compiler S02/S03: ràng buộc tải

Files: `constraints/hard_variants.py` (phần OR-Tools tách hàm, import lười), `solver/model_builder.py`,
`tests/unit/test_hard_variant_model.py`.

1. RED: model nhỏ load=limit FEASIBLE, limit+1 cưỡng bức → INFEASIBLE; limit=0; double tính 2;
   S02 tách session, S03 cộng session; range guard `HARD_RULE_RANGE`.
2. `build_model` thêm ràng buộc sau occupancy, trước `_add_interchangeable_ordering`; giữ
   `cp_sat.solve` clone `hard_model` sau `build_model` (test: hard_model chứa ràng buộc).
3. Ordering vẫn tắt khi có hard ở task này.

## Task 6 — Pipeline, status và bật capability

Files: `solver/cp_sat.py`, `contracts/capabilities.py`, `tests/integration/test_hard_variants_solver.py`,
cập nhật `tests/integration/test_quality_solver.py::test_hard_modes_and_unknown_rejected`
(giữ ca 0.1 bị từ chối; thêm ca 0.2 được giải).

1. RED: 0.2 chỉ hard → output 1.3, `NOT_REQUESTED`, validator PASS; 0.2 hard+soft → tier runs
   như 2A, incumbent thỏa hard; empty demand; compiler cố ý sai (monkeypatch bỏ bucket) →
   MODEL_INVALID/INTERNAL_VALIDATION_FAILED, không assignments; stub INFEASIBLE sau incumbent →
   INTERNAL_STAGE_INCONSISTENCY; zero-probe clone chứa ràng buộc hard.
2. Bật capability 0.2 hard cho đúng bốn code chỉ trong commit/task này.

## Task 7 — Oracle vét cạn và symmetry ordering (D5)

Files: `tests/properties/test_hard_variant_oracle.py` (oracle Python độc lập, tự enumerate).

1. Bài nhỏ (≤2 GV, ≤3 lớp, ≤6 slots, có double/timed): tập hard-valid brute force; so
   FEASIBLE/INFEASIBLE với solve; hard+soft so optimum vector brute force.
2. Ordering: bật tạm trong test, so optimum vector với/không ordering. Nếu bằng nhau trên
   mọi fixture → cho phép ordering khi enabled hard ⊂ S01–S04 (sửa `model_builder`). Nếu không
   → giữ tắt, ghi rõ trong báo cáo; không chặn 2B.

## Task 8 — CLI/package và tài liệu

Files: `cli.py` (nếu cần cho output 1.3), `tests/integration/test_quality_cli.py`, `tests/integration/test_packaging.py`, `docs/constraint-catalog.md`,
`docs/domain-model.md`, `docs/solver-design.md`, `README` (nếu có mục capability),
`docs/phase-2b-report.md` mới, cập nhật trạng thái trong spec Phase 2 và cloud handoff.

1. RED: solve 0.2 → 1.3 → `validate-schedule`/`evaluate-score`; evaluate-score khi không có
   OR-Tools; forged result vi phạm hard → exit 2; stdout không lộ input.
2. Docs: S01 hard cấm cả alias giao phút; INFEASIBLE không chỉ ra rule gây ra; không có ngưỡng
   mặc định; hạn chế 2A (Windows, v2 DRAFT, zero NOT_MET, primary 0/108) giữ nguyên.
3. Sửa trạng thái cũ trong `docs/phase-2a-cloud-handoff.md`: commit 124b89d đã tồn tại
   (tài liệu đang ghi “chưa được tạo”).

## Checks trước khi báo hoàn thành (Bước B)

```bash
uv sync --locked --extra solver
```

```bash
uv run --extra solver pytest
```

```bash
uv run --extra solver pytest tests benchmarks/tests
```

```bash
uv run ruff check .
```

```bash
uv run ruff format --check src tests
```

```bash
uv run mypy
```

```bash
git diff --check
```

Báo đúng số passed/skipped thực chạy; baseline lịch sử là Core 363 / full 728 passed, 8 skipped
(chưa chạy lại trong cloud). Skips Windows không được coi là Windows đã chạy. Không build wheel
hay installed preflight trừ khi được ủy quyền; nếu có, đó là candidate mới, không dùng receipt cũ.

## Rủi ro và giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| Lọc domain thay đổi hành vi 0.1 | Test domains byte-identical khi không có hard 0.2 |
| Compiler và checker cùng sai | Không chia sẻ helper; oracle brute force độc lập thứ ba |
| Hard vào sau clone `hard_model` | Test cấu trúc + integration feasibility-stage với hard |
| Ordering làm mất optimum | Bật chỉ khi oracle Task 7 đạt; mặc định tắt |
| Hash lịch sử bị đổi | Hash cứng của fixtures 1.0/0.1 trong regression |
| Diễn giải INFEASIBLE thành “rule X gây ra” | Diagnostic cố định, docs nêu rõ không có IIS |
