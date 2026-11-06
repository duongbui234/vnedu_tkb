# Phase 2 — báo cáo tổng hợp tiến độ

Ngày 2026-11-05. Base `24bad78` trên `main`. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-05.**

Đây là bản tổng hợp để định hướng: Phase 2 đang ở đâu, đã quyết định gì, việc tiếp theo nằm ở phía ai, và
tài liệu nào chứa chi tiết. Phân tích trạng thái và rủi ro đầy đủ nằm ở
[đánh giá Phase 2](phase-2-status-assessment.md) và [cập nhật 1](phase-2-status-assessment-update-1.md);
báo cáo này không thay thế hai bản đó.

Lượt soạn chỉ đọc tài liệu và git log. Không sửa code, không chạy test, solver hay campaign. Mọi con số là
kết quả đã lưu trong các tài liệu được dẫn.

## 1. Tóm tắt một trang

| Trục | Trạng thái | Ghi chú |
|---|---|---|
| Kỹ thuật synthetic | **Đạt** | S01–S11 soft; hard variants S01–S06; evaluator độc lập; oracle; CLI/package. Policy 0.1–0.4, output 1.2–1.5, ScoreReport 1.0–1.2 |
| Tooling đo hiệu năng v2 | **Sẵn sàng** | Policy 0.4, 72 dataset, verdict H/Q/P/zero theo acceptance v2. Đã tự rà soát (F1–F5 đã sửa) và diễn tập end-to-end trên cloud (R1 đã sửa, R2 đã ghi) |
| Hard validity (H) campaign Linux v2 | **PASS 216/216** | *Cập nhật 2026-11-06*, campaign `phase2-v2-linux-02`, candidate `7e47f74` (chưa merge). [Báo cáo](phase-2a-linux-acceptance-report.md) |
| Hiệu năng (P) trên máy đích | **MET** | 162/162 known-feasible có lịch trong giới hạn, 54/54 UNSAT đúng; một máy, workload UNCONTROLLED, n = 3, không P95/SLA |
| Benchmark zero | Riêng | NOT_APPLICABLE ở ma trận v2 (không witness zero); verdict lịch sử NOT_MET giữ nguyên |
| Chất lượng giáo vụ (Q) | REVIEW_REQUIRED | Chưa có quality profile |
| Windows/cross-OS | **Ngoài phạm vi Phase 2 v2** | S2: Phase 2 v2 là Linux-only |
| Dữ liệu thật | UNKNOWN | Ngoài Core |

Kiểm tra gần nhất trên source hiện tại (`f873126`; các commit sau đó chỉ đổi tài liệu):
`uv run --extra solver pytest tests benchmarks/tests` **1352 passed, 8 skipped**; ruff, format và mypy
PASS. Wheel `cdd34282…35d1`.

## 2. Các mốc đã xong

| Mốc | Kết quả | Tài liệu chính |
|---|---|---|
| 2A | S01–S04 soft, lexicographic P1–P3, evaluator độc lập; chốt kỹ thuật synthetic. Campaign Linux v1 dừng ở primary 0/108 (lịch sử giữ nguyên) | [chốt 2A](phase-2a-technical-closeout.md), [báo cáo 2A](phase-2a-report.md) |
| 2B | Hard variants S01–S04 (policy 0.2 → output 1.3) | [báo cáo](phase-2b-report.md), [rà soát](phase-2b-review.md) |
| 2C-1 | S05/S06 soft + hard (0.3 → 1.4, Score 1.1) | [báo cáo](phase-2c-report.md), [rà soát](phase-2c-review.md) |
| 2C-2 | S07–S11 soft + `occupied_work` (0.4 → 1.5, Score 1.2) | [báo cáo](phase-2c-gaps-report.md), [rà soát](phase-2c-gaps-review.md) |
| Đánh giá Phase 2 | E1–E4, E6 duyệt; acceptance v2 D1–D3 duyệt | [đánh giá](phase-2-status-assessment.md) |
| Tooling v2 | `generate_phase2`, `run_phase2`, `aggregate_phase2`; 70 test + 11 regression; tooling v1 giữ nguyên byte | [kế hoạch v2 §11](superpowers/plans/2026-11-05-phase-2-linux-performance-v2.md), [rà soát](phase-2-linux-performance-tooling-review.md) |
| Diễn tập E0 (cloud) | Preflight → prepare → warmup → 2 pilot → aggregate chạy được; R1 đã sửa, R2 đã ghi | [báo cáo E0](phase-2-linux-performance-rehearsal-e0-report.md) |
| Đánh giá cập nhật 1 | S1–S4 duyệt | [cập nhật 1](phase-2-status-assessment-update-1.md) |
| Runbook D/E/F | Cả ba đã duyệt | [D](phase-2-linux-performance-step-d-runbook.md), [E](phase-2-linux-performance-step-e-runbook.md), [F](phase-2-linux-performance-step-f-runbook.md) |

## 3. Vị trí hiện tại trong quy trình đo hiệu năng

