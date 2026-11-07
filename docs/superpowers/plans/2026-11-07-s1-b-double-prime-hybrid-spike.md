# Spike S1-b″ — interleave có trần rồi LNS (A5)

Ngày 2026-11-07. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-07 (H1–H8 theo đề xuất).** **Spike
dừng theo quyết định người dùng ngày 2026-11-07, sau 26/252 run (đều thuộc phần s101 chỉ để báo cáo, exit
0); không kết luận.** Phần gate s102/s103 chưa chạy. Người dùng ưu tiên đối chiếu với thời khóa biểu thật
từ DB công ty, vì kiểm kỹ trên synthetic là quá mức so với nhu cầu hiện tại. Run `c40-base-s101-hard` B bị
ngắt giữa chừng. Worktree `.worktrees/s1-hybrid`, code A5 (patch SHA256 `5d9ba8c5…`) và evidence được giữ
nguyên; runner bỏ qua run đã xong nên có thể chạy tiếp nếu có lệnh mới. Base `6f9e5bb` trên `main`.

**Quyết định của người dùng ngày 2026-11-07:** mở spike mới ngoài L8, sau khi
[spike S1-b′](../../s1-b-prime-spike-report.md) không đạt. Spike phải giữ search toàn model, có baseline
cùng phiên và điều kiện chốt trước, đo trên s101 và thêm s102/s103, không đổi budget hay profile.

Đây vẫn là **spike chẩn đoán** của [kế hoạch S1](2026-11-07-search-quality-s1.md), không phải S1-b. Kết
quả chỉ để quyết định có lập S1-b cho A5 hay không. Tài liệu chỉ là kế hoạch: không sửa code, không chạy
solver. Duyệt kế hoạch **không** phải cho phép làm spike.

## 1. Vì sao A5

Số đo của S1-b′ (s101, n = 3, cùng phiên) cho thấy hai cách search bổ sung cho nhau:

| Nhóm dataset | Interleave toàn model (B) | LNS thay interleave (L) |
|---|---|---|
| BASE/MIXED (12) | Đạt 5/12. Ở 7 dataset B không đạt, stage P1 dùng 45–176 s mà không chứng minh được gì | Đạt 12/12. P1 = 0 sau 28–93 s LNS ở 40 lớp |
| TIGHT (6) | Đạt 3/6. Interleave **chứng minh** P1 = 0 trong 4,6 dt (`c10-tight-s101-soft`), 12,8 dt (`c10-tight-s101-hard`, 13,5 s) và 27,1 dt (`c20-tight-s101-soft`, 32 s) | Đạt 0/6. Kẹt ở cực tiểu cục bộ, vì mọi bài con trả cùng một vector |

Ở cả ba dataset TIGHT mà B đạt, slice ép mọi tầng bằng 0 trả INFEASIBLE ngay, rồi interleave của P1 trả
OPTIMAL với giá trị 0 (theo `native-calls.jsonl`). Nếu lấy kết quả tốt hơn của B hoặc L cho từng dataset,
15/18 dataset đạt. Đây là **giới hạn trên kiểu oracle**, không phải thuật toán.

**Giả thuyết:** cho interleave một khoản deterministic time cố định trước, rồi chuyển sang LNS nếu chưa
chứng minh xong tier. Cách này giữ được các chứng minh nhanh ở TIGHT, đồng thời vẫn còn đủ budget để LNS
giảm P1 ở BASE/MIXED.

**Cảnh báo về độ tin cậy:** giả thuyết và trần dưới đây được rút ra **sau khi** xem dữ liệu s101. Vì vậy
gate chỉ chấm trên s102/s103, là các seed chưa dùng để thiết kế (H3). s101 chỉ được báo cáo.

## 2. Thiết kế A5 (chỉ trong spike, sau cờ)

Cờ `TKB_S1_SPIKE=A5`, tắt mặc định. A5 kèm A2 (hint đầy đủ) và dùng lại nguyên máy LNS của A4 (S1-b′).
Cờ tắt thì mọi lời gọi giữ đúng như `main`, như S1-a và S1-b′ đã làm.

**Vị trí:** pha sau probe của mỗi tier chưa chứng minh trong `_solve_tier`, gồm cả đường `sticky`. Đây
cũng là chỗ A4 đã thay interleave. Feasibility, verification và probe (slice) giữ nguyên như `main`.

