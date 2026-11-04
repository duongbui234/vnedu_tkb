# Phase 2B — hard variants explicit cho S01–S04

Ngày 2026-11-05. Trạng thái: **D1–D7 ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT THEO ĐỀ XUẤT; ĐÃ TRIỂN KHAI
(technical synthetic)** — xem [báo cáo 2B](../../phase-2b-report.md). Đoạn dưới là bản đặc tả
được duyệt; các ghi chú “chưa triển khai” trong thân bài phản ánh thời điểm soạn.
Base: `124b89d318467421dedf421f8d1c9a6b72b6991e`, nhánh `work/phase2a-operational-completion`.

Tài liệu này chỉ là đặc tả. Không sửa `src/`, `tests/`, `benchmarks/`, dependency, gate,
budget hoặc evidence; không chạy solver/pilot/campaign; không commit/merge/push. Việc duyệt
đặc tả chưa phải ủy quyền triển khai. Phase 2A vẫn chỉ là mốc **technical synthetic**;
acceptance v2 vẫn DRAFT; Windows/cross-OS và chất lượng giáo vụ vẫn chưa nghiệm thu.
2B không thay đổi, không bù đắp và không dựa vào các hạng mục còn mở đó.

## 1. Căn cứ và mục tiêu

Nguồn: [Đặc tả Phase 2 mục 10/2B](2026-10-26-phase-2-quality-design.md), [policy H10](../../research/stkb/09-vnedu-hard-soft-policy.md),
[catalog](../../constraint-catalog.md), [cloud handoff](../../phase-2a-cloud-handoff.md).

- **VERIFIED (code tại base):** `contracts/capabilities.py:23–28` từ chối mọi enabled hard
  trên input 1.1 bằng `UNSUPPORTED_FEATURE/CUSTOM_HARD_RULE`. `HardConstraintConfigV11`
  (`domain/models.py`) đã có `id/code/scope/parameters/enabled`, không có priority/weight.
- **VERIFIED:** `contracts/input.py::check_references` đã parse tham số và tham chiếu của
  known code cho cả hard lẫn soft; `fingerprint()` 1.1 đã sort hard theo id và sort
  `slot_ids/session_ids` của known code. `registry.validate_rule_config` chỉ kiểm overlap
  giữa các **soft** enabled cùng code.
- **VERIFIED:** `RuleDefinition.supported_modes=("soft",)` cho cả bốn code;
  `QualityReport.policy_version` và `ConstraintConfigV11.policy_version` là `Literal["0.1"]`.
- **VERIFIED:** `solver/cp_sat.py` clone `hard_model` sau `build_model` và trước
  `compile_soft`; nhánh không có soft active gọi CP-SAT trực tiếp trên `built.model`.
  `model_builder._add_interchangeable_ordering` tắt ngay khi có enabled hard.
- **INFERRED:** mọi tên code/diagnostic/version dưới đây là đề xuất mới, chưa tồn tại.
- **UNKNOWN:** ngưỡng hard thực tế của trường. 2B chỉ cung cấp cơ chế; application phải
  xác nhận từng hard rule (H10) trước khi tạo input. Không tự nâng soft thành hard.

**Mục tiêu 2B:** caller có thể khai báo S01–S04 ở **hard mode** với cùng tham số/scope như
2A; Core chặn mọi lịch vi phạm, independent validator kiểm lại từ assignments, capability
chỉ được công bố khi compiler + validator + oracle tests cùng hoàn chỉnh.

**Ngoài phạm vi:** S05–S12, gaps/spacing (2C), hard variant cho class/subject/room scope,
relax/diagnose-IIS, repair, auto-migrate soft→hard, Desktop/SQLite/API, thay gate/budget,
generator/harness/campaign mới, tuyên bố hiệu năng.

## 2. Contract và version

### 2.1 Input: schema 1.1 + policy 0.2 (D1)

