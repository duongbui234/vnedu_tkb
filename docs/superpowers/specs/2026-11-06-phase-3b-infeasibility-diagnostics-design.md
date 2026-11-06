# Phase 3B — đặc tả chẩn đoán vô nghiệm

Ngày 2026-11-06. Trạng thái: **DRAFT — chờ người dùng duyệt B1–B10 (§10); chưa triển khai.** Base
`fe3e1c5` trên `main`.

Nguồn yêu cầu:

- [Đặc tả Core First](../../VNEDU_TKB_CORE_FIRST_CODEX.md) §6: precheck là điều kiện cần; khi CP-SAT trả
  `INFEASIBLE`, "không tự khẳng định nguyên nhân duy nhất khi chưa có bằng chứng; cung cấp chẩn đoán hữu
  ích, có thể nghiên cứu assumption literals/unsat core". §9 (test), §10 (Done Phase 3).
- [Đặc tả Phase 3](2026-11-05-phase-3-repair-diagnostics-design.md) §3 (thiết kế nguyên tắc 3B) và P3-9,
  P3-11, P3-12.

Lượt soạn chỉ đọc source và tài liệu; không sửa `src/`, `tests/`, `benchmarks/`, không chạy solver hay
campaign. Mọi lựa chọn dưới đây là **đề xuất để duyệt**.

## 1. Mục tiêu

Khi một input không có lịch, trả lời được câu hỏi của giáo vụ: **"những ràng buộc nào cùng nhau làm không
xếp được?"**, kèm bằng chứng, mà không nói quá mức bằng chứng cho phép.

Hai đầu ra có độ mạnh khác nhau, phải ghi rõ:

| Loại | Ví dụ | Độ mạnh |
|---|---|---|
| **Phản chứng đếm** (precheck) | GV T07 cần 32 tiết nhưng chỉ có 30 ô dạy được | Chứng minh số học, kiểm lại được bằng tay và bằng evaluator độc lập |
| **Tập xung đột** (sau CP-SAT) | {khóa L3, availability GV T07, demand REQ-C02-S05} | Solver chứng minh tập này vô nghiệm; nếu `minimal_proved`, bỏ một phần tử bất kỳ thì có lịch, mỗi lịch đó được validator độc lập kiểm |

Không bao giờ nói "nguyên nhân là X". Một input vô nghiệm có thể có nhiều tập xung đột rời nhau; 3B chỉ
trả **một** tập và nói rõ điều đó.

## 2. Phạm vi

**Trong phạm vi:**

- input 1.0 và 1.1 (policy 0.1–0.4) mà `solve()` hiện nhận;
- mọi ràng buộc hard hiện có (§3.2), kể cả hard variants S01–S06;
- lệnh CLI mới và một API Python mới; contract output riêng.

**Ngoài phạm vi:**

- soft rule (không gây vô nghiệm);
- giải thích vô nghiệm của **repair** (`max_changes`, `change_scope`): để lát sau, khi có dữ liệu 3C;
- gợi ý sửa tự động ("bỏ khóa L3 thì xếp được" chỉ là hệ quả của bằng chứng minimality, không phải đề
  xuất hành động);
- UNKNOWN của `solve()` (hết budget mà không chứng minh vô nghiệm): 3B **không** biến UNKNOWN thành
  INFEASIBLE;
- input bị từ chối ở validation/capability (`INPUT_INVALID`, `UNSUPPORTED_FEATURE`): đó không phải vô
  nghiệm.

**Bất biến** (giữ như Phase 3):

- `solve()`, `repair()`, mọi contract hiện có, fingerprint, output 1.1–1.5, ScoreReport 1.0–1.2 **không
  đổi**. Precheck hiện tại của `solve()` giữ nguyên hành vi và mã lỗi.
- Validator độc lập vẫn không import solver/compiler.
- Không có giá trị mặc định ngầm: budget và chế độ do request khai báo.

## 3. Mô hình nhóm ràng buộc

### 3.1 Đơn vị chẩn đoán là "nhóm"

Một nhóm là tập ràng buộc hard mà giáo vụ hiểu như **một điều kiện**, có ID ổn định suy từ input. Báo cáo
liệt kê nhóm, không liệt kê từng ràng buộc CP-SAT.

