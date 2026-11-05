# Phase 2 — đánh giá trạng thái, cập nhật 1

Ngày 2026-11-05. Trạng thái: **S1–S4 ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT theo đề xuất ngày 2026-11-05 (S2 chọn (a): Phase 2 v2 là Linux-only).** Duyệt không phải ủy quyền chạy bước D/E/F. Base `a0f7b80` trên `main`. Bản này
cập nhật [đánh giá Phase 2 ban đầu](phase-2-status-assessment.md) (E1–E4, E6 đã duyệt; E5 chưa quyết
định); nội dung và quyết định của bản đó giữ nguyên.

Đây chỉ là tài liệu đánh giá. Không sửa code, không chạy test, solver hay campaign trong lượt này. Mọi con
số là kết quả **đã lưu** trong các tài liệu được dẫn. Duyệt bản này không phải ủy quyền chạy bước D/E/F.

## 1. Kết luận ngắn

- **Kỹ thuật synthetic: không đổi.** Phase 2 vẫn đạt theo Core First cho S01–S11 cùng hard variants
  S01–S06 (E4). Không có thay đổi nào trong `src/` kể từ bản đánh giá đầu.
- **Vận hành: tooling đã sẵn sàng, vẫn chưa có số đo.** Đã có:
  - tooling đo hiệu năng v2 cho policy 0.4, hiện thực tiêu chí acceptance v2 (H/Q/P/zero, pilot theo D2);
  - một đợt tự rà soát, với F1–F5 đã sửa;
  - một lần diễn tập end-to-end trên cloud, với R1 đã sửa và R2 đã ghi vào tài liệu;
  - runbook và kế hoạch cho các bước D/E/F trên máy Linux.

  **Chưa có số đo nào trên máy đích.** Trục P vẫn chưa nghiệm thu.
- **Tín hiệu đáng chú ý từ diễn tập (không phải evidence):** ở cỡ 10 lớp, hai pilot có lịch đúng hard
  và nằm trong giới hạn, nhưng P1 khác 0 và P2/P3 không được chạy. Pilot HARD mất khoảng 46 s trong 60 s
  chỉ để tìm lịch khả thi. Rủi ro hiệu năng ở cỡ 20/40 lớp, vốn là rủi ro lớn nhất trong bản đầu, nay có
  dấu hiệu cụ thể hơn.
- **Windows:** tooling v2 hiện **chỉ chạy trên Linux** (preflight từ chối nền tảng khác), nên E3 cần thêm
  việc so với giả định ban đầu.

## 2. Đã làm kể từ bản đánh giá đầu (`5d685f9`)

| Commit | Nội dung | Tài liệu |
|---|---|---|
| `42d0ccd` | Kế hoạch hiệu năng v2 (G1–G10 duyệt) | [kế hoạch v2](superpowers/plans/2026-11-05-phase-2-linux-performance-v2.md) |
| `d23124f` | Tooling v2 (Task 1–5): `generate_phase2`, `run_phase2`, `aggregate_phase2`, 70 test; tooling v1 giữ nguyên byte | §11 của kế hoạch v2 |
| `35b0c29` | Sửa F1–F5 của đợt tự rà soát | [rà soát tooling](phase-2-linux-performance-tooling-review.md) |
| `93706e3` | Runbook bước D | [runbook D](phase-2-linux-performance-step-d-runbook.md) |
| `8f4094a` | Kế hoạch bước E (K1–K7 duyệt) | [bước E](superpowers/plans/2026-11-05-phase-2-linux-performance-step-e.md) |
| `f873126` | Sửa R1 (prepare bị từ chối không còn khóa campaign), ghi R2 (cần cgroup2) | [báo cáo E0](phase-2-linux-performance-rehearsal-e0-report.md) |
| `533d6c7` | Báo cáo diễn tập E0 | như trên |
| `a0f7b80` | Kế hoạch bước F (M1–M7 duyệt) | [bước F](superpowers/plans/2026-11-05-phase-2-linux-performance-step-f.md) |

Kiểm tra gần nhất (`f873126`): `uv run --extra solver pytest tests benchmarks/tests` **1352 passed, 8
skipped**; ruff, format và mypy PASS. Wheel không đổi so với 2C-2 (`cdd34282…35d1`), vì `src/` không đổi.
PR duongbui234/vnedu_tkb#4, duongbui234/vnedu_tkb#5 và duongbui234/vnedu_tkb#6 đã merge mà không có
review comment hay CI. Từ sau `812b0b6`, theo yêu cầu người dùng, thay đổi được push thẳng lên `main`,
không qua PR.

## 3. Bảng hạng mục còn mở (cập nhật)

