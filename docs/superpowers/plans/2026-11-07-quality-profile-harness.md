# Harness chấm Q tự động theo quality profile v0

Ngày 2026-11-07. Trạng thái: **ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-07 (QG1–QG8 theo đề xuất); chưa
triển khai.** Triển khai (Task 0–6) cần lệnh cho phép riêng và, theo QG8, chỉ làm sau khi spike S1-b′ xong
và có báo cáo. Base `d7a8c64` trên `main`.

Thực hiện PV4/PV5 của [quality profile v0](../../quality-profile-v0.md):

- **PV4:** bản máy đọc được `benchmarks/quality-profiles/v0.json` chỉ được tạo cùng lượt sửa harness đã
  được ủy quyền, và SHA256 của nó phải vào plan và seal.
- **PV5:** chấm tay "cho tới khi có kế hoạch chất lượng search (S1)". Kế hoạch S1 đã duyệt ngày
  2026-11-07, nên điều kiện này đã thỏa.

Đây là phần còn mở của [acceptance v2](../../phase-2a-acceptance-v2-draft.md) §3.2, cách 1: "quality
profile đã duyệt trước khi dùng làm gate". Bốn trục H/Q/P/zero và pilot theo D2 đã có trong
`benchmarks/run_phase2.py` (protocol `phase2-linux-v2`), nhưng trục Q ở đó luôn là `REVIEW_REQUIRED`.

Tài liệu chỉ là kế hoạch. Lượt soạn không sửa code, không tạo `v0.json`, không chạy test hay solver.
Duyệt kế hoạch không phải ủy quyền triển khai hay chạy campaign.

## 0. Hiện trạng đã kiểm trong source (chỉ đọc)

| Điểm | Hiện trạng | Hệ quả |
|---|---|---|
| Trục Q | `CaseVerdict.quality` (schema 2.0) chỉ có `REVIEW_REQUIRED` / `NO_SCHEDULE` / `NOT_APPLICABLE`. `judge_case` gán `REVIEW_REQUIRED` cho mọi lịch H PASS (`run_phase2.py:307`) | Chưa có nhãn ACCEPTED / NOT_ACCEPTED |
| Aggregator | `aggregate_phase2.py` gộp Q thành `REVIEW_REQUIRED` và in "(no quality profile)" | Chưa có báo cáo theo profile |
| Identity v2 | `run_phase2.source_ids()` băm `run_phase2.py`, `generate_phase2.py`, `aggregate_phase2.py` cùng các file v1. `run_phase3c.source_ids()` = `r2.source_ids()` cộng 4 file 3C. `_verify_frozen` dựng lại plan và so `source_ids` | **Sửa bất kỳ file nào trong số đó sẽ làm evidence `phase2-v2-linux-02` và `phase3c-linux-02` không kiểm lại được.** Đây là cùng lý do v2 đã không sửa v1 (G1, `test_phase2_v1_frozen.py`) |
| Seal v2 | `plan.json` (`CampaignPlan` schema 2.0, không có chỗ cho profile) và `seal.json` với đúng ba khóa | Không thêm hash profile vào plan v2 mà không sửa `run_phase2.py` |
| ScoreReport 1.2 | Mỗi `RuleScore` có `rule_id`, `code`, `priority`, `weight`, `unit`, `raw_penalty`. Rule theo GV có `scope.teacher_ids` trong input | Chấm được M1–M3 và U1–U5 từ ScoreReport. U6 cần thêm tải tuần của GV từ input (PV3) |
| Biến thể HARD | S02 và S06 là hard, không có dòng soft trong ScoreReport | M2/M3 được bảo đảm bởi H, không phải bởi Q (profile §3) |

## 1. Nguyên tắc

- **Không sửa product code** (`src/`). Không đổi ScoreReport, policy hay contract.
- **Không sửa tooling đã dùng cho campaign** (v1, v2, 3C). Code mới nằm trong module mới và chỉ import.
- **Không đổi gate H/P, pilot hay stop gate.** Q không bao giờ dừng campaign, không chặn pilot (D2), và
  không đổi H/P của run.
