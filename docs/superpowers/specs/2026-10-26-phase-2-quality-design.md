# Phase 2 — Registry ràng buộc, ưu tiên và independent score evaluator

Ngày: 2026-10-26. Trạng thái: **PHASE 2A ĐÃ ĐƯỢC DUYỆT VÀ TRIỂN KHAI**; xem [báo cáo](../../phase-2a-report.md). Mốc 2B/2C chưa triển khai.

Phạm vi lượt này chỉ là tài liệu. Không sửa Core, tests, dependency, dữ liệu nghiên cứu hoặc gọi API. Thiết kế cần được review trước khi lập implementation plan; tài liệu này không phải biên bản nghiệm thu Phase 2.

## 1. Căn cứ, mục tiêu và ranh giới

Nguồn chuẩn: [Core First, mục 10/Phase 2](../../VNEDU_TKB_CORE_FIRST_CODEX.md), [policy 0.1](../../research/stkb/09-vnedu-hard-soft-policy.md), [Gap Analysis Phase 1](../../research/stkb/03-phase1-gap-analysis.md), [thiết kế Phase 1](2026-10-26-phase-1-design.md). Snapshot đối chiếu: `7f58f710a9901fe2c0457573feaad272e713d7a1`.

- **VERIFIED:** `domain/models.py::SoftConstraintConfig:156–159` hiện có weight nguyên dương, chưa có priority hoặc rule ID. `RuleScope:138–144` có bốn loại resource; contract tồn tại không chứng minh mọi kiểu scope đã được thực thi.
- **VERIFIED:** `contracts/capabilities.py::check_capabilities:7–28` từ chối mọi custom rule đang bật; chỉ một GV/một lớp và block 1–2. `solver/cp_sat.py::solve:27–28,116–167` hiện giải feasibility, validate hard trước khi xuất lịch.
- **VERIFIED:** `contracts/input.py::ScheduleInput:38–51,107–134` chỉ nhận input 1.0; fingerprint có schema/config, canonical hóa các tập hiện có nhưng giữ thứ tự danh sách rule. `contracts/output.py::ScheduleResult:50–75` đọc output 1.0/1.1 và chặn xuất assignments chưa validate.
- **VERIFIED:** dữ liệu giải mã có lịch đủ demand nhưng vi phạm ô Nghỉ/max-buổi; xem E1–E3 trong policy. Điều đó không xác lập hardness, trọng số hoặc ngưỡng chung của vnEdu.
- **INFERRED:** mọi contract, tên code, phạm vi triển khai và chính sách ưu tiên dưới đây là đề xuất thiết kế mới. Không tuyên bố tương đương STKB/FET, không sao chép implementation của hai phần mềm.
- **UNKNOWN:** ngưỡng thực tế của trường, ý nghĩa đầy đủ mã 999/Họp và auto-lock, trọng số đã hiệu chỉnh, hiệu năng trên máy người dùng. Không cần các dữ kiện này để kiểm thử synthetic; bắt buộc giải quyết trước bật policy tương ứng với dữ liệu thật.

Mục tiêu mốc **Phase 2A**: hỗ trợ S01–S04 với penalty chính xác, cấu hình rõ ràng, tối ưu theo ưu tiên, và tính lại điểm bằng Python độc lập OR-Tools. Hard nền tảng Phase 1 luôn giữ nguyên. Phase 2A không đồng nghĩa hoàn thành toàn Phase 2 trong Core First: phân phối môn và gaps thuộc mốc 2C.

Chưa làm repair/minimize changes, chọn split tự động, travel, đồng giảng/lớp ghép, tuần A/B, curriculum resolver, import STKB, API, UI hoặc lưu trữ. Không dùng `so_tiet=0` để tự tạo demand. Core chỉ nhận snapshot demand/split/calendar/policy đã được application xác nhận.

## 2. Phương án được đề xuất

| Phương án | Đánh đổi | Quyết định thiết kế |
|---|---|---|
| Một weighted sum cho mọi rule | Ít lượt solve; dễ để nhiều nguyện vọng nhẹ lấn một nguyện vọng mạnh | Không chọn làm profile 0.1 |
| Lexicographic theo priority, weighted sum trong mỗi tier | Bảo toàn thứ tự ưu tiên; phải quản lý budget, incumbent và bằng chứng tối ưu theo từng lượt | **Chọn**, phù hợp policy 0.1 |
| Gom tiers bằng big-M hoặc hard thành penalty lớn | Khó kiểm soát overflow/đánh đổi; dễ báo sai tính hợp lệ | Không dùng |