| Bước | Nội dung | Ai làm | Trạng thái |
|---|---|---|---|
| Kế hoạch v2 + tooling | Thiết kế, code, test, rà soát | Claude | **Xong** |
| E0 | Diễn tập trên cloud (không phải evidence) | Claude | **Xong** |
| D | Sinh bundle + preflight trên máy Linux | **Người dùng** | **Chờ chạy** ← vị trí hiện tại |
| Kiểm D | Kiểm theo §3 của runbook D | Claude | Chờ kết quả D |
| E | Prepare, warmup, 2 pilot | Người dùng | Chờ D đạt |
| Kiểm E, quyết định mở F | Tóm tắt pilot; người dùng quyết định (K6, M1) | Claude, rồi người dùng | — |
| F | 216 run primary (khoảng 6–10 giờ liền) | Người dùng | Cần ủy quyền riêng |
| Báo cáo | `docs/phase-2-linux-performance-report.md` | Claude | Chỉ khi được cho phép (M6) |

*Cập nhật 2026-11-06:* `phase2-v2-linux-01` trên `86f624d` bị gián đoạn ở bước F và giữ nguyên. Chuỗi D/E/F
được làm lại với ID mới `phase2-v2-linux-02` trên candidate `7e47f74`: E PASS (2 pilot), F COMPLETE 216/216,
aggregate SUMMARIZED. Báo cáo M6 là [báo cáo nghiệm thu Linux](phase-2a-linux-acceptance-report.md)
(DRAFT, chờ duyệt).

Điều kiện máy đích: Linux x86_64 native, Python 3.12 qua `uv`, **cgroup v2** (`stat -fc %T /sys/fs/cgroup`
= `cgroup2fs`), ≥ 6 GiB RAM khả dụng cho bước F, cắm sạc, không ngủ. Các bước D, E, F phải dùng cùng
một commit và cùng một máy.

## 4. Sổ quyết định đã duyệt

| Bộ | Nội dung chính | Tài liệu |
|---|---|---|
| D1–D3 | Acceptance v2: tách H/Q/P/zero; pilot hard-valid mở primary để đo; không sửa evidence cũ | [acceptance v2](phase-2a-acceptance-v2-draft.md) |
| E1–E4, E6 | Duyệt acceptance v2; mở rộng benchmark sang 0.4; Windows là bước riêng; hoãn S12; ghi nhận thiếu review độc lập. **E5 (chính sách version) chưa quyết định** | [đánh giá](phase-2-status-assessment.md) |
| G1–G10 | Module mới, không sửa v1; hai biến thể SOFT/HARD; priority; occupied work; không ép zero; 216 primary; Q REVIEW_REQUIRED; gate dừng; máy người dùng; hai pilot | [kế hoạch v2](superpowers/plans/2026-11-05-phase-2-linux-performance-v2.md) |
| K1–K7 | Diễn tập cloud; ID `phase2-v2-linux-01`; chạy E liên tiếp; không retry; điều kiện máy; pilot không tự mở primary; báo cáo khi được phép | [kế hoạch E](superpowers/plans/2026-11-05-phase-2-linux-performance-step-e.md) |
| M1–M7 | F chỉ sau E đạt; một phiên liền mạch; điều kiện máy; xem tiến độ chỉ đọc; không retry; báo cáo khi được phép; không đổi gì giữa chừng | [kế hoạch F](superpowers/plans/2026-11-05-phase-2-linux-performance-step-f.md) |
| S1–S4 | Không tối ưu trước khi có số đo; Phase 2 v2 là Linux-only; cần review người thứ hai trước quyết định sản phẩm; push thẳng `main` nhưng mỗi commit vẫn cần duyệt | [cập nhật 1](phase-2-status-assessment-update-1.md) |

## 5. Những điểm cần nhớ

- **Chưa có con số hiệu năng nào cho Phase 2 v2.** Số từ diễn tập E0 là của container cloud, n = 1, và
  không phải evidence.
- **Tín hiệu từ diễn tập:** pilot HARD ở cỡ 10 lớp mất khoảng 46 s trong 60 s chỉ để tìm lịch khả thi; P2
  và P3 không được chạy. Ở cỡ 20/40 lớp có thể có nhiều run P NOT_MET. Đó là thứ campaign cần đo; không
  nới budget (M7, S1).
- **Benchmark zero:** NOT_APPLICABLE cho cả 72 dataset v2 (G5). Kết quả zero của v1 giữ nguyên lịch sử.
- **Ngắt campaign giữa chừng tức là kết thúc nó.** Chạy lại phải dùng ID mới, và cần ủy quyền mới.
- **Kiểm chứng độc lập vẫn mỏng:** mọi rà soát là tự kiểm trong cùng phiên; từ `812b0b6` thay đổi push
  thẳng `main`. S3 yêu cầu review người thứ hai trước khi dùng kết quả cho quyết định sản phẩm.

## 6. Việc tiếp theo

*Cập nhật 2026-11-06:* bước 1–3 dưới đây đã xong với campaign `phase2-v2-linux-02`; bước 4 đang ở khâu
duyệt [báo cáo nghiệm thu Linux](phase-2a-linux-acceptance-report.md) và quyết định merge candidate.

1. **Người dùng:** chạy runbook D trên máy Linux, gửi kết quả theo §3 của runbook.
2. **Claude:** kiểm kết quả D; nếu đạt, người dùng chạy runbook E.
3. Sau khi E đạt: tóm tắt pilot; người dùng quyết định có cho chạy F không.
4. Sau F: aggregate; báo cáo hiệu năng khi được cho phép; quyết định hướng hiệu năng dựa trên dữ liệu.
5. Về sau, theo các quyết định đã có: Windows là mốc riêng (S2), quality profile (D), review người thứ
   hai (S3), S12 khi có use case (E4), E5 khi có mốc version mới.