- **Profile được chốt trước khi chạy.** SHA256 của `v0.json` vào plan và seal trước run đầu tiên. Profile
  lệch là lỗi identity: dừng.
- **Không chấm lại campaign cũ.** Theo profile v0 §1 và kế hoạch Q §4a, công cụ từ chối campaign không có
  profile seal. `phase2-v2-linux-02` giữ Q = `REVIEW_REQUIRED`.
- **Chỉ synthetic.** ACCEPTED theo v0 là "đạt profile v0 trên synthetic", không phải giáo vụ duyệt lịch.

## 2. Kiến trúc đề xuất (QG1)

Ba module mới, protocol `phase2-linux-v2q`:

| File | Vai trò |
|---|---|
| `benchmarks/quality_profile.py` | Model của `v0.json`; hàm thuần `score_quality(profile, score, input) -> QualityVerdict`. Không import solver hay compiler, giống evaluator độc lập |
| `benchmarks/run_phase2q.py` | `bind`: gắn profile vào campaign đã seal của v2. `run`: kiểm binding rồi giao cho controller v2 **không sửa** |
| `benchmarks/aggregate_phase2q.py` | Kiểm v2 frozen (gọi `aggregate_phase2._verify_frozen`), kiểm binding, chấm Q từng run, báo cáo |

### 2.1 Seal hai tầng (như 3C)

1. **Tầng v2, không đổi.** `run_phase2` prepare và seal như hiện nay: `plan.json`, `environment.json`,
   `seal.json`.
2. **Tầng Q, mới.** `run_phase2q bind` chạy sau seal v2, trước warmup. Nó ghi
   `quality-binding.json`:

   ```json
   {
     "schema_version": "1.0",
     "protocol": "phase2-linux-v2q",
     "v2_plan_sha256": "…",
     "v2_seal_sha256": "…",
     "profile_path": "benchmarks/quality-profiles/v0.json",
     "profile_id": "v0",
     "profile_sha256": "…",
     "q_source_ids": {"quality_profile": "…", "run_phase2q": "…", "aggregate_phase2q": "…"},
     "applicability": {"<dataset_id>": {"M1": "SOFT", "M2": "HARD", "M3": "HARD"}}
   }
   ```

   Sau đó ghi `quality-seal.json` (`binding_sha256`). Đây là "plan và seal" của PV4 ở tầng Q.
3. **Chạy.** `run_phase2q run` kiểm lại binding, profile và `q_source_ids`, rồi ghi `q-journal.jsonl`
   (dòng `START` có `binding_sha256`), rồi gọi đường chạy của `run_phase2` không đổi. Lệch thì
   `STOPPED` trước khi giao cho v2.
4. **Chấm.** Q được chấm ở aggregate, không ở controller. Q không phải gate, nên chấm sau trên evidence
   đã seal cho kết quả giống hệt chấm ngay sau mỗi run, mà không phải đụng đường chạy. `case-verdict.json`
   v2 giữ nguyên; Q mới nằm trong `quality-verdicts.json` riêng.

Aggregator từ chối nếu:

- không có `quality-seal.json`;
- `START` của `q-journal` không đứng trước run đầu tiên trong journal v2;
- hash của profile, binding hoặc nguồn Q lệch.

**Phương án khác (không đề xuất):** viết controller mới với `CampaignPlan` có trường profile. Cách này
nhiều code hơn, phải nhân đôi seal và journal, và có rủi ro lệch khỏi đường chạy đã chạy hai campaign.

## 3. File `v0.json` (QG2)

Nguồn là [profile v0](../../quality-profile-v0.md) đã duyệt; file chỉ chép lại, không đổi giá trị.