Mỗi tier dùng tổng `weight × raw_penalty`. Vector so sánh `(P1,P2,P3)`, không một scalar chung. Tất cả S01–S04 mặc định đề xuất P1, weight 1 khi application tạo cấu hình; payload phải ghi explicit, Core không tự thêm rule/ngưỡng. Caller có thể chọn priority 1–3 và weight nguyên dương; đây là thay đổi policy có chủ ý, không phải tự suy từ mã STKB.

## 3. Contract version và migration

### 3.1 Input đề xuất 1.1

Giữ nguyên input 1.0 và fingerprint của nó; input 1.0 vẫn chỉ giải built-in hard, mọi enabled custom rule vẫn UNSUPPORTED_FEATURE như Phase 1. Không tự nâng version hoặc gán priority cho rule cũ. Disabled rules 1.0 tiếp tục được mang theo/fingerprint mà không thực thi.

Input 1.1 giữ các domain fields và constraints nền hiện tại, thay `constraint_config` bằng envelope rõ phiên bản:

```json
{
  "policy_version": "0.1",
  "hard": [],
  "soft": [
    {
      "id": "pref-teacher-a-am-load",
      "code": "TEACHER_MAX_PERIODS_PER_SESSION",
      "scope": {"teacher_ids": ["teacher-a"]},
      "parameters": {"limit": 3, "session_ids": ["AM"]},
      "enabled": true,
      "priority": 1,
      "weight": 1
    }
  ]
}
```

Đây là **fragment của constraint_config tương lai**, không phải JSON chạy được trên Core hiện tại hoặc schema API vnEdu. Root `schema_version` phải là `1.1`. `policy_version` bắt buộc, chỉ nhận `0.1` trong mốc này. Không thêm root quality profile hoặc ngôn ngữ policy thứ hai.

Envelope soft: id/code không rỗng; id duy nhất xuyên cả hard/soft, kể cả rule tắt; enabled là strict bool (default true như hiện tại); priority bắt buộc strict int 1..3; weight bắt buộc strict int >0. Scope chỉ nhận field đã định nghĩa, defaults tập rỗng như Phase 1. Parameters được parse theo code. Không cho float/bool thay integer, không ép chuỗi thành số, không bỏ unknown fields.

Hard envelope tương lai có id/code/scope/parameters/enabled, **không** có priority/weight. Trong 2A, mọi enabled custom hard vẫn bị từ chối; built-in hard không đi qua envelope và không có nút tắt. 2B mới cho phép hard variants đã có compiler lẫn validator.

Một mã mới chưa biết nhưng envelope hợp lệ: enabled → UNSUPPORTED_FEATURE/UNKNOWN_RULE; disabled → giữ raw parameters JSON và không thực thi. Code đã biết mà tham số sai → INPUT_INVALID, kể cả disabled. Unknown envelope fields, ID trùng hoặc reference sai vẫn INPUT_INVALID. Version input/policy không hỗ trợ bị từ chối tại boundary, không thử parse bằng version gần nhất.

### 3.2 Scope và precedence

S01–S04 chỉ cho teacher scope: tập teacher_ids rỗng nghĩa mọi GV trong snapshot, tập không rỗng nghĩa đúng các GV đó. class_ids/subject_ids/room_ids phải rỗng; field scope không được hỗ trợ trả UNSUPPORTED_FEATURE/RULE_SCOPE, không âm thầm lọc. Tập teachers không được chứa ID trùng hoặc lạ.

Core không chạy kế thừa trường → nhóm → cá nhân. Application phải resolve trước, xuất các scope hiệu lực không chồng nhau cho cùng một rule family/đối tượng/bucket. Một rule global cộng một rule riêng cùng family áp vào cùng GV/bucket là INPUT_INVALID/OVERLAPPING_RULES, không cộng hai penalty và không chọn bản cuối.

Quy tắc overlap theo rule family: S01 hai tập ô cùng bao phủ ít nhất một teaching period trong calendar (symbolic theo ID, timed theo giao khoảng phút nửa mở), không chỉ so ID; S02 cùng GV/ngày/buổi; S03 cùng GV/ngày; S04 cùng GV/ngày/buổi. Ngưỡng/priority khác nhau không làm chúng thành độc lập. S01 và S04 có thể cùng phạt một tiết nếu caller chủ ý đặt cả hai: đó là hai mục tiêu khác nhau, không phải bản sao kế thừa; report phải hiển thị riêng. Empty scope mở rộng ra tập GV hiện tại để kiểm overlap.

