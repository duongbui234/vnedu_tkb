# Core so với lịch STKB trên dữ liệu thật: số worker, tính công bằng, RAM

Ngày 2026-11-08. Trạng thái: **DRAFT, chờ người dùng duyệt.** Đây là phép đo chẩn đoán
trên dữ liệu thật, không phải evidence nghiệm thu. Mỗi cấu hình chạy n = 1, seed 42.

Trường được ghi bằng mã ẩn danh R01…R50. Bảng đối chiếu sang site_id chỉ lưu local ở
`benchmarks/artifacts/real/school-pseudonyms.csv` (gitignore); thư mục kết quả local vẫn đặt theo
site_id (`<site>`).

Báo cáo có năm phần, mới nhất trước:

- **Phần L5 (lượt 5):**
  - nối nghĩa khung tiết GV từ binary và đưa vào thang theo trường;
  - chạy lại cả hai kịch bản Nghỉ hard và Nghỉ soft với 4 worker;
  - chứng minh số tiết tối thiểu trên ô Nghỉ của trường R17.

- **Phần L4 (lượt 4):** giới hạn tải GV theo cấu hình STKB của từng trường thay cho ngưỡng chung; Nghỉ ở
  P1 cho trường R17. Chỉ chạy kịch bản Nghỉ soft, 4 worker.
- **Phần 0 (lượt 3):** thêm ràng buộc giáo viên (Họp, Nghỉ, Bận, Hạn chế) và tiết khóa từ phần cuối file
  STKB; so 33 trường với 2 và 4 worker, hai kịch bản Nghỉ hard / Nghỉ soft.
- **Phần A (lượt 2):** so 34 trường sau khi chặn ô theo lớp, với 2, 4 và 8 worker.
- **Phần B (lượt 1, §1–§9):** chẩn đoán trên 3 trường xem Core thua vì thiếu thời gian hay vì cách tìm.

**Kết luận ngắn:**

1. **Cùng ràng buộc, Core tốt hơn STKB** ở mọi trường so được, với 4 worker:
   - **Thang chung, Nghỉ hard** (Phần 0): 29/29 trường.
   - **Thang chung, Nghỉ soft** (Phần 0): 33/33 trường.
   - **Thang theo trường, Nghỉ soft** (Phần L4): 33/33 trường, với khoảng cách lớn hơn.
   - **Thang theo trường có khung tiết, Nghỉ hard** (Phần L5): 29/29 trường. P1 chứng minh tối ưu ở
     32/32. Tiết GV dạy ngoài khung: STKB 72, Core 16.
   - **Thang theo trường có khung tiết, Nghỉ soft** (Phần L5): 33/33 trường, P1 chứng minh tối ưu ở
     33/33. Core [1, 61, 1161] so với STKB [110, 1052, 3951]; tiết ngoài khung: STKB 72, Core 17.
2. **Thang theo trường giữ nguyên kết luận.** 22/33 trường không bật giới hạn tải GV nào trong STKB. Khi
   bỏ ngưỡng chung, tổng P1 của STKB giảm từ 770 xuống 110, nhưng Core vẫn tốt hơn ở 33/33 trường và
   chứng minh P1 tối ưu ở 33/33.
3. **Nghỉ:** ở trường R17 (59 lớp), Core xếp vào ô Nghỉ ít hơn STKB (71) trong mọi cấu hình trừ
   cấu hình cũ (thang chung, Nghỉ ở P2: 236):
   - Nghỉ ở P1, thang chung: 32;
   - Nghỉ ở P1, thang theo trường: 17;
   - Nghỉ ở P2, thang theo trường: 20.

   Con số 236 ở lượt 3 là do ngưỡng chung "GV ≤ 4 tiết/buổi" đứng trên Nghỉ, mà trường này không đặt
   ngưỡng đó.

   **Lượt 5 chứng minh 17 là tối thiểu** (8 worker, chỉ Nghỉ ở P1, tối ưu sau 19 s): không lịch hợp lệ
   nào đặt ít hơn 17 tiết vào ô Nghỉ.
4. **Số worker:** không dùng 1 worker (Phần B). Có ràng buộc giáo viên và tiết khóa thì 2 worker không
   còn đủ cho mọi trường; **nên dùng 4 worker**, nhất là với trường từ 31 lớp trở lên.
5. **RAM (RSS đỉnh):** với 4 worker, cao nhất 1,5 GB, trung vị 0,6 GB; với 2 worker, cao nhất 1,2 GB.
   Lượt 2 có 8 worker: cao nhất 2,3 GB. Chỉ đo trên Linux.

## Phần L5 — Lượt 5: khung tiết GV, Nghỉ hard với thang theo trường, chứng minh P1 cho R17

### L5.1. Khung tiết GV: nghĩa đọc từ binary

Record thuộc tính 96 byte của GV (L4.1) có thêm hai khung tiết:

- byte +3 bật khung buổi sáng; tiết đầu, tiết cuối là i32 tại +32, +36;
- byte +4 bật khung buổi chiều; i32 tại +40, +44.

Hàm chấm là `CAlgAutoSFNew::GetValue_FromT1toT2` (0x6c5a40), đọc bằng objdump:

- Trường `this+0x1d7004` chọn buổi: 0 dùng cờ +3 và +32/+36, khác 0 dùng cờ +4 và +40/+44. Cờ tắt thì
  hàm trả 0.
- Với mỗi thứ 1..7 và mỗi tiết p < T1 hoặc p > T2 (p ≤ 5), nếu ô `[this+0x1fcb10 + 16p + 96·(thứ +
  8·GV)]` > 0 (GV có tiết), hàm cộng hệ số tại `this+0x74b2f0`. Đây cùng lưới ô GV mà
  `GetValue_MaxTietBuoi` (0x6c5510) đọc.
- `this+0x1d7004` do hai handler 0x482fd0 / 0x482ff0 ghi 0 / 1 rồi gọi `InitProgress`. Hai handler gắn
  với lệnh 1752 / 1753; trong dialog 290 "Tự động xếp thời khóa biểu", 1752 là "Buổi Sáng", 1753 là
  "Buổi Chiều". Vậy 0 là buổi sáng.

**Kết luận:** khung tiết là phạt mềm, mỗi tiết GV dạy ngoài khung bị cộng một hệ số. Hệ số này là 4
(báo cáo 06), so với Nghỉ 30, Bận 5, Hạn chế 2, MaxTietBuoi 5. Nên khung tiết ngang mức Bận/Hạn chế.

Trên 33 trường:

- Có 82 khung bật ở 14 trường, tất cả hợp lệ (1 ≤ đầu ≤ cuối ≤ 5).
- 35 khung không loại ô nào của khung tiết trường, trong đó 31 khung là 1–5.
- Còn **40 GV ở 11 trường** có khung thật sự, với 298 ô nằm ngoài khung. Lịch STKB đặt **72 tiết** vào
  các ô đó.

**Cách đưa vào thang theo trường** (`convert_real.py --teacher-windows`): mỗi GV có khung thêm một rule
`TEACHER_AVOID_SLOTS` (id `S01K-<GV>`) phủ các ô ngoài khung, ở **P2**, cùng mức với Bận/Hạn chế.
Không truyền `--teacher-limits` và `--teacher-windows` thì input giống hệt lượt 3. Có 4 test dữ liệu giả
mới; tổng 47 test qua.

### L5.2. Cách bố trí chạy

- **Batch Nghỉ hard, thang theo trường** (giới hạn tải + khung tiết), `stkb-v5-hard`:
  - 33 job × 4 worker, 180 s;
  - 5 job cùng lúc trên ngân sách 20 luồng;
  - tổng **18,8 phút**, luồng cao nhất 20, 0 lỗi, 0 watchdog.
  - Mức tranh CPU giống cột 4 worker của lượt 3 và lượt 4.
- **R17, Nghỉ ở P1, 8 worker, 600 s** (input lượt 4, `stkb-v4-p1school` và `stkb-v4-p1common`):
  - 2 job × 8 worker = 16/20 luồng chạy cùng lúc;
  - 10,4 phút.
- **R17, chỉ Nghỉ ở P1** (chẩn đoán, `stkb-v5-nghionly`):
  - 1 job × 8 worker, 600 s;
  - chạy riêng sau batch, nên ít tranh CPU hơn hai job trên.

### L5.3. Kết quả: Nghỉ hard, thang chung (lượt 3) so với thang theo trường (lượt 5), 4 worker