### 3.2 Danh mục nhóm đề xuất

| Kind | ID | Ràng buộc trong model hiện tại | Cách gắn assumption |
|---|---|---|---|
| `DEMAND` | requirement ID | `ExactlyOne` của mọi occurrence thuộc requirement | Khi tắt: `AtMostOne` (occurrence được phép không xếp) |
| `CLASS_OCCUPANCY` | class ID | `AtMostOne` theo (lớp, token) | `enforce_if(a)` |
| `TEACHER_OCCUPANCY` | teacher ID | `AtMostOne` theo (GV, token) | `enforce_if(a)` |
| `ROOM_OCCUPANCY` | room ID | `AtMostOne` theo (phòng, token) | `enforce_if(a)` |
| `HARD_RULE` | rule ID (S02, S03, S05, S06 hard) | Giới hạn tải/phân phối trong `constraints/hard.py` | `enforce_if(a)` cho mọi bucket của rule |
| `LOCK` | occurrence ID của khóa | Lọc domain về slot/phòng khóa (preprocessing) | Mở rộng domain, xem §3.3 |
| `AVAILABILITY` | class/teacher/room ID | Lọc domain theo `available_slot_ids` | Mở rộng domain |
| `HARD_PLACEMENT_RULE` | rule ID (S01, S04 hard) | `placement_filter` trong preprocessing | Mở rộng domain |

**Nền cố định, không chẩn đoán** (luôn bật): calendar và `can_teach`, độ dài block và tính liên tiếp của
tiết đôi, phòng đúng loại và đủ sức chứa, mỗi occurrence nhiều nhất một placement. Đây là định nghĩa của
bài toán, không phải điều kiện giáo vụ có thể "bỏ"; nếu chúng tự mâu thuẫn thì đó là lỗi precheck
(`EMPTY_DOMAIN`) và được báo bằng phản chứng đếm.

### 3.3 Nhóm lọc domain (LOCK, AVAILABILITY, HARD_PLACEMENT_RULE)

Hiện tại các điều kiện này loại placement ngay ở preprocessing, nên model không có ràng buộc để gắn
assumption. Đề xuất cho **đường chẩn đoán** (không đổi `prepare()` của `solve()`):

- dựng domain **mở rộng**: chỉ áp nền cố định; với mỗi placement, ghi tập nhóm lọc-domain mà nó vi phạm;
- với mỗi placement p và mỗi nhóm G trong tập vi phạm của p: thêm `x_p ⇒ ¬a_G`;
- domain mở rộng đi qua cùng guard `max_placements` / `max_occupancy_terms` như `solve()`. Vượt guard →
  báo `RESOURCE_LIMIT` cho lần chẩn đoán, không nới guard.

Hệ quả: model chẩn đoán lớn hơn model `solve()`. Đây là lý do B4 cho phép chọn **mức chi tiết** (§10).

## 4. Quy trình chẩn đoán

```text
validate + capability ──fail──► trả lỗi gốc (không phải chẩn đoán)
        │
        ▼
precheck mở rộng (§5) ──có phản chứng──► PRECHECK_PROOF (dừng; không gọi CP-SAT)
        │ không có
        ▼
CP-SAT trên model đầy đủ, mọi assumption = true
        ├─ FEASIBLE/OPTIMAL ──► NOT_INFEASIBLE (không trả lịch)
        ├─ UNKNOWN (hết budget) ──► UNKNOWN
        └─ INFEASIBLE
                ▼
        core = sufficient_assumptions_for_infeasibility()
                ▼
        thu nhỏ theo deletion (§6) trong budget còn lại
                ▼
        CORE_SUBSET (minimal_proved = true | false)
```

Budget là **một** giới hạn chung cho toàn lần chẩn đoán, chia cho các lời gọi theo phần còn lại (giống
`solve()` và `repair()`), không reset theo lời gọi. workers = 1 và seed khai báo để kết quả lặp lại được
trên cùng máy và cùng wheel; không hứa lặp lại trên máy khác.

## 5. Precheck mở rộng (chỉ trong đường chẩn đoán)

