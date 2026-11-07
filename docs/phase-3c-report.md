# Phase 3C — báo cáo benchmark repair trên Linux (`phase3c-linux-02`)

Ngày 2026-11-07. Bước G của [kế hoạch 3C](superpowers/plans/2026-11-06-phase-3c-repair-benchmark.md)
(C1–C10 đã duyệt). Campaign chạy theo [runbook 3C](phase-3c-runbook.md); tooling và các sai khác so với kế
hoạch: [báo cáo tooling 3C](phase-3c-tooling-report.md).

**Phạm vi kết luận (C10):** repair trên dữ liệu synthetic, một máy Linux, n = 1 mỗi ô. Không có P95/SLA,
không chạy Windows, không chấp nhận chất lượng (Q vẫn REVIEW_REQUIRED). Khác biệt giữa các ô là quan sát,
không phải kết luận thống kê.

## 1. Tóm tắt

| Câu hỏi (kế hoạch §1) | Trả lời trên campaign này |
|---|---|
| 1. Repair có tìm được lịch hard-valid trong giới hạn không? | BASE/MIXED: có, **96/96** run R1 ra OPTIMAL ở cả 10/20/40 lớp, đều trong giới hạn. TIGHT: 6/48 OPTIMAL, 6 FEASIBLE (hết budget), 18 UNKNOWN, 18 INFEASIBLE (đã chứng minh). **Mọi lịch đều H PASS (148/148)**; không có lịch nào sai. Ở mức campaign, theo §4 thì **R1 không đạt P** vì có 18 run UNKNOWN, tất cả thuộc TIGHT |
| 2. Repair đổi bao nhiêu so với số thay đổi bắt buộc? | Với `BEFORE_QUALITY`, mọi run R1 OPTIMAL (102) đều có `min_changes_proved`; số thay đổi 0–9 tiết trên khoảng 260–1040 tiết. 44/108 run có lịch đổi đúng bằng `forced`; số còn lại đổi thêm do dây chuyền: tiết bị buộc dời phải lấy chỗ của tiết khác (N2 còn đổi GV) |
| 3. Hint và thứ tự ảnh hưởng thế nào? | **Hint:** ở R1, 72/72 cặp cùng status, cùng số thay đổi (trừ 1 cặp FEASIBLE: 22 và 17), thời gian gần như nhau (tỷ lệ 0,77–1,28, trung vị 1,0). **Thứ tự:** `AFTER_QUALITY` đổi 40–259 tiết thay vì 0–31, không cặp nào chứng minh được tối ưu trong 60 s; điểm tốt hơn `BEFORE_QUALITY` ở 33/40 cặp có lịch và kém hơn ở 7 |
| 4. `explain` mất bao lâu trên bài vô nghiệm? | 36/36 UNSAT_CAPACITY: `PRECHECK_PROOF` trong 0,3–0,9 s, không gọi solver. Với 22 repair INFEASIBLE, explain theo sau ra 20 `PRECHECK_PROOF` (0,08–0,64 s) và 2 `CORE_SUBSET` ở 20 lớp (khoảng 25 s, 13 lời gọi solver, minimal đã chứng minh) |

## 2. Danh tính campaign

| Mục | Giá trị |
|---|---|
| Campaign | `phase3c-linux-02`, worktree `.worktrees/phase3c-run-02` |
| Commit ghim | `67b45027b1c74445d0fc6c8de437427fa3085b2a` (git status sạch khi seal) |
| Wheel | `vnedu_tkb_core-0.2.0` `7ae89efc8453ac279026fc249f7e1da22d4623e2356441ca837db94697563b98`; OR-Tools 9.15.6755 |
| Máy | i7-12700H (20 luồng), RAM 40 GB, Linux 7.0.0-42, cgroup2; cắm sạc, `systemd-inhibit`, workload không kiểm soát (UNCONTROLLED) |
| Thời gian | 2026-11-07, 00:59 → 03:35 (khoảng 2,6 h; kế hoạch ước lượng trần 6,2 h budget, 11,5 h watchdog) |
| Reference (C2) | Plan `phase2-v2-linux-02` SHA256 `cf9c5b82…e99e`; 36 dataset trùng byte |
| `plan.json` | `fab2f327f9c6b97bccb668079e04dae412630753229557697221adaa93a0925b` |
| `derived.json` | `c90569ac7ad2c0c905bf8ed117a85880f58c4d301106107e68af44e7866c7452` |
| `summary.json` | `98b5956cfddc4c5e35d8108181b928e50026faa64cb9ad4f6449c4fb0887f981` |
| Gói evidence | `phase3c-campaign-02.tar.gz` `87a228b0d8f31a594e118824ce79a24a7ea98e8188228dd48f638ddccf1670da`, nằm trên máy người dùng, không commit |

