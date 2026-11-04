# Phase 2B — rà soát diff `91c16da..1e07961`

Ngày 2026-11-05. Phạm vi: 30 files (+1386/−40) của commit `1e07961`, đối chiếu với
[đặc tả 2B](superpowers/specs/2026-11-05-phase-2b-hard-variants-design.md). Không sửa product code
hay tests; không pilot/campaign. Người rà soát cùng phiên với người triển khai: đây là rà soát
lại có probe/red test, **không** phải review của một người thứ hai độc lập.

**Kết luận: 0 finding P1/P2; 1 finding P3 (có từ trước 2B, 2B mở rộng sang 1.3); 3 quan sát.**
**Cập nhật: F1 đã sửa theo TDD (xem cuối mục F1); O2 đã ghi vào catalog.**

## Finding

### F1 (P3, có từ trước 2B) — input 1.0 không kiểm version của result

`cli.py:177` chỉ kiểm `RESULT_VERSION` khi `problem.schema_version == "1.1"`. Với input 1.0, chỉ
fingerprint được so; một result 1.3 (hoặc 1.2) có fingerprint 1.0 và assignments hợp lệ vẫn được
`validate-schedule`/`evaluate-score` chấp nhận (exit 0), dù input 1.0 chỉ sinh output 1.1.

- Red test (ngoài `tests/`, không sửa product code):
  `/tmp/…/scratchpad/review/test_review_red.py` — **2 failed** (cả hai lệnh trả 0, mong đợi 2).
- Cùng test với result 1.2/policy 0.1 chạy trên worktree tạm của `91c16da`: **2 failed** → gap có
  từ Phase 2A; 2B đổi đúng dòng này nhưng giữ nguyên điều kiện.
- Ảnh hưởng: chỉ là nhãn version mâu thuẫn trên dữ liệu forged; assignments vẫn bị validator kiểm
  lại theo input 1.0, nên không làm lịch sai thành hợp lệ.
- **Đã sửa (được người dùng ủy quyền):** `cli.py` luôn kiểm version: input 1.1/0.1 chỉ nhận 1.2,
  1.1/0.2 chỉ nhận 1.3; input 1.0 nhận result legacy 1.0/1.1 (giữ tương thích Phase 0/1) và từ chối
  1.2/1.3 bằng `RESULT_VERSION`. Regression trong `tests/integration/test_hard_variants_cli.py`:
  4 ca (1.2/1.3 × hai lệnh) RED trước sửa, GREEN sau sửa; thêm ca input 1.0 + result 1.1 vẫn exit 0.

## Quan sát (không phải lỗi so với đặc tả)

- **O1 — Range guard bất đối xứng.** Hard S02/S03 `limit = 2**63`: `solve` trả
  `INPUT_INVALID/HARD_RULE_RANGE`, còn `validate_schedule`/`evaluate_score` chấp nhận lịch. Đúng §5.2
  (giới hạn kỹ thuật của model) và giống `OBJECTIVE_RANGE` của 2A.
- **O2 — Lock vượt hard S02/S03.** Lock `r::1`@1-AM-1 (đôi) + `r::2`@1-PM-1 với hard S03 limit 2 →
  `INFEASIBLE` qua solver, không phải `LOCK_CONFLICT`. Hợp lý vì từng lock không sai, chỉ tổ hợp
  của chúng vô nghiệm; đặc tả chỉ nêu LOCK_CONFLICT cho S01/S04. Đã thêm một câu vào catalog.
- **O3 — Giới hạn coverage của oracle.** `test_hard_variant_oracle.py` chỉ có calendar symbolic,
  rule global scope, không lock/phòng; scope, timed alias và lock được kiểm bằng unit tests. Không có
  test riêng khẳng định zero-probe clone chứa ràng buộc hard (đã ghi ở báo cáo 2B).

## Đã kiểm, không phát hiện lỗi

| Điểm | Cách kiểm |
|---|---|
| Lọc domain S01/S04 trước lock/prechecks; 0.1 giữ domains | Đọc `feasibility.py`; tests domain; probe window ngoài calendar → EMPTY_DOMAIN đúng nghĩa |
| S02/S03 thêm trước clone `hard_model`, bucket = start slot × duration | Đọc `hard.py`/`model_builder.py`/`cp_sat.py`; test compiler thiếu → MODEL_INVALID |
| Overlap mọi mode, 0.1 giữ lỗi `CUSTOM_HARD_RULE` | Đọc `registry.py`; probe timed alias hard S01 + soft S01 → OVERLAPPING_RULES |
| Validator `HARD_*` độc lập | Đọc `independent_validator.py`; test chặn import compiler/solver |
| Ordering D5 chỉ với S01–S04 hard của 0.2 | Đọc guard; oracle 60 seeds bật/tắt ordering |
| Cặp 1.2↔0.1, 1.3↔0.2 trong contract, `solve`, CLI (input 1.1) | Đọc `output.py`/`cp_sat.py`/`cli.py`; tests contract/CLI |
| Benchmarks không bị ảnh hưởng | `run_benchmarks.py`/`windows_preflight.py` vẫn đòi 1.2; generator chỉ tạo policy 0.1 |

## Lệnh đã chạy

| Lệnh | Kết quả |
|---|---|
| `uv run --extra solver python …/review/probe.py` | 5 probe; chỉ P1 lộ gap (F1) |
| `uv run --extra solver pytest …/review/test_review_red.py` | 2 failed (red, như dự định) |
| Cùng test với 1.2/0.1 trên worktree tạm `91c16da` (đã xóa) | 2 failed |
| `uv run --extra solver pytest tests benchmarks/tests` | 897 passed, 8 skipped |
| `uv run ruff check .` | PASS |
| `uv run mypy` | PASS, 29 source files |

Probe và red test nằm trong scratchpad phiên (ngoài repo, mất khi container bị thu hồi).
File này được commit cùng bản sửa F1.
