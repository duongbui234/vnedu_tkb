# Windows Task 2 — hoàn thiện bộ bàn giao, không thực thi native

Scope được user duyệt: chuẩn bị trọn bộ trên main; không copy payload sang Windows,
cài đặt, chạy native tests/solver/search/profiling, sửa Core/budget/guards, commit/push.
Spec: `docs/phase-2a-windows-preflight-handoff-checklist.md` và hai mẫu intake/transfer.

Thiết kế: standard-library tooling ngoài Core; đọc Git objects của frozen commit
để inventory source/tests/config, đọc nguyên wheel/bundle/evidence Linux; không
materialize payload. Probes dùng installed Core sau native gate; fakes kiểm logic
điều phối trên Linux, không là nghiệm thu Windows. Không dùng runner Linux.

## Task 1 — Inventory đầy đủ và verification

- Tạo `benchmarks/windows_payload.py`: `build_inventory(repo: Path) -> dict`,
  `verify_payload(root: Path, inventory: dict) -> dict`; CLI `inventory --repo`,
  `verify --root --inventory`, xuất JSON stdout, không copy/install.
- Inventory: source bytes từ frozen Git commit; wheel/lock/full36 bundle,
  reference evidence/probes, tooling/runbook/checklist/templates mới; SHA256/size,
  origin và destination riêng, sender verified/receiver NOT_RUN.
- Tests trước code tại `benchmarks/tests/test_windows_handoff.py`: corruption,
  missing/extra files, duplicate/traversal/Windows paths, symlinks, null receiver,
  full bundle membership và root/child hashes. Chạy RED rồi GREEN bằng no-sync pytest.

## Task 2 — Native probes có gate, kiểm bằng fakes

- `benchmarks/windows_preflight.py`: CLI environment, bundle, smoke, registry,
  guard-score. Mỗi CLI yêu cầu win32/x64, isolation và explicit approval reference;
  không gọi solve khi import, verify inventory hoặc chạy fakes.
- Environment đối chiếu package/site-packages/wheel/source/lock, không `/proc`.
  Bundle dùng frozen generator `verify_bundle` với import guard chặn native solver.
  Smoke giữ default budget60/workers1/seed42/guards; tiny input duration1/2,
  S01–S04/3tiers; invalid/stale cases, no-solver guard và registry checks.
- Tests dùng fake CLI, metadata, filesystem; chặn CpSolver và subprocess phát sinh.
  Coverage: platform/approval rejection trước imports, mismatch/rejection semantics,
  default options, no-solver import boundary, exclusive output/no retry.

## Task 3 — Runbook, receipts và kiểm chứng

- Tạo runbook PowerShell theo gates: intake → approval → receiver hash → install
  pinned dev/solver/no-solver → installed checks → Core suite → tiny probes →36
  validation/scoring không search → review evidence. Không tự chạy các bước native.
- Cập nhật checklist/templates chỉ để liên kết bộ bàn giao và làm rõ scopes.
- Tạo `docs/windows-task2-payload-inventory.json` từ chỉ-đọc nguồn sau khi docs/tools
  ổn định; không hash chính inventory vào nó. Report ghi counts, actual commands,
  blockers, fake-only limits; không Windows PASS/performance claim.
- Chạy dedicated fake suite, no-sync ruff/format/mypy, diff check. Không uv sync,
  full pytest, build/install hoặc native probes trên Linux. Author tự kiểm diff;
  fresh reviewer xem code/runbook trước kết luận cuối, không chạy solver.

Review focus: provenance source khác HEAD; Windows case/path traversal và symlinks;
hash verification không là approval; same versions chưa đủ installed-byte identity;
full Core suite có solve nên chỉ là lệnh tương lai sau approval.