```json
{
  "schema_version": "1.0",
  "profile_id": "v0",
  "source_document": "docs/quality-profile-v0.md",
  "approved_on": "2026-11-07",
  "scope": "synthetic",
  "policy_version": "0.4",
  "score_schema_version": "1.2",
  "mandatory": [
    {"id": "M1", "code": "TEACHER_AVOID_SLOTS", "max_raw_penalty_per_row": 0},
    {"id": "M2", "code": "TEACHER_MAX_PERIODS_PER_SESSION", "max_raw_penalty_per_row": 0},
    {"id": "M3", "code": "CLASS_SUBJECT_MAX_PERIODS_PER_DAY", "max_raw_penalty_per_row": 0}
  ],
  "report_only": [
    {"id": "U1", "code": "TEACHER_MAX_PERIODS_PER_DAY", "max_raw_penalty_per_row": 2},
    {"id": "U2", "code": "TEACHER_MAX_GAP_RUN", "max_raw_penalty_per_row": 3},
    {"id": "U3", "code": "SUBJECT_COMPONENT_DAY_SPREAD", "max_raw_penalty_per_row": 2},
    {"id": "U4", "code": "TEACHER_RESTRICTED_SLOTS", "max_raw_penalty_per_row": 1},
    {"id": "U5", "code": "TEACHER_MIN_FREE_TIME", "max_raw_penalty_per_row": 1},
    {"id": "U6", "code": "TEACHER_PREFERRED_PERIOD_WINDOW", "max_share_of_teacher_weekly_load": 0.5}
  ],
  "recorded_without_limit": ["TEACHER_TOTAL_GAPS", "TEACHER_SINGLE_PERIOD_SESSION"]
}
```

- Model pydantic strict: từ chối field lạ, code ngoài catalog policy 0.4, giới hạn âm, mã trùng.
- So sánh dùng `raw_penalty`, không dùng `weighted_penalty`. Ở v2 mọi weight là 1, nên hai giá trị bằng
  nhau.
- Một "dòng" là một `RuleScore`, tức một instance rule: mỗi GV, mỗi requirement hoặc toàn trường, đúng
  như profile §3–§4.
- **U6:** `raw_penalty / tải tuần`. Tải tuần là tổng `periods_per_cycle` của các requirement có GV trong
  `scope.teacher_ids` của rule, đọc từ input đã kiểm SHA256 trong plan. Tải tuần bằng 0 thì ghi
  `NOT_EVALUABLE` (report-only, không đổi nhãn).
- Mọi thay đổi giá trị tạo file mới (`v0.1.json`, `v1.json`); không sửa `v0.json` sau khi commit (PV4).

## 4. Quy tắc chấm (QG3, QG4)

| Tình huống của run | Q mới |
|---|---|
| Dataset UNSAT_CAPACITY | `NOT_APPLICABLE` |
| Không có lịch (UNKNOWN, watchdog, resource stop, chưa chạy) | `NO_SCHEDULE` |
| Có lịch nhưng H khác PASS | `NOT_ASSESSED` (campaign đã STOPPED theo gate H; Q không chấm lịch sai) |
| H PASS, mọi dòng M1–M3 có `raw_penalty = 0` | `ACCEPTED` |
| H PASS, ít nhất một dòng M1–M3 có `raw_penalty > 0` | `NOT_ACCEPTED`, ghi mục vượt, số dòng vượt và tổng penalty |

- **Mục bắt buộc vắng mặt trong ScoreReport (QG4).** Lúc `bind`, mỗi dataset được phân loại cho từng
  mục M:
  - `SOFT`: input có rule soft cùng code;
  - `HARD`: input có rule hard cùng code, H bảo đảm bằng 0;
  - `ABSENT`: không có cả hai. Khi đó `bind` từ chối với `QUALITY_PROFILE_NOT_APPLICABLE`, và campaign
    không chạy.

  Lúc chấm, mục `SOFT` mà không có dòng nào trong ScoreReport là `OUTPUT_MISMATCH`: Q `NOT_ASSESSED`,
  báo cáo nêu rõ.
- **U1–U6 không bao giờ đổi nhãn.** Mỗi run ghi số dòng vượt và giá trị lớn nhất cho từng mục U. S08/S11
  ghi tổng, không giới hạn.
- **Nguồn điểm (QG6).** Chấm từ ScoreReport của `independent-checks/<run>/evaluate-score.stdout`, tức
  đường độc lập. Aggregator so nó với `run.output.score` trong `run.json`. Khác nhau thì Q `NOT_ASSESSED`
  với lý do `SCORE_SOURCES_DIFFER`. Trường hợp này không thể xảy ra nếu H PASS, nên nó cũng là cảnh báo
  tooling.
