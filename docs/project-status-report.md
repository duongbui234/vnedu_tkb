# vnEdu TKB — báo cáo hiện trạng toàn dự án

Ngày 2026-11-05, **cập nhật 2026-11-06** tại base `fe3e1c5` trên `main`. Trạng thái: bản 2026-11-05 đã được
người dùng duyệt; bản cập nhật 2026-11-06 là **DRAFT — chờ duyệt**.

Báo cáo tổng hợp hiện trạng toàn dự án so với lộ trình trong
[đặc tả Core First](VNEDU_TKB_CORE_FIRST_CODEX.md) §10. Lượt soạn chỉ đọc tài liệu, source và git log.
Không sửa code, không chạy test, solver hay campaign; mọi con số là kết quả đã lưu trong tài liệu được
dẫn. Chi tiết Phase 2 nằm ở [báo cáo tiến độ Phase 2](phase-2-progress-report.md).

## 1. Tóm tắt

- **Sản phẩm hiện có là Scheduling Core** (thư viện Python và CLI), chưa có ứng dụng cho người dùng cuối.
  Đúng phạm vi Core First: chưa có UI, SQLite, vnEdu API hay installer (Phase 4).
- **Phase 0 và Phase 1 đã đạt.**
- **Phase 2 đạt điều kiện Done của đặc tả §10** (S01–S11, hard variants S01–S06, evaluator độc lập). Campaign
  Linux v2 `phase2-v2-linux-02` trên no-LP `7e47f74` (đã merge vào `main` ở `1c2819f`) đạt **H PASS 216/216,
  P MET 162/162 + 54/54 UNSAT**. **Q vẫn REVIEW_REQUIRED**: kế hoạch duyệt Q và ba biên bản DRAFT đã có,
  chờ người dùng ghi quyết định. Zero là benchmark riêng. Windows ngoài phạm vi Phase 2 v2 (S2). Xem
  [báo cáo nghiệm thu Linux](phase-2a-linux-acceptance-report.md) và [kế hoạch Q](phase-2a-quality-review-plan.md).
- **Phase 3 đang làm.** 3A (repair) đã triển khai, commit và kiểm installed wheel. 3B (chẩn đoán vô
  nghiệm) có [đặc tả DRAFT](superpowers/specs/2026-11-06-phase-3b-infeasibility-diagnostics-design.md)
  chờ duyệt B1–B10. 3C (benchmark repair) chưa bắt đầu; điều kiện tiên quyết P3-10 (campaign Phase 2 v2)
  đã thỏa.
- **Nút thắt hiện tại:** quyết định Q (phía người dùng) và duyệt đặc tả 3B.
- **Dữ liệu và quy tắc thật của trường vẫn là UNKNOWN.** Các câu hỏi nghiệp vụ ở §13 của đặc tả vẫn mở.

## 2. Trạng thái theo phase

| Phase | Điều kiện Done (đặc tả §10) | Trạng thái | Bằng chứng |
|---|---|---|---|
| 0 — Skeleton, contracts | Import được, validate fixture, test/lint chạy | **Đạt** | [báo cáo Phase 0](phase-0-report.md) |
| 1 — Scheduling MVP (hard) | CLI solve trên fixture có nghiệm; validator độc lập xác nhận; xử lý đúng fixture vô nghiệm; test pass | **Đạt** (2026-10-26) | [báo cáo Phase 1](phase-1-report.md) |
| 2 — Quality optimization | Fixture chứng minh soft score cải thiện so baseline mà không phá hard; test pass | **Đạt** (Done §10). H/P campaign Linux v2 đạt (`7e47f74`, đã merge); Q REVIEW_REQUIRED; Windows ngoài phạm vi v2 | [tiến độ Phase 2](phase-2-progress-report.md), [nghiệm thu Linux](phase-2a-linux-acceptance-report.md), [kế hoạch Q](phase-2a-quality-review-plan.md) |
| 3 — Repair + Benchmark | Repair test pass; benchmark có số liệu thực; validator pass trên mọi nghiệm | **Đang làm.** 3A repair xong (technical synthetic); 3B đặc tả DRAFT; 3C chưa bắt đầu. Done khi cả ba xong (P3-11) | [đặc tả Phase 3](superpowers/specs/2026-11-05-phase-3-repair-diagnostics-design.md), [báo cáo 3A](phase-3a-report.md), [đặc tả 3B](superpowers/specs/2026-11-06-phase-3b-infeasibility-diagnostics-design.md) |
| 4 — Adapter, SQLite, UI, installer, Windows benchmark | Ngoài phạm vi hiện tại | **Không thực hiện** (đúng đặc tả) | — |

