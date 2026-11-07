# Kế hoạch chất lượng search (S1)

Ngày 2026-11-07. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-07 (R1–R6 theo đề xuất).** **S1-a đã chạy
2026-11-07: không hướng nào đạt §5** ([báo cáo spike](../../s1-a-spike-report.md)); không làm S1-b/S1-c với
A1/A2. **Spike [S1-b′ (A4, LNS)](2026-11-07-s1-b-prime-lns-spike.md) đã chạy
2026-11-07: không đạt §4** ([báo cáo](../../s1-b-prime-spike-report.md)). A4 cải thiện mạnh P1/P2 ở BASE/MIXED đến
40 lớp nhưng hồi quy ở TIGHT, nên không đưa sang S1-b. Theo L8, hướng search của S1 dừng ở đây; lựa
chọn tiếp theo là quyết định sản phẩm riêng, **chưa quyết định**. Base `201a6e0` trên `main`.

Nguồn:
- Quyết định S1 ([cập nhật 1](../../phase-2-status-assessment-update-1.md)): không tối ưu solver trước
  khi có số đo campaign. Nay đã có số đo của `phase2-v2-linux-02`.
- [Biên bản Q](../../quality-decisions/README.md): nguyên tắc **P1 > 0 không chấp nhận**.
- [Quality profile v0](../../quality-profile-v0.md): P1 = 0 bắt buộc.
- [Thiết kế solver](../../solver-design.md).

Tài liệu chỉ là kế hoạch. Lượt soạn chỉ đọc evidence local và source; không sửa code, không chạy solver
hay campaign. Duyệt kế hoạch **không** phải ủy quyền sửa Core hay chạy campaign.

## 1. Mục tiêu và phạm vi

**Mục tiêu:** tăng số lịch đạt profile v0 (P1 = 0) trong **cùng điều kiện đo** của campaign v2: budget
60/120/180 s, 1 worker, seed 42, cùng dataset, cùng policy 0.4. Không được làm mất H PASS và không được
làm giảm P MET.

**Trong phạm vi:** chiến lược search trong `run_quality`
(`src/tkb_core/solver/objectives.py`): thứ tự stage, zero-target probe, hint, phân bổ budget giữa các
stage.

**Ngoài phạm vi:**
- Nới budget, thêm worker, đổi gate hay policy, đổi trọng số.
- Dùng witness làm hint (bị cấm).
- Đổi contract hay ScoreReport.
- Dữ liệu thật, Windows.
- Nghiệm thu Q tự động (bước 3 của kế hoạch Q).

## 2. Số đo hiện tại (`phase2-v2-linux-02`, 162 lịch, chỉ đọc)

Nguồn là `result.json` và `native-calls.jsonl` của từng run primary, gồm mọi lời gọi CP-SAT, thời gian,
status và incumbent của từng stage. Script phân tích nằm ngoài repo.

**F1 — Khoảng cách nằm ở search, không ở model.** P1 = 0 ở 72/162 lịch, trong khi witness của **mọi**
dataset có P1 = 0. Vậy P1 = 0 luôn đạt được, chỉ là search không tìm ra trong budget.

| Biến thể / lớp | P1 = 0 | P1 > 0, stage P1 có cải thiện nhưng chưa tới 0 | P1 > 0, stage P1 không có incumbent nào |
|---|---:|---:|---:|
| SOFT 10 | 27 | 0 | 0 |
| SOFT 20 | 16 | 11 | 0 |
| SOFT 40 | 0 | 18 | **9** (toàn bộ BASE) |
| HARD 10 | 20 | 7 | 0 |
| HARD 20 | 6 | 21 | 0 |
| HARD 40 | 3 | 15 | **9** (toàn bộ BASE) |

**F2 — Stage P1 ăn gần hết budget, và P1 chỉ được chứng minh khi chạm 0.** Best bound của P1 là 0 ở mọi
run có bound (LP bound yếu). Vì vậy tier P1 chỉ OPTIMAL khi tìm được lịch P1 = 0. Thời gian trung vị của
stage P1:

| Lớp | Budget | SOFT | HARD |
|---|---:|---:|---:|
| 10 | 60 s | 15 s | 22 s |
| 20 | 120 s | 71 s | 104 s |
| 40 | 180 s | 143 s | 154 s |

Ở 20/40 lớp, P2/P3 gần như không chạy: tier status phổ biến nhất là `(FEASIBLE, NOT_RUN, NOT_RUN)`. Ở 40
lớp, P1 hầu như không giảm: trung vị từ lời giải hard-only tới lịch cuối là 63 → 61 (SOFT) và 22 → 21
(HARD).

**F3 — Zero-target probe chưa bao giờ cho incumbent.** Theo thiết kế, probe của stage P1 buộc **cả P1, P2
và P3** bằng 0 cùng lúc. Witness có P3 > 0, nên ràng buộc này gần như luôn vô nghiệm:

