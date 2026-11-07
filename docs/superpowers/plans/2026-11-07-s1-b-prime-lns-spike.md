# Spike S1-b′ — LNS theo cấu trúc bài toán (A4)

Ngày 2026-11-07. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-07 (L1–L8 theo đề xuất); chưa làm
spike.** Làm spike cần lệnh cho phép riêng. Base `2ff4834` trên `main`.

Tiếp nối [kế hoạch S1](2026-11-07-search-quality-s1.md) sau khi
[spike S1-a](../../s1-a-spike-report.md) không đạt điều kiện. Dù mang tên S1-b′, đây vẫn là **spike chẩn
đoán**, không phải bước S1-b (triển khai vào Core) của kế hoạch S1. Kết quả spike chỉ để quyết định có
lập S1-b cho A4 hay không.

Tài liệu chỉ là kế hoạch: không sửa code, không chạy solver. Duyệt kế hoạch **không** phải cho phép làm
spike.

## 1. Vì sao A4

- **F2 (kế hoạch S1):** ở 20/40 lớp, stage P1 dùng gần hết budget mà P1 hầu như không giảm (trung vị
  63 → 61 ở SOFT 40 lớp).
- **S1-a:** ép P1 = 0 trên toàn bài, kể cả chỉ riêng P1 (A1), vẫn quá khó trong 12 dt. A2 giữ được
  incumbent ở 40 lớp BASE nhưng không cải thiện nó.
- **P1 vi phạm có tính cục bộ.** Trên 90 lịch v2 có P1 > 0:

  | Biến thể / lớp | S01 tránh ô (theo GV) | S02 tải/buổi (theo GV) | S06 môn/lớp/ngày (theo lớp) |
  |---|---:|---:|---:|
  | SOFT 20 | 80 | 299 | 136 |
  | SOFT 40 | 555 | 987 | 219 |
  | HARD 10/20/40 | 31 / 150 / 465 | — (hard) | — (hard) |

  Ở 40 lớp, mỗi lịch có 7–49/60 GV có dòng P1 > 0. Sửa một vi phạm thường chỉ cần dời vài tiết của một GV
  và các lớp người đó dạy. Đó là một bài con nhỏ, trong khi search hiện tại phải xử lý cả model 90 000
  biến.

**Giả thuyết:** với cùng budget, vòng LNS giải lặp các bài con nhỏ quanh vi phạm (giữ nguyên phần còn
lại của incumbent) giảm P1 nhanh hơn `interleave_search` trên toàn model. Spike đo giả thuyết này.
CP-SAT đã có LNS nội bộ trong interleave; nếu nó đã đủ tốt thì spike sẽ cho kết quả "không khác", và đó
cũng là một kết quả.

## 2. Thiết kế A4 (chỉ trong spike, sau cờ)

Cờ `TKB_S1_SPIKE=A4`, tắt mặc định. A4 luôn kèm A2 (hint đầy đủ) cho bài con. Cờ tắt thì mọi lời gọi giữ
đúng như code hiện tại, như cách S1-a đã làm.

**Vị trí:** thay pha `interleave` của mỗi tier chưa được chứng minh trong `_solve_tier`
(`src/tkb_core/solver/objectives.py`). Feasibility, verification và probe giữ nguyên như `main`.

**Vòng LNS cho tier p** (incumbent ban đầu = incumbent đã kiểm hiện có):

1. Chọn một neighborhood, xác định theo seed (`random.Random(seed, p, vòng)`):
   - **GV:** mọi occurrence của 1–3 GV;
   - **lớp:** mọi occurrence của 1–2 lớp;
   - **ngày:** mọi occurrence trong một ngày của một nhóm lớp.

   Một nửa số vòng chọn theo vi phạm, tức GV hoặc lớp có dòng phạt dương ở tier p (lấy từ evaluator độc
   lập); nửa còn lại chọn ngẫu nhiên. Kích thước mục tiêu khoảng 8 % số occurrence (giá trị chốt ở L3).
