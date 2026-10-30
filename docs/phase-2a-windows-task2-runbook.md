# Windows Task 2 — Runbook bàn giao và preflight

**PREPARED / WINDOWS BLOCKED — chưa thực hiện trên Windows.** Runbook này là
hướng dẫn tương lai, không phải approval hoặc transcript đã chạy. Theo
[checklist](phase-2a-windows-preflight-handoff-checklist.md) và
[mẫu intake/transfer](phase-2a-windows-preflight-handoff-templates.md).

## 1. Phạm vi và gates

| Gate | Điều kiện trước khi qua |
|---|---|
| Chuẩn bị Linux | Inventory đầy đủ, source frozen đúng Git commit/tree; fake tests không search |
| Máy và bàn giao | Native Windows x64/Python3.12 được xác nhận; intake có evidence, staging read-only theo quy trình; địa điểm nhận được duyệt |
| Approval Task2 | User duyệt rõ machine ID, paths/output root mới, payload inventory SHA256 và scope install/Core suite/tiny probes; ghi reference nguyên văn |
| Receiver | Kiểm mọi file/size/hash/membership; chưa install khi thiếu/mismatch |
| Dependencies | Windows binary wheels đúng lock/pins/hashes; thiếu wheel/import lỗi → ENVIRONMENT_BLOCKED, không đổi pin/build OR-Tools |
| Installed identity | Core ở site-packages, không editable/source shadowing, source bytes = wheel = frozen source; solver/no-solver tách riêng |
| Correctness | Actual Core suite và tất cả tiny/registry/no-solver/bundle checks đạt, raw logs và receipts đầy đủ |
| Kết luận | Review evidence trước Windows Task2 PASS; không tự mở Task3–5 hoặc campaign |

Hash consistency không là approval hay attestation chống người sửa toàn bộ gói.
`--approval-reference` chỉ ghi lại tham chiếu consent đã có, không tự cấp quyền.
Approval Linux trước đã tiêu thụ. Nếu paths/payload/máy/scope thay đổi thì quay lại
review approval; không sửa dữ liệu frozen hoặc dùng lại output attempt cũ để retry.

## 2. Chuẩn bị ở Linux — chỉ đọc nguồn

Inventory tại `docs/windows-task2-payload-inventory.json` mô tả từng file cần có,
origin (`git_blob` hoặc `local_file`), destination, size và sender SHA256. Không có
payload directory/ZIP được tạo. Manifest không chứa chính nó để tránh hash vòng.
File inventory và intake/approval/evidence đặt **ngoài** payload root khi bàn giao.

Origin `git_blob` phải xuất đúng bytes của commit ghi trong row, không lấy file từ
HEAD hoặc checkout có CRLF. Origin local giữ nguyên bytes, không regenerate bundle
hay rebuild Core wheel. Source snapshot nằm dưới `source/`; wheel dưới `wheel/`;
probes mới dưới `tools/`; `linux-reference/` chỉ là evidence lịch sử, không chạy
các scripts Linux đó trên Windows. Không chuyển venv/site-packages Linux.

Chỉ sau khi được phép chuyển mới materialize đúng layout theo inventory và copy.
Mỗi sender/receiver dùng cùng inventory hash được duyệt. Root bundle hash là hash
`manifest.json`, không là hash archive. Giữ đủ36 datasets, kể cả UNSAT provenance.

## 3. Intake và approval — trước install/native tests

Người vận hành điền mẫu `windows-machine-intake.json` từ evidence read-only thực:
`Get-CimInstance Win32_OperatingSystem`, `Win32_Processor`, `Win32_ComputerSystem`,
`Win32_PageFileUsage`, `Get-Date -AsUTC`, `$PSVersionTable`, `uv --version` và
`<python> -I -X utf8 -c "import sys,platform; print(sys.executable,sys.version,platform.machine())"`.
Ghi exact argv/UTC/exit/stdout/stderr; các commands này **chưa chạy trong preparation**.

Power/AC/mode và workload phải ghi trạng thái quan sát thực, timestamp, method và
limitations; thiếu giữ null/reason hoặc UNKNOWN. Không tự đổi power plan, affinity,
đóng ứng dụng hoặc kết luận VERIFIED_IDLE từ một process listing. Virtualization
và P/E topology không xác định được cũng phải giữ null/reason. So hiệu ứng OS chỉ
khi hardware và Python patch khớp Linux3.12.3; khác thì so deployment.

Approval phải ghi machine ID, root nhận payload, root evidence mới, ba venv riêng,
inventory hash và phạm vi Task2. Chưa có approval như vậy trong bộ bàn giao này.
Staging source/bundle không được sửa theo quy trình; không dùng file attribute
ReadOnly như bằng chứng rằng thư mục bất biến. Dev suite dùng bản working copy riêng.

