# Phase 2A — kế hoạch duyệt chất lượng (trục Q)

Ngày 2026-11-06. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-06** (Q1–Q4 ở §6). Bước 1 của §5 đã xong: ba biên bản
mẫu A/B/C trong [`quality-decisions/`](quality-decisions/README.md) có quyết định ngày 2026-11-07. Bước 2
cũng đã xong: [quality profile v0](quality-profile-v0.md) được duyệt ngày 2026-11-07, với P1 = 0 bắt buộc
và P2/P3 chỉ ghi nhận. Bước 3 (thay đổi harness) chưa lập kế hoạch. Áp dụng
[acceptance v2](phase-2a-acceptance-v2-draft.md) §3.2 cho kết quả campaign `phase2-v2-linux-02`
([báo cáo nghiệm thu Linux](phase-2a-linux-acceptance-report.md)), source `1c2819f` trên `main`
(cây `src/` trùng `7e47f74`).

Tài liệu này **chỉ đề xuất cách duyệt Q**. Nó không đặt ngưỡng, không chấm ACCEPTED hay NOT_ACCEPTED cho
bất kỳ lịch nào, không sửa harness/gate/evidence, và không chạy solver hay campaign. Đến khi có một quyết
định được ghi theo §5 hoặc §6, mọi lịch vẫn là **REVIEW_REQUIRED**.

## 1. Vì sao Q chưa thể tự đóng

- Acceptance v2 yêu cầu một trong hai căn cứ: **(a) quality profile đã chốt trước khi dùng làm gate**,
  hoặc **(b) người có thẩm quyền duyệt kết quả cụ thể theo result hash**. Campaign v2 chạy với G7 (chưa có
  profile), nên chưa có căn cứ nào.
- Priority và weight của dataset là **cấu hình benchmark** (G3: P1 S01/S02/S06; P2 S03/S05/S07/S09/S10;
  P3 S04/S08/S11; weight 1), không phải policy của trường. Dataset là synthetic. Vì vậy một quyết định Q
  trên các lịch này chỉ có nghĩa **trong phạm vi synthetic**; nó không chứng nhận lịch thật.
- Một profile tạo ra **sau** khi đã xem kết quả chỉ được dùng làm gate cho run tương lai, không được dùng
  để gọi các kết quả hiện có là PASS (acceptance v2 §8).

## 2. Hiện trạng chất lượng của 162 lịch

Kiểm kê chỉ đọc từ `independent-checks/*/evaluate-score.stdout` (ScoreReport 1.2, tính bằng venv không
OR-Tools) và `baseline_score` trong manifest dataset. Vector là `[P1, P2, P3]`, so theo thứ tự từ điển,
không cộng các tier.

| Biến thể | Lớp | Lịch | Có P1 > 0 | P1 | P2 | P3 | Witness P1 / P2 / P3 | So witness |
|---|---:|---:|---:|---|---|---|---|---|
| SOFT | 10 | 27 | 0 | 0 | 0–129 | 32–219 | 0 / 0–83 / 61–85 | BETTER 8, WORSE 19 |
| SOFT | 20 | 27 | 11 | 0–94 | 148–308 | 134–457 | 0 / 0–166 / 126–165 | WORSE 27 |
| SOFT | 40 | 27 | **27** | 12–114 | 345–641 | 289–865 | 0 / 0–335 / 249–330 | WORSE 27 |
| HARD | 10 | 27 | 7 | 0–7 | 0–71 | 37–250 | 0 / 0 / 61–85 | BETTER 3, EQUAL 9, WORSE 15 |
| HARD | 20 | 27 | 21 | 0–10 | 0–116 | 125–475 | 0 / 0 / 126–165 | WORSE 27 |
| HARD | 40 | 27 | 24 | 0–25 | 26–233 | 265–978 | 0 / 0 / 249–330 | WORSE 27 |

Ở HARD, S02/S03/S05/S06 là hard nên không xuất hiện trong ScoreReport; P1 chỉ còn S01, P2 chỉ còn
S07/S09/S10.

Các quan sát quan trọng cho người duyệt (đây là sự kiện, không phải verdict):

1. **P1 khác 0 ở 90/162 lịch**, trong khi witness của mọi dataset có P1 = 0. Từ 20 lớp trở lên, phần lớn
   lịch còn vi phạm ưu tiên cao nhất (S01 tránh ô, S02 vượt tải/buổi, S06 môn/ngày).