2. Trên một clone của model, cố định mọi biến placement ngoài neighborhood theo incumbent, rồi tối thiểu
   tier p. Các tier đã chứng minh được giữ bằng equality như hiện nay. Giới hạn bài con bằng deterministic
   time (L3), không bằng wall time, để giảm phụ thuộc vào thời điểm cắt.
3. Chỉ nhận lời giải khi vector `[P1,P2,P3]` tốt hơn theo thứ tự từ điển. Mỗi lời giải được nhận phải qua
   hard checker và evaluator độc lập, như mọi candidate hiện nay.
4. Dừng khi hết budget của tier. Tier chỉ được đánh dấu OPTIMAL khi giá trị bằng 0 (penalty không âm);
   ngoài ra là FEASIBLE. LNS không bao giờ claim chứng minh tối ưu khác 0.

**Không đổi:** contract, ScoreReport, policy, budget, worker, seed, guard; không dùng witness.

## 3. Phương pháp đo

| Mục | Giá trị |
|---|---|
| Biến thể | **B** = cờ tắt (baseline cùng phiên), **L** = A4 (+A2) |
| Dataset | 18 dataset s101 (như S1-a) |
| Lặp | n = 3 cho mỗi biến thể; cùng seed 42 như v2, nên lặp đo dao động theo thời gian |
| Thứ tự | Theo cặp, xen kẽ B và L trên từng dataset và lần lặp (B L / L B / B L), để chia đều dao động của máy |
| Số run | 2 × 18 × 3 = 108 run; tổng budget khoảng 3,6 h, cộng overhead khoảng 4 h liền |
| Máy | Máy Linux của người dùng, cắm sạc, `systemd-inhibit`, không chạy việc nặng |
| Lệnh | Như S1-a: `native_trace.py` + `solve`, cùng budget và guard với v2; mỗi lịch chạy lại `validate-schedule` và `evaluate-score` |
| Ghi thêm cho L | Số vòng LNS, số vòng được nhận, loại neighborhood và thời điểm từng lần P1 giảm |

## 4. Điều kiện đánh giá (chốt trước khi đo)

Một dataset **đạt** với một biến thể khi lịch đạt M1–M3 của profile v0 (P1 = 0) ở **ít nhất 2/3** lần lặp.

L được đề xuất lập kế hoạch S1-b khi thỏa **cả bốn** điều kiện:

1. **An toàn:** 54/54 lịch của L hard-valid và có `evaluate-score` OK. Không có `MODEL_INVALID` hay
   diagnostic `INTERNAL_*`. Không run nào của L mất lịch khi run B cùng cặp có lịch.
2. **Cải thiện chính:** số dataset đạt của L ≥ số dataset đạt của B **+ 3**.
3. **Không hồi quy:** không dataset nào B đạt 3/3 mà L đạt ≤ 1/3.
4. **Tài nguyên:** peak RSS của mọi run L dưới target 1/2/4 GiB; thời gian feasibility không đổi (stage
   này không bị sửa).

Ghi nhận, không dùng làm gate:
- P1 trung vị theo cặp trên các dataset mà cả hai biến thể chưa đạt;
- P2/P3 khi P1 bằng nhau;
- thời điểm chạm P1 = 0;
- dao động giữa ba lần lặp của B, để so với v2 r1–r3.

Nếu (1) đến (4) không cùng đạt, A4 ở dạng này bị loại, và báo cáo nêu điều kiện nào trượt.

## 5. Việc trước khi chạy (thuộc phần được ủy quyền khi duyệt spike)

- Worktree mới `.worktrees/s1-lns` từ `main`, nhánh local `spike/s1-b-prime`, không merge. Mang theo A2
  từ patch S1-a (`4eba00e0…`).
- TDD cho phần LNS:
  - chọn neighborhood xác định theo seed;
  - nhận lời giải chỉ khi tốt hơn theo thứ tự từ điển;
  - không claim OPTIMAL khi giá trị khác 0;
  - mọi lời giải được nhận đều qua hard checker và evaluator;
  - cờ tắt thì đường gọi không đổi.
- Chạy toàn bộ test suite với cờ tắt: phải đạt như `main`. Chạy với `A4`: oracle vét cạn phải giữ
  optimum. Test cố định đường gọi cũ được phép lỗi nếu lý do đã ghi rõ.
