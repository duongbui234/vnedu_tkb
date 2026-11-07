# S1-b′ — báo cáo spike LNS theo cấu trúc bài toán (A4)

Ngày 2026-11-07. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-07.** Spike theo
[kế hoạch S1-b′](superpowers/plans/2026-11-07-s1-b-prime-lns-spike.md) (L1–L8 đã duyệt). Đây là phép đo
chẩn đoán, không phải evidence nghiệm thu. **Kết luận: không đạt §4.** Điều kiện (3) trượt: A4 hồi quy ở 3 dataset TIGHT, dù đạt (1),
(2) với +4 và (4). Theo mục 0.2, **A4 ở dạng này bị loại.**

> **Thời điểm soạn khung:** khoảng 20:50 ngày 2026-11-07, khi 64/108 run đã xong. Đến lúc này người soạn
> mới chỉ đọc mã thoát và thời lượng của từng run (`runner.out`) cùng `power.log`. Chưa chạy script chấm,
> chưa đọc ScoreReport hay `result.json` của run nào. Mục 0 vì thế được chốt trước khi biết kết quả và
> không được sửa sau khi chấm. Nếu cần đổi, ghi thành mục "Sửa đổi sau khi chấm" kèm lý do.

## 0. Cây quyết định (chốt trước khi chấm)

Điều kiện §4 của kế hoạch giữ nguyên. Một dataset **đạt** với một biến thể khi P1 = 0 (M1–M3 của profile
v0) ở ít nhất 2/3 lần lặp. Bốn điều kiện: (1) an toàn, (2) L ≥ B + 3 dataset đạt, (3) không hồi quy
3/3 → ≤ 1/3, (4) RSS dưới target và feasibility không chậm hơn.

### 0.1 Run có dùng được để chấm không

| Tình huống | Xử lý |
|---|---|
| Thiếu run, runner dừng giữa chừng hoặc `exit` khác 0 | **Không kết luận.** Báo cáo ghi phần đã có. Chạy bù chỉ những run thiếu, cùng patch (`spike.patch` SHA256 bắt đầu `3f5f56dc…`), và chỉ khi có lệnh cho phép riêng |
| `spike.patch` hoặc test lúc chấm khác bản đã ghi lúc chạy | **Không kết luận.** Evidence không gắn được với code |
| Đủ 108 run, mọi run `exit = 0` | Chấm theo 0.2 |

### 0.2 Nhánh theo kết quả §4

```text
(1) an toàn đạt? ──không──► LOẠI A4 ở dạng này (kể cả khi (2) đạt).
   │                          Tìm nguyên nhân, ghi vào báo cáo. Sửa lỗi rồi đo lại thì đó là
   │                          spike mới, cần kế hoạch và điều kiện chốt trước mới.
   có
   ▼
(3) có hồi quy 3/3 → ≤ 1/3? ──có──► LOẠI A4 ở dạng này. Nêu dataset hồi quy.
   │
   không
   ▼
(4) RSS / feasibility đạt? ──không──► LOẠI A4 ở dạng này. Nêu run vượt.
   │
   có
   ▼
(2) L − B ≥ +3? ──không──► KHÔNG ĐẠT → áp dụng L8 (mục 0.4).
   │
   có
   ▼
ĐẠT → kiểm độ nhạy (0.3) → đề xuất soạn kế hoạch S1-b cho A4 (mục 0.5).
```

Các quy tắc cố định:

- Không nới ngưỡng sau khi thấy số liệu. +2 vẫn là không đạt; 2/3 vẫn là ngưỡng đạt của một dataset.
- Không dò lại tham số (8 % occurrence, 1 dt mỗi bài con) trên chính 18 dataset này (L3).
- Các mục "ghi nhận, không dùng làm gate" của §4 không được dùng để đổi kết luận theo bất kỳ chiều nào.

### 0.3 Kiểm độ nhạy theo hồ sơ điện năng (chốt trước)

Hồ sơ đổi từ `balanced` sang `performance` giữa 18:57 và 19:02, do người dùng chủ động đổi. Bốn run đầu
(`c10-base-s101-soft` B/L r1, `c10-base-s101-hard` B/L r1) chạy dưới `balanced`. Run thứ năm
(`c10-mixed-s101-soft` B r1, bắt đầu 19:02) không xác định được hồ sơ. Mọi run sau đó chạy dưới
`performance`.

