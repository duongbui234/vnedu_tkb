# Phase 3 — đặc tả repair, chẩn đoán vô nghiệm và benchmark

Ngày 2026-11-05. Trạng thái: **P3-1 đến P3-12 ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT theo đề xuất ngày 2026-11-05. **Phase 3 Done (P3-11): người dùng duyệt ngày 2026-11-07**, ở mức mốc kỹ thuật trên dữ liệu synthetic (xem P3-11 và mục "Quyết định Done" ở cuối).** Runbook D/E/F đã ghim commit `86f624d`.

- **3A:** triển khai và commit, duyệt ngày 2026-11-05 — [báo cáo 3A](../../phase-3a-report.md).
- **3B:** triển khai, commit, tự rà soát và kiểm installed wheel ngày 2026-11-06 —
  [đặc tả 3B](2026-11-06-phase-3b-infeasibility-diagnostics-design.md), [báo cáo 3B](../../phase-3b-report.md).
- **3C:** campaign `phase3c-linux-02` xong ngày 2026-11-07 —
  [kế hoạch 3C](../plans/2026-11-06-phase-3c-repair-benchmark.md), [báo cáo 3C](../../phase-3c-report.md).

Base
`86f624d` trên `main`. Kế hoạch triển khai lát đầu (3A):
[2026-11-05-phase-3a-repair.md](../plans/2026-11-05-phase-3a-repair.md).

Nguồn yêu cầu: [đặc tả Core First](../../VNEDU_TKB_CORE_FIRST_CODEX.md):

- §4.3: khi repair, tối thiểu hóa số occurrence bị thay đổi;
- §6: chẩn đoán vô nghiệm;
- §7: repair và khóa tiết;
- §9.2 và §9.4: test và benchmark;
- §10: điều kiện Done của Phase 3 là repair test pass, benchmark có số liệu thực, validator độc lập pass
  trên mọi nghiệm.

Hiện trạng: [báo cáo dự án](../../project-status-report.md).

Tài liệu chỉ là đặc tả. Lượt soạn không sửa `src/`, `tests/` hay `benchmarks/`, không chạy solver hay
campaign, không commit hay push. Mọi lựa chọn dưới đây là **đề xuất để duyệt**, không phải quy tắc của
trường.

## 1. Mục tiêu và phạm vi

Phase 3 chia thành ba lát, mỗi lát đi qua đặc tả → kế hoạch → TDD → rà soát như các mốc trước:

| Lát | Nội dung | Mức chi tiết trong tài liệu này |
|---|---|---|
| **3A — Repair** | Xếp lại khi dữ liệu đổi, giữ lịch cũ nhiều nhất có thể; giới hạn số thay đổi; vùng được phép thay đổi | Đặc tả đầy đủ + kế hoạch task |
| **3B — Chẩn đoán vô nghiệm** | Khi INFEASIBLE, chỉ ra một tập nhóm ràng buộc xung đột, có bằng chứng | Thiết kế mức nguyên tắc; đặc tả chi tiết sau 3A |
| **3C — Benchmark repair** | Đo repair trên dữ liệu synthetic có nhiễu, trên máy Linux | Thiết kế mức nguyên tắc; sau campaign Phase 2 v2 |

**Ngoài phạm vi Phase 3:**

- UI, SQLite, vnEdu adapter, installer, Windows (Phase 4);
- đồng giảng, lớp ghép, tuần A/B, block dài hơn 2 tiết;
- S12;
- hard mode cho S07–S11;
- tối ưu hiệu năng tổng quát cho `solve()` (theo S1, chờ số đo Phase 2 v2).

**Bất biến:**

- `solve()`, mọi contract hiện có, fingerprint, output 1.1–1.5 và ScoreReport 1.0–1.2 **không đổi**.
  Repair là đường mới, có contract riêng.
- Validator độc lập vẫn là cổng duy nhất cho `valid_schedule=true`.
- Mọi phép đếm thay đổi phải có evaluator độc lập: không import compiler hay solver.
- Không có giá trị mặc định ngầm. Mọi tham số repair (thứ tự ưu tiên, giới hạn, vùng) do request khai báo
  tường minh.

## 2. 3A — Repair

### 2.1 Khái niệm

