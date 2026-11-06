# Phase 3B — kế hoạch triển khai chẩn đoán vô nghiệm

Ngày 2026-11-06. Trạng thái: **B1–B11 đã duyệt ngày 2026-11-06; spike B9 đã chạy; bước C (Task 1–9) ĐÃ
THỰC HIỆN, chưa commit.** Kết quả và sai khác: [báo cáo 3B](../../phase-3b-report.md).
Đặc tả: [2026-11-06-phase-3b-infeasibility-diagnostics-design.md](../specs/2026-11-06-phase-3b-infeasibility-diagnostics-design.md).
Base `4b15936` trên `main`.

Mỗi task theo TDD: test RED trước, sửa tối thiểu, GREEN. Nếu wiring có sẵn làm test mới xanh ngay, kiểm
hiệu lực của test bằng cách tạm khôi phục file cũ. Không sửa `benchmarks/`, gate, budget hay pins; không
chạy campaign; không commit trong từng task.

## 1. Kết quả spike B9

Chạy ngày 2026-11-06 trên máy Linux của người dùng, OR-Tools **9.15.6755** từ
`uv sync --locked --extra solver`. Script nằm ngoài repo (scratchpad phiên làm việc), dựng model
`cp_model` trực tiếp theo đúng cách gắn nhóm của đặc tả §3: DEMAND (`AtMostOne` luôn bật + `sum == 1`
`only_enforce_if(a)`), OCCUPANCY (`sum <= 1` `only_enforce_if(a)`), HARD_RULE (giới hạn tải theo ngày
`only_enforce_if(a)`), LOCK/AVAILABILITY (`x ⇒ ¬a`). Assumptions qua `add_assumptions`; core qua
`sufficient_assumptions_for_infeasibility()`. Mỗi ca nhỏ được đối chiếu với **liệt kê vét cạn mọi tập con
nhóm** để biết mọi MUS thật.

### 1.1 Các ca nhỏ

