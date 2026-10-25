# vnEdu TKB — Scheduling Core

Phase 0: package Python độc lập, versioned domain contracts và kiểm tra JSON đầu vào.
Chưa có CP-SAT solver, preprocessing, independent schedule validator hoặc lệnh solve.
Không có Electron, React, SQLite, HTTP server hoặc vnEdu adapter.

## Chạy local

Python 3.12+ và [uv](https://docs.astral.sh/uv/) được yêu cầu.

```sh
uv sync --locked
uv run python -m tkb_core.cli validate-input tests/fixtures/feasible_small.json
uv run tkb-core validate-input tests/fixtures/feasible_small.json
uv run pytest
uv run ruff check .
uv run ruff format --check src tests
uv run mypy
uv build
```

`uv.lock` pin runtime/dev và extra `solver`. Phase 0 chỉ cài Pydantic và tooling dev;
không cần cài OR-Tools. Extra solver dành cho Phase 1, chưa phải chức năng đã có.

Source distribution dùng allowlist; không chứa nghiên cứu, file STKB hay collection
Postman. Integration test kiểm tra nội dung cả sdist và wheel.

Contract là schema nội bộ synthetic, **không phải schema API vnEdu**. CLI thành công chỉ
xác nhận cấu trúc/tham chiếu, không chứng minh lịch có thể xếp được. Mọi fixture dùng ID giả.

## Tài liệu

- [Đặc tả Core First](docs/VNEDU_TKB_CORE_FIRST_CODEX.md).
- [Thiết kế tổng thể](docs/superpowers/specs/2026-10-25-scheduling-core-design.md).
- [Giả định và giới hạn](docs/assumptions.md).
- [Domain contract v1](docs/domain-model.md).
- [Kết quả nghiệm thu Phase 0](docs/phase-0-report.md).

Nghiên cứu trước nằm trong `docs/research/`, `research/`, `reverse-engineering/` và được
giữ riêng với package. Không dùng dữ liệu thật từ đó làm fixture, không sao chép mã engine.