Không tắt được hard bằng soft, không tự nâng soft lên hard. Raw STKB chưa xác nhận không phải rule input hợp lệ. Disabled không chứng minh override/inheritance của phần mềm nguồn; application phải giữ provenance riêng.

### 3.3 Fingerprint và tương thích

Fingerprint input 1.1 bao gồm schema_version, policy_version và mọi declarations, kể cả disabled/weight/priority/parameters. Canonical JSON SHA-256 như 1.0, nhưng nhánh 1.1 sort rules theo id và các tập ID trong scope. Chỉ sort tập parameters được parameter model của code đã biết định nghĩa: slot_ids của S01, session_ids của S02/S04; 2A không có day_ids. Unknown disabled rule giữ nguyên thứ tự mọi array trong raw parameters vì chưa biết array là tập hay chuỗi có thứ tự; chỉ canonical hóa object keys. Không sort block_durations vì ordinal là identity. Không hash theo thứ tự đăng ký compiler hoặc dict traversal.

Hai bản chỉ đảo tập/danh mục có cùng hash 1.1; đổi weight/priority/limit/slot set/split phải đổi hash. Không chuyển hash 1.0 thành hash 1.1, kể cả không có rule. Parser phân nhánh version trước validation; không dùng union có fallback nuốt lỗi.

Phase 2 đọc input 1.0/1.1, output 1.0/1.1/1.2. Input 1.0 tiếp tục phát output 1.1 với hành vi cũ; input 1.1 phát output 1.2. Parser strict cũ không được hứa đọc version mới. Đây là quyết định migration cho implementation plan, chưa thay parser hiện tại.

## 4. Registry tối thiểu

Registry tĩnh trong package, không plugin động, import bên ngoài, reflection hoặc thực thi code từ JSON. Mỗi entry gồm:

| Field | Trách nhiệm |
|---|---|
| code, policy ID | Định danh semantics ổn định trong policy 0.1 |
| parameter model, allowed scope | Parse tham số strict và kiểm reference trước solve |
| supported modes | 2A chỉ soft; không quảng cáo hard khi validator chưa có |
| raw unit, explanation | Đơn vị penalty và cách giải thích cho report |
| compiler | Tạo expression/auxiliary vars cho CP-SAT cùng upper bound bảo thủ |
| evaluator | Callable Python độc lập tính raw penalty từ input và assignments |

Chỉ được công bố capability khi compiler **và** evaluator hoàn chỉnh; thêm hard mode cần independent hard checker tương ứng. Dùng chung metadata/typed parameter definitions là được; không dùng chung helper tính penalty, footprint, tải, coefficients hoặc candidate domain giữa compiler và evaluator.

Luồng boundary: revalidate snapshot → dispatch input/policy version → parse registry params/references → check capability/scope/overlap → prepare hard domains → compile soft → solve → independent hard validation → independent score → đối chiếu compiled score → result. Validate-schedule/evaluate-score phải dùng cùng gate về capability; không có đường kiểm tra khác âm thầm bỏ rule.

Known unsupported code/scope/mode → UNSUPPORTED_FEATURE. Tham số sai/reference sai/overlap → INPUT_INVALID. Domain hard rỗng hợp lệ → INFEASIBLE như trước. Overflow/ràng buộc mô hình nội bộ lỗi → MODEL_INVALID; operational size guard → UNKNOWN/RESOURCE_LIMIT, không INFEASIBLE.

## 5. Semantics S01–S04 — chuẩn triển khai

### 5.1 Calendar và footprint chung về nghĩa

Một tiết dạy là một covered slot của occurrence, không phải một assignment row. Double duration 2 có một assignment nhưng hai tiết tải và có thể hai đơn vị phạt. Footprint vẫn theo Phase 1: cùng ngày/buổi, period liên tiếp, mọi slot hợp lệ; timed calendar còn yêu cầu phút liền nhau.

day là real-day index của cycle, session là ID opaque. Tải ngày cộng mọi session cùng day; không quy đổi sáng/chiều thành hai ngày. Giữ nguyên consistency gates Phase 1: period trong cùng day/session không được giao phút; slots thuộc sessions khác nhau cùng day có thể giao phút, occupancy vẫn ngăn một GV/lớp/phòng dạy chồng thời gian. Không thêm gate ép các slot giao thời gian phải cùng session. Khi một occurrence chọn slot nào thì S02/S04 dùng đúng session của slot đó, S03 dùng đúng day của slot đó; không cộng tải thêm vào các slot alias không được chọn. Không suy luận ngày/buổi từ tên slot hoặc chia phút cho 1440.