- Chạy thử một dataset với budget nhỏ, ngoài thư mục kết quả, để kiểm cờ và log.

## 6. Ranh giới

- Không commit code spike lên `main`, không merge, không push nhánh spike.
- Không đổi gate, budget, worker, seed, policy; không dùng witness hint.
- Evidence ghi vào `.worktrees/s1-lns/benchmarks/artifacts/s1-lns/`, không commit.
- Báo cáo spike là file docs riêng, chỉ commit khi được duyệt.

## 7. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| LNS Python có overhead (clone model, hint, kiểm lại) lớn ở 40 lớp, ít vòng trong budget | Đo số vòng và thời gian mỗi vòng; ghi nhận nếu overhead chiếm phần lớn |
| Kiểm lại mỗi lời giải được nhận bằng evaluator tốn thời gian | Chỉ kiểm lời giải được nhận (ít hơn số vòng), vẫn giữ bảo đảm hiện tại |
| Neighborhood quá nhỏ (kẹt) hoặc quá lớn (chậm như toàn bài) | Một kích thước chốt trước (L3); không dò tham số trên chính tập đo |
| Dao động theo thời gian che hiệu ứng | Baseline cùng phiên, n = 3, xen kẽ theo cặp, điều kiện theo đa số 2/3 |
| Kết quả trên s101 không tổng quát | Nếu đạt, S1-b và campaign S1-c dùng cả 3 seed |

## 8. Quyết định cần duyệt

- [x] **L1 — Hướng và vị trí:** A4 thay pha interleave của tier chưa chứng minh, luôn kèm A2. *(Đề xuất:
  chọn.)*
- [x] **L2 — Neighborhood:** GV (1–3), lớp (1–2), ngày × nhóm lớp; một nửa chọn theo vi phạm, một nửa
  ngẫu nhiên, xác định theo seed. *(Đề xuất: chọn.)*
- [x] **L3 — Tham số cố định:** kích thước khoảng 8 % số occurrence; giới hạn bài con 1 deterministic
  second; không dò tham số. *(Đề xuất: chọn. Hai giá trị này đặt trước, chưa thử.)*
- [x] **L4 — Đo:** 18 dataset s101, B và L, n = 3, xen kẽ theo cặp, khoảng 4 h liền. Phương án nhỏ hơn
  là chỉ 20/40 lớp (12 dataset, khoảng 3 h). *(Đề xuất: 18 dataset.)*
- [x] **L5 — Điều kiện §4:** đạt = ít nhất 2/3 lần lặp; +3 dataset; không hồi quy 3/3 → ≤ 1/3.
  *(Đề xuất: chọn.)*
- [x] **L6 — Ngưỡng an toàn:** mọi lời giải được nhận phải qua hard checker và evaluator độc lập trong
  vòng LNS. *(Đề xuất: chọn.)*
- [x] **L7 — Worktree:** `.worktrees/s1-lns` mới từ `main`, mang A2 sang; giữ nguyên `.worktrees/s1-spike`.
  *(Đề xuất: chọn.)*
- [x] **L8 — Nếu không đạt:** dừng hướng S1 về search và ghi nhận "chất lượng P1 ở 20/40 lớp không cải
  thiện được trong budget hiện tại bằng A1/A2/A4". Lựa chọn tiếp theo (budget, worker, hay chấp nhận giới
  hạn) khi đó là quyết định sản phẩm riêng. *(Đề xuất: chọn.)*

## 9. Kiểm tra khi soạn

- Bảng §1 tính lại chỉ đọc từ 90 ScoreReport có P1 > 0 của `phase2-v2-linux-02`
  (`independent-checks/*/evaluate-score.stdout`).
- Vị trí thay đổi đối chiếu với `_solve_tier` và `run_quality` trong `src/tkb_core/solver/objectives.py`
  (`main` `2ff4834`).
- Ước lượng thời gian: 108 run × budget trung bình 120 s ≈ 3,6 h, cộng khoảng 2–5 s overhead mỗi run.
- Không chạy test hay solver; không sửa file nào khác.
