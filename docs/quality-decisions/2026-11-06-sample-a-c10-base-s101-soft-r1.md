# Biên bản Q — mẫu A: SOFT, 10 lớp, BASE (c10-base-s101-soft r1)

Trạng thái: **ĐÃ QUYẾT ĐỊNH 2026-11-07 — ACCEPTED** (chỉ synthetic, đúng result hash). Theo [kế hoạch duyệt Q](../phase-2a-quality-review-plan.md)
§4(b). Xem [index](README.md).

## Định danh

| Trường | Giá trị |
|---|---|
| Campaign | `phase2-v2-linux-02`, source `7e47f74` (= `src/` của `main` `1c2819f`) |
| Run ID | `primary-c10-base-s101-soft-a53d4d10c014c3d240e5b759e5357bb86bed41945186f452d9fd1e7ad0eff1e6-w1-s42-r1` |
| Input fingerprint | `6b0a108dbd035bba5c4056d5587152de3ef29991a22b3db471d6b30912c62958` |
| `result.json` SHA256 | `edf42a0f03aa9968369013d0f58ee2ee6a1a21d788c1fe8f34b63b54b8affa29` |
| Status / H / P | FEASIBLE / PASS / MET |
| Quy mô | 10 lớp, 15 GV, 300 tiết |
| Vector `[P1,P2,P3]` | `[0,106,219]`; witness `[0,0,72]` (WORSE) |
| Repeat khác | r2, r3 cùng `[0,106,219]`; pilot cùng input `[46,146,211]` |

## Breakdown và mức tập trung

Tham số benchmark (G3, không phải policy trường): S02 ≤ 3 tiết/buổi, S03 ≤ 4 tiết/ngày, S06 ≤ 3 tiết
môn/lớp/ngày, S04 khung ưu tiên tiết 2–4, S09 chuỗi trống tối đa 0, S10 ≥ 1 buổi rảnh, S05 cách ≥ 1 ngày.

| P | Rule | Tổng | Mức tập trung |
|---|---|---:|---|
| 1 | S01 tránh ô | 0 | — |
| 1 | S02 tải/buổi | 0 | — |
| 1 | S06 môn/lớp/ngày | 0 | — |
| 2 | S05 giãn ngày (`day_gap_shortfall`) | 49 | 32/71 cặp component thiếu; phân bố thiếu 1: 18, 2: 11, 3: 3 |
| 2 | S09 chuỗi trống dài nhất vượt giới hạn (cộng dồn theo GV) | 41 | 13/15 GV; phân bố 1: 4, 2: 3, 3: 1, 5: 3, 6: 1, 7: 1 |
| 2 | S03 tải/ngày | 10 | 5 GV, 8 ngày-GV vượt (6 ngày vượt 1 tiết, 2 ngày vượt 2); GV cao nhất cộng dồn 4 |
| 2 | S10 buổi rảnh | 3 | 3/11 GV thiếu 1 buổi |
| 2 | S07 ô hạn chế | 3 | 3/15 GV, mỗi GV 1 tiết |
| 3 | S04 ngoài khung tiết 2–4 | 113 | 37,7 % tổng tiết; theo GV min 18 %, median 39 %, max 55 % |
| 3 | S08 tổng tiết trống | 57 | 15/15 GV; tối đa 7 trên một GV |
| 3 | S11 buổi chỉ 1 tiết | 49 | 15/15 GV; tối đa 6 trên một GV |

Đối chiếu: witness cùng input đạt `[0,0,72]`, tức có lịch hard-valid không vi phạm P2 nào.

## Câu hỏi cho người duyệt

1. P1 = 0. Mức P2 trên (một GV có penalty S09 cộng dồn qua các buổi bằng 7; 8 ngày-GV quá tải; 32 cặp component đặt
   quá sát) có chấp nhận được không?
2. Gần 38 % tiết ngoài khung ưu tiên, một GV tới 55 %: chấp nhận được không?
3. Nếu không chấp nhận, rule nào là lý do chính (để đưa vào profile v0)?

## Quyết định

| Trường | Nội dung |
|---|---|
| Quyết định | ☒ ACCEPTED ☐ NOT_ACCEPTED |
| Phạm vi | Chỉ synthetic, đúng result hash trên |
| Lý do theo rule | P1 = 0 (S01, S02, S06 đều 0). Ghi chú cho quality profile v0: P2 (S05 giãn ngày, S09 chuỗi trống, S03 tải/ngày) và mức tập trung S04 theo GV (tới 55 % tiết ngoài khung) cần có giới hạn |
| Người duyệt | Người dùng (duongbui234) |
| Ngày | 2026-11-07 |

Nguyên tắc người duyệt: **P1 > 0 không chấp nhận.**