**Mỗi tier p chưa chứng minh:**

1. **Interleave có trần.** Chạy `interleave` trên model gốc như `main`, với cùng hint và cùng giới hạn
   wall time còn lại. Thêm `max_deterministic_time = 30` (H2).
2. Nếu interleave trả **OPTIMAL**, tier xong, giống B.
3. Nếu chưa OPTIMAL, gồm FEASIBLE, UNKNOWN hoặc hết trần, thì chạy **LNS** với phần budget còn lại của
   tier. Incumbent bắt đầu là lời giải tốt nhất theo thứ tự từ điển trong số: kết quả interleave, kết quả
   probe và incumbent đang giữ. Mọi incumbent đều đã qua kiểm.
4. LNS giữ nguyên S1-b′:
   - neighbourhood GV (≤ 3), lớp (≤ 2) và ngày; một nửa chọn theo vi phạm;
   - khoảng 8 % số occurrence; mỗi bài con 1 dt;
   - nhận theo thứ tự từ điển; mọi lời giải được nhận đều qua hard checker và evaluator;
   - OPTIMAL chỉ khi giá trị bằng 0;
   - xử lý trường hợp hết thời gian trước khi giải (bản sửa lỗi `MODEL_INVALID` của S1-b′).

   **Không dò lại tham số LNS.**
5. Kết quả của tier là lời giải tốt nhất theo thứ tự từ điển của bước 1 và bước 3. Wall time là tổng hai
   bước.

**Không đổi:** contract, ScoreReport, policy, budget, worker, seed, guard; không dùng witness.

**Phương án đã cân nhắc nhưng không chọn:** chuyển sang LNS khi interleave "không giảm P1". Muốn phát
hiện điều này phải cắt interleave thành nhiều đoạn (mất trạng thái search giữa các đoạn) hoặc dừng bằng
timer theo wall time. Cả hai đều làm thay đổi chính cái interleave đang giúp TIGHT, và tăng phụ thuộc vào
tốc độ máy. Trần deterministic time đơn giản hơn và tái lập được.

## 3. Phương pháp đo

| Mục | Giá trị |
|---|---|
| Biến thể | **B** = cờ tắt (baseline cùng phiên), **H** = A5 |
| Gate | 36 dataset known-feasible s102 và s103 (bỏ UNSAT_CAPACITY), từ bundle v2 đã dùng cho S1-b′ |
| Lặp | n = 3 cho mỗi biến thể; seed solver 42 như v2 |
| Báo cáo thêm, không làm gate | 18 dataset s101 × {B, H} × 1. Chạy **trước** phần gate, đóng vai trò chạy thử mở rộng |
| Thứ tự | Xen kẽ theo cặp trên từng dataset và lần lặp (B H / H B / B H) |
| Số run | 36 (s101) + 2 × 36 × 3 = 216 (gate) = **252 run**. Budget trung bình khoảng 120 s, nên khoảng 8,5 h liền (s101 khoảng 1,2 h, gate khoảng 7,2 h) |
| Máy | Máy Linux của người dùng, cắm sạc, `systemd-inhibit`, hồ sơ `performance` cố định (H6), không chạy việc nặng song song |
| Lệnh | Như S1-b′: `native_trace.py` + `solve`, cùng budget và guard với v2; mỗi lịch chạy lại `validate-schedule` và `evaluate-score` |
| Ghi thêm cho H | Kết quả và dt của interleave có trần; số vòng LNS, số vòng được nhận, thời điểm P1 giảm; hồ sơ điện năng mỗi 5 phút |

## 4. Điều kiện đánh giá (chốt trước khi đo)

Một dataset **đạt** với một biến thể khi lịch đạt M1–M3 của profile v0 (P1 = 0) ở **ít nhất 2/3** lần
lặp. Chỉ 36 dataset s102/s103 được dùng cho gate.

H được đề xuất lập kế hoạch S1-b khi thỏa **cả bốn** điều kiện:

1. **An toàn:**
   - 108/108 lịch H của phần gate và 18/18 lịch H của s101 hard-valid, có `evaluate-score` OK;
   - không `MODEL_INVALID`, không diagnostic `INTERNAL_*`;
   - không run H nào mất lịch khi run B cùng cặp có lịch.
2. **Cải thiện chính:** số dataset đạt của H ≥ số dataset đạt của B **+ 6**, tức cùng tỉ lệ +3/18 của
   S1-b′.