- Chấm chính dùng cả 108 run, vì B và L chạy xen kẽ theo cặp.
- Kiểm độ nhạy: chấm lại (2) và (3) sau khi bỏ các cặp có ít nhất một run trước 19:02 (cặp r1 của
  `c10-base-s101-soft`, `c10-base-s101-hard`, `c10-mixed-s101-soft`); với dataset bị bỏ một lần lặp, ngưỡng
  đạt là 2/2.
  - Kết luận không đổi: giữ kết luận chính.
  - Kết luận đổi: ghi **"không kết luận được do hồ sơ điện năng"**, không chọn nhánh nào. Đo lại cần lệnh
    cho phép riêng.
- Không so số tuyệt đối (thời gian, P1 tại thời điểm cắt) với v2 hay S1-a, vì hồ sơ khác. Chỉ so B với L
  trong cùng phiên.

### 0.4 Nếu không đạt (L8)

- Dừng hướng S1 về search. Ghi: "chất lượng P1 ở 20/40 lớp không cải thiện được trong budget hiện tại bằng
  A1/A2/A4".
- Không mở spike search khác (ví dụ neighbourhood lớn hơn, sub-solve dài hơn) trong phạm vi S1.
- Lựa chọn tiếp theo là **quyết định sản phẩm riêng**, báo cáo chỉ liệt kê, không đề xuất chọn:
  - tăng budget hoặc số worker;
  - chấp nhận giới hạn chất lượng ở 20/40 lớp và ghi vào profile;
  - thay đổi cách mô hình hóa ở bước sau, ngoài S1.
- Nếu L cải thiện rõ ở chỉ số phụ (P1 trung vị theo cặp) nhưng không đạt (2), báo cáo ghi nhận đúng như
  vậy, không đổi kết luận.

### 0.5 Nếu đạt

Đề xuất soạn **kế hoạch S1-b** (DRAFT, cần duyệt riêng; chưa sửa Core). Kế hoạch phải xử lý ít nhất:

1. **Tính tất định.** Vòng LNS trong spike dừng theo wall time, nên cùng seed vẫn có thể cho kết quả
   khác. S1-b cần chọn: giới hạn vòng bằng deterministic time hoặc số vòng, hoặc chấp nhận không tất
   định như một quyết định sản phẩm có ghi rõ.
2. **Contract và metadata:** báo cáo LNS trong `tier_runs` (vòng, vòng nhận, lý do dừng) mà không đổi
   ScoreReport; OPTIMAL chỉ khi giá trị bằng 0.
3. **Test:** viết lại các test cố định đường gọi interleave và hàm giả thiếu `keep_solution`; giữ oracle
   vét cạn.
4. **Campaign S1-c:** 3 seed (không chỉ s101), baseline cùng phiên, điều kiện chốt trước. Không đổi gate
   Acceptance v2 trong S1.

Nếu đạt nhưng sát ngưỡng (đúng +3, hoặc có dataset đạt 2/3 nhờ một lần lặp), báo cáo ghi rõ để S1-c kiểm
lại trên seed khác. Kết luận không đổi.

## 1. Cách làm

- Worktree `.worktrees/s1-lns`, nhánh local `spike/s1-b-prime` từ `70d180b`; không commit, không merge.
  Patch có SHA256 `3f5f56dc2d2b5d001d4bc8cebe53bce55a1fa007b13d7b33bfbee7f2eff9ad7f`. Lúc chấm, `git diff`
  của worktree vẫn cho đúng hash này, và hai file test khớp byte với bản sao trong thư mục evidence. Test
  spike: `tests/unit/test_s1_lns.py` (10 test) và `tests/unit/test_s1_spike_flags.py` (từ S1-a).
- Cờ `TKB_S1_SPIKE=A4` (tự kèm A2). Thay pha interleave của tier chưa chứng minh bằng vòng LNS:
  - neighbourhood GV (≤ 3), lớp (≤ 2) và ngày; một nửa số vòng chọn theo vi phạm;
  - khoảng 8 % số occurrence; mỗi bài con 1 deterministic second;
  - assumptions cố định placement ngoài neighbourhood, hint đầy đủ;
  - nhận theo thứ tự từ điển; mỗi lời giải được nhận qua hard checker và evaluator.