## 4. PowerShell setup và thu logs — sau approval

Ví dụ dùng PowerShell **7.4+** để native stdout redirection giữ bytes. Nếu chưa có,
ghi blocker cho phương pháp capture này, không tự cài/upgrade. Các biến dưới phải
thay bằng paths/IDs đã được duyệt; không chạy nguyên placeholder. Chọn paths tuyệt
đối, tách payload/evidence/dev work/venvs; evidence root chưa tồn tại.

```powershell
$ErrorActionPreference = 'Stop'
$Payload = 'C:\REPLACE\payload'
$Inventory = 'C:\REPLACE\windows-task2-payload-inventory.json'
$Intake = 'C:\REPLACE\windows-machine-intake.json'
$Evidence = 'C:\REPLACE\new-windows-task2-evidence'
$Python = 'C:\REPLACE\Python312\python.exe'
$DevSource = 'C:\REPLACE\dev-working-copy'
$Dev = 'C:\REPLACE\venv-dev'
$Solver = 'C:\REPLACE\venv-solver'
$NoSolver = 'C:\REPLACE\venv-no-solver'
$Wheelhouse = 'C:\REPLACE\windows-wheelhouse'
$MachineId = 'REPLACE-WITH-APPROVED-OPAQUE-ID'
$Approval = 'REPLACE-WITH-ACTUAL-USER-APPROVAL-REFERENCE'
if ($PSVersionTable.PSVersion -lt [version]'7.4') { throw 'CAPTURE_METHOD_BLOCKED' }
if (Test-Path $Evidence) { throw 'OUTPUT_ROOT_EXISTS; do not retry here' }
$NewPaths = @($Evidence, $DevSource, $Dev, $Solver, $NoSolver)
$AllRoots = @($Payload, $Wheelhouse) + $NewPaths
$CanonicalRoots = @($AllRoots | ForEach-Object { [IO.Path]::GetFullPath($_).TrimEnd('\') })
if (($CanonicalRoots | Select-Object -Unique).Count -ne $CanonicalRoots.Count) { throw 'PATHS_MUST_DIFFER' }
foreach ($A in $CanonicalRoots) {
    foreach ($B in $CanonicalRoots) {
        if ($A.StartsWith($B + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'ROOTS_MUST_NOT_OVERLAP'
        }
    }
}
foreach ($Path in $NewPaths) {
    if (Test-Path $Path) { throw "NEW_PATH_ALREADY_EXISTS: $Path" }
}
New-Item -ItemType Directory -Path $Evidence | Out-Null

function Invoke-Recorded {
    param([string]$Name, [string]$Exe, [string[]]$Arguments)
    $PSNativeCommandUseErrorActionPreference = $false
    $Root = Join-Path $Evidence $Name
    if (Test-Path $Root) { throw "ATTEMPT_EXISTS: $Name" }
    New-Item -ItemType Directory -Path $Root | Out-Null
    $Record = [ordered]@{ argv = @($Exe) + $Arguments; cwd = (Get-Location).Path
        started_at_utc = [DateTime]::UtcNow.ToString('o'); exit_code = $null
        status = 'STARTED'; reason = 'COMMAND_NOT_COMPLETED' }
    $Receipt = Join-Path $Root 'receipt.json'
    $Record | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $Receipt
    try {
        & $Exe @Arguments 1> (Join-Path $Root 'stdout.txt') 2> (Join-Path $Root 'stderr.txt')
        $Record.exit_code = $LASTEXITCODE
        if ($Record.exit_code -ne 0) { throw "COMMAND_EXIT_$($Record.exit_code)" }
        $Record.status = 'COMMAND_EXIT_ZERO'
        $Record.reason = $null
    } catch {
        $Record.status = 'FAILED_OR_INCOMPLETE'
        $Record.reason = $_.Exception.Message
        throw
    } finally {
        $Record['finished_at_utc'] = [DateTime]::UtcNow.ToString('o')
        $Record | ConvertTo-Json -Depth 10 | Set-Content -Encoding utf8 $Receipt
    }
}
```

`COMMAND_EXIT_ZERO` không là check PASS; phải đọc nội dung output. Không tiếp tục
khi exception/nonzero. Giữ logs/partial directories; không overwrite hoặc auto retry.
Nếu cần attempt khác, review failure và xin scope/root mới trước, giữ attempt cũ.

## 5. Kiểm receiver và dependencies

Đối chiếu inventory SHA256 qua kênh bàn giao đã duyệt, không chỉ hash inventory
với chính nó. Điền transfer manifest sender/receiver ID/hash/time thực; không sửa
inventory frozen để thêm receiver hashes. `verify` sinh receipt riêng:

```powershell
Get-FileHash -Algorithm SHA256 $Inventory
Invoke-Recorded 'receiver-hashes' $Python @('-I','-B','-X','utf8',
    "$Payload\tools\windows_payload.py",'verify','--root',$Payload,'--inventory',$Inventory)
```