- **Lịch trước (previous schedule):** tập assignment `(occurrence_id, slot_id, room_id?)` mà trường đang
  dùng. Có thể là kết quả `solve`/`repair` trước đó, hoặc lịch nhập tay.
- **Input mới:** một `ScheduleInput` hợp lệ như hiện nay, đã phản ánh thay đổi: GV bận thêm, đổi phân
  công, thêm hoặc bớt tiết, khóa mới…
- **Ghép occurrence:** theo `occurrence_id`. Phase 1 đã bảo đảm ID ổn định dạng `REQ::ordinal`. Không suy
  luận ghép bằng tên môn hay GV.

Mỗi occurrence của input mới thuộc đúng một nhóm:

| Nhóm | Định nghĩa | Tính vào số thay đổi? |
|---|---|---|
| `MATCHED` | Có trong lịch trước | Có, nếu `(slot, room)` mới khác lịch trước |
| `MATCHED_TARGET_INVALID` | Có trong lịch trước, nhưng vị trí cũ không còn hợp lệ một mình (slot hoặc phòng ngoài availability, calendar, phòng, hard rule hay khóa) | Luôn là 1 thay đổi bắt buộc; được báo trong diagnostics |
| `NEW` | Không có trong lịch trước | Không |

Occurrence của lịch trước không còn trong input mới → `DROPPED`, chỉ báo cáo.

Thay đổi giáo viên của một requirement nhưng giữ ID vẫn là `MATCHED`: giữ slot cũ nếu GV mới dạy được ở
đó.

### 2.2 Contract (P3-2, P3-3, P3-4)

Ba file JSON riêng, mỗi file có `schema_version`; **không** sửa `ScheduleInput`:

1. **`PreviousSchedule` 1.0:**
   - `assignments`: theo shape `ScheduleAssignment` hiện có;
   - `source_input_fingerprint`: tùy chọn, ghi để truy vết.

   CLI cũng nhận trực tiếp một `ScheduleResult` 1.1–1.5 có `valid_schedule=true`, rồi chuyển sang
   `PreviousSchedule` (P3-3). Trùng occurrence, slot lạ hay phòng lạ → `INPUT_INVALID`.
2. **`RepairRequest` 1.0** (mọi field quan trọng đều bắt buộc, không mặc định):
   - `change_order`: `"BEFORE_QUALITY"` (tối thiểu thay đổi trước, rồi mới P1–P3) hoặc
     `"AFTER_QUALITY"` (giữ tối ưu chất lượng, thay đổi là tiêu chí cuối);
   - `max_changes`: số nguyên ≥ 0 hoặc `null` (không giới hạn), tức giới hạn **cứng** trên số thay đổi;
   - `change_scope`: `null` (mọi occurrence được đổi) hoặc
     `{class_ids, teacher_ids, subject_ids, day_ids}`. Occurrence `MATCHED` nằm **ngoài** scope bị giữ
     nguyên vị trí cũ như một khóa;
   - `use_previous_as_hint`: `true` hoặc `false` (P3-7).
3. **`RepairResult` 1.0:** một envelope bọc kết quả, gồm:
   - `result`: một `ScheduleResult` **đúng version hiện có** theo policy của input (1.1–1.5), không có
     version output mới (P3-4);
   - `previous`: `sha256` của file lịch trước, `source_input_fingerprint`, số assignment;
   - `request`: bản sao `RepairRequest` và hash của nó;
   - `repair`: `RepairReport`, xem §2.4.

### 2.3 Mô hình và giai đoạn giải (P3-5, P3-6)

- Dùng lại model hiện có (placements Boolean). Với mỗi occurrence `MATCHED`, `changed_l = 1 − x[l, p₀]`,
  trong đó `p₀` là placement cũ (slot, và phòng nếu quản lý phòng). Nếu `p₀` không còn trong domain →
  `changed_l = 1` cố định (`MATCHED_TARGET_INVALID`). Thêm số hạng tuyến tính, không thêm cặp hay big-M.
- `max_changes = K` → ràng buộc cứng `Σ changed_l ≤ K`.
- **Vùng thay đổi:** `MATCHED` ngoài scope được cố định ở `p₀` như khóa time+room. Nếu `p₀` không hợp lệ
  thì đó là mâu thuẫn trong request → `INPUT_INVALID / REPAIR_FROZEN_TARGET_INVALID`, liệt kê occurrence.
  Không âm thầm giữ nguyên (§7 của đặc tả gốc).
