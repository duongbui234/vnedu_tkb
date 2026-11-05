# Phase 2 hiệu năng v2 — kế hoạch bước E (prepare, warmup, pilot)

Ngày 2026-11-05. Trạng thái: **DRAFT — K1–K7 ĐÃ ĐƯỢC NGƯỜI DÙNG DUYỆT theo đề xuất ngày 2026-11-05; E0 (diễn tập cloud) ĐÃ CHẠY, xem §3; E1–E3 trên máy đích chưa chạy, mỗi bước chạy vẫn cần ủy quyền riêng.** Mã nguồn: commit
đã ghi ở runbook D, phải chứa bản sửa R1 (§3 E0).
 Thuộc bước E của
[kế hoạch v2](2026-11-05-phase-2-linux-performance-v2.md) (§5 bước 3–4, §8), tiếp sau
[runbook bước D](../../phase-2-linux-performance-step-d-runbook.md).

Tài liệu chỉ là kế hoạch. Lượt soạn không sửa code, không chạy lệnh nào, không commit hay push. Duyệt kế
hoạch không phải ủy quyền chạy; bước F (216 run primary) luôn cần ủy quyền riêng sau khi xem pilot.

## 0. Điều kiện trước

| Điều kiện | Trạng thái hiện tại |
|---|---|
| Bước D chạy trên máy đích, `preflight-1` PASS và **đã được kiểm** theo §3 của runbook D | **Chưa có.** Bước E không bắt đầu trước điều này |
| Bundle và preflight của bước D còn nguyên (không sửa, không xóa) | Phụ thuộc bước D |
| HEAD vẫn là commit đã ghi ở bước D (có bản sửa R1) | Kiểm lại trước khi chạy |
| `/sys/fs/cgroup` là `cgroup2fs` (R2) | Kiểm ở bước D; cgroup v1 làm gate headroom chặn mọi run |

## 1. Những gì đã xác minh trong source (VERIFIED)

- `prepare` (`run_phase2.prepare_campaign`) không solve. Lệnh này làm các việc sau:
  - kiểm bảng version và preflight v2 (`protocol`, `policy04_smoke = PASS`);
  - dựng plan 216 + 2 pilot;
  - đọc runtime identity: Python phải là venv đã cài, không editable, wheel khớp từng byte;
  - đọc machine identity;
  - lấy owner lock;
  - kiểm headroom: target 2 GiB cộng reserve 2 GiB, tức cần ≥ 4 GiB khả dụng, và **chỉ trên cgroup2**
    (R2);
  - kiểm lại bundle dưới import guard (watchdog 1 800 s, RSS ≤ 2 GiB);
  - ghi `plan.json`, `environment.json`, `seal.json`.
- **Python dùng cho prepare/warmup/pilot phải là `<preflight>/venv-solver/bin/python`**, chạy từ thư mục
  gốc repo với `-m benchmarks.run_phase2`. Dùng `uv run` (môi trường dev, Core editable) sẽ bị chặn với
  `EDITABLE_PACKAGE_NOT_ALLOWED`.
- **Warmup:** fixture tiny policy 0.1 của preflight (budget 10 s / watchdog 15 s / 256 MiB). Không tính là
  mẫu. Phải có lịch hợp lệ thì mới mở được pilot.
- **Pilot:** `c10-base-s101-soft` rồi `c10-base-s101-hard`, repeat 0, budget 60 s / watchdog 150 s / RSS
  ≤ 1 GiB, cần reserve 2 GiB trước mỗi run.
  - Pilot đạt (D2) khi: harness COMPLETE, H PASS, có lịch hợp lệ, P MET.
  - Score khác 0, Q REVIEW_REQUIRED hay zero NOT_APPLICABLE vẫn cho qua.
  - Pilot đầu không đạt → STOPPED, pilot thứ hai không chạy.
- **Mỗi run kiểm lại toàn bộ identity:** seal, sources, bundle, preflight, runtime, machine. Drift →
  BLOCKED trước khi chạy.
