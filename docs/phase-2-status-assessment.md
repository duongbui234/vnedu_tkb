# Phase 2 — đánh giá trạng thái toàn phase

Ngày 2026-11-05. Trạng thái: **E1–E4 và E6 ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-05; E5 chưa quyết định
(giữ quy tắc version hiện tại).** Duyệt không phải ủy quyền chạy campaign hay sửa code. Base `486c6a1d7c181610b917adfa627fcda6fcb112`
(merge duongbui234/vnedu_tkb#3 vào `main`); source/tests trùng với `6a1d937`.

Đây chỉ là tài liệu đánh giá và đề xuất. Không sửa `src/`, `tests/`, `benchmarks/`, gate, budget hay pins;
không chạy test, solver hay campaign trong lượt này. Mọi con số dưới đây là kết quả **đã lưu** trong các
báo cáo được dẫn, không phải đo lại. Duyệt tài liệu này không phải ủy quyền chạy campaign hay viết code.

## 1. Kết luận ngắn

- **Kỹ thuật synthetic: Phase 2 đã đạt theo tiêu chí Core First.** Tiêu chí “có fixture chứng minh soft
  score được cải thiện so với baseline mà không vi phạm hard constraints; test pass” và phạm vi
  “nguyện vọng giáo viên, phân phối môn, giảm tiết trống” đã có hiện thực, evaluator độc lập và oracle
  cho S01–S11 cùng hard variants S01–S06.
- **Vận hành: chưa nghiệm thu.** Chưa có số đo hiệu năng cho các rule sau 2A; campaign Linux duy nhất
  (2A) dừng ở primary 0/108; Windows/cross-OS chưa chạy cho candidate hiện tại; chất lượng giáo vụ
  REVIEW_REQUIRED; acceptance v2 vẫn DRAFT.
- **Dữ liệu thật: chưa có.** Mọi ngưỡng, nhóm component, ô hạn chế và lịch họp là UNKNOWN; Core không
  có giá trị mặc định và không được tự suy ra.
- **Còn lại trong phạm vi Phase 2:** S12 (theo policy chỉ làm từng instance khi có use case).

## 2. Đã đạt — technical synthetic

| Mốc | Nội dung | Bằng chứng (đã lưu) |
|---|---|---|
| 2A | S01–S04 soft, priority P1–P3 lexicographic, independent evaluator, CLI/package; input 1.1/policy 0.1 → output 1.2 | [Chốt kỹ thuật 2A](phase-2a-technical-closeout.md), [báo cáo 2A](phase-2a-report.md) |
| 2B | Hard variants S01–S04 (policy 0.2 → output 1.3); validator `HARD_*` | [Báo cáo 2B](phase-2b-report.md), [rà soát](phase-2b-review.md) (F1 đã sửa) |
| 2C-1 | S05/S06 soft + hard (policy 0.3 → output 1.4, ScoreReport 1.1) | [Báo cáo 2C-1](phase-2c-report.md), [rà soát](phase-2c-review.md) (F1 kích thước model đã sửa) |
| 2C-2 | S07–S11 soft + `occupied_work` (policy 0.4 → output 1.5, ScoreReport 1.2) | [Báo cáo 2C-2](phase-2c-gaps-report.md), [rà soát](phase-2c-gaps-review.md) (F1 contract đã sửa) |

Kiểm tra gần nhất trên source hiện tại (`6a1d937`): `uv run --extra solver pytest tests benchmarks/tests`
**1271 passed, 8 skipped**; ruff, format, mypy PASS. Installed wheel `cdd34282…35d1` kiểm trên Linux (hai
venv sạch, có/không OR-Tools), 30/30 file khớp source. Mỗi mốc có oracle vét cạn (60 seeds, ordering
bật/tắt) và giữ nguyên hash/hành vi của các policy cũ.

Các rà soát là **tự kiểm lại trong cùng phiên** với người triển khai, không phải review độc lập của người
thứ hai. Ba PR đã được merge mà không có review comment hay CI (repo chưa có `.github`).

## 3. Còn mở

| ID | Hạng mục | Trạng thái hiện tại | Cần gì để đóng |
|---|---|---|---|
| A | **Acceptance v2** | [D1–D3 đã duyệt 2026-11-05](phase-2a-acceptance-v2-draft.md) (E1); protocol/harness/gate mới chưa triển khai | Triển khai protocol v2 khi được ủy quyền |
| B | **Hiệu năng (trục P)** | Campaign Linux 2A: primary 0/108, STOPPED; benchmark harness/generator chỉ biết policy 0.1 và output 1.2 (`run_benchmarks.py` kiểm `schema_version == "1.2"`; generator tạo `ConstraintConfigV11(policy_version="0.1")`); **không có số đo nào** cho hard variants hay S05–S11 | Protocol mới (sau A), mở rộng harness/generator sang policy 0.4 có kiểm soát, campaign được ủy quyền |
| C | **Windows/cross-OS** | Evidence Windows chỉ cho snapshot cũ; wheel hiện tại chưa chạy trên Windows | Chạy trên máy Windows của người dùng (cloud không làm được), đối chiếu kết quả chéo |
| D | **Chất lượng giáo vụ (trục Q)** | Pilot `[0,5,120]` REVIEW_REQUIRED; chưa có quality profile | Chủ thể nghiệp vụ duyệt profile trước run, hoặc duyệt kết quả cụ thể theo hash |
| E | **Benchmark zero** | NOT_MET (giữ nguyên lịch sử) | Không bắt buộc nếu D1 của acceptance v2 được duyệt; vẫn là benchmark riêng |
| F | **Dữ liệu thật** | Ngưỡng H10, nhóm S05, ô hạn chế, lịch họp, mục tiêu ngày rảnh: UNKNOWN | Application/upstream xác nhận; ngoài Core |
| G | **S12** | Chưa có; policy: “chỉ bật instance có semantics/unit riêng” | Một use case cụ thể (ví dụ ưu tiên phòng, đầu/cuối buổi) |
| H | **Chẩn đoán INFEASIBLE** | Không chỉ ra rule gây vô nghiệm (không IIS/relax) | Thiết kế riêng (thuộc diagnostics Phase 3) |
| I | **Số phiên bản contract** | Policy 0.1–0.4, output 1.1–1.5, ScoreReport 1.0–1.2; mỗi mốc thêm một version | Quyết định có gom version cho các mốc sau hay không |

## 4. Rủi ro đáng chú ý

- **Hiệu năng chưa biết là rủi ro lớn nhất.** S08/S09 thêm ~170–230 biến mỗi rule trên fixture 6 ngày ×
  2 buổi × 5 tiết, 1 GV; S05 soft tăng bậc hai theo cỡ nhóm (có guard 20 000 cặp). Đây là số đếm model,
  không phải thời gian solve. Lịch có nhiều GV và nhiều rule cùng bật có thể vượt budget 60/120/180 s mà
  hiện chưa ai đo.
- **Benchmark cũ không bao phủ code mới.** Mọi kết luận P đã lưu chỉ áp dụng cho S01–S04 policy 0.1 ở
  snapshot cũ; không được chuyển sang candidate hiện tại.
- **Tích hợp:** `occupied_work` đòi availability tường minh; S10 tính ngày chỉ-unavailable là rảnh; nhóm
  S05 và scope phải do upstream resolve không chồng lấn. Sai ở upstream sẽ thành INPUT_INVALID hoặc điểm
  khác ý định, không phải lỗi Core.

## 5. Đề xuất thứ tự xử lý

1. **Duyệt acceptance v2 (A)** — chỉ là quyết định. Mở đường cho protocol đo mới mà không cần zero.
2. **Đo hiệu năng trên Linux (B)** — trong một nhiệm vụ: mở rộng generator/harness để sinh input policy 0.4
   với tập rule cố định (S01–S11, có/không hard), giữ nguyên budget/watchdog/RSS hiện có, sealed plan mới,
   pilot nhỏ trước, rồi campaign theo protocol v2. Không sửa product code. Kết quả trả lời rủi ro lớn nhất.
3. **Windows (C)** — chạy cùng wheel và plan trên máy Windows của người dùng theo runbook có sẵn, sau khi
   (2) cho thấy candidate đáng nghiệm thu.
4. **Quality profile (D)** — cùng chủ thể nghiệp vụ, trước campaign tiếp theo nếu muốn dùng làm gate.
5. **Phase 3 (repair + benchmark)** theo Core First, sau khi (2) có số đo thật.
6. **S12 (G)** — chỉ khi có use case; không làm theo danh sách.

## 6. Quyết định cần duyệt

- [x] **E1** — Duyệt acceptance v2 D1–D3 như bản DRAFT. *(Đề xuất: duyệt.)*
- [x] **E2** — Mở rộng benchmark sang policy 0.4 (S01–S11) cho campaign Linux tiếp theo, không đổi
  budget/gate an toàn. *(Đề xuất: chọn.)*
- [x] **E3** — Coi Windows/cross-OS là bước riêng sau campaign Linux, do người dùng chạy trên máy
  Windows. *(Đề xuất: chọn.)*
- [x] **E4** — Hoãn S12 đến khi có một use case cụ thể; Phase 2 được ghi là “technical synthetic đạt
  S01–S11”. *(Đề xuất: chọn.)*
- [ ] **E5** *(chưa quyết định)* — Từ mốc sau, không tạo policy/output mới cho mỗi rule mới nếu không đổi semantics của rule
  cũ: thêm rule vào policy mới nhất kèm `since_policy` chỉ khi chưa phát hành. *(Đề xuất: thảo luận; hiện
  mọi policy đã phát hành nên quy tắc cũ vẫn áp dụng cho đến khi có quyết định.)*
- [x] **E6** — Ghi lại rằng ba PR Phase 2B/2C được merge không có review độc lập; nếu cần, yêu cầu một
  reviewer người cho các thay đổi contract trước khi dùng với dữ liệu thật. *(Đề xuất: chọn.)*
