# Phase 2A — báo cáo nghiệm thu Linux (campaign `phase2-v2-linux-02`)

Ngày 2026-11-06. Trạng thái: **DRAFT — chờ người dùng duyệt.** Đây là báo cáo kết quả theo bước G
của [kế hoạch hiệu năng v2](superpowers/plans/2026-11-05-phase-2-linux-performance-v2.md) (M6 của
[kế hoạch F](superpowers/plans/2026-11-05-phase-2-linux-performance-step-f.md)), áp dụng tiêu chí
[acceptance v2](phase-2a-acceptance-v2-draft.md) D1–D3 đã duyệt.

**Kết luận một dòng:** trên máy Linux của người dùng, candidate `7e47f74` đạt **H PASS** và
**P MET** cho đủ 216/216 run primary; **Q giữ REVIEW_REQUIRED**; **benchmark zero là kết quả riêng**
(NOT_APPLICABLE cho toàn bộ ma trận này, verdict zero lịch sử NOT_MET giữ nguyên). Đây là nghiệm thu
**H/P của campaign Linux v2 cho một candidate chưa merge trên một máy**, không phải nghiệm thu vận hành
toàn Phase 2A, không phải chất lượng giáo vụ được chấp nhận, không phải Windows/cross-OS, SLA hay P95.

## 1. Đối tượng được đo

| Mục | Giá trị |
|---|---|
| Campaign ID | `phase2-v2-linux-02` (ID mới theo M2/M5 sau khi `phase2-v2-linux-01` bị gián đoạn) |
| Source | `7e47f74515f0681c1d6a5bbdde7241c369f02e87`, branch `work/hard-feasibility-no-lp` (base `120058e` trên `main` + 1 commit no-LP). **Chưa merge vào `main`** |
| Thay đổi so với base | `linearization_level=0` chỉ ở native call hard-only đầu tiên của public quality solve workers1; model, budget, gate, schema không đổi. Xem [review commit](hard-feasibility-no-lp-commit-review.md) |
| Protocol | `phase2-linux-v2`, policy 0.4, output 1.5, ScoreReport 1.2 |
| Ma trận | 72 datasets (3 quy mô × 4 profile × 3 seed × SOFT/HARD) × 3 repeats = **216 primary**: 162 known-feasible, 54 UNSAT_CAPACITY |
| Cấu hình | workers1, seed42; budget 60/120/180 s; watchdog 150/210/270 s; RSS target 1/2/4 GiB; reserve 2 GiB. Không đổi so với kế hoạch |
| Máy | i7-12700H, 20 logical CPU, RAM 40,7 GB, kernel 7.0.0-42-generic, Python 3.12.3, cgroup v2. Workload **UNCONTROLLED** (G9) |
| Plan SHA256 | `cf9c5b82cb25997144683b5f22924aff5cb3f432815024671870d466f871e99e` |
| Seal SHA256 | `c23eb2ce449e0cd71176268918164b396236cc3847a6f0894ce0b1fb7da9e437` |
| Preflight SHA256 | `1477cd93895689b47bd3bcd7f86a5d9315430a4d35d4a1a9ed531adb68b7fbb4` |
| Summary SHA256 | `76735553ba8b5173c8e3ab20daed92a07891b66033be4838d87c86424e917e21` |
| Gói evidence | `phase2-primary-02.tar.gz`, SHA256 `906db8180cc168051c6a8bd6a4c713974ca02d9eab7bfe082f8a15470a583a07` |

Trình tự: preflight/bundle (D) → prepare, warmup, 2 pilot SOFT/HARD đều PASS (E) → người dùng cho mở
primary → primary 216 run dưới `tmux` + `systemd-inhibit`, không retry/resume → aggregate.
Primary exit 0, controller `COMPLETE` (attempted 216, completed 216, failed 0, pending 0); aggregate
exit 0, `SUMMARIZED`. Owner marker cuối `IDLE`.

## 2. Kết quả theo trục acceptance v2

| Trục | Kết quả campaign | Đếm theo run | Kết luận |
|---|---|---|---|
| **H** — hard validity, tính đúng | **PASS** | PASS 216/216 | **Đạt.** 162 lịch được validate/score lại độc lập bằng venv không OR-Tools; 54/54 UNSAT trả INFEASIBLE đúng kỳ vọng |
| **P** — tìm lịch trong giới hạn | **MET** | MET 162/162 known-feasible; NOT_APPLICABLE 54 (UNSAT) | **Đạt** theo định nghĩa §4 kế hoạch v2: đủ 216 outcomes và measurements, 162/162 có lịch hard-valid trong watchdog và RSS target, 54/54 UNSAT đúng, 0 missing, 0 censored |
| **Q** — chất lượng soft | **REVIEW_REQUIRED** | REVIEW_REQUIRED 162; NOT_APPLICABLE 54 | **Giữ nguyên.** Chưa có quality profile (G7); không có nhãn ACCEPTED |
| **Zero** — benchmark riêng | NOT_APPLICABLE | NOT_APPLICABLE 216 | Không dataset nào trong ma trận v2 có witness `[0,0,0]` (G5), nên ma trận này không đo zero. Verdict zero lịch sử (`[0,5,120]` so witness `[0,0,0]`, NOT_MET) **giữ nguyên**, không bị thay bằng kết quả này |