## 3. Năng lực của Core hiện tại

| Nhóm | Đã có |
|---|---|
| Contracts | Input 1.0/1.1 (policy 0.1–0.4); output 1.1–1.5; ScoreReport 1.0–1.2. Pydantic strict, từ chối field lạ, fingerprint SHA-256 canonical. Ghép version chặt (`RESULT_VERSION`) |
| Hard (Phase 1) | Lớp, GV, môn, phân công, slot symbolic/timed, availability, tiết đơn/đôi, phòng (khi bật), khóa time/room, precheck tải/phòng cần thiết, resource guards |
| Soft (Phase 2) | S01–S04 nguyện vọng GV; S05/S06 phân phối môn; S07–S11 tiết trống, buổi/ngày rảnh, buổi một tiết; `occupied_work`. Priority P1–P3 lexicographic, trọng số tường minh, không có giá trị mặc định ngầm |
| Hard variants | S01–S04 (0.2), S05/S06 (0.3) |
| Kiểm chứng độc lập | Validator và evaluator không import solver/compiler (có test guard), dùng được cả khi không cài OR-Tools |
| Repair (3A) | `repair()` giữ lịch trước nhiều nhất có thể, `max_changes`, `change_scope`, `change_order` tường minh, hint tùy chọn; contract `PreviousSchedule`/`RepairRequest`/`RepairResult` 1.0; evaluator thay đổi độc lập |
| CLI | `validate-input`, `solve`, `validate-schedule`, `evaluate-score`, `repair`, `evaluate-repair`; JSON stdout, exit code theo status |
| Đóng gói | Wheel `vnedu-tkb-core` 0.2.0 (`cdd34282…35d1`), OR-Tools là extra `solver`; đã kiểm installed wheel trên Linux |

**Chưa có trong Core:**

- chẩn đoán vì sao vô nghiệm (đặc tả 3B DRAFT; chưa triển khai);
- benchmark repair (3C);
- S12;
- hard mode cho S07–S11;
- timed calendar có buổi chồng giờ cho S08–S11 (bị từ chối có chủ ý);
- requirement có nhiều lớp hoặc nhiều GV (đồng giảng, lớp ghép), block dài hơn 2 tiết, tuần A/B. Các
  trường hợp này bị từ chối tường minh; theo đặc tả, chỉ hỗ trợ khi có quy tắc xác nhận.

## 4. Kiểm chứng và evidence

| Hạng mục | Kết quả đã lưu |
|---|---|
| Test suite (`main` sau merge `1c2819f`, 2026-11-06) | `pytest tests benchmarks/tests` **1564 passed, 8 skipped**. 8 skip là test Windows native/opt-in. Ruff, format và mypy strict (36 file) PASS |
| Oracle | Mỗi mốc soft có oracle vét cạn 60 seed, bật/tắt ordering; Phase 1 có 20 tiny exhaustive cases |
| Installed wheel | Kiểm trên Linux ở mỗi mốc 2B/2C và 3A (`0d318d1`) (n = 1, synthetic). Chưa kiểm installed wheel cho source no-LP sau merge |
| Benchmark v1 (2A, policy 0.1) | Campaign Linux cũ: 54/81 known-feasible có lịch, 27/27 UNSAT đúng. Campaign candidate 2A: STOPPED, primary 0/108. Benchmark zero NOT_MET. Toàn bộ là lịch sử, giữ nguyên |
| Điều tra TIGHT10 / Windows S03 | Chuỗi báo cáo trace, CPU và accounting ([tổng hợp](tight10-evidence-synthesis.md)); lịch sử 2A |
| Benchmark v2 (policy 0.4) | `phase2-v2-linux-01` (`86f624d`) bị gián đoạn, giữ nguyên. `phase2-v2-linux-02` (candidate `7e47f74`, 2026-11-06): 216/216 terminal, **H PASS, P MET**, Q REVIEW_REQUIRED, zero NOT_APPLICABLE; một máy, workload UNCONTROLLED, n = 3 — [báo cáo](phase-2a-linux-acceptance-report.md) |
| Windows | Evidence chỉ cho snapshot cũ; Phase 2 v2 là Linux-only (S2) |

