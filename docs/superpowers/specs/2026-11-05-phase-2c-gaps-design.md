# Phase 2C-2 — ô hạn chế, tiết trống và ngày nghỉ S07–S11

Ngày 2026-11-05. Trạng thái: **DRAFT — CHỜ DUYỆT, CHƯA TRIỂN KHAI.**
Base: `45f63eec0380b22e60b4a4ab83a790cbe0f4921e` (merge của duongbui234/vnedu_tkb#2 vào `main`),
nhánh `work/phase2a-operational-completion` được đặt lại từ `origin/main`.

Đây chỉ là đặc tả. Không sửa `src/`, `tests/`, `benchmarks/`, dependency, gate hay budget; không chạy
solver/campaign; không commit/push trước khi được duyệt. S12 là mốc sau. Hạn chế đã có giữ nguyên:
chỉ synthetic, Windows chưa nghiệm thu, acceptance v2 DRAFT, zero NOT_MET, primary 0/108.

## 1. Căn cứ

- [Policy 0.1 §4](../../research/stkb/09-vnedu-hard-soft-policy.md):
  - **S07 (P2):** số tiết dạy ở ô Hạn chế đã xác nhận; “cùng GV/slot không tính lặp S01 và S07”.
  - **S08 (P2):** tổng số tiết idle theo định nghĩa gap; phân biệt objective tổng với threshold.
  - **S09 (P2):** theo GV+ngày+buổi, `max(0, longest_idle_run − limit)`; không phạt bằng số buổi.
  - **S10 (P2):** `max(0, target_free − actual_free)` theo unit đã chọn; không bật cả hai unit chỉ vì
    cùng tên; calendar/cycle đủ điều kiện phải rõ.
  - **S11 (P2):** 1 cho mỗi GV/ngày/buổi có tải dạy đúng 1; không áp lên lớp, không phạt buổi trống.
  - **Định nghĩa gap:** xét từng GV/ngày/buổi, chỉ giữa tiết dạy đầu và cuối. Ô `can_teach=false` không
    tính gap và **cắt chuỗi**; ô họp bắt buộc đã xác nhận là occupied work, không idle, không cộng tải;
    ô GV không thể dạy vẫn là gap nếu là tiết dạy của trường nằm giữa hai tiết dạy và không có occupied
    work. Compiler và evaluator phải dùng cùng calendar/occupied work; `available_slot_ids` không đủ.
  - H09: họp/sự kiện bắt buộc có thể compile thành unavailability hiện có.
- [Đặc tả Phase 2 §10/2C](2026-10-26-phase-2-quality-design.md): “gaps cần calendar/occupied work đủ
  nghĩa”. [Đặc tả 2C-1](2026-11-05-phase-2c-subject-distribution-design.md): mẫu version, overlap,
  ordering, oracle.
- **VERIFIED (code tại base):** input chưa có khái niệm occupied work; `TimeSlot` có
  `day/session/period/can_teach/start_minute/end_minute`; `Teacher.available_slot_ids`; registry có
  `soft_policies/hard_policies/since_policy/scope`; policy mới nhất 0.3 ↔ output 1.4 ↔ ScoreReport 1.1.
- **UNKNOWN:** ô Hạn chế, lịch họp, ngưỡng gap và số ngày nghỉ mong muốn thực tế. Core không có mặc định.

## 2. Contract và version (D1, D2)

- **D1 — policy `0.4`** thêm S07–S11 (chỉ soft, xem D5). 0.1–0.3 giữ nguyên capability và hash; các mã
  mới có `since_policy="0.4"`.
- **D2 — output `1.5` và ScoreReport `1.2`**. ScoreReport 1.2 thêm unit `idle_periods`, `free_days`,
  `free_sessions`, `single_period_sessions`. Cặp (output, policy, score): 1.5 ↔ 0.4 ↔ 1.2.

## 3. Occupied work (D3)

Đề xuất thêm `constraint_config.occupied_work`, **chỉ hợp lệ khi policy 0.4**:

```json
{"occupied_work": [{"teacher_id": "teacher-a", "slot_ids": ["1-AM-3", "2-PM-1"]}]}
```

- Một entry mỗi GV (trùng `teacher_id` → INPUT_INVALID); `slot_ids` là tập không rỗng, tồn tại, không
  trùng. Fingerprint sort entries theo `teacher_id` và sort `slot_ids`.
- **Phải nằm ngoài availability của GV đó:** nếu `available_slot_ids` là `null` (dạy được mọi ô) hoặc
  chứa slot occupied → INPUT_INVALID/OCCUPIED_AVAILABLE. Upstream phải loại ô họp khỏi availability
  (H09), nên Core không xếp dạy vào ô họp mà không cần ràng buộc mới.
- Với policy 0.1–0.3: field không được có mặt (khác rỗng → INPUT_INVALID) và **không xuất hiện** trong
  dump/fingerprint, nên hash cũ không đổi.
- Occupied work chỉ dùng cho định nghĩa gap/nghỉ (S08–S10); không cộng tải S02/S03/S11, không là lock.
- Thay thế đã cân nhắc: (B) tham số `occupied_slot_ids` trên từng rule — không đổi contract nhưng các
  rule khác family có thể khai báo lịch họp khác nhau cho cùng GV; (C) bỏ occupied work — ô họp sẽ bị
  phạt như gap, trái policy.

## 4. Semantics

Mọi rule chỉ có teacher scope (rỗng = mọi GV). Tiết dạy = covered period (double = 2). Bucket
GV/ngày/buổi dùng `day/session/period` của slot thật.

| Code | Parameters | Raw penalty (unit) |
|---|---|---|
| S07 `TEACHER_RESTRICTED_SLOTS` | `slot_ids` (tập, can_teach) | Số tiết dạy trên ô hạn chế; timed giao phút, mỗi covered period tối đa một lần (`teaching_periods`) |
| S08 `TEACHER_TOTAL_GAPS` | `session_ids` (tập) | Σ ô **idle** theo GV/ngày/buổi (`idle_periods`) |
| S09 `TEACHER_MAX_GAP_RUN` | `limit` ≥ 0, `session_ids` | Σ `max(0, chuỗi idle dài nhất − limit)` theo GV/ngày/buổi (`idle_periods`) |
| S10 `TEACHER_MIN_FREE_TIME` | `unit` ∈ {`day`, `session`}, `target` ≥ 1 | Σ GV `max(0, target − số ngày/buổi rảnh)` (`free_days`/`free_sessions`) |
| S11 `TEACHER_SINGLE_PERIOD_SESSION` | `session_ids` | Số (GV, ngày, buổi) có đúng 1 tiết dạy (`single_period_sessions`) |

**Ô idle** của GV t ở (ngày d, buổi s): slot có `can_teach=true`, period nằm **giữa** tiết dạy nhỏ nhất
và lớn nhất của t trong (d,s), t không dạy ở đó, và slot không thuộc occupied work của t. Ô
`can_teach=false` và ô occupied không idle. **Chuỗi idle** (S09) là các ô idle có period liên tiếp
trong cùng (d,s); ô `can_teach=false` hoặc occupied ở giữa **cắt chuỗi**. Buổi có < 2 tiết dạy không
có ô idle.

**Ngày/buổi rảnh** (S10): ngày (hoặc (ngày, buổi)) của calendar có ít nhất một slot `can_teach=true`,
GV không dạy tiết nào và không có occupied work ở đó. Ngày/buổi không có slot dạy được không tính.

**Ràng buộc kết hợp:** S07 và S01 là hai family khác nhưng policy cấm tính lặp: S01 và S07 bật cho cùng
GV có tập ô giao nhau (theo định nghĩa overlap S01) → INPUT_INVALID/OVERLAPPING_RULES. Overlap cùng
family: S07 như S01; S08/S09/S11 cùng GV và giao `session_ids`; S10 cùng GV bất kể `unit` (policy:
không bật cả hai). Khác family còn lại được kết hợp.

**Timed calendar (D4):** khi bật S08–S11, nếu hai slot khác buổi cùng ngày giao phút →
UNSUPPORTED_FEATURE/GAP_TIMELINE. Gap theo buổi không định nghĩa được khi một GV có thể dạy ở buổi khác
trùng giờ. S07 vẫn hỗ trợ timed (giao phút như S01).

## 5. Compiler (CP-SAT)

Với GV t và bucket (d,s) có các period `1..m` theo thứ tự:

- `teach[p]` = Σ biến placement của t phủ slot (d,s,p) (≤ 1 nhờ occupancy). Ô không thể dạy có `teach=0`.
- Tiền tố `before[p] = OR(teach[q], q<p)` và hậu tố `after[p] = OR(teach[q], q>p)` bằng
  `AddMaxEquality` trên Boolean (O(m) mỗi bucket).
- `idle[p] = before[p] ∧ after[p] ∧ ¬teach[p]` cho ô đủ điều kiện (can_teach, không occupied); các ô khác
  idle = 0 cố định. Viết bằng equality Boolean, không dựa objective.
- S08: raw = Σ idle. S09: `run[p] = idle[p]·(run[p−1]+1)` bằng big-M với M = m (exact, reset khi
  idle=0); `longest = max(run)`; excess = `max(0, longest − limit)`.
- S10: `busy[d] = OR(teach của t trong d)`; ô occupied làm ngày đó không rảnh (hằng số);
  `free = Σ (1 − busy)` trên ngày/buổi đủ điều kiện; short = `max(0, target − free)`.
- S11: `single[d,s]` reified đúng `load == 1` (cả hai chiều).
- S07: như S01 (hệ số theo placement).
- Bound và range guard như 2A; không thêm precheck. Biến tăng tuyến tính theo GV × ngày × buổi × period.

**Ordering (D6):** S07–S11 chỉ phụ thuộc GV/ngày/buổi/period của placement, nên bất biến khi hoán vị
occurrence cùng requirement/duration/domain. Đề xuất thêm vào allowlist chỉ sau oracle có/không ordering.

## 6. Evaluator độc lập

`score_evaluator` tự dựng tập period dạy theo GV/ngày/buổi từ assignments, tự tính idle/chuỗi/rảnh/đơn
tiết từ calendar và `occupied_work`. Không import compiler, `prepare`, OR-Tools; không dùng chung helper.
Chưa có hard mode nên validator không đổi, ngoại trừ kiểm contract occupied work qua input.

## 7. Tests và oracle (chưa viết/chạy)

| Nhóm | Ca có expected độc lập |
|---|---|
| Version | 0.1–0.3 + mã mới → UNKNOWN_RULE; 0.4 → 1.5 + Score 1.2; cặp sai bị reject; hash cũ không đổi (kể cả input không có `occupied_work`) |
| Occupied work | Chỉ 0.4; trùng GV; slot lạ; availability `null` hoặc chứa ô occupied → OCCUPIED_AVAILABLE; fingerprint sort |
| Overlap | S01+S07 giao ô cùng GV; S07+S07; S08/S09/S11 giao session; S10 day+session cùng GV |
| S07 | single/double/timed alias; không trùng S01 |
| S08 | Dạy 1 và 4 → idle 2; ô can_teach=false giữa → idle 1; ô occupied giữa → không idle; double; buổi 1 tiết → 0 |
| S09 | Chuỗi 3 limit 1 → 2; chuỗi bị cắt bởi can_teach=false/occupied; nhiều buổi cộng dồn |
| S10 | unit day/session; ngày chỉ có họp không rảnh; ngày không có slot dạy được không tính; target > số ngày |
| S11 | Đúng 1 tiết → 1; double (2 tiết) → 0; buổi trống → 0 |
| Timed | S08–S11 + slot khác buổi giao phút → GAP_TIMELINE; S07 timed vẫn chạy |
| Compiler | Giá trị raw với placement cưỡng bức, không objective, cho từng rule |
| Oracle | Vét cạn bài nhỏ trộn S07–S11 với S01–S06 (soft/hard sẵn có); ordering bật/tắt |
| CLI/package | 0.4 → 1.5 → validate/evaluate (Score 1.2); evaluate-score không OR-Tools; RESULT_VERSION |

## 8. Điều kiện ra 2C-2 (technical synthetic)

S07–S11 soft có compiler, evaluator độc lập, oracle; occupied work có contract và kiểm availability;
policy 0.1–0.3 và input 1.0 không đổi hành vi/hash; mọi lệnh AGENTS.md PASS. Không chứng nhận ngưỡng,
chất lượng giáo vụ, hiệu năng hay Windows.

## 9. Quyết định cần duyệt

- [ ] **D1** — policy `0.4` cho S07–S11. *(Đề xuất: chọn.)*
- [ ] **D2** — output `1.5`, ScoreReport `1.2` với bốn unit mới. *(Đề xuất: chọn.)*
- [ ] **D3** — `constraint_config.occupied_work` chỉ ở policy 0.4, bắt buộc nằm ngoài availability.
  *(Đề xuất: chọn. Thay thế: tham số mỗi rule (B), hoặc bỏ occupied work (C).)*
- [ ] **D4** — từ chối S08–S11 trên timed calendar có slot khác buổi cùng ngày giao phút. *(Đề xuất: chọn.
  Thay thế: coi ô giao giờ với tiết dạy ở buổi khác là không idle — phức tạp hơn.)*
- [ ] **D5** — chỉ soft trong 2C-2; không hard mode cho S07–S11. *(Đề xuất: chọn. S07 hard trùng S01
  hard; S08 là objective tổng; hard S09/S10/S11 để mốc sau khi trường xác nhận.)*
- [ ] **D6** — bật ordering với S07–S11 nếu oracle đạt; nếu không thì giữ tắt. *(Đề xuất: chọn.)*
- [ ] **D7** — S01 và S07 cùng GV với ô giao nhau bị từ chối như overlap. *(Đề xuất: chọn, theo policy.)*