| ID | Hạng mục | Bản đầu | Hiện tại | Cần gì để đóng |
|---|---|---|---|---|
| A | Acceptance v2 | D1–D3 duyệt; protocol chưa triển khai | **Đã hiện thực trong tooling v2**: verdict H/Q/P/zero, pilot theo D2, gate dừng, mẫu số đầy đủ. Chưa áp dụng cho run thật nào | Evidence từ campaign v2 |
| B | Hiệu năng (P) | Không có số đo; harness chỉ biết policy 0.1 | Tooling sẵn sàng. Diễn tập cloud chạy hết preflight → pilot (không phải evidence). **Chưa có số đo trên máy đích** | Bước D → E → F trên máy Linux, rồi báo cáo |
| C | Windows/cross-OS | Chưa chạy cho candidate | **Tooling v2 chỉ hỗ trợ Linux** (preflight dùng `bin/python`, từ chối nền tảng khác). Tooling v1 có runtime Windows nhưng chỉ cho policy 0.1 | Quyết định S2 |
| D | Chất lượng (Q) | REVIEW_REQUIRED; chưa có profile | Không đổi. Diễn tập cho thấy P2/P3 có thể không được tối ưu trong budget, nên Q của campaign nhiều khả năng là WORSE so witness | Quality profile hoặc duyệt kết quả cụ thể, sau campaign |
| E | Benchmark zero | NOT_MET (v1) | v1 giữ nguyên. **v2: NOT_APPLICABLE cho cả 72 dataset**, vì S08/S11 làm P3 của witness dương (G5) | Không cần trong phạm vi v2 |
| F | Dữ liệu thật | UNKNOWN | Không đổi | Ngoài Core |
| G | S12 | Hoãn (E4) | Không đổi | Use case cụ thể |
| H | Chẩn đoán INFEASIBLE | Chưa có | Không đổi | Diagnostics Phase 3 |
| I | Số phiên bản contract | E5 chưa quyết định | Không đổi; tooling v2 không tạo version product mới | Quyết định E5 khi có mốc mới |

## 4. Rủi ro (cập nhật)

- **Hiệu năng vẫn là rủi ro lớn nhất, nay có tín hiệu cụ thể:** biến thể HARD ở 10 lớp đã dùng khoảng
  46 s cho feasibility. Ở 20/40 lớp, khả năng P NOT_MET là đáng kể. Đây là giả thuyết từ cloud với n = 1.
  Campaign sẽ đo; không nới budget (M7).
- **Campaign dài và dễ đứt:** primary cần khoảng 6–10 giờ liền. Ngắt giữa chừng thực tế kết thúc campaign
  (CANCELLED hoặc run dở dang không resume được), nên phải chạy lại với ID mới.
- **Điều kiện máy:** gate headroom chỉ chấp nhận cgroup2 (R2). Máy đích phải đáp ứng, không có đường vòng.
- **Kiểm chứng độc lập vẫn mỏng:** mọi rà soát vẫn là tự kiểm trong cùng phiên (E6). Từ khi push thẳng lên
  `main`, các thay đổi không còn đi qua PR nên càng ít dấu vết review. Tooling v2 thêm khoảng 3 600 dòng
  benchmark code chưa có người thứ hai đọc.
- **Không so được với v1:** rule set, priority và protocol đều khác. Số v2 không được đặt cạnh số v1 như
  cùng bài.

## 5. Thứ tự đề xuất

1. **Người dùng chạy bước D** trên máy Linux (runbook D), gửi kết quả để kiểm.
2. **Bước E** (prepare, warmup, 2 pilot) sau khi D đạt, theo K1–K7.
3. **Bước F** (216 run) chỉ khi pilot đạt và được ủy quyền riêng (M1–M7), rồi aggregate và báo cáo (M6).
4. **Sau khi có số đo:** quyết định hướng hiệu năng (phân tích model, Phase 3 repair) dựa trên dữ liệu,
   không dựa trên diễn tập.
5. **Windows (C)** theo S2, sau campaign Linux.
6. **Quality profile (D)** cùng chủ thể nghiệp vụ, nếu muốn dùng Q làm gate trong tương lai.

## 6. Quyết định cần duyệt

- [x] **S1 — Giữ nguyên thứ tự §5:** không bắt đầu tối ưu solver hay phân tích model trước khi có số đo
  campaign. Tín hiệu từ diễn tập chỉ là giả thuyết. *(Đề xuất: chọn.)*
- [x] **S2 — Phạm vi Windows cho Phase 2:** (a) ghi Phase 2 v2 là **Linux-only**, Windows/cross-OS là
  mốc riêng về sau, có port tooling v2; hoặc (b) port tooling v2 sang Windows trước campaign Linux. *(Đề
  xuất: (a), vì port là việc lớn và nên làm sau khi biết candidate có đáng nghiệm thu trên Linux không,
  đúng tinh thần E3.)*
- [x] **S3 — Review người thứ hai** cho tooling v2 và các contract 2B/2C trước khi dùng kết quả campaign
  để ra quyết định sản phẩm, hoặc trước khi dùng dữ liệu thật (mở rộng E6). *(Đề xuất: chọn; không chặn
  việc chạy D/E/F.)*
- [x] **S4 — Quy trình push thẳng `main`:** giữ như người dùng yêu cầu, nhưng mỗi commit vẫn cần duyệt
  riêng, và mỗi thay đổi code vẫn kèm test cùng một ghi chú rà soát trong `docs/`. *(Đề xuất: chọn.)*

E5 (chính sách version) vẫn chưa quyết định và không ảnh hưởng các bước trên.