Evidence thô của campaign nằm trong `benchmarks/artifacts/` trên máy người dùng và không có trong clone
cloud.

## 5. Quy trình và quản trị

- **Quy tắc làm việc:** AGENTS.md và CLAUDE.md. Mỗi thay đổi product code, commit, push, merge hay xóa
  nhánh cần duyệt riêng. Không đổi gate, không dùng witness hint, không chạy campaign khi chưa được giao.
- **Mỗi mốc đi qua:** đặc tả và kế hoạch DRAFT → duyệt → TDD → checks → commit/push → tự rà soát → sửa →
  kiểm installed wheel.
- **Nhánh:** PR duongbui234/vnedu_tkb#3 đến duongbui234/vnedu_tkb#6 đã merge, không có review comment hay
  CI. Repo chưa có `.github`. Từ `812b0b6`, theo yêu cầu người dùng, thay đổi push thẳng lên `main`,
  nhưng mỗi commit vẫn cần duyệt (S4).
- **Sổ quyết định:** D1–D3, E1–E4/E6, G1–G10, K1–K7, M1–M7 và S1–S4 đã duyệt; E5 (chính sách version)
  chưa quyết định. Xem [tiến độ Phase 2 §4](phase-2-progress-report.md).

## 6. Câu hỏi nghiệp vụ còn mở (đặc tả §13)

Core được thiết kế để các câu hỏi này là **cấu hình tường minh**, không phải giá trị đoán. Chưa câu nào có
câu trả lời từ trường thật.

| # | Câu hỏi | Core hiện tại |
|---:|---|---|
| 1–2 | Quy tắc theo cấp học; số ngày/buổi/tiết theo lớp | Calendar và availability do input khai báo; không có mặc định theo cấp học |
| 3 | Chào cờ, sinh hoạt | Biểu diễn được bằng tiết khóa hoặc requirement; chưa có quy ước |
| 4 | Đồng giảng, lớp ghép, nhóm, phòng bộ môn | Phòng theo loại có. Requirement có nhiều lớp hoặc nhiều GV bị từ chối (`UNSUPPORTED_FEATURE/MULTIPLE_PARTICIPANTS`) |
| 5 | Tiết đôi, liên tiếp, giãn cách | Block dài 1 hoặc 2 tiết (dài hơn bị từ chối); giãn cách (S05) và giới hạn môn/ngày (S06) có, ngưỡng UNKNOWN |
| 6 | Nhiều GV cho cùng môn/lớp | Mỗi requirement một GV; chưa hỗ trợ khác |
| 7 | Tuần cố định hay A/B | Chu kỳ một tuần; A/B chưa hỗ trợ |
| 8 | Tiêu chí nào bắt buộc, tiêu chí nào ưu tiên | Mỗi rule chọn được soft/hard (khi có hard mode), priority và trọng số; quyết định thuộc nhà trường |
| 9 | Sửa lịch giữ tiết đã công bố hay chỉ tiết khóa | `solve()` chỉ giữ tiết khóa; `repair()` (3A) giữ lịch trước nhiều nhất có thể trong `max_changes`/`change_scope`. Quy tắc trường vẫn UNKNOWN |
| 10 | Contract vnEdu API | Phase 4, khi có contract thật |

