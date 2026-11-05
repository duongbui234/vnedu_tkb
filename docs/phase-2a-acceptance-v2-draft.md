# Phase 2A — đề xuất tiêu chí nghiệm thu v2

Ngày: 2026-11-04. **D1–D3 ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT ngày 2026-11-05** (E1 của
[đánh giá Phase 2](phase-2-status-assessment.md)). Duyệt là duyệt **tiêu chí**: protocol, harness, gate và
sealed plan mới **chưa triển khai**; evidence, gate và verdict lịch sử (NOT_MET, STOPPED, primary 0/108)
giữ nguyên; mọi run mới vẫn cần ủy quyền riêng. Phần thân dưới đây là bản đã duyệt, chưa sửa nội dung.

Đề xuất tách ba kết luận: **lịch đúng hard**, **chất lượng soft được chấp nhận**,
và **khả năng đáp ứng trong giới hạn thời gian/RAM**. Zero là một kết quả benchmark
riêng, không là điều kiện mặc định cho mọi lịch hợp lệ hoặc mọi mốc Phase 2A.

Theo cách phân loại này, phần kỹ thuật synthetic đã có mốc nghiệm thu lịch sử;
candidate hiện tại có kiểm chứng kỹ thuật Linux và một lịch pilot hợp lệ. Chưa đủ
evidence để nghiệm thu chất lượng được chấp nhận, campaign Linux hiện tại hoặc
vận hành hai OS. **Không thể kết luận toàn Phase 2A vận hành đã xong chỉ bằng việc
bỏ điều kiện zero.**

Tài liệu này chỉ đề xuất tiêu chí và đối chiếu evidence. Không sửa gate/controller,
product code, installed package, input, budget, evidence lịch sử hoặc verdict cũ;
không chạy solver/campaign, không commit/merge/push. Việc duyệt bản này chưa phải
ủy quyền triển khai hoặc chạy campaign mới.

## 1. Phạm vi và nguyên tắc

Giữ phạm vi Phase 2A: S01–S04, input1.1/policy0.1/output1.2, hard built-ins hiện có,
independent validator/evaluator, CLI và packaging. Không thêm 2B/2C, repair, UI,
API hoặc quy tắc trường chưa xác nhận. Không đồng nhất synthetic acceptance với
production readiness.

- Soft không đạt không làm một lịch hard-valid thành hard-invalid.
- Một lịch hợp lệ không tự được coi là lịch đủ đẹp để giáo vụ sử dụng.
- Không có lịch ở known-feasible là thiếu năng lực tìm nghiệm trong giới hạn;
  không đổi UNKNOWN thành INFEASIBLE, PASS hoặc điểm0.
- Đúng status, score và proof là yêu cầu kỹ thuật bắt buộc. FEASIBLE không cần
  chứng minh tối ưu; claim OPTIMAL/optimal prefix phải có căn cứ đúng semantics.
- Phân loại v2 dưới đây là nhãn trong báo cáo đề xuất, không là schema/API mới.

## 2. Trục H — hard validity và tính đúng kỹ thuật

| ID | Điều kiện bắt buộc | Cách kết luận |
|---|---|---|
| H1 | Contract/schema/capability và input fingerprint đúng; không bỏ unknown fields hoặc bỏ rule không hỗ trợ | Sai → FAIL, không xuất lịch dùng được |
| H2 | Đủ đúng demand và occurrences, đúng GV/lớp, duration/continuity hợp lệ | Independent validator phải PASS trên toàn bộ assignments |
| H3 | Không trùng GV/lớp/phòng; đúng availability/calendar, room requirements và explicit locks | Không được nới hard để giảm soft score |
| H4 | Raw/weighted/tier score tính lại khớp; status, incumbent/bound và proof prefix nhất quán | Score/proof sai là lỗi kỹ thuật, dù occupancy đúng |
| H5 | Với UNSAT_CAPACITY, đúng INFEASIBLE và không có assignments/score; với known-feasible không được kết luận INFEASIBLE khi witness vẫn valid | Sai ground truth → FAIL; UNKNOWN không được tính PASS |
| H6 | Hash/source/wheel/input, receipt, measurement và cleanup đáng tin cậy | Identity/integrity/probe/cleanup gate thất bại → dừng, giữ evidence |

H được kết luận **theo từng kết quả có lịch**. Để đóng coverage của campaign,
phải thu đủ ma trận; 1/1 lịch valid không thay cho 81/81 known-feasible runs.
Các error/UNSAT cases được đánh giá theo kết quả mong đợi, không bắt chúng có lịch.

## 3. Trục Q — chất lượng soft được chấp nhận

Tách **tính đúng của cơ chế tính/tối ưu điểm** khỏi **mức vi phạm mà người dùng
chấp nhận**. Oracle bài nhỏ và fixture cải thiện baseline chứng minh cơ chế;
chúng không quyết định lịch của một trường đã đủ tốt.

