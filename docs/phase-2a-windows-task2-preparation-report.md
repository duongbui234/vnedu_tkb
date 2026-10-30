# Windows Task 2 — Báo cáo chuẩn bị bàn giao 2026-10-30

**PREPARED_NOT_AUTHORIZED / WINDOWS BLOCKED.** Chỉ chuẩn bị trên main theo
[checklist](phase-2a-windows-preflight-handoff-checklist.md) và
[kế hoạch triển khai](superpowers/plans/2026-10-30-windows-task2-handoff.md).
Không có Windows install/Core tests/mini solve hoặc campaign mới.

## Bộ bàn giao

- [Runbook PowerShell](phase-2a-windows-task2-runbook.md): intake, approval mới,
  receiver hashes, export/install pinned dev/solver/no-solver, installed identity,
  Core suite, tiny smoke/registry/no-solver và verification36datasets, final evidence.
- [Hai mẫu intake/transfer](phase-2a-windows-preflight-handoff-templates.md): null
  và reason, staging read-only theo quy trình, approval NOT_GRANTED, receiver NOT_RUN.
- [Inventory sender](windows-task2-payload-inventory.json): **235 file**, gồm
  67frozen source/tests/config,118bundle files của36datasets,1Core wheel,
  41Linux reference files,2tooling files,1fake-test source reference và5docs.
  Không tạo payload directory/archive; không copy bytes sang Windows.
- `benchmarks/windows_payload.py`: đọc Git blobs/local bytes để tạo inventory;
  receiver verifier kiểm exact membership/size/hash, reject traversal, Windows
  reserved paths, duplicate/case collisions, symlinks/junctions. Chỉ hash match,
  không cấp approval hoặc Windows PASS.
- `benchmarks/windows_preflight.py`: native win32/x64/Python3.12/isolation/reference
  gate; output không overlap payload, output exclusive; mỗi native invocation kiểm
  lại inventory/installed source identity. Bundle/scorer chặn search imports;
  registry phát hiện cả attempted forbidden import bị Core bắt lại.

Inventory chứa origin+destination+size+sender SHA256 từng file; receiver hashes
vẫn null/reason. Source lấy đúng Git commit
`4cfa643148b967ad7baf674fe6439699afbe51e2`, Core tree
`1efd459b2514f448dcf4ac297989de09eb76a3a1`, không lấy Core source của HEAD.
Wheel/lock/root bundle manifest giữ đúng3hash trong checklist. Đã kiểm tất cả
child manifests và raw bundle file hashes/membership bằng standard library;
không import Core để search hoặc regenerate. Chưa revalidate/score36trên Windows.

Các đường dẫn frozen receipts/provenance Linux được giữ nguyên, chỉ là reference;
không chỉnh thành Windows paths, không gán Linux PASS thành Windows PASS. Payload
inventory không tự chứa chính nó. Báo cáo này không nhúng hash inventory để tránh
vòng hash; phải lấy hash inventory cuối qua kênh bàn giao được duyệt.

## Kiểm chứng thực tế trên Linux

| Command/kiểm tra | Kết quả |
|---|---|
| `uv run --no-sync --extra solver pytest benchmarks/tests/test_windows_handoff.py -q` | **36 PASS**; fake-only orchestration và pure input-contract check, CpSolver/subprocess.run bị chặn trong tests |
| `uv run --no-sync ruff check .` | PASS |
| `uv run --no-sync ruff format --check src tests benchmarks` | PASS57files |
| `uv run --no-sync mypy` | PASS27Core source files; không phải extended mypy cho tooling |
| `git diff --check` | PASS trên tracked diff; Python formatting và kiểm whitespace riêng cho docs mới |
| `python3 -B` gọi `build_inventory(Path.cwd())` rồi ghi JSON inventory | Đã thực hiện; đọc sources/Git blobs, không materialize/copy payload |
| `python3 -B` tái tạo inventory trong bộ nhớ và đối chiếu JSON/files/hashes | PASS; receiver null, source commit/tree, bundle membership và index rỗng |
| `command -v pwsh` | Không tìm thấy; chưa parse/chạy PowerShell trên host này |

TDD đã quan sát RED lúc module chưa tồn tại và khi tiny input thiếu session_ids;
pure contract regression phát hiện và sửa fixture. Fresh review phát hiện overlap
output/payload và guard ImportError bị nuốt;4regressions RED→GREEN. Fake tests bao
phủ corruption/missing/extra/duplicate, Windows paths/case, links, no approval from
hash, no retry và failure receipt, no-solver versions, editable/source bytes,
Linux gate trước Core/files, independent score mismatch và attempted imports.
Author bổ sung regression RED→GREEN để giữ exact stdout/stderr bytes (kể cả CRLF
và stderr không phải UTF8), không decode/re-encode raw child logs.

Fresh reviewer read-only: không còn Critical/Important trong tooling/runbook đã
review; reviewer không chạy tests/native và chưa review inventory/report cuối.
Author kiểm lại inventory/report sau đó bằng các commands nêu trên.

## Blockers và giới hạn còn lại

1. Chưa có native Windows intake/provenance, approved machine/paths, workload/power
   observations hoặc approval Task2 gắn inventory hash. Null/UNKNOWN giữ nguyên.
2. Chưa materialize/transfer/receiver-verify payload; inventory prepared không là
   kết quả kiểm bytes ở Windows. Chưa có Windows binary-wheel availability,
   platform-resolved requirements, download/install/import/package evidence.
3. Packaging test của full Core suite gọi `uv build --offline` cần build backend
   Hatchling1.32.4/cache/dependency evidence riêng; backend không trong uv.lock.
   Thiếu cache là blocker, không skip test, đổi pin hoặc rebuild wheel để thay frozen.
4. PowerShell7.4+ capture method chưa được chạy/parse; probe native path handling,
   pyvenv/metadata behavior và binary compatibility chưa được kiểm trên Windows.
   **Minor deferred:** PowerShell GetFullPath check là lexical, chưa tự loại trừ
   ancestor junction aliases của staging/evidence/dev/venv roots. Người vận hành
   phải xác minh roots không alias/overlap trong intake trước approve; Python probe
   có resolved output/payload check nhưng không bảo vệ các bước install PowerShell.
5. Chưa có full Core suite, tiny quality solve, registry/no-solver và36dataset
   validation/scoring trên Windows, nên chưa thể WindowsTask2PASS. API check PASS
   hoặc exit0 không đủ nghiệm thu. Installed identity chỉ chứng minh bytes/path,
   không phải performance hoặc attestation.

Không chạy `uv sync`, full pytest, build/install, native tests/solver/search/profiling.
Dedicated fake suite dùng tools đã có với `--no-sync`; không thêm dependency.
Không sửa `src/`, existing `tests/`, generator/runner frozen, pyproject/lock,
budget/guards, research hoặc raw Linux artifacts. Thay đổi AGENTS.md từ lượt trước
và mẫu tài liệu untracked trước tác vụ được giữ; chưa stage/commit/push.

Task3–5Windows/cross-OS performance, Phase2B/2C không được triển khai. Linuxfailed63,
ba repeats/fingerprint và WindowsBLOCKED trong evidence lịch sử giữ nguyên.
