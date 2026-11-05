# Hard feasibility no-LP — review trước commit

Ngày 2026-11-05. **Triển khai và kiểm tra hoàn tất; chưa staged/commit.**
Branch `work/hard-feasibility-no-lp`, worktree `.worktrees/hard-feasibility-no-lp`,
base `120058e5a75d15c11280b126ac364684d5470605`.

## Thay đổi để duyệt

Public quality solve có active priorities và workers1 chọn
`linearization_level=0` chỉ ở native call hard-only feasibility đầu tiên.
`run_quality` có opt-in keyword nội bộ mặc định default, nên hai repair caller
giữ nguyên. Verification, tiers, legacy/no-active quality và workers>1 không
nhận setting mới. Không đổi model, hints, trạng thái, budget, gate, schema,
CLI, dependency hay solver pin. Không thêm fallback hoặc native call.

Candidate kiểm giả thuyết LP overhead; chưa có số đo để kết luận nhanh hơn hay
giải được bất kỳ trường hợp nào trong 30 UNKNOWN. Không chứng nhận hiệu năng.

## Allowlist commit dự kiến — 12 file

- Product (2): `src/tkb_core/solver/objectives.py`, `src/tkb_core/solver/cp_sat.py`.
- Regression (6): `tests/unit/test_stage_parameters.py`,
  `tests/unit/test_hard_feasibility_stage.py`, `tests/unit/test_quality_stages.py`,
  `tests/integration/test_hard_feasibility_native.py`,
  `tests/integration/test_repair_solver.py`,
  `tests/integration/test_tier_two_phase_native.py`.
- Docs (4): `docs/solver-design.md`,
  `docs/superpowers/specs/2026-11-05-hard-feasibility-no-lp-design.md`,
  `docs/superpowers/plans/2026-11-05-hard-feasibility-no-lp.md`, tài liệu review này.

Không gồm raw evidence/ZIP/wheel, venv, logs, credentials, dữ liệu thật,
research/reverse-engineering hoặc 7 tài liệu local có trước ở main.
Hai file product có tổng diff +31/-6 dòng; còn lại là tests và tài liệu.

## Kiểm tra thực tế

| Lệnh | Kết quả cuối |
|---|---|
| `uv sync --locked --extra solver` | PASS, lock không đổi |
| `uv run --extra solver pytest` | 1.118 passed, 44,70s |
| `uv run --extra solver pytest benchmarks/tests` | 446 passed, 8 skipped, 127,55s |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` | PASS, 91 files |
| `uv run mypy` | PASS, 36 source files |
| `git diff --check` | PASS |

8 skip: 7 cần native Windows, 1 cần frozen Task2 installed wheel qua
`TKB_PREFLIGHT_DIR`. Không có preflight hoặc campaign chạy trong lượt này.
Các native solves đã chạy chỉ thuộc regression/oracle tests được duyệt.

TDD: trước product change có 2 regression RED đúng vì thiếu parameter và thiếu
public opt-in, sau sửa GREEN. Nhóm tập trung cuối 68 tests PASS; thêm file
tier-two-phase 5 tests PASS. Full suite đầu tìm ra expectation cũ ở call đầu
của `test_unproved_slice_switches_to_sticky_interleaving`; chỉ đổi tuple mode
đầu sang no-LP, các kỳ vọng verification/slice/interleave giữ nguyên. Full suite
đã chạy lại và PASS như bảng trên.

Regression kiểm exact parameter delta, fake-stage statuses/deadline/incumbent,
model bytes giống nhau default/no-LP, native feasible/UNSAT tiny có phòng,
tiết đôi, khóa và hard S02/S03/S05/S06; lịch valid/score được kiểm độc lập.
Repair BEFORE/AFTER và legacy/no-active solve đều giữ default search.

Review độc lập read-only: **không findings** trong product change và regression;
reviewer không chạy tests/native solver hoặc sửa file.

## Bảo toàn evidence và giới hạn

Đã kiểm lại seal/plan cùng 642 member hashes trong complete receipts và 83
preflight file hashes của campaign-01: khớp. Owner vẫn RUNNING stale với PID cũ,
không reset/move/delete. Run dở dang và journal lịch sử giữ nguyên.
Không sửa installed wheel cũ hoặc measured worktree. Không stage/commit/merge/push.

## Commit message đề xuất

```text
feat(core): isolate no-LP search for initial quality feasibility

Use linearization_level=0 only for the initial hard-only stage of
single-worker public quality solves. Keep repair, verification and tier
searches on their existing paths without changing models or budgets.

Add regression coverage for parameter isolation, model identity,
status/budget handling and hard validity; document the unmeasured
candidate and the separate diagnostic pilot approval boundary.
```

## Bước sau cần duyệt

Chỉ sau khi người dùng duyệt allowlist/diff/message mới stage và tạo một commit
local trên branch này. Không merge/push. Preflight, recovery owner và pilot
6-case là công việc riêng, chưa được mở bởi lượt triển khai hoặc commit.
