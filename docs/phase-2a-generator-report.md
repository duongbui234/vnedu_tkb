# Phase 2A — Task 1: synthetic generator và witness/manifest

Ngày thực hiện: 2026-10-26. Worktree: `.worktrees/phase2a-generator`, branch `feature/phase2a-synthetic-generator`; base Core `30a6c55b0871c8212dd858e3fd8d165728186390`.

## Phạm vi và file thay đổi

Chỉ Task 1 của [kế hoạch vận hành đã duyệt](superpowers/plans/2026-10-26-phase-2a-operational-validation.md#task-1--fixturewitness-generator). Giữ nguyên `src/`, `tests/`, `pyproject.toml`, `uv.lock`, nghiên cứu và các file gốc ở main. Không runner, benchmark campaign, sửa solver hay Phase 2B/2C.

- `benchmarks/generate_synthetic.py`: constructive generator, artifact contracts, independent validation/score, manifests, publication và verify.
- `benchmarks/tests/conftest.py`: import root cho benchmark tooling, không thay product packaging.
- `benchmarks/tests/test_generate_synthetic.py`: 38 tests, gồm invariants, deterministic hash, mutations, source identity và publication.
- `.gitignore`: chỉ thêm `/benchmarks/artifacts/` cho các bundle cục bộ.
- Báo cáo này và checklist Task 1 trong kế hoạch; Task 2–5 chưa triển khai.

Các bản sao `AGENTS.md`, `docs/phase-2a-report.md`, `docs/research/stkb/` là context có sẵn từ main, không phải thay đổi của Task 1. Chưa commit, merge hoặc push.

## Kết quả được kiểm chứng

**VERIFIED:** Generator không gọi solver/model builder hoặc import OR-Tools. Test subprocess chặn các imports này vẫn generate/validate/score thành công. Dùng `prepare()` chỉ để kiểm guard và đếm domains; dùng independent validator/evaluator cho witness.

Ba quy mô 10/20/40 lớp, 15/30/60 giáo viên; 9 môn, 60 slots, 30 periods và 26 occurrences/lớp (4 double + 22 single). Phân công nối các lớp qua giáo viên, không nhân các block 10 lớp độc lập. Thử đúng `5*C` resource-safe swaps; ghi riêng số thành công, không đổi seed để tìm profile dễ hơn.

| Profile | Bằng chứng |
|---|---|
| BASE | Symbolic, không phòng/locks, witness vector `(0,0,0)` |
| MIXED | Timed, lớp 42 slots, GV `max(36,load+6)` slots, phòng và 10% occurrence locks; witness vector 0 |
| TIGHT | Timed, lớp 32 slots, GV `load+2`, phòng và 20% locks; witness hard-valid, P1/P3=0, P2 có lower bound dương |
| UNSAT_CAPACITY | Từ BASE, một lớp cần 30 periods chỉ có 29 slots; input contract hợp lệ, precheck INFEASIBLE; không gán feasible witness cho input này |

UNSAT giữ BASE input/witness riêng với role `PROVENANCE_ONLY` và fingerprint của BASE. Không giả lập `ScheduleResult` hay solver proof. BASE/MIXED biết optimum vector 0 do có witness 0 và penalties không âm. TIGHT chỉ biết feasible upper bound và lower bound P2, chưa chứng minh attainable optimum.

Input schema 1.1, policy 0.1; benchmark artifact schema 1.0. Mỗi GV có đúng một S01–S04 enabled, weight 1, priorities 1/1/2/3 và teacher scope tường minh. Cổng kiểm chứng từ chối profile bị tắt rule, đổi priority/family/parameters hoặc nới availability GV. Mỗi witness được kiểm trên input cuối sau availability/phòng/locks.

Manifest chứa input fingerprint, SHA-256 từng artifact, số lượng entities/demand/locks/domains/occupancy terms, teacher load/availability, baseline score và nguồn generator/Core/lock. Core source hash lấy từ package thực đang import. Source hash chuẩn hóa CRLF; artifact hash dùng nguyên bytes. Cùng code/input/seed xuất canonical JSON UTF-8, sorted keys, LF. Verify yêu cầu cùng source identities; đây là kiểm toàn vẹn/tái lập, không phải chữ ký xác thực nguồn.

UNSAT có placements/occupancy terms/slot_tokens `null`: `prepare()` đã raise ở precheck trước khi trả domains. Không dùng số 0 giả làm số đo.

## Cách sử dụng

Chạy từ worktree root, đã `uv sync --locked --extra solver`:

```bash
uv run python benchmarks/generate_synthetic.py --output benchmarks/artifacts/phase2a/task1-v1
uv run python -c 'from pathlib import Path; from benchmarks.generate_synthetic import verify_bundle; m=verify_bundle(Path("benchmarks/artifacts/phase2a/task1-v1")); print(len(m.datasets))'
```

`generate_dataset()`, `validate_dataset()`, `write_bundle()` và `verify_bundle()` là APIs của tooling, không public Core APIs. Output phải là thư mục mới. Construct/verify tất cả dataset trong staging; tạo output root độc quyền, chuyển root manifest cuối cùng. Không thay output đã có. Lỗi giữa publication có thể để lại root chưa hoàn chỉnh; thiếu manifest thì không verify, không tự xóa hoặc ghi đè khi chạy lại.

## Kiểm chứng thực tế trên Linux

| Command | Kết quả |
|---|---|
| `uv sync --locked --extra solver` | PASS, không đổi lock |
| `uv run --extra solver pytest` | PASS, 232 tests, 5.00s |
| `uv run --extra solver pytest tests benchmarks/tests -q` | 270 passed (232 Core + 38 generator), 37.39s; đây là thời gian suite, không phải benchmark |
| `uv run pytest benchmarks/tests/test_generate_synthetic.py -q` | 38 passed, 30.76s |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check src tests benchmarks` | PASS, 47 files |
| `uv run mypy` | PASS, 27 Core files |
| `uv run mypy src/tkb_core benchmarks/generate_synthetic.py` | PASS, 28 files |
| `uv build` | PASS, wheel + sdist 0.2.0; tooling không được thêm vào distribution |
| `git diff --exit-code -- src tests pyproject.toml uv.lock` | PASS, không đổi Core/test cũ/dependency |

Regression RED→GREEN đã quan sát: construction counter vượt attempts; publication thay racing directory; calendar drift ở unused slot; source hash lấy checkout thay vì imported package; TIGHT daily limit drift; legacy input được nhận nhầm profile; availability bị nới, S04 bị disable hoặc đổi priority. Mutation family đã được cổng cũ chặn, tiếp tục giữ regression. Test sửa witness kèm cập nhật checksum vẫn bị independent validation chặn.

## Quyết định trong quá trình thực hiện

1. Worktree riêng, copy context chưa commit để đọc: bảo toàn main; chi phí là cần reconcile tài liệu khi merge sau.
2. Tests được dựng/kiểm tất cả 36 datasets trong memory/temp nhưng không solve chúng: đây là Task 1, không campaign hay số đo hiệu năng.
3. Thêm root vào sys.path chỉ trong benchmark conftest: tooling không phải product package; phải chạy test benchmark riêng vì `testpaths` hiện chỉ gồm `tests`.
4. Domains của UNSAT để null với precheck evidence: API không trả domains cho input bị reject, chưa có dimension counts sau precheck này.
5. Exclusive mkdir + manifest cuối thay directory rename: tránh Linux thay thư mục trống do process khác vừa tạo; có thể để root chưa hoàn chỉnh nếu publication lỗi, phải dùng root mới khi thử lại.
6. Giữ source tree/ledger và thay đổi chưa commit để người dùng review; không chạy Task 2–5 dù skill thường tiếp tục toàn plan, vì phạm vi người dùng giới hạn Task 1.

## Giới hạn và review

**UNKNOWN:** Windows thật, installed-wheel preflight, latency/RAM và chất lượng search quy mô trường. Không chạy benchmark, không kết luận solver nhanh/chậm hoặc production-ready.

Review độc lập ban đầu bị usage limit trước verdict cuối; sau khi tiếp tục phiên đã hoàn tất bằng reviewer fresh context thay thế (process cũ không còn). **Verdict: Ship within Task 1 scope; không có Critical/Important/Minor findings.** Reviewer đọc toàn bộ generator/tests và code contract, prepare, independent validation/score liên quan; không sửa file, không rerun tests/solver/benchmark. Bằng chứng 270 tests xanh do tác giả chạy. Phát hiện Important từ lượt trước (profile bị nới âm thầm) đã được kiểm chứng RED→GREEN; không còn lỗi được review chỉ ra.

Những phần reviewer không kết luận và quyết định phạm vi:

- Windows execution và installed-wheel preflight thuộc Task 2; giữ UNKNOWN, không thay Linux pass làm Windows pass. Chi phí: chưa biết khả năng vận hành Windows thật.
- Solver performance thuộc campaign sau; không có readiness/latency/RAM claim. Chi phí: không bảo đảm lịch quy mô trường đạt thời gian/chất lượng mong muốn.
- Không kiểm adversarial concurrent filesystem replacement. Tooling dùng output parent do người chạy kiểm soát; exclusive mkdir bảo vệ tránh thay output có sẵn, không cam kết chống process thù địch sửa thư mục cha. Chi phí: không dùng bundle ở đường dẫn đang bị process khác cố ý thay nội dung mà tin checksum là chữ ký xác thực.

Đã rà lại nguồn generator không đổi sau xuất bundle. Không có deferred minor. Giữ ledger/source/worktree vì chưa commit; không tự dọn scratch hoặc merge.

Các bộ synthetic kiểm chứng correctness theo protocol, không đại diện đầy đủ trường thật và không phải schema vnEdu. API hỗ trợ seed nguyên không âm, nhưng bundle nghiệm thu chỉ seeds 101/102/103. Thay generator/Core/lock cần tạo bundle version mới và giữ nguyên bundle cũ.

## Bundle đã xuất và đọc lại

**VERIFIED:** `verify_bundle()` đọc lại đủ 36 datasets từ `benchmarks/artifacts/phase2a/task1-v1/`: 27 feasible witnesses và 9 capacity-infeasible inputs. Mọi checksum/fingerprint, hard validity, score và dimensions đều khớp. Bundle không được commit; nằm dưới path ignored.

Root manifest SHA-256: `a278a02dd9e10fedc7c5fcf44ef81d038d7712eba929d881a0f6193fc97cc93d`.

Số đếm lớn nhất trong bundle: 60,480 placements, 136,320 occupancy terms, 60 slot tokens; prepare pass guards mặc định cho mọi feasible dataset. TIGHT lower bounds P2 lần lượt 60/120/240 cho 10/20/40 lớp. Swap successes trong bundle từ 3 đến 21, không giả định tất cả attempts thành công. Đây là số đếm cấu trúc, không phải số đo performance.

Nguồn thực của bundle:

```json
{
  "core_source_sha256": "9869e2e55abc4869ba026e8e28a88b045e0dc1f9e1bb2ac96ea624fde1defd80",
  "generator_source_sha256": "8144a3fc0270a7f83812913e9040b74d233b1bd702856ff63f026d2079f56c93",
  "uv_lock_sha256": "e7cf88d7082db5bceb43bc2694c488f2b4b64525f2963cf1a6a7f9bd93faa084"
}
```

`repository_head=30a6c55...`, `generator_matches_head=false` được ghi đúng vì generator hiện chưa commit; HEAD là base Core, không phải commit chứa generator. Source SHA nêu trên định danh đúng code đã xuất bundle.