Precheck của `solve()` dừng ở lỗi đầu tiên. Đường chẩn đoán chạy **tất cả** phép đếm và trả **mọi**
phản chứng tìm được, mỗi phản chứng kèm số liệu:

| ID | Phép đếm | Ví dụ số liệu |
|---|---|---|
| `PC_EMPTY_DOMAIN` | Occurrence không còn placement nào sau nền cố định + lọc domain | occurrence, lý do loại từng ứng viên theo nhóm |
| `PC_RESOURCE_CAPACITY` | Tổng tiết của lớp/GV > số ô khả dụng của họ (như hiện có, nhưng liệt kê hết) | cần 32, có 30 |
| `PC_ROOM_CAPACITY` | Tổng tiết cần phòng theo loại > số ô phòng loại đó | theo từng `room_type` |
| `PC_LOCK_OVERLAP` | Hai khóa cùng resource cùng token | hai occurrence, resource, slot |
| `PC_HARD_DAY_LOAD` | S03 hard: tổng tiết GV > Σ_ngày min(limit, ô khả dụng trong ngày) | cần 24, trần 20 |
| `PC_HARD_SESSION_LOAD` | S02 hard: tương tự theo buổi | — |
| `PC_HARD_SUBJECT_DAY` | S06 hard: tiết môn của lớp > Σ_ngày min(limit, ô khả dụng của lớp trong ngày) | — |
| `PC_HARD_DAY_SPREAD` | S05 hard: số component > số "cửa sổ" ngày khả dụng có thể chứa chúng với khoảng cách k | — |

Mỗi phép đếm là **điều kiện cần**: không có phản chứng không có nghĩa là có lịch. Phản chứng là chứng minh
vô nghiệm hoàn chỉnh, nên 3B dừng ở đây mà không gọi CP-SAT.

Kiểm chứng: một module độc lập trong `validation/` tính lại mọi phản chứng từ input thô, không import
preprocessing hay solver (B6).

## 6. Thu nhỏ tập xung đột

1. Lấy core C từ `sufficient_assumptions_for_infeasibility()`. API này không đảm bảo core nhỏ nhất.
2. Deletion: duyệt phần tử g của C theo thứ tự ổn định (kind, ID). Giải với C \ {g} bật, mọi nhóm khác tắt:
   - INFEASIBLE → bỏ g khỏi C (vẫn vô nghiệm khi thiếu g);
   - FEASIBLE → giữ g, **lưu lịch tìm được làm witness** cho g;
   - UNKNOWN (hết budget lời gọi) → giữ g, đánh dấu g chưa kết luận.
3. `minimal_proved = true` chỉ khi mọi g còn lại đều có witness FEASIBLE **và** mỗi witness được validator
   độc lập kiểm (§7). Nếu còn g chưa kết luận hoặc hết budget → `minimal_proved = false`, vẫn trả C hiện tại
   (đã được chứng minh vô nghiệm ở lần giải gần nhất).

Kết quả là một tập **tối tiểu theo bao hàm** (bỏ một phần tử bất kỳ thì có lịch), **không** phải tập nhỏ
nhất về số phần tử.

## 7. Bằng chứng và kiểm độc lập

| Khẳng định | Bằng chứng | Ai kiểm |
|---|---|---|
| Phản chứng đếm đúng | Số liệu trong báo cáo | Module kiểm độc lập tính lại từ input thô |
| Tập C vô nghiệm | Status INFEASIBLE của CP-SAT với đúng C bật | **Chỉ solver.** Báo cáo ghi `infeasibility_evidence: "SOLVER"`; không có proof độc lập |
| C tối tiểu | Với mỗi g ∈ C: một lịch thỏa mọi nhóm trong C \ {g} | Validator độc lập ở chế độ **bỏ qua đúng các nhóm đã tắt** (B5) |

Chế độ "bỏ qua nhóm" của validator là thay đổi mới trong `validation/`: nhận danh sách nhóm được bỏ qua,
vẫn kiểm nền cố định và mọi nhóm khác. Nó không import solver/compiler (test guard như hiện có). Witness
không được trả ra như lịch dùng được: chúng vi phạm nhóm g theo định nghĩa.

