# Windows Task 2 — readiness trước intake thực tế

**WINDOWS BLOCKED — chưa đủ dữ liệu để chốt approval thực thi.** Đây là baseline
readiness trên evidence hiện có, không là báo cáo đã thu từ Windows. Hướng dẫn
thu tại [intake guide](phase-2a-windows-task2-intake-guide.md); tiêu chí tại
[checklist](phase-2a-windows-preflight-handoff-checklist.md).

## Evidence đã có và chưa có

| Mục | Trạng thái hiện tại | Cần nhận/đối chiếu |
|---|---|---|
| Sender payload | PREPARED, inventory235files/36datasets | Giữ đúng hash cuối bên dưới; chưa chuyển |
| Máy Windows native/x64 | NOT_VERIFIED | CIM OS/build, shell launch context, Python sys.platform/arch; virtualization riêng |
| Python/công cụ | NOT_COLLECTED | Python3.12 exact patch/path/bits, uv version, PowerShell version/capture method |
| CPU/RAM/pagefile | NOT_COLLECTED | CPU/topology, RAM native units, pagefile settings/usage, null+reason nếu thiếu |
| Context | UNKNOWN | UTC/AC-battery/Windows power mode/workload; không tự coi idle |
| So Linux | NOT_ASSESSED | Cùng hardware dual-boot và Python3.12.3 mới cô lập OS; khác thì deployment comparison |
| Roots và aliases | NOT_SELECTED/NOT_VERIFIED | Payload/dev/evidence/venvs/wheelhouse local, tách nhau, không nesting/junction/reparse aliases; root mới |
| Staging read-only | NOT_CONFIRMED | Quy trình và evidence reference; không chỉ Windows ReadOnly attribute |
| Bàn giao | NOT_CONFIRMED | Người vận hành, điểm nhận, cách trả evidence; inventory/approval ngoài payload root |
| Approval Task2 | NOT_GRANTED | Machine ID/paths/root/scope và inventory hash được user duyệt rõ |

Không đổi null thành0/false. Thiếu thông tin critical về native identity hoặc roots
thì chưa đề xuất thực thi. Power/workload không kiểm soát được có thể được báo
UNKNOWN cùng giới hạn để user review, không tự bịa VERIFIED_IDLE. Snapshot thay
đổi theo thời gian, cần thu lại context khi execution sau này được phép.

## Các checks sau approval, không phải evidence đã PASS

- Materialize/copy đúng payload và verify đủ receiver hashes/membership trước install.
- Windows lock resolution, binary dependency-wheel availability/hash inventory và
  install/import/package checks; failure → ENVIRONMENT_BLOCKED, không đổi pins.
- Build cache cho Hatchling1.32.4/packaging test: ngoài uv.lock, cần source/hash
  evidence và review trước full Core suite; chưa download hoặc cài trong intake.
- Installed solver/no-solver identity, full Core suite và tất cả tiny/registry/
  no-solver checks, verification36datasets. Chưa có result hoặc test counts Windows.
- PowerShell capture/runbook/native path behavior chưa kiểm trên Windows; không
  coi fake tests Linux là nghiệm thu Windows. Không tự cài/upgrade công cụ để qua gate.

## Hash và proposed scope cho approval sau intake

Inventory được kiểm lại tại Linux bằng `sha256sum`; hash hiện tại:

`4cb49a7b6b173be0fcb7d277263df7a53c4418ea01f142ff7596e9887ec9988c`

Hai tài liệu intake/readiness mới nằm **ngoài inventory payload**; không chỉnh
payload frozen để nhúng chúng. Phải đối chiếu origin bytes/hash lại trước bàn giao,
không tự tái tạo inventory mới rồi xem approval hash cũ còn hiệu lực.

Mẫu dưới là **đề xuất chưa được chấp thuận**, chỉ điền actual machine/paths và gửi
user sau review intake; không chạy placeholder hoặc tự ghi approval GRANTED:

> Tôi chấp thuận chỉ Task2 Windows preflight trên machine-ID [ACTUAL_ID], Python
> [ACTUAL_PATH_AND_PATCH], payload root [ACTUAL_PATH], inventory SHA256
> 4cb49a7b6b173be0fcb7d277263df7a53c4418ea01f142ff7596e9887ec9988c,
> dev working copy [PATH], venv dev/solver/no-solver [THREE_PATHS], wheelhouse
> [PATH], evidence/output root mới [PATH]. Cho phép materialize/chuyển payload,
> verify receiver, export/resolve/download binary dependencies đúng lock/pins,
> kiểm wheel/build-dependency hashes trước install, tạo các môi trường riêng,
> chạy full Core suite, tiny smoke/registry/no-solver và validation/scoring đủ36
> datasets theo runbook. Giữ nguyên Core wheel/budget/guards; chỉ tiến hành khi
> các gate tương ứng đạt. Giữ errors/partial evidence và dừng khi gate fail;
> không tự retry, đổi pin, nâng Python/uv/PowerShell, build OR-Tools từ source,
> chạy school-size search/benchmark, Task3–5 hoặc Phase2B/2C. Không commit/push.

Approval này không là hứa hẹn preflight PASS; tiny quality/Core suite có thể có
nhiều native calls theo tests, không dùng lại one-call approvals Linux trước.
Đổi máy/paths/hash/scope phải review lại. Receiver success chỉ là byte consistency.

## Lượt chuẩn bị hướng dẫn này

Đã đọc runbook/checklist/templates/preparation report, kiểm hash inventory cuối
và hướng dẫn Microsoft về memory units, power query, redirection. Chưa có kết nối
Windows hoặc evidence thực thu; không đưa ra Windows hardware/version/workload
values giả. Hai tài liệu mới được thêm, chưa sửa payload đã freeze, stage/commit/push.
Không copy payload, cài đặt, tạo venv, export/download dependencies, chạy tests,
solver/search/profiling hoặc thay Core/budget/guards. WindowsTask2 vẫn BLOCKED;
Task3–5 và cross-OS performance chưa được nghiệm thu.