| Kết quả probe P1 | Số run | Thời gian |
|---|---:|---|
| INFEASIBLE | 108 (MIXED, TIGHT) | khoảng 0 s |
| UNKNOWN (chạm trần 12 deterministic seconds) | 54 (toàn bộ BASE) | 15–22 s mỗi run, tới khoảng 1/3 budget ở 10 lớp |
| Có incumbent | 0 | — |

**F4 — Ở 40 lớp BASE, stage P1 không tìm được incumbent nào trong khoảng 150 s, dù đã có hint.** Lịch trả
về là lời giải hard-only chưa tối ưu (ví dụ mẫu C `[114,446,865]`). `_hint` chỉ gợi ý biến placement
(58–70 % số biến của model), không gợi ý biến penalty hay biến phụ của soft rule. Giả thuyết: CP-SAT
không hoàn thiện được hint thành một lời giải trong model đầy đủ, nên mất luôn incumbent ban đầu.

**F5 — Feasibility thường nhanh và ràng buộc hard variant gần như không làm chậm.** Trung vị feasibility
là 0,3–5,2 s. Ở biến thể HARD (S02, S03, S05, S06 là hard), trung vị ở 40 lớp là 5,2 s, so với 4,2 s ở
SOFT. Ngoại lệ: `c40-tight-s101` mất 85 s (SOFT) và 152 s (HARD).

**F6 — Lặp lại có biến động.** 6/54 dataset cho vector khác nhau giữa ba lần lặp. So sánh trước/sau phải
theo cặp cùng dataset và nên có lặp.

## 3. Hướng cải thiện (ứng viên)

| ID | Hướng | Giả thuyết (từ số đo) | Thay đổi dự kiến | Rủi ro |
|---|---|---|---|---|
| **A1** | Probe P1 = 0 **chỉ cho tier hiện tại** | F3 và F5: buộc P1 = 0 riêng (gần với chạy hard variant của S01, S02, S06) thì khả thi ngay ở mọi dataset (theo witness) và có thể nhanh như feasibility. Có lời giải P1 = 0 thì tier P1 được chứng minh tối ưu ngay | Probe đặt tier hiện tại = 0 thay vì mọi tier `p >= priority`; giữ cap và fallback hiện có | Ở dataset mà search khó, probe tốn thời gian vô ích; cần cap. Phải giữ nguyên semantics "INFEASIBLE của probe không chứng minh gì cho tier gốc" |
| **A2** | Hint đầy đủ | F4: incumbent ban đầu bị mất ở 40 lớp BASE | Gợi ý cả biến penalty và biến phụ, tính từ incumbent đã kiểm; hoặc thêm cutoff để không bao giờ trả lời giải kém hơn incumbent | Phải chứng minh hint không đổi kết quả của model (hint không phải lock); thêm chi phí tính |
| **A3** | Bỏ probe tất-cả-tier khi nó chắc chắn vô ích | F3: probe hiện tại tốn 15–22 s ở BASE mà không bao giờ cho incumbent | Thay bằng A1, hoặc giới hạn theo kết quả đo | Thấp, nếu A1 thay thế được |
| A4 | LNS theo cấu trúc bài toán (GV, ngày, lớp) | F2: cải thiện chậm ở 40 lớp khi đã có incumbent | Neighborhood tùy chỉnh | Việc lớn; chỉ cân nhắc nếu A1–A3 không đủ |

Không đề xuất: tăng budget hay số worker (đổi điều kiện đo P), witness hint (bị cấm), đổi policy hay trọng
số (đổi bài toán, không phải search).

## 4. Cách đo

**Bước S1-a — spike chẩn đoán (không đổi sản phẩm).**
- Làm trong một worktree riêng, thay đổi đặt sau một cờ nội bộ, không merge.
- Tập chẩn đoán: 18 dataset s101 (cùng tập với 3C), mỗi dataset một run cho mỗi biến thể A1, A2, A1 + A2.
  Budget, worker và seed như v2.
- Đo:
  - số lịch đạt M1–M3 của profile v0;
  - P1 cuối cùng và thời điểm lần đầu chạm P1 = 0 (từ `native-calls`);
  - P2/P3;
  - H bằng validator độc lập.
- So theo cặp với chính run `phase2-v2-linux-02` của cùng dataset (r1–r3). Đây là phép đo chẩn đoán, không
  phải evidence nghiệm thu.

**Bước S1-b — triển khai vào Core (cần ủy quyền riêng).**
- Chỉ làm hướng đạt điều kiện ở §5.
- TDD; oracle vét cạn hiện có phải giữ nguyên optimum.
- Regression cho repair (3A/3C): `run_quality` dùng chung với repair, nên phải chạy lại test repair và
  một tập con 3C.