- Khác biệt so với chữ trong kế hoạch (không đổi bản chất):
  - Kế hoạch ghi "clone của model"; spike dùng assumptions trên chính model và xóa assumptions sau mỗi
    vòng.
  - RNG là một luồng `random.Random(f"{seed}|{p}")` cho cả tier, thay vì seed riêng mỗi vòng. Vẫn xác
    định theo seed.
- Lỗi tìm được khi TDD, đã sửa trước khi chạy: thời gian dựng vòng có thể làm giới hạn CP-SAT âm, gây
  `MODEL_INVALID` (3/60 case oracle). Đã có test hồi quy.
- Kiểm trước khi chạy:
  - **Cờ tắt:** `pytest tests benchmarks/tests` 2019 passed, 22 skipped. Lần chạy đầu có một lỗi không
    lặp lại; chạy lại thì đạt. Ruff, format, mypy PASS.
  - **Cờ A4, trước khi sửa lỗi trên:**

    | Nhóm test | Kết quả |
    |---|---|
    | unit | 38 failed, 470 passed |
    | integration | 16 failed, 166 passed |
    | properties | 155 failed, 694 passed, 14 skipped |
    | benchmarks/tests | 5 failed, 474 passed, 8 skipped |

    Các lỗi gồm:
    - assertion về status OPTIMAL hoặc proof, vì LNS không chứng minh tối ưu khác 0 (phần lớn lỗi ở
      oracle);
    - hàm giả và test riêng của interleave;
    - `best_bound` là None;
    - tính tất định;
    - lỗi `MODEL_INVALID` nói trên.

    Sau khi sửa, tôi chạy lại các instance oracle hard-variant bằng một script quét, không chạy lại cả
    suite: không có lịch sai hay `MODEL_INVALID`, và mọi kết quả OPTIMAL khớp optimum của oracle. Không
    phân loại số lỗi theo từng nhóm.
- Chạy: 18 dataset s101 × {B, L} × 3 = 108 run, 2026-11-07 18:57–22:25, xen kẽ theo cặp. Máy Linux của
  người dùng (i7-12700H, cắm sạc suốt, `systemd-inhibit`). Lệnh qua `benchmarks/native_trace.py`, cùng
  budget, guard, 1 worker, seed 42 như v2. Mỗi lịch được chạy lại `validate-schedule` và `evaluate-score`.
  Cả 108 run có `exit = 0` (mục 0.1: đủ để chấm).
- **Hồ sơ điện năng theo cặp:**

  | Cặp | Run | Hồ sơ |
  |---|---|---|
  | `c10-base-s101-soft` r1 | B 18:57:29–18:58:16, L 18:58:16–18:59:18 | `balanced` |
  | `c10-base-s101-hard` r1 | B 18:59:18–19:00:14, L 19:00:14–19:01:04 | `balanced` |
  | `c10-mixed-s101-soft` r1 | B 19:01:04–19:02:05 (không xác định), L 19:02:05–19:03:06 | đổi trong cặp |
  | 51 cặp còn lại | 19:03:07–22:25:21 | `performance` |

  `power.log` ghi `balanced` lúc 18:57 và `performance` ở 41 mẫu từ 19:02 đến 22:22 (cắm sạc suốt). Giờ bắt
  đầu mỗi run = thời điểm ghi `record.json` trừ thời lượng.
- Evidence: `.worktrees/s1-lns/benchmarks/artifacts/s1-lns/` (`runs/`, `runner.out`, `power.log`,
  `power-profile.txt`, `spike.patch`). Không commit. Script chấm nằm ngoài repo: `lns_analyze.py` (§4) và
  `lns_secondary.py` (ghi nhận phụ).

## 2. Kết quả

Giá trị P1 lấy từ `evaluate-score` độc lập. Một dataset đạt khi P1 = 0 ở ít nhất 2/3 lần lặp.