| Ca | MUS thật (vét cạn) | Core thô (w1, presolve bật/tắt, w8) | Sau deletion | Lời gọi deletion |
|---|---|---|---|---:|
| C1 hai khóa cùng GV, cùng ô | {DEMAND R1, DEMAND R2, LOCK R1#0, LOCK R2#0, OCC T1} | Đúng bằng MUS | MUS, `minimal_proved` | 5 |
| C2 GV bận 2/5 ô, demand 4 | {AVAIL T1, DEMAND R1, OCC T1} | Đúng bằng MUS | MUS | 3 |
| C3 giới hạn hard 2 tiết/ngày × 2 ngày, demand 5 | {DEMAND R1, HARD_S03 T1} | **Thừa** OCC T1 | MUS (bỏ được OCC) | 3 |
| C4 hai xung đột rời nhau (C1 + C2) | Hai MUS | Một trong hai MUS (luôn C1) | MUS đó | 5 |
| C5 có lịch | — | OPTIMAL, core rỗng | — | — |
| C6 như C2, demand mã hóa `bool_or` | {AVAIL, DEMAND, OCC} | Đúng bằng MUS | MUS | 3 |

Mọi ca: hai lần gọi cùng tham số cho cùng status và core. Ba cấu hình (w1 có presolve, w1 không presolve,
w8) cho cùng core trên các ca này.

### 1.2 Hết budget

Pigeonhole 13 occurrence vào 12 ô, budget 0,5 s: status **UNKNOWN**, core **rỗng**, cả có và không
presolve. API không trả core giả khi chưa chứng minh vô nghiệm.

### 1.3 Phát hiện quan trọng: đối xứng giữa occurrence hoán đổi được

Pigeonhole n occurrence cùng requirement vào n − 1 ô, budget 10 s, w1:

| n | Không ràng buộc thứ tự (presolve bật / tắt) | Có thứ tự rank(o_i) ≤ rank(o_{i+1}) |
|---:|---|---|
| 6 | INFEASIBLE 0,002 s / 0,001 s | INFEASIBLE 0,001 s |
| 8 | INFEASIBLE 0,09 s / 0,08 s | INFEASIBLE 0,002 s |
| 10 | INFEASIBLE 4,9 s / 9,6 s | INFEASIBLE 0,003 s |
| 12 | **UNKNOWN** 10 s / 10 s | INFEASIBLE 0,004 s |
| 16 | **UNKNOWN** | INFEASIBLE 0,009 s |
| 22 | **UNKNOWN** | INFEASIBLE 0,024 s |

Ca C7: GV T1 cần 22 tiết, chỉ có 20 ô khả dụng, lẫn trong 48 GV khác có lịch (147 nhóm). Không thứ tự:
UNKNOWN sau 10 s. Có thứ tự cho mọi requirement: INFEASIBLE sau 1,05 s (presolve bật) / 4,2 s (tắt); core
thô = MUS {AVAIL T1, DEMAND R1, OCC T1}; deletion 3 lời gọi; tổng 3,0 s / 4,9 s.

Diễn giải: xung đột kiểu "đếm" là bài pigeonhole, rất khó cho SAT nếu không phá đối xứng. Hai lớp bảo vệ:

1. precheck mở rộng (`PC_RESOURCE_CAPACITY`…) bắt phần lớn các xung đột đếm trước khi gọi CP-SAT;
2. model chẩn đoán phải có ràng buộc thứ tự giữa các occurrence hoán đổi được, như `solve()` đã có
   (`_add_interchangeable_ordering`).

### 1.4 Kết luận spike

API đáp ứng thiết kế B1–B10: core đúng, có thể thừa (cần deletion như B8), không giả khi hết budget, ổn
định theo seed. **Không cần đổi thiết kế**, nhưng cần bổ sung **B11** (§2). Giới hạn của spike: model
dựng tay, không qua `prepare()`/`build_model()`; chưa đo ở cỡ 20/40 lớp; một máy, n = 1 mỗi ca.

## 2. Quyết định mới từ spike

- [x] **B11 — Phá đối xứng trong model chẩn đoán:** thêm ràng buộc thứ tự rank giữa các occurrence cùng
  requirement, cùng domain (domain mở rộng ở `FULL`), cùng tập nhóm, không bị khóa — làm phần **nền cố
  định** (không có assumption). Điều kiện: chứng minh ràng buộc này giữ nguyên tính khả thi với **mọi**
  tập con nhóm (kể cả khi DEMAND tắt và occurrence được phép không xếp, rank = 0), và kiểm bằng oracle
  so có/không thứ tự (Task 5). Nếu oracle tìm thấy một tập con mà thứ tự đổi kết quả → dừng và báo.
  *(Đề xuất: chọn. Không có B11, xung đột đếm cỡ ≥ 12 tiết trả UNKNOWN.)*

## 3. Ranh giới phê duyệt

| Bước | Cần duyệt riêng |
|---|---|
| A. Duyệt đặc tả B1–B10 | Đã duyệt 2026-11-06 |
| B. Spike B9, kế hoạch này | Đã làm; kế hoạch + B11 đã duyệt 2026-11-06 |
| C. Task 1–9 trong working tree, chạy checks | Đã duyệt và thực hiện 2026-11-06 |
| D. Commit + push | Có |
| E. Tự rà soát, sửa finding, kiểm installed wheel | Có, từng bước |

## 4. Task

### Task 1 — Contract `InfeasibilityReport` 1.0 (B2)

Files: `src/tkb_core/contracts/diagnostics.py` (mới), `tests/unit/test_diagnostics_contracts.py` (mới).

RED: roundtrip; field lạ bị từ chối; `status` sai; `minimal_proved`/`subset` chỉ hợp lệ với `CORE_SUBSET`;
`precheck_proofs` chỉ với `PRECHECK_PROOF`; `evidence.infeasibility` khớp status; `limitations` đúng câu
cố định; không có field `assignments`.

### Task 2 — Danh mục nhóm và ID (B3, B4)

Files: `src/tkb_core/diagnostics/groups.py` (mới), `tests/unit/test_diagnostics_groups.py` (mới).

RED: liệt kê nhóm từ input 1.0 và 1.1 (policy 0.1–0.4): DEMAND theo requirement, OCCUPANCY theo lớp/GV/phòng
(phòng chỉ khi có occurrence cần phòng), HARD_RULE theo rule ID hard đang bật (S02/S03/S05/S06), và ở
`FULL` thêm LOCK, AVAILABILITY (chỉ resource có `available_slot_ids`), HARD_PLACEMENT_RULE (S01/S04 hard).
ID ổn định, thứ tự (kind, ID) xác định; `MODEL` không có nhóm lọc-domain.

### Task 3 — Precheck mở rộng và verifier độc lập (B6)

Files: `src/tkb_core/diagnostics/prechecks.py` (mới), `src/tkb_core/validation/precheck_verifier.py` (mới),
`tests/unit/test_diagnostics_prechecks.py` (mới).

RED: mỗi `PC_*` của đặc tả §5 có fixture dương và fixture biên vừa đủ; liệt kê **mọi** phản chứng, không
dừng ở cái đầu; verifier tính lại từ input thô và từ chối phản chứng sai số; subprocess import guard
(verifier không import ortools, preprocessing, solver, diagnostics). Precheck của `solve()` không đổi:
test hồi quy mã lỗi `EMPTY_DOMAIN`, `RESOURCE_CAPACITY`, `ROOM_CAPACITY`, `LOCK_CONFLICT` trên fixture cũ.

### Task 4 — Model chẩn đoán có assumption (B3, B4, B11)

Files: `src/tkb_core/diagnostics/model.py` (mới), `tests/unit/test_diagnostics_model.py` (mới).

RED: dựng từ domain của `prepare()` (`MODEL`) hoặc domain mở rộng (`FULL`, cùng guard
`max_placements`/`max_occupancy_terms`; vượt → `RESOURCE_LIMIT`). Mỗi nhóm có đúng một literal; DEMAND
tắt cho phép occurrence không xếp; nhóm lọc-domain qua `x ⇒ ¬a`; ràng buộc thứ tự B11 là nền. Không gọi
`prepare()` theo cách làm đổi hành vi của `solve()`: tách hàm dựng domain mở rộng thay vì thêm tham số
vào `prepare()`. Test rằng với mọi literal bật, model chẩn đoán `MODEL` và model `solve()` hard-only cùng
status trên các fixture cũ.

### Task 5 — Pipeline `explain_infeasibility()` (B1, B5, B7, B8)

Files: `src/tkb_core/diagnostics/pipeline.py` (mới), `src/tkb_core/diagnostics/__init__.py` (mới),
`tests/integration/test_diagnostics_solver.py` (mới).

RED (ca tính tay, lấy từ spike C1–C6 viết lại bằng input JSON): validate/capability lỗi → trả lỗi gốc;
có phản chứng precheck → `PRECHECK_PROOF`, không gọi CP-SAT; có lịch → `NOT_INFEASIBLE`; core thừa (C3)
→ deletion bỏ đúng phần tử; hai xung đột rời (C4) → một MUS; budget rất nhỏ → `UNKNOWN` hoặc
`minimal_proved=false`, không bao giờ khẳng định sai; budget chung chia theo phần còn lại; workers = 1,
seed từ request; witness không bao giờ xuất hiện trong report.

### Task 6 — Validator chế độ bỏ qua nhóm (B5)

Files: `src/tkb_core/validation/independent_validator.py` (sửa, thêm tham số tường minh),
`tests/unit/test_validator_relaxed_groups.py` (mới).

RED: mặc định (không truyền danh sách) hành vi và output **không đổi** (hash trên fixture cũ); chấp nhận
witness vi phạm đúng nhóm được bỏ qua; từ chối witness vi phạm nhóm khác hoặc nền cố định; DEMAND bỏ qua
cho phép thiếu occurrence của đúng requirement đó; import guard giữ nguyên.

### Task 7 — Oracle vét cạn

Files: `tests/properties/test_diagnostics_oracle.py` (mới).

60 seed bài tí hon (≤ 8 nhóm), mỗi seed cả `MODEL` và `FULL`: liệt kê mọi tập con nhóm bằng một solver
tham chiếu **không thứ tự** để biết mọi MUS. Kiểm: (a) `subset` vô nghiệm; (b) nếu `minimal_proved` thì
`subset` là một MUS thật; (c) B11: với mọi tập con, có/không thứ tự cho cùng status; (d) có lịch ↔
`NOT_INFEASIBLE`. Kiểm độ đa dạng (đủ ca PRECHECK_PROOF, CORE_SUBSET, NOT_INFEASIBLE).

### Task 8 — CLI

Files: `src/tkb_core/cli.py` (thêm `explain`, `check-explanation`), `tests/integration/test_diagnostics_cli.py`
(mới).

RED: `explain` thiếu `--time-limit`/`--seed`/`--granularity` → lỗi usage; end-to-end
`explain` → `check-explanation` trên fixture `infeasible_teacher.json` và các fixture mới; report giả
(sai số, fingerprint lệch) bị từ chối; `check-explanation` chạy trong subprocess không có OR-Tools; các
lệnh cũ giữ nguyên exit code và output.

### Task 9 — Tài liệu

README (lệnh mới), `docs/domain-model.md`, `docs/solver-design.md` (model chẩn đoán, B11),
`docs/constraint-catalog.md` (nhóm chẩn đoán theo rule), báo cáo `docs/phase-3b-report.md`, trạng thái
đặc tả/kế hoạch.

## 5. Checks trước khi báo hoàn thành (bước C)

- `uv sync --locked --extra solver`
- `uv run --extra solver pytest tests benchmarks/tests`
- `uv run ruff check .`, `uv run ruff format --check src tests`, `uv run mypy`
- `git diff --check`
- `git diff -- src/tkb_core/solver src/tkb_core/preprocessing src/tkb_core/constraints src/tkb_core/repair benchmarks`
  phải rỗng (hoặc chỉ thêm hàm mới không được `solve()`/`repair()` gọi, nêu rõ trong báo cáo)
- hash output `solve()`/`repair()`/`validate-schedule` trên fixture cũ không đổi

## 6. Rủi ro và giảm thiểu

| Rủi ro | Giảm thiểu |
|---|---|
| B11 làm sai kết quả khi một số nhóm tắt | Chứng minh trong `solver-design.md` + oracle (c) Task 7; sai → dừng |
| Thời gian chẩn đoán ở 20/40 lớp chưa biết (spike chỉ đến 147 nhóm, ~1 s) | Budget chung, `minimal_proved=false` khi hết; đo thuộc 3C hoặc lát sau (B10) |
| Domain mở rộng `FULL` lớn | Cùng guard như `solve()`; `RESOURCE_LIMIT` thay vì nới |
| Sửa validator làm yếu đường chính | Tham số tường minh, mặc định không đổi, test hash |
| Spike dùng model dựng tay, không qua code thật | Task 4 test cùng status với model `solve()` trên fixture cũ |
