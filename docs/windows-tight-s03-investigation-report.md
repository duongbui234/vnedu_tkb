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
| tier-search-experiments-v3 | `4af9e8f5ce0b01a7229f4235d5063954465cb088013e38c5eba02559e823ed75` |
| tier-b1-sticky-sim-v1 | `36ca5d4f2a7b54a8272053c8fbdc54445b5ce41617fb129b7ac0f25a6a20162b` |
| tier-b1-impl-v1 | `e031765395e192b397097eeb5cf35fde1c6e7c733e3abce2db1fa1788b5866fd` |
| tier-b1-eval-v1 | `6800016f16e257e7d659c1211c70affb7b62271d25e9d8ceecc1759fb54f8416` |
| tier-b1-robustness-v1 | `abf4b945e4c30401d72a1a413264423ce1e4a78871afad8fe1f40abb3a9be1c5` |
| independent-validation-v1 | `35d82dd6cb6ce180e9d59f9f82e7105a6295dedcde6740a6dbbbde897f71ade9` |
| tight-s103-diagnosis-v1 | `ee8b0b529a28b39d82e6d3566aba12d2c95810c7ae58c7f1228ed4e922205a11` |

Hồ sơ thiết kế tương ứng: `windows-s03-core-bounds-design-v1`, `windows-tight-s03-bounds-eval-design-v1`, `windows-tight-s03-bounds-eval60-design-v1`, `windows-tight-dettime-design-v1`. Lượt hardfeas-eval-v1 dùng lại harness, gates và bảng diễn giải của eval-v2. Mục 8 dựa trên hồ sơ `tier-b1-impl-design-v1` (manifest `0af5a87d8ff302c9a9b3a7bbd1e38546094bd13f2762dced4733306ff9e8f6a9`).

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

## 8. Tier search hai pha, sticky (`d050eb0`) trên tight, mixed và base

Ở 60s với 1 worker, Core `ffae995` dừng tier 1 của c10-tight-s101 ở 13: search tuần tự không cải thiện được incumbent đã hint. Nếu luôn bật `interleave_search` cho stage tier thì tight được cứu, nhưng tier 3 của base bị bỏ đói (thử nghiệm trên branch `feat/tier-interleave-search`, không merge).

Commit `d050eb0` cho mỗi stage tier tìm tuần tự tối đa 12 deterministic seconds trước. Nếu chưa proof, stage chuyển sang interleave với phần budget còn lại. Từ đó các tier sau interleave ngay (xem [solver-design.md](solver-design.md)). Giá trị 12 lấy từ deterministic time mà search tuần tự cần trên base (tối đa 10.854) và mixed (tối đa 1.647), cùng phần budget còn lại cho tight (tier-search-experiments-v3).

Thiết lập: ABBA CLI 60s/seed 42/workers 1 trên tight, mixed và base. BASE = `ffae995`, NEW = `d050eb0`. Venv NEW cài non-editable với `--reinstall-package`; identity strict 28/28 cho cả hai venv; structural gate PASS.

| Case | BASE ×2 | NEW ×2 |
|---|---|---|
| tight | FEASIBLE [13,79,5], prefix [] | OPTIMAL [0,78,0], prefix [1,2,3]; tier 1 ≈ 50.5s (hai pha), tier 2/3 < 0.6s |
| mixed | OPTIMAL [0,0,0] | OPTIMAL [0,0,0], cùng lịch với BASE |
| base | OPTIMAL [0,0,0] | OPTIMAL [0,0,0], cùng lịch với BASE |

no-solver-v1: 12/12 lịch SCHEDULE_VALID, score khớp toàn phần, 0 forbidden import. Mỗi arm cho cùng lịch ở cả hai lần chạy.

Theo tiêu chí định trước, không case nào kém `ffae995`, và tight đạt OPTIMAL. Giới hạn:
- n=2/arm, ba ca tổng hợp, một máy Windows.
- Giá trị 12 được chọn từ chính ba ca này.
- Trên tight, sau tier 1 còn khoảng 9s budget. Độ bền khi máy chậm hơn được đo ở mục 8.1.
- `interleave_search` là Experimental trong OR-Tools 9.15.

Không tuyên bố tăng tốc.

### 8.1. Độ bền của S = 12 trên tight khi máy chậm hơn

Lát tuần tự dừng ở 12 deterministic seconds, nên trên máy chậm nó chiếm nhiều wall hơn mà không ngắn lại. Lượt `tier-b1-robustness-v1` mô phỏng máy chậm đều f lần bằng cách giảm budget xuống 60/f (hồ sơ `tier-b1-robustness-design-v1`, manifest `616f908fd587facd8c05ecc9f24bab493ca86b157aab12fd5cdd428b022f5313`).

Thiết lập: ABBA CLI trên c10-tight-s101, seed 42, workers 1; BASE = `ffae995`, NEW = `1bc3bfc`; identity strict 28/28 cho cả hai venv.

| Budget | f tương đương | BASE ×2 | NEW ×2 |
|---|---|---|---|
| 55s | 1.09 | FEASIBLE [13,79,5] | OPTIMAL [0,78,0], prefix [1,2,3] |
| 52s | 1.15 | FEASIBLE [13,79,5] | OPTIMAL [0,78,0], prefix [1,2,3]; solver wall 51.3s |
| 50s | 1.20 | FEASIBLE [13,79,5] | FEASIBLE [4,79,2], prefix []; pha interleave của tier 1 bị cắt |