- Khóa trong input mới luôn thắng lịch trước. Khóa khác vị trí cũ được tính là thay đổi (bắt buộc).
- **Giai đoạn**, dùng chung một budget như `solve()`:
  1. feasibility;
  2. nếu `BEFORE_QUALITY`: tầng thay đổi (min `Σ changed`); chứng minh được tối ưu thì đóng băng giá trị,
     không thì giữ incumbent theo cùng quy tắc tier hiện có;
  3. các tầng P1–P3 như `solve()`;
  4. nếu `AFTER_QUALITY`: tầng thay đổi sau P3.
- Tầng thay đổi có `StageRun` riêng trong `RepairReport`. `quality.optimal_prefix` vẫn chỉ nói về P1–P3.
- **Đơn vị:** một occurrence có slot **hoặc** phòng khác lịch trước = 1 thay đổi. Báo riêng
  `slot_changes` và `room_only_changes`. Tiết đôi tính là 1 (một occurrence). Đơn vị được ghi trong báo
  cáo; không đổi ngầm.

### 2.4 Kết quả và kiểm chứng độc lập

`RepairReport` gồm:

- `change_order`, `max_changes`, `change_scope`;
- các bộ đếm `matched`, `new`, `dropped`, `target_invalid`, `frozen`, `changed`, `slot_changes`,
  `room_only_changes`, `unchanged`;
- danh sách occurrence bị đổi: ID, vị trí cũ, vị trí mới, lý do bắt buộc nếu có;
- `change_stage` (`StageRun`);
- `min_changes_proved: bool`.

**Evaluator độc lập** `evaluate_repair(problem, previous, assignments)`:

- chỉ dùng Python thuần trên ba dữ liệu này, không import compiler, preprocessing hay solver;
- tính lại mọi bộ đếm và danh sách;
- kiểm `max_changes`, và kiểm vùng đóng băng được giữ đúng.

`repair()` chỉ trả lịch khi validator hard PASS, score khớp như `solve()` **và** `evaluate_repair` khớp
`RepairReport`. Lệch → `MODEL_INVALID / REPAIR_REPORT_MISMATCH`, không xuất lịch.

CLI:

- `repair <input> <previous> --request <request> [solver flags] --output <file>`;
- `evaluate-repair <input> <previous> <repair-result>` → `OK`, hoặc `INPUT_INVALID /
  RESULT_REPAIR_MISMATCH` / `STALE_RESULT`. Lệnh này chạy được cả khi không cài OR-Tools.

Mã lỗi mới (đều thuộc `INPUT_INVALID`): `PREVIOUS_SCHEDULE_INVALID`, `REPAIR_REQUEST_INVALID`,
`REPAIR_FROZEN_TARGET_INVALID`. Ngoài ra `INFEASIBLE` khi `max_changes` hoặc vùng đóng băng làm bài toán
vô nghiệm (chỉ khi đã chứng minh); `UNKNOWN` khi hết budget.

### 2.5 Hint (P3-7)

Lịch trước là gợi ý tự nhiên cho CP-SAT (`AddHint`) và có thể giúp tìm nghiệm nhanh. Đây là **tính năng
sản phẩm của repair**, khác với "witness hint" bị cấm trong benchmark `solve()` (CLAUDE.md). Hint không
được thay đổi tính đúng: kết quả vẫn qua validator, evaluator và oracle. Request phải khai báo tường minh
`use_previous_as_hint`. Benchmark 3C báo riêng hai chế độ có và không có hint.

### 2.6 Test bắt buộc (§9.2 của đặc tả gốc)

- Contract: hợp lệ và không hợp lệ cho ba file; nhận `ScheduleResult` làm lịch trước; từ chối field lạ.
- Evaluator: các ca tính tay (đổi slot, chỉ đổi phòng, tiết đôi, `NEW`, `DROPPED`, target invalid, đóng
  băng).
- Pipeline: không có thay đổi dữ liệu → 0 thay đổi và lịch giữ nguyên; GV bận một slot → chỉ đổi số tối
  thiểu; `max_changes` quá nhỏ → INFEASIBLE; vùng đóng băng mâu thuẫn → INPUT_INVALID; khóa mới thắng
  lịch trước; `BEFORE` khác `AFTER` trên fixture có đánh đổi tính tay; compiler cố ý sai →
  `MODEL_INVALID`.