- Giữ input 1.0 và input 1.1/policy `0.1` **byte-for-byte cùng hành vi**: enabled hard vẫn
  `UNSUPPORTED_FEATURE/CUSTOM_HARD_RULE`, fingerprint không đổi.
- Thêm `policy_version: "0.2"` (input schema vẫn `1.1`). Chỉ policy 0.2 mở hard mode cho
  S01–S04. Soft của 0.2 giữ nguyên semantics 0.1.
- Lý do: một payload 0.1 có enabled hard hôm nay là UNSUPPORTED; nếu cùng payload bỗng được
  giải thì kết quả lịch sử không còn tái lập được. Version tách biệt làm rõ ý định caller.
- Dispatch theo version trước validation, không fallback 0.2→0.1. Version lạ → INPUT_INVALID.
- Hard envelope giữ shape hiện có; `priority`/`weight` trên hard vẫn bị extra-forbid.

Fragment ví dụ (không phải input hoàn chỉnh):

```json
{
  "policy_version": "0.2",
  "hard": [
    {"id": "hard-a-day", "code": "TEACHER_MAX_PERIODS_PER_DAY",
     "scope": {"teacher_ids": ["teacher-a"]}, "parameters": {"limit": 4}, "enabled": true}
  ],
  "soft": [
    {"id": "pref-a-am", "code": "TEACHER_MAX_PERIODS_PER_SESSION",
     "scope": {"teacher_ids": ["teacher-a"]}, "parameters": {"limit": 3, "session_ids": ["AM"]},
     "enabled": true, "priority": 1, "weight": 1}
  ]
}
```

### 2.2 Fingerprint

Không đổi thuật toán: `policy_version` đã nằm trong payload nên 0.2 khác hash 0.1. Hard
rules sort theo id; known sets sort như 2A. Regression bắt buộc: hard/soft đổi chỗ trong
cùng danh sách, đảo `slot_ids/session_ids` không đổi hash; chuyển một rule từ `soft` sang
`hard` (cùng id/code/params) **phải** đổi hash; đổi `enabled` của hard đổi hash.

### 2.3 Output: ScheduleResult 1.3 cho policy 0.2 (D2)

`QualityReport.policy_version` hiện là literal `"0.1"`; nới literal trong 1.2 sẽ làm một
parser 1.2 strict cũ đọc sai ngữ nghĩa. Đề xuất: input policy 0.2 → **output 1.3**, cùng shape
1.2, khác ở:

- `quality.policy_version: "0.2"`; `quality` luôn có mặt (kể cả chỉ hard → `NOT_REQUESTED`).
- `validation.violations` có thể chứa các diagnostic hard-variant ở §4.
- Không thêm field liệt kê hard rules; hard rules không có dòng score.

Input policy 0.1 tiếp tục phát 1.2; input 1.0 phát 1.1. Parser output đọc 1.0–1.3 và kiểm
cặp (output version, policy version) nhất quán. ScoreReport giữ `1.0` (rows chỉ là soft).

## 3. Semantics hard

Dùng đúng calendar/footprint/bucket của 2A §5.1: covered period thật của placement đã chọn,
day/session của slot đã chọn, timed aliases xét giao phút nửa mở. Scope chỉ teacher; tập rỗng
= mọi GV trong snapshot. Disabled hard được mang theo/fingerprint, không enforce.

| Code | Hard mode yêu cầu với mọi GV trong scope |
|---|---|
| S01 TEACHER_AVOID_SLOTS | Không covered period nào trùng ô tránh (symbolic: cùng slot ID; timed: giao phút với bất kỳ `slot_ids`). Tương đương raw S01 = 0 |
| S02 TEACHER_MAX_PERIODS_PER_SESSION | Với mọi day và mọi session trong `session_ids`: `teaching_periods[t,d,s] ≤ limit` |
| S03 TEACHER_MAX_PERIODS_PER_DAY | Với mọi day: `Σ_s teaching_periods[t,d,s] ≤ limit` |
| S04 TEACHER_PREFERRED_PERIOD_WINDOW | Mọi covered period thuộc session trong `session_ids` có `first ≤ period ≤ last`; double kiểm cả tiết hai. Raw S04 = 0 |

