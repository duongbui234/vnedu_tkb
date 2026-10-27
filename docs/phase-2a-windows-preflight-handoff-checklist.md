# Phase 2A — Checklist bàn giao Task 2 Windows preflight

**Trạng thái hiện tại: WINDOWS BLOCKED / CHƯA THỰC HIỆN.** Checklist này chỉ chuẩn bị bàn giao; không phải approval cài đặt, chạy Core tests/mini solve hoặc benchmark. Lượt viết checklist không cài package, tạo venv, copy payload sang Windows, chạy solve/search/profiling hoặc sửa Core/budget/guards.

Nguồn: [kế hoạch operational validation, Task 2](superpowers/plans/2026-10-26-phase-2a-operational-validation.md), [Linux preflight và provenance](phase-2a-operational-report.md), [Linux Task 5](phase-2a-task5-linux-report.md). Các ô trống là công việc sau khi máy/scope được xác nhận và user cho phép; không là kết quả PASS sẵn có.

## 1. Thông tin máy Windows cần cung cấp trước

| Thông tin | Người vận hành điền / evidence cần thu |
|---|---|
| Machine ID | ID opaque để phân biệt máy và các lần preflight |
| OS | Windows edition/version/build, x64; xác nhận chạy Windows native, không WSL/Linux cross-build; ghi virtualization nếu có, không tự suy bare metal |
| Python | Đường dẫn interpreter, architecture và exact patch; tham chiếu Linux3.12.3. Kế hoạch dùng Python3.12; nếu patch khác phải công bố, không kết luận hiệu ứng OS |
| Công cụ | Phiên bản uv, shell/PowerShell và cách người vận hành sẽ thu stdout/stderr/exit codes |
| CPU | Model, logical cores, topology/P-E cores nếu lấy được; thiếu thì null+reason |
| RAM | Total/available RAM, pagefile/swap configuration; không dùng RAM host làm peak của solver |
| Power/workload | AC/battery/power mode, workload đang cạnh tranh, thời điểm UTC; unknown giữ UNKNOWN, không VERIFIED_IDLE |
| Khả năng so với Linux | Có phải cùng máy dual-boot i7-12700H/20logical cores không; khác hardware hoặc Python patch thì chỉ so deployment, không cô lập hiệu ứng OS |
| Paths | Staging source/bundle read-only về mặt quy trình, paths venv solver/no-solver/dev riêng và output root Windows mới, chưa tồn tại |
| Khả năng cài đúng pins | Có thể lấy binary wheels phù hợp Windows/Python từ lock không; ghi dependency/install/import failure thay vì tự đổi pin hoặc build OR-Tools từ source |
| Cách bàn giao lại | Người vận hành chạy tại Windows và trả về manifest + logs + outputs cùng hashes; chưa giả định có kết nối Windows từ phiên Linux này |

Ưu tiên máy tham chiếu theo plan: dual-boot cùng máy, RAM≥16GiB và≥4logical cores. Đây là lựa chọn tham chiếu đề xuất trong plan, không phải thay đổi Core guards hoặc proof rằng cấu hình thấp hơn chạy sai. Không tự đổi governor/power/affinity/env hoặc đóng ứng dụng để làm đẹp kết quả.

- [ ] Có đủ thông tin máy/paths/cách thu evidence; thiếu mục nào ghi rõ blocker hoặc null+reason.
- [ ] User xác nhận máy Windows native và scope **chỉ Task 2 preflight** trước bất kỳ cài đặt hoặc native tests/mini solve nào. Approval các diagnostic Linux trước đã tiêu thụ, không áp dụng cho Windows.

## 2. Payload đã có ở Linux — dùng đúng bytes

Các assets sau đã được kiểm SHA256 trong lượt lập checklist; **chưa chuyển hoặc kiểm trên Windows**.

| Asset | Nguồn local | Expected SHA256 |
|---|---|---|
| Core wheel | `.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/preflight-linux-v1/distribution/vnedu_tkb_core-0.2.0-py3-none-any.whl` | `1686079c62af5b796fb87ade66e54858bb453cf579d1b9b6bc48c8d8b96dbbb9` |
| Lock | `.worktrees/phase2a-task5/uv.lock` | `e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084` |
| Toàn bộ bundle36datasets | `.worktrees/phase2a-generator/benchmarks/artifacts/phase2a/task1-v1/`; root `manifest.json` có hash bên cạnh | `a278a02dd9e10fedc7c5fcf44ef81d038d7712eba929d881a0f6193fc97cc93d` |