Kiểm stdout là `PAYLOAD_HASHES_MATCH`, `execution_authorized=false`; đây chưa là
Windows PASS. Verifier yêu cầu exact file membership; không để evidence/venv hoặc
inventory trong payload. Ghi hash intake/approval references bên ngoài root.

Sau approval, tạo working copy của `source/` tại `$DevSource` (không sửa staging),
kiểm từng file copy với inventory các row `source/`. Không checkout HEAD thay thế.
Xuất ba requirements từ **lock frozen**; uv export không được cập nhật lock:

```powershell
Invoke-Recorded 'export-solver' 'uv' @('export','--locked','--project',"$Payload\source",
    '--no-dev','--extra','solver','--no-emit-project','--output-file',"$Evidence\requirements-solver.txt")
Invoke-Recorded 'export-no-solver' 'uv' @('export','--locked','--project',"$Payload\source",
    '--no-dev','--no-emit-project','--output-file',"$Evidence\requirements-no-solver.txt")
Invoke-Recorded 'export-dev' 'uv' @('export','--locked','--project',"$Payload\source",
    '--extra','solver','--group','dev','--no-emit-project','--output-file',"$Evidence\requirements-dev.txt")
```

Chuẩn bị wheelhouse Windows **sau approval**, chọn artifacts đúng Python/platform
và versions từ lock/requirements export. Lưu từng URL, filename, version, SHA256,
UTC và log download; kiểm hash artifact thuộc lock, lưu `dependency-wheel-inventory.json`.
Không chỉ copy Linux requirements/package list rồi gán PASS. Nếu uv cần interpreter
khác, thiếu binary wheel hoặc export/resolution lỗi thì ENVIRONMENT_BLOCKED.
Không tự tải Python khác, đổi pins hoặc build OR-Tools từ source.

Wheelhouse chưa được tạo trong preparation. Người vận hành phải hoàn thành và
review inventory này trước các lệnh install offline dưới đây; không tự coi việc
ghi một tên file là đã có wheel hợp lệ. Core wheel dùng chính bytes frozen.

```powershell
Invoke-Recorded 'venv-dev' 'uv' @('venv','--python',$Python,$Dev)
Invoke-Recorded 'venv-solver' 'uv' @('venv','--python',$Python,$Solver)
Invoke-Recorded 'venv-no-solver' 'uv' @('venv','--python',$Python,$NoSolver)
Invoke-Recorded 'install-dev-dependencies' 'uv' @('pip','install','--python',"$Dev\Scripts\python.exe",
    '--require-hashes','--only-binary',':all:','--no-index','--find-links',$Wheelhouse,
    '-r',"$Evidence\requirements-dev.txt")
Invoke-Recorded 'install-solver-dependencies' 'uv' @('pip','install','--python',"$Solver\Scripts\python.exe",
    '--require-hashes','--only-binary',':all:','--no-index','--find-links',$Wheelhouse,
    '-r',"$Evidence\requirements-solver.txt")
Invoke-Recorded 'install-no-solver-dependencies' 'uv' @('pip','install','--python',"$NoSolver\Scripts\python.exe",
    '--require-hashes','--only-binary',':all:','--no-index','--find-links',$Wheelhouse,
    '-r',"$Evidence\requirements-no-solver.txt")
Invoke-Recorded 'install-core-solver' 'uv' @('pip','install','--python',"$Solver\Scripts\python.exe",
    '--no-deps',"$Payload\wheel\vnedu_tkb_core-0.2.0-py3-none-any.whl[solver]")
Invoke-Recorded 'install-core-no-solver' 'uv' @('pip','install','--python',"$NoSolver\Scripts\python.exe",
    '--no-deps',"$Payload\wheel\vnedu_tkb_core-0.2.0-py3-none-any.whl")
```

Dev suite có packaging test gọi `uv build --offline`: build backend
`hatchling==1.32.4` nằm trong pyproject nhưng **không trong uv.lock**. Chuẩn bị
cache/build-dependency inventory riêng có hash và provenance trước khi chạy;
nếu thiếu thì ghi blocker, không bỏ test hoặc đổi backend. Dev environment được
phép dùng editable working copy riêng; installed solver/no-solver tuyệt đối không.
Để cài dev source, dùng `uv pip install --python <dev-python> --no-deps -e <DevSource>`
với build dependencies/cache đã review; ghi argv/log/hash thực. Không build lại
Core wheel dùng cho installed probes để thay wheel frozen.

Chạy `uv pip check --python <venv-python>` và `uv pip list --python <venv-python> --format json`
qua `Invoke-Recorded`, với tên riêng cho từng venv; lưu actual packages và compare
lock. Hash wheelhouse/requirements/install logs là phần evidence bắt buộc.

