# Windows — S03 bounds và c10-tight-s101 UNKNOWN: báo cáo điều tra

**Kết luận:** S03 bounds đã vào Core (`63506ca`) với regression đầy đủ, nhưng trên Windows ca `c10-tight-s101` policy gốc vẫn UNKNOWN ở 5s và 60s, có hay không có bounds. Model feasibility trên Windows trùng byte với model Linux, nhưng search trajectory khác: ở deterministic time 60 Windows chưa có lịch, trong khi bốn success Linux cần 46.39. Không có evidence bug Core hoặc model loại nghiệm. Task2 frozen Linux vẫn DEFERRED_NOT_ACCEPTED.

**Cập nhật hard-feasibility stage (`ec9ced1`):** khi feasibility chạy trên model chỉ có hard constraints, Core trả lịch hard-valid ở 5s cả 2/2 lần, còn Core `63506ca` vẫn UNKNOWN 2/2 (mục 7). Score [13,79,5] chưa có tier nào được chứng minh tối ưu. Không tuyên bố tăng tốc.

Báo cáo docs-only, tổng hợp evidence đã lưu ngoài repository dưới `C:\tkb-checkout-check\`. Lượt viết báo cáo không chạy solver, pytest hoặc build model. Tổng hợp Linux trước đó: [tight10-evidence-synthesis.md](tight10-evidence-synthesis.md).

## 1. Triển khai S03 bounds trong Core

- Commit `63506ca` (fast-forward vào main, đã push): `src/tkb_core/constraints/s03_bounds.py` tính cho mỗi giáo viên trong scope và mỗi ngày D/U/F/L từ prepared domains; `soft.py` append `lower ≤ var ≤ upper` trên excess/raw S03 sau khi stage toàn rule, fallback nguyên rule nếu không chứng minh được. Mô tả: [solver-design.md](solver-design.md#bound-dư-thừa-s03).
- Regression: unit R01–R16, oracle vét cạn 12 fixtures (14,630 tổ hợp, `rejected_by_bounds=0`), 6 cặp native nhỏ. Worktree: full suite 280 passed; ruff/format/mypy PASS. Sau merge trên main: chạy lại cùng kết quả.
- Lệch plan đã duyệt: file integration đổi tên `test_s03_bounds_native.py` vì trùng basename với unit test.

## 2. Đánh giá trên c10-tight-s101

Input SHA256 `7d023d04…8735`, fingerprint `126305e0…b0ee`, policy gốc 60 soft rules (15 mỗi family S01–S04, mỗi rule một giáo viên); witness score (0,78,0). BASE = Core `e4efa26` (installed-solver-v1, read-only), BOUND = Core `63506ca`; gates identity và structural (15/15 rule S03 không fallback, 105 bounds, 1,255 constraints gốc giữ thứ tự, witness 0 vi phạm) PASS trước mọi solve.

| Lượt | Thiết lập | Kết quả |
|---|---|---|
| eval-v1 | ABBA 5s CLI | PARTIAL: 4 invocations chạy nhưng `OUTPUT_WRITE_ERROR` do lỗi quoting đường dẫn trong harness; không có kết quả |
| eval-v2 | ABBA 5s CLI, harness đã sửa | BASE 2/2, BOUND 2/2 UNKNOWN (feasibility 5.0015–5.0019s) |
| eval60-v1 | ABBA 60s CLI | BASE 2/2, BOUND 2/2 UNKNOWN (feasibility 60.003–60.004s) |
| dettime-v1 | Driver, Core e4efa26, `max_deterministic_time=60`, wall cap 300s | Proto `str()` SHA256 `f8c390bc…8083` trùng Linux; UNKNOWN tại deterministic 60.0003, wall 73.07s |

Theo tiêu chí định trước: không có bằng chứng S03 bounds giúp tìm lịch ở 5s hoặc 60s trên Windows cho mẫu này. Không kết luận bounds vô ích ở input hoặc budget khác. Không tuyên bố tốc độ.

## 3. Bảng điều kiện × kết quả

| Điều kiện | Families | Bounds | Runner | OS | Budget | n | Feasibility |
|---|---|---|---|---|---|---|---|
| Hard-only | — | — | CLI | Windows | 5s | 1 | OPTIMAL 0.166s |
| Split B | S01+S04 | — | CLI | Windows | 5s | 1 | OPTIMAL 0.165s |
| Without S02 | S01+S03+S04 | không | CLI | Windows | 5s | 1 | UNKNOWN |
| Split A | S03 | không | CLI | Windows | 5s | 1 | UNKNOWN |
| Prototype | S03 | 105, cuối model | driver | Windows | 5s | 1 | OPTIMAL 4.92s |
| Policy gốc | S01–S04 | không / product | CLI | Windows | 5s, 60s | 4+4 | UNKNOWN ×8 |
| Policy gốc | S01–S04 | không | driver, deterministic 60 | Windows | — | 1 | UNKNOWN |
| Policy gốc | S01–S04 | không | campaign / diagnostic | Linux | 60s | 3 / 4 | UNKNOWN ×3 / OPTIMAL ×4 (46.0–55.9s) |
| Policy gốc, feasibility hard-only (`ec9ced1`) | S01–S04 | product | CLI | Windows | 5s | 2 | OPTIMAL 0.231s ×2 (hard-only model) |

## 4. Counters: Windows deterministic 60 vs Linux success

| Chỉ số | Windows dettime-v1 | Linux success ×4 |
|---|---|---|
| Deterministic time | 60.0003 (UNKNOWN) | 46.3929 (OPTIMAL) |
| Wall | 73.07s | 46.03–55.92s |
| Branches | 1,109,212 | 1,150,007 |
| Conflicts | 33,475 | 25,380 |
| LP iterations | 518,173 | 374,745 |
| Restarts | 83 | 87 |

Wall/deterministic của run Windows ≈1.22 (n=1). Ở tỉ lệ đó 60s wall ≈49 đơn vị; nếu cùng trajectory với Linux thì eval60 đã kịp tìm lịch.

## 5. Đã chứng minh / chưa chứng minh

- **Trong phạm vi mẫu:** hard constraints không phải chỗ khó; feasibility khó lên khi model có auxiliaries S03; model Windows trùng byte Linux; Windows search khác trajectory Linux và chưa có lịch ở deterministic 60.
- **Biến nhiễu còn lại:** tham số dettime lệch Linux (thêm deterministic limit, wall cap 300 thay 60); binary OR-Tools Windows vs Linux (cùng version 9.15.6755); runner, máy, thời điểm; n nhỏ ở mọi lượt; prototype thành công sát budget và đặt bounds khác vị trí.
- **Chưa đủ căn cứ:** nguyên nhân platform cụ thể, tác động S03 bounds ở input khác, đổi default budget/guards, sửa Core. UNKNOWN không phải INFEASIBLE.

## 6. Evidence

Mỗi thư mục có `report.md` (hoặc `design.md`/`analysis.md`) và manifest hash; SHA256 manifest:

| Thư mục | Manifest SHA256 |
|---|---|
| windows-s03-core-bounds-impl-v1 | `96b4417c74696b9e5715b2f0509639a860dcd4e541268cf2464cd3b8e47644e4` |
| windows-s03-main-merge-v1 | `169509fbbf197936a699b1b63e7bde11c6341ce53fc4a341817e7ee5bc0c3131` |
| windows-tight-s03-bounds-eval-v1 | `1bc661097d39a156d1618bf5de2c598ed1c74523ffe9fcaa733bacf998b71752` |
| windows-tight-s03-bounds-eval-v2 | `66d4f9513079ac7409bd430e07769bbe844d7d85b011aa966b3bb5b688e6a960` |
| windows-tight-s03-bounds-eval60-v1 | `d4e33b51e84201f7da5cc11dbe94d7a523a41c34562e90bff1d80057f77ecef8` |
| windows-tight-unknown-analysis-v1 | `baf396b684fe52fc0d235f1f1290c0ed391ac1d5088b198d8fc99549960fa9e4` |
| windows-tight-dettime-v1 | `dd9afa1875754ac920fd4e038e5cca89b3c79527f8d811d57d478148c92fa4e7` |
| windows-tight-hardfeas-eval-v1 | `d8bd3b99a8fe22f0c56bd54d44a9804c32b6c6d42643ba64d61601dd83557f00` |

Hồ sơ thiết kế tương ứng: `windows-s03-core-bounds-design-v1`, `windows-tight-s03-bounds-eval-design-v1`, `windows-tight-s03-bounds-eval60-design-v1`, `windows-tight-dettime-design-v1`. Lượt hardfeas-eval-v1 dùng lại harness, gates và bảng diễn giải của eval-v2.

## 7. Hard-feasibility stage (`ec9ced1`) trên c10-tight-s101

Commit `ec9ced1` chạy feasibility trên bản clone model chỉ có hard constraints. Sau đó Core chạy một verification solve, cố định placements của incumbent để đối chiếu expression với evaluator. Cuối cùng là các tier, mỗi tier được hint bằng incumbent tốt nhất (xem [solver-design.md](solver-design.md)).

Thiết lập: ABBA CLI 5s/seed 42/workers 1, BASE = Core `63506ca` (venv eval-v1, read-only), HF = Core `ec9ced1` (venv mới, non-editable).

Gates:
- Identity BASE: 28 file khớp từng byte.
- Identity HF: 27/28 file khớp từng byte với bản export. Riêng `solver/objectives.py` trong worktree là LF trong khi bản export là CRLF; file này khớp nguyên byte với blob của commit. Bỏ qua line ending thì 28/28 khớp. Lệch này được duyệt trước khi solve.
- Structural gate: PASS.

| Run | Status | Feasibility | Tier 1 | Tier 2/3 | Score | Prefix |
|---|---|---|---|---|---|---|
| BASE-1 | UNKNOWN | UNKNOWN 5.008s | NOT_RUN | NOT_RUN | null | [] |
| HF-1 | FEASIBLE | OPTIMAL 0.231s | FEASIBLE 13, bound 0 | NOT_RUN | [13,79,5] | [] |
| HF-2 | FEASIBLE | OPTIMAL 0.231s | FEASIBLE 13, bound 0 | NOT_RUN | [13,79,5] | [] |
| BASE-2 | UNKNOWN | UNKNOWN 5.005s | NOT_RUN | NOT_RUN | null | [] |

Hai lịch HF giống hệt nhau, 260 assignments. no-solver-v1 xác nhận SCHEDULE_VALID ×2 và score [13,79,5] ×2, full score object khớp result, 0 forbidden import.

Theo tiêu chí định trước: trên mẫu này ở 5s, Core `ec9ced1` trả lịch hard-valid còn `63506ca` thì không. Kết quả tương thích với giả thuyết rằng bước feasibility hard-only giúp tìm lịch, nhưng không phải bằng chứng nhân quả và không tổng quát ra input hoặc budget khác.

Về chất lượng: score [13,79,5] là score của một lịch hard-valid, không phải tối ưu. Witness có score (0,78,0) nên tốt hơn ở tier 1 và tier 2. Tier 1 hết budget ở incumbent 13 với bound 0, còn tier 2/3 không chạy. n=2/arm, một ca TIGHT, một máy Windows. Không tuyên bố tăng tốc, không đo CPU/RAM/deterministic time.