- `limit=0` hợp lệ: GV không được dạy trong bucket đó; demand mâu thuẫn → INFEASIBLE.
- S01 hard **không** thay thế availability; nó cấm cả slot alias giao phút với ô tránh (khác
  availability theo slot ID). Đây là semantics có chủ ý, phải nêu trong catalog.
- Hard không có weight/priority, không là penalty lớn, không bị nới khi timeout/infeasible.
- Không đổi tên code theo mode; mode xác định bởi danh sách `hard` hay `soft` chứa rule.

### 3.1 Overlap và kết hợp (D4)

- Cùng family (cùng code), cùng GV và cùng bucket theo quy tắc overlap 2A §3.2 → **INPUT_INVALID/
  OVERLAPPING_RULES bất kể mode**: soft+soft (như cũ), hard+soft và hard+hard. Application phải
  resolve một scope hiệu lực; Core không chọn rule chặt hơn, không gộp.
- Khác family được phép kết hợp, ví dụ hard S03 + soft S02, hard S04 + soft S01. Soft vẫn chỉ
  chấm điểm trên tập lịch đã thỏa hard.
- Kiểm overlap dùng tập enabled hard ∪ soft; disabled không tham gia.

### 3.2 Capability matrix

| Input | Enabled hard S01–S04 | Enabled hard code khác/unknown | Soft S01–S04 |
|---|---|---|---|
| 1.0 | UNSUPPORTED/CUSTOM_RULE (giữ) | UNSUPPORTED (giữ) | UNSUPPORTED (giữ) |
| 1.1 / 0.1 | UNSUPPORTED/CUSTOM_HARD_RULE (giữ) | UNSUPPORTED (giữ) | Hỗ trợ (2A) |
| 1.1 / 0.2 | **Hỗ trợ** | UNSUPPORTED/UNKNOWN_RULE | Hỗ trợ (2A) |

Scope class/subject/room trên hard → UNSUPPORTED/RULE_SCOPE. Tham số sai, reference sai,
duplicate → INPUT_INVALID (kể cả disabled known code), như 2A.
`RuleDefinition` thêm mode theo policy (ví dụ `supported_modes_by_policy`), không dựa vào
một tuple dùng chung cho mọi version.

## 4. Independent hard checker

`validation/independent_validator.validate_schedule` kiểm thêm các hard variants đã bật, tự
dựng footprint/loads từ assignments + demand/split + calendar như phần hiện có. **Không import**
`constraints/*`, `preprocessing.prepare`, `solver/*` hoặc `score_evaluator`; không dùng
chung helper tính intersection/load/window với compiler hay soft evaluator. Chỉ dùng chung
domain types, parameter models và registry metadata.

Violation codes đề xuất (không kèm raw records):

| Code | resource_ids | slot_ids | occurrence_ids |
|---|---|---|---|
| `HARD_AVOID_SLOT` | (teacher,) | covered slot vi phạm | occurrence |
| `HARD_SESSION_LIMIT` | (teacher,) | các slot của bucket | các occurrence của bucket |
| `HARD_DAY_LIMIT` | (teacher,) | các slot của ngày | các occurrence của ngày |
| `HARD_PERIOD_WINDOW` | (teacher,) | covered slot ngoài window | occurrence |

Vì non-overlap đảm bảo mỗi (family, GV, bucket) thuộc tối đa một rule, bộ (code, teacher,
slot) xác định được rule mà không cần thêm field `rule_id` vào `Diagnostic` (giữ schema).

`evaluate_score` gọi validator trước nên lịch vi phạm hard variant → `INVALID_SCHEDULE`, không
partial score. `validate-schedule` và `evaluate-score` CLI dùng cùng capability gate.

## 5. Compiler và solve pipeline

### 5.1 Placement-local: S01/S04 lọc domain (D3)