| | Thang chung (lượt 3) | Thang theo trường + khung tiết (lượt 5) |
|---|---|---|
| Core tốt hơn STKB | 29/29 | **29/29** |
| Không so được | 4 trường: lịch STKB vi phạm hard | 4 trường, như lượt 3 |
| P1 chứng minh tối ưu | 29/32 | **32/32** |
| Tối ưu cả 3 mức | 6/32 | 10/32 |
| Tổng STKB `[P1, P2, P3]` (29 trường) | [686, 1210, 3298] | [109, 772, 3298] |
| Tổng Core `[P1, P2, P3]` (29 trường) | [122, 304, 1589] | **[1, 34, 805]** |
| Lịch Core hợp lệ / điểm khớp | 32/32 | 32/32 |
| RSS đỉnh: cao nhất / trung vị | 1,40 / 0,57 GB | 1,40 / 0,54 GB |

- R17 vô nghiệm khi Nghỉ là hard ở cả hai thang; Core chứng minh vô nghiệm trong 6 s.
- 4 trường có lịch STKB vi phạm hard (R29, R12, R34, R17) giống lượt 3.

Theo quy mô trường (thang theo trường):

| Nhóm | STKB | Core |
|---|---|---|
| ≤ 18 lớp (6) | [7, 143, 398] | [0, 14, 121] |
| 19–30 lớp (11) | [47, 236, 1150] | [0, 4, 212] |
| ≥ 31 lớp (12) | [55, 393, 1750] | [1, 16, 472] |

Từng rule, thang theo trường (tổng vi phạm thô; số trường Core tốt hơn / bằng / kém):

| Rule (mức) | STKB | Core | Tốt hơn / bằng / kém |
|---|---:|---:|---|
| CLASS_SUBJECT_MAX_PERIODS_PER_DAY (P1) | 107 | 1 | 13 / 16 / 0 |
| TEACHER_MAX_PERIODS_PER_SESSION (P1, chỉ GV bật) | 2 | 0 | 1 / 6 / 0 |
| TEACHER_AVOID_SLOTS — Bận/Hạn chế + khung tiết (P2) | 65 | **16** | 8 / 5 / 0 |
| SUBJECT_COMPONENT_DAY_SPREAD (P2) | 528 | 17 | 26 / 3 / 0 |
| TEACHER_MAX_GAP_RUN (P2) | 173 | 2 | 20 / 9 / 0 |
| TEACHER_MAX_PERIODS_PER_DAY (P2, chỉ GV bật) | 6 | 0 | 1 / 6 / 0 |
| TEACHER_SINGLE_PERIOD_SESSION (P3) | 747 | 433 | 19 / 1 / 9 |
| TEACHER_TOTAL_GAPS (P3) | 2551 | 431 | 28 / 1 / 0 |

**Riêng khung tiết** (đếm tiết GV nằm ngoài khung, 32 trường Core có lịch hợp lệ):

- STKB 72 tiết, Core 16.
- Core ít hơn ở 8 trường, bằng ở 1 trường, không trường nào nhiều hơn.
- Phần lớn tiết ngoài khung của Core nằm ở trường R37 (16 GV có khung, 96 ô ngoài khung): STKB
  38, Core 14. Ở đây khung tiết cùng mức P2 với giãn ngày và chuỗi tiết trống, nên Core đổi qua lại giữa
  các rule này.

**Nhận xét:**

- Kết luận lượt 3 giữ nguyên: với Nghỉ hard, Core tốt hơn STKB ở 29/29 trường so được. Khoảng cách lớn
  hơn khi bỏ ngưỡng chung, giống lượt 4 ở kịch bản Nghỉ soft.
- STKB tôn trọng khung tiết kém hơn giới hạn tải: 72 tiết ngoài khung, so với 2 tiết vượt max/buổi và 6
  tiết vượt max/ngày. Điều này hợp với hệ số: khung tiết 4, Nghỉ 30.

### L5.4. R17: số tiết tối thiểu phải nằm trên ô Nghỉ

Lượt 4 chạy 4 worker, 180 s, và không chứng minh được P1 ở cấu hình Nghỉ P1. Lượt này chạy 8 worker,
600 s:

| Cấu hình (Nghỉ/Bận/Hạn chế ở P1) | P1 | Chứng minh | Tiết trên ô Nghỉ | Điểm Core | Điểm STKB |
|---|---:|---|---:|---|---|
| Thang theo trường | **17** | **tối ưu sau 95 s** | 17 | [17, 7, 328] | [71, 43, 268] |
| Thang chung | **32** | **tối ưu sau 532 s** | 24 | [32, 52, 342] | [129, 55, 268] |

- P1 thang chung gồm 24 tiết trên ô Nghỉ và 8 tiết vượt "≤ 4 tiết/buổi".
- Với 8 worker, P2 chưa chứng minh xong, còn P3 chưa chạy. RSS đỉnh 1,75 GB (thang theo trường) và
  1,46 GB (thang chung).

Ở hai cấu hình này, P1 là tổng của Nghỉ, Bận, Hạn chế và môn/lớp/ngày (và S02 ở thang chung). Nên 17 là
tối thiểu của tổng đó, chưa phải tối thiểu của riêng Nghỉ. Để có câu trả lời trực tiếp, input chẩn đoán
`stkb-v5-nghionly` chỉ để ở P1 một rule `TEACHER_AVOID_SLOTS` phủ 1.066 ô Nghỉ. Môn/lớp/ngày và 5 ô
Bận/Hạn chế chuyển xuống P2. Fingerprint được tính lại, `real-assignments.json` giữ nguyên lịch STKB.

Kết quả (8 worker, 600 s, chạy một mình, 8/20 luồng, 10,3 phút):

| | Lịch STKB | Core |
|---|---:|---:|
| Tiết trên ô Nghỉ (P1) | 71 | **17, chứng minh tối ưu sau 19 s** |
| P2 | 43 | 7, chứng minh tối ưu sau 255 s |
| P3 | 268 | 133 (cận dưới 49, hết giờ) |

**Trả lời:** với Họp, tiết khóa và ô được học của lớp là hard, **mọi lịch hợp lệ của trường R17
phải đặt ít nhất 17 tiết vào ô Nghỉ**, và Core đạt đúng 17. Lịch STKB đặt 71. Con số này khớp P1 = 17 ở
cấu hình thang theo trường (trường không bật giới hạn tải và không có khung tiết). Vì vậy lời giải đó cũng
không xếp tiết nào vào ô Bận/Hạn chế hay vượt môn/lớp/ngày.

- Khi P1 chỉ còn Nghỉ, chứng minh nhanh hơn: 19 s so với 95 s.
- RSS đỉnh 1,70 GB.
- 17 là tối thiểu với dữ liệu đã chuyển đổi. Các tiết chia nhóm/lớp ghép bị loại vẫn chặn ô như mô tả ở
  README, và lịch STKB vẫn hợp lệ với input này.

### L5.5. Nghỉ soft, thang theo trường có khung tiết (4 worker)

Chạy lại kịch bản Nghỉ soft để hai kịch bản dùng cùng thang.

**Input** (`stkb-v5-soft`): giống hệt input lượt 4 (`stkb-v4-school`) ở cả 33 trường, chỉ thêm các rule
khung tiết `S01K-*`; lịch thật cũng giống hệt.

**Cách bố trí chạy:**

- 33 job × 4 worker, 180 s;
- 5 job cùng lúc trên 20 luồng;
- **19,2 phút**, 0 lỗi, 0 watchdog.

Mức tranh CPU giống lượt 4.

| | Lượt 4 (không khung tiết) | Lượt 5 (có khung tiết) |
|---|---|---|
| Core tốt hơn STKB | 33/33 | **33/33** |
| P1 chứng minh tối ưu | 33/33 | **33/33** |
| Tối ưu cả 3 mức | 10/33 | 8/33 |
| Tổng STKB `[P1, P2, P3]` | [110, 980, 3951] | [110, 1052, 3951] |
| Tổng Core `[P1, P2, P3]` | [1, 47, 1142] | **[1, 61, 1161]** |
| Lịch Core hợp lệ / điểm khớp | 33/33 | 33/33 |
| RSS đỉnh: cao nhất / trung vị | 1,41 / 0,58 GB | 1,33 / 0,58 GB |

- **Rule TEACHER_AVOID_SLOTS** (Nghỉ/Bận/Hạn chế + khung tiết, P2): STKB 250, Core 36. Core tốt hơn ở
  12 trường, bằng ở 6, kém ở 0.
- **Riêng khung tiết:** STKB 72 tiết ngoài khung, Core 17. Core ít hơn ở 8 trường, bằng ở 1. Gần như
  trùng với kịch bản Nghỉ hard (Core 16).
- **Trường R17:** Core đặt 19 tiết vào ô Nghỉ (lượt 4: 20), STKB đặt 71. Trường này không có khung
  tiết, nên chênh 1 tiết là do lượt chạy (n = 1, cùng seed nhưng tìm kiếm song song không tất định). Mức
  tối thiểu đã chứng minh là 17 (L5.4).
