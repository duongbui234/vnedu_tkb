# Biên bản quyết định chất lượng (trục Q)

Thư mục này lưu các quyết định Q theo phương án (b) của
[kế hoạch duyệt chất lượng](../phase-2a-quality-review-plan.md): mỗi biên bản gắn với **một result
hash**, không áp sang input, repeat hay dataset khác. Biên bản không sửa `case-verdict.json`,
`summary.json` hay báo cáo campaign. Người duyệt được chỉ định là người dùng (Q3); phạm vi mặc định là
**chỉ synthetic**.

| Mẫu | Biên bản | Lịch | Vector | Quyết định |
|---|---|---|---|---|
| A | [2026-11-06-sample-a](2026-11-06-sample-a-c10-base-s101-soft-r1.md) | SOFT 10 lớp BASE | `[0,106,219]` | **ACCEPTED** (2026-11-07) |
| B | [2026-11-06-sample-b](2026-11-06-sample-b-c40-base-s101-hard-r1.md) | HARD 40 lớp BASE | `[21,233,924]` | **NOT_ACCEPTED** (2026-11-07; S01) |
| C | [2026-11-06-sample-c](2026-11-06-sample-c-c40-base-s103-soft-r1.md) | SOFT 40 lớp BASE | `[114,446,865]` | **NOT_ACCEPTED** (2026-11-07; S02, S01, S06, S03) |

**Quyết định ngày 2026-11-07** (người duyệt: Người dùng (duongbui234)). Nguyên tắc: **P1 > 0 không chấp nhận.** Mẫu A được
chấp nhận kèm ghi chú: P2 (S05, S09, S03) và mức tập trung S04 theo GV cần giới hạn trong quality profile
v0. Ba quyết định chỉ áp cho đúng ba result hash. Trục Q của campaign `phase2-v2-linux-02` vẫn là
REVIEW_REQUIRED: harness chưa chấm Q, và profile không áp ngược cho campaign đã chạy.

[Quality profile v0](../quality-profile-v0.md) được duyệt ngày 2026-11-07 từ ba biên bản này: M1–M3 (P1 = 0)
bắt buộc, U1–U6 (P2/P3) chỉ ghi nhận; áp cho campaign tương lai.

## Mẫu tham khảo D (không cần quyết định)

Một lịch tốt hơn witness để làm mốc khi đọc A/B/C. Không có ô quyết định.

- Run `primary-c10-mixed-s101-soft-ae35b0855c30dab2…-w1-s42-r1`, FEASIBLE, 300 tiết, 15 GV.
- `result.json` SHA256 `b93b43618842f133ec31055c8e7c729c533b51e08a018a9bb413f754eb24cec5`.
- Vector `[0,0,42]`; witness `[0,0,72]`.
- P1 = 0 và P2 = 0. P3: S04 18 tiết ngoài khung ưu tiên (6 %, GV cao nhất 11 %); S08 6/15 GV có tiết
  trống, tối đa 3; S11 8/15 GV có buổi chỉ 1 tiết, tối đa 3.
- Hai repeat khác của cùng input cho `[0,0,105]` và `[0,0,38]`.

## Cách số liệu được tạo

- Breakdown theo rule lấy từ `evaluate-score.stdout` đã kiểm độc lập trong lượt campaign
  `phase2-v2-linux-02` (venv không OR-Tools).
- Mức tập trung theo GV/ngày/buổi/lớp được tính lại read-only từ `result.json` và `input.json` bằng một
  script Python stdlib ngoài repo. Tổng tính lại của S02, S03, S04 và S06 **khớp** tổng chính thức ở cả
  bốn mẫu; các rule còn lại lấy trực tiếp từ dòng ScoreReport.
- Evidence local: `benchmarks/artifacts/hard-feasibility-no-lp/` (không có trong clone cloud).

## Cách ghi quyết định

Điền mục "Quyết định" trong từng biên bản: ACCEPTED hoặc NOT_ACCEPTED, phạm vi, lý do theo rule, người
duyệt, ngày. Sau đó cập nhật bảng trên. Một quyết định không biến kết quả benchmark thành PASS của một
ngưỡng; nó là đầu vào để soạn quality profile v0 cho run tương lai.