Một cặp slot ID khác nhau có thể cùng thời gian vật lý: resource occupancy vẫn kiểm theo phút như Phase 1. Penalty tính một lần theo mỗi covered period của occurrence, không nhân theo các slot alias giao nhau. S01 dùng giao thời gian để nhận biết ô muốn tránh; các bucket S02–S04 dùng day/session/period của covered slot thật.

Chưa có event domain: tải S02/S03 chỉ là tiết giảng dạy của TeachingRequirement; availability/họp đã chặn không cộng thành tiết dạy. Không suy load từ số slots resource có thể dạy.

### 5.2 Danh sách tham số và công thức

| Policy / code | Parameters strict | Scope và raw penalty |
|---|---|---|
| S01 / TEACHER_AVOID_SLOTS | `slot_ids`: tập ID slot không rỗng | Mỗi GV đã chọn: đếm covered periods nằm trên ô tránh. Calendar symbolic dùng tọa độ slot; timed dùng khoảng phút nửa mở giao nhau, đếm mỗi covered period tối đa một lần dù giao nhiều ô tránh. |
| S02 / TEACHER_MAX_PERIODS_PER_SESSION | `limit`: int ≥0; `session_ids`: tập session không rỗng | Mọi ngày trong cycle, đúng sessions đã chọn; tổng `max(0, teaching_periods[t,d,s] - limit)` theo t,d,s. |
| S03 / TEACHER_MAX_PERIODS_PER_DAY | `limit`: int ≥0 | Mọi ngày trong cycle; tổng `max(0, sum_s teaching_periods[t,d,s] - limit)` theo t,d. |
| S04 / TEACHER_PREFERRED_PERIOD_WINDOW | `first_period`, `last_period`: int ≥1, first≤last; `session_ids`: tập session không rỗng | Mọi ngày, đúng sessions đã chọn; đếm covered periods có period nằm ngoài khoảng inclusive [first,last]. Kiểm cả tiết thứ hai của double. |

Trong 2A không có day_ids filter; mọi ngày calendar đều áp dụng. Mọi tập session phải tham chiếu session xuất hiện trong calendar, cấm duplicate/unknown; slot_ids phải tồn tại và can_teach=true. S04 không yêu cầu toàn bộ các period number trong khoảng phải tồn tại: khoảng rộng hơn calendar có thể tạo penalty 0 hợp lệ. Chỉ placements hợp lệ hard mới được xét; S01 có thể phạt một slot alias khả dụng giao thời gian với ô tránh, kể cả ID của ô tránh không nằm trong teacher availability. Availability Phase 1 xét slot IDs, còn S01 timed xét giao phút; không tự mở availability. Nếu upstream muốn cấm một khoảng thời gian vật lý, phải loại mọi slot ID giao khoảng đó khỏi availability, không chỉ một alias.

Tập slot IDs S01 là mong muốn tránh, không bị loại khỏi candidate domain. limit=0 hợp lệ khi rule bật; disabled+limit=0 không có penalty. Rule có scope GV chưa có demand vẫn được ghi với penalty 0. Không mặc định max=3 hoặc tải/ngày=2×max/buổi. Không lấy FET “số ngày vi phạm” thay số tiết vượt.

### 5.3 Compilation cho CP-SAT

S01/S04: mỗi placement p có coefficient là số covered periods bị phạt; `raw = sum(coeff[o,p] × x[o,p])`. Gộp các lựa chọn phòng của cùng time placement theo tổng Boolean hoặc dùng expression tương đương; một occurrence chỉ được chọn một placement nên không đếm các candidate không chọn.

S02/S03: dựng load expression từ duration/covered periods của các placements thuộc bucket; lập excess int với `AddMaxEquality(excess, [0, load-limit])`. Raw là tổng excess. **Phải** là equality đúng giá trị ngay cả khi tier chưa được tối ưu; không chỉ dùng `excess >= ...` rồi dựa objective kéo xuống. Bound tính từ demand liên quan, không từ giả định số tiết/ngày.

Weighted penalty là raw × weight, integer chính xác. Bound của raw/weighted/tổng tier được tính bảo thủ trước build; yêu cầu mọi phép tính và expression domain trong signed int64 an toàn, tổng tier ≤2^53−1 để metadata số thực không che mất đơn vị nguyên. Vượt bound → INPUT_INVALID/OBJECTIVE_RANGE trước solve, không clip, scale hoặc giảm weight. Vẫn gọi validation của model; model bất hợp lệ phát sinh ngoài gate → MODEL_INVALID. Giới hạn này là engineering contract, không phải ngưỡng nghiệp vụ.