- **Chạy lại một phase:** khi phase đã có journal, phải dùng `--resume`. Resume chỉ chạy tiếp các run chưa
  bắt đầu và giữ nguyên các kết quả đã có; một run dở dang (PARTIAL) → NEEDS_REVIEW.
- **Prepare bị từ chối không để lại gì (sửa R1):** headroom không đạt hoặc kiểm bundle không đạt → lệnh
  in `BLOCKED`, không tạo thư mục output, owner marker trở về IDLE. Evidence kiểm bundle lỗi nằm cạnh
  output, trong `.<tên>-prepare-*`. Chạy lại đúng lệnh cũ là được. Chỉ lỗi bất ngờ mới để marker
  `NEEDS_REVIEW`.
- **Owner lock** nằm ở `.git/tkb-campaign-owner`, dùng chung với campaign v1 trên cùng clone. Marker cũ ở
  trạng thái khác IDLE → `STALE_ACTIVE_MARKER_NEEDS_REVIEW`.

## 2. Chưa được kiểm (rủi ro tích hợp)

Trước E0, `preflight`, `prepare` và `execute_campaign` **chưa từng chạy end-to-end** với wheel đã cài (O1 của
[rà soát](../../phase-2-linux-performance-tooling-review.md)). Test chỉ kiểm plan chưa seal bị chặn. Lỗi
tích hợp (đường import, identity, headroom cgroup, journal) chỉ lộ ra khi chạy thật. Vì vậy K1 đề xuất diễn
tập trước trên cloud.

## 3. Trình tự đề xuất

### E0 — Diễn tập kỹ thuật trên cloud (nếu K1 được chọn)

Chạy D và E trong container cloud với campaign ID có tiền tố `rehearsal-`, đi đủ preflight → prepare →
warmup → 2 pilot.

- **Mục đích duy nhất** là bắt lỗi tích hợp của tooling. Số thời gian/RAM là của một container dùng
  chung, CPU không rõ. Chúng **không phải evidence P**, không vào báo cáo hiệu năng, không thay pilot thật.
- Evidence nằm trong scratchpad của phiên (mất khi container bị thu hồi). Chỉ ghi tóm tắt và các lỗi tìm
  được.
- Nếu diễn tập lộ lỗi tooling: dừng, báo cáo, sửa theo TDD trong một nhiệm vụ riêng có ủy quyền. Sau đó
  bundle/preflight của bước D phải làm lại nếu source đổi.

**Kết quả diễn tập E0 (2026-11-05, cloud, không phải evidence).** Đã chạy: bundle (72 dataset,
`DATASETS_VERIFIED`) → preflight (`PREFLIGHT_PASS`, 25 check, smoke 0.4 ra 1.5 / Score 1.2) → prepare →
warmup → 2 pilot → aggregate. Hai phát hiện:

- **R1:** prepare `rehearsal-01` bị chặn ở headroom nhưng để lại owner marker `NEEDS_REVIEW` và thư mục
  output, nên lần chạy lại bị `STALE_ACTIVE_MARKER_NEEDS_REVIEW`. **Đã sửa theo TDD** trong
  `run_phase2.prepare_campaign`: kiểm headroom và bundle trước khi tạo output; lần bị từ chối để marker
  IDLE. Đã kiểm thật trên cloud: prepare không shim bị chặn, không để lại gì; ngay sau đó prepare có shim
  ra `PREPARED` với cùng campaign ID.
- **R2:** container cloud dùng cgroup v1, nên gate headroom (chỉ cgroup2) chặn. Để đi tiếp, diễn tập dùng
  một shim chỉ nằm trong scratchpad (`REHEARSAL_HEADROOM_SHIM`, ước lượng từ `/proc/meminfo`). Máy đích
  phải là cgroup2 (đã thêm vào runbook D và §0).

Với shim, `rehearsal-02` cho kết quả sau:

| Bước | Kết quả |
|---|---|
| Prepare | `PREPARED` |
| Warmup | `COMPLETE` |
| Pilot SOFT | H PASS, P MET; `[39,125,243]` so witness `[0,0,72]` (WORSE); 51,3 s; 238 MiB |
| Pilot HARD | H PASS, P MET; `[6,70,235]` (WORSE); 61,5 s; 194 MiB |
| Aggregate | 216 missing → H/P INCOMPLETE, đúng như kỳ vọng |