- **Giá phải trả:** thêm khung tiết thì P2 của Core tăng từ 47 lên 61, P3 từ 1142 lên 1161, vì Core phải
  tránh thêm 298 ô ngoài khung. Khoảng cách với STKB vẫn lớn.

### L5.6. Giới hạn

- n = 1, seed 42, chỉ 4 worker cho hai batch.
- Khung tiết đặt ở P2 vì hệ số STKB (4) ngang Bận/Hạn chế. STKB dùng tổng có hệ số; thứ tự P1/P2/P3 là
  của dự án.
- Thuộc tính nhóm GV (72 byte/nhóm) và các trường khác của record GV chưa đưa vào.
- Kết quả local: `benchmarks/artifacts/real/stkb-v5-hard/<site>/cmp-w4/`,
  `stkb-v5-soft/<site>/cmp-w4/`,
  `stkb-v4-p1{school,common}/R17/cmp-w8/`, `stkb-v5-nghionly/R17/cmp-w8/`; CSV ở
  `stkb-v5/`.

## Phần L4 — Lượt 4: giới hạn tải GV theo từng trường (33 trường, 4 worker, Nghỉ soft)

### L4.1. Thuộc tính GV đọc được và cách đưa vào thang chấm

Theo [báo cáo 08 §4](research/stkb/08-suffix-constraints-and-locks.md), mỗi GV có một record thuộc tính
96 byte. Các trường dùng ở đây đã được xác minh trên binary:

- byte +1: bật max tiết/buổi; giá trị là i32 tại +24 (`GetValue_MaxTietBuoi`);
- byte +2: bật max tiết/ngày; giá trị là i32 tại +28 (`GetValue_MaxTietNgay`).

Giới hạn không bật thì bỏ qua, dù file có lưu giá trị. Nhiều file lưu sẵn 5 và 10 ở các GV không bật;
nếu dùng thì sẽ đoán sai.

Số GV bật giới hạn trong 33 trường, trên khoảng 2.200 GV:

| Giới hạn | Số GV bật | Số trường | Mức hay gặp |
|---|---:|---:|---|
| Max tiết/buổi | 33 | 9 | 5 (25 GV), 4 (5 GV) |
| Max tiết/ngày | 54 | 8 | 6 (20 GV), 5 (20 GV) |

11/33 trường có ít nhất một GV bật giới hạn. **22 trường không bật giới hạn tải GV nào.** Không có giá trị
bật nào nhỏ hơn 1.

**Thang theo trường** (`convert_real.py --teacher-limits`):

- S02 (tiết/buổi, P1) và S03 (tiết/ngày, P2) chỉ có với GV đã bật giới hạn đó, đúng mức trường đặt.
- GV không bật thì không có hai rule này.
- Các rule khác giữ thang chung, vì chúng không phải thuộc tính GV: S06 môn/lớp/ngày, S09 chuỗi tiết
  trống, S05 giãn ngày, S08, S11. STKB lưu chúng ở chỗ khác (hệ số và thuộc tính môn), chưa nối nghĩa
  đủ để thay.
- Khung tiết của GV (byte +3/+4, `GetValue_FromT1toT2`) chưa đưa vào ở lượt này, vì chưa rõ STKB chấm
  khung này ra sao. Lượt 5 đã nối nghĩa và đưa vào (L5.1).

Kiểm tra:

- `stkb_to_csv.py` ghi thêm `teacher-limits.csv`; 4 file CSV cũ giống hệt lượt 3.
- Khi không truyền `--teacher-limits`, input sinh ra giống hệt input lượt 3.
- Có 5 test dữ liệu giả mới (cờ tắt, giá trị không dùng được, trọn vòng CSV, GV thiếu, priority). Tổng
  43 test qua.

### L4.2. Cách bố trí chạy

- Có 35 job, mỗi job 4 worker, 180 s:
  - 33 trường, thang theo trường, Nghỉ soft ở P2;
  - R17, Nghỉ ở P1, thang chung;
  - R17, Nghỉ ở P1, thang theo trường.
- Ngân sách 20 luồng, nên 5 job chạy cùng lúc (5 × 4 = 20 luồng), trường lớn trước.
- Tổng **19,9 phút**; luồng dùng cao nhất là 20; 0 lỗi; 0 lượt bị watchdog dừng.
- `stkb-v4-school/layout.jsonl` giờ ghi thư mục gốc của từng job.
- Mức tranh CPU giống lượt 3 ở 4 worker: 5 job × 4 worker trên 20 luồng (6 nhân P có hyperthreading,
  8 nhân E). Vì vậy so lượt 4 với cột 4 worker của lượt 3 là công bằng về CPU.

### L4.3. Kết quả: thang chung so với thang theo trường (Nghỉ soft, 4 worker)

| | Thang chung (lượt 3) | Thang theo trường (lượt 4) |
|---|---|---|
| Core tốt hơn STKB | 33/33 | **33/33** |
| P1 chứng minh tối ưu | 28/33 | **33/33** |
| Tối ưu cả 3 mức | 7/33 | 10/33 |
| Tổng STKB `[P1, P2, P3]` | [770, 1592, 3951] | [110, 980, 3951] |
| Tổng Core `[P1, P2, P3]` | [130, 826, 2581] | **[1, 47, 1142]** |
| Lịch Core hợp lệ / điểm khớp | 33/33 | 33/33 |

Theo quy mô trường (thang theo trường):

| Nhóm | STKB | Core |
|---|---|---|
| ≤ 18 lớp (6) | [7, 95, 398] | [0, 0, 80] |
| 19–30 lớp (12) | [48, 231, 1230] | [0, 3, 251] |
| ≥ 31 lớp (15) | [55, 654, 2323] | [1, 44, 811] |

Từng rule, thang theo trường (tổng vi phạm thô; số trường Core tốt hơn / bằng / kém):

| Rule (mức) | STKB | Core | Tốt hơn / bằng / kém |
|---|---:|---:|---|
| CLASS_SUBJECT_MAX_PERIODS_PER_DAY (P1) | 107 | 1 | 13 / 20 / 0 |
| TEACHER_MAX_PERIODS_PER_SESSION (P1, chỉ GV bật) | 3 | 0 | 2 / 7 / 0 |
| TEACHER_AVOID_SLOTS — Nghỉ/Bận/Hạn chế (P2) | 178 | **20** | 5 / 5 / 0 |
| SUBJECT_COMPONENT_DAY_SPREAD (P2) | 566 | 19 | 29 / 4 / 0 |
| TEACHER_MAX_GAP_RUN (P2) | 230 | 8 | 23 / 10 / 0 |
| TEACHER_MAX_PERIODS_PER_DAY (P2, chỉ GV bật) | 6 | 0 | 1 / 7 / 0 |
| TEACHER_SINGLE_PERIOD_SESSION (P3) | 906 | 486 | 25 / 1 / 7 |
| TEACHER_TOTAL_GAPS (P3) | 3045 | 656 | 31 / 0 / 2 |

- **STKB gần như tôn trọng giới hạn mà trường đã bật:** chỉ 3 tiết vượt max/buổi và 6 tiết vượt
  max/ngày. Phần lớn vi phạm P1 của STKB ở lượt 3 (663 tiết theo ngưỡng chung "≤ 4 tiết/buổi") đến từ
  ngưỡng mà trường không đặt.
- **Core không vi phạm giới hạn nào trường đã bật.** Còn 1 vi phạm P1 (môn/lớp/ngày) ở một trường từ 31
  lớp trở lên.
- **Bỏ ngưỡng chung giúp Core tốt hơn ở P2, P3.** Thứ tự từ điển ưu tiên P1, nên khi P1 không còn ép
  "≤ 4 tiết/buổi", Core có chỗ để giảm vi phạm P2 và P3. Core tránh ô Nghỉ/Bận/Hạn chế tốt hơn STKB:
  20 so với 178. Lượt 3, với ngưỡng chung, là 253 so với 178.
- **STKB vẫn tốt hơn ở P3 một số trường:** 7 trường về số buổi GV chỉ có 1 tiết, 2 trường về tổng tiết
  trống. Thứ tự từ điển không đổi vì Core tốt hơn ở mức cao hơn.

### L4.4. Nghỉ ở P1 cho trường R17

Trường 59 lớp, 1.066 ô Nghỉ, 440 tiết khóa. Theo lượt 3, trường này vô nghiệm khi coi Nghỉ là hard.
Trường không bật giới hạn tải GV nào, nên thang theo trường không có S02/S03. Bảng đếm **số tiết nằm
trên ô Nghỉ**, không tính Bận/Hạn chế, với 4 worker và 180 s:

| Cấu hình | Tiết trên ô Nghỉ | Điểm STKB | Điểm Core | Mức chứng minh tối ưu |
|---|---:|---|---|---|
| Lịch STKB | **71** | | | |
| Thang chung, Nghỉ P2 (lượt 3) | 236 | [58, 126, 268] | [6, 374, 473] | không mức nào |
| Thang chung, **Nghỉ P1** | **32** | [129, 55, 268] | [40, 150, 396] | không mức nào |
| Thang theo trường, Nghỉ P2 | **20** | [0, 114, 268] | [0, 28, 314] | P1 |
| Thang theo trường, **Nghỉ P1** | **17** | [71, 43, 268] | [17, 124, 357] | không mức nào |

- Đưa Nghỉ lên P1 làm số tiết trên ô Nghỉ giảm từ 236 xuống 32 với thang chung, và còn 17 với thang theo
  trường. Cả bốn cấu hình Core đều tốt hơn STKB theo thứ tự từ điển của chính cấu hình đó.
- Không cấu hình nào về 0, khớp với chứng minh vô nghiệm ở lượt 3. Ở hai cấu hình Nghỉ P1, P1 chưa được
  chứng minh tối ưu trong 180 s, nên 17 và 32 là cận trên. Chưa biết số tiết tối thiểu phải nằm trên ô
  Nghỉ.
- Với thang theo trường, đặt Nghỉ ở P1 hay P2 cho kết quả gần như nhau (17 so với 20): P1 chỉ còn rule
  môn/lớp/ngày, mà rule này bằng 0 ở cả hai lịch. Vấn đề của lượt 3 là ngưỡng chung, không phải mức của
  Nghỉ.

### L4.5. Giới hạn

- n = 1, seed 42, 4 worker, chỉ kịch bản Nghỉ soft. Không chạy lại 2 worker hay kịch bản Nghỉ hard với
  thang theo trường.
- Thang theo trường chỉ thay S02 và S03. Thứ tự P1, P2, P3 và các ngưỡng S06, S09, S05 vẫn là của dự án,
  không phải của STKB. STKB dùng tổng có hệ số (báo cáo 06), không dùng thứ tự từ điển.
- Khung tiết của GV và thuộc tính nhóm GV chưa đưa vào.
- Kết quả local: `benchmarks/artifacts/real/stkb-v4-school/<site>/cmp-w4/`,
  `stkb-v4-p1common/R17/`, `stkb-v4-p1school/R17/`; CSV ở `stkb-v4/`.

---

## Phần 0 — Lượt 3: cùng ràng buộc giáo viên và tiết khóa (33 trường, 2/4 worker)

### 0.1. Thay đổi so với lượt 2

- **Bộ đọc phần cuối file** (`reverse-engineering/scripts/inspect_stkb_suffix.py`, chỉ dùng cho nghiên
  cứu, đã gitignore). Trước đây đọc được 12/34 trường, nay đọc được **33/34**. Ba nguyên nhân lỗi căn
  chỉnh đều được xác nhận bằng binary, không đoán layout:
  - **File kết thúc sớm.** Mọi trường được đọc qua `CFile::Read` (mfc140u ordinal 12351). Hàm này gọi
    `ReadFile` và trả về số byte đọc được mà không so với số byte cần. Không có call site nào trong 111
    call site của hàm đọc 0x443310 kiểm kết quả. Vì vậy STKB mở file thiếu đuôi mà không báo lỗi, và các
    trường phía sau giữ giá trị cũ. Bộ đọc chỉ chấp nhận file kết thúc **đúng ở ranh giới một section**,
    ghi `absent_from` và coi phần sau là UNKNOWN. Nếu file kết thúc giữa một section thì vẫn báo lỗi.
  - **Kế hoạch đang bật.** Layout đọc từ hàm 0x444900–0x444b1b: với mỗi buổi, 12 B × môn × lớp, 12 B ×
    lớp × 35, 12 B × GV × 35 và 8 B × phòng × 35.
  - **Chuỗi rỗng.** `FReadString` (Common.dll 0x10006221) chấp nhận độ dài 0.

  Trường còn lại (R41) có 168 byte 0 dư trong bản ghi thực thể thứ hai. Chưa xác định nghĩa của số
  byte này, nên không đoán và loại trường khỏi lượt này.
- **`stkb_to_csv.py`** ghi thêm:
  - `teacher-cells.csv` (`ma_gv,thu,buoi,tiet,loai`): `hop` (1000–1006), `nghi` (998), `ban` (999),
    `hanche` (997); mã lạ ghi thành `ma_<số>`;
  - `locks.csv` (ô có cờ khóa).
- **`convert_real.py`** ghi `available_slot_ids` cho GV (bỏ ô thuộc loại hard) và `locked_assignments`.
  - Mỗi ô khóa khóa tiết chứa nó, tại ô bắt đầu của block.
  - Các loại không hard thành rule mềm `TEACHER_AVOID_SLOTS` (S01) ở P2.
  - Lịch STKB và lịch Core được chấm cùng rule đó.
  - Không sửa `src/`.
- Test: 45 test dùng dữ liệu giả đều qua (38 ở `tools/real_data/tests`, 7 ở bộ đọc nghiên cứu). Có test
  cho layout kế hoạch, cho EOF ở ranh giới và cho EOF giữa section.

### 0.2. Hai kịch bản

Họp luôn là hard; Bận và Hạn chế luôn là soft; tiết khóa giống nhau ở cả hai kịch bản.

| | Nghỉ hard | Nghỉ soft |
|---|---|---|
| Ô Họp bị chặn | 5.188 | 5.188 |
| Ô Nghỉ | 3.284 bị chặn (14 ô để mở vì trùng tiết khóa) | 3.298 thành S01, P2 |
| Tiết khóa | 832 tiết, từ 1.116 ô; 0 ô khóa nằm ở ô trống | như bên trái |
| Lịch STKB hợp lệ hard | **29/33** (177 tiết STKB nằm trên ô Nghỉ) | 33/33 |

- 18/33 trường có mã ô giáo viên.
- 7/33 trường có ô khóa. Ở 6 trường, ô khóa thêm tiết khóa mới. Ở trường còn lại, cả 21 ô khóa rơi vào
  Chào cờ/Sinh hoạt, vốn đã khóa theo tên.
- 13 trường không có cả hai, nên với các trường này lượt 3 giải cùng bài toán như lượt 2.

### 0.3. Cách bố trí chạy

- 33 trường × 2 kịch bản × {2, 4} worker = **132 lượt**, 180 s mỗi lượt; watchdog là giới hạn + 300 s;
  không chạy lại lượt nào.
- `run_batch.py` dùng chung một ngân sách **20 luồng** (`nproc`; i7-12700H có 6 nhân P có
  hyperthreading và 8 nhân E) cho cả hai thư mục kịch bản.
  - Job 4 worker chạy trước, rồi đến 2 worker; trong mỗi mức, trường lớn chạy trước.
  - Lượt hard và lượt soft của cùng một trường chạy gần cùng lúc.
- Số luồng dùng cao nhất là 20, không chạy chồng luồng. Tổng thời gian **58,4 phút**; 0 lỗi; 0 lượt bị
  watchdog dừng. Thời gian thực mỗi lượt có trung vị 187–188 s, cao nhất 207 s.
- **Thiên lệch:** cũng như lượt 2, worker có thể rơi vào luồng hyperthread hoặc nhân E. Vì vậy số liệu là
  cận dưới, nhất là với 2 worker. Hard và soft của cùng một trường chịu mức tranh CPU tương tự nhau.
- `layout.jsonl` nằm trong `stkb-v3-hard/`. Ở lượt này, sự kiện start/end chưa ghi thư mục gốc, nên log
  không tách được job hard và job soft; lỗi đã sửa cho các lượt sau. Kết quả theo trường không bị ảnh
  hưởng vì mỗi lượt ghi vào thư mục riêng.

### 0.4. Kết quả

| Kịch bản | Worker | Core tốt hơn | STKB tốt hơn | Không so được | P1 chứng minh tối ưu | Tối ưu cả 3 mức |
|---|---:|---:|---:|---:|---:|---:|
| Nghỉ hard | 2 | 28 | 1 | 4 | 28/33 | 4/33 |
| Nghỉ hard | 4 | **29** | 0 | 4 | 29/33 | 6/33 |
| Nghỉ soft | 2 | 32 | 1 | 0 | 28/33 | 4/33 |
| Nghỉ soft | 4 | **33** | 0 | 0 | 28/33 | 7/33 |

Mọi lịch Core trả về đều hợp lệ hard, và điểm Core tự tính khớp điểm chấm độc lập (32/32 ở kịch bản
hard, 33/33 ở kịch bản soft).

**4 trường "không so được" trong kịch bản Nghỉ hard** là các trường mà chính lịch STKB vi phạm Nghỉ:

