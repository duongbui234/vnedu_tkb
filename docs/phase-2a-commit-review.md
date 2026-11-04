# Phase 2A — review và chuẩn bị commit

Ngày2026-11-05. Base `537c89125c0e1a81173cd099f08f014194d249b4`, nhánh
`work/phase2a-operational-completion`. Phạm vi review: mọi thay đổi chưa commit
so với HEAD, gồm các file mới được chọn trong allowlist bên dưới.

**READY_FOR_USER_COMMIT_REVIEW — finding Spec P2 đã được sửa theo ủy quyền.**
Đã cập nhật product/test delta, checks và staged diff để người dùng duyệt commit.
Chưa commit/merge/push; không thay gate/budget và không chạy pilot/campaign.

## Standards

Không có confirmed finding ở trục Standards. Đã đọc `AGENTS.md`, Core First,
README, pyproject và đặc tả2A; review code liên quan, callers và regression.
Không thấy CONTRIBUTING/CODING_STANDARDS bổ sung. Không có dependency/pin,
research hoặc reverse-engineering changes trong diff dự kiến.

## Spec

**P2 đã giải quyết — raw status của probe khi hết budget.**

Mô tả dưới đây ghi lại lỗi đã tái hiện trước sửa:
`src/tkb_core/solver/objectives.py:173` chuyển probe INFEASIBLE thành UNKNOWN để
tránh coi restricted infeasibility là vô nghiệm của bài gốc. Nếu không còn budget
cho fallback, status đã đổi được trả ra và ghi vào `tier_runs[].raw_status`, dù
native không trả UNKNOWN. Đặc tả2A mục8 yêu cầu “raw solver status hoặc NOT_RUN”;
`solver-design.md` cũng nói raw status/bound thuộc response được chọn.

Tái hiện xác định bằng `_run` test helper: script trả OPTIMAL cho hard/verification,
INFEASIBLE cho P1 slice, clock giả và limit3.0 để không còn budget. Kết quả top-level
FEASIBLE giữ incumbent hợp lệ, nhưng tier raw UNKNOWN; không có interleave call.
`CpSolver.solve` được thay bằng hàm luôn raise để bảo đảm **0 native solve thực**.
Đây là lỗi metadata, không phải bằng chứng lịch hard-invalid và không chứng minh
nguyên nhân pilot không đạt zero. Trong pilot gần nhất, probe thực sự UNKNOWN nên
finding không làm sai raw status đã ghi ở pilot đó.

Đã sửa sau khi người dùng cho phép: internal `StageOutcome.raw_status` giữ response
INFEASIBLE của probe; normalized UNKNOWN chỉ điều khiển luồng tier. Khi không còn
budget fallback, public tier raw INFEASIBLE đi kèm diagnostic
`ZERO_TARGET_PROBE_INFEASIBLE` nêu rõ chỉ probe bị restricted infeasibility; top-level
vẫn FEASIBLE và giữ incumbent đã kiểm. Nếu fallback đã chạy mà không có incumbent
mới, raw metadata lấy từ response thực của fallback, không kéo override của probe.
Không thay public schema, constraints, gates, native-call count hoặc ngân sách.

Hai regression clock/fake-stage kiểm ca hết budget và fallback UNKNOWN, giữ đúng
wall-time/bound/proof/incumbent và chặn mọi native solve trong regression. Cả hai
còn kiểm public `solve()` và JSON roundtrip. Regression RED trước sửa, GREEN sau
sửa. Một vòng review độc lập của delta mới không có finding.

Standards:0 confirmed findings. Spec:1 P2 đã đóng,0 finding còn mở trong phạm vi review.
Thiếu Windows native verification là hạn chế đã công bố, không được ghi như một
finding mới hoặc bị đổi thành PASS.

## Kiểm tra và dữ liệu

- Static checks thực chạy: `uv run ruff check .`, `uv run ruff format --check src
  tests benchmarks`, `uv run mypy`, `git diff --check HEAD`: PASS.
- Checks sau sửa thực chạy: `uv sync --locked --extra solver` PASS;
  `uv run --extra solver pytest` **363 passed**;
  `uv run --extra solver pytest tests benchmarks/tests` **728 passed,8 skipped**.
  Full suite có native tiny integration/oracle tests thông thường; không có pilot
  hay campaign mới. Riêng regression lỗi mới dùng fake stages và forbid native solve.
- Logs mới giữ local tại `benchmarks/artifacts/phase2a/raw-status-fix-20261105-v1/`,
  không stage. Các logs/evidence cũ và ZIP bàn giao cũ không bị sửa. Wheel hash và
  số tests361/726 trong biên bản chốt trước đó là lịch sử; không tái gán chúng cho
  source đã sửa. Chưa chạy installed-wheel preflight hoặc benchmark cho fix này.