- **Oracle vét cạn độc lập:** ≥ 60 seed nhỏ, có hoặc không có hint, cả hai `change_order`, có
  `max_changes` và vùng. So FEASIBLE/INFEASIBLE và vector tối ưu `(changes, P1, P2, P3)` theo thứ tự
  lexicographic đã khai báo.
- Hồi quy: `solve()` cho cùng input → output, hash và hành vi không đổi. Test guard: evaluator repair
  không import solver.

## 3. 3B — Chẩn đoán vô nghiệm (thiết kế nguyên tắc)

- **Precheck mở rộng** (điều kiện cần, rẻ, chạy trước CP-SAT): cộng thêm các phép đếm theo ngày/buổi cho
  rule hard đang bật (ví dụ tổng tải hard S03 so với ngày khả dụng). Mỗi phép đếm là chứng minh vô nghiệm
  có điều kiện, kèm số liệu.
- **Tập xung đột sau CP-SAT** (chỉ khi người dùng yêu cầu `--explain`, có budget riêng):
  - mỗi nhóm ràng buộc hard (availability theo resource, từng khóa, từng instance hard rule, demand từng
    requirement) được gắn một assumption literal;
  - giải với assumptions → `SufficientAssumptionsForInfeasibility`;
  - thu nhỏ bằng vòng loại từng phần tử trong budget.
- **Báo cáo:** `INFEASIBILITY_SUBSET` gồm danh sách nhóm và cờ `minimal_proved`. **Không** khẳng định đây
  là nguyên nhân duy nhất (§6 của đặc tả gốc). Bằng chứng gồm: giải lại chỉ với tập đó vẫn INFEASIBLE; nếu
  `minimal_proved` thì bỏ bất kỳ phần tử nào đều FEASIBLE. Cả hai đều do CP-SAT kiểm, nên ghi rõ đây là
  bằng chứng của solver, không phải của evaluator độc lập.
- Có contract output riêng (envelope), không đổi `ScheduleResult`.
- Đặc tả chi tiết và quyết định riêng sau khi 3A xong (P3-9).

## 4. 3C — Benchmark repair (thiết kế nguyên tắc)

- Dùng lại tooling v2 (module mới, không sửa v1/v2 đã đóng băng):
  - lịch trước là nghiệm của một lần `solve` đã kiểm;
  - nhiễu có seed: GV bận một ngày, đổi GV cho k requirement, thêm hoặc bớt tiết, khóa mới.
- Đo: thời gian, số thay đổi so với số thay đổi bắt buộc, có/không hint, verdict H/P như v2.
- Chạy trên máy Linux của người dùng, sau campaign Phase 2 v2 (P3-10).

## 5. Tương thích và version

- Không đổi input, output hay ScoreReport hiện có, nên E5 không bị ảnh hưởng.
- Ba contract mới có version riêng 1.0. Lần đổi sau tăng version riêng của chúng.
- `capabilities` báo `repair` là tính năng mới. Input dùng với repair phải là 1.1 (policy 0.1–0.4); input
  1.0 → `UNSUPPORTED_FEATURE` (P3-3).

## 6. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Phase 3 code thay đổi `src/` khi campaign Phase 2 v2 chưa chạy | P3-1: campaign ghim commit trước Phase 3; repair không chạm đường `solve()`; test hồi quy hash |
| Ghép theo `occurrence_id` sai khi upstream đổi ID | Contract ghi rõ: ID ổn định là trách nhiệm upstream; báo `NEW`/`DROPPED` để người dùng thấy |
| Hint che lỗi model | Hint không vào validator, evaluator hay oracle; oracle chạy cả hai chế độ |
| Tầng thay đổi làm hết budget, P1–P3 NOT_RUN | Báo đúng proof prefix; đo ở 3C; không nới budget |
| Lịch nhập tay sai từ đầu | Kiểm từng occurrence; báo `MATCHED_TARGET_INVALID`; không nhận lịch trước như hard |

## 7. Quyết định cần duyệt