| Trường | Lớp | Tiết STKB trên ô Nghỉ | Core 2 worker | Core 4 worker |
|---|---:|---:|---|---|
| 3050… | 32 | 56 | hợp lệ, [0, 0, 49] | hợp lệ, [0, 0, 46] |
| 4334… | 19 | 4 | hợp lệ, [0, 0, 36] | hợp lệ, [0, 0, 30] |
| 5797… | 44 | 42 | hợp lệ, [0, 10, 8] | hợp lệ, [0, 10, 4] |
| 3114… | 59 | 54 | UNKNOWN (không có lời giải) | **INFEASIBLE** |

Ở trường 3114, CP-SAT với 4 worker chứng minh không có lịch nào vừa giữ 440 tiết khóa vừa tránh 1.052 ô
Nghỉ. Không có mâu thuẫn ở mức đếm: không GV, lớp hay phân công nào có số tiết vượt số ô còn mở, và
không tiết khóa nào nằm trên ô bị chặn. Đây là kết quả của bài toán, không phải lỗi của Core: STKB cũng
không xếp được lịch hợp lệ cho trường này.

**Tổng điểm `[P1, P2, P3]`**, chỉ tính các trường mà cả hai lịch đều hợp lệ:

| Kịch bản (số trường) | Nhóm | STKB | Core 2 worker | Core 4 worker |
|---|---|---|---|---|
| Nghỉ hard (29) | ≤ 18 lớp (6) | [65, 109, 398] | [12, 30, 164] | [12, 34, 171] |
| | 19–30 lớp (11) | [144, 424, 1150] | [2, 16, 343] | [2, 16, 304] |
| | ≥ 31 lớp (12) | [477, 677, 1750] | [170, 477, **2093**] | [108, 254, 1114] |
| | **Tổng** | **[686, 1210, 3298]** | **[184, 523, 2600]** | **[122, 304, 1589]** |
| Nghỉ soft (33) | ≤ 18 lớp (6) | [65, 109, 398] | [13, 40, 162] | [12, 33, 165] |
| | 19–30 lớp (12) | [151, 455, 1230] | [2, 16, 358] | [2, 16, 356] |
| | ≥ 31 lớp (15) | [554, 1028, 2323] | [170, 821, **2973**] | [116, 777, 2060] |
| | **Tổng** | **[770, 1592, 3951]** | **[185, 877, 3493]** | **[130, 826, 2581]** |

Khác lượt 2: Core không còn đạt P1 = 0 ở mọi trường. Lý do là có ô GV bị chặn và tiết khóa thì không
phải lúc nào cũng tránh được hết vi phạm P1. Với 2 worker, P3 của nhóm từ 31 lớp trở lên kém STKB
(2.093 so với 1.750 khi Nghỉ hard; 2.973 so với 2.323 khi Nghỉ soft). Với 4 worker, P3 tốt hơn STKB.

**Từng rule, kịch bản Nghỉ soft** (33 trường; tổng vi phạm thô; với 4 worker, số trường Core tốt hơn /
bằng / kém):

| Rule (mức) | STKB | Core 2w | Core 4w | 4w: tốt hơn/bằng/kém |
|---|---:|---:|---:|---|
| CLASS_SUBJECT_MAX_PERIODS_PER_DAY (P1) | 107 | 40 | 2 | 12 / 21 / 0 |
| TEACHER_MAX_PERIODS_PER_SESSION (P1) | 663 | 145 | 128 | 26 / 7 / 0 |
| TEACHER_AVOID_SLOTS — Nghỉ/Bận/Hạn chế (P2) | **178** | **238** | **253** | 4 / 5 / 1 |
| SUBJECT_COMPONENT_DAY_SPREAD (P2) | 566 | 426 | 361 | 25 / 3 / 5 |
| TEACHER_MAX_GAP_RUN (P2) | 230 | 146 | 148 | 18 / 10 / 5 |
| TEACHER_MAX_PERIODS_PER_DAY (P2) | 618 | 67 | 64 | 24 / 8 / 1 |
| TEACHER_SINGLE_PERIOD_SESSION (P3) | 906 | 1464 | 1058 | 15 / 1 / 17 |
| TEACHER_TOTAL_GAPS (P3) | 3045 | 2029 | 1523 | 27 / 0 / 6 |

`TEACHER_AVOID_SLOTS` theo trường (STKB → Core 2w / 4w):

- 3050…: 60 → 0 / 0;
- 4334…: 4 → 0 / 0;
- 3454…: 1 → 0 / 0;
- 5797…: 42 → 7 / 17;
- 3114… (59 lớp): **71 → 231 / 236**.

Core tránh ô Nghỉ tốt hơn STKB ở 4 trường. Ở trường 3114, trường mà Nghỉ hard vô nghiệm, Core đổi thêm
khoảng 160 tiết vào ô Nghỉ để lấy P1 tốt hơn (6 so với 58). Theo thang chung, đổi như vậy là đúng; theo
nhà trường thì chưa chắc.

**RAM và thời gian:**

| Kịch bản | Worker | RSS cao nhất | RSS trung vị | Thời gian thực trung vị / cao nhất |
|---|---:|---:|---:|---|
| Nghỉ hard | 2 | 1,2 GB | 0,44 GB | 188 / 205 s |
| Nghỉ hard | 4 | 1,4 GB | 0,57 GB | 187 / 198 s |
| Nghỉ soft | 2 | 1,2 GB | 0,46 GB | 188 / 207 s |
| Nghỉ soft | 4 | 1,5 GB | 0,58 GB | 188 / 197 s |

### 0.5. Trả lời: cùng ràng buộc, Core có còn tốt hơn STKB không?

**Có, theo thang chung của dự án và với 4 worker:**

- Nghỉ hard: Core tốt hơn ở 29/29 trường so được. Core còn xếp hợp lệ 3 trường mà STKB không xếp hợp lệ
  được, và chứng minh trường thứ tư vô nghiệm.
- Nghỉ soft: Core tốt hơn ở 33/33 trường.
- Với 2 worker, Core thua 1 trường (47 lớp) ở cả hai kịch bản, và P3 của nhóm trường lớn kém STKB.

**Phải đọc kèm ba điều kiện:**

1. "Tốt hơn" là theo thứ tự từ điển của thang chung, nặng nhất là P1 (GV ≤ 4 tiết/buổi, môn ≤ 2
   tiết/lớp/ngày). STKB không tối ưu theo thang này, và trường có thể không đặt các rule đó.
2. Khi Nghỉ là soft ở P2, Core có thể xếp vào ô Nghỉ nhiều hơn STKB (trường 3114). Nếu trường coi Nghỉ là
   hard hoặc ưu tiên trên P1, cần cấu hình đúng như vậy cho trường đó.
3. Thuộc tính GV trong phần cuối file (max tiết/buổi, max tiết/ngày, …) chưa đưa vào input. STKB có thể
   đang tối ưu theo các giới hạn riêng của từng trường mà thang chung không biết.

### 0.6. Giới hạn

- n = 1, seed 42; chỉ đo Linux, máy i7-12700H, 20 luồng chạy đầy (§0.3). Không có lượt 8 worker trong lượt 3.
- 33/34 trường; trường R41 bị loại vì phần cuối file có 168 byte chưa rõ nghĩa. 2 trường bị loại
  từ lượt 2 do trùng tên lớp.
- Không biết 14 ô Họp/Nghỉ trùng tiết khóa nghĩa là gì trong STKB. Tooling giữ khóa và để mở ô đó.
- Tiết khóa lấy theo cờ trong file; chưa kiểm STKB dùng cờ này khi xếp lại hay chỉ để hiển thị (báo
  cáo 08).
- Kết quả local: `benchmarks/artifacts/real/stkb-v3-{hard,soft}/<site>/cmp-w{2,4}/`; bố trí trong
  `stkb-v3-hard/layout.jsonl`.

---

## Phần A — Lượt 2: so sánh sau khi chặn ô theo lớp (34 trường, 2/4/8 worker)

### A1. Thay đổi so với lượt 1

- **Tooling mới trong `tools/real_data/`** (không sửa `src/`):
  - `stkb_api.py`: quét và tải file qua API;
  - `stkb_to_csv.py`: chuyển `.STKB` thành `tkb.csv` và `class-cells.csv`;
  - `warm_start.py`: cho Core xuất phát từ lịch có sẵn;
  - `run_batch.py`: chạy nhiều lượt song song, lấp đầy CPU.

  `convert_real.py` có thêm `--class-cells` và ghi `available_slot_ids` cho lớp. `compare_real.py` có
  thêm `--workers`, `--warm-start` và ghi `tier_runs`. Tổng cộng 34 test dùng dữ liệu giả; có kiểm bằng
  cách tạm bỏ bước sắp xếp trong `warm_start.py`: đúng 2 test đỏ, nên test bắt được lỗi thứ tự ở §6.