| Dataset | B r1 · r2 · r3 (P1) | B đạt | L r1 · r2 · r3 (P1) | L đạt | Vòng LNS (nhận) |
|---|---|---:|---|---:|---|
| c10-base-s101-hard | 7 · 7 · 7 | 0/3 | 0 · 0 · 0 | 3/3 | 53(38) · 53(38) · 53(38) |
| c10-base-s101-soft | 46 · 0 · 0 | 2/3 | 0 · 0 · 0 | 3/3 | 48(33) · 64(45) · 64(45) |
| c10-mixed-s101-hard | 0 · 0 · 0 | 3/3 | 0 · 0 · 0 | 3/3 | 840(43) · 826(43) · 825(43) |
| c10-mixed-s101-soft | 0 · 0 · 0 | 3/3 | 0 · 0 · 0 | 3/3 | 617(51) · 640(51) · 634(51) |
| **c10-tight-s101-hard** | 0 · 0 · 0 | 3/3 | 6 · 6 · 6 | **0/3** | 2405(1) · 2423(1) · 2418(1) |
| **c10-tight-s101-soft** | 0 · 0 · 0 | 3/3 | 11 · 11 · 11 | **0/3** | 2007(5) · 2009(5) · 2049(5) |
| c20-base-s101-hard | 10 · 10 · 10 | 0/3 | 0 · 0 · 0 | 3/3 | 75(53) · 75(53) · 75(53) |
| c20-base-s101-soft | 94 · 94 · 94 | 0/3 | 0 · 0 · 0 | 3/3 | 82(44) · 82(45) · 81(44) |
| c20-mixed-s101-hard | 10 · 10 · 10 | 0/3 | 0 · 0 · 0 | 3/3 | 515(77) · 523(77) · 522(77) |
| c20-mixed-s101-soft | 0 · 0 · 0 | 3/3 | 0 · 0 · 0 | 3/3 | 354(83) · 360(84) · 368(84) |
| c20-tight-s101-hard | 7 · 7 · 7 | 0/3 | 9 · 9 · 9 | 0/3 | 2112(3) · 2090(3) · 2081(3) |
| **c20-tight-s101-soft** | 0 · 0 · 0 | 3/3 | 20 · 20 · 20 | **0/3** | 1827(16) · 1847(16) · 1825(16) |
| c40-base-s101-hard | 21 · 21 · 21 | 0/3 | 0 · 0 · 0 | 3/3 | 74(65) · 75(66) · 74(65) |
| c40-base-s101-soft | 110 · 110 · 110 | 0/3 | 0 · 0 · 0 | 3/3 | 58(53) · 57(52) · 58(53) |
| c40-mixed-s101-hard | 0 · 0 · 0 | 3/3 | 0 · 0 · 0 | 3/3 | 143(99) · 136(98) · 132(97) |
| c40-mixed-s101-soft | 63 · 63 · 63 | 0/3 | 0 · 0 · 0 | 3/3 | 213(80) · 186(80) · 199(80) |
| c40-tight-s101-hard | 25 · 25 · 25 | 0/3 | 25 · 25 · 25 | 0/3 | 266(1) · 280(1) · 280(1) |
| c40-tight-s101-soft | 12 · 24 · 12 | 0/3 | 20 · 20 · 20 | 0/3 | 730(5) · 723(5) · 734(5) |
| **Số dataset đạt** | | **8** | | **12** | |

Hình dạng kết quả rõ theo profile dataset:

- **BASE và MIXED (12 dataset):** L đạt 12/12, B đạt 5/12. L đưa P1 về 0 ở 7 dataset mà B còn
  P1 = 7–110, gồm cả 40 lớp. L không thua B ở dataset nào trong nhóm này.
- **TIGHT (6 dataset):** L thua B ở 5/6 và hòa ở 1/6 (`c40-tight-s101-hard`, cùng `[25,43,317]`). B đạt
  3/6 (P1 = 0 ở cả ba lần lặp), L đạt 0/6.

## 3. Chấm theo §4