## 6. Ưu tiên, budget, incumbent và status

SolveOptions hiện có time_limit_seconds/seed/num_workers/resource guards; 2A giữ API đó. Không tạo budget riêng mặc định cho từng rule hoặc tier. Tổng thời gian CP-SAT của các lượt feasibility + tối ưu không vượt budget được phân bổ (ngoại trừ overhead dừng solver); tính remaining bằng monotonic clock quanh các lần gọi. Preprocessing/validation/evaluation đo riêng và không được hứa nằm trong budget CP-SAT. Không thêm cancellation IPC trong mốc này.

1. Chạy hard feasibility trước trong budget còn lại. Lấy incumbent hoàn chỉnh, validate hard và tính score độc lập. Nếu không có nghiệm, giữ phân loại Phase 1; không đọc assignments từ UNKNOWN.
2. Duyệt tiers có rule bật theo 1→2→3. Tier không có rule là trivial score 0, không cần solver call. Minimize tổng weighted penalty tier hiện tại, có thể hint incumbent; hint không là lock.
3. Mỗi nghiệm được chọn giữ lại phải qua hard validation, score evaluation và đối chiếu expression. Chỉ thêm equality giữ score tier trước khi solver đã trả OPTIMAL với cấu hình proof chính xác; không freeze incumbent FEASIBLE như optimum.
4. Không đặt relative/absolute gap tolerance khác 0 để rồi gọi đó là tối ưu nguyên chính xác. Best bound chỉ là bằng chứng của tier đang solve với các tier trước đã cố định; không là bound chung cho vector.
5. Tier FEASIBLE hoặc hết budget chưa chứng minh tối ưu: dừng chuỗi, trả incumbent tốt nhất đã xác nhận, không tiếp tục tier thấp. Nếu raw status UNKNOWN ở lượt sau thì giữ incumbent trước, top-level FEASIBLE; ghi raw UNKNOWN trong tier run. Không dùng top-level UNKNOWN khi đã có incumbent hợp lệ.
6. Tier sau trả INFEASIBLE dù incumbent trước đáp ứng các equality vừa thêm: coi là lỗi consistency MODEL_INVALID/INTERNAL_STAGE_INCONSISTENCY, không tuyên bố bài toán gốc vô nghiệm. MODEL_INVALID hoặc sai validator/score ở bất kỳ lượt nào đều là lỗi nội bộ, không che bằng fallback thành công.

So incumbent bằng toàn vector khi cần chọn giữa các candidate. Với cùng vector không hứa lịch ổn định; repair là Phase 3. Mốc 2A không cần callback đánh giá mọi intermediate solution: đánh giá nghiệm trả về mỗi lượt và incumbent cũ là đủ. Không phụ thuộc callback để giữ được nghiệm của lượt trước.

| Tình huống | Top-level status / quality status |
|---|---|
| Có active soft, mọi tier đã tối ưu chính xác | OPTIMAL / LEXICOGRAPHIC_OPTIMAL |
| Có active soft, còn tier chưa chứng minh nhưng có incumbent | FEASIBLE / SCORED_FEASIBLE |
| Không active soft | Giữ semantics feasibility; quality NOT_REQUESTED, không gọi là lịch đẹp tối ưu |
| Không có incumbent và chưa chứng minh vô nghiệm | UNKNOWN / NOT_EVALUATED |
| Hard vô nghiệm đã chứng minh | INFEASIBLE / NOT_EVALUATED |
| Input/capability/model lỗi | Status tương ứng / NOT_EVALUATED; không xuất assignments |

Empty confirmed demand với active S01–S04 có penalty 0 theo định nghĩa, không gọi solver: FEASIBLE/SCORED_FEASIBLE, diagnostic EMPTY_PROBLEM; không chế CP-SAT proof. Không active soft thì giữ đường empty Phase 1. Mọi lịch xuất ra phải hard-valid; các ưu tiên chưa đạt không làm valid_schedule=false.

## 7. Independent score evaluator

API đề xuất thuần Python:

```text
evaluate_score(problem, assignments) -> ScoreReport
```

Không import OR-Tools, preprocessing.prepare, candidate domains, compiler, objectives hoặc helper footprint của solver. Có thể dùng domain types, registry metadata và parameter models; tự mở occurrences từ demand/split, tự dựng footprint từ start slot và calendar, tự tính loads/avoid/window. Gọi independent hard validator trước để loại lịch thiếu/trùng/sai; không dùng report valid=true do caller gửi.