- **Ô được học của lớp:** mọi ô của các (thứ, buổi) mà lớp có ít nhất một tiết trong lịch STKB, trừ ô
  STKB đánh dấu 254/255. Mỗi lớp còn trung bình **61%** số ô của khung chung (29.106/47.910 ô-lớp). Lịch
  STKB vẫn hợp lệ hard ở 34/34 trường trên bài toán đã thu hẹp.
- **Loại 2 trường so với lượt 1.** Hai trường có tên lớp trùng giữa buổi sáng và buổi chiều nhưng mã lớp
  khác nhau (một trường: 8.5; trường kia: 9A1–9A4). Không xác định được đó là một lớp hay hai lớp, nên
  không gộp và không đoán. Còn lại 34 trường: 26 lịch xếp đủ, 8 lịch còn tối đa 5% tiết chưa xếp.

### A2. Cách bố trí chạy

- 34 trường × {2, 4, 8} worker = 102 lượt. Giới hạn thời gian của solver là 180 s; watchdog là giới
  hạn + 300 s; không chạy lại lượt nào.
- `run_batch.py` xếp job sao cho tổng worker đang chạy không vượt **20 luồng** (`nproc`; máy có 14
  nhân: 6 nhân P có hyperthreading và 8 nhân E). Job 8 worker chạy trước, rồi 4, rồi 2. Trong mỗi mức,
  trường lớn chạy trước.
- Số luồng đang dùng cao nhất là 20, không chạy chồng luồng. Tổng thời gian 70,6 phút; 0 lỗi; 0 lượt bị
  watchdog dừng. Cách bố trí ghi trong `benchmarks/artifacts/real/stkb-v2/layout.jsonl`.
- **Thiên lệch:** mỗi worker có thể chạy trên luồng hyperthread chia nhân hoặc trên nhân E, nên chậm hơn
  một nhân P riêng. Cả 3 mức worker đều chịu điều này. Vì vậy số liệu là cận dưới cho chất lượng của
  từng mức, đặc biệt mức 2 worker.
- Thời gian thực mỗi lượt có trung vị 186–189 s, cao nhất 205 s. Phần vượt 180 s là thời gian khởi động
  tiến trình, nạp input và kiểm độc lập.

### A3. Kết quả

| Worker | Core tốt hơn STKB | P1 chứng minh tối ưu | Tối ưu cả 3 mức | Hard hợp lệ / điểm độc lập khớp |
|---:|---:|---:|---:|---:|
| 2 | 34/34 | 34/34 | 4/34 | 34/34 |
| 4 | 34/34 | 34/34 | 6/34 | 34/34 |
| 8 | 34/34 | 34/34 | 6/34 | 34/34 |

Tổng điểm `[P1, P2, P3]` của 34 trường:

| Nhóm quy mô | STKB | Core 2 worker | Core 4 worker | Core 8 worker |
|---|---|---|---|---|
| ≤ 18 lớp (6 trường) | [65, 109, 398] | [0, 0, 111] | [0, 0, 123] | [0, 0, 112] |
| 19–30 lớp (13 trường) | [162, 470, 1349] | [0, 10, 388] | [0, 10, 357] | [0, 10, 302] |
| ≥ 31 lớp (15 trường) | [554, 854, 2323] | [0, 106, 2199] | [0, 2, 1025] | [0, 2, 778] |
| **Tổng** | **[781, 1433, 4070]** | **[0, 116, 2698]** | **[0, 12, 1505]** | **[0, 12, 1192]** |

Từng rule, tổng vi phạm thô và số trường Core tốt hơn / bằng / kém STKB:

| Rule (mức) | STKB | Core 2w | Core 4w | Core 8w | 2w: tốt hơn/bằng/kém |
|---|---:|---:|---:|---:|---|
| CLASS_SUBJECT_MAX_PERIODS_PER_DAY (P1) | 107 | 0 | 0 | 0 | 13 / 21 / 0 |
| TEACHER_MAX_PERIODS_PER_SESSION (P1) | 674 | 0 | 0 | 0 | 27 / 7 / 0 |
| SUBJECT_COMPONENT_DAY_SPREAD (P2) | 566 | 90 | 0 | 0 | 27 / 5 / 2 |
| TEACHER_MAX_GAP_RUN (P2) | 249 | 14 | 0 | 0 | 24 / 10 / 0 |
| TEACHER_MAX_PERIODS_PER_DAY (P2) | 618 | 12 | 12 | 12 | 25 / 9 / 0 |
| TEACHER_SINGLE_PERIOD_SESSION (P3) | 928 | 1255 | 768 | 580 | 17 / 1 / 16 |
| TEACHER_TOTAL_GAPS (P3) | 3142 | 1443 | 737 | 612 | 31 / 0 / 3 |

- **2 worker đủ cho P1 và gần đủ cho P2.** Ở trường lớn, P3 kém STKB ở 4/34 trường với 2 worker, 1/34
  với 4 worker, 0/34 với 8 worker. Trường 59 lớp lớn nhất có P3 = 480 / 246 / 199 với 2 / 4 / 8 worker,
  trong khi STKB là 268.
- **Thắng theo thứ tự từ điển chủ yếu nhờ P1.** 674/781 vi phạm P1 của STKB là rule "GV ≤ 4 tiết/buổi"
  của thang chung. Trường có thể không đặt rule này, nên "thắng" ở đây chỉ là thắng trên thang của dự
  án.

### A4. Phần còn chưa công bằng: ràng buộc giáo viên và tiết khóa

> Đã xử lý ở Phần 0 (lượt 3). Phần này giữ nguyên để đối chiếu.

Phần cuối file STKB lưu, cho từng ô của từng giáo viên, mã yêu cầu và cờ khóa tiết. Nghĩa đã nối với
binary trong [báo cáo 08](research/stkb/08-suffix-constraints-and-locks.md): 1000–1006 Họp, 998 Nghỉ,
999 Bận, 997 Hạn chế. Bộ đọc nghiên cứu chỉ đọc được phần này ở **12/34** trường; 22 trường còn lại lỗi
căn chỉnh.

Trong 12 trường đọc được:

- 7 trường có mã Họp/Nghỉ/Bận/Hạn chế: 3.556 ô Họp, 1.826 ô Nghỉ và vài ô Bận/Hạn chế.
- 2 trường có 575 tiết khóa; cả 575 tiết đều trùng tiết trong lịch STKB.
- 4 trường không có ràng buộc giáo viên hay tiết khóa nào.

Đếm số tiết xếp vào các ô ràng buộc, ở 8 trường có ràng buộc hoặc tiết khóa:

| Ô giáo viên | Lịch STKB | Core 2 worker | Core 8 worker |
|---|---:|---:|---:|
| Họp (1000–1006) | **0** | 668 | 653 |
| Nghỉ (998) | 135 | 472 | 428 |
| Bận (999) | 1 | 0 | 1 |

- STKB không bao giờ xếp tiết vào giờ họp, nhưng có xếp vào ô Nghỉ (135 tiết). Điều này khớp với báo
  cáo 08: STKB không luôn coi Nghỉ là hard.
- Core không biết các ô này, nên được tự do hơn STKB.
- Core cũng không biết 575 tiết khóa, nên có thể dời chúng sang ô khác.
- Với 22 trường không đọc được phần cuối file, không biết có ràng buộc như vậy hay không.

**Hệ quả:** chỉ 4 trường đọc được phần cuối file mà không có ràng buộc giáo viên hay tiết khóa là phép
so công bằng theo những gì đọc được, và Core thắng ở cả 4 trường đó. Với 30 trường còn lại, kết quả
"Core tốt hơn" có thể một phần đến từ việc Core giải bài toán dễ hơn.

### A5. Trả lời

- **Core có bằng hoặc hơn STKB không?** Theo thang chung và khi ô được học của lớp đã đúng, Core tốt hơn
  ở 34/34 trường với 2–8 worker. Nhưng **chưa đủ để kết luận** Core tốt hơn STKB, vì Core chưa nhận
  ràng buộc giáo viên (Họp/Nghỉ/Bận) và tiết khóa. Bằng chứng công bằng hiện chỉ có 4 trường.
- **Cần tối thiểu bao nhiêu worker?**
  - 2 worker: P1 tối ưu và thắng theo thứ tự từ điển ở mọi trường.
  - 4 worker: cần cho chất lượng P3 ở trường từ 31 lớp trở lên; tổng P3 của nhóm này từ 2.199 giảm còn
    1.025.
  - 8 worker: cải thiện thêm ít (1.025 → 778).
  - 1 worker: không dùng được.
  - **INFERRED:** khác biệt giữa 1 và 2 worker là do nhánh tìm kiếm khác nhau (Phần B §7), không phải
    do lượng CPU.
