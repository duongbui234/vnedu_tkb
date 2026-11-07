# S1-a — báo cáo spike chất lượng search (A1, A2)

Ngày 2026-11-07. Bước S1-a của [kế hoạch S1](superpowers/plans/2026-11-07-search-quality-s1.md)
(R1–R6 đã duyệt). **Kết luận: không hướng nào đạt điều kiện §5; không đưa A1 hay A2 sang S1-b ở dạng
hiện tại.** Đây là phép đo chẩn đoán (n = 1 mỗi ô), không phải evidence nghiệm thu.

## 1. Cách làm

- Worktree `.worktrees/s1-spike`, nhánh local `spike/s1-a` từ `4261fcc`; không commit, không merge.
  Patch `src/tkb_core/solver/objectives.py` có SHA256
  `4eba00e07d10c2395430cdaa143590687086fe072de3d855e94036f3cfac6f4c`, kèm test
  `tests/unit/test_s1_spike_flags.py`.
- Cờ nội bộ `TKB_S1_SPIKE`, tắt mặc định:
  - **A1** (kèm A3): probe chỉ ép tầng hiện tại bằng 0, thay cho probe ép mọi tầng; giữ trần 12
    deterministic seconds.
  - **A2**: hint toàn bộ biến của incumbent, không chỉ biến placement.
- Kiểm trước khi chạy:
  - cờ tắt: `pytest tests benchmarks/tests` 2009 passed, 22 skipped; ruff, format, mypy PASS;
  - cờ `A1,A2`: mọi test oracle vét cạn đạt (optimum giữ nguyên). 38 test lỗi đều do test cố định đường
    gọi cũ (35 hàm giả không nhận `keep_solution`, 3 test kiểm probe ép mọi tầng), không có lỗi đúng/sai.
- Chạy: 18 dataset s101 × A1, A2, A1+A2 = 54 run, 2026-11-07 12:36–14:19, máy Linux của người dùng
  (cắm sạc, `systemd-inhibit`). Lệnh solve qua `benchmarks/native_trace.py`, cùng budget, guard, 1 worker,
  seed 42 như campaign v2. Mỗi lịch được chạy lại `validate-schedule` và `evaluate-score`.
- So theo cặp với `phase2-v2-linux-02` cùng dataset (r1, và r1–r3). Đường solve không đổi từ `7e47f74`
  đến `main` (chỉ `cli.py` có thêm lệnh). Evidence: `.worktrees/s1-spike/benchmarks/artifacts/s1-spike/`.

## 2. Kết quả

Vector `[P1,P2,P3]` lấy từ `evaluate-score`; ✓ là đạt M1–M3 của profile v0 (P1 = 0).

| Dataset | v2 r1 | v2 r1–r3 đạt | A1 | A2 | A1+A2 |
|---|---|---:|---|---|---|
| c10-base-hard | `[7,71,250]` | 0/3 | `[7,71,250]` | `[6,72,250]` | `[6,72,250]` |
| c10-base-soft | `[0,106,219]` ✓ | 3/3 | `[46,146,211]` | `[45,144,210]` | `[45,144,210]` |
| c10-mixed-hard | `[0,0,117]` ✓ | 3/3 | `[0,0,36]` ✓ | `[0,0,117]` ✓ | `[0,0,37]` ✓ |
| c10-mixed-soft | `[0,0,42]` ✓ | 3/3 | `[0,0,107]` ✓ | `[0,0,105]` ✓ | `[0,0,106]` ✓ |
| c10-tight-hard | `[0,0,72]` ✓ | 3/3 | `[0,0,72]` ✓ | `[0,0,72]` ✓ | `[0,0,72]` ✓ |
| c10-tight-soft | `[0,110,68]` ✓ | 3/3 | `[0,111,69]` ✓ | `[0,110,69]` ✓ | `[0,110,69]` ✓ |
| c20-base-hard | `[10,116,475]` | 0/3 | `[10,116,475]` | `[10,116,475]` | `[0,108,462]` ✓ |
| c20-base-soft | `[0,211,457]` ✓ | 1/3 | `[94,290,433]` | `[93,288,432]` | `[93,288,432]` |
| c20-mixed-hard | `[10,81,300]` | 0/3 | `[11,79,296]` | `[11,79,296]` | `[11,79,296]` |
| c20-mixed-soft | `[0,148,290]` ✓ | 3/3 | `[0,148,290]` ✓ | `[0,145,287]` ✓ | `[0,145,287]` ✓ |
| c20-tight-hard | `[7,23,154]` | 0/3 | `[7,23,154]` | `[7,23,154]` | `[7,23,154]` |
| c20-tight-soft | `[0,236,151]` ✓ | 3/3 | `[0,236,151]` ✓ | `[0,236,151]` ✓ | `[0,236,151]` ✓ |
| c40-base-hard | `[21,233,924]` | 0/3 | `[21,233,924]` | `[21,233,924]` | `[21,233,924]` |
| c40-base-soft | `[110,571,865]` | 0/3 | `[110,571,865]` | `[110,571,865]` | `[110,571,865]` |
| c40-mixed-hard | `[0,134,564]` ✓ | 3/3 | `[0,134,564]` ✓ | `[0,136,562]` ✓ | `[0,136,562]` ✓ |
| c40-mixed-soft | `[63,397,601]` | 0/3 | `[63,397,601]` | `[62,396,603]` | `[62,396,603]` |
| c40-tight-hard | `[25,43,317]` | 0/3 | `[25,43,317]` | `[23,43,313]` | `[25,43,317]` |
| c40-tight-soft | `[24,567,322]` | 0/3 | `[24,567,322]` | `[24,567,322]` | `[12,542,312]` |
| **Đạt M1–M3** | **9** (r2, r3: 8) | | **7** | **7** | **8** |

