# Phase 2A — bàn giao qua Git cho Claude Code cloud

Ngày 2026-11-05. **Cập nhật:** commit Phase 2A đã được tạo và push là
`124b89d318467421dedf421f8d1c9a6b72b6991e` trên `work/phase2a-operational-completion`;
các đoạn “chưa commit” bên dưới mô tả trạng thái lúc soạn. Phase 2B đã được làm sau đó
theo [báo cáo 2B](phase-2b-report.md); mọi hạn chế 2A dưới đây giữ nguyên.
Đọc [review trước commit](phase-2a-commit-review.md) trước khi sửa code: finding
P2 về raw status đã được sửa theo ủy quyền, checks đạt; commit vẫn đang chờ duyệt.

## Snapshot và phạm vi

Base HEAD `537c89125c0e1a81173cd099f08f014194d249b4`; nhánh chuẩn bị hiện tại
`work/phase2a-operational-completion`. Các thay đổi Phase 2A hiện còn uncommitted.
Khi commit/push đã được duyệt và thực hiện ở lượt khác, dùng đúng nhánh remote chứa
commit đó làm base của phiên cloud; không giả định `main` đã có các thay đổi này.
Xác nhận commit thực tế bằng `git rev-parse HEAD`, không dùng tên nhánh thay cho hash.

Wheel đã kiểm trước đây có SHA256
`382a54ba845ce30325670d72a06d13a0b06e2dcd7702fec398e7c262f4d3eead`;
uv.lock SHA256 `fe404cb126bce893368517318d4982b5f7842990429467d2a793af066c2e4c3b`.
Wheel không nằm trong commit. Hash này nhận dạng snapshot cũ đã test, không phải
yêu cầu mọi wheel build lại phải có cùng toàn bộ byte/metadata. Nếu sửa source,
build/preflight phải nhận dạng candidate mới; không tái sử dụng receipt của wheel cũ.

Phạm vi người dùng đã chốt: **technical synthetic Phase 2A**, xem
[biên bản chốt](phase-2a-technical-closeout.md). S01–S04 soft, independent hard
validator/score evaluator, ưu tiên P1–P3, CLI/package và regression đã có.
Input1.0 giữ compatibility; input1.1/policy0.1/output1.2 là tuyến quality.
Không có hard variants Phase2B, spacing/gaps2C, repair, Desktop, SQLite hoặc API.

## Evidence nào đi theo nhánh

- Source, tests tổng hợp, lock/config, benchmark tooling và các báo cáo/plan được
  liệt kê trong review commit đi theo nhánh sau khi được commit/push.
- Raw evidence, venvs, wheel/ZIP, snapshots nghiên cứu, binary STKB và dữ liệu thật
  không đi theo nhánh. Không force-add thư mục đang bị Git ignore.
- Các báo cáo giữ kết quả lịch sử nhưng đường dẫn `benchmarks/artifacts/...` sẽ
  không tồn tại trong clone cloud thông thường. Đó không phải chứng cứ đã được
  cloud chạy lại. Không fabricate raw logs, hashes hoặc proof để lấp chỗ thiếu.
- Các ghi chú chẩn đoán/upstream riêng không cần cho handoff kỹ thuật này được
  giữ local ngoài allowlist commit. Không upload toàn bộ evidence để thay cho
  việc đọc báo cáo chốt.

Snapshot trước review có Core361/full726 và installed preflight PASS. Sau fix raw
status, checks mới là **Core363 passed; full728 passed,8 skipped**; locked sync,
lint/format/Core mypy PASS. Full suite có native tiny integration/oracle tests;
regression mới dùng fake stages, không có pilot/campaign mới. Chưa có installed-wheel
preflight mới cho source sau fix. Không dùng wheel/ZIP snapshot cũ để giả định đã
chứa fix mới hoặc dùng các số benchmark cũ để chứng nhận candidate sau sửa.

Với restricted zero probe INFEASIBLE và hết budget fallback, result giữ top-level
FEASIBLE/hard-valid incumbent; tier raw INFEASIBLE đi kèm diagnostic
`ZERO_TARGET_PROBE_INFEASIBLE`. Nếu fallback đã chạy, dùng raw response thực của
fallback. Đây là metadata scope, không là hard infeasibility của bài gốc và không
thay đổi public schema hay quy tắc xếp lịch.

## Hạn chế không được che khi chuyển sang cloud

Pilot mới nhất hard-valid FEASIBLE `[0,5,120]`; zero **NOT_MET**, primary **0/108**,
controller đã STOPPED. Chất lượng giáo vụ REVIEW_REQUIRED. Current native Windows
và cross-OS chưa được nghiệm thu. Các evidence Windows/synthetic cũ không chứng
nhận toàn bộ candidate mới. [Trace và kết quả](phase-2a-incumbent-trace-report.md).

[Tiêu chí v2](phase-2a-acceptance-v2-draft.md) vẫn DRAFT, D1–D3 chưa duyệt.
Quyết định chốt kỹ thuật không đổi gate zero, không cho resume/retry campaign đã
dừng và không tự mở primary. Benchmark cloud là một môi trường mới; phải qua
identity/headroom/preflight nếu có run mới được ủy quyền, không bypass gate cũ.

## Trình tự cho agent tiếp nhận

1. Đọc `AGENTS.md`, `CLAUDE.md`, review commit và biên bản chốt. Xác nhận branch,
   commit, workspace và pin trong `uv.lock`; báo rõ tài liệu/evidence local bị thiếu.
2. Xác nhận nhánh chứa fix raw status và regression đã nêu trong review; không
   quay lại dùng snapshot ZIP trước fix làm code base mới. Giữ nguyên
   hard/priority/budget/gates khi làm nhiệm vụ tiếp theo.
3. Nếu nhiệm vụ là chuẩn bị Phase2B sau khi review được giải quyết, đọc
   [đặc tả hiện có](superpowers/specs/2026-10-26-phase-2-quality-design.md), mục2B:
   hard variants explicit, không weight/priority, compiler/independent checker và
   capability/overlap phải được thiết kế đồng bộ. Lập đặc tả/kế hoạch để duyệt trước;
   không tự biến soft declarations thành hard hoặc triển khai2C.
4. Chỉ chạy checks/native tests/solver trong phạm vi nhiệm vụ được ủy quyền;
   không tự chạy pilot/campaign, thay pins/gates, dùng witness hint, commit, merge,
   push hoặc đăng hồ sơ upstream. Báo các lệnh thực sự chạy và giới hạn kết luận.

Gói ZIP local vẫn là bản sao lưu snapshot trước review; không cần đưa ZIP lên Git
để Claude đọc source. Commit review hoặc fix tiếp theo làm snapshot mới, nên ZIP
cũ không tự trở thành gói đã chứa các cập nhật đó.