- **RAM:** RSS đỉnh tăng theo quy mô trường và số worker. Ở nhóm từ 31 lớp trở lên, RSS cao nhất là
  1,2 / 1,5 / 2,3 GB với 2 / 4 / 8 worker. Đây là số đo trên Linux; chưa đo trên Windows nên chưa kết
  luận được máy ở trường cần bao nhiêu RAM.

### A6. Giới hạn

- Mỗi trường chạy n = 1 với seed 42. Chỉ đo trên Linux, máy i7-12700H, chạy song song lấp đầy 20 luồng
  (§A2). Chưa đo Windows hay máy ít nhân.
- Ràng buộc giáo viên, tiết khóa và thuộc tính giáo viên (max tiết/buổi, khung tiết) chưa được đưa vào
  input (§A4). Phần cuối file chỉ đọc được ở 12/34 trường.
- Số tiết và tiết đôi suy ra từ lịch STKB (RD4). Ô được học của lớp cũng suy từ các buổi lớp có tiết
  trong lịch STKB.
- Thang chấm là thang chung của dự án, không phải mục tiêu của STKB hay của trường.
- Kết quả local: `benchmarks/artifacts/real/stkb-v2/<site>/cmp-w{2,4,8}/` và `layout.jsonl`.

---

# Phần B — Lượt 1: chẩn đoán số worker và thời gian (3 trường)

Phần này viết trước lượt 2. Nhận định "chưa công bằng" ở §5 đã được xử lý phía lớp trong Phần A.

## 1. Câu hỏi và dữ liệu

Lượt so sánh trước trên 36 trường (1 worker, 120–180 s): Core xếp hợp lệ 36/36, nhưng kém lịch STKB
theo thứ tự từ điển ở 24/36 trường. Core thắng cả 6/6 trường từ 18 lớp trở xuống, nhưng chỉ thắng 1/16
trường từ 31 lớp trở lên. Câu hỏi lượt này: Core thua là do thiếu thời gian/tài nguyên, hay do cách tìm
lời giải?

Ba trường lấy trong bộ 36 trường, chuyển từ file `.STKB` tải qua API sang input Core bằng
`tools/real_data/convert_real.py`. Dữ liệu chỉ nằm dưới `benchmarks/artifacts/real/` (gitignore).

| Mã | Lớp | GV | Tiết | Lịch STKB `[P1,P2,P3]` |
|---|---:|---:|---:|---|
| R20 | 20 | 50 | 725 | [19, 50, 89] |
| R37 | 37 | 66 | 968 | [34, 44, 149] |
| R59 | 59 | 106 | 1712 | [58, 55, 268] |

Thang chấm là thang chung §5 của
[kế hoạch tiếp nhận dữ liệu thật](superpowers/plans/2026-11-07-real-timetable-intake.md), không phải
quality profile. So sánh theo thứ tự từ điển `[P1, P2, P3]`, rồi theo từng rule.

## 2. Cấu hình

| Cấu hình | Worker | Thời gian | Warm start | Ghi chú |
|---|---:|---:|---|---|
| (a) | 1 | 180 s | không | Như lượt 36 trường |
| (b) | 8 | 600 s | không | |
| (c) | 8 | 600 s | lịch STKB | Lượt đầu lỗi do script của tôi, đã chạy lại thành (c2), xem §6 |
| (d) | 1 | 600 s | không | **Bổ sung, ngoài 3 cấu hình được giao**: tách yếu tố thời gian khỏi số worker |

- Core chạy qua CLI công khai `tkb_core.cli solve`. Kết quả được kiểm hard và chấm lại bằng validator
  và evaluator độc lập. Cả 12 lượt (a), (b), (c2), (d) đều hard hợp lệ, điểm chấm độc lập khớp với điểm Core báo.
- **Warm start (c2):** không sửa `src/`. Một script ngoài repo chạy CLI trong cùng tiến trình, thay kết
  quả của bước tìm lời giải hợp lệ đầu tiên bằng lịch STKB. Sau đó `run_quality` vẫn kiểm hard và chấm
  độc lập lịch đó, xác nhận nó khớp mô hình soft, rồi dùng nó làm hint cho từng mức ưu tiên.
- Máy: i7-12700H, 14 nhân (6P + 8E), 20 luồng, profile `performance`.

### Cách bố trí chạy và tranh CPU

Theo yêu cầu chạy nhanh, các lượt chạy song song:

1. Ba lượt (a) chạy cùng lúc: 3 luồng.
2. Sáu lượt (b) và (c) chạy cùng lúc: 48 luồng trên 20 luồng phần cứng.
3. Ba lượt (c2) và ba lượt (d) chạy cùng lúc, chồng một phần với lượt (b) của R59: tối đa
   32 + 3 luồng.

Hệ quả:

- (b) và (c2) được ít CPU hơn 8 nhân riêng, nên chúng **đánh giá thấp** cấu hình 8 worker. Dù vậy
  (b) vẫn đạt tối ưu, nên kết luận về 8 worker càng chắc.
- Thời gian chạy và RAM chỉ để tham khảo, không phải số đo hiệu năng.

## 3. Quy tắc diễn giải (chốt trước khi có kết quả)

Chốt lúc 2026-11-08, khi mới chỉ có lượt chạy thử trên trường 12 lớp:

- **D1.** (b) tốt hơn hoặc bằng STKB ở ≥ 2/3 trường → nguyên nhân chính là thiếu thời gian/tài nguyên.
- **D2.** (b) vẫn kém STKB ở ≥ 2/3 trường, nhưng (c) tốt hơn STKB ở ≥ 2/3 trường → mô hình đúng, điểm
  nghẽn là tìm lời giải từ đầu → ưu tiên cải tiến cách tìm (LNS/S1).
- **D3.** (c) không cải thiện được STKB ở ≥ 2/3 trường → Core yếu cả khi tìm cục bộ, hoặc lịch STKB
  đã gần tối ưu trên thang này.
- **Phụ.** Nếu (b) cải thiện P1 dưới 25% so với (a) ở ≥ 2/3 trường thì tài nguyên là yếu tố phụ.

(d) được thêm sau khi chốt các quy tắc trên. Nó không đổi quy tắc, chỉ dùng để tách hai yếu tố trong D1.

## 4. Kết quả

### 4.1 Vector điểm

| Trường | STKB | (a) 1w 180 s | (d) 1w 600 s | (b) 8w 600 s | (c2) 8w 600 s + STKB |
|---|---|---|---|---|---|
| R20 | [19, 50, 89] | [57, 130, 150] | [54, 127, 152] | **[0, 0, 0]** OPT, 119 s | [0, 0, 1], 609 s |
| R37 | [34, 44, 149] | [68, 318, 370] | [67, 315, 370] | **[0, 0, 3]** OPT, 79 s | [0, 0, 3] OPT, 109 s |
| R59 | [58, 55, 268] | [108, 563, 647] | [108, 563, 647] | **[0, 0, 5]** OPT, 193 s | [0, 0, 5] OPT, 221 s |

OPT = Core chứng minh tối ưu cho cả 3 mức (`optimal_prefix = [1, 2, 3]`).

### 4.2 Từng mức ưu tiên (`tier_runs`)

| Trường | Cấu hình | P1 | P2 | P3 |
|---|---|---|---|---|
| R20 | (a) | FEASIBLE 57, cận dưới 0, hết 103 s | NOT_RUN | NOT_RUN |
| R20 | (d) | FEASIBLE 54, cận dưới 0, hết 471 s | NOT_RUN | NOT_RUN |
| R20 | (b) | OPTIMAL 0 sau 4,4 s | OPTIMAL 0 sau 5,7 s | OPTIMAL 0 sau 104 s |
| R37 | (a) | FEASIBLE 68, hết 152 s | NOT_RUN | NOT_RUN |
| R37 | (d) | FEASIBLE 67, hết 586 s | NOT_RUN | NOT_RUN |
| R37 | (b) | OPTIMAL 0 sau 11,8 s | OPTIMAL 0 sau 27,4 s | OPTIMAL 3 sau 26,8 s |
| R59 | (a) | UNKNOWN (không cải thiện), hết 174 s | NOT_RUN | NOT_RUN |
| R59 | (d) | UNKNOWN (không cải thiện), hết 588 s | NOT_RUN | NOT_RUN |
| R59 | (b) | OPTIMAL 0 sau 34,5 s | OPTIMAL 0 sau 59,8 s | OPTIMAL 5 sau 71,3 s |