## 8. Contract

### 8.1 `InfeasibilityReport` 1.0 (envelope mới)

| Field | Ý nghĩa |
|---|---|
| `schema_version` | `"1.0"` |
| `status` | `PRECHECK_PROOF` / `CORE_SUBSET` / `NOT_INFEASIBLE` / `UNKNOWN` / `RESOURCE_LIMIT` |
| `input_fingerprint` | Như `solve()` |
| `precheck_proofs[]` | `{id, resources[], occurrences[], required, available, detail}` |
| `subset[]` | `{kind, id, label}` theo §3.2 |
| `minimal_proved` | Boolean; chỉ có nghĩa khi `CORE_SUBSET` |
| `unresolved[]` | Nhóm trong `subset` chưa kết luận minimality |
| `evidence` | `infeasibility`: `ARITHMETIC` hoặc `SOLVER`; `minimality_witnesses[]`: `{group, validator_status}` |
| `granularity` | Mức chi tiết đã dùng (B4) |
| `metadata` | solver version, seed, workers, time limit, wall time, số lời gọi |
| `limitations` | Câu cố định: "Một tập xung đột, không phải nguyên nhân duy nhất; input có thể có tập khác" |

Không có `assignments` trong report. Không đổi `ScheduleResult`.

### 8.2 API và CLI

- `tkb_core.diagnostics.explain_infeasibility(problem, options) -> InfeasibilityReport`.
- CLI: `tkb-core explain INPUT --time-limit S --seed N --granularity G` → JSON stdout. Cả ba tham số
  bắt buộc.
- CLI kiểm độc lập: `tkb-core check-explanation INPUT REPORT` kiểm fingerprint, tính nhất quán của report
  và tính lại mọi phản chứng precheck; không cần OR-Tools. Witness không nằm trong report (§7), nên
  `check-explanation` không kiểm lại được minimality; muốn kiểm phải chạy lại `explain`.
- `contracts/capabilities.py` không có danh sách tính năng (như 3A); input bị `check_capabilities` từ
  chối thì `explain` trả đúng lỗi đó.

Exit code: 0 khi report hợp lệ (kể cả `NOT_INFEASIBLE`), mã lỗi hiện có cho input lỗi. Không dùng exit
code để phân biệt PRECHECK_PROOF/CORE_SUBSET.

## 9. Test bắt buộc

| Nhóm | Nội dung |
|---|---|
| Contract | Roundtrip, field lạ bị từ chối, status/field nhất quán (`minimal_proved` chỉ với CORE_SUBSET) |
| Precheck | Mỗi `PC_*` có fixture dương và fixture biên (vừa đủ → không phản chứng); liệt kê hết, không dừng ở lỗi đầu; verifier độc lập khớp |
| Core tính tay | Fixture có tập xung đột biết trước: hai khóa cùng GV; GV bận + demand; S03 hard + demand; phòng duy nhất; S01 hard + khóa |
| Oracle | Bài tí hon sinh theo seed: liệt kê vét cạn mọi tập con nhóm để biết MUS; kiểm (a) `subset` vô nghiệm, (b) nếu `minimal_proved` thì `subset` là một MUS thật |
| Budget | Budget rất nhỏ → `minimal_proved=false` hoặc `UNKNOWN`, không bao giờ khẳng định sai |
| Feasible | Input có lịch → `NOT_INFEASIBLE`, không trả assignments |
| Witness | Validator chế độ bỏ qua nhóm: chấp nhận witness đúng, từ chối witness vi phạm nhóm khác |
| Bất biến | Hash output của `solve()`/`repair()` trên fixture hiện có không đổi; precheck `solve()` giữ mã lỗi; import guard của validation |
| CLI | `explain` → `check-explanation` end-to-end; `check-explanation` chạy được trong venv không OR-Tools; report giả (phản chứng sai số, fingerprint lệch) bị từ chối |

## 10. Quyết định cần duyệt

- [ ] **B1 — Đường riêng:** chẩn đoán là API/CLI mới (`explain`); `solve()` và `repair()` không đổi, không
  tự gọi chẩn đoán. *(Đề xuất: chọn. Giữ bất biến Phase 3; phương án khác là `solve --explain`, nhưng sẽ
  làm đổi output của `solve()`.)*
