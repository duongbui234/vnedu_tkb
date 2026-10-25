# PHASE: 0 — Foundation và versioned contracts

Ngày nghiệm thu: 2026-10-26. Hoàn thành tiêu chí Phase 0 của
[Core First](VNEDU_TKB_CORE_FIRST_CODEX.md). **Phase 1 chưa bắt đầu.**

## Implemented

- Python src-layout package import/install được, dùng Python 3.12.3 trong kiểm tra.
- Domain và input/output Pydantic v2 schema `1.0`: opaque IDs, strict scalar types,
  uniqueness, references, availability IDs, demand/split và lock references.
- SHA-256 fingerprint canonical, ổn định với thứ tự danh mục/participants/availability/
  rule scope; thay đổi dữ liệu làm đổi hash. Đây không phải preprocessing solver.
- Result contract tách NOT_RUN/FEASIBLE/OPTIMAL/INFEASIBLE/UNKNOWN và lỗi đầu vào;
  chặn valid_schedule không có report/status/hash tương thích.
- CLI `validate-input` qua module và entrypoint installed: JSON stdout, exit codes;
  từ chối malformed JSON, key trùng, NaN/Infinity và schema sai, không echo record.
- Hai fixture synthetic, pytest unit/integration, artifact-content regression.
- uv.lock và dependencies tách runtime/dev/extra solver; ruff và mypy strict.
- Sdist allowlist, wheel độc lập; không đóng gói source nghiên cứu, STKB hoặc Postman.

## Files changed

Workspace ban đầu chỉ có `docs/`, `research/`, `reverse-engineering/`, không có Git,
README, AGENTS hoặc Python package. Không tự init Git, không tạo worktree/commit.
Không sửa dữ liệu/source nghiên cứu.

Các file mới:

- `pyproject.toml`, `uv.lock`, `.python-version`, `.gitignore`, `README.md`, `AGENTS.md`.
- `src/tkb_core/__init__.py`, `src/tkb_core/cli.py`.
- `src/tkb_core/domain/{__init__.py,enums.py,models.py}`.
- `src/tkb_core/contracts/{__init__.py,input.py,output.py}`.
- `tests/conftest.py`, `tests/unit/test_contracts.py`.
- `tests/integration/{test_cli.py,test_packaging.py}`.
- `tests/fixtures/{feasible_small.json,empty_requirements.json}`.
- `docs/assumptions.md`, `docs/domain-model.md`, báo cáo này.
- [Kế hoạch và execution ledger](superpowers/plans/2026-10-25-phase-0.md).

`.venv/`, caches và `dist/` là artifact local đã ignore. Wheel và sdist đã build;
không upload/publish artifact.

## Commands executed / kết quả

| Lệnh | Kết quả thực tế |
|---|---|
| `uv sync --locked` | PASS, 27 packages resolved trong lock, 17 packages checked trong env; không cài extra solver |
| `uv run pytest -q` | **63 passed in 1.48s** ở lần nghiệm thu cuối |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` | PASS, 12 Python files formatted |
| `uv run mypy` | PASS, 8 source files, strict |
| `uv build --offline` | PASS, sdist + wheel |
| `uv run tkb-core validate-input tests/fixtures/feasible_small.json` | INPUT_VALID, checked=contract, solver_executed=false |
| `uv run python -m tkb_core.cli validate-input tests/fixtures/empty_requirements.json` | INPUT_VALID, checked=contract, solver_executed=false |
| `uv run python -c 'import tkb_core'` | PASS; import source package không cần OR-Tools |
| `uv run --no-project --isolated --offline --python 3.12 --with ./dist/vnedu_tkb_core-0.1.0-py3-none-any.whl tkb-core validate-input tests/fixtures/feasible_small.json` | PASS trong môi trường tách biệt chỉ cài wheel + runtime deps |

Môi trường: Python 3.12.3, Pydantic 2.14.1, pytest 9.1.1, ruff 0.17.2, mypy 2.4.0.
OR-Tools 9.15.6755 được pin optional nhưng `ortools_installed=False` trong env Phase 0.

## Review và sửa lỗi có kiểm chứng

- Test đầu thất bại vì chưa có contracts; tests subprocess thất bại trước khi có CLI.
  Sau implementation đã chạy suite thực, không giả lập kết quả.
- Strict boolean regression phát hiện `manage_rooms="false"` bị coerce; chuyển sang
  StrictBool rồi test pass. Type-check phát hiện biến local union bị dùng chung tên,
  sửa binding và chạy mypy pass.
- Fresh review độc lập phát hiện đảo thứ tự rule-scope IDs làm đổi fingerprint.
  Hai regression tests đã tái hiện lỗi trước sửa và pass sau canonicalization.
- Build ban đầu với mặc định sdist đưa cả workspace nghiên cứu/collection vào archive
  local. Kiểm tra nội dung phát hiện; đã thay bằng allowlist, thêm test build artifact,
  thay archive local bằng bản sạch và xóa archive của test thất bại. Không gửi archive
  đó ra ngoài. `.gitignore` tự được Hatchling thêm là metadata được allow rõ.

## Benchmark results

**Not run.** Thời gian pytest/build không phải benchmark scheduling. Không có model
CP-SAT, không đo throughput/quality hoặc so tốc độ STKB/FET/core mới.

## Known limitations

- Chưa normalize, precheck khả thi, model CP-SAT, solve, independent validator,
  validate-schedule, quality, repair, benchmark hoặc runtime worker.
- Input hợp lệ về contract có thể vô nghiệm: Phase 0 không phát hiện tải vượt slot,
  clash giữa các khóa, block qua break, thiếu phòng phù hợp hoặc khóa vào giờ bận.
- Result guardrails chỉ kiểm tính nhất quán shape; report valid từ caller không
  thay independent validator chạy thật. Không sinh lịch trong Phase 0.
- Zero demand/empty requirements hợp lệ về cấu trúc; không xem là dữ liệu trường
  thực đầy đủ. Chưa có adapter diễn giải `so_tiet` hoặc các field vnEdu.
- Chưa hỗ trợ membership nhóm học sinh, cơ sở/travel, tuần A/B, PreviousSchedule;
  chưa compile/evaluate rule declarations. Những phần này được ghi rõ trong
  [assumptions](assumptions.md) và [domain model](domain-model.md).
- Chưa thử Windows, Python versions khác, OR-Tools runtime hay dữ liệu trường thật.
  Model instances mutable; Phase 1 phải revalidate và tạo snapshot riêng.

## Open business questions

Nguồn/đơn vị số tiết thật; calendar/break/availability; scope phòng và tài nguyên
dùng chung; hard/soft/ngưỡng; lớp ghép/đồng giảng; hoạt động chung và lịch cũ.
Không tự chọn câu trả lời hoặc gọi vnEdu để giải quyết ở Phase 0.

## Next proposed step

Phase 1: normalize và occurrence IDs theo contract, prechecks, hard model, CP-SAT,
independent schedule validator và CLI solve/validate-schedule. Chỉ nghiệm thu khi
fixture có nghiệm, fixture vô nghiệm và mọi hard constraint có test/validator đúng.
Không tự chuyển sang Phase 1 hoặc Phase 2 trong nhiệm vụ hiện tại.