Status solver: FEASIBLE 153, OPTIMAL 9 (toàn bộ là HARD/c10/TIGHT), INFEASIBLE 54. Không có UNKNOWN,
watchdog, resource stop, crash hay measurement thiếu.

## 3. Hiệu năng theo biến thể và quy mô

Launch-to-exit là thời gian từ launch tới khi process thoát, chỉ tính trên run có lịch
(conditional-on-success; ở campaign này mọi known-feasible đều có lịch). RSS là peak resident của child.

| Biến thể | Lớp | Run có lịch | Launch-to-exit max (s) | Budget / watchdog (s) | Peak RSS max (MiB) | RSS target (MiB) |
|---|---:|---:|---:|---:|---:|---:|
| HARD | 10 | 27/27 | 61,079 | 60 / 150 | 397,2 | 1 024 |
| HARD | 20 | 27/27 | 122,432 | 120 / 210 | 554,9 | 2 048 |
| HARD | 40 | 27/27 | 184,333 | 180 / 270 | 573,2 | 4 096 |
| SOFT | 10 | 27/27 | 61,196 | 60 / 150 | 471,6 | 1 024 |
| SOFT | 20 | 27/27 | 122,258 | 120 / 210 | 692,5 | 2 048 |
| SOFT | 40 | 27/27 | 183,940 | 180 / 270 | 616,1 | 4 096 |

Bảng đầy đủ theo dataset (min/median/max, RSS) nằm trong `summary-02/summary.md` và báo cáo thực thi
`campaign-02-primary-execution/report.md` (evidence local).

Cách đọc:

- Phần lớn run feasible kết thúc ở khoảng budget solver + vài giây overhead, vì search dùng hết
  wall-time để cải thiện soft score rồi trả FEASIBLE. Đây **không** phải time-to-first-feasible và
  không phải SLA; biên an toàn đo được là so với watchdog (≥ 85 s ở mọi quy mô), không so với budget.
- RSS cao nhất tuyệt đối 692,5 MiB (SOFT/c20, 34 % target); tỷ lệ cao nhất so với target là SOFT/c10
  (471,6/1 024 MiB, 46 %).
- n = 3 mỗi fingerprint: không tính P95/SLA, không gộp fingerprint khác nhau.

## 4. Chất lượng: thông tin, không phải nghiệm thu

So witness (thông tin benchmark, không phải quyết định giáo vụ): WORSE 142, BETTER 11
(HARD/c10/MIXED 3, SOFT/c10/MIXED 8), EQUAL 9 (HARD/c10/TIGHT), không áp dụng 54 (UNSAT). WORSE so
witness không làm H hay P thất bại; H đã kiểm không có vector proof-prefix hoặc claim optimal nào tệ hơn
witness.

Quan sát pilot cùng input/cùng wheel: `c10-base-s101-soft` cho `[46,146,211]` ở pilot campaign-02 nhưng
`[0,106,219]` ở diagnostic trước đó; `c10-base-s101-hard` lặp lại `[7,71,250]`. Dưới search giới hạn
wall-time, score soft có thể khác giữa các lần chạy; chưa xác định nguyên nhân duy nhất. Điều này là lý do
thêm để Q phải được duyệt theo kết quả cụ thể hoặc profile, không suy từ một lần chạy.

## 5. Kiểm chứng đã thực hiện

Kiểm tra trong lượt thực thi campaign (đã lưu trong `verification.json`, `status: VERIFIED`):

- 219 terminal receipts (warmup + 2 pilot + 216 primary) và 438 journal events hợp lệ; không run dở
  dang bị che.
- 162 lịch trả về được `validate-schedule` và `evaluate-score` lại bằng venv không OR-Tools.
- Identity preflight/source/runtime/machine/seal khớp; receipts pre-primary và prefix journal của pilot
  không đổi.
- 761 file của campaign cũ `phase2-v2-linux-01` giữ nguyên SHA256.

Kiểm lại read-only trong lượt soạn báo cáo này (chỉ Python stdlib và `sha256sum`, không gọi solver):

- SHA256 của `plan.json`, `seal.json`, `summary.json` khớp các giá trị ở §1.
- `journal.jsonl` có đúng 219 `START` + 219 `TERMINAL`; `campaign-state.json` là `COMPLETE`, 216/216,
  failed 0.