- [ ] **B2 — Contract `InfeasibilityReport` 1.0** riêng như §8.1, không có assignments. *(Đề xuất: chọn.)*
- [ ] **B3 — Danh mục nhóm** như §3.2, với nền cố định §3.2 không chẩn đoán. *(Đề xuất: chọn.)*
- [ ] **B4 — Mức chi tiết:** `MODEL` (chỉ DEMAND, OCCUPANCY, HARD_RULE; model nhỏ) và `FULL` (thêm LOCK,
  AVAILABILITY, HARD_PLACEMENT_RULE qua domain mở rộng). Request phải chọn tường minh. *(Đề xuất: chọn cả
  hai, triển khai `MODEL` trước trong cùng lát. GV bận và khóa là nguyên nhân thường gặp nên `FULL` cần
  có trước khi dùng với dữ liệu thật.)*
- [ ] **B5 — Bằng chứng minimality** qua witness và validator độc lập chế độ bỏ qua nhóm (§7); phía vô
  nghiệm ghi rõ chỉ solver. *(Đề xuất: chọn.)*
- [ ] **B6 — Precheck mở rộng** §5, chỉ trong đường chẩn đoán, liệt kê mọi phản chứng, có verifier độc
  lập. Không đổi precheck của `solve()`. *(Đề xuất: chọn; đưa vào `solve()` là quyết định riêng sau.)*
- [ ] **B7 — Budget:** một budget chung bắt buộc khai báo; workers = 1; seed khai báo. *(Đề xuất: chọn.)*
- [ ] **B8 — Thu nhỏ bằng deletion** theo thứ tự ổn định (§6); tối tiểu theo bao hàm, không tối ưu số phần
  tử. *(Đề xuất: chọn. QuickXplain là cải tiến sau nếu đo thấy chậm.)*
- [ ] **B9 — Spike kỹ thuật trước TDD:** xác nhận trên OR-Tools 9.15.6755 đã pin rằng
  `add_assumptions` + `sufficient_assumptions_for_infeasibility()` trả core đúng với workers = 1, có/không
  presolve, và hành vi khi hết budget. Kết quả ghi vào kế hoạch; nếu API không đáp ứng thì dừng và đề xuất
  lại, không tự đổi thiết kế. *(Đề xuất: chọn.)*
- [ ] **B10 — Ngoài phạm vi:** không giải thích vô nghiệm của repair, không gợi ý sửa tự động, không
  benchmark 3B trong lát này (đo thời gian chẩn đoán thuộc 3C hoặc lát sau). *(Đề xuất: chọn.)*

Duyệt đặc tả là duyệt thiết kế; viết kế hoạch task, spike và code cần ủy quyền riêng.

## 11. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Domain mở rộng (FULL) vượt guard ở 40 lớp | Báo `RESOURCE_LIMIT`; người dùng chọn `MODEL`; không nới guard |
| Core lớn, deletion tốn nhiều lời gọi | Budget chung; trả tập chưa tối tiểu với `minimal_proved=false` thay vì chạy mãi |
| Người đọc hiểu tập xung đột là "nguyên nhân" | `limitations` cố định trong mọi report; tài liệu và CLI ghi rõ |
| Assumption API khác kỳ vọng ở 9.15 | Spike B9 trước TDD |
| Validator chế độ bỏ qua nhóm làm yếu validator chính | Chế độ chỉ bật bằng tham số tường minh; test rằng mặc định vẫn kiểm đủ; witness không bao giờ được trả như lịch |

## 12. Kiểm tra khi soạn

Đọc `preprocessing/feasibility.py`, `solver/model_builder.py`, `constraints/hard.py`,
`constraints/hard_variants.py`, `contracts/capabilities.py`, `cli.py`, đặc tả gốc §6 và đặc tả Phase 3.
OR-Tools pin `9.15.6755` lấy từ `uv.lock`. Hành vi API assumption **chưa được thử** trong lượt này (B9).
Không chạy test, solver hay campaign.