| Điều kiện | Ngưỡng | Kết quả | Đạt? |
|---|---|---|---|
| (1) An toàn | 54/54 L hard-valid, score OK; không `MODEL_INVALID` / `INTERNAL_*`; không mất lịch so với B cùng cặp | 54/54 `SCHEDULE_VALID` và `evaluate-score` OK; không `MODEL_INVALID`, không `INTERNAL_*`; 0 run mất lịch | **Đạt** |
| (2) Cải thiện chính | L − B ≥ +3 dataset đạt | B = 8, L = 12, **+4** | **Đạt** |
| (3) Không hồi quy | không dataset B 3/3 → L ≤ 1/3 | **3 dataset:** `c10-tight-s101-hard`, `c10-tight-s101-soft`, `c20-tight-s101-soft` (B 3/3 → L 0/3) | **Trượt** |
| (4) Tài nguyên | RSS < 1/2/4 GiB; feasibility không chậm hơn | Max RSS B 647 MiB, L 550 MiB; 0 run vượt target. Trung vị wall time của feasibility khác nhau ≤ 2 % ở mọi dataset | **Đạt** |
| Độ nhạy hồ sơ điện năng (0.3) | kết luận không đổi khi bỏ các cặp trước 19:02 | Bỏ cặp r1 của `c10-base-s101-soft`, `c10-base-s101-hard`, `c10-mixed-s101-soft` (ngưỡng 2/2). Ba dataset vẫn có cùng kết quả đạt/không cho B và L, nên vẫn B = 8, L = 12; ba dataset hồi quy là TIGHT, không bị ảnh hưởng | **Không đổi** |

**Nhánh theo mục 0.2:** (1) đạt → (3) có hồi quy → **LOẠI A4 ở dạng này.** Điều kiện (2) đạt không cứu
được kết luận, đúng như quy tắc đã chốt.

Không có sửa đổi nào với mục 0 sau khi chấm.

## 4. Ghi nhận phụ (không dùng làm gate)

- **P1 theo cặp khi cả hai biến thể đều P1 > 0:** 9 cặp, tất cả thuộc TIGHT. L < B ở 1 cặp, L = B ở 3,
  L > B ở 5; tỉ lệ trung vị L/B là 1,29.
- **P2/P3 khi P1 bằng nhau và bằng 0** (BASE/MIXED): L tốt hơn B ở cả P2 lẫn P3 trong mọi cặp. Ví dụ:

  | Dataset | B | L |
  |---|---|---|
  | `c20-mixed-s101-soft` | `[0,148,290]` | `[0,0,61]` hoặc `[0,0,62]` |
  | `c40-mixed-s101-hard` | `[0,134,564]` | `[0,0,178–180]` |

  L còn cho `[0,0,0]` OPTIMAL ở `c10-base-s101-hard` và `c20-base-s101-hard`. Trên các dataset BASE/MIXED
  mà B còn P1 > 0, P2 của L cũng giảm rất nhiều, ví dụ `c40-mixed-s101-soft` từ `[63,397,601]` xuống
  `[0,1,437]`.
- **Thời điểm chạm P1 = 0** (tính từ đầu pha LNS của P1, ở L):

  | Quy mô | Thời gian |
  |---|---|
  | c10 | 2–16 s |
  | c20 | 8–44 s |
  | c40 | 28–93 s |

  Lâu nhất là `c40-base-s101-soft`, khoảng 91 s trên budget 180 s.
- **Dao động của B:** P1 của B giống nhau ở cả ba lần lặp, trừ hai trường hợp:
  - `c10-base-s101-soft`: r1 có P1 = 46, chạy dưới `balanced`; r2 và r3 có P1 = 0, chạy dưới
    `performance`. Đây là dấu hiệu phép đo nhạy với hồ sơ điện năng. Kiểm độ nhạy ở §3 cho thấy nó không
    đổi kết luận.
  - `c40-tight-s101-soft`: P1 = 12 · 24 · 12.

  Hai vector của B trùng với mẫu đã duyệt ở [biên bản Q](quality-decisions/README.md):
  `c10-base-s101-soft` r2/r3 = `[0,106,219]` (mẫu A) và `c40-base-s101-hard` = `[21,233,924]` (mẫu B).
- **Dao động của L:** P1 giống nhau ở cả ba lần lặp, trên mọi dataset. P2/P3 và số vòng dao động nhẹ,
  đúng như dự kiến vì vòng LNS dừng theo wall time. Ví dụ:
  - `c40-base-s101-soft`: P2 từ 140 đến 150;
  - `c20-base-s101-soft`: P3 từ 224 đến 249.