Số liệu là của container dùng chung, n = 1, chỉ để thử tích hợp. Riêng chất lượng (P1 khác 0, không tier
nào được chứng minh) là tín hiệu cần chú ý khi xem pilot thật. Evidence diễn tập nằm trong scratchpad
của phiên và sẽ mất khi container bị thu hồi.

### E1 — Prepare trên máy đích

Chạy từ thư mục gốc repo:

```bash
benchmarks/artifacts/phase2-v2/preflight-1/venv-solver/bin/python -m benchmarks.run_phase2 --phase prepare --bundle benchmarks/artifacts/phase2-v2/bundle --preflight-dir benchmarks/artifacts/phase2-v2/preflight-1 --output benchmarks/artifacts/phase2-v2/campaign-01 --campaign-id phase2-v2-linux-01 --machine-id <tên-máy-ngắn>
```

Kỳ vọng: `{"status": "PREPARED", "primary_planned": 216, "pilots": 2}`, exit 0. Không có solve nào.

```bash
sha256sum benchmarks/artifacts/phase2-v2/campaign-01/plan.json benchmarks/artifacts/phase2-v2/campaign-01/seal.json
```

### E2 — Warmup

```bash
benchmarks/artifacts/phase2-v2/preflight-1/venv-solver/bin/python -m benchmarks.run_phase2 --phase warmup --plan benchmarks/artifacts/phase2-v2/campaign-01/plan.json --preflight-dir benchmarks/artifacts/phase2-v2/preflight-1
```

Kỳ vọng: JSON `CampaignState` với `"status": "COMPLETE"`, exit 0.

### E3 — Pilot

Chỉ chạy khi E2 COMPLETE (theo K3):

```bash
benchmarks/artifacts/phase2-v2/preflight-1/venv-solver/bin/python -m benchmarks.run_phase2 --phase pilot --plan benchmarks/artifacts/phase2-v2/campaign-01/plan.json --preflight-dir benchmarks/artifacts/phase2-v2/preflight-1
```

Kỳ vọng nếu đạt: `"status": "COMPLETE"`, `"failed": 0`, exit 0. Trần thời gian của hai pilot là 2 × 150 s
watchdog.

**Không chạy `--phase primary`.**

### E4 — Gửi lại để kiểm

- stdout và exit code của E1–E3; hash của `plan.json` và `seal.json`.
- `campaign-01/` gồm:
  - `seal.json`, `environment.json`, `prepare-headroom.json`, `campaign-state.json`, `journal.jsonl`;
  - `bundle-verification/execution.json`;
  - với mỗi run trong `warmup/` và `pilot/`: `run.json`, `case-verdict.json`, `terminal.json`,
    `result.json`, `stderr.txt`.
- Không cần gửi `plan.json` đầy đủ (lớn); chỉ cần hash.
- `environment.json` chứa hostname, model CPU, dung lượng RAM và hash `/etc/machine-id`. Xem trước nếu
  không muốn chia sẻ.

Tôi sẽ kiểm:

- seal khớp plan và environment;
- warmup có lịch hợp lệ;
- mỗi pilot: harness, verdict H/Q/P/zero, vector score so với witness, launch-to-exit, peak RSS so với
  150 s / 1 GiB, measurement OK;
- journal đúng thứ tự, không run PARTIAL.

Kết luận chỉ là "pilot n = 1 mỗi biến thể", không phải hiệu năng campaign.

## 4. Điều kiện dừng

Dừng, giữ nguyên thư mục campaign và gửi lại khi gặp bất kỳ trường hợp nào sau đây:

- `prepare` in `BLOCKED` (identity, editable, headroom, bundle verification, owner marker…).
- Warmup hoặc pilot trả trạng thái khác `COMPLETE`: `BLOCKED`, `STOPPED`, `NEEDS_REVIEW` hoặc `CANCELLED`.
- Một pilot có H FAIL, không có lịch (UNKNOWN), vượt watchdog hoặc RSS, hoặc measurement lỗi.

Khi dừng:

- **Không retry**, không dùng `--resume` khi chưa được đề nghị.
- Không sửa input, budget, guard hay code.
- Không xóa và không tạo lại campaign với cùng ID.

Campaign `phase2-v2-linux-01` khi đã STOPPED thì giữ nguyên làm evidence. Lần sau (nếu có) dùng ID mới,
`-02`, và cần ủy quyền mới (K4).

Nếu bị ngắt giữa chừng (Ctrl-C, mất điện): không chạy lại ngay. Gửi `campaign-state.json` và
`journal.jsonl` để quyết định resume hay NEEDS_REVIEW.

## 5. Quyết định cần duyệt

- [x] **K1 — Diễn tập E0 trên cloud trước** (rehearsal, không phải evidence). *(Đề xuất: chọn, vì tooling
  chưa chạy end-to-end lần nào; diễn tập rẻ hơn một campaign bị STOPPED vì lỗi tích hợp trên máy đích.)*
- [x] **K2 — Định danh:** campaign `phase2-v2-linux-01`; machine ID là tên ngắn do người dùng chọn (không
  chứa thông tin cá nhân). Output dưới `benchmarks/artifacts/phase2-v2/`. *(Đề xuất: chọn.)*
- [x] **K3 — Chạy E1 → E2 → E3 liên tiếp trong một buổi**, dừng ngay khi một lệnh không ra kết quả kỳ
  vọng, rồi gửi E4 một lần. Gate của tooling đã tự chặn pilot khi warmup không đạt. Phương án thay thế là
  gửi kết quả sau từng lệnh, an toàn hơn nhưng tốn thêm vòng trao đổi. *(Đề xuất: chọn chạy liên tiếp.)*
- [x] **K4 — Không retry trong cùng campaign ID.** Pilot STOPPED → phân tích trước; chạy lại cần ID mới và
  ủy quyền mới. *(Đề xuất: chọn.)*
- [x] **K5 — Điều kiện máy khi chạy:** cắm sạc, không chạy workload nặng khác, không cho máy ngủ. Campaign
  vẫn ghi `workload_control = UNCONTROLLED` như v1, vì tooling không kiểm soát được máy. *(Đề xuất:
  chọn.)*
- [x] **K6 — Kết quả pilot không mở primary tự động.** Sau E4, tôi tóm tắt và anh/chị quyết định ủy
  quyền bước F (216 run, trần watchdog khoảng 9,45 giờ cho phần feasible). *(Đề xuất: chọn.)*
- [x] **K7 — Ghi kết quả:** bản tóm tắt pilot ghi vào `docs/phase-2-linux-performance-report.md` (tạo mới)
  chỉ khi anh/chị cho phép, kèm hash evidence và giới hạn n = 1. Evidence thô không commit.
  *(Đề xuất: chọn.)*

## 6. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Lỗi tích hợp lần đầu chạy thật | K1 diễn tập; gate dừng sớm, evidence giữ nguyên |
| Pilot c10 không tìm được lịch trong 60 s với S08–S11 | Đó là kết quả P NOT_MET hợp lệ, không phải lỗi; không nới budget. Primary không mở; cần quyết định riêng (ví dụ phân tích model) |
| Headroom bị chặn vì máy đang dùng nhiều RAM | Prepare: đóng bớt ứng dụng rồi chạy lại đúng lệnh (sau R1, lần bị chặn không để lại output hay marker). Warmup/pilot: gate chặn trước khi run bắt đầu, ghi `GATE_BLOCKED`; gửi lại `campaign-state.json` trước khi chạy lại với `--resume` |
| Machine identity đổi giữa các bước (cập nhật kernel, đổi RAM) | MACHINE_DRIFT chặn run. Không cập nhật hệ thống giữa E1 và F |
| Marker owner ở trạng thái khác IDLE (`STALE_ACTIVE_MARKER_NEEDS_REVIEW`) | Gửi nội dung `.git/tkb-campaign-owner/active.json` và thư mục campaign nó trỏ tới; không tự xóa. Chỉ dời marker sang chỗ khác (không xóa) sau khi đã xác nhận campaign đó không có run dở dang |
