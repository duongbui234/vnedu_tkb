# Biên bản Q — mẫu C: SOFT, 40 lớp, BASE (c40-base-s103-soft r1)

Trạng thái: **DRAFT — chưa có quyết định.** Theo [kế hoạch duyệt Q](../phase-2a-quality-review-plan.md)
§4(b). Xem [index](README.md).

## Định danh

| Trường | Giá trị |
|---|---|
| Campaign | `phase2-v2-linux-02`, source `7e47f74` (= `src/` của `main` `1c2819f`) |
| Run ID | `primary-c40-base-s103-soft-7b40af013d7706ee17f1f505727ffcb06d9b212190df5a362cc147ff47365e15-w1-s42-r1` |
| Input fingerprint | `ef05bc341d307f2e787a38d0a9bc1b51dc8ede91f3e19e51c435201fe74060d9` |
| `result.json` SHA256 | `1a15a2d6dad840dcc79a1b6c6b72cf8eb394f016cdb43435895a9ee7a2b30b5c` |
| Status / H / P | FEASIBLE / PASS / MET |
| Quy mô | 40 lớp, 60 GV, 1 200 tiết |
| Vector `[P1,P2,P3]` | `[114,446,865]`; witness `[0,0,330]` (WORSE) |
| Repeat khác | r2, r3 cùng `[114,446,865]` |

Đây là lịch có P1 cao nhất trong 162 lịch của campaign.

## Breakdown và mức tập trung

Tham số benchmark (G3, không phải policy trường): S02 ≤ 3 tiết/buổi, S03 ≤ 4 tiết/ngày, S06 ≤ 3 tiết
môn/lớp/ngày, S04 khung tiết 2–4, S09 chuỗi trống tối đa 0, S10 ≥ 1 buổi rảnh, S05 cách ≥ 1 ngày.

| P | Rule | Tổng | Mức tập trung |
|---|---|---:|---|
| 1 | S02 tải/buổi | 76 | 44/60 GV; 63 buổi vượt (50 buổi 4 tiết, 13 buổi 5 tiết); GV cao nhất cộng dồn 4 |
| 1 | S01 tránh ô | 20 | 20/60 GV, mỗi GV 1 tiết |
| 1 | S06 môn/lớp/ngày | 18 | 18 cặp (lớp, môn, ngày) có 4 tiết, ở 13/40 lớp; lớp cao nhất cộng dồn 2 |
| 2 | S05 giãn ngày (`day_gap_shortfall`) | 235 | 122/205 cặp component thiếu; 8 cặp thiếu 6 |
| 2 | S09 chuỗi trống dài nhất vượt giới hạn (cộng dồn theo GV) | 112 | 47/60 GV; tối đa 6 |
| 2 | S03 tải/ngày | 77 | 41 GV, 49 ngày-GV vượt (29 vượt 1, 12 vượt 2, 8 vượt 3 = 7 tiết/ngày); GV cao nhất cộng dồn 4 |
| 2 | S07 ô hạn chế | 21 | 21/60 GV, mỗi GV 1 tiết |
| 2 | S10 buổi rảnh | 1 | 1/43 GV thiếu 1 buổi |
| 3 | S04 ngoài khung tiết 2–4 | 453 | 37,8 % tổng tiết; theo GV min 17 %, median 37 %, max 56 % |
| 3 | S08 tổng tiết trống | 220 | 58/60 GV; tối đa 11 trên một GV |
| 3 | S11 buổi chỉ 1 tiết | 192 | 60/60 GV; tối đa 7 trên một GV |

Ghi chú: ScoreReport có một dòng S06 cho toàn trường (scope rỗng), nên mức theo lớp ở trên là tính lại
từ lịch; tổng tính lại (18) khớp tổng chính thức. Witness cùng input đạt `[0,0,330]`.

## Câu hỏi cho người duyệt

1. **P1 = 114:** 63 buổi GV vượt 3 tiết (13 buổi dạy 5 tiết), 20 GV dạy ở ô xin tránh, 18 lần một lớp
   học 4 tiết cùng môn trong ngày. Có trường hợp nào chấp nhận được không?
2. 8 ngày-GV dạy 7 tiết (giới hạn 4). Đây có nên là hard trong profile/policy thật không?
3. Nếu NOT_ACCEPTED, có cần ghi riêng "search không đạt chất lượng ở 40 lớp trong budget 180 s" như một
   phát hiện cho kế hoạch hiệu năng tiếp theo không?

## Quyết định

| Trường | Nội dung |
|---|---|
| Quyết định | ☐ ACCEPTED ☐ NOT_ACCEPTED |
| Phạm vi | Chỉ synthetic, đúng result hash trên |
| Lý do theo rule | |
| Người duyệt | |
| Ngày | |