- **Vì sao L thua ở TIGHT (chẩn đoán, không phải kết luận gate):**
  - Ở `c10-tight-s101-hard`, B dùng interleave toàn model và **chứng minh** P1 = 0 trong 13,5 s, rồi
    P2 = 0, kết thúc với `[0,0,72]` LEXICOGRAPHIC_OPTIMAL.
  - L bỏ interleave và bắt đầu LNS từ incumbent `[6,10,78]`. Trong khoảng 2 400 vòng, mọi bài con trả
    OPTIMAL với cùng vector, và chỉ vòng đầu được nhận (vì bằng nhau). Nghĩa là incumbent là cực tiểu cục
    bộ đối với neighbourhood khoảng 8 %.
  - Ở TIGHT, availability chặt nên sửa vi phạm cần di chuyển xa hơn kích thước neighbourhood. Search toàn
    model tìm được nước đi đó; LNS thì không.
  - Ở BASE/MIXED thì ngược lại: interleave toàn model không đủ thời gian (40 lớp), còn bài con nhỏ thì
    giảm P1 nhanh.
- **Overhead:** số vòng mỗi run từ 48 (c10 BASE) đến 2 423 (c10 TIGHT). Ở c40 BASE/MIXED có 57–213 vòng
  trong budget 180 s, tức khoảng 1–3 s mỗi vòng, gồm dựng vòng, sub-solve 1 dt và kiểm lời giải được nhận.
  Chưa tách riêng phần overhead Python.

## 5. Giới hạn

- Synthetic, chỉ seed s101, một máy Linux, n = 3. Đây là phép đo chẩn đoán, không phải bằng chứng chất
  lượng.
- Vòng LNS dừng theo wall time, nên L không tất định với cùng seed. Ba lần lặp cho thấy P1 ổn định, còn
  P2/P3 dao động nhẹ.
- Hồ sơ điện năng đổi trong lúc chạy (mục 0.3). Kiểm độ nhạy không đổi kết luận, nhưng một cặp B
  (`c10-base-s101-soft` r1) cho thấy B nhạy với tốc độ máy.
- Không so số tuyệt đối với v2 hay S1-a.
- Trong lúc chạy chỉ có việc nhẹ (soạn docs); không chạy solver hay test suite song song. Tải máy theo
  `power.log` ở khoảng 1,0–1,3.

## 6. Kết luận và bước tiếp

**A4 ở dạng này không đạt §4 và bị loại.** Lý do duy nhất là điều kiện (3): ba dataset TIGHT mà B đạt
3/3 thì L đạt 0/3. An toàn, cải thiện chính (+4) và tài nguyên đều đạt.

Theo L8, khi spike không đạt thì hướng S1 về search dừng lại, và lựa chọn tiếp theo là quyết định sản phẩm
riêng. **Tuy vậy, câu ghi nhận soạn sẵn trong L8 không đúng với dữ liệu, nên không được ghi.** Câu đó là "chất lượng P1 ở
20/40 lớp không cải thiện được trong budget hiện tại bằng A1/A2/A4". Thực tế, A4 đưa P1 về 0 ở mọi dataset
BASE/MIXED 20/40 lớp (8/8), kể cả những dataset B còn P1 = 10–110. Ghi câu đó sẽ là ghi sai. **Kết luận được
ghi (người dùng duyệt ngày 2026-11-07, thay cho câu của L8):**

> A4 (LNS thay interleave) cải thiện mạnh P1/P2 ở BASE/MIXED đến 40 lớp nhưng hồi quy ở TIGHT, nơi search
> toàn model chứng minh được P1 = 0 còn LNS kẹt ở cực tiểu cục bộ; vì hồi quy, A4 ở dạng này không được
> đưa sang S1-b.

Áp dụng mục 0.4, các lựa chọn tiếp theo là quyết định sản phẩm của người duyệt. **Đến ngày 2026-11-07 chưa
có quyết định nào.** Báo cáo không chọn thay:

- dừng S1 như L8;
- tăng budget hoặc số worker;
- chấp nhận giới hạn chất lượng và ghi vào profile;
- mở một kế hoạch **spike mới** với điều kiện chốt trước mới, cho một biến thể không bỏ search toàn model.
  Ví dụ: chạy interleave như B, rồi chạy LNS trên incumbent tốt nhất; hoặc chạy LNS trước, rồi interleave.
  Theo mục 0.2, đây không phải đo lại spike này, và nó nằm ngoài phạm vi L8 nên cần quyết định riêng.
  Spike này không cho biết biến thể như vậy có đạt hay không.

Không có gì được merge hay commit lên `main` từ worktree spike. Worktree `.worktrees/s1-lns`, nhánh
`spike/s1-b-prime` và evidence được giữ nguyên.
