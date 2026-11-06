# Biên bản Q — mẫu B: HARD, 40 lớp, BASE (c40-base-s101-hard r1)

Trạng thái: **DRAFT — chưa có quyết định.** Theo [kế hoạch duyệt Q](../phase-2a-quality-review-plan.md)
§4(b). Xem [index](README.md).

## Định danh

| Trường | Giá trị |
|---|---|
| Campaign | `phase2-v2-linux-02`, source `7e47f74` (= `src/` của `main` `1c2819f`) |
| Run ID | `primary-c40-base-s101-hard-7166dccf6154eebfc4129fbf64213ab52a3a8fd72acf3ca3cdbd5a88a3722182-w1-s42-r1` |
| Input fingerprint | `b91db70ed31ba465e262c6b3958eaf89295f45b0b6fd4a8dad73fd22c2ed2b89` |
| `result.json` SHA256 | `bd68de54811d58894349b41d67468fc4cd53eff4470ddf71ec2a76597eb52bcc` |
| Status / H / P | FEASIBLE / PASS / MET |
| Quy mô | 40 lớp, 60 GV, 1 200 tiết |
| Vector `[P1,P2,P3]` | `[21,233,924]`; witness `[0,0,279]` (WORSE) |
| Repeat khác | r2, r3 cùng `[21,233,924]` |

Biến thể HARD: S02 (≤ 3 tiết/buổi), S03 (≤ 4 tiết/ngày), S05 và S06 là ràng buộc cứng, đã được validator
độc lập xác nhận không vi phạm, nên không có trong breakdown dưới đây.

## Breakdown và mức tập trung

Tham số benchmark (G3): S04 khung tiết 2–4, S09 chuỗi trống tối đa 0, S10 ≥ 2 buổi rảnh.

| P | Rule | Tổng | Mức tập trung |
|---|---|---:|---|
| 1 | S01 tránh ô | 21 | 21/60 GV, mỗi GV đúng 1 tiết ở ô xin tránh |
| 2 | S09 chuỗi trống dài nhất vượt giới hạn (cộng dồn theo GV) | 191 | 48/60 GV; 10 GV ≥ 7, tối đa 11 |
| 2 | S07 ô hạn chế | 24 | 24/60 GV, mỗi GV 1 tiết |
| 2 | S10 buổi rảnh | 18 | 16/48 GV thiếu (14 thiếu 1, 2 thiếu 2) |
| 3 | S04 ngoài khung tiết 2–4 | 438 | 36,5 % tổng tiết; theo GV min 15 %, median 35 %, max 67 % |
| 3 | S08 tổng tiết trống | 277 | 58/60 GV; tối đa 11 trên một GV |
| 3 | S11 buổi chỉ 1 tiết | 209 | 60/60 GV; tối đa 7 trên một GV |

Đối chiếu: witness cùng input đạt `[0,0,279]`, nghĩa là có lịch hard-valid không vi phạm S01 nào.

## Câu hỏi cho người duyệt

1. **P1 > 0:** 21 GV mỗi người dạy 1 tiết ở ô đã xin tránh. Có chấp nhận được không, hay P1 > 0 luôn
   là NOT_ACCEPTED?
2. 10 GV có penalty S09 (chuỗi trống dài nhất vượt giới hạn, cộng dồn qua các buổi) ≥ 7; một GV tới 11. Chấp nhận được không?
3. Một GV có 2/3 số tiết ngoài khung ưu tiên. Có cần giới hạn tập trung theo GV không?

## Quyết định

| Trường | Nội dung |
|---|---|
| Quyết định | ☐ ACCEPTED ☐ NOT_ACCEPTED |
| Phạm vi | Chỉ synthetic, đúng result hash trên |
| Lý do theo rule | |
| Người duyệt | |
| Ngày | |