2. Khoảng cách với witness tăng theo quy mô. Ở 10 lớp có 20/54 lịch BETTER hoặc EQUAL witness; ở 20 và
   40 lớp, 108/108 lịch WORSE.
3. Nhiều lịch dừng ở FEASIBLE khi hết budget (153 FEASIBLE, 9 OPTIMAL), nên vector là incumbent tại thời
   điểm dừng, không phải tối ưu.
4. **Lặp lại không luôn cho cùng vector.** 6/54 dataset có repeat khác nhau (ví dụ `c10-mixed-s101-soft`:
   `[0,0,42]`, `[0,0,105]`, `[0,0,38]`). Pilot `c10-base-s101-soft` cho `[46,146,211]`, còn 3 repeat
   primary cùng input cho `[0,106,219]`. Quyết định Q vì vậy phải gắn với **result hash**, không với
   dataset.

## 3. Ba mẫu đề xuất cho phương án (b)

Chọn để phủ ba tình huống: lịch nhỏ điển hình, biến thể HARD quy mô lớn, và lịch xấu nhất về P1. Mỗi mẫu
lấy repeat r1. "Dương" = số dòng rule (theo GV, lớp hoặc cặp component) có penalty > 0 trên tổng số dòng
của rule; "max" = penalty lớn nhất trên một dòng.

### Mẫu A — SOFT, 10 lớp, BASE (lịch nhỏ điển hình, P1 = 0)

- Run `primary-c10-base-s101-soft-a53d4d10…-w1-s42-r1`, status FEASIBLE, 300 tiết, 15 GV.
- Input fingerprint `6b0a108dbd035bba5c4056d5587152de3ef29991a22b3db471d6b30912c62958`.
- `result.json` SHA256 `edf42a0f03aa9968369013d0f58ee2ee6a1a21d788c1fe8f34b63b54b8affa29`.
- Vector `[0,106,219]`; witness `[0,0,72]`.

| P | Rule | Đơn vị | Tổng | Dương | Max |
|---|---|---|---:|---:|---:|
| 1 | S01 TEACHER_AVOID_SLOTS / S02 MAX_PERIODS_PER_SESSION / S06 CLASS_SUBJECT_MAX_PERIODS_PER_DAY | teaching_periods | 0 | 0 | 0 |
| 2 | S05 SUBJECT_COMPONENT_DAY_SPREAD | day_gap_shortfall | 49 | 32/71 | 3 |
| 2 | S09 TEACHER_MAX_GAP_RUN | idle_periods | 41 | 13/15 | 7 |
| 2 | S03 TEACHER_MAX_PERIODS_PER_DAY | teaching_periods | 10 | 5/15 | 4 |
| 2 | S10 TEACHER_MIN_FREE_TIME | free_sessions | 3 | 3/11 | 1 |
| 2 | S07 TEACHER_RESTRICTED_SLOTS | teaching_periods | 3 | 3/15 | 1 |
| 3 | S04 TEACHER_PREFERRED_PERIOD_WINDOW | teaching_periods | 113 | 15/15 | 11 |
| 3 | S08 TEACHER_TOTAL_GAPS | idle_periods | 57 | 15/15 | 7 |
| 3 | S11 TEACHER_SINGLE_PERIOD_SESSION | single_period_sessions | 49 | 15/15 | 6 |

Câu hỏi cho người duyệt: 113/300 tiết (38 %) ngoài khung ưu tiên, một GV có penalty S09 (chuỗi trống
dài nhất vượt giới hạn, cộng dồn qua các buổi) bằng 7, một GV vượt tải ngày cộng dồn 4 tiết. Chấp nhận được không?

### Mẫu B — HARD, 40 lớp, BASE (biến thể hard, quy mô lớn)

- Run `primary-c40-base-s101-hard-7166dccf…-w1-s42-r1`, status FEASIBLE, 1 200 tiết, 60 GV.
- Input fingerprint `b91db70ed31ba465e262c6b3958eaf89295f45b0b6fd4a8dad73fd22c2ed2b89`.
- `result.json` SHA256 `bd68de54811d58894349b41d67468fc4cd53eff4470ddf71ec2a76597eb52bcc`.
- Vector `[21,233,924]`; witness `[0,0,279]`.

