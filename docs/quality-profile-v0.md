# Quality profile v0

Ngày 2026-11-07. Trạng thái: **ĐÃ DUYỆT ngày 2026-11-07** (người dùng, PV1–PV5 theo đề xuất, xem §6).
**Profile v0 = M1–M3 bắt buộc; U1–U6 chỉ ghi nhận (report-only).** Có hiệu lực cho campaign tương lai,
được chốt trước khi seal. Chấm vẫn làm tay (PV5).
Đây là bước 2 của §5 trong [kế hoạch duyệt Q](phase-2a-quality-review-plan.md), soạn từ
[ba biên bản Q](quality-decisions/README.md) (A ACCEPTED; B, C NOT_ACCEPTED; nguyên tắc **P1 > 0 không
chấp nhận**).

Lượt soạn chỉ có tài liệu này. Không sửa code, harness hay gate, không chạy solver.

## 1. Phạm vi và ranh giới

- **Chỉ cho campaign tương lai.** Profile được chốt trước khi seal campaign đó, và hash của profile được ghi
  vào plan. Theo §4a của kế hoạch Q, profile **không** dùng để chấm lại `phase2-v2-linux-02`. Bảng đối chiếu
  ở §5 chỉ là thông tin tác động, không phải verdict.
- **Chỉ synthetic.** Mọi ngưỡng ở đây đều là phỏng đoán, vì chưa có dữ liệu hay quy tắc trường thật.
- **Không đổi H/P**, không đổi policy 0.4, không biến soft thành hard.
- **Phải chấm được từ dữ liệu sẵn có.** Mỗi mục kiểm được từ các dòng ScoreReport 1.2 (một dòng cho mỗi GV,
  mỗi requirement hoặc toàn trường). Riêng S04 cần thêm tải tuần của GV, lấy từ input.
- **Chấm Q tự động cần thay đổi harness** (đọc profile, chấm theo từng dòng, ghi hash). Đó là việc code
  riêng, cần ủy quyền riêng (§4a của kế hoạch Q).

## 2. Kết quả chấm

| Kết quả | Khi nào |
|---|---|
| `ACCEPTED` | Có lịch hard-valid, và mọi mục của profile nằm trong giới hạn |
| `NOT_ACCEPTED` | Có lịch, nhưng ít nhất một mục vượt giới hạn; ghi rõ mục vượt và số dòng vượt |
| `NO_SCHEDULE` | Không có lịch (UNKNOWN, INFEASIBLE, giới hạn tài nguyên) |

Ngưỡng không có dung sai; FEASIBLE và OPTIMAL được chấm như nhau. Một lịch NOT_ACCEPTED vẫn giữ nguyên H/P.

## 3. Mục bắt buộc (từ nguyên tắc đã duyệt)

| Mục | Rule | Code ScoreReport | Dòng | Giới hạn mỗi dòng |
|---|---|---|---|---:|
| M1 | S01 tránh ô | `TEACHER_AVOID_SLOTS` | mỗi GV | 0 |
| M2 | S02 tải/buổi | `TEACHER_MAX_PERIODS_PER_SESSION` | mỗi GV | 0 |
| M3 | S06 môn/lớp/ngày | `CLASS_SUBJECT_MAX_PERIODS_PER_DAY` | toàn trường | 0 |

Ba mục này tương đương "P1 = 0" của policy 0.4. Ở biến thể HARD, S02 và S06 là ràng buộc cứng nên luôn
bằng 0.

## 4. Mục ghi nhận cho P2/P3 (report-only theo PV1)

Đây là các ghi chú của biên bản A, cộng với hai rule P2 còn lại. **Giá trị được chốt trước khi tính tác
động ở §5**, theo nguyên tắc của acceptance v2 là không chọn ngưỡng vừa khít kết quả đã thấy. Giá trị là
số tròn, đặt từ ý nghĩa của rule:

| Mục | Rule (P) | Code | Dòng | Giới hạn | Lý do đặt giá trị |
|---|---|---|---|---:|---|
| U1 | S03 tải/ngày (P2) | `TEACHER_MAX_PERIODS_PER_DAY` | mỗi GV | ≤ 2 tiết vượt/tuần | Tối đa hai ngày vượt 1 tiết, hoặc một ngày vượt 2. Ngày 7 tiết (vượt 3) như mẫu C thì không đạt |
| U2 | S09 chuỗi trống (P2) | `TEACHER_MAX_GAP_RUN` | mỗi GV | ≤ 3 | Cỡ một tiết trống thừa mỗi hai ngày |
| U3 | S05 giãn ngày (P2) | `SUBJECT_COMPONENT_DAY_SPREAD` | mỗi requirement | ≤ 2 | Mỗi môn thiếu giãn cách tổng cộng không quá 2 ngày |
| U4 | S07 ô hạn chế (P2) | `TEACHER_RESTRICTED_SLOTS` | mỗi GV | ≤ 1 | Tối đa một tiết ở ô hạn chế |
| U5 | S10 buổi rảnh (P2) | `TEACHER_MIN_FREE_TIME` | mỗi GV | ≤ 1 | Thiếu tối đa một buổi rảnh |
| U6 | S04 khung tiết (P3) | `TEACHER_PREFERRED_PERIOD_WINDOW` | mỗi GV | ≤ 50 % tải tuần của GV | Không quá nửa số tiết của một GV nằm ngoài khung. Cần tải tuần từ input |

S08 (tổng tiết trống) và S11 (buổi một tiết) chỉ được ghi nhận, không có giới hạn trong v0, vì chưa biên
bản nào nêu chúng là lý do.

**Giới hạn của cách biểu diễn:** ScoreReport chỉ có tổng theo dòng, chưa có chi tiết theo ngày hay buổi.
Vì vậy "không ngày nào quá N tiết" chỉ chặn được gián tiếp: U1 ≤ 2 cho phép tối đa 6 tiết/ngày với giới
hạn 4. Muốn có giới hạn theo ngày cần một ScoreReport mới (version mới, cần ủy quyền riêng).

## 5. Đối chiếu với 162 lịch của `phase2-v2-linux-02` (thông tin, không phải verdict)

Đọc chỉ đọc từ `independent-checks/*/evaluate-score.stdout` của campaign. Tải tuần của GV lấy từ input
trong bundle v2 sinh lại; fingerprint của 162 input khớp ScoreReport (0 lệch). Script nằm ngoài repo.

| Biến thể / lớp | Lịch | Đạt M1–M3 (P1 = 0) | Đạt M1–M3 + U1–U6 | Mục U làm trượt nhiều nhất (số lịch) |
|---|---:|---:|---:|---|
| SOFT 10 | 27 | 27 | 9 | U1 12, U3 12, U2 9, U6 9 |
| SOFT 20 | 27 | 16 | 0 | U3 24, U2 18, U1 17 |
| SOFT 40 | 27 | 0 | 0 | U3 27, U1 24, U2 18, U5 18 |
| HARD 10 | 27 | 20 | 18 | U2 9, U5 6, U6 3 |
| HARD 20 | 27 | 6 | 6 | U2 12, U6 9 |
| HARD 40 | 27 | 3 | 0 | U2 18, U5 15, U6 9 |
| **Tổng** | **162** | **72** | **33** | — |

- **Chỉ M1–M3:** 72/162 đạt, khớp số 90 lịch có P1 > 0 trong kế hoạch Q.
- **Thêm U1–U6:** chỉ 33/162 đạt, và cả 33 đều có P2 = 0 (vector `[0,0,x]`). Trên dữ liệu này, bộ U
  thực tế tương đương "P2 = 0".
- **Với các mẫu đã quyết định:**

| Mẫu | Quyết định đã ghi | Chỉ M1–M3 | M1–M3 + U1–U6 |
|---|---|---|---|
| A `[0,106,219]` | ACCEPTED | Đạt | **Không đạt**: U3 (3 dòng), U2 (5), U1 (1), U6 (2) |
| B `[21,233,924]` | NOT_ACCEPTED | Không đạt (M1) | Không đạt |
| C `[114,446,865]` | NOT_ACCEPTED | Không đạt (M1, M2, M3) | Không đạt |
| D `[0,0,42]` (tham khảo) | — | Đạt | Đạt |

**Mâu thuẫn cần anh/chị quyết định (PV1):** nếu áp U1–U6, mẫu A, đã được duyệt ACCEPTED, sẽ không đạt
profile. Tôi không nới ngưỡng để A đạt, vì như vậy là chọn ngưỡng vừa khít kết quả. Có hai cách nhất quán:

- **Phương án 1 — v0 = M1–M3; U1–U6 chỉ ghi nhận (report-only).** Khớp cả ba biên bản. P2/P3 được báo
  cáo theo dòng nhưng không làm trượt. Profile yếu hơn: lịch như A vẫn ACCEPTED.
- **Phương án 2 — v0 = M1–M3 + U1–U6.** Profile chặt hơn quyết định A. Chỉ áp cho run tương lai;
  biên bản A vẫn giữ nguyên, vì biên bản gắn với result hash. Ghi chú "cần giới hạn" của biên bản A trở
  thành giới hạn thật.

## 6. Quyết định cần duyệt

- [x] **PV1 — Phạm vi v0:** Phương án 1 (chỉ P1, U1–U6 ghi nhận) hay Phương án 2 (P1 + U1–U6)?
  *(Đề xuất: Phương án 1 cho v0, vì khớp với mọi quyết định đã ghi và không cần thêm phỏng đoán. U1–U6 vẫn
  được báo cáo theo dòng, để v1 có số liệu khi có dữ liệu trường thật.)*
- [x] **PV2 — Giá trị U1–U6** (chỉ áp nếu chọn Phương án 2 hoặc để ghi nhận): giữ các giá trị ở §4, hay
  anh/chị đặt giá trị khác? Đặt lại sau khi đã xem §5 phải ghi rõ là đã biết tác động.
- [x] **PV3 — S04 theo tỷ lệ tải** cần thêm tải tuần từ input khi chấm. Chấp nhận, hay đổi U6 sang số
  tiết tuyệt đối?
- [x] **PV4 — Lưu trữ và version:** profile được duyệt sẽ là file máy đọc được
  (`benchmarks/quality-profiles/v0.json`) cộng với tài liệu này. SHA256 của file được ghi vào plan và seal
  của campaign dùng nó. Mọi thay đổi tạo version mới (v0.1, v1…).
- [x] **PV5 — Bước sau:** sau khi duyệt, lập kế hoạch thay đổi harness để chấm Q theo profile (code
  riêng, TDD, cần ủy quyền), hay giữ chấm tay cho tới khi có kế hoạch chất lượng search (S1)?

### Quyết định ngày 2026-11-07 (người dùng)

| Mục | Quyết định |
|---|---|
| PV1 | **Phương án 1.** v0 chỉ có M1–M3. U1–U6 được báo cáo theo dòng nhưng không làm trượt. Profile khớp cả ba biên bản A/B/C |
| PV2 | Giữ giá trị U1–U6 ở §4 (dùng để ghi nhận) |
| PV3 | U6 tính theo tỷ lệ tải tuần của GV, lấy từ input |
| PV4 | Bản máy đọc được `benchmarks/quality-profiles/v0.json` chỉ được tạo cùng lượt thay đổi harness đã được ủy quyền. SHA256 của file đó được ghi vào plan và seal của campaign dùng nó. Tài liệu này là nguồn của v0 |
| PV5 | Giữ chấm tay cho tới khi có kế hoạch chất lượng search (S1). Chưa lập kế hoạch harness |

Chấm theo v0 trên một campaign tương lai (làm tay): lịch đạt M1–M3 → `ACCEPTED`, kèm bảng U1–U6 ghi nhận;
lịch vượt M1–M3 → `NOT_ACCEPTED`, ghi rule vượt; không có lịch → `NO_SCHEDULE`. Trục Q của
`phase2-v2-linux-02` vẫn là REVIEW_REQUIRED (§1).

## 7. Kiểm tra khi soạn

- Rule, code, priority và đơn vị lấy từ 162 ScoreReport của campaign: 11 code, khớp catalog S01–S11
  policy 0.4.
- Ngưỡng U1–U6 được ghi vào script trước khi tính bảng §5.
- Đối chiếu trên ba mẫu khớp breakdown trong biên bản: A có S03 tối đa 4 trên một GV, S09 tối đa 7, S04
  tới 55 %; C có S03 dòng cao nhất 4, nhưng ngày 7 tiết nằm trong tổng của GV.
- Không chạy test hay solver; không sửa file nào khác.