## 3. Chấm theo §5 của kế hoạch

| Điều kiện | A1 | A2 | A1+A2 |
|---|---|---|---|
| (1) Không mất H, không mất lịch | Đạt (54/54 hard-valid, `evaluate-score` OK) | Đạt | Đạt |
| (2) Đạt M1–M3 tăng ít nhất +3 so với v2 r1, không dataset nào từ P1 = 0 sang P1 > 0 | **Không đạt**: −2; hồi quy c10-base-soft, c20-base-soft | **Không đạt**: −2; cùng hai hồi quy | **Không đạt**: −1; cùng hai hồi quy (có thêm c20-base-hard đạt) |
| (3) Feasibility không chậm hơn 10 % hoặc 1 s | Đạt (stage feasibility không đổi) | Đạt | Đạt |

Peak RSS cao nhất là 644 MiB.

## 4. Vì sao không đạt

- **Giả thuyết của A1 sai trong phạm vi trần 12 dt.** Probe chỉ ép P1 = 0 tìm được lời giải ở 2/18
  dataset (c10-mixed, nơi v2 vốn đã đạt P1 = 0); 16 dataset còn lại dừng UNKNOWN ở trần. Ép P1 = 0 riêng
  **không** dễ như bài feasibility của biến thể HARD (F5 trong kế hoạch). Probe còn tốn 12 dt mỗi tầng như
  trước, kể cả ở MIXED/TIGHT, nơi probe cũ trả INFEASIBLE gần như ngay lập tức.
- **A2 sửa đúng triệu chứng F4 nhưng không cải thiện điểm.** Ở c40-base, stage P1 interleave nay trả
  FEASIBLE (giữ được incumbent) thay vì UNKNOWN như v2. Nhưng incumbent đó chính là lịch hard-only ban đầu;
  điểm cuối không đổi (`[21,233,924]`, `[110,571,865]`).
- **Hai hồi quy nằm ở dataset sát ngưỡng thời gian, chưa chắc do cờ gây ra.** Ở c10-base-soft:
  - stage feasibility và verification giống hệt v2 (cùng lời giải `[48,144,210]`);
  - probe dừng ở trần 12 dt, mất 24 s thay vì 20 s (v2);
  - stage interleave sau đó, cùng model và hint ở biến thể A1, bị cắt ở dt 17,1. v2 tìm ra P1 = 0 lúc dt
    17,5.

  Pilot của v2 trên cùng input cũng ra `[46,146,211]`. c20-base-soft chỉ đạt 1/3 lần lặp ở v2. Chênh lệch
  −1/−2 nằm trong mức dao động giữa các lần lặp (v2 r1/r2/r3: 9/8/8). Vì vậy kết luận chỉ là
  "**không thấy cải thiện**", không phải "làm xấu đi".

## 5. Hệ quả cho kế hoạch S1

- Không đưa A1, A2 sang S1-b ở dạng hiện tại.
- Bài học đo:
  - So với campaign cũ bị nhiễu bởi các điểm cắt theo wall time. Spike sau nên có **baseline cờ tắt chạy
    cùng phiên** và có lặp, để tách hiệu ứng của cờ khỏi dao động thời gian.
  - Tốc độ máy so với v2 tương đương: tỷ lệ wall/dt của stage feasibility có trung vị 1,01, dao động
    0,97–1,12.
- Hướng còn lại theo kế hoạch: **A4 (LNS theo cấu trúc bài toán)**, hoặc giữ phần A2 (giữ incumbent) làm
  nền rồi đổi cách tìm P1 = 0. Cả hai cần kế hoạch hoặc spike mới được duyệt.
- Worktree `.worktrees/s1-spike` và evidence được giữ nguyên, chưa xóa.