- Cập nhật thiết kế solver.

**Bước S1-c — campaign mới (cần ủy quyền riêng).**
- Campaign v2 mới `phase2-v2-linux-03` với cùng ma trận 216 run, chấm tay theo profile v0.
- So theo cặp với `linux-02`.

## 5. Điều kiện đánh giá (chốt trước khi đo)

Một hướng được đưa sang S1-b khi, trên tập chẩn đoán:

1. không lịch nào mất H PASS, không run nào chuyển từ có lịch sang không có lịch;
2. số lịch đạt M1–M3 **tăng** so với v2 cùng dataset, và không dataset nào giảm từ P1 = 0 sang P1 > 0
   (mức tăng tối thiểu theo R4);
3. không làm chậm feasibility trên dataset đã nhanh: thời gian tới lời giải đầu tiên không tăng quá 10 %
   hoặc 1 s.

Kết quả spike chỉ để chọn hướng. Mọi kết luận về hiệu năng hay chất lượng phải đến từ campaign S1-c.

## 6. Ranh giới

- Không đổi gate, budget, worker, seed hay policy; không dùng witness hint.
- Spike S1-a nằm trong worktree riêng và không merge; mọi thay đổi Core (S1-b) cần duyệt riêng.
- Không sửa evidence của `phase2-v2-linux-02` hay `phase3c-linux-02`.
- Giữ nguyên các bảo đảm hiện có:
  - hint không phải lock;
  - INFEASIBLE của probe không là bằng chứng vô nghiệm của tier;
  - mọi candidate được kiểm lại bằng hard checker và evaluator độc lập.

## 7. Quyết định cần duyệt

- [x] **R1 — Hướng đưa vào spike:** A1, A2 và A1 + A2; A3 đi kèm A1. A4 để sau. *(Đề xuất: chọn.)*
- [x] **R2 — Tập chẩn đoán:** 18 dataset s101, n = 1 mỗi biến thể (khoảng 3 × 18 run × trung bình 2 phút ≈
  1,8 h). Phương án nhỏ hơn là chỉ 40 lớp (6 dataset) cộng 10 lớp BASE. *(Đề xuất: 18 dataset.)*
- [x] **R3 — Nơi chạy spike:** máy Linux của người dùng (cùng máy với v2), có cho phép riêng; không cần
  tmux dài. *(Đề xuất: chọn.)*
- [x] **R4 — Mức tăng tối thiểu ở §5(2):** ít nhất +3 lịch đạt M1–M3 trên 18 dataset (khoảng một ô quy mô
  × biến thể), hay chỉ cần "tăng" mà không đặt mức? *(Đề xuất: +3, chốt trước khi đo.)*
- [x] **R5 — Regression repair** (3A test + tập con 3C) bắt buộc ở S1-b. *(Đề xuất: chọn.)*
- [x] **R6 — Phép đo phụ "nếu có thêm budget"** (ví dụ 2× budget cho 40 lớp, chỉ để biết search có hội tụ
  không, không dùng làm gate): có làm trong spike không? *(Đề xuất: không, để giữ S1 đúng nghĩa "cùng
  điều kiện".)*

## 8. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| A1 giúp ít ở 40 lớp vì chính feasibility kèm P1 = 0 đã khó | Đo riêng 40 lớp; khi đó A4 mới đáng cân nhắc |
| Thay đổi hint hay probe làm đổi kết quả repair (dùng chung `run_quality`) | R5; so 3C theo cặp |
| Cải thiện trên s101 không tổng quát sang s102/s103 | Campaign S1-c dùng cả 3 seed |
| Biến động giữa các lần lặp che hiệu ứng nhỏ | So theo cặp, đặt mức tăng tối thiểu trước (R4), xác nhận bằng S1-c với n = 3 |
| `interleave_search` là Experimental trong OR-Tools 9.15 | Không đổi phiên bản OR-Tools trong S1 |

## 9. Kiểm tra khi soạn

- Số liệu §2 tính lại chỉ đọc từ 162 run primary (không gồm 54 run UNSAT) trong
  `benchmarks/artifacts/hard-feasibility-no-lp/campaign-02/primary/`: `result.json` (tier_runs,
  optimal_prefix, feasibility_run) và `native-calls.jsonl` (stage, mode, status, incumbent, wall time,
  `hint_variables`/`variables`).
- Mô tả probe và hint đối chiếu với `src/tkb_core/solver/objectives.py` (`_solve_tier`, `_hint`,
  `_TIER_SLICE_DETERMINISTIC_SECONDS = 12.0`) và [thiết kế solver](../../solver-design.md).
- Không chạy test, solver hay campaign; không sửa file nào khác.