- Không dung sai. FEASIBLE và OPTIMAL được chấm như nhau (profile §2).

## 5. Báo cáo (QG5)

`aggregate_phase2q` ghi `quality-summary.json` và một mục Markdown:

- Đếm `ACCEPTED` / `NOT_ACCEPTED` / `NO_SCHEDULE` / `NOT_ASSESSED`, tách theo biến thể, quy mô và profile
  dataset. Mẫu số là mọi run known-feasible; null không thành 0.
- Theo dataset: số lần lặp `ACCEPTED` trên 3. Không định nghĩa "dataset đạt" ở đây; S1-c hoặc kế hoạch
  campaign sẽ tự chốt định nghĩa đó.
- Bảng mục M bị vượt (dòng, penalty). Bảng U1–U6 ghi nhận, giống §5 của profile.
- Không có nhãn Q "đạt" ở mức campaign, và Q không ảnh hưởng kết luận H/P/zero của `aggregate_phase2`.
  Mọi câu trong báo cáo ghi rõ "theo profile v0, synthetic".

## 6. Task (TDD; chỉ làm khi được ủy quyền)

| Task | File | Test RED trước |
|---|---|---|
| 0 | — (chỉ đọc) | Ghi SHA256 hiện tại của `run_phase2.py`, `generate_phase2.py`, `aggregate_phase2.py` và 4 file 3C. Đối chiếu với `source_ids` trong `plan.json` của `phase2-v2-linux-02` và `phase3c-linux-02` trên máy người dùng. Nếu đã lệch từ trước, ghi lại, không sửa |
| 1 | `benchmarks/tests/test_phase2_v2_frozen.py` | Ghim byte-identical 7 file trên, theo mẫu `test_phase2_v1_frozen.py` |
| 2 | `benchmarks/quality-profiles/v0.json`, `benchmarks/quality_profile.py`, test | Parse strict; từ chối field lạ, code lạ, giới hạn âm. Bảng §4 từng nhánh. M vượt 1 dòng → NOT_ACCEPTED. U vượt → vẫn ACCEPTED, có ghi nhận. U6 theo tỷ lệ tải, tải 0 → NOT_EVALUABLE. HARD-only → ACCEPTED. SOFT vắng dòng → NOT_ASSESSED. Ba mẫu dựng lại theo breakdown của biên bản A/B/C → ACCEPTED / NOT_ACCEPTED (M1) / NOT_ACCEPTED (M1, M2, M3). Module không import `ortools` hay `tkb_core.solver` (guard như evaluator) |
| 3 | `benchmarks/run_phase2q.py`, test | `bind` từ chối plan chưa seal, dataset `ABSENT`, binding đã tồn tại. Ghi exclusive. `run` dừng khi profile, binding hoặc nguồn Q lệch, trước khi gọi v2. Đường chạy v2 được gọi với đúng tham số như khi gọi trực tiếp (spy) |
| 4 | `benchmarks/aggregate_phase2q.py`, test | Từ chối campaign không có binding (kể cả fixture giống `phase2-v2-linux-02`). Kiểm thứ tự `START` so với run đầu. So hai nguồn score. Mẫu số đủ. Q không đổi H/P/zero. Output exclusive, ngoài đường dẫn frozen |
| 5 | — | `uv run --extra solver pytest tests benchmarks/tests`, ruff, format, mypy. Kiểm lại: `aggregate_phase2._verify_frozen` và 3C vẫn qua trên fixture |
| 6 | — (chỉ đọc, local) | Kiểm scorer bằng một lần replay trên 162 ScoreReport của `phase2-v2-linux-02` (script ngoài repo, output vào scratchpad). Phải tái tạo đúng bảng §5 của profile: 72/162 đạt M1–M3, A/B/C đúng như biên bản. **Đây là kiểm công cụ, không phải verdict Q của campaign đó**, và không ghi vào evidence của campaign |

Không thêm `benchmarks` vào wheel hay sdist, không thêm dependency. `benchmarks/artifacts/` vẫn local.