### 3.1 Điều kiện kỹ thuật của chất lượng

Mọi lịch phải có breakdown theo rule/resource và đơn vị; ghi vector theo priority,
proof prefix, tier chưa chạy và giới hạn còn lại của kết luận. So theo vector
lexicographic trên cùng input/policy; không cộng P1+P2+P3 thành một điểm chung,
không so raw score giữa datasets khác nhau.

Giữ test oracle/priority/weight và fixed-baseline improvement. Không bắt mọi
FEASIBLE run tốt hơn witness đã biết, vì product không nhận witness làm hint.
BETTER/EQUAL/WORSE so witness là thông tin benchmark, không là quyết định giáo vụ.

### 3.2 Quyết định chấp nhận chất lượng

**Đề xuất:** không đặt một ngưỡng zero hoặc một tỷ lệ đạt nguyện vọng chung cho
mọi trường. Dùng một trong hai căn cứ được ghi rõ:

1. **Quality profile đã duyệt trước khi dùng làm gate:** rule/scope/unit, giới hạn
   tổng và mức tập trung vi phạm trên từng GV/ngày/buổi; priority và người duyệt.
   Sau đó chấm bằng tiêu chí đã đóng băng, không chọn ngưỡng vừa khít kết quả.
2. **Duyệt kết quả cụ thể có lưu quyết định:** người có thẩm quyền xem breakdown,
   chấp nhận các vi phạm còn lại và phạm vi sử dụng của đúng input/result hash.
   Quyết định mới không sửa verdict benchmark cũ hoặc áp sang input khác.

Chưa có một trong hai căn cứ → **REVIEW_REQUIRED**, không tự thành ACCEPTED.
Đạt căn cứ → **ACCEPTED** trong phạm vi đã duyệt; vượt profile hoặc bị từ chối →
**NOT_ACCEPTED**. Không có lịch → **NO_SCHEDULE**, không có soft score để chấm.

Không tự đặt mức 80%, 95% hoặc cho phép một số tiết vượt tải chỉ để pilot hiện tại
được qua. Ngưỡng giáo vụ chưa được xác nhận là thiếu dữ kiện nghiệp vụ; không phải
lý do để vô hạn định ép mọi bài synthetic về zero.

### 3.3 Đối chiếu pilot mới nhất

`[0,5,120]` là lịch hard-valid với:

- P1=0: không còn penalty tránh ô và vượt tải/buổi trong profile này.
- P2=5: tổng5 teaching periods vượt giới hạn tải/ngày; không có nghĩa5 GV vi phạm.
- P3=120:120/300 teaching periods ngoài khung ưu tiên2–4, tức40%; không phải thiếu120
  tiết. P3 NOT_RUN nên đây không phải kết quả tối ưu P3.

Kết luận Q đề xuất: **score đáng tin cậy; mức chấp nhận REVIEW_REQUIRED**.
Duyệt tài liệu v2 không tự chấp nhận40% tiết ngoài khung ưu tiên. Nếu giới hạn nào
thực sự bắt buộc của trường, phải được đặc tả/triển khai như hard trong phạm vi
được duyệt riêng; không đổi nhãn S01–S04 hiện tại bằng lời trong báo cáo.

## 4. Trục P — hiệu năng và khả năng tìm lịch

Giữ nguyên các giới hạn hiện có, không nâng budget để bù việc đổi cách phân loại:

| Quy mô | Budget solver chung | Watchdog launch-to-exit | Peak child RSS target | Reserve trước mỗi run |
|---|---:|---:|---:|---:|
| 10 lớp | 60s | 150s | ≤1GiB | 2GiB |
| 20 lớp | 120s | 210s | ≤2GiB | 2GiB |
| 40 lớp | 180s | 270s | ≤4GiB | 2GiB |

Workers1, seed42;36 datasets ×3 repeats =108 primary/OS, gồm81 known-feasible và27
UNSAT_CAPACITY. Giữ input bytes, order, guards, đo đúng PID, identity/headroom
trước run, no retry và stop khi gate an toàn/tính đúng thất bại. Các native calls
dùng phần budget chung còn lại, không reset toàn budget cho từng call. Solver60s
không được mô tả thành SLA end-to-end60s.

**Đề xuất điều kiện P đạt cho một campaign/OS:** đủ108 outcomes và measurements;
81/81 known-feasible có lịch hard-valid trong các giới hạn;27/27 UNSAT đúng;
không crash, watchdog/resource stop hoặc measurement bị thiếu. Score nonzero tự
nó không làm P thất bại; nó được ghi ở Q và mục benchmark zero. Không có lịch
ở known-feasible vẫn là P NOT_MET; integrity/coverage thiếu là INCOMPLETE/BLOCKED.

