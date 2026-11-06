# Phase 3B — tự rà soát sau commit

Ngày 2026-11-06. Đối tượng: commit `f3b2c94` trên `main` (đã push). Người rà soát: Claude (tự rà soát,
không phải review người thứ hai theo S3). **Trạng thái: F1–F5 ĐÃ SỬA ngày 2026-11-06; F6 (từ kiểm installed wheel) MỞ** (xem
§Kết quả sửa); người dùng duyệt sửa, commit và push.

Phạm vi đọc: `contracts/diagnostics.py`, `diagnostics/` (domains, groups, prechecks, model, pipeline),
`validation/precheck_verifier.py`, phần `relaxed_groups` của `validation/independent_validator.py`, hai
lệnh CLI mới và các test 3B. Mọi finding có repro chạy thật (script ngoài repo, không sửa file trong repo).

## Findings

| ID | Mức | Tóm tắt |
|---|---|---|
| F1 | Cao | `RESOURCE_LIMIT` trả trước precheck; `check-explanation` từ chối chính report đó |
| F2 | Trung bình | `check-explanation` chấp nhận tập xung đột có ID nhóm không tồn tại |
| F3 | Thấp | `explain` gặp `MODEL_INVALID` trả exit 2, còn `solve` trả 5 |
| F4 | Thấp (test) | Logic bucket S02/S03/S05/S06 sao lại; oracle dùng cùng logic làm tham chiếu |
| F5 | Thấp | Lời gọi solver đầu vẫn chạy khi budget đã hết |
| F6 | Trung bình | `explain` crash (exit 1, không JSON) khi không cài OR-Tools — từ kiểm installed wheel, **mở** |

### F1 — Guard tài nguyên che phản chứng đếm và làm hỏng tính nhất quán với verifier

`explain_infeasibility()` dựng domain (`build_domains`) trước khi chạy precheck. Ở `FULL`, domain giữ cả
placement vi phạm nên vượt `max_placements` sớm hơn nhiều. Khi guard chặn, pipeline trả `RESOURCE_LIMIT`
dù precheck (vốn không phụ thuộc mức chi tiết) đã đủ chứng minh vô nghiệm. Sau đó `check_explanation()`
coi `RESOURCE_LIMIT` như mọi status không phải `PRECHECK_PROOF` và đòi không có phản chứng nào, nên trả
`PRECHECK_PROOF_MISSING`: CLI báo `EXPLANATION_MISMATCH` cho một report thật do chính tool sinh.

Repro: 1 lớp, 1 GV chỉ rảnh 2/6 ô, cần 3 tiết, `max_placements=10`.

| Mức | Kết quả `explain` | `check_explanation` |
|---|---|---|
| MODEL | `PRECHECK_PROOF` (2 × `PC_RESOURCE_CAPACITY`) | OK |
| FULL | `RESOURCE_LIMIT` | `('PRECHECK_PROOF_MISSING',)` |

Cùng lỗi xảy ra ở `MODEL` khi chính domain sạch vượt guard (ví dụ tam giác có r1 = 3 tiết,
`max_placements=8`).

Đề xuất sửa:

1. Dựng domain sạch và chạy precheck **trước**, độc lập với mức chi tiết; chỉ sau đó mới dựng domain mở
   rộng cho `FULL`.
2. `RESOURCE_LIMIT` nghĩa là "chưa chẩn đoán được": verifier không được đòi vắng phản chứng với status
   này. Chỉ `NOT_INFEASIBLE`, `UNKNOWN` và `CORE_SUBSET` (đều đi qua precheck) mới đòi.
3. Test hồi quy cho cả hai mức.

### F2 — `check-explanation` không kiểm ID nhóm của tập xung đột

Với `CORE_SUBSET`, verifier chỉ kiểm fingerprint và việc không có phản chứng. Một report sửa tay có
`subset = [{"kind": "DEMAND", "id": "no-such-requirement"}]` (và witness tương ứng) vẫn được trả `OK`.
Cũng không kiểm kind có hợp với `granularity` không (ví dụ `LOCK` trong report `MODEL`). Tập con là bằng
chứng của solver nên không kiểm lại được tính vô nghiệm, nhưng ID tồn tại và kind hợp lệ là điều kiện cần
kiểm được độc lập.