| P | Rule | Đơn vị | Tổng | Dương | Max |
|---|---|---|---:|---:|---:|
| 1 | S01 TEACHER_AVOID_SLOTS | teaching_periods | 21 | 21/60 | 1 |
| 2 | S09 TEACHER_MAX_GAP_RUN | idle_periods | 191 | 48/60 | 11 |
| 2 | S07 TEACHER_RESTRICTED_SLOTS | teaching_periods | 24 | 24/60 | 1 |
| 2 | S10 TEACHER_MIN_FREE_TIME | free_sessions | 18 | 16/48 | 2 |
| 3 | S04 TEACHER_PREFERRED_PERIOD_WINDOW | teaching_periods | 438 | 60/60 | 12 |
| 3 | S08 TEACHER_TOTAL_GAPS | idle_periods | 277 | 58/60 | 11 |
| 3 | S11 TEACHER_SINGLE_PERIOD_SESSION | single_period_sessions | 209 | 60/60 | 7 |

Câu hỏi cho người duyệt: 21 GV mỗi người dạy 1 tiết ở ô xin tránh (P1). Chấp nhận được không, hay P1 > 0
là không chấp nhận?

### Mẫu C — SOFT, 40 lớp, BASE (P1 cao nhất)

- Run `primary-c40-base-s103-soft-7b40af01…-w1-s42-r1`, status FEASIBLE, 1 200 tiết, 60 GV.
- Input fingerprint `ef05bc341d307f2e787a38d0a9bc1b51dc8ede91f3e19e51c435201fe74060d9`.
- `result.json` SHA256 `1a15a2d6dad840dcc79a1b6c6b72cf8eb394f016cdb43435895a9ee7a2b30b5c`.
- Vector `[114,446,865]`; witness `[0,0,330]`.

| P | Rule | Đơn vị | Tổng | Dương | Max |
|---|---|---|---:|---:|---:|
| 1 | S02 TEACHER_MAX_PERIODS_PER_SESSION | teaching_periods | 76 | 44/60 | 4 |
| 1 | S01 TEACHER_AVOID_SLOTS | teaching_periods | 20 | 20/60 | 1 |
| 1 | S06 CLASS_SUBJECT_MAX_PERIODS_PER_DAY | teaching_periods | 18 | 1/1 | 18 |
| 2 | S05 SUBJECT_COMPONENT_DAY_SPREAD | day_gap_shortfall | 235 | 122/205 | 6 |
| 2 | S09 TEACHER_MAX_GAP_RUN | idle_periods | 112 | 47/60 | 6 |
| 2 | S03 TEACHER_MAX_PERIODS_PER_DAY | teaching_periods | 77 | 41/60 | 4 |
| 2 | S07 TEACHER_RESTRICTED_SLOTS | teaching_periods | 21 | 21/60 | 1 |
| 2 | S10 TEACHER_MIN_FREE_TIME | free_sessions | 1 | 1/43 | 1 |
| 3 | S04 TEACHER_PREFERRED_PERIOD_WINDOW | teaching_periods | 453 | 60/60 | 12 |
| 3 | S08 TEACHER_TOTAL_GAPS | idle_periods | 220 | 58/60 | 11 |
| 3 | S11 TEACHER_SINGLE_PERIOD_SESSION | single_period_sessions | 192 | 60/60 | 7 |

S06 có một dòng rule cho toàn trường (scope rỗng), nên "1/1, max 18" là tổng 18 tiết vượt giới hạn
môn/ngày cộng trên mọi lớp, chưa tách theo lớp. Người duyệt cần xem breakdown theo lớp/ngày từ lịch nếu
muốn đánh giá mức tập trung.

Mẫu tham khảo tùy chọn: `c10-mixed-s101-soft` r1 `[0,0,42]` tốt hơn witness `[0,0,72]`, để có một lịch
"tốt" làm mốc so sánh.

## 4. Hai phương án

### Phương án (a) — quality profile cho run tương lai

Một profile là tài liệu có version, chốt **trước khi seal** một campaign mới. Mỗi mục gồm:

- rule (S01–S11), scope (toàn trường, nhóm GV, lớp), đơn vị theo ScoreReport;
- giới hạn **tổng** (ví dụ tổng S01 ≤ x tiết) và giới hạn **tập trung** (ví dụ ≤ y tiết vi phạm trên một
  GV, một ngày hoặc một buổi), vì cùng một tổng có thể rải đều hoặc dồn vào một người;
- priority áp dụng, người duyệt, ngày duyệt, SHA256 của profile.