Với 1 worker, Core dùng hết ngân sách cho P1 mà không chứng minh được gì, và **không bao giờ chạy tới
P2, P3**. Điểm P2, P3 của (a) và (d) chỉ là điểm của lời giải hợp lệ đầu tiên, chưa hề được tối ưu.
Điều này giải thích vì sao lượt 36 trường thua nặng nhất ở P2, P3.

### 4.3 Từng rule (tổng vi phạm thô)

| Rule | Trường | STKB | (a) | (d) | (b) | (c2) |
|---|---|---:|---:|---:|---:|---:|
| CLASS_SUBJECT_MAX_PERIODS_PER_DAY (P1) | R20 / R37 / R59 | 0 / 0 / 0 | 32 / 49 / 79 | 30 / 48 / 79 | 0 / 0 / 0 | 0 / 0 / 0 |
| TEACHER_MAX_PERIODS_PER_SESSION (P1) | R20 / R37 / R59 | 19 / 34 / 58 | 25 / 19 / 29 | 24 / 19 / 29 | 0 / 0 / 0 | 0 / 0 / 0 |
| SUBJECT_COMPONENT_DAY_SPREAD (P2) | R20 / R37 / R59 | 2 / 3 / 5 | 26 / 167 / 308 | 25 / 164 / 308 | 0 / 0 / 0 | 0 / 0 / 0 |
| TEACHER_MAX_GAP_RUN (P2) | R20 / R37 / R59 | 8 / 17 / 38 | 13 / 59 / 103 | 13 / 59 / 103 | 0 / 0 / 0 | 0 / 0 / 0 |
| TEACHER_MAX_PERIODS_PER_DAY (P2) | R20 / R37 / R59 | 40 / 24 / 12 | 91 / 92 / 152 | 89 / 92 / 152 | 0 / 0 / 0 | 0 / 0 / 0 |
| TEACHER_SINGLE_PERIOD_SESSION (P3) | R20 / R37 / R59 | 7 / 38 / 77 | 96 / 187 / 329 | 96 / 186 / 329 | 0 / 3 / 5 | 0 / 3 / 5 |
| TEACHER_TOTAL_GAPS (P3) | R20 / R37 / R59 | 82 / 111 / 191 | 54 / 183 / 318 | 56 / 184 / 318 | 0 / 0 / 0 | 1 / 0 / 0 |

Tổng từng rule khớp với vector ở §4.1 (ví dụ STKB R20: P1 = 0 + 19, P2 = 2 + 8 + 40, P3 = 7 + 82).

RSS cao nhất: 1 worker 0,3–1,0 GB; 8 worker 1,0 GB (R20), 2,0 GB (R37), 3,4 GB (R59).

## 5. Phát hiện về tính công bằng của phép so sánh với STKB

Khung tiết do `convert_real.py` dựng cho mọi lớp gồm mọi thứ × hai buổi × mọi tiết, không chặn ô nào
theo lớp. Bộ chuyển `.STKB` → CSV cũng bỏ qua các ô STKB đánh dấu 254/255 (R20: 656 ô, R37: 251 ô,
R59: 353 ô), thay vì chặn chúng. Nghĩa của 254/255 còn UNKNOWN; có thể là ô không học, chào cờ/sinh
hoạt hoặc ô khóa.

Lịch Core (b) dùng những buổi mà lớp thật không học:

| Trường | Buổi-lớp Core dùng mà lớp thật không học | Ô bắt đầu của Core nằm ngoài ô lớp thật dùng |
|---|---:|---:|
| R20 | 20 / 200 | 143 |
| R37 | 206 / 408 (50%) | 519 |
| R59 | 342 / 680 (50%) | 882 |

Như vậy Core được giải một bài toán **rộng hơn** bài toán STKB phải giải: ví dụ dồn tiết sang buổi chiều
cho lớp chỉ học buổi sáng. Ngoài ra lịch STKB còn tuân theo ràng buộc GV và tiết khóa trong phần cuối
file mà bộ đọc chưa đọc được. Hệ quả:

- **So giữa các cấu hình Core (a/b/c2/d) vẫn hợp lệ**, vì cùng một input.
- **Không được** đọc kết quả [0, 0, 0] so với [19, 50, 89] là "Core tốt hơn STKB".
- Kết luận của lượt 36 trường ("Core 1 worker thua STKB") vẫn đứng, và còn chắc hơn: Core thua dù được
  lợi khung rộng hơn.

Core đã hỗ trợ chặn ô theo lớp (`ClassGroup.available_slot_ids`). Sửa hoàn toàn trong tooling
(`tools/real_data/`), không cần đổi `src/`.

## 6. Sự cố khi chạy

Lượt (c) đầu tiên lỗi `MODEL_INVALID / INTERNAL_SCORE_MISMATCH` ở cả 3 trường, sau 1–7 giây.

- **Nguyên nhân:** script warm start của tôi nạp lịch STKB theo thứ tự trong file. `run_quality` so danh
  sách xếp tiết theo đúng thứ tự từng phần tử, còn mô hình trả về theo thứ tự tiết của Core.
- **Vì sao lượt chạy thử không phát hiện:** trên trường 12 lớp, hai thứ tự tình cờ trùng nhau.
- **Cách sửa:** sắp lịch theo thứ tự tiết của Core, rồi chạy lại thành (c2).
- Kết quả lỗi cũ giữ nguyên trong `diag/<trường>/c/`. Core báo lỗi đúng như thiết kế; đây không phải
  lỗi của Core.

## 7. Diễn giải

- **Theo quy tắc chốt trước:** (b) tốt hơn STKB ở 3/3 trường, nên rơi vào **D1**. Mức cải thiện P1 từ
  (a) sang (b) là 100% ở cả 3 trường, nên quy tắc phụ không áp dụng.
- **Tách yếu tố bằng (d):** D1 không phân biệt thời gian với số worker, nên cần (d).
  - (d) có thời gian gấp 3,3 lần (a) mà gần như không đổi: R59 giống hệt, R20/R37 chỉ giảm 1–3 điểm
    P1. **Vậy không phải thiếu thời gian.**
  - 8 worker chứng minh P1 = 0 trong 4–35 giây thực, tức chưa tới khoảng 280 giây-CPU. Trong khi đó
    1 worker chạy 600 giây-CPU vẫn không xuống được.
  - **INFERRED:** khác biệt nằm ở **cách tìm**, không phải ở lượng CPU. Với 1 worker, Core dùng nhánh
    riêng (`_solve_tier`: thử nhanh ép mọi mức về 0, rồi tìm xen kẽ LNS trên một luồng). Với từ 2
    worker trở lên, Core dùng bộ chiến lược song song mặc định của CP-SAT. Chưa đo cấu hình 2 hoặc 4
    worker nên chưa khẳng định được ngưỡng.
- **Warm start không cần:** (c2) bằng (b) ở R37 và R59. Ở R20, (c2) kém hơn một chút (P3 = 1, chưa
  chứng minh tối ưu trong 600 s khi đang tranh CPU). Xuất phát từ lịch STKB không giúp gì khi tìm từ
  đầu đã đạt tối ưu.

**Trả lời câu hỏi:** ưu tiên **cấu hình tìm kiếm**, cụ thể là chạy nhiều worker, trước khi làm LNS/S1.
Không ưu tiên tăng thời gian. Việc LNS/S1 chỉ đáng xét lại nếu, sau khi sửa khung tiết (§5), Core nhiều
worker vẫn không đạt bằng STKB.

## 8. Giới hạn

- n = 1, chỉ 3 trường, seed 42. Có tranh CPU khi chạy song song (§2).
- Bài toán Core rộng hơn bài toán thật (§5), nên mọi số so với STKB chỉ có giá trị tham khảo.
- Số tiết đôi suy ra từ chính lịch STKB (RD4).
- Chưa đo trên Windows, chưa đo trên máy ít nhân. Một máy 4 nhân ở trường có thể không đạt kết quả
  như 8 worker; RSS 3,4 GB ở R59 là rủi ro cho máy yếu.
- Script quét API, tải file, chuyển `.STKB` → CSV, warm start và chạy chẩn đoán đang nằm ngoài repo
  (thư mục tạm của phiên), chưa được review hay test.

## 9. Lệnh và đường dẫn

- Kết quả: `benchmarks/artifacts/real/diag/<site>/{a,b,c,c2,d}/` (`comparison.json`, `core-result.json`),
  log chạy: `benchmarks/artifacts/real/diag/run.log`. Ánh xạ R20/R37/R59 sang mã trường chỉ có trong
  thư mục local đó.
- Mỗi lượt: `diag.py <conv> <out> <workers> <seconds> <warm>`, gọi `compare_real.compare` với hàm
  `run_core` thay số worker; warm start qua `warm_cli.py`. Watchdog `timeout` = giới hạn + 300 s.
  Không chạy lại lượt nào, trừ (c) → (c2) sau khi sửa lỗi script ở §6.