Evaluator không tối ưu và không chứng nhận optimality. Không đọc score, validation hoặc covered slots trong result làm oracle. Fingerprint của result được wrapper kiểm trước; API raw assignments không có lịch sử để tự biết stale snapshot.

ScoreReport version 1.0 đề xuất:

- `status`: OK / INPUT_INVALID / UNSUPPORTED_FEATURE / INVALID_SCHEDULE / INTERNAL_ERROR.
- `input_fingerprint`: hash input nếu parse được; `diagnostics`: mã lỗi không kèm raw records.
- `rules`: chỉ khi OK; mỗi enabled soft rule một dòng gồm rule_id/code/priority/weight/unit/raw_penalty/weighted_penalty. Có cả rule có penalty 0; disabled không xuất dòng.
- `tiers`: ba tổng nguyên không âm theo thứ tự P1/P2/P3. Raw không gộp qua các đơn vị khác nhau; weighted được cộng trong tier có trade-off đã công bố.
- Không trả partial score nếu có rule không hiểu, lịch thiếu hoặc bất kỳ kiểm tra thất bại. No-soft input hợp lệ trả rules rỗng, tiers [0,0,0]; điều đó không chứng nhận chất lượng theo policy chưa được bật.

Trong tuyến solve, evaluator OK chưa đủ: so từng rule raw, weighted và tier với integer expression value của model tại incumbent. Sai một phần → MODEL_INVALID/INTERNAL_SCORE_MISMATCH, không xuất assignments hay điểm làm như hợp lệ. Trong evaluate-score CLI, lỗi lịch là input-invalid/exit 2, không phải solver vô nghiệm. Báo cáo hard/score độc lập với solver proof metadata.

## 8. Output 1.2 và CLI

Input 1.1 phát ScheduleResult 1.2, giữ assignments start-only và các guardrails Phase 1. `quality` bắt buộc gồm policy_version, quality status, score (ScoreReport hoặc null), optimal_prefix (danh sách tiers có bằng chứng theo thứ tự) và tier_runs.

Mỗi tier_run có priority, raw solver status hoặc NOT_RUN, exact incumbent tier value hoặc null, solver best bound hoặc null, wall time đo được, proved_optimal. Tier không active không tạo solver run. Score hiển thị **toàn bộ** tiers từ incumbent cuối, cả tiers chưa optimize; không nhầm số điểm đã tính với điểm đã chứng minh tối ưu. optimal_prefix chỉ gồm active tiers đã được chứng minh liên tiếp; không bỏ qua một active tier chưa chứng minh.

Metadata 1.2 giữ seed/workers/budget/version/wall_time/solver_wall_time/solver_executed. solver_wall_time là tổng solver calls; thêm feasibility_run cùng shape measurements/raw status để biết lượt feasibility thực sự chạy. objective_value/best_bound ở metadata tổng để null khi có quality; không nhét vector hoặc scalar tier cuối vào field cũ thiếu ngữ cảnh. Exact integer incumbent values nằm trong score/tier_runs, bound float nullable chỉ ghi khi đã đo.

Nếu quality status SCORED_FEASIBLE/LEXICOGRAPHIC_OPTIMAL thì score phải OK, hash khớp result và hard validation valid. LEXICOGRAPHIC_OPTIMAL yêu cầu mọi active tier proved; FEASIBLE không bị nâng lên OPTIMAL vì lượt feasibility trả OPTIMAL. NOT_EVALUATED không có score; NOT_REQUESTED có thể chứa score rỗng đã kiểm nhưng không có proof tối ưu quality. Lỗi nội bộ giữ diagnostics/measurements, không assignments.

Giữ `validate-input` là contract-only; registry parameter shape/reference thuộc contract 1.1, nhưng support mode/solver không được giả thành kiểm chứng khả thi. `solve` và `validate-schedule` giữ cú pháp/exit codes; validate-schedule với input 1.1 phải tái tính score, so với result 1.2 nếu có, không tin số tự khai. Thêm lệnh thuần Python, không cần solver extra:

```sh
tkb-core evaluate-score problem.json result.json
```

Lệnh nhận result đã parse đúng version, kiểm fingerprint, lấy assignments và tính lại từ đầu; bỏ qua điểm cũ làm oracle. Score mismatch trong result người dùng là INPUT_INVALID/RESULT_SCORE_MISMATCH, không phải lỗi model nội bộ. stdout một JSON ScoreReport; stderr log; exit 0 khi OK, 2 khi input/unsupported/stale/lịch sai, 5 khi lỗi nội bộ. Không thêm file writer mới hoặc overwrite behavior cho lệnh này.

## 9. Nghiệm thu và fixture kế hoạch