Paths trên tính từ repo gốc `/home/ddevtk/code/vnedu_tkb`. Bundle hash là hash **root manifest**, không phải hash một archive chưa được tạo. Phải chuyển đủ36directories, input/witness/provenance/manifests và kiểm mọi file hash được tham chiếu; không chỉ chuyển manifest hoặc regenerate trên Windows.

Core source provenance: commit `4cfa643148b967ad7baf674fe6439699afbe51e2`, Core tree `1efd459b2514f448dcf4ac297989de09eb76a3a1`. Chuyển source/tests/fixtures/config tương ứng để chạy dev suite và kiểm source-vs-wheel; không dùng checkout/PYTHONPATH để thay installed Core trong installed probes. Current benchmark branch HEAD không phải Core provenance commit của wheel.

- [ ] Bàn giao wheel/lock/full bundle cùng checksum inventory; đối chiếu sender/receiver hashes trước install.
- [ ] Giữ cùng Core wheel, không rebuild rồi gọi là cùng wheel; không chuyển Linux venv/site-packages làm môi trường Windows.
- [ ] Giữ dataset IDs, fingerprints, raw bytes, witness scores và frozen source IDs; xác nhận đủ36datasets sau copy.
- [ ] Kèm Linux `preflight-manifest.json`/report làm tham chiếu, không đổi trường Windows BLOCKED hoặc gắn Linux PASS thành Windows PASS.
- [ ] Kèm probes/tests làm tài liệu tái lập. Scripts/paths Linux chỉ là reference; rà path handling và installed-package checks cho Windows trước khi dùng, chưa tự port/sửa runner trong checklist này.

## 3. Kiểm Task 2 sau khi được phép — không thực hiện trong lượt này

Task2 có thể dùng installed Core APIs và probes phù hợp Windows, không cần bắt đầu campaign/resource benchmark. Runner benchmark hiện hard-reject platform khác Linux và dùng wait4/proc/fcntl; **không gọi hoặc bypass Linux runner để giả Windows PASS**. Windows supervisor/resource peak thuộc Task3 riêng.

- [ ] Tạo dev environment riêng và hai venv sạch: solver và no-solver. Install từ cùng lock/pins, yêu cầu hashes/binary wheels; dependencies thực phải khớp versions frozen. Hash binary dependency wheels được phép khác Linux theo platform; Core wheel hash phải giống.
- [ ] Lưu install/export/check logs, exact argv/exit codes và package inventory. Nếu export/resolution Windows thiếu wheel hoặc import lỗi: ENVIRONMENT_BLOCKED với reason; không đổi pins/lock/Core hoặc build OR-Tools từ source để qua gate.
- [ ] Installed probes xác nhận `sys.executable`, prefix, `tkb_core.__file__` nằm trong Windows venv/site-packages; đối chiếu source bytes với frozen wheel/Core tree. Không editable install hoặc source-shadowing. Ghi OS/arch/Python exact patch, wheel/lock/bundle hashes thực tế.
- [ ] Chạy full **Core** suite từ snapshot phù hợp, ghi total/pass/fail/skip/xfail và lý do. Linux từng232PASS là reference, không copy thành kết quả Windows; không tính benchmark/Linux-only supervisor tests là Core Windows acceptance.
- [ ] Installed solver tiny smoke: input1.1/output1.2/policy0.1, duration1/2, S01–S04 và cả3tiers; mini solve rồi independent validate/score. Lưu raw input/result/stdout/stderr/exit; không coi đây là latency/RAM trường thật hoặc yêu cầu assignments giống Linux.
- [ ] Installed no-solver smoke: xác nhận OR-Tools vắng mặt; validate/evaluate saved schedule vẫn khớp. Guard không import solver/preprocessing/compiler/model builder trong scorer path.
- [ ] Ready/non-ready registry: S01–S04 ready; pending rule, disabled rule, malformed/stale result, invalid locks và unknown/unsupported custom hard đúng rejection/status, không publish schedule sai. Lưu dữ liệu tiny synthetic và expected-vs-actual; không mutate frozen bundle.
- [ ] Installed validation/scoring toàn bộ36datasets:27feasible witnesses hard-valid và score khớp;18BASE/MIXED vector0;9TIGHT witnesses có P1=P3=0, positive P2≥conditional lower bound60/120/240, không claim bound attainable;9UNSAT contract hợp lệ và demand30>29class slots, provenance witness không gán thành target witness hợp lệ. Không solve các datasets10/20/40 ở Task2.
- [ ] Giữ nguyên options/guards của protocol; không tuning/hints/seed sweep/workers4. Khi dùng default SolveOptions:60s/workers1/seed42, guards10,000slots/10,000occurrences/100,000placements/1,000,000occupancy terms. Các budgets campaign60/120/180s và watchdog150/210/270s không được sửa hoặc chạy như một phần preflight.