Các bước D, E đạt (pilot `phase3c-linux-02-pilot`: 6/6 COMPLETE, H PASS). Lần chạy trước
`phase3c-linux-01` (`1ab0764`) dừng ở run R 43/192 vì lỗi tooling. Lỗi đã sửa ở `67b4502` (mục "Sửa sau
sự cố" của báo cáo tooling). Kết quả linux-01 không dùng trong báo cáo này.

## 3. Kiểm toàn vẹn (sau campaign, chỉ đọc)

Script kiểm chạy bằng tooling ở commit ghim. Nó gọi `check_identity`, `check_derived` và
`read_terminals`, rồi chạy lại mọi kiểm độc lập trong venv không có OR-Tools. Mọi output của script ghi ra
thư mục tạm, không vào campaign.

| Kiểm | Kết quả |
|---|---|
| Seal 1: `seal.json` khớp hash `plan.json` và `environment.json`; nguồn, bundle, preflight, runtime và máy không drift | OK, 54 hàng |
| Seal 2: `seal-derived.json` móc vào hash plan; 192 input nhiễu, lịch trước và request khớp hash | OK, không loại dataset nào |
| Chuỗi: mọi lịch trước trong `derived.json` là `S/<dataset>/result.json` của chính campaign | OK |
| Journal và receipt S/R/X: không có START trùng, không có run lạ, mọi TERMINAL khớp `terminal.json`, file evidence khớp receipt | OK: 18/18, 192/192, 36/36; state cả ba stage `COMPLETE` |
| Chạy lại `validate-schedule` và `evaluate-score` trên 18 lịch S | 18/18 OK |
| Chạy lại `validate-schedule`, `evaluate-score` và `evaluate-repair` trên 148 lịch repair | 148/148 OK cả ba |
| Chạy lại `check-explanation` trên 36 report X và 22 report explain theo sau | 58/58 OK |
| Mọi repair INFEASIBLE đều có explain theo sau | 22/22 |
| Harness và đo đạc | 246/246 `COMPLETE`, `measurement_status` OK; không có `CORE_REJECTED_INPUT`, `UNEXPECTED_STATUS` hay `SCHEDULE_FOR_PROVED_INFEASIBLE` |

## 4. Kết quả

### 4.1 Bước S — lịch trước (18 run)

H PASS 18/18, P MET 18/18. Repair đo so với lịch trước đúng như nó là: 17 lịch FEASIBLE (chưa tối ưu
chất lượng) và 1 lịch OPTIMAL.

| Dataset | Status | Time | Score |
|---|---|---|---|
| c10-base-s101-hard | FEASIBLE | 53 s | [7, 71, 250] |
| c10-base-s101-soft | FEASIBLE | 51 s | [46, 146, 211] |
| c10-mixed-s101-hard | FEASIBLE | 52 s | [0, 0, 117] |
| c10-mixed-s101-soft | FEASIBLE | 54 s | [0, 0, 106] |
| c10-tight-s101-hard | OPTIMAL | 47 s | [0, 0, 72] |
| c10-tight-s101-soft | FEASIBLE | 61 s | [0, 110, 69] |
| c20-base-s101-hard | FEASIBLE | 84 s | [10, 116, 475] |
| c20-base-s101-soft | FEASIBLE | 77 s | [95, 286, 428] |
| c20-mixed-s101-hard | FEASIBLE | 119 s | [10, 81, 300] |
| c20-mixed-s101-soft | FEASIBLE | 108 s | [0, 148, 290] |
| c20-tight-s101-hard | FEASIBLE | 121 s | [7, 23, 154] |
| c20-tight-s101-soft | FEASIBLE | 120 s | [0, 236, 151] |
| c40-base-s101-hard | FEASIBLE | 184 s | [21, 233, 924] |
| c40-base-s101-soft | FEASIBLE | 184 s | [110, 571, 865] |
| c40-mixed-s101-hard | FEASIBLE | 184 s | [0, 134, 564] |
| c40-mixed-s101-soft | FEASIBLE | 108 s | [63, 397, 601] |
| c40-tight-s101-hard | FEASIBLE | 184 s | [25, 43, 317] |
| c40-tight-s101-soft | FEASIBLE | 185 s | [12, 542, 312] |

### 4.2 R1 — `BEFORE_QUALITY` (144 run)

Mỗi ô ghi run có hint · run không hint. Ký hiệu: `OPT 5/2 3.1s` nghĩa là OPTIMAL, đổi 5 tiết, 2 tiết bị
buộc đổi (`forced`), launch-to-exit 3,1 s. `INF` là INFEASIBLE, `UNK` là UNKNOWN (hết budget, chưa có
lịch), `FEA` là FEASIBLE (có lịch, chưa chứng minh tối thiểu).

| Dataset | N1 | N2 | N3 | N4 |
|---|---|---|---|---|
| c10-base-s101-hard | OPT 2/2 3.4s · OPT 2/2 3.3s | OPT 2/0 5.4s · OPT 2/0 5.3s | OPT 0/0 3.6s · OPT 0/0 4.6s | OPT 6/2 38s · OPT 6/2 38s |
| c10-base-s101-soft | OPT 1/1 2.7s · OPT 1/1 2.6s | OPT 1/0 4.0s · OPT 1/0 3.8s | OPT 0/0 2.7s · OPT 0/0 3.3s | OPT 2/2 2.6s · OPT 2/2 2.6s |
| c10-mixed-s101-hard | OPT 5/2 2.7s · OPT 5/2 2.7s | OPT 5/2 3.2s · OPT 5/2 3.3s | OPT 1/0 2.5s · OPT 1/0 2.6s | OPT 8/2 3.1s · OPT 8/2 3.0s |
| c10-mixed-s101-soft | OPT 2/2 2.0s · OPT 2/2 1.9s | OPT 2/0 2.7s · OPT 2/0 2.9s | OPT 0/0 2.1s · OPT 0/0 2.0s | OPT 4/2 2.5s · OPT 4/2 2.6s |
| c10-tight-s101-hard | UNK 60s · UNK 60s | INF 0.3s · INF 0.3s | FEA 22/0 60s · FEA 17/0 60s | OPT 4/2 1.7s · OPT 4/2 1.8s |
| c10-tight-s101-soft | OPT 1/1 1.7s · OPT 1/1 1.7s | INF 0.3s · INF 0.3s | OPT 5/0 3.6s · OPT 5/0 3.5s | FEA 31/2 60s · FEA 31/2 60s |
| c20-base-s101-hard | OPT 1/1 7.6s · OPT 1/1 9.4s | OPT 1/0 9.6s · OPT 1/0 9.8s | OPT 0/0 8.0s · OPT 0/0 9.6s | OPT 4/2 9.5s · OPT 4/2 7.4s |
| c20-base-s101-soft | OPT 2/2 6.4s · OPT 2/2 6.8s | OPT 1/0 7.6s · OPT 1/0 7.3s | OPT 0/0 6.1s · OPT 0/0 6.6s | OPT 5/2 7.0s · OPT 5/2 6.5s |
| c20-mixed-s101-hard | OPT 8/4 23s · OPT 8/4 23s | OPT 3/1 6.6s · OPT 3/1 6.0s | OPT 1/0 7.0s · OPT 1/0 7.2s | OPT 9/2 28s · OPT 9/2 27s |
| c20-mixed-s101-soft | OPT 2/2 4.8s · OPT 2/2 5.4s | OPT 4/0 7.1s · OPT 4/0 7.3s | OPT 0/0 4.8s · OPT 0/0 4.8s | OPT 7/2 7.0s · OPT 7/2 6.9s |
| c20-tight-s101-hard | INF 0.4s · INF 0.4s | INF 0.4s · INF 0.4s | UNK 120s · UNK 120s | UNK 120s · UNK 120s |
| c20-tight-s101-soft | INF 0.4s · INF 0.4s | INF 0.4s · INF 0.4s | FEA 11/0 121s · FEA 11/0 121s | INF 0.9s · INF 0.8s |
| c40-base-s101-hard | OPT 2/2 21s · OPT 2/2 20s | OPT 3/0 26s · OPT 3/0 25s | OPT 0/0 21s · OPT 0/0 20s | OPT 4/2 20s · OPT 4/2 20s |
| c40-base-s101-soft | OPT 1/1 16s · OPT 1/1 17s | OPT 1/0 19s · OPT 1/0 20s | OPT 0/0 16s · OPT 0/0 17s | OPT 4/2 18s · OPT 4/2 17s |
| c40-mixed-s101-hard | OPT 1/1 15s · OPT 1/1 15s | OPT 3/1 17s · OPT 3/1 17s | OPT 0/0 14s · OPT 0/0 14s | OPT 9/2 19s · OPT 9/2 18s |
| c40-mixed-s101-soft | OPT 1/1 13s · OPT 1/1 13s | OPT 2/1 17s · OPT 2/1 17s | OPT 0/0 13s · OPT 0/0 14s | OPT 7/2 19s · OPT 7/2 20s |
| c40-tight-s101-hard | UNK 180s · UNK 180s | INF 0.8s · INF 0.8s | UNK 180s · UNK 180s | UNK 180s · UNK 180s |
| c40-tight-s101-soft | UNK 180s · UNK 180s | INF 0.8s · INF 0.8s | UNK 180s · UNK 180s | UNK 180s · UNK 180s |

Tổng: H PASS 108, NOT_APPLICABLE 36; P MET 108, NOT_MET 18 (UNKNOWN), NOT_APPLICABLE 18 (INFEASIBLE).

- **BASE và MIXED (96 run):** tất cả OPTIMAL với `min_changes_proved`. Thời gian 1,9–38 s ở 10 lớp,
  4,8–28 s ở 20 lớp và 13–26 s ở 40 lớp, thấp hơn nhiều so với bước S cùng dataset (47–185 s, phần lớn
  dừng ở budget). Ô chậm nhất là c10-base-hard/N4, khoảng 38 s.
- **TIGHT (48 run):** profile dựng sát giới hạn. Kết quả: 6 OPTIMAL, 6 FEASIBLE, 18 UNKNOWN (gồm cả 6 ô
  40 lớp ngoài N2) và 18 INFEASIBLE.
- **N3** (thêm và bớt tiết) đổi 1 `new` và 1 `dropped` như thiết kế. `room_only_changes` bằng 0 ở mọi run,
  vì dataset không quản lý phòng.

### 4.3 R2 — `AFTER_QUALITY`, chỉ 10 lớp (48 run)

| Dataset | N1 | N2 | N3 | N4 |
|---|---|---|---|---|
| c10-base-s101-hard | FEA 63/2 53s · FEA 251/2 61s | FEA 117/0 61s · FEA 252/0 61s | FEA 116/0 61s · FEA 256/0 61s | FEA 50/2 52s · FEA 255/2 61s |
| c10-base-s101-soft | FEA 154/1 61s · FEA 257/1 51s | FEA 154/0 61s · FEA 257/0 52s | FEA 153/0 61s · FEA 254/0 50s | FEA 154/2 55s · FEA 259/2 54s |
| c10-mixed-s101-hard | FEA 203/2 61s · FEA 221/2 53s | FEA 228/2 61s · FEA 224/2 61s | FEA 210/0 61s · FEA 216/0 60s | FEA 214/2 61s · FEA 225/2 61s |
| c10-mixed-s101-soft | FEA 40/2 57s · FEA 214/2 60s | FEA 225/0 58s · FEA 225/0 53s | FEA 48/0 51s · FEA 230/0 55s | FEA 224/2 52s · FEA 224/2 61s |
| c10-tight-s101-hard | UNK 60s · UNK 60s | INF 0.3s · INF 0.3s | UNK 60s · UNK 60s | FEA 166/2 60s · FEA 179/2 60s |
| c10-tight-s101-soft | FEA 108/1 61s · FEA 193/1 60s | INF 0.3s · INF 0.3s | FEA 43/0 60s · FEA 192/0 60s | FEA 178/2 61s · FEA 186/2 60s |

Tổng: H PASS 40, NOT_APPLICABLE 8; P MET 40, NOT_MET 4 (UNKNOWN), NOT_APPLICABLE 4 (INFEASIBLE). Không
run nào có `min_changes_proved`. Ở tầng chất lượng, mọi run có lịch đều chạy tới gần budget 60 s.

So sánh cặp cùng input và cùng hint (40 cặp R1/R2 đều có lịch; điểm P1–P3 so theo thứ tự từ điển,
nhỏ hơn là tốt hơn):

- Điểm R2 tốt hơn R1 ở 33 cặp và kém hơn ở 7 cặp: c10-base-soft N1–N3 không hint; c10-tight-hard N4 cả
  hai; c10-mixed-soft N2 cả hai. Ví dụ c10-base-soft/N1 không hint: R1 `[46,146,209]`, R2
  `[199,327,125]`. Nguyên nhân: R2 không chứng minh được tối ưu trong budget nên điểm phụ thuộc lời giải
  tìm được.
- R2 đổi nhiều hơn hẳn: 40–259 tiết, so với 0–31 ở R1.
- Có hint thì R2 thường đổi ít hơn: ví dụ c10-base-hard/N1 đổi 63 tiết có hint, 251 tiết không hint.

### 4.4 Hint (96 cặp R1 + R2)

| Nhóm | Quan sát |
|---|---|
| R1 (72 cặp) | Cùng status ở 72/72. Cùng số thay đổi ở 71/72; cặp còn lại là c10-tight-hard/N3 (FEASIBLE, 22 và 17). Ở 51 cặp cùng OPTIMAL, tỷ lệ thời gian hint/không hint là 0,77–1,28, trung vị 1,0 |
| R2 (24 cặp) | Cùng status ở 24/24. Số thay đổi khác nhau ở 18 cặp, thường ít hơn khi có hint (xem 4.3) |

Với `BEFORE_QUALITY`, hint không thay đổi kết quả hay thời gian theo cách quan sát được ở dữ liệu này.

### 4.5 X — explain (36 run + 22 explain theo sau)

| Phần | Run | Kết quả | Thời gian |
|---|---:|---|---|
| UNSAT_CAPACITY 10 lớp (MODEL, FULL) | 12 | `PRECHECK_PROOF`, 0 lời gọi solver | 0,3 s |
| UNSAT_CAPACITY 20 lớp | 12 | `PRECHECK_PROOF` | 0,4–0,5 s |
| UNSAT_CAPACITY 40 lớp | 12 | `PRECHECK_PROOF` | 0,8–0,9 s |
| Theo sau 20 repair INFEASIBLE trên input `EXPECTED_INFEASIBLE` (core `prepare` báo `RESOURCE_CAPACITY` trong 0,3–0,8 s) | 20 | `PRECHECK_PROOF` | 0,08–0,64 s |
| Theo sau 2 repair INFEASIBLE trên c20-tight-soft/N4 (`GROUND_TRUTH_UNKNOWN`; solver trả INFEASIBLE trong khoảng 0,6 s, launch-to-exit 0,8–0,9 s) | 2 | `CORE_SUBSET` FULL, 8 nhóm (4 DEMAND, 2 LOCK, `TEACHER_AVAILABILITY` và `TEACHER_OCCUPANCY` của T004), `minimal_proved` | 25–26 s, 13 lời gọi solver |

Tất cả H PASS và P MET; `check-explanation` độc lập OK. Đây là lần đầu đường `CORE_SUBSET` chạy ở quy
mô 20 lớp. Đúng như C8 dự kiến, nó chỉ xuất hiện vì một input nhiễu tình cờ sinh ra bài loại này.

### 4.6 Nhãn input nhiễu

8/72 input nhiễu có nhãn `EXPECTED_INFEASIBLE`, tất cả thuộc TIGHT: N2 ở cả 6 dataset TIGHT, N1 ở
c20-tight hard và soft. Repair trên cả 8 input (20 run R1/R2) trả INFEASIBLE, khớp nhãn. 64 input còn lại
là `GROUND_TRUTH_UNKNOWN`. Trong số này, 1 input (c20-tight-soft/N4) được chứng minh vô nghiệm (4.5);
những input khác hoặc có lịch, hoặc UNKNOWN.

### 4.7 Tài nguyên

Peak RSS cao nhất: S 397/502/610 MiB, R 626/527/580 MiB, X 43/53/73 MiB (10/20/40 lớp). Tất cả dưới
target 1/2/4 GiB. Không có watchdog stop: mọi UNKNOWN dừng theo `--time-limit`, khoảng budget + 0,3 s.

## 5. Kết luận theo §4 của kế hoạch

| Trục | Kết luận |
|---|---|
| H | **PASS** trên mọi lịch: 166/166 (18 S + 148 R) qua kiểm độc lập. INFEASIBLE chỉ xuất hiện trên input đã có hoặc vừa nhận chứng minh vô nghiệm được kiểm độc lập; không có INFEASIBLE trên input có lịch đã biết |
| P (R1, mức campaign) | **NOT_MET**: 18 run UNKNOWN, ở c10-tight-hard/N1, c20-tight-hard/N3–N4 và c40-tight (6 ô). Nếu chỉ tính BASE/MIXED thì 96/96 MET |
| P (R2) | 40 MET, 4 UNKNOWN (c10-tight-hard N1, N3) |
| C | Xem 4.2. `BEFORE_QUALITY` cho thay đổi nhỏ nhất đã chứng minh ở mọi run OPTIMAL |
| Q | **REVIEW_REQUIRED.** Vector P1–P3 được ghi cho mọi lịch; không có nhãn chấp nhận |
| X | 36/36 UNSAT và 22/22 explain theo sau đều kết luận được và kiểm độc lập OK |

Điều kiện §10 của đặc tả gốc cho Phase 3 là "benchmark có số liệu thực, validator pass trên mọi nghiệm".
Campaign này cung cấp số đo thực trên dữ liệu synthetic, và mọi nghiệm đều pass validator độc lập. **Người
dùng duyệt Phase 3 Done (P3-11) ngày 2026-11-07**, ở mức mốc kỹ thuật synthetic; xem mục "Quyết định Done"
trong [đặc tả Phase 3](superpowers/specs/2026-11-05-phase-3-repair-diagnostics-design.md). Trước khi dùng
repair với dữ liệu thật vẫn cần review người thứ hai cho contract repair (P3-12).

## 6. Hạn chế

- n = 1 mỗi ô, một máy, workload không kiểm soát, synthetic s101. Không P95/SLA, không Windows.
- TIGHT ở 20/40 lớp phần lớn không có lịch trong budget. Campaign này không phân biệt được "vô nghiệm"
  với "chưa tìm được lịch".
- Mọi run R2 đều FEASIBLE: so sánh BEFORE/AFTER phụ thuộc lời giải tìm được trong 60 s, không phải tối
  ưu đã chứng minh.
- Đường `CORE_SUBSET` của explain chỉ có 1 input (2 run) ở 20 lớp, không có ở 40 lớp (C8).
- `evaluate-repair` không tính lại lý do `forced` hay `min_changes_proved`; đó vẫn là claim của solver
  ([báo cáo 3A](phase-3a-report.md)).
- Input nhiễu có trước kiểm `prepare` (sửa ở `67b4502`) chỉ được kiểm lại trên 72 input của linux-01 (báo
  cáo tooling). Input của linux-02 sinh bằng generator đã sửa và không có run nào bị core từ chối.
- Evidence thô (`benchmarks/artifacts/`, gói tar) chỉ có trên máy người dùng.

## 7. Bước sau cần duyệt

- Phase 3 Done đã được duyệt (2026-11-07). Còn hai việc độc lập: quyết định Q của Phase 2 và review
  người thứ hai (P3-12, S3).
- Nếu cần thêm số đo cho TIGHT hoặc AFTER_QUALITY (ví dụ budget dài hơn hoặc nhiều seed), lập kế hoạch
  riêng. Không nới gate của campaign này.