Mọi tests dưới đây là **yêu cầu tương lai, chưa được viết/chạy trong lượt này**. Fixture synthetic, không dùng tên/mã thật hoặc dữ liệu STKB/API. Giữ toàn bộ hồi quy Phase 0/1 và lệnh lint/type/build/wheel CLI; import evaluator không yêu cầu solver extra.

| Nhóm | Ca có expected độc lập |
|---|---|
| Version | Input 1.0 giữ fingerprint/hành vi cũ; 1.1/1.2 roundtrip; priority trên 1.0 bị reject; unknown version/field không fallback |
| Registry | Unknown enabled/disabled; malformed known disabled; hard mode 2A reject; unsupported scope; duplicate id; params refs sai; overlap global+GV; disabled không được tính |
| Fingerprint | Đảo sets/rules/danh mục không đổi hash 1.1; đổi weight/priority/limit/split đổi hash; giữ thứ tự split và hash cũ 1.0 |
| S01 | Single tránh=1; double cả hai tránh=2; chỉ tiết thứ hai tránh=1; timed aliases khác session cùng day giao nhiều avoided IDs chỉ tính một lần mỗi covered period; overlap trong cùng day/session vẫn bị từ chối; hard busy vẫn không được xếp |
| S02 | Load 4 limit 3 →1; load 2 limit 3 →0; load 2 limit 0 →2; disabled limit 0 →không dòng điểm; double tính 2; AM/PM tách biệt |
| S03 | AM=2, PM=2, limit 3 →1; hai ngày mỗi ngày 2, limit 3 →0; không lấy max AM/PM hoặc đếm số ngày vi phạm |
| S04 | Window [2,3], double start3 phủ3–4 →1; start1 phủ1–2 →1; toàn bộ trong window →0; sessions khác không phạt |
| Aggregation | Scope nhiều GV; GV không demand=0; weight 3 × raw 2=6; S01+S04 cùng một tiết có hai dòng độc lập; candidate room không nhân penalty |
| Hard regression | Demand/split/locks/calendar/rooms/resource collision giữ nguyên; preference không cắt miền hard; strong soft không làm thiếu tiết |
| Evaluator sai chủ động | Missing/duplicate/foreign occurrence, sai GV, double sai footprint, stale result, forged score/report; không partial score; không import model helpers |
| Objective | Vét cạn bài nhỏ và đối chiếu lexicographic optimum, không chỉ score của solver; nhiều đơn vị penalty đúng; expression excess đúng khi tier chưa optimize |
| Priority | Fixture có trade-off: P1=0/P2=5 phải thắng P1=1/P2=0 dù weight P2 lớn; cùng tier chọn weighted sum nhỏ hơn |
| Time/status | Stub stage outcomes deterministic: tier OPTIMAL→FEASIBLE; UNKNOWN sau incumbent; hết budget trước tier; later INFEASIBLE; MODEL_INVALID; empty demand; no-soft; không tạo timing test flaky |
| Mismatch | Cố ý compiler sai coefficient/excess: evaluator phát hiện và solve không xuất lịch; forged result mismatch CLI exit 2 |
| Limits | Bound sát/ngang/vượt 2^53−1; intermediate int64 unsafe; placement/occupancy guards cũ; invalid params không thành INFEASIBLE |
| CLI/package | Solve 1.1→result1.2→validate-schedule/evaluate-score; installed wheel; evaluator chạy khi không cài OR-Tools; stdout JSON đúng và không lộ input |

Oracle test nhỏ tự enumerate mọi assignment hard-valid bằng Python độc lập, dùng expected hand-calculated cho từng penalty trước khi so optimum vector. Không chỉ cho solver và evaluator cùng gọi một hàm rồi kết luận đúng. Có ít nhất một fixture hard-valid với hai lịch khác chất lượng, chứng minh tối ưu cải thiện so lịch baseline đã cố định; không đòi solver feasibility tình cờ sinh đúng lịch xấu.

Measurement smoke sau triển khai ghi CPU/RAM/OS/Python/OR-Tools, sizes/placements/terms, seed/workers, time-to-feasible nếu đo, số stage, wall time, incumbent/bound/tier proof, validation và score. Chưa có benchmark nên không hứa tốc độ, không kết luận nhanh hơn FET/STKB hay phù hợp mọi trường.

## 10. File impact và thứ tự mốc sau khi được duyệt

