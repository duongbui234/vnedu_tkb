# Phase 2C-2 — kế hoạch triển khai S07–S11

Ngày 2026-11-05. Trạng thái: **ĐÃ DUYỆT (D1–D7 theo đề xuất) VÀ ĐÃ THỰC HIỆN Task 1–9** — kết quả
và sai khác so với kế hoạch ở [báo cáo 2C-2](../../phase-2c-gaps-report.md).
Đặc tả: [2026-11-05-phase-2c-gaps-design.md](../specs/2026-11-05-phase-2c-gaps-design.md).
Base `45f63eec0380b22e60b4a4ab83a790cbe0f4921e` trên `main`.

Kế hoạch giả định D1–D7 được duyệt như đề xuất; nếu chọn khác thì cập nhật đặc tả và task bị ảnh hưởng
trước khi viết code. Mỗi task theo TDD: test RED trước, sửa tối thiểu, GREEN. Nếu wiring đã có từ task
trước làm test mới xanh ngay, kiểm test có tác dụng bằng cách tạm khôi phục file cũ (như 2C-1). Không
sửa `benchmarks/`, gate, budget hay pins; không witness hint, pilot/campaign; không commit trong các task.

## Ranh giới phê duyệt

| Bước | Cần duyệt riêng |
|---|---|
| A. Duyệt đặc tả + D1–D7 | Có — lượt này dừng ở đây |
| B. Triển khai Task 1–9 trong working tree, chạy checks | Có (product code) |
| C. Docs + checks + commit + push (+ PR nếu muốn) | Có, gộp một lần |

## Task 1 — Contract policy 0.4, output 1.5, ScoreReport 1.2 (D1, D2)

Files: `domain/models.py`, `contracts/score.py`, `contracts/output.py`, `solver/cp_sat.py`, `cli.py`,
`validation/score_evaluator.py` (`score_version`), `tests/unit/test_gaps_contracts.py` (mới),
`tests/integration/test_cli.py` (enum).

RED: 0.4 roundtrip; 0.5 reject; cặp 1.5 ↔ 0.4 ↔ Score 1.2 và mọi cặp sai; Score 1.0/1.1 từ chối unit
mới; hash fixtures 0.1–0.3 không đổi (so với giá trị ở base).

## Task 2 — Occupied work (D3)

Files: `domain/models.py` (`OccupiedWork`), `contracts/input.py` (references, availability, fingerprint,
serializer bỏ field ở policy < 0.4), tests trong `test_gaps_contracts.py`.

RED: field ở 0.1–0.3 → lỗi; dump/fingerprint 0.1–0.3 không có field; trùng GV; slot lạ/trùng;
availability `null` hoặc chứa ô occupied → INPUT_INVALID/OCCUPIED_AVAILABLE; sort trong fingerprint.

## Task 3 — Registry, scope, overlap (D7)

Files: `domain/rule_parameters.py` (5 model tham số), `constraints/registry.py`, `contracts/capabilities.py`.

RED: tham số strict từng mã (`unit` literal, `target ≥ 1`, `limit ≥ 0`, tập không rỗng); teacher scope
only; 0.1–0.3 → UNKNOWN_RULE; overlap S07+S07, **S01+S07**, S08/S09/S11 theo session, S10 bất kể unit;
GAP_TIMELINE cho S08–S11 với slot khác buổi giao phút (D4); S07 timed vẫn được.

## Task 4 — Evaluator độc lập

Files: `validation/score_evaluator.py`, `tests/unit/test_gaps_score.py` (mới).

RED: mọi ca §7 của đặc tả cho S07–S11 (idle, cắt chuỗi, occupied, double, buổi 1 tiết, ngày rảnh,
unit, target lớn hơn số ngày), unit đúng trong `RuleScore`, Score 1.2.

## Task 5 — Compiler S07, S08, S11

Files: `constraints/soft.py` (hoặc module mới `constraints/gaps.py` không dùng chung helper với
evaluator), `tests/unit/test_soft_compilers.py` (thêm ca).

RED: raw đúng với placement cưỡng bức, không objective; range guard. Hiện thực `teach`, tiền tố/hậu tố,
`idle` bằng equality Boolean; S11 reified hai chiều; S07 theo hệ số placement.

## Task 6 — Compiler S09, S10

Files như Task 5. RED: chuỗi dài nhất bằng big-M exact (reset khi không idle), excess; S10 theo ngày và
buổi, ngày có occupied không rảnh. Đo số biến/hạng tử trên fixture 6 ngày × 2 buổi × 5 tiết để có số
tham chiếu (không tuyên bố hiệu năng).

## Task 7 — Pipeline

Files: `tests/integration/test_gaps_solver.py` (mới).

Ca: 0.4 → 1.5, LEXICOGRAPHIC_OPTIMAL trên fixture có đánh đổi đã tính tay; occupied work làm đổi
optimum; compiler cố ý sai → MODEL_INVALID/score mismatch, không xuất lịch; 0.3 vẫn 1.4.

## Task 8 — Oracle vét cạn và ordering (D6)

Files: `tests/properties/test_gaps_oracle.py` (mới, oracle Python tự viết).

≥ 60 seeds nhỏ (≤ 4 occurrence, 2–3 ngày, 2 buổi × 3 tiết, có ô `can_teach=false` và occupied work),
trộn S07–S11 với S01–S06. So FEASIBLE/INFEASIBLE và optimum vector; ordering bật/tắt; spy test cho
allowlist. Nếu không khớp ở chế độ bật ordering → giữ tắt, ghi rõ.

## Task 9 — CLI/package và tài liệu

Files: `tests/integration/test_gaps_cli.py` (mới), `README.md`, `docs/constraint-catalog.md`,
`docs/domain-model.md`, `docs/solver-design.md`, `docs/phase-2c-gaps-report.md` (mới), trạng thái spec
Phase 2 và spec/plan 2C-2.

RED: solve 0.4 → 1.5 → validate/evaluate (Score 1.2); evaluate-score không OR-Tools/compiler;
RESULT_VERSION cho cặp sai. Docs: định nghĩa idle/chuỗi/rảnh, occupied work phải ngoài availability,
GAP_TIMELINE, không có ngưỡng mặc định, không hard mode.

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

Baseline tại `45f63ee`: 1087 passed, 8 skipped (đo ở `f697e41`, cùng source/tests). Báo số thực chạy.

## Rủi ro và giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| Field `occupied_work` làm đổi hash input cũ | Bỏ field khỏi dump/fingerprint khi policy < 0.4; regression hash cứng |
| Định nghĩa gap lệch giữa compiler và evaluator | Hai hiện thực độc lập + oracle thứ ba; ca tay cho can_teach=false/occupied |
| Big-M chuỗi idle sai ở biên | M = số period của buổi; test chuỗi bị cắt và chuỗi dài nhất ở đầu/cuối |
| Model lớn (biến theo GV × ngày × buổi × period) | Chỉ tạo bucket cho GV trong scope và buổi trong `session_ids`; đo số hạng tử Task 6 |
| Timed calendar khó định nghĩa | D4 từ chối rõ (GAP_TIMELINE) thay vì đoán |
