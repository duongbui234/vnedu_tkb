# PHASE: 1 — Scheduling MVP, tiết đơn và tiết đôi

Trạng thái: đang nghiệm thu, 2026-10-26. [Thiết kế](superpowers/specs/2026-10-26-phase-1-design.md),
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

Kết quả cuối sẽ được ghi sau fresh review và toàn bộ checks; không dùng kết quả
trung gian làm tuyên bố nghiệm thu. Các chu kỳ RED→GREEN đã được thực hiện cho
preprocessing, validator, solver/output và CLI; ledger nằm trong worktree local.

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