3. **Không hồi quy:** không dataset nào B đạt 3/3 mà H đạt ≤ 1/3.
4. **Tài nguyên:** peak RSS của mọi run H dưới target 1/2/4 GiB; thời gian feasibility không đổi.

Ghi nhận, không dùng làm gate:

- kết quả s101, đặt cạnh B và L của S1-b′ để tham khảo; không so số tuyệt đối vì khác phiên;
- tách theo BASE, MIXED và TIGHT;
- P1 trung vị theo cặp khi cả hai biến thể chưa đạt;
- P2/P3 khi P1 bằng nhau;
- tỉ lệ tier mà interleave có trần chứng minh được, và dt nó đã dùng;
- thời điểm chạm P1 = 0;
- dao động giữa các lần lặp của B và H.

## 5. Cây quyết định (chốt trước, chép vào báo cáo trước khi chấm)

| Tình huống | Xử lý |
|---|---|
| Thiếu run, `exit` khác 0, hoặc patch/test lúc chấm khác bản lúc chạy | **Không kết luận.** Chạy bù chỉ những run thiếu, và chỉ khi có lệnh cho phép riêng |
| (1) trượt, kể cả chỉ ở s101 | **Loại A5 ở dạng này.** Nếu s101 (chạy trước) đã trượt an toàn thì dừng, không chạy phần gate |
| (3) trượt | Loại A5 ở dạng này; nêu dataset hồi quy |
| (4) trượt | Loại A5 ở dạng này; nêu run vượt |
| (2) trượt, các điều kiện khác đạt | Không đạt → mục H8 |
| Cả bốn đạt | Đề xuất soạn kế hoạch S1-b cho A5 (tính tất định, metadata, viết lại test, campaign S1-c theo protocol có chấm Q) |

Quy tắc cố định:

- Không nới ngưỡng sau khi thấy số liệu (+5 vẫn là không đạt).
- Không dò lại trần 30 dt hay tham số LNS trên chính các dataset gate.
- Không đổi kết luận dựa trên các mục ghi nhận.
- **Hồ sơ điện năng:** nếu hồ sơ khác `performance` ở bất kỳ run nào, chấm lại sau khi bỏ các cặp bị
  ảnh hưởng. Nếu kết luận đổi, ghi "không kết luận được do hồ sơ điện năng".

## 6. Việc trước khi chạy (thuộc phần được ủy quyền khi duyệt spike)

- Worktree mới `.worktrees/s1-hybrid` từ `main`, nhánh local `spike/s1-b-double-prime`, không merge. Áp
  patch S1-b′ (SHA256 `3f5f56dc2d2b5d001d4bc8cebe53bce55a1fa007b13d7b33bfbee7f2eff9ad7f`) để có A2 và A4.
  Giữ nguyên `.worktrees/s1-lns`.
- TDD cho A5:
  - interleave chạy trước với `max_deterministic_time = 30` và cùng giới hạn wall time;
  - interleave OPTIMAL thì không chạy LNS;
  - chưa OPTIMAL thì LNS bắt đầu từ incumbent tốt nhất theo thứ tự từ điển;
  - đường `sticky` cũng theo A5;
  - kết quả tier là lời giải tốt nhất của hai bước;
  - cờ tắt thì đường gọi không đổi; cờ A4 giữ nguyên hành vi S1-b′;
  - A5 tự kèm A2.
- Chạy toàn bộ test với cờ tắt: phải đạt như `main`. Chạy với `A5`: oracle vét cạn phải giữ optimum, và
  mọi kết quả OPTIMAL phải khớp oracle. Test cố định đường gọi cũ được phép lỗi nếu lý do đã ghi rõ.
- Chạy thử một dataset với budget nhỏ, ngoài thư mục kết quả.
- Soạn khung báo cáo có §5 (cây quyết định) trước khi chấm, như S1-b′.

## 7. Ranh giới

- Không commit code spike lên `main`, không merge, không push nhánh spike.
- Không đổi gate, budget, worker, seed, policy hay profile; không dùng witness hint.
- Evidence ghi vào `.worktrees/s1-hybrid/benchmarks/artifacts/s1-hybrid/`, không commit.
- Báo cáo spike là file docs riêng, chỉ commit khi được duyệt.