S01/S04 hard chỉ phụ thuộc placement → loại placement vi phạm trong `prepare`, cùng chỗ với
availability, **trước** các precheck cần thiết. Hệ quả có chủ ý:

- Domain rỗng → `INFEASIBLE/EMPTY_DOMAIN`; capacity → `INFEASIBLE/RESOURCE_CAPACITY` như cũ.
  Đây là chứng minh đúng vì rule đã là hard.
- Slot lock vi phạm S01/S04 hard → `INPUT_INVALID/LOCK_CONFLICT` (cùng xử lý với lock trái
  availability). Lock không tự thắng hard rule.
- Predicate lọc nằm trong module compiler mới `constraints/hard_variants.py` (không phụ thuộc
  OR-Tools), không dùng lại code của soft compiler hoặc evaluator.
- `S03 bounds` dẫn xuất từ domain đã lọc vẫn hợp lệ (chỉ chặt hơn); không cần sửa.

### 5.2 Aggregate: S02/S03 ràng buộc tuyến tính

Trong `build_model` (hiện thực ở `constraints/hard.add_load_limits`), sau occupancy, với mỗi bucket (t,d[,s]) có placement: `Σ duration·x ≤ limit`
(dùng covered periods theo session/day của slot đã chọn; double nằm trọn một session/day).
Thêm vào `built.model` **trước** khi `cp_sat.solve` clone `hard_model`, để lượt feasibility,
các tier, zero-probe và hint đều thấy cùng tập hard. Kiểm `limit` và tổng hệ số trong signed
int64 trước khi thêm ràng buộc; vượt → `INPUT_INVALID/HARD_RULE_RANGE` trước solve, không clip.

Không thêm precheck tổng hợp mới cho S02/S03 trong 2B (D6): CP-SAT chứng minh INFEASIBLE.
Precheck chặt hơn có thể làm sau, khi có oracle chứng minh là điều kiện cần.

### 5.3 Symmetry ordering (D5)

`_add_interchangeable_ordering` hiện tắt khi có enabled hard. S01–S04 hard chỉ phụ thuộc
teacher/day/session/period của placement, nên hoán vị nhãn occurrence cùng requirement, cùng
duration và cùng domain (sau lọc) bảo toàn tính hợp lệ và điểm. Đề xuất cho phép ordering khi
mọi enabled hard thuộc tập resource-only S01–S04, **chỉ sau** oracle vét cạn chứng minh tập
vector tối ưu không đổi với/không ordering trên fixture có hard variants. Nếu oracle không đạt,
giữ tắt — không chặn phần còn lại của 2B.

### 5.4 Status và quality

- Không soft active, có hard variants → nhánh feasibility hiện có; output 1.3 với
  `quality.status = NOT_REQUESTED` và score rỗng đã kiểm. Không gọi lịch là “tối ưu chất lượng”.
- Có soft active → `run_quality` như 2A; mọi incumbent đã thỏa hard variants vì cùng model.
  Tier INFEASIBLE sau incumbent hợp lệ vẫn là `MODEL_INVALID/INTERNAL_STAGE_INCONSISTENCY`.
- `INFEASIBLE` nghĩa là vô nghiệm với built-ins **cộng** hard variants đã khai báo. 2B không
  chỉ ra rule gây vô nghiệm (không IIS/relax); diagnostic không được ngụ ý nguyên nhân cụ thể.
- Independent validator từ chối lịch của solver → `MODEL_INVALID/INTERNAL_VALIDATION_FAILED`,
  không xuất assignments (như hiện tại).
- Empty demand + hard variants: FEASIBLE/EMPTY_PROBLEM, validator không có vi phạm.

## 6. Tests và oracle bắt buộc (chưa viết/chạy)

Fixture synthetic, ID opaque, không dữ liệu thật. Giữ toàn bộ regression Phase 0/1/2A.