## 7. Ranh giới phê duyệt

| Bước | Cần duyệt riêng |
|---|---|
| A. Duyệt kế hoạch, QG1–QG8 | Có (lượt này dừng ở đây) |
| B. Task 0–6 trong working tree, chạy checks | Có |
| C. Commit và push tooling | Có |
| D. Dùng `phase2-linux-v2q` cho một campaign (bind, run) | Có, trong kế hoạch campaign riêng (ví dụ S1-c) |

## 8. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Vô tình sửa file v2/3C làm hỏng kiểm lại evidence cũ | Task 1 ghim hash; review diff chỉ có file mới |
| Q chấm sau, nên có thể chạy campaign bằng `run_phase2` trực tiếp rồi gắn profile sau khi thấy kết quả | Aggregator đòi `START` của `q-journal` đứng trước run đầu tiên; binding ghi exclusive |
| `v0.json` chép sai so với tài liệu | Test so từng giá trị với bảng §3–§4 của profile; replay Task 6 tái tạo bảng §5 |
| Người đọc hiểu ACCEPTED là "giáo vụ đã duyệt" | Nhãn luôn đi kèm "theo profile v0, synthetic" |
| ScoreReport chỉ có tổng theo dòng, nên U1 không chặn được "ngày 7 tiết" | Ghi trong báo cáo như giới hạn đã biết của profile §4; sửa cần ScoreReport mới, ngoài kế hoạch này |

## 9. Quyết định cần duyệt

- [x] **QG1 — Kiến trúc:** ba module mới, seal hai tầng, Q chấm ở aggregate; không sửa file v1/v2/3C.
  *(Đề xuất: chọn.)*
- [x] **QG2 — `v0.json`:** nội dung như §3, so theo `raw_penalty`, U6 theo tỷ lệ tải tuần. *(Đề xuất:
  chọn.)*
- [x] **QG3 — Nhãn:** thêm `NOT_ASSESSED` cho lịch có H khác PASS hoặc dữ liệu chấm không nhất quán.
  Không ép thành NOT_ACCEPTED. *(Đề xuất: chọn.)*
- [x] **QG4 — Mục M vắng mặt:** `HARD` = đạt (do H bảo đảm); `ABSENT` = `bind` từ chối. *(Đề xuất:
  chọn.)*
- [x] **QG5 — Báo cáo:** đếm theo run và theo dataset (k/3). Không có nhãn Q đạt ở mức campaign; định
  nghĩa "dataset đạt" để kế hoạch campaign tự chốt. *(Đề xuất: chọn.)*
- [x] **QG6 — Nguồn điểm:** chấm từ `evaluate-score` độc lập, đối chiếu với `run.json`. *(Đề xuất:
  chọn.)*
- [x] **QG7 — Kiểm công cụ bằng replay** trên `phase2-v2-linux-02` (Task 6), ghi là kiểm công cụ, không
  phải verdict. *(Đề xuất: chọn. Phương án khác: chỉ dùng fixture, bỏ Task 6.)*
- [x] **QG8 — Thời điểm:** triển khai sau khi spike S1-b′ chạy xong và có báo cáo, vì full test suite
  nặng CPU sẽ làm nhiễu phép đo theo wall time. *(Đề xuất: chọn.)*

## 10. Kiểm tra khi soạn

- Đọc `benchmarks/run_phase2.py` (`CaseVerdict`, `judge_case`, `CampaignPlan`, `source_ids`, seal và
  `check_campaign_identity`), `benchmarks/aggregate_phase2.py` (cách gộp Q, `_verify_frozen`),
  `benchmarks/run_phase3c.py` (`source_ids`), `benchmarks/tests/test_phase2_v1_frozen.py`,
  `src/tkb_core/contracts/score.py`, cùng [profile v0](../../quality-profile-v0.md) và
  [acceptance v2](../../phase-2a-acceptance-v2-draft.md).
- Code của 11 rule lấy từ `src/tkb_core` bằng grep.
- Không chạy test, solver hay campaign; không đụng spike S1-b′; không sửa file nào khác.