## 7. Rủi ro chính

1. **Hiệu năng mới đo trên synthetic, một máy.** Campaign v2 đạt P đến 40 lớp (n = 3, workload
   UNCONTROLLED); không P95/SLA, chưa có dữ liệu trường thật.
2. **Chất lượng lịch chưa được chấp nhận.** Q là REVIEW_REQUIRED; P1 > 0 ở 90/162 lịch, mọi lịch 20/40
   lớp kém hơn witness. Biên bản Q chờ người dùng.
3. **Khoảng cách tới dữ liệu thật.** Mọi ngưỡng, nhóm và lịch họp là UNKNOWN; synthetic không thay được
   trường thật.
4. **Kiểm chứng độc lập mỏng.** Mọi rà soát là tự kiểm; không CI; không review người thứ hai (E6, S3).
5. **Số phiên bản contract tăng theo từng mốc** (E5 chưa quyết định).
6. **Windows chưa được kiểm cho candidate hiện tại**, trong khi Phase 4 nhắm ứng dụng desktop.

## 8. Lộ trình đề xuất

1. **Ngay bây giờ:** người dùng ghi quyết định Q cho ba biên bản; duyệt đặc tả 3B (B1–B10).
2. **Sau khi duyệt 3B:** spike assumption API (B9), kế hoạch task, TDD, báo cáo 3B.
3. **3C:** benchmark repair trên máy Linux (dùng lại tooling v2), sau khi có kế hoạch duyệt.
4. **Hướng chất lượng search** (S1): nếu Q cho thấy P1 > 0 không chấp nhận được, lập kế hoạch riêng dựa
   trên số đo v2; review người thứ hai cho contract và tooling (S3).
5. **Song song khi có thể:** thu thập câu trả lời nghiệp vụ §13 và một bộ dữ liệu thật đã ẩn danh; quality
   profile cùng chủ thể nghiệp vụ; quyết định E5.
6. **Phase 4** (adapter, SQLite, UI, Windows) chỉ khi Core đạt Phase 3 và có contract vnEdu thật.

## 9. Tài liệu chính

| Chủ đề | Tài liệu |
|---|---|
| Đặc tả gốc | [Core First](VNEDU_TKB_CORE_FIRST_CODEX.md) |
| Mô hình và giả định | [domain model](domain-model.md), [assumptions](assumptions.md), [constraint catalog](constraint-catalog.md), [solver design](solver-design.md) |
| Phase 0/1 | [Phase 0](phase-0-report.md), [Phase 1](phase-1-report.md) |
| Phase 2 | [tiến độ](phase-2-progress-report.md), [đánh giá](phase-2-status-assessment.md), [cập nhật 1](phase-2-status-assessment-update-1.md), [acceptance v2](phase-2a-acceptance-v2-draft.md) |
| Hiệu năng v2 | [kế hoạch](superpowers/plans/2026-11-05-phase-2-linux-performance-v2.md), runbook [D](phase-2-linux-performance-step-d-runbook.md) / [E](phase-2-linux-performance-step-e-runbook.md) / [F](phase-2-linux-performance-step-f-runbook.md), [diễn tập E0](phase-2-linux-performance-rehearsal-e0-report.md) |
| Phase 2 nghiệm thu | [nghiệm thu Linux](phase-2a-linux-acceptance-report.md), [kế hoạch Q](phase-2a-quality-review-plan.md), [biên bản Q](quality-decisions/README.md) |
| Phase 3 | [đặc tả](superpowers/specs/2026-11-05-phase-3-repair-diagnostics-design.md), [báo cáo 3A](phase-3a-report.md), [rà soát 3A](phase-3a-review.md), [đặc tả 3B](superpowers/specs/2026-11-06-phase-3b-infeasibility-diagnostics-design.md) |
| Quy tắc làm việc | `AGENTS.md`, `CLAUDE.md` |