## 6. Installed checks và Core suite — có native search, chưa được chạy

```powershell
$Probe = "$Payload\tools\windows_preflight.py"
$SolverPython = "$Solver\Scripts\python.exe"
$NoSolverPython = "$NoSolver\Scripts\python.exe"
$Common = @('--payload',$Payload,'--inventory',$Inventory,'--machine-id',$MachineId,
    '--approval-reference',$Approval)
Invoke-Recorded 'environment-solver' $SolverPython (@('-I','-B','-X','utf8',$Probe,'environment',
    '--environment','solver','--output',"$Evidence\checks\environment-solver") + $Common)
```

Tiếp tục trong cùng phiên PowerShell sau khi installed identity solver đạt:

```powershell
Invoke-Recorded 'environment-no-solver' $NoSolverPython (@('-I','-B','-X','utf8',$Probe,'environment',
    '--environment','no-solver','--output',"$Evidence\checks\environment-no-solver") + $Common)
Push-Location $DevSource
try {
    Invoke-Recorded 'core-pytest' "$Dev\Scripts\python.exe" @('-B','-X','utf8','-m','pytest','tests',
        '-p','no:cacheprovider','-q')
} finally { Pop-Location }
Invoke-Recorded 'tiny-smoke' $SolverPython (@('-I','-B','-X','utf8',$Probe,'smoke',
    '--output',"$Evidence\checks\smoke") + $Common)
Invoke-Recorded 'registry' $SolverPython (@('-I','-B','-X','utf8',$Probe,'registry',
    '--result',"$Evidence\checks\smoke\result.json",'--output',"$Evidence\checks\registry") + $Common)
Invoke-Recorded 'no-solver-guard-score' $NoSolverPython (@('-I','-B','-X','utf8',$Probe,'guard-score',
    '--environment','no-solver','--input',"$Evidence\checks\smoke\input.json",
    '--result',"$Evidence\checks\smoke\result.json",'--output',"$Evidence\checks\guard-score") + $Common)
Invoke-Recorded 'bundle-verification' $SolverPython (@('-I','-B','-X','utf8',$Probe,'bundle',
    '--output',"$Evidence\checks\bundle") + $Common)
```

Các probes chạy Python isolated, kiểm lại toàn payload và installed identity mỗi
lần. Root check phải mới; không tự retry. Tiny smoke dùng default SolveOptions
60s/workers1/seed42 và guards10,000slots/10,000occurrences/100,000placements/
1,000,000occupancy terms; không hint/tuning. Một tiny feasibility và các quality
tiers có thể có nhiều native calls theo Core; không phải protocol một-call của
diagnostic TIGHT10. CLI invalid-lock/hard cases và pending registry phải trả rejection
trước native search. Bộ fake tests Linux không chứng minh điều này trên Windows.

Bundle command chỉ import verifier frozen để validate/score36, guard chặn OR-Tools,
solver/compiler. Nó không solve10/20/40datasets. No-solver guard-score chặn thêm
preprocessing; phải khớp hard validity/score của **result Windows vừa tạo**, không
lấy result Linux làm kết quả Windows. Lưu schema1.1/output1.2/policy0.1, duration1/2,
S01–S04, tier1–3, actual assignments/fingerprint và expected-vs-actual cases.

## 7. Thu evidence và kết luận

Không tự động tổng hợp thành Windows PASS từ exit0 hoặc một check PASS. Chốt
`preflight-manifest.json` liên kết intake/native proof, approval reference,
inventory hash, source commit/tree, actual environments/dependencies, từng command
và verdict. Hash toàn bộ raw receipts/logs/inputs/results sau khi hoàn tất;
inventory evidence riêng không hash chính nó. Không sửa stdout/raw paths/source
identity, không ghi đè artifacts Linux. File thiếu/null phải có reason.

Review theo checklist: Core counts/pass/fail/skip/xfail/reasons; installed identity
hai venv; tiny smoke độc lập validate/score; registry ready/pending/disabled;
malformed/stale/invalid locks/custom hard; no-solver imports;27feasible witnesses
(18zero,9TIGHT positive P2≥60/120/240, không claim attainable) và9UNSAT30>29.
Giữ vector/null/proof/status riêng, không so assignments/latency giữa OS.

`windows-preflight-report.md` ghi PASS/BLOCKED/FAIL từng check, machine/context,
drift so Linux, missing evidence và performance **NOT_MEASURED**. Chỉ sau review
đủ native evidence mới cân nhắc Windows Task2 PASS. Task3Windows supervisor/RAM,
Task4campaign, Task5cross-OS/performance, Phase2B/2C vẫn ngoài scope. Linuxfailed63,
ba repeats/fingerprint và Windows BLOCKED trong receipts lịch sử giữ nguyên.