- [x] **P3-1 — Thời điểm:** cho phép viết code 3A ngay. Campaign Phase 2 v2 (D/E/F) **ghim commit
  `86f624d`** (hoặc commit tài liệu kế tiếp chưa có code 3A); runbook D/E/F được cập nhật ghi rõ commit
  ghim. *(Đề xuất: chọn. Repair là tính năng mới, không phải tối ưu hiệu năng, nên không trái S1.)*
- [x] **P3-2 — Contract riêng:** ba file `PreviousSchedule`, `RepairRequest`, `RepairResult` 1.0; không sửa
  `ScheduleInput`. *(Đề xuất: chọn.)*
- [x] **P3-3 — Đầu vào:** nhận `ScheduleResult` (`valid_schedule=true`) hoặc `PreviousSchedule`; input phải
  là 1.1. *(Đề xuất: chọn.)*
- [x] **P3-4 — Output:** envelope `RepairResult` bọc `ScheduleResult` đúng version hiện có; **không** tạo
  output 1.6. *(Đề xuất: chọn; tránh thêm version product.)*
- [x] **P3-5 — Đơn vị thay đổi:** 1 occurrence có slot hoặc phòng khác = 1; báo riêng slot và chỉ-phòng.
  *(Đề xuất: chọn.)*
- [x] **P3-6 — Thứ tự:** `change_order` bắt buộc khai báo, có hai giá trị `BEFORE_QUALITY` và
  `AFTER_QUALITY`; không có mặc định. *(Đề xuất: chọn.)*
- [x] **P3-7 — Hint:** cho phép `use_previous_as_hint` như tính năng sản phẩm của repair, khai báo tường
  minh. Không áp dụng cho `solve()` hay benchmark Phase 2. *(Đề xuất: chọn.)*
- [x] **P3-8 — Giới hạn và vùng:** có cả `max_changes` (hard) và `change_scope` (lớp, GV, môn, ngày) ngay
  trong 3A. *(Đề xuất: chọn; phương án nhỏ hơn là để `change_scope` sang lát sau.)*
- [x] **P3-9 — 3B sau 3A:** đặc tả chi tiết chẩn đoán vô nghiệm làm sau khi 3A xong. *(Đề xuất: chọn.)*
- [x] **P3-10 — 3C sau campaign Phase 2 v2:** benchmark repair chạy trên máy người dùng sau khi có số đo
  Phase 2. *(Đề xuất: chọn.)*
- [x] **P3-11 — Done của Phase 3** = 3A, 3B, 3C đều xong và đạt điều kiện §10 của đặc tả gốc. Từng lát có
  báo cáo riêng. *(Đề xuất: chọn.)* **Người dùng duyệt Done ngày 2026-11-07** — xem mục "Quyết định Done"
  ở cuối.
- [x] **P3-12 — Review người thứ hai** (S3) cho contract repair trước khi dùng với dữ liệu thật; không
  chặn việc triển khai. *(Đề xuất: chọn.)*

## Quyết định Done (P3-11) — 2026-11-07

Người dùng duyệt **Phase 3 Done** ngày 2026-11-07, ở mức **mốc kỹ thuật trên dữ liệu synthetic**, giống
cách Phase 2A được đóng.

| Điều kiện §10 của đặc tả gốc | Bằng chứng |
|---|---|
| Repair test pass | `pytest tests benchmarks/tests` 2002 passed, 22 skipped (`67b4502`); oracle repair và diagnostics ([báo cáo 3A](../../phase-3a-report.md), [báo cáo 3B](../../phase-3b-report.md)) |
| Benchmark có số liệu thực | Campaign `phase3c-linux-02` (246 run, một máy Linux, n = 1 mỗi ô) — [báo cáo 3C](../../phase-3c-report.md) |
| Validator độc lập pass trên mọi nghiệm | 166/166 lịch (18 S + 148 repair) qua `validate-schedule`, `evaluate-score` và `evaluate-repair`; 58/58 report explain qua `check-explanation` |

Quyết định này **không** bao gồm:

- **Chấp nhận chất lượng:** Q vẫn REVIEW_REQUIRED.
- **Hiệu năng repair trên bài sát giới hạn:** R1 có P NOT_MET ở mức campaign vì 18 run UNKNOWN thuộc TIGHT.
- **P95/SLA và Windows.**
- **Dùng với dữ liệu thật:** trước đó vẫn cần review người thứ hai cho contract repair (P3-12, S3), còn mở.