no-solver-v1: 12/12 lịch SCHEDULE_VALID, score khớp, 0 forbidden import. Mỗi arm cho cùng lịch ở cả hai lần chạy.

Ngưỡng nằm trong (50, 52]s, tương ứng máy chậm hơn khoảng 15%. Chậm hơn mức đó, tight trả FEASIBLE: vẫn tốt hơn `ffae995` ở tier 1, nhưng không còn proof.

Giới hạn:
- Giảm budget chỉ mô phỏng thô một máy chậm và giả định mọi phần wall chậm đều; chưa đo trên máy chậm thật.
- Một ca, n=2/arm mỗi budget, một máy Windows.
- Base và mixed không chạy lại ở budget nhỏ.

Không tuyên bố tăng tốc.

### 8.2. Kiểm chứng trên các ca chưa dùng để chọn S, và chẩn đoán tight-s103

S = 12 và quy tắc sticky được chọn từ ba ca `c10-*-s101`. Lượt `independent-validation-v1` kiểm trên sáu ca c10 seed 102 và 103, sinh bằng `benchmarks/generate_synthetic.py` tại `4709f1a` (hồ sơ `independent-validation-design-v1`, manifest `f68532088cdfc1debebef5d7970df635122a4efdaaf6d5d6db0b0145f2c44000`). Bundle sinh lại cho c10 s101 trùng từng byte input và witness với bộ dataset đã dùng trước đây.

Thiết lập: ABBA CLI 60s/seed 42/workers 1, BASE = `ffae995`, NEW = `4709f1a`. Venv NEW cài non-editable với `--reinstall-package`. Identity strict 28/28 cho cả hai venv; structural gate PASS cho 6 ca.

| Ca | BASE ×2 | NEW ×2 | Score của witness |
|---|---|---|---|
| tight-s102 | FEASIBLE [5,78,3] | OPTIMAL [0,80,0], prefix [1,2,3] | [0,80,0] |
| tight-s103 | FEASIBLE [8,81,2] | FEASIBLE [2,83,1], tier 1 hết budget | [0,83,0] |
| base-s102 | OPTIMAL [0,0,0] | OPTIMAL [0,0,0], cùng lịch | [0,0,0] |
| base-s103 | FEASIBLE [0,0,111], tier 3 hết budget | FEASIBLE [0,0,111], cùng lịch | [0,0,0] |
| mixed-s102 | OPTIMAL [0,0,0] | OPTIMAL [0,0,0], cùng lịch | [0,0,0] |
| mixed-s103 | OPTIMAL [0,0,0] | OPTIMAL [0,0,0], cùng lịch | [0,0,0] |

no-solver-v1: 24/24 lịch SCHEDULE_VALID, score khớp toàn phần, 0 forbidden import. Mỗi arm cho cùng lịch ở cả hai lần chạy.

Theo tiêu chí định trước, cả sáu ca đều không kém `ffae995`: NEW ≤lex BASE ở mọi run, và ở mọi ca BASE OPTIMAL thì NEW cũng OPTIMAL. Riêng base-s103 hết budget ở tier 3 với cả hai Core và cho cùng lịch, nên đây là giới hạn budget có từ trước, không do S hay sticky gây ra.

Lượt `tight-s103-diagnosis-v1` (hồ sơ `tight-s103-diagnosis-design-v1`, manifest `b3000e18d49a2090ad184818b100c5a6e2e790f1b6c77eeb5529f1d6f282db42`) chạy `4709f1a` có bật log từng pha, n=1. Ở 60s, driver tái hiện đúng lịch CLI.

| Lượt | Lát tuần tự tier 1 | Interleave tier 1 | Kết quả |
|---|---|---|---|
| s103, 60s | 22.6s, 11 → 9 | 35.3s budget, về 2, không proof | FEASIBLE [2,83,1] |
| s103, bỏ lát, 60s | – | 57.8s (40.6 det), về 2, không proof | FEASIBLE [2,82,0] |
| s103, 180s (chỉ để đo) | 22.6s, 11 → 9 | 37.5s (24.7 det), về 0 | OPTIMAL [0,83,0], cả lần solve 64.7s |
| s102, 60s | 23.3s, đứng ở 10 | 6.8s (4.7 det), về 0 | OPTIMAL [0,80,0] |

Trên tight-s103, tier 1 cần khoảng 60.1s trong khi budget còn lại khoảng 59.5s; cả lần solve cần khoảng 65s trên máy này. Bỏ lát tuần tự cũng không proof được trong 60s. Ở 60s, kết quả FEASIBLE [2,83,1] vẫn tốt hơn `ffae995` ở tier 1. Đây được ghi như một giới hạn đã biết; không đổi code hay budget mặc định.

Giới hạn:
- Chỉ c10, seed 102/103; n=2/arm cho ABBA và n=1 cho chẩn đoán; một máy Windows.
- Tight không có known optimum; score của witness chỉ là một lịch đã biết.
- CLI không ghi pha; số đo từng pha chỉ có ở lượt chẩn đoán.
- c20 và c40 chưa được đánh giá.

Không tuyên bố tăng tốc.