Đề xuất: verifier tự liệt kê nhóm hợp lệ theo `granularity` từ input thô (không import `diagnostics`) và
đòi `subset`, `unresolved`, nhóm của witness đều nằm trong đó. Thêm test report giả.

### F3 — Exit code `MODEL_INVALID` không thống nhất

`explain` bắt `CoreError` qua `emit_error` nên `MODEL_INVALID` (model chẩn đoán bị từ chối, hoặc core tự
giải lại ra FEASIBLE) trả exit 2. `solve`/`repair` trả 5 cho `MODEL_INVALID` (`main` docstring: "5 model
failure"). Repro: ép `build_diagnostic_model` raise `MODEL_INVALID` → exit 2, status `MODEL_INVALID`.

Đề xuất: map status lỗi của `explain` giống `_exit_code` (5 cho `MODEL_INVALID`), ghi vào domain model.

### F4 — Phía "vô nghiệm" của model chẩn đoán thiếu đối chiếu độc lập trong test

`diagnostics/model.py` sao lại logic bucket của `constraints/hard.py`. Oracle dùng chính
`build_diagnostic_model` (không B11) làm tham chiếu, nên một lỗi chung về ngữ nghĩa nhóm sẽ không bị
oracle bắt. Witness được validator độc lập kiểm, nhưng đó chỉ là phía FEASIBLE. Test
`test_all_on_model_matches_solve_status` chỉ chạy 7 fixture, không fixture nào có rule hard.

Kiểm trong lượt rà soát (script ngoài repo): 400 input ngẫu nhiên policy 0.3, 3–6 requirement, có tiết
đôi, mỗi input 1–3 rule hard trong S01–S06. Model chẩn đoán (mọi literal bật) **khớp** status `solve()`
trên cả 397 ca so được (240 INFEASIBLE, 157 FEASIBLE; 3 ca `solve()` UNKNOWN bị loại). Không thấy lỗi,
nhưng phép kiểm này chưa có trong test suite.

Đề xuất: thêm property test như trên (seed cố định, budget nhỏ, bỏ qua UNKNOWN).

### F5 — Lời gọi đầu không kiểm budget còn lại

`solve_subset` dùng `max(seconds, 0.001)`. Pipeline kiểm `left() > 0` trước lời gọi xác nhận và mỗi
bước deletion, nhưng không kiểm trước lời gọi đầu. Nếu normalize, domain và precheck đã dùng hết budget,
vẫn có thêm một lời gọi solver và `wall_time` có thể vượt `time_limit_seconds`. Không gây kết luận sai.

Đề xuất: `left() <= 0` trước lời gọi đầu → `UNKNOWN`, `solver_calls = 0`.

## F6 — `explain` crash khi không cài OR-Tools

Phát hiện khi kiểm installed wheel từ `c1a49e1` (xem [báo cáo 3B](phase-3b-report.md)). **Mở, chưa sửa.**

Trong venv không có OR-Tools, `python -I -m tkb_core.cli explain triangle.json --time-limit 10 --seed 42
--granularity MODEL` thoát với exit 1, in traceback `ModuleNotFoundError: No module named 'ortools'` ra
stderr và không in JSON. Cùng venv đó, `solve` và `repair` trả JSON `UNSUPPORTED_FEATURE /
SOLVER_NOT_INSTALLED` với exit 2. Nguyên nhân: CLI import `diagnostics.pipeline`, mà module này import
`diagnostics.model`, nơi `ortools` được import ngay khi nạp module. Hệ quả phụ: input có phản chứng đếm
(không cần solver) cũng không chẩn đoán được khi thiếu OR-Tools.

Mức: trung bình (đường lỗi không có cấu trúc, lệch hợp đồng CLI). Không tạo kết luận sai.

Đề xuất: import model lười trong pipeline (chỉ khi cần CP-SAT); khi thiếu OR-Tools và không có phản chứng,
trả `UNSUPPORTED_FEATURE / SOLVER_NOT_INSTALLED` (exit 2) như `solve`; precheck vẫn chạy được không cần
OR-Tools. Test: subprocess chặn import `ortools`, kiểm cả input precheck và input cần solver.

## Đã kiểm, không có finding

- **B11:** mọi ràng buộc (DEMAND, occupancy, S02/S03/S05/S06, `x ⇒ ¬a`) đối xứng giữa occurrence cùng
  requirement, cùng domain đã gắn nhãn, không khóa. Occurrence không xếp có rank 0, bằng rank của
  placement chỉ số 0, nên `≤` vẫn sắp lại được khi DEMAND tắt hoặc occupancy tắt (hai occurrence cùng
  placement). Oracle đã kiểm trên mọi tập con.
- **Đơn điệu:** literal chỉ xuất hiện ở `only_enforce_if(a)` và `x ⇒ ¬a`, nên để literal không active ở
  trạng thái tự do là đúng; lọc core về literal active là đúng.
- **Deletion:** phần tử bỏ được thì tập còn lại đã được giải INFEASIBLE trực tiếp; witness của phần tử giữ
  lại thỏa một tập lớn hơn, nên cũng thỏa tập cuối; witness được kiểm lại với tập cuối.
- **`relaxed_groups`:** mặc định giống bản `HEAD` trên 2 843 lịch (đo khi triển khai); DEMAND chỉ cho
  thiếu; nền cố định luôn kiểm; kind lạ bị từ chối.
- **Verifier độc lập:** import guard chặn `ortools`, `solver`, `constraints`, `preprocessing`, `repair`,
  `diagnostics`; danh sách phản chứng khớp precheck trên mọi fixture và ca tay.

## Ghi chú test

`test_tiny_budget_never_claims_a_wrong_answer` gần như không thể fail (bài nhỏ giải xong trong 1 ms). Tính
chất "không khẳng định sai khi hết budget" được bảo đảm thực sự bởi hai test monkeypatch UNKNOWN. Có thể bỏ
hoặc thay bằng ca budget hết trước lời gọi đầu (cùng lúc sửa F5).

## Kết quả sửa (2026-11-06)

TDD: viết test trước, chạy thấy 19 test fail đúng chỗ (F1 ×2, F2 ×15, F3 ×1, F5 ×1), sau đó sửa.

| ID | Sửa | Test |
|---|---|---|
| F1 | `pipeline.py`: luôn dựng domain sạch và chạy precheck trước; chỉ sau đó mới dựng domain mở rộng cho `FULL`. `check_explanation`: `RESOURCE_LIMIT` không đòi vắng phản chứng | `test_prechecks_run_before_the_expanded_domain_guard` (MODEL, FULL), `test_resource_limit_report_passes_its_own_check` |
| F2 | `precheck_verifier.recompute_groups()` liệt kê nhóm từ input thô theo `granularity`; `subset`, `unresolved`, nhóm witness phải thuộc danh mục, nếu không → `UNKNOWN_GROUP` | `test_check_explanation_rejects_unknown_or_out_of_granularity_groups`; danh mục khớp `enumerate_groups` trên 7 fixture × 2 mức và 200 input sinh |
| F3 | `cli.py`: `explain` gặp `MODEL_INVALID` → exit 5, như `solve`/`repair` | `test_explain_model_invalid_exits_5` |
| F4 | Property test mới `tests/properties/test_diagnostics_solve_agreement.py`: 200 seed có rule hard S01–S06, tiết đôi, availability, khóa; model chẩn đoán (mọi nhóm bật) phải cùng status với `solve()` | 199 passed, 1 skip (`solve()` UNKNOWN). **Mutation thử:** nới giới hạn bucket thêm 1 → 50 ca fail; đã hoàn nguyên, `model.py` không đổi |
| F5 | `pipeline.py`: `left() <= 0` trước lời gọi đầu → `UNKNOWN`, `solver_calls = 0`. Test budget yếu được thay | `test_exhausted_budget_skips_the_solver` |

Checks sau sửa: `pytest tests benchmarks/tests` **1967 passed, 22 skipped**; ruff, format (107 file), mypy
(44 file) PASS; `git diff --check` PASS; diff ở `solver/`, `preprocessing/`, `constraints/`, `repair/`,
`benchmarks/` rỗng. `diagnostics/model.py` không đổi trong lượt sửa.
