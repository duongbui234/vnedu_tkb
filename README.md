# vnEdu TKB — Scheduling Core

Phase 1: Python core độc lập, input contract 1.0, hard-feasibility CP-SAT solver cho
tiết đơn/đôi, preprocessing và independent schedule validator. Output solver là 1.1;
reader vẫn đọc/serialize đúng shape output 1.0.
Không có Electron, React, SQLite, HTTP server hoặc vnEdu adapter.

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

Contract là schema nội bộ synthetic, **không phải schema API vnEdu**. `validate-input` chỉ
xác nhận cấu trúc/tham chiếu, không chứng minh lịch có thể xếp được. Mọi fixture dùng ID giả.

## Tài liệu

- [Đặc tả Core First](docs/VNEDU_TKB_CORE_FIRST_CODEX.md).
- [Thiết kế tổng thể](docs/superpowers/specs/2026-10-25-scheduling-core-design.md).
- [Giả định và giới hạn](docs/assumptions.md).
- [Domain contract v1](docs/domain-model.md).
- [Thiết kế Phase 1 đã duyệt](docs/superpowers/specs/2026-10-26-phase-1-design.md).
- [Model và trạng thái solver](docs/solver-design.md).
- [Danh mục hard constraints](docs/constraint-catalog.md).
- [Kết quả Phase 1](docs/phase-1-report.md), [lịch sử Phase 0](docs/phase-0-report.md).

Một block đôi là một assignment chiếm hai period liền nhau cùng buổi. Không qua slot
nghỉ hoặc gap dương trong timed calendar. Không có objective chất lượng ở Phase 1:
OPTIMAL của bài feasibility không có nghĩa lịch đẹp nhất. Nghiệp vụ chưa hỗ trợ
(nhiều GV/lớp, block >2, enabled custom rules) bị từ chối rõ ràng.

Nghiên cứu trước nằm trong `docs/research/`, `research/`, `reverse-engineering/` và được
giữ riêng với package. Không dùng dữ liệu thật từ đó làm fixture, không sao chép mã engine.