| Thành phần dự kiến | Thay đổi khi triển khai, không thực hiện trong lượt này |
|---|---|
| domain/models, contracts/input/output/capabilities, exports | Version dispatch, rule ID/priority, typed config, ScoreReport/quality, guards/fingerprint |
| constraints/registry.py, constraints/soft.py | Static registry và bốn compilers; không dynamic plugin |
| solver/model_builder.py, solver/objectives.py, solver/cp_sat.py | Expressions/bounds, stage orchestration, incumbent/proof/budget; giữ built-in hard |
| validation/score_evaluator.py, independent_validator.py | Evaluator độc lập; shared capability gate cập nhật, không chuyển solver helpers thành oracle |
| cli.py | Version-aware I/O và evaluate-score; giữ an toàn output hiện tại |
| tests/unit, integration, properties, fixtures | Synthetic cases và oracle trên; không tạo fixture từ file trường |
| docs/domain-model, solver-design, constraint-catalog, README, phase-2-report | Contract/capability/CLI và kết quả thực khi có triển khai |

**2A — S01–S04 soft:** contract/registry → independent evaluator + expected cases → compilers → lexicographic orchestration → CLI/regression. Không công bố rule support trước khi cả compiler/evaluator và tests pass. Thứ tự viết code chi tiết thuộc implementation plan.

**2B — hard variants explicit:** cùng semantics tham số nhưng dùng hard mode: S01 raw=0, S02/S03 load≤limit, S04 raw=0; không có weight/priority. Bổ sung independent hard checker và capability cùng lượt. Soft và hard cùng family/scope/bucket không được bật trùng; caller chọn mode, không tự nâng. Chỉ bắt đầu khi có yêu cầu xác nhận và review riêng; 2A không quảng cáo đã hỗ trợ H10.

**2C — hoàn thiện quality Phase 2:** S05/S06 phân phối môn trước, rồi S07–S11 gaps/nghỉ và S12 từng use case. Mỗi rule có typed parameters/unit/compiler/evaluator/oracle như 2A; gaps cần calendar/occupied work đủ nghĩa theo policy. 2A chưa được ghi là nghiệm thu toàn Phase 2 khi các nhóm này chưa triển khai. Không tự triển khai 2B/2C trong nhiệm vụ chỉ viết đặc tả.

Điều kiện ra 2A: tất cả S01–S04 có penalty đúng và oracle xác nhận tối ưu bài nhỏ; regression Phase 1 giữ nguyên; deadline/status/proof không nhập nhằng; CLI/wheel/evaluator độc lập hoạt động; báo các lệnh thực chạy. Không yêu cầu có dữ liệu nhà trường thật để đạt mốc synthetic này; chưa được dùng kết quả đó làm nghiệm thu production.

## 11. Review tài liệu và quyết định còn mở

Các quyết định của người thiết kế để review: input 1.1/output 1.2; legacy 1.0 không tự migrate custom rules; strict scope không overlap; S01 timed dùng giao thời gian; P1–P3 tối ưu tuần tự và dừng khi chưa chứng minh tier; default proposal weight 1 nhưng payload explicit; custom hard để mốc riêng. Người dùng đã duyệt thiết kế, kế hoạch và triển khai trong phạm vi Phase2A; 2B/2C vẫn ngoài phạm vi.

Không còn yêu cầu nghiệp vụ bắt buộc phải đoán để lập plan cho synthetic 2A. Ngưỡng/rule áp dụng cho trường cụ thể và nguồn dữ liệu vẫn UNKNOWN, được application xác nhận trước khi tạo input. Benchmark, hiệu chỉnh weight và review pháp lý khi tái sử dụng mã không được thay bằng suy luận từ tài liệu.

### Kết quả builder check

Reviewer độc lập đã đọc đặc tả và code hiện tại, nêu hai vấn đề: gate session mới xung đột semantics timed aliases của Phase 1, và fingerprint chưa phân biệt known sets với unknown arrays. Đã xử lý: giữ timeline gates Phase 1, bucket theo slot được chọn; chỉ sort known parameter sets, giữ thứ tự array của unknown disabled code. Review lại đã xác nhận hết hai blocker; một lưu ý bổ sung về availability theo slot ID so với S01 theo giao phút cũng đã được làm rõ ở mục 5.2. Không còn câu hỏi quan trọng cản lập plan 2A theo reviewer. Đây là review tài liệu, không phải kiểm thử implementation.

Đã kiểm tra local links, JSON minh họa và `git diff --check`; xác nhận không có diff trong `src/`, `tests/`, `pyproject.toml`, `uv.lock`. Không chạy pytest/benchmark/lint/type-check cho lượt chỉ cập nhật Markdown; chưa có Phase 2 code để nghiệm thu.