Phân biệt “một run đo được trong giới hạn” với “campaign đạt”. Không gộp runtime
khác fingerprint thành SLA, không suy P95 từ3 repeats, không coi trace nội bộ là
time-to-first-feasible từ lúc launch. Báo rõ overhead/profile quan trắc.

## 5. Benchmark zero vẫn giữ nguyên

BASE/MIXED profile Z có witness `[0,0,0]` được kiểm độc lập, nên zero là optimum
đã biết và là bài kiểm tra chất lượng tìm kiếm có giá trị. Báo riêng:

- ZERO_TARGET_MET/NOT_MET và số lượt đạt, cùng đúng dataset/fingerprint/budget.
- Vector, proof prefix, BETTER/EQUAL/WORSE so witness; không giả tạo gap phần trăm
  bằng cách chia cho optimum0 hoặc gộp các tiers.
- Với TIGHT/profile C: không ép zero; công bố witness, lower bound có điều kiện
  và score/proof thật, không mặc định bound khả đạt.

Zero không còn là **điều kiện chặn chung** cho việc thu thập primary v2 hoặc
nghiệm thu cơ chế kỹ thuật. Nếu một bên cần chứng nhận “tìm được zero trong60s”,
benchmark zero vẫn là điều kiện riêng và candidate hiện tại **chưa đạt** điều đó.

FET được nghiên cứu có thể COMPLETE dù còn soft conflicts; STKB có nhiều thang
đánh giá và chưa chứng minh toàn bộ engine đòi score0. Đây là căn cứ để phân biệt
lịch hoàn chỉnh với mọi nguyện vọng hoàn hảo, không là bằng chứng hiệu năng tương
đương hoặc căn cứ lấy nguyên weight/default của hai công cụ làm policy mới.
Xem [FET](research/fet/02-scheduling-algorithm.md) và
[STKB](research/stkb/02-business-coverage.md).

## 6. Đối chiếu evidence hiện có

| Hạng mục | Đã có bằng chứng | Phần còn thiếu / kết luận đề xuất |
|---|---|---|
| Mốc kỹ thuật synthetic | Snapshot chốt2026-11-01 đã có nghiệm thu S01–S04, oracle, CLI/package và independent evaluation | Giữ nguyên mốc lịch sử; không dùng nó để chứng nhận mọi candidate mới trên hai OS |
| Candidate hiện tại trên Linux | Core361 tests; full suite726 passed/8 skipped; lint/format/mypy và installed preflight PASS | Đây là kết quả lượt trước, không chạy lại trong lượt soạn v2 |
| H trên pilot mới nhất | 260 assignments/300 periods; independent hard và score audit PASS, fingerprint/receipts đúng | PASS cho lịch này; chưa có coverage81/81 của candidate |
| Q cơ chế | Score `[0,5,120]` khớp đầy đủ rule rows; oracle và regression giữ ưu tiên/proof/status | Không tự suy chất lượng giáo vụ ACCEPTED |
| Q nghiệp vụ | Có breakdown tổng và resource để xem xét; witness zero cùng input tồn tại | Chưa có profile hoặc quyết định chấp nhận lịch này: REVIEW_REQUIRED |
| P trên một pilot | Launch-to-exit56,533945s; RSS410.972.160bytes; native exit0, measurementOK; không resource stop | Trong giới hạn ở n=1; không chứng minh độ ổn định hay khả năng20/40 lớp |
| Campaign của candidate | Preflight/prepare/warmup và đúng1 pilot; primary0/108 | Chưa đạt P campaign; cần campaign mới được ủy quyền sau khi protocol v2 được duyệt/triển khai |
| Zero benchmark hiện tại | `[0,5,120]` so witness `[0,0,0]` | NOT_MET, giữ nguyên lịch sử |
| Campaign Linux cũ108 runs | 54/81 known-feasible có lịch valid;27 UNKNOWN;27 UNSAT đúng;108 measurements trong giới hạn | Không đủ81/81 tìm lịch ngay cả nếu bỏ zero; wheel/lock khác nên không chuyển thành coverage candidate mới |
| Windows/cross-OS | Có evidence kỹ thuật ở snapshot trước; candidate mới chưa chạy native Windows | Chưa có current Windows108 runs/cùng wheel và exchanged-result validation; không tuyên bố nghiệm thu hai OS |
| Cutoff native | Trace phân biệt joint-zero UNKNOWN và P2 FEASIBLE trước raw deadline | Nhánh OR-Tools termination cụ thể chưa chứng minh; không lấy giả thuyết thay verdict H/Q/P |

Nguồn chính:

- [Mốc kỹ thuật và lịch sử cập nhật](phase-2a-report.md).
- [Pilot mới nhất và trace](phase-2a-incumbent-trace-report.md).
- [Campaign Linux cũ](phase-2a-task5-linux-report.md).
- [Protocol v1 đang có hiệu lực](superpowers/plans/2026-10-26-phase-2a-operational-validation.md).
- [Policy hard/soft hiện có](research/stkb/09-vnedu-hard-soft-policy.md).

Pilot/wheel mới nhất: `incumbent-trace-20261104-v1`, wheel SHA256
`382a54ba845ce30325670d72a06d13a0b06e2dcd7702fec398e7c262f4d3eead`;
plan SHA256 `10945c1f5c7a7fe482e272713fda0c5c321cef67820d6d47fe0b1936c8b18260`.
HEAD vẫn là base `537c891`; candidate uncommitted được nhận dạng bằng hash nguồn,
wheel và patch, không coi base core-tree là hash của candidate.

## 7. Cách áp dụng nếu được duyệt — chưa thực hiện

1. Giữ protocol/evidence/verdict v1 nguyên trạng, kể cả NOT_MET và STOPPED.
   Không resume campaign đã dừng hoặc viết lại `case-verdict.json` của lịch sử.
2. Triển khai phân loại H/Q/P/zero ở harness/report với protocol ID mới, regressions
   và sealed plan mới; không cần sửa semantics S01–S04 hoặc public product API.
3. Cho phép pilot nonzero mở primary **để thu thập đánh giá** khi H, identity,
   integrity, measurement và resource gates đều đạt. Q REVIEW_REQUIRED và zero
   NOT_MET được giữ rõ trong báo cáo; không đồng nghĩa cho phát hành lịch.
4. Chỉ mở một campaign mới khi có ủy quyền, preflight và headroom mới. No retry;
   gate an toàn/tính đúng thất bại thì dừng. Nếu cần dùng quality profile làm gate,
   phải chốt nó trước run; không đổi sau khi nhìn score để gọi PASS.
5. Kết luận độc lập theo phạm vi: kỹ thuật synthetic; P campaign Linux; Q được
   chấp nhận; Windows/cross-OS; benchmark zero. Chỉ kết luận nghiệm thu vận hành
   trong phạm vi được duyệt khi mọi phần bắt buộc của phạm vi đó có đủ evidence.
   Thiếu Windows thì không gọi là nghiệm thu hai OS; thiếu Q thì không gọi là lịch
   đã được giáo vụ chấp nhận. Không tự mở Phase2B/2C hoặc production.

## 8. Các quyết định đề nghị duyệt

- [x] **D1 — Tách tiêu chí:** H bắt buộc; Q cần profile/duyệt kết quả; P dùng coverage
  và giới hạn hiện có; zero là benchmark riêng, không là gate chung.
- [x] **D2 — Cho đo thay vì chờ lịch hoàn hảo:** trong protocol mới, pilot hard-valid,
  identity/resource/measurement đạt có thể mở primary thu thập dữ liệu dù Q còn
  REVIEW_REQUIRED hoặc zero NOT_MET. Không tự duyệt sử dụng lịch `[0,5,120]`.
- [x] **D3 — Giữ ranh giới:** không sửa evidence/gate cũ; không giảm denominator,
  nới budget/hard, dùng witness hint hoặc tuyên bố Windows/production đã đạt.
  Việc triển khai gate mới và mọi run mới cần ủy quyền tiếp theo.

Không cần chọn một ngưỡng soft tùy tiện để duyệt D1–D3. Sau khi có đủ kết quả,
chủ thể nghiệp vụ có thể duyệt quality profile hoặc một báo cáo kết quả cụ thể;
đến lúc đó Q vẫn chưa ACCEPTED. Profile được tạo sau khi xem kết quả chỉ làm gate
cho các run tương lai; với kết quả đã có, nếu chấp nhận thì ghi quyết định duyệt
riêng đúng result hash, không gọi đó là PASS một ngưỡng đã được freeze từ trước.

## 9. Kiểm tra thực hiện trong lượt soạn tài liệu

Chỉ đọc source/report/JSON và dùng Python standard library để kiểm SHA256 của
**249 entries** trong manifest evidence mới nhất, đối chiếu result/run/receipt với
`score-final.json`: pilot `[0,5,120]`, witness `[0,0,0]`, hard-valid và audit PASS.
Đây là kiểm checksum/nhất quán metadata của evidence đã có; không tạo proof native
mới và không chạy lại evaluator/solver. Các con số tests/preflight ở trên là kết
quả đã lưu, không là tests chạy trong lượt này.

Chỉ tạo tài liệu mới này. Kiểm đường dẫn tham chiếu, Markdown/diff và xác nhận các
file có trước cùng manifest evidence không đổi. Không chạy uv sync/pytest hoặc
bất kỳ native solve/campaign nào trong lượt docs-only này; không tuyên bố kiểm lại
product code hay đã triển khai nghiệm thu v2.