- Scan literal private keys/tokens/credential assignments, URL password, địa chỉ
  email và personal absolute paths trên allowlist: không phát hiện giá trị cần
  loại. Có kiểm thêm loại file, kích thước và ignore rules; đây không phải quét
  toàn Git history hay chứng nhận secrets của cả repository.
- Evidence under `benchmarks/artifacts/`, venvs, wheel/ZIP và raw data không được
  stage; không có source hay dữ liệu trong `research/`/`reverse-engineering/` được
  thêm. File lớn nhất trong phần code là runner khoảng79KB.
- Root `CLAUDE.md` trỏ rõ AGENTS và cloud handoff; guide giữ v2 DRAFT, zero NOT_MET,
  primary0/108, quality chưa duyệt và Windows/cross-OS chưa nghiệm thu.

## Allowlist commit dự kiến —31 files

A=new file, M=modified. Giữ thay đổi có sẵn; chỉ đưa những file này vào index để
review bằng `git diff --cached`. Staging không phải commit và chưa có gì được gửi.

| Trạng thái | File |
|---|---|
| A | `CLAUDE.md` |
| M | `benchmarks/aggregate_linux.py` |
| A | `benchmarks/native_trace.py` |
| A | `benchmarks/phase2a_preflight.py` |
| M | `benchmarks/run_benchmarks.py` |
| A | `benchmarks/run_phase2a_windows.ps1` |
| M | `benchmarks/tests/test_campaign_linux.py` |
| A | `benchmarks/tests/test_native_trace.py` |
| A | `benchmarks/tests/test_phase2a_preflight.py` |
| M | `benchmarks/tests/test_run_benchmarks.py` |
| A | `benchmarks/tests/test_windows_runtime.py` |
| A | `benchmarks/windows_runtime.py` |
| A | `docs/phase-2a-acceptance-v2-draft.md` |
| A | `docs/phase-2a-cloud-handoff.md` |
| A | `docs/phase-2a-commit-review.md` |
| A | `docs/phase-2a-current-operational-report.md` |
| A | `docs/phase-2a-incumbent-trace-report.md` |
| A | `docs/phase-2a-joint-zero-report.md` |
| A | `docs/phase-2a-linux-closeout-report.md` |
| M | `docs/phase-2a-report.md` |
| A | `docs/phase-2a-technical-closeout.md` |
| M | `docs/solver-design.md` |
| A | `docs/superpowers/plans/2026-11-03-phase-2a-operational-completion.md` |
| A | `docs/superpowers/plans/2026-11-04-phase2a-incumbent-trace.md` |
| A | `docs/superpowers/plans/2026-11-04-phase2a-joint-zero.md` |
| A | `docs/superpowers/plans/2026-11-04-phase2a-linux-closeout.md` |
| M | `src/tkb_core/solver/objectives.py` |
| M | `tests/integration/test_occurrence_ordering_native.py` |
| M | `tests/integration/test_tier_two_phase_native.py` |
| M | `tests/unit/test_quality_stages.py` |
| M | `tests/unit/test_tier_two_phase.py` |

Các ghi chú `docs/c10-base-s101-*.md` và hai bản nháp upstream OR-Tools được giữ
local, không xóa và không stage trong commit kỹ thuật/cloud handoff này. Chúng là
hồ sơ chẩn đoán riêng; các báo cáo2A đã chọn giữ đủ kết luận và giới hạn cần thiết.
File tracked ngoài allowlist và toàn bộ evidence lịch sử cũng không bị thay đổi.

## Commit message dự kiến — chưa thực hiện

```text
fix(core): preserve tier incumbents and prepare Phase 2A handoff

- retain the best active-tier vector with honest selected-response metadata
- isolate suffix-zero probes and preserve original-model fallback
- preserve native probe metadata when fallback budget expires
- add native-call tracing, installed preflight and Windows accounting tooling
- record technical-only closure and Claude Code cloud handoff instructions
- preserve NOT_MET pilot, primary 0/108 and unverified Windows/cross-OS limits
```

Finding raw status đã được giải quyết và các checks sau sửa đạt. Đây là nội dung
commit dự kiến để người dùng duyệt; chưa tạo commit. Merge và push vẫn chưa được
ủy quyền. Việc duyệt code kỹ thuật không đổi trạng thái nghiệm thu vận hành.
Draft v2 không được áp dụng, Phase2B chưa triển khai và không có campaign retry.