| Nhóm | Ca có expected độc lập |
|---|---|
| Version | 0.1 + enabled hard vẫn CUSTOM_HARD_RULE; 0.2 roundtrip; 0.2 → output 1.3; policy lạ reject; 1.0 không đổi hash/hành vi; output 1.3/policy mismatch reject |
| Contract | priority/weight trên hard reject; scope class/subject/room → RULE_SCOPE; params sai kể cả disabled; unknown enabled hard → UNKNOWN_RULE |
| Overlap | hard+soft cùng family/GV/bucket; hard+hard; S01 timed aliases; S02 session giao nhau; khác family được phép; disabled không tính |
| Fingerprint | Như §2.2 |
| S01 | Ô tránh duy nhất trống → INFEASIBLE/EMPTY_DOMAIN; double chạm tiết hai bị loại; timed alias giao phút bị loại; lock vào ô tránh → LOCK_CONFLICT |
| S02/S03 | load = limit hợp lệ; limit+1 bị cấm; limit=0; double tính 2; AM/PM tách (S02) và cộng (S03); demand vượt Σ limit → INFEASIBLE |
| S04 | Window [2,3]: start3 double (3–4) bị loại, start2 double hợp lệ; session ngoài `session_ids` không bị ràng buộc |
| Validator | Lịch forged vi phạm từng family → đúng code/resource/slot; không import compiler (kiểm bằng import graph test như 2A) |
| Oracle | Vét cạn bài nhỏ: tập lịch hard-valid ≡ tập solver có thể trả; FEASIBLE/INFEASIBLE khớp brute force; hard+soft optimum vector khớp brute force trên tập đã lọc |
| Mismatch | Compiler cố ý sai (bỏ một bucket) → validator bắt, solve trả MODEL_INVALID, không xuất lịch |
| Pipeline | Không soft: NOT_REQUESTED; có soft: tier runs như 2A; stub stage INFEASIBLE sau incumbent → INTERNAL_STAGE_INCONSISTENCY; zero-probe clone chứa hard |
| Ordering | Nếu bật D5: optimum vector bằng nhau với/không ordering trên fixture hard |
| CLI/package | solve 0.2 → 1.3 → validate-schedule/evaluate-score; evaluate-score không cần OR-Tools; forged result vi phạm hard → exit 2 |

Không cần pilot/campaign để đạt mốc 2B synthetic. Measurement smoke (nếu được ủy quyền riêng)
chỉ ghi số đo thật, không so sánh với gate Phase 2A.

## 7. Điều kiện ra 2B (technical synthetic)

Bốn hard variants có compiler + independent checker + capability cùng lượt; oracle xác nhận
FEASIBLE/INFEASIBLE và optimum vector trên bài nhỏ; policy 0.1/input 1.0 không đổi hành vi
hay hash; mọi lệnh trong AGENTS.md PASS và được báo đúng lệnh thực chạy. 2B không chứng nhận
ngưỡng trường, hiệu năng, Windows/cross-OS hay chất lượng giáo vụ.

## 8. Quyết định cần duyệt

- [x] **D1** — policy `0.2` (schema input 1.1) mở hard; policy 0.1 giữ nguyên. *(Đề xuất: chọn)*
- [x] **D2** — output `1.3` cho policy 0.2; 1.2 giữ literal 0.1. *(Đề xuất: chọn)*
- [x] **D3** — S01/S04 hard lọc domain trong `prepare`; lock trái hard → LOCK_CONFLICT. *(Đề xuất: chọn; thay thế: ràng buộc `x=0` trong model, giữ domain/precheck như cũ)*
- [x] **D4** — overlap cùng family bị cấm bất kể mode (kể cả hard+hard). *(Đề xuất: chọn)*
- [x] **D5** — bật symmetry ordering với hard S01–S04 có điều kiện oracle. *(Đề xuất: chọn có điều kiện)*
- [x] **D6** — không thêm precheck tổng hợp S02/S03 trong 2B. *(Đề xuất: chọn)*
- [x] **D7** — violation codes `HARD_*` giữ schema `Diagnostic`, không thêm `rule_id`. *(Đề xuất: chọn)*