- `sha256sum -c` trên manifest `campaign-02-primary-execution/SHA256SUMS` (2 533 entries): toàn bộ OK.
- Đếm `status` trong 216 `result.json` khớp §2.

Không chạy lại pytest/lint/mypy trong lượt này. Kết quả kiểm source của candidate là kết quả đã lưu trong
[review commit](hard-feasibility-no-lp-commit-review.md) (pytest 1 118 passed; benchmarks/tests 446
passed, 8 skipped; ruff, format, mypy PASS).

## 6. Hạn chế

1. **Candidate chưa merge.** Kết quả gắn với `7e47f74`, không với `main` (`120058e`) và không với commit
   ghim `86f624d` của runbook D/E/F. Không được dán nhãn kết quả này cho source khác; nếu merge làm đổi
   source của wheel, cần preflight nhận dạng lại.
2. **Baseline không có số đo đầy đủ.** Campaign `phase2-v2-linux-01` trên `86f624d` bị gián đoạn
   (104 primary terminal, 1 partial, 111 chưa chạy) và giữ nguyên; owner đã được chuyển IDLE nhưng không
   resume. Vì vậy báo cáo này **không** chứng minh no-LP nhanh hơn hay tốt hơn baseline; chỉ chứng minh
   candidate đạt H/P.
3. **Một máy, workload UNCONTROLLED**, n = 3 mỗi fingerprint: không P95, không SLA, không suy ra máy khác.
4. **Q REVIEW_REQUIRED.** Không có lịch nào được chấp nhận cho giáo vụ; WORSE so witness chiếm 142/162.
   Score soft có biến thiên giữa các lần chạy (§4).
5. **Zero tách riêng và không được đo ở ma trận này.** Không được viết "đạt zero" hay "zero không còn là
   vấn đề"; verdict zero lịch sử NOT_MET giữ nguyên.
6. **Linux-only.** Windows/cross-OS chưa có evidence cho candidate này (S2); `windows_status: NOT_RUN`.
7. **Synthetic.** Dataset sinh với priority/weight benchmark (G3), không phải policy trường; dữ liệu và
   quy tắc thật vẫn UNKNOWN.
8. **Evidence thô chỉ ở local** (`benchmarks/artifacts/hard-feasibility-no-lp/`, ignored). Clone cloud
   không có chúng; không được fabricate lại.

## 7. Trạng thái Phase 2A sau báo cáo

| Phạm vi | Trạng thái |
|---|---|
| Kỹ thuật synthetic | Đạt (mốc lịch sử, không đổi) |
| H campaign Linux v2 (candidate `7e47f74`) | **Đạt** — 216/216 |
| P campaign Linux v2 (candidate `7e47f74`) | **Đạt** — 162/162 known-feasible, 54/54 UNSAT |
| Q chất lượng giáo vụ | REVIEW_REQUIRED |
| Benchmark zero | Riêng; NOT_APPLICABLE ở ma trận v2; lịch sử NOT_MET |
| Windows/cross-OS | Chưa nghiệm thu |
| Nghiệm thu vận hành toàn Phase 2A | **Chưa** — thiếu Q và Windows; candidate chưa merge |

## 8. Bàn giao

Đi theo nhánh khi được duyệt commit: báo cáo này và các cập nhật trạng thái trong
[báo cáo hiện trạng](project-status-report.md), [tiến độ Phase 2](phase-2-progress-report.md),
[review commit no-LP](hard-feasibility-no-lp-commit-review.md).

Ở lại local (không commit, không force-add): `benchmarks/artifacts/hard-feasibility-no-lp/` gồm
`campaign-02/`, `campaign-02-execution/`, `campaign-02-primary-execution/`, `summary-02/`,
`preflight-20261105-v1/`, `primary-02.out` và `phase2-primary-02.tar.gz`; cùng
`benchmarks/artifacts/owner-recovery/`. Muốn người khác kiểm lại thì chuyển gói tar và đối chiếu SHA256 ở §1.

Các quyết định còn thuộc người dùng, mỗi mục cần ủy quyền riêng:

1. Duyệt báo cáo này; commit docs (và commit candidate nếu chưa) lên `work/hard-feasibility-no-lp`.
2. Merge candidate vào `main` hay không. Sau merge, ghi rõ source merge có trùng `7e47f74` hay không.
3. Q: chốt quality profile cho run tương lai, hoặc duyệt kết quả cụ thể theo result hash.
4. Có cần baseline so sánh (campaign mới trên `86f624d`/`main`) để kết luận hiệu quả của no-LP không.
5. Windows là mốc riêng (S2).

Không làm trong lượt soạn báo cáo: không chạy solver/pilot/campaign, không sửa code, gate, plan hay
evidence, không commit, merge hoặc push.