## 8. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Trần 30 dt rút ra từ s101 nên khớp quá mức | Gate chỉ dùng s102/s103; trần là số tròn, không dò |
| 30 dt interleave lấy mất budget của LNS ở 40 lớp. Ví dụ ở `c40-base-s101-soft`: feasibility 4 s + slice 17 s + khoảng 30 s interleave + khoảng 91 s LNS ≈ 142 s trên 180 s | Ghi nhận thời điểm chạm P1 = 0; nếu BASE/MIXED 40 lớp trượt vì hết thời gian, báo cáo nêu rõ |
| TIGHT 40 lớp: riêng feasibility đã tốn 80–150 s, nên cả B và H đều khó | Không kỳ vọng cải thiện ở nhóm này; điều kiện (3) vẫn bảo vệ |
| Vẫn không tất định, vì LNS dừng theo wall time | n = 3, điều kiện theo đa số 2/3 |
| Chạy khoảng 8,5 h liền, nên máy dễ bị gián đoạn | `systemd-inhibit`, log hồ sơ điện năng; runner ghi từng run, có thể chạy bù run thiếu (cần lệnh riêng) |

## 9. Quyết định cần duyệt

- [x] **H1 — Hướng:** A5 = interleave có trần deterministic time, rồi LNS nếu chưa chứng minh; áp cho
  mọi tier chưa chứng minh, cả đường sticky; luôn kèm A2. *(Đề xuất: chọn. Không chọn cách phát hiện
  "không giảm P1", lý do ở §2.)*
- [x] **H2 — Tham số:** trần interleave 30 dt. Số tròn trên mức tối đa đã thấy ở s101 (27,1 dt). LNS giữ
  nguyên S1-b′ (8 %, 1 dt). Không dò. *(Đề xuất: chọn.)*
- [x] **H3 — Dữ liệu:** gate trên 36 dataset s102/s103, n = 3; s101 n = 1 chỉ báo cáo và chạy trước.
  Phương án nhỏ hơn: gate n = 2 với "đạt = 2/2" (khoảng 6 h). *(Đề xuất: n = 3.)*
- [x] **H4 — Điều kiện §4:** đạt = ít nhất 2/3; cải thiện ≥ +6 trên 36; không hồi quy 3/3 → ≤ 1/3; an toàn
  và tài nguyên như S1-b′. *(Đề xuất: chọn.)*
- [x] **H5 — Cây quyết định §5,** chép vào khung báo cáo trước khi chấm. *(Đề xuất: chọn.)*
- [x] **H6 — Máy và hồ sơ điện năng:** `performance` cố định, kiểm trước khi chạy, ghi mỗi 5 phút; quy
  tắc độ nhạy như §5. *(Đề xuất: chọn.)*
- [x] **H7 — Worktree:** `.worktrees/s1-hybrid` mới từ `main`, áp patch S1-b′; giữ nguyên
  `.worktrees/s1-lns`. *(Đề xuất: chọn.)*
- [x] **H8 — Nếu không đạt:** dừng hướng S1 về search. Câu kết luận được viết **từ dữ liệu sau khi
  chấm** và được duyệt cùng báo cáo, không soạn sẵn. Đây là bài học từ L8, khi câu soạn sẵn sai với kết
  quả. Lựa chọn tiếp theo (budget, worker, profile) là quyết định sản phẩm riêng. *(Đề xuất: chọn.)*

## 10. Kiểm tra khi soạn

- Số liệu §1 đọc lại từ evidence S1-b′ (`.worktrees/s1-lns/benchmarks/artifacts/s1-lns/runs/`):
  - `result.json` (`tier_runs`) của B và L ở r2;
  - `native-calls.jsonl` của `c10-tight-s101-soft`, `c10-tight-s101-hard` và `c20-tight-s101-soft` (B r2), và
    `c40-base-s101-soft` L r2.
- Vị trí thay đổi đối chiếu với `_solve_tier` trong patch S1-b′
  (`.worktrees/s1-lns/src/tkb_core/solver/objectives.py`).
- Bundle v2 (`.worktrees/phase3c-run-02/benchmarks/artifacts/phase3c/bundle`) có 36 dataset s102/s103
  không thuộc UNSAT_CAPACITY.
- Ước lượng thời gian: mỗi lần lặp 36 cặp × trung bình 2 × 120 s ≈ 2,4 h.
- Không chạy test hay solver; không sửa file nào khác.
