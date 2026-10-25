# PHASE: 1 — Scheduling MVP, tiết đơn và tiết đôi

Trạng thái: **đạt tiêu chí nghiệm thu Phase 1**, 2026-10-26. [Thiết kế](superpowers/specs/2026-10-26-phase-1-design.md),
[kế hoạch](superpowers/plans/2026-10-26-phase-1.md). Không thực hiện Phase 2.

## Implemented

- Revalidated owned snapshot, occurrence IDs ổn định, split đơn/đôi bảo toàn demand.
- Timeline symbolic/timed, availability toàn footprint, domain preprocessing,
  necessary load/room checks, khóa time/room riêng, capacity metadata và resource guards.
- CP-SAT Boolean placements, ExactlyOne và indexed AtMostOne trên resource/time token.
- Validator Python độc lập: không import solver/preprocessing và không dùng model helpers.
- Output solver 1.1, đọc output 1.0 đúng shape cũ; status/metadata/phân biệt chưa chạy solver.
- CLI solve/validate-schedule, stale fingerprint check, atomic output, path/symlink/hardlink guard.
- Fixtures synthetic, adversarial validation, status tests và 20 tiny exhaustive oracle cases.

## Files changed

Thêm `domain/errors.py`, `contracts/capabilities.py`, `preprocessing/`, `constraints/`,
`solver/{options,model_builder,cp_sat}.py`, `validation/` và tests unit/integration/properties.
Chỉnh output contract, CLI, AGENTS/README, package metadata/lock và tài liệu Phase 1.
Không thay `research/`, `reverse-engineering/` hoặc collection Postman.

## Commands / test results

| Lệnh/kiểm tra thực tế | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS, OR-Tools 9.15.6755 được cài theo lock |
| `uv run --extra solver pytest -q` | **143 passed in 4.11s**, lần full suite sau final fix |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` | PASS, 30 Python files |
| `uv run mypy` | PASS, 21 source files, strict |
| `uv build --offline` | PASS, wheel/sdist package 0.2.0 |
| CLI six synthetic fixtures | 4 OPTIMAL/valid, 2 INFEASIBLE; không xuất assignments lỗi |
| Tiny exhaustive oracle | 20 seeds, kết luận feasibility khớp, không dùng model helpers |
| Installed wheel + solver extra | Solve room_required thành công, output 1.1, 2 block assignments |
| Installed wheel không extra | Solve trả UNSUPPORTED_FEATURE/SOLVER_NOT_INSTALLED, exit 2 |
| Installed wheel không extra chạy validator | Kiểm lại room_required result thành SCHEDULE_VALID, exit 0 |
| Sdist/wheel content test | PASS, không chứa research, STKB, Postman hoặc dữ liệu ngoài allowlist |

Môi trường đã kiểm: Linux, Python 3.12.3, OR-Tools 9.15.6755, Pydantic 2.14.1,
pytest 9.1.1, ruff 0.17.2, mypy 2.4.0. Các vòng RED→GREEN có chạy thật cho
preprocessing, validator, solver/output và CLI. Test timeout mapping deterministic
và tiny-budget smoke không giả định một fixture chắc chắn timeout trên mọi máy.

Các fixture có nghiệm: feasible_small (3 assignments), feasible_double (2),
locked_lessons (3), room_required (2). infeasible_teacher và double_blocked được
prechecks chứng minh vô nghiệm. Test Hall-subset riêng qua prechecks nhưng phải
chạy CP-SAT mới ra INFEASIBLE. Test 5 tiết `[2,1,1,1]` tạo đúng bốn occurrences
cho demand đó, không thêm/bớt tổng tiết.

Offline isolated resolver ban đầu chưa có registry metadata của OR-Tools trong cache;
đã chạy lại installed-wheel smoke có mạng để resolve dependencies, không đổi pin.
Không coi thiếu cache là lỗi core hoặc báo thử nghiệm offline đó đã pass.
Sau khi cache được nạp, fresh wheel cuối đã chạy lại offline: solve có extra,
validator không extra, missing-extra diagnostic và cyclic-output JSON regression
đều PASS. Import validator trong môi trường không extra không nạp module OR-Tools.

Fresh whole-branch review đã chạy 141 tests ở snapshot trước final fix; không tìm
thấy lỗi tính đúng của scheduling. Reviewer phát hiện cyclic output symlink làm
CLI trả traceback thay vì JSON: đã tái hiện bằng subprocess test RED, sửa tại
path resolution và chạy GREEN + toàn suite. Không catch mọi RuntimeError để giấu
lỗi không liên quan. Không có deferred minor chưa xử lý.

## Quyết định và rủi ro được giữ rõ

- Metadata output 1.1 tách khỏi 1.0 để giữ đúng shape reader cũ; thay đổi schema
  không được gọi nhầm là backward compatible nếu gắn nhãn 1.0.
- Lỗi symlink được nâng mức ưu tiên vì phá machine-readable CLI contract, dù
  không làm mất input. Đã sửa có regression, không chỉ thay thông báo.
- Performance/memory production chưa chứng nhận: guards cấu hình được, trường lớn
  có thể cần tuning; không dùng test timing làm cam kết tốc độ.
- Windows chưa kiểm: cần Windows CI/filesystem tests trước phân phối Desktop.
- Policy/dữ liệu trường thật chưa xác minh: fixtures synthetic không đủ chứng nhận
  số tiết/calendar/ràng buộc của một trường hoặc API vnEdu.
- Phase 2/3 không thuộc nhiệm vụ: hard-valid không bảo đảm ít gaps, đẹp hoặc ít
  xáo trộn. Chưa public progress callback/worker IPC.

## Git và vị trí làm việc

Code được thực hiện/commit ở branch `feat/phase-1`, worktree `.worktrees/phase-1`;
không merge vào main hoặc push tự động. Kế hoạch/thiết kế cũng được lưu trong repo.
Report này và git history giữ kết quả khi scratch ledger được dọn.

## Benchmark results

Not run. Các bài brute-force/oracle là kiểm thử tính đúng, không phải benchmark
STKB/FET/core hoặc cam kết số lớp/thời gian production.

## Known limitations

Một lớp/GV mỗi requirement, duration 1/2 và split khai báo trước. Chưa soft objective,
repair, travel, subgroup membership, tuần A/B, progress callback public, IPC/UI/API/SQLite.
Timed block không vượt gap dương; symbolic break phải khai báo can_teach=false/period gap.
Chưa kiểm Windows hoặc dữ liệu trường thật; input synthetic không phải schema vnEdu.

## Open business questions

Nguồn demand thực, lịch giờ/break/availability, metadata phòng, hard/soft và mức chất
lượng trường chấp nhận. Không tự đoán các câu trả lời để lấy lịch hợp lệ giả.

## Next step

Chỉ sau nghiệm thu Phase 1 mới thiết kế/triển khai Phase 2 theo yêu cầu tiếp theo.
Không tự bắt đầu quality optimization, repair hoặc đồng bộ server.
