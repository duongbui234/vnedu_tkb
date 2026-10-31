# vnEdu TKB — Scheduling Core

Phase 2A: Python core độc lập, hard-feasibility CP-SAT cho tiết đơn/đôi và tối ưu
S01–S04 theo ưu tiên P1–P3, có independent hard validator và score evaluator.
Input 1.0 giữ hành vi/hash Phase 1 và phát output 1.1; input 1.1/policy 0.1 phát output 1.2.
Output reader đọc 1.0/1.1/1.2. Không có Electron, React, SQLite, HTTP hoặc vnEdu adapter.

## Chạy local

Python 3.12+ và [uv](https://docs.astral.sh/uv/) được yêu cầu.

```sh
uv sync --locked --extra solver
uv run python -m tkb_core.cli validate-input tests/fixtures/feasible_small.json
uv run tkb-core validate-input tests/fixtures/feasible_small.json
uv run --extra solver tkb-core solve tests/fixtures/feasible_double.json --time-limit 5 --output /tmp/tkb-result.json
uv run tkb-core validate-schedule tests/fixtures/feasible_double.json /tmp/tkb-result.json
uv run --extra solver pytest
uv run ruff check .
uv run ruff format --check src tests
uv run mypy
uv build
```

`uv.lock` pin runtime/dev và extra `solver` (OR-Tools 9.15.6755). Contract và validator
không import OR-Tools; `solve` cần extra solver. Defaults 60 giây, 1 worker, seed 42
là cấu hình thử nghiệm, không phải cam kết hiệu năng.

Source distribution dùng allowlist; không chứa nghiên cứu, file STKB hay collection
Postman. Integration test kiểm tra nội dung cả sdist và wheel.
`[tool.uv] cache-keys` gồm `pyproject.toml`, `README.md` và `src/**/*.py`, nên cài
non-editable lại từ cùng thư mục sẽ build lại khi source đổi, không dùng wheel cũ.

Contract là schema nội bộ synthetic, **không phải schema API vnEdu**. `validate-input` chỉ
xác nhận cấu trúc/tham chiếu, không chứng minh lịch có thể xếp được. Mọi fixture dùng ID giả.

## Tài liệu

- [Đặc tả Core First](docs/VNEDU_TKB_CORE_FIRST_CODEX.md).
- [Thiết kế tổng thể](docs/superpowers/specs/2026-10-25-scheduling-core-design.md).
- [Giả định và giới hạn](docs/assumptions.md).
- [Domain contract v1](docs/domain-model.md).
- [Thiết kế Phase 1 đã duyệt](docs/superpowers/specs/2026-10-26-phase-1-design.md).
- [Đặc tả Phase 2A — S01–S04](docs/superpowers/specs/2026-10-26-phase-2-quality-design.md).
- [Implementation plan Phase 2A](docs/superpowers/plans/2026-10-26-phase-2a.md).
- [Model và trạng thái solver](docs/solver-design.md).
- [Danh mục hard constraints](docs/constraint-catalog.md).
- [Kết quả Phase 2A](docs/phase-2a-report.md).
- [Kết quả Phase 1](docs/phase-1-report.md), [lịch sử Phase 0](docs/phase-0-report.md).

Một block đôi là một assignment chiếm hai period liền nhau cùng buổi. Không qua slot
nghỉ hoặc gap dương trong timed calendar. Tuyến input 1.0 vẫn không có objective chất lượng:
OPTIMAL của bài feasibility không có nghĩa lịch đẹp nhất. Nghiệp vụ chưa hỗ trợ
(nhiều GV/lớp, block >2, mọi custom hard và soft ngoài S01–S04) bị từ chối rõ ràng.
Input 1.0 tiếp tục từ chối mọi enabled custom rule.

Nghiên cứu trước nằm trong `docs/research/`, `research/`, `reverse-engineering/` và được
giữ riêng với package. Không dùng dữ liệu thật từ đó làm fixture, không sao chép mã engine.

## Quality Phase 2A

```sh
uv run --extra solver tkb-core solve tests/fixtures/quality/priority_tradeoff.json --time-limit 5 --workers 1 --seed 42 --output /tmp/tkb-quality.json
uv run tkb-core validate-schedule tests/fixtures/quality/priority_tradeoff.json /tmp/tkb-quality.json
uv run tkb-core evaluate-score tests/fixtures/quality/priority_tradeoff.json /tmp/tkb-quality.json
```

S01 tránh ô mong muốn, S02 vượt tải/buổi, S03 vượt tải/ngày, S04 ngoài khung tiết.
Mỗi penalty tính theo tiết dạy trên toàn block, có weight và priority explicit.
Hard không được nới; chỉ tier có proof OPTIMAL mới được giữ cố định trước tối ưu tier sau.
Timeout giữ incumbent đã hard-validate và score đúng; quality report tách điểm khỏi proof.
Evaluator/CLI evaluate-score không cần OR-Tools. Chưa có hard variants, spacing/gaps hoặc repair.
