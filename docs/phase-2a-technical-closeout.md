# Chốt mốc kỹ thuật Phase 2A — 2026-11-05

**TECHNICAL_ACCEPTED_WITH_STATED_LIMITATIONS.** Người dùng đã chọn rõ:
“Chốt mốc kỹ thuật, bàn giao các hạn chế vận hành riêng”. Đây là chốt phạm vi
kỹ thuật synthetic của Phase 2A, không phải nghiệm thu vận hành/production.
Không đổi verdict benchmark cũ, không áp dụng draft nghiệm thu v2 và không mở 2B.

## Snapshot được bàn giao

- Base HEAD: `537c89125c0e1a81173cd099f08f014194d249b4`.
- Wheel: `vnedu_tkb_core-0.2.0-py3-none-any.whl`, SHA256
  `382a54ba845ce30325670d72a06d13a0b06e2dcd7702fec398e7c262f4d3eead`.
- uv.lock SHA256: `fe404cb126bce893368517318d4982b5f7842990429467d2a793af066c2e4c3b`.
- Python3.12.3 / OR-Tools9.15.6755; source layout `src/tkb_core/`.
- Candidate còn uncommitted. Base HEAD/core-tree không phải định danh của các
  thay đổi chưa commit; source hash, wheel và patch mới là căn cứ bàn giao snapshot.
  Không có commit, merge hay push được thực hiện để chốt mốc này.

## Điều kiện kỹ thuật đã có bằng chứng

| Điều kiện Phase 2A | Bằng chứng được giữ lại |
|---|---|
| S01–S04 đúng parameter/scope/unit/weight/priority | Strict contracts, compiler/evaluator tests; typed registry; không suy policy từ STKB/FET |
| Giữ hard feasibility, demand, duration1/2, locks và optional rooms | Independent validator, native tiny cases, exhaustive/ordering oracles |
| Tối ưu lexicographic P1–P3 và cải thiện fixed baseline trên fixture | Quality oracle, priority/weight tradeoff, baseline-improvement regressions |
| Status/proof/incumbent/budget đúng semantics | Stage regressions; freeze chỉ tier proved; giữ incumbent đã kiểm; full-vector tie fix giữ đúng raw status/bound |
| Input1.0 không bị tự migrate; input1.1/policy0.1/output1.2 | Compatibility/hash/serialization/capability regressions |
| CLI/package và scoring không cần OR-Tools | Installed solver/no-solver preflight, CLI roundtrip và guarded independent scoring |
| Quan trắc nằm ngoài product | Native-call harness, argument/result/parameter preservation và receipt/source hash tests |

Kết quả kiểm tra **đã thực chạy ở lượt triển khai trước**, được đối chiếu lại bằng
hash trong lượt chốt này:

| Lệnh | Kết quả đã lưu |
|---|---|
| `uv sync --locked --extra solver` | PASS |
| `uv run --extra solver pytest` | 361 passed |
| `uv run --extra solver pytest tests benchmarks/tests` | 726 passed, 8 skipped |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests` | PASS, 57 files |
| `uv run mypy` | PASS, 28 Core files |

7 skips cần Windows native;1 cần historical installed-wheel opt-in. Current wheel
đã có preflight riêng; các skips không được coi là Windows candidate đã chạy.
Kết quả đầu tiên có lỗi setup fixture được giữ trong log lịch sử; chỉ kết quả full
suite cuối cùng 726/8 được dùng làm bằng chứng PASS. Source review đã ghi không có
important finding trong lượt triển khai.

Trong lượt chốt này không chạy lại native tests, solver hoặc campaign. Đã kiểm
lại đủ249 manifest entries, 28/28 Core files khớp source/wheel/cả hai installed venvs,
và observer/controller source khớp snapshot đã kiểm thử. Đây là xác nhận snapshot
hiện tại đúng byte với evidence, không tuyên bố một lần chạy tests mới.

## Hạn chế vận hành bàn giao riêng

| Hạng mục | Trạng thái được giữ nguyên |
|---|---|
| Pilot Linux mới nhất | Hard-valid FEASIBLE `[0,5,120]`; independent score khớp; zero NOT_MET |
| Tài nguyên pilot, n=1 | Launch-to-exit56,533945s; peak RSS410.972.160bytes; trong watchdog/RSS target |
| Primary current candidate | **0/108**, controller STOPPED; không retry/resume |
| Chất lượng giáo vụ | Chưa được chấp nhận;120/300 periods ngoài khung ưu tiên, P3 NOT_RUN |
| Native cutoff | Call3 UNKNOWN ở cap12 deterministic seconds; call5 FEASIBLE sau13,70/17,89s; nhánh cutoff nội bộ chưa chứng minh |
| Windows/cross-OS của candidate | Chưa có current native campaign và exchanged-result validation; evidence Windows ở snapshot cũ không thay thế |
| Draft nghiệm thu v2 | Vẫn DRAFT, D1–D3 chưa được phê duyệt/triển khai; không tự đổi gate zero |
| Git integration | Các thay đổi chưa commit/merge/push; bản clone từ remote có thể thiếu candidate |

Các mục này tiếp tục là công việc vận hành/chất lượng còn mở. Chúng không được
đổi thành PASS bằng quyết định chốt mốc kỹ thuật. Chưa có SLA trường thật, không
tuyên bố tối ưu toàn cục từ FEASIBLE, không coi mọi nguyện vọng là hard.

## Gói bàn giao local

Thư mục mới: `benchmarks/artifacts/phase2a/technical-closeout-20261105-v1/`.
Gói: `phase2a-technical-handoff.zip`, kèm `SHA256SUMS`, inventory và kết quả kiểm
reconstruction/hash. Gói gồm source/tests/tooling cần thiết, lock/config, wheel
đúng hash, patch từ base và các tài liệu chỉ rõ phạm vi/hạn chế.

Không chứa installed venv, third-party source/binary, dữ liệu STKB thật,
credentials hoặc raw campaign history. Verification summary trong gói là tóm tắt
evidence đã giữ tại máy này, không thay thế toàn bộ raw receipts của campaign.
Không upload/gửi gói hoặc tự commit/push để chuyển máy.

**Lưu ý khi sang Claude Code cloud:** dùng snapshot/patch trong gói thay vì chỉ
clone remote rồi giả định đã có mọi thay đổi. Kiểm manifest và source/wheel hash;
làm việc trên checkout mới. Gói không tự ủy quyền solver/campaign, sửa gate hoặc
triển khai Phase 2B. Phase2B hard variants cần đặc tả và review riêng; 2C/gaps,
repair, API/Desktop vẫn ngoài phạm vi 2A.

## Hồ sơ tham chiếu

- [Đặc tả Phase 2](superpowers/specs/2026-10-26-phase-2-quality-design.md).
- [Mốc triển khai và lịch sử nghiệm thu 2A](phase-2a-report.md).
- [Candidate mới nhất, native trace và kết quả kiểm tra](phase-2a-incumbent-trace-report.md).
- [Đề xuất nghiệm thu v2 — chưa có hiệu lực](phase-2a-acceptance-v2-draft.md).

Phần bổ sung của lượt này chỉ là biên bản chốt, liên kết trạng thái trong báo cáo
và gói bàn giao mới. Product/harness source, gates, pins, research và mọi evidence
cũ giữ nguyên. Các kiểm tra gói chỉ dùng filesystem, checksum và Git apply trên
snapshot tạm; không có native solve hoặc campaign mới.