## 4. Evidence Windows cần nhận lại

Tên file dưới đây là **gợi ý layout cho root mới**, không là artifacts đã tồn tại. Không ghi đè preflight/campaign Linux.

| Artifact | Nội dung bắt buộc |
|---|---|
| `preflight-manifest.json` | Version/protocol, machine/preflight ID, Windows status +reason, source commit/tree, wheel/lock/bundle hashes, từng check status và file digests; Windows-native flag có provenance |
| `environment-solver.json`, `environment-no-solver.json` | OS/build/arch, Python patch/path/prefix, CPU/RAM/pagefile/power/workload, actual packages, installed Core path/source check; field thiếu=null+reason |
| Lock/dependency evidence | Bản lock đúng hash, platform-resolved requirements/install logs và hashes của binary dependency wheels thực dùng; không chỉ sao Linux package list |
| `logs/core-pytest.txt` | Actual command/working directory/interpreter, stdout/stderr hoặc transcript, exit code, test counts/skips/xfails và reasons |
| `smoke-summary.json`, `smoke/` | Tiny inputs/results, expected vs actual cases, raw stdout/stderr, process exit codes và fingerprints; independent validity/score/proof consistency |
| `registry-summary.json`, `no-solver-guard-score.json` | API checks/rejections/disabled behavior, no-solver import guard và package availability evidence |
| `bundle-verification.json` | Đủ36datasets cùng hashes/fingerprints/dimensions/guard result, witness vectors/ground truth và từng validation/scoring verdict |
| Probe provenance | Exact commands/scripts/source hashes thực dùng và mapping tới source snapshot; không sửa raw output/path để giả provenance |
| `windows-preflight-report.md` | PASS/BLOCKED/FAIL theo check, missing evidence/reasons, hardware/Python differences, giới hạn; phân biệt correctness preflight với performance NOT_MEASURED |

- [ ] Tất cả commands có exit status và output đối chiếu nội dung; file tồn tại riêng lẻ không đủ chứng minh PASS.
- [ ] Hash inventory chốt sau thu evidence; receiver có thể kiểm lại source/package/input/result identity và file membership. Hashes là consistency evidence, không là attestation chống người có quyền sửa toàn bộ artifacts.
- [ ] Không ghi payload/outputs Windows vào old Linux root hoặc đem venv/raw ignored artifacts mặc định vào Git/upload. Chọn nơi bàn giao được user xác nhận; giữ IDs synthetic và không dữ liệu vnEdu thật.

## 5. Điều kiện kết luận và phần vẫn chưa nghiệm thu

- **Windows Task2 PASS** chỉ khi actual native Windows checks và required artifacts ở trên đầy đủ, hashes/contract/validation/score/status đúng. Cài package thành công hoặc chỉ một mini solve chưa đủ.
- Máy chưa có, install/import/probe thiếu hoặc environment identity chưa xác minh→**Windows BLOCKED**, giữ missing/null/reason. Validation/score/contract mismatch là check FAIL và dừng; không gọi INFEASIBLE/UNKNOWN để thay environment/harness failure.
- Task2 PASS không nghiệm thu Windows resource accounting/watchdog (Task3),108run campaign (Task4), cross-OS aggregation/performance (Task5), P95/SLA hoặc toànPhase2. Không triển khai Task3–5 tự động từ checklist.
- Linux Task5 vẫn performanceNOT_MET/failed63; ba repeats/fingerprint và Windows BLOCKED trong evidence lịch sử giữ nguyên. Chỉ cập nhật trạng thái preflight mới sau review actual Windows evidence; không sửa lịch sử để trông như đã chạy hai OS.

## Kiểm chứng lượt lập checklist

Đã đọc AGENTS/Core First và plan/report, kiểm actual Core wheel/lock/bundle manifest SHA256 khớp frozen preflight manifest; bundle membership36datasets. Không cài đặt, export requirements, tạo venv, copy payload sang Windows, import Core/OR-Tools hoặc chạy tests/solve/benchmark/profiling. Windows vẫn BLOCKED, không có Windows PASS mới. Chỉ checklist này được thêm; mọi checkboxes là bước chưa thực hiện.

Standard-library asserts về3asset hashes,36dataset membership, local links, unchecked future steps và chỉ một checklist mới: PASS. Lệnh thực chạy: `uv run --no-sync ruff check .` PASS; `uv run --no-sync ruff format --check src tests benchmarks` PASS54files; `uv run --no-sync mypy` PASS27Core source files; `git diff --check` PASS. Không chạy `uv sync`/install hoặc pytest để giữ scope chưa cài đặt/chưa solve; các checks dùng tools đã có, không tạo kết quả Windows preflight.
