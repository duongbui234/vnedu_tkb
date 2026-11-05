# Phase 2C-1 — phân phối môn S05/S06

Ngày 2026-11-05. Trạng thái: **DRAFT — CHỜ DUYỆT, CHƯA TRIỂN KHAI.**
Base: `7e83fd349772412289b34864d89199c200e3ffdf` (merge của duongbui234/vnedu_tkb#1 vào `main`),
nhánh `work/phase2a-operational-completion` được đặt lại từ `origin/main`.

Đây chỉ là đặc tả. Không sửa `src/`, `tests/`, `benchmarks/`, dependency, gate hay budget; không chạy
solver/campaign; không commit/push trước khi được duyệt. 2C-1 chỉ gồm S05/S06. Gaps/nghỉ (S07–S11) và
S12 là các mốc sau. Hạn chế của Phase 2A/2B giữ nguyên: chỉ synthetic, Windows chưa nghiệm thu,
acceptance v2 DRAFT, zero NOT_MET, primary 0/108.

## 1. Căn cứ

- [Core First §10/Phase 2](../../VNEDU_TKB_CORE_FIRST_CODEX.md): “phân phối môn” thuộc Phase 2.
- [Policy 0.1 §4](../../research/stkb/09-vnedu-hard-soft-policy.md):
  - S05 (P1): “mỗi unordered pair component trong explicit group: `max(0,k−abs(day_i−day_j))` ngày
    thiếu; k và group phải có; không tự gom mọi activity cùng tên môn; không thêm consecutive/cap
    cùng ngày ngầm theo FET”.
  - S06 (P1): “số tiết vượt max của class+subject+realday; chỉ cấu hình riêng; không hardcode 2
    tiết/ngày”.
  - Khoảng cách ngày S05 dùng “thứ tự ngày thực trong cycle, tính tuyến tính; không vòng tuần, không
    half-day”. Split `[2,1,1,1]` là 4 components / 6 cặp; block đôi vẫn là 2 tiết khi tính tải.
  - H10 liệt kê “môn/ngày, spacing **bắt buộc** — chỉ trường xác nhận” là candidate hard.
- [Đặc tả Phase 2 §10/2C](2026-10-26-phase-2-quality-design.md): mỗi rule cần typed parameters, unit,
  compiler, evaluator và oracle như 2A. [Đặc tả 2B](2026-11-05-phase-2b-hard-variants-design.md): mẫu
  hard variant, policy theo version, overlap mọi mode.
- **VERIFIED (code tại base):**
  - `RuleScore.unit` là `Literal["teaching_periods"]`; `ScoreReport.schema_version` là `"1.0"`.
  - `RuleScope` có `class_ids/teacher_ids/subject_ids/room_ids`. `registry.validate_rule_config` từ
    chối mọi scope khác teacher.
  - `TeachingRequirement` có đúng một `subject_id`; capability chỉ nhận một lớp và một GV.
  - Occurrence = component; một block đôi là một occurrence (một Boolean/placement).
  - `_add_interchangeable_ordering` chỉ chạy khi mọi rule bật nằm trong `_RESOURCE_ONLY_SOFT_RULES`.
- **UNKNOWN:** giá trị k, nhóm component và max/ngày thực tế của trường. Core không có mặc định.

## 2. Contract và version (D1, D2)

- **D1 — policy `0.3`** (input schema vẫn 1.1) thêm S05/S06 ở cả soft và hard. Policy 0.1/0.2 giữ
  nguyên capability và fingerprint: S05/S06 enabled ở đó vẫn là `UNSUPPORTED_FEATURE/UNKNOWN_RULE`.
  Lý do giống D1 của 2B: cùng payload không đổi từ “bị từ chối” sang “được giải” trong một policy đã
  phát hành. Policy 0.3 bao gồm toàn bộ semantics S01–S04 (soft + hard) của 0.2.
- **D2 — output `1.4`** cho policy 0.3, cùng shape 1.3, và **ScoreReport `1.1`**. ScoreReport 1.1 cho
  phép `unit ∈ {"teaching_periods", "day_gap_shortfall"}`; ScoreReport 1.0 giữ literal cũ. Output
  1.2/1.3 chỉ chứa ScoreReport 1.0; output 1.4 chỉ chứa 1.1. Reader kiểm cặp (output, policy, score).
- `evaluate-score` in ScoreReport 1.1 khi input là policy 0.3. CLI `RESULT_VERSION` mở rộng: 0.3 → 1.4.

## 3. Semantics

### 3.1 S05 `SUBJECT_COMPONENT_DAY_SPREAD`

- **Parameters:** `requirement_ids` (tập không rỗng, không trùng, phải tồn tại) và `min_day_gap`
  (int ≥ 1). Scope phải rỗng: nhóm do `requirement_ids` xác định, không suy từ tên môn hay lớp (D3).
- **Nhóm:** mọi occurrence (component) của các requirement đã liệt kê. Block đôi là một component.
- **Khoảng cách:** `|day_i − day_j|` theo giá trị `TimeSlot.day` của start slot (D4). Không vòng tuần;
  ngày không có slot vẫn được tính trong hiệu.
- **Soft raw (unit `day_gap_shortfall`):** `Σ_{i<j} max(0, k − |day_i − day_j|)` trên mọi cặp không
  thứ tự trong nhóm. Nhóm < 2 component → 0, rule vẫn có dòng điểm.
- **Hard:** mọi cặp có `|day_i − day_j| ≥ k`.
- **Ví dụ:** k=2, components ngày (1,1,3): cặp (1,1)→2, (1,3)→0, (1,3)→0 ⇒ raw 2. Split `[2,1,1,1]`
  → 6 cặp.
- S05 không ngầm thêm cap cùng ngày (S06) hay điều kiện liên tiếp.

### 3.2 S06 `CLASS_SUBJECT_MAX_PERIODS_PER_DAY`

- **Parameters:** `limit` (int ≥ 0). **Scope:** `class_ids` và `subject_ids` (rỗng = mọi lớp / mọi
  môn trong snapshot); `teacher_ids` và `room_ids` phải rỗng (D5).
- **Tải:** `periods[c,s,d]` = số tiết dạy (covered periods, double = 2) của mọi requirement có lớp
  `c`, môn `s`, start slot ngày `d`, cộng mọi buổi trong ngày.
- **Soft raw (unit `teaching_periods`):** `Σ_{c,s,d} max(0, periods[c,s,d] − limit)` trên các cặp
  (c,s) trong scope và mọi ngày calendar.
- **Hard:** `periods[c,s,d] ≤ limit` với mọi (c,s,d) trong scope.
- Scope rỗng hoàn toàn là cấu hình explicit hợp lệ (“mọi lớp/môn, limit đã chọn”), không phải mặc
  định ngầm; Core không có limit mặc định.

### 3.3 Overlap và kết hợp (theo D4 của 2B)

- S05–S05 (mọi mode): overlap khi hai rule có chung ít nhất một requirement → `OVERLAPPING_RULES`.
- S06–S06 (mọi mode): overlap khi tập (lớp × môn) hiệu lực giao nhau.
- Khác family được phép (S05 + S06, S06 + S03…). S06 không trùng family với S03 (S03 theo GV).
- Scope không hợp lệ (S05 có scope, S06 có teacher/room) → `UNSUPPORTED_FEATURE/RULE_SCOPE`.

## 4. Compiler (CP-SAT) và precheck

- **Biểu thức ngày:** với occurrence o, `day_o = Σ_p day(start(p))·x_p` (tuyến tính, đúng một
  placement được chọn).
- **S05 soft:** với mỗi cặp (i,j): `diff = day_i − day_j`; `dist = |diff|` bằng `AddAbsEquality`;
  `short = max(0, k − dist)` bằng `AddMaxEquality`. Raw = Σ short, ràng buộc bằng **equality** (như S02/S03
  của 2A), không dựa vào objective kéo xuống. Bound: `C(n,2)·k`, kiểm int64 và 2^53−1 như 2A.
- **S05 hard (D6):** với mỗi cửa sổ `W = [d, d+k−1]` trên trục ngày, `Σ_{o∈nhóm} Σ_{p: day(p)∈W} x_p ≤ 1`.
  Tương đương “mọi cặp cách ≥ k” trên số nguyên và không cần biến phụ. Chỉ thêm cửa sổ có ≥ 2 hạng tử.
- **S06 soft/hard:** bucket (c,s,d) = `Σ duration·x`. Soft dùng `AddMaxEquality(excess, [0, load−limit])`;
  hard dùng `load ≤ limit`. Cả hai thêm trong model trước clone `hard_model` (hard) hoặc trong
  `compile_soft` (soft).
- **Precheck:** không thêm precheck tổng hợp mới (theo D6 của 2B). Solver chứng minh INFEASIBLE.
  Lock tổ hợp vượt hard S05/S06 → INFEASIBLE, không phải `LOCK_CONFLICT`.
- **Symmetry ordering (D7):** S05/S06 chỉ phụ thuộc requirement/lớp/môn/ngày, nên bất biến khi hoán vị
  các occurrence cùng requirement, cùng duration và cùng domain. Đề xuất thêm vào allowlist **chỉ sau**
  oracle vét cạn so optimum có/không ordering, như D5 của 2B.

## 5. Evaluator và validator độc lập

- `score_evaluator` tự tính day của từng component từ start slot và tải (c,s,d) từ footprint. Không
  import compiler, `prepare`, OR-Tools. Không dùng chung helper tính cặp/tải với compiler.
- `independent_validator` thêm hard checks:
  - `HARD_DAY_SPREAD`: resource_ids = các requirement của cặp, slot_ids = hai start slot,
    occurrence_ids = cặp vi phạm.
  - `HARD_SUBJECT_DAY_LIMIT`: resource_ids = (lớp, môn), slot_ids/occurrence_ids của bucket.
- Lịch vi phạm hard → `INVALID_SCHEDULE` trong `evaluate_score`, không partial score.

## 6. Tests và oracle bắt buộc (chưa viết/chạy)

| Nhóm | Ca có expected độc lập |
|---|---|
| Version | 0.1/0.2 + S05/S06 enabled → UNKNOWN_RULE; 0.3 → output 1.4 + ScoreReport 1.1; cặp sai bị reject; hash 0.1/0.2 không đổi |
| Contract | `min_day_gap=0`, requirement lạ/trùng, S05 có scope, S06 có teacher scope → lỗi đúng mã |
| Overlap | S05 chung requirement; S06 giao lớp×môn; hard+soft; khác family được phép |
| S05 | Ví dụ §3.1; split `[2,1,1,1]` = 6 cặp; nhóm 1 component = 0; nhiều requirement trong một nhóm; ngày không liên tục dùng hiệu giá trị |
| S06 | double = 2; AM+PM cộng trong ngày; limit 0; scope rỗng; scope theo lớp/môn |
| Hard | S05 cửa sổ ≡ cặp (forged + brute force); S06 load = limit hợp lệ, +1 bị cấm; INFEASIBLE khi k quá lớn |
| Validator/evaluator | Lịch forged từng family; cô lập import (subprocess guard như 2B) |
| Oracle | Vét cạn bài nhỏ: feasibility và optimum vector với S05/S06 soft+hard trộn S01–S04; ordering bật/tắt |
| Mismatch | Compiler cố ý sai (bỏ một cặp/bucket) → MODEL_INVALID, không xuất lịch |
| CLI/package | solve 0.3 → 1.4 → validate/evaluate; evaluate-score không cần OR-Tools; RESULT_VERSION cho cặp sai |

## 7. Điều kiện ra 2C-1 (technical synthetic)

S05/S06 soft + hard có compiler, evaluator, validator và oracle; policy 0.1/0.2 và input 1.0 không
đổi hành vi/hash; mọi lệnh AGENTS.md PASS và được báo đúng. Không chứng nhận ngưỡng trường, chất
lượng giáo vụ, hiệu năng hay Windows.

## 8. Quyết định cần duyệt

- [ ] **D1** — policy `0.3` cho S05/S06; 0.1/0.2 giữ nguyên. *(Đề xuất: chọn. Thay thế: thêm vào 0.2 —
  đơn giản hơn nhưng đổi capability của policy đã phát hành.)*
- [ ] **D2** — output `1.4` và ScoreReport `1.1` (thêm unit `day_gap_shortfall`). *(Đề xuất: chọn.)*
- [ ] **D3** — S05 nhóm bằng `requirement_ids` explicit, một nhóm mỗi rule. *(Đề xuất: chọn. Thay thế:
  scope lớp+môn tự lập nhóm mỗi (lớp,môn) — tiện hơn nhưng gần với “tự gom” mà policy cấm.)*
- [ ] **D4** — khoảng cách ngày theo giá trị `day`, không theo thứ hạng ngày có slot. *(Đề xuất: chọn.
  Thay thế: thứ hạng — bỏ qua ngày không có slot.)*
- [ ] **D5** — S06 dùng scope `class_ids`/`subject_ids` (rỗng = tất cả). *(Đề xuất: chọn.)*
- [ ] **D6** — có hard mode cho S05 (cửa sổ k ngày) và S06 trong cùng mốc. *(Đề xuất: chọn. Thay thế:
  chỉ soft, hard để mốc sau.)*
- [ ] **D7** — bật symmetry ordering với S05/S06 nếu oracle đạt; nếu không thì giữ tắt. *(Đề xuất: chọn.)*