Kết quả chấm: ACCEPTED khi mọi mục trong giới hạn; NOT_ACCEPTED khi vượt; NO_SCHEDULE khi không có lịch.

Hệ quả triển khai: harness v2 hiện chỉ biết REVIEW_REQUIRED, nên cần một thay đổi tooling (đọc profile,
chấm theo breakdown từng dòng, ghi profile hash vào plan/seal) cùng regression. Đó là **công việc code
riêng, cần ủy quyền riêng**; kế hoạch này không thực hiện. Profile không thay đổi H/P và không được dùng
lại cho kết quả của `phase2-v2-linux-02`.

Điểm yếu: chưa có dữ liệu trường thật, nên mọi ngưỡng hôm nay đều là phỏng đoán. Acceptance v2 cấm chọn
ngưỡng vừa khít kết quả đã thấy.

### Phương án (b) — duyệt kết quả cụ thể theo result hash

Người có thẩm quyền xem breakdown ở §3 (và lịch đầy đủ nếu cần), rồi ghi một **biên bản quyết định** cho
từng result hash:

| Trường | Nội dung |
|---|---|
| Run ID, input fingerprint, `result.json` SHA256 | Như §3 |
| Quyết định | ACCEPTED hoặc NOT_ACCEPTED |
| Phạm vi | Ví dụ: "synthetic, minh họa cách duyệt; không dùng cho trường thật" |
| Lý do | Rule nào chấp nhận được, rule nào không, kèm số liệu |
| Người duyệt, ngày | — |

Biên bản được lưu ở `docs/quality-decisions/` (đề xuất). Nó không sửa `case-verdict.json`, `summary.json`
hay báo cáo campaign, và không áp sang input, repeat hay dataset khác.

Ưu điểm: dùng được ngay và không cần đổi code. Nhược điểm: mỗi quyết định chỉ đúng cho một hash, nên
không phải gate cho run sau.

## 5. Đề xuất

Làm **(b) trước, dùng kết quả để soạn (a)**:

1. Người dùng (hoặc người có thẩm quyền nghiệp vụ được chỉ định) duyệt ba mẫu A/B/C theo §4(b). Câu hỏi
   then chốt: **P1 > 0 có bao giờ chấp nhận được không**, và giới hạn tập trung theo GV là bao nhiêu.
2. Từ lý do trong ba biên bản, soạn bản nháp quality profile v0 (§4a). Profile v0 chỉ có hiệu lực cho
   campaign **tương lai** và phải chốt trước seal.
3. Chỉ khi có profile v0 đã duyệt mới lập kế hoạch thay đổi harness để chấm ACCEPTED/NOT_ACCEPTED.

Lưu ý: nếu câu trả lời ở bước 1 là "P1 > 0 không chấp nhận được", thì 90/162 lịch hiện có sẽ là
NOT_ACCEPTED theo cùng lý do khi được duyệt, đặc biệt toàn bộ SOFT 40 lớp. Đó là tín hiệu về chất lượng
search trong budget hiện tại. Nó không đổi H/P đã đạt, và không cho phép nới budget hay hard để cải thiện
Q nếu không có kế hoạch riêng được duyệt.

## 6. Quyết định cần duyệt

- [x] **Q1** — (b) trước rồi (a), như §5.
- [x] **Q2** — Ba mẫu A/B/C ở §3, thêm mẫu tham khảo `c10-mixed-s101-soft` r1 (không cần quyết định).
- [x] **Q3** — Người duyệt là người dùng; phạm vi mặc định "chỉ synthetic".
- [x] **Q4** — Biên bản lưu ở `docs/quality-decisions/`.

Duyệt tài liệu này **không** phải ghi quyết định Q cho mẫu nào, và không cho phép sửa harness hay chạy run
mới.

## 7. Kiểm tra khi soạn

- Chỉ đọc evidence local `benchmarks/artifacts/hard-feasibility-no-lp/` (campaign-02,
  independent-checks, bundle manifest) bằng một script Python stdlib trong scratchpad, ngoài repo. Không
  gọi solver, `validate-schedule` hay `evaluate-score`.
- Số liệu §2/§3 lấy trực tiếp từ ScoreReport đã kiểm độc lập trong lượt campaign. SHA256 của
  `result.json` tính lại trong lượt này.
- Không sửa code, gate, plan hoặc evidence; không commit.
