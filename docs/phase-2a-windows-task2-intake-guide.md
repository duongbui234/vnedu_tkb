# Windows Task 2 — thực hiện intake, chưa install/solve

Hướng dẫn này bổ sung ngoài payload frozen, không đổi inventory đã chốt:
`4cb49a7b6b173be0fcb7d277263df7a53c4418ea01f142ff7596e9887ec9988c`.
Theo [checklist](phase-2a-windows-preflight-handoff-checklist.md),
[mẫu intake](phase-2a-windows-preflight-handoff-templates.md) và
[runbook Task2](phase-2a-windows-task2-runbook.md).

## 1. Chạy ở đâu và điền gì

Mở PowerShell từ Start/Windows Terminal **trên Windows**, không chạy trong WSL,
SSH Linux hoặc shell của repository Linux. Dùng quyền user hiện có; gặp Access
Denied thì giữ lỗi/null, không tự đổi quyền. Có thể thu CIM bằng PowerShell5.1;
PowerShell7.4+ là yêu cầu của phương pháp capture cho Task2 sau này, chưa cần cài.

Không chạy phần install/venv/probes/Core suite của runbook. Các block dưới chỉ
query máy và ghi một thư mục intake mới trong TEMP. Chưa tạo các paths Task2,
copy payload, export requirements, tải binary wheels, cài đặt hoặc gọi solver.
Không thay execution policy, power plan, affinity hoặc đóng ứng dụng.

Đầu tiên chỉ liệt kê executable đã có, không chạy alias để mở Store/tải Python:

```powershell
Get-Command python.exe,python3.exe,py.exe,uv.exe,pwsh.exe -All -ErrorAction SilentlyContinue |
    Select-Object Name, CommandType, Source
```

Chọn đường dẫn Python3.12 thực đã cài; không chọn Microsoft WindowsApps alias.
Nếu không có, để `$TkbPython = $null` và thu phần còn lại, ghi blocker; chưa cài.
Sửa các giá trị đầu block tiếp theo:

- Machine ID opaque, không hostname/tên người thật.
- Python path hoặc null; không dùng launcher tự chọn/tải interpreter.
- Base path dự kiến trên local fixed drive, ví dụ `C:\tkb-task2`; mới chỉ đề xuất.
- Ghi AC/battery, Windows power mode đang thấy, workload đang chạy, cùng timestamp.
  Không biết thì để null. Active power scheme không tự chứng minh power mode slider.
- Dual-boot cùng máy Linux tham chiếu hay không: true/false/null theo thông tin thực.
  Virtualization/P-E topology chưa xác định được thì vẫn null/reason.

## 2. Thu observations và logs

Copy toàn bộ block này vào cùng phiên PowerShell. Các functions chỉ có hiệu lực
trong phiên đó. Đây là lệnh hướng dẫn chưa được chạy/parse trên Windows trong lượt
soạn tài liệu; cần đọc kết quả thực và giữ errors, không coi script kết thúc là PASS.

```powershell
$TkbMachineId = 'win-native-01'
$TkbPython = $null # Thay bằng absolute path python.exe thực nếu đã có.
$TkbPlannedBase = 'C:\tkb-task2'
$TkbAcOrBattery = $null # Ví dụ: AC, quan sát trực tiếp tại thời điểm thu.
$TkbWindowsPowerMode = $null # Ghi nguyên tên hiển thị, không đổi setting.
$TkbWorkloadDescription = $null # Ví dụ: IDE/browser đang mở; không kết luận idle.
$TkbSameDualBootHardware = $null
$TkbManualObservationUtc = [DateTime]::UtcNow.ToString('o')
$TkbIntakeRoot = Join-Path $env:TEMP ('tkb-intake-' + [guid]::NewGuid().ToString('N'))
if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_SESSION_REQUIRED' }
if (Test-Path -LiteralPath $TkbIntakeRoot) { throw 'INTAKE_ROOT_EXISTS' }
New-Item -ItemType Directory -Path $TkbIntakeRoot -ErrorAction Stop | Out-Null
$TkbIntakeObservations = [ordered]@{}

function Read-TkbObservation {
    param([string]$Name, [scriptblock]$Query)
    $Record = [ordered]@{ kind = 'POWERSHELL_QUERY'; command = $Query.ToString()
        cwd = (Get-Location).Path; started_at_utc = [DateTime]::UtcNow.ToString('o')
        status = 'NOT_COLLECTED'; data = $null; reason = $null
        exit_code = $null; exit_code_reason = 'NOT_APPLICABLE_TO_CMDLET' }
    try {
        $Value = & $Query
        if ($null -eq $Value -or @($Value).Count -eq 0) {
            $Record.status = 'UNAVAILABLE'; $Record.reason = 'NO_DATA_RETURNED'
        } else {
            $Record.data = $Value; $Record.status = 'OBSERVED'
        }
    } catch {
        $Record.status = 'UNAVAILABLE'; $Record.reason = $_.Exception.Message
    }
    $Record['finished_at_utc'] = [DateTime]::UtcNow.ToString('o')
    $script:TkbIntakeObservations[$Name] = $Record
}

function Read-TkbNativeObservation {
    param([string]$Name, [string]$Executable, [string[]]$Arguments)
    $Record = [ordered]@{ kind = 'NATIVE_QUERY'; argv = @($Executable) + $Arguments
        cwd = (Get-Location).Path; started_at_utc = [DateTime]::UtcNow.ToString('o')
        status = 'UNAVAILABLE'; exit_code = $null; reason = 'EXECUTABLE_NOT_SELECTED'
        launch_attempted = $false
        stdout_path = $null; stderr_path = $null
        capture = 'POWERSHELL_REDIRECTION; encoding depends on shell version; not solver raw evidence' }
    $PSNativeCommandUseErrorActionPreference = $false
    $ErrorActionPreference = 'Continue'
    if ($Executable -and (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        $Record.stdout_path = "$Name.stdout.txt"
        $Record.stderr_path = "$Name.stderr.txt"
        try {
            $Record.launch_attempted = $true
            & $Executable @Arguments 1> (Join-Path $TkbIntakeRoot $Record.stdout_path) 2> (Join-Path $TkbIntakeRoot $Record.stderr_path)
            $Record.exit_code = $LASTEXITCODE
            if ($Record.exit_code -eq 0) {
                $Record.status = 'OBSERVED'; $Record.reason = $null
            } else { $Record.reason = 'NATIVE_QUERY_NONZERO; READ_STDERR' }
        } catch { $Record.reason = $_.Exception.Message }
    }
    $Record['finished_at_utc'] = [DateTime]::UtcNow.ToString('o')
    $script:TkbIntakeObservations[$Name] = $Record
}

Read-TkbObservation 'os' {
    Get-CimInstance Win32_OperatingSystem -ErrorAction Stop |
        Select-Object Caption,Version,BuildNumber,OSArchitecture,TotalVisibleMemorySize,FreePhysicalMemory
}
Read-TkbObservation 'cpu' {
    Get-CimInstance Win32_Processor -ErrorAction Stop |
        Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,Architecture,LoadPercentage
}
Read-TkbObservation 'system' {
    Get-CimInstance Win32_ComputerSystem -ErrorAction Stop |
        Select-Object Manufacturer,Model,HypervisorPresent,TotalPhysicalMemory,NumberOfLogicalProcessors,AutomaticManagedPagefile
}
Read-TkbObservation 'pagefile_usage' {
    Get-CimInstance Win32_PageFileUsage -ErrorAction Stop |
        Select-Object AllocatedBaseSize,CurrentUsage,PeakUsage
}
Read-TkbObservation 'pagefile_settings' {
    Get-CimInstance Win32_PageFileSetting -ErrorAction Stop |
        Select-Object InitialSize,MaximumSize
}
Read-TkbObservation 'battery' {
    Get-CimInstance Win32_Battery -ErrorAction Stop |
        Select-Object BatteryStatus,EstimatedChargeRemaining
}
Read-TkbObservation 'shell' {
    [ordered]@{ version = $PSVersionTable.PSVersion.ToString(); edition = $PSVersionTable.PSEdition
        is_64bit_process = [Environment]::Is64BitProcess; is_64bit_os = [Environment]::Is64BitOperatingSystem }
}
Read-TkbObservation 'existing_tools' {
    Get-Command python.exe,python3.exe,py.exe,uv.exe,pwsh.exe -All -ErrorAction SilentlyContinue |
        Select-Object Name,CommandType,Source
}
Read-TkbObservation 'process_count_snapshot' { (Get-Process -ErrorAction Stop | Measure-Object).Count }
Read-TkbObservation 'planned_paths' {
    if ($TkbPlannedBase -notmatch '^[A-Za-z]:\\') { throw 'LOCAL_ABSOLUTE_PATH_REQUIRED' }
    $Rows = foreach ($Leaf in @('payload-v1','dev-work-v1','venv-dev-v1','venv-solver-v1',
                              'venv-no-solver-v1','evidence-v1','wheelhouse-v1')) {
        $Path = [IO.Path]::GetFullPath((Join-Path $TkbPlannedBase $Leaf))
        $Ancestors = @(); $Cursor = $Path
        while ($Cursor) {
            if (Test-Path -LiteralPath $Cursor) {
                $Item = Get-Item -LiteralPath $Cursor -Force -ErrorAction Stop
                $Ancestors += [ordered]@{ path = $Item.FullName
                    reparse_point = [bool]($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) }
            }
            $Parent = Split-Path -Path $Cursor -Parent
            if ($Parent -eq $Cursor) { break }; $Cursor = $Parent
        }
        [ordered]@{ path = $Path; exists = (Test-Path -LiteralPath $Path)
            existing_ancestors = $Ancestors; reason = 'PROPOSED_ONLY; NO_DIRECTORY_CREATED' }
    }
    $Rows
}
Read-TkbObservation 'local_fixed_drives' {
    Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' -ErrorAction Stop |
        Select-Object DeviceID,DriveType,Size,FreeSpace
}

$TkbUvCommand = Get-Command uv.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
Read-TkbNativeObservation 'uv-version' $TkbUvCommand.Source @('--version')
Read-TkbNativeObservation 'power-scheme' (Join-Path $env:WINDIR 'System32\powercfg.exe') @('/getactivescheme')
if ($TkbPython -and $TkbPython -match '(?i)\\WindowsApps\\') {
    throw 'DO_NOT_RUN_STORE_ALIAS; keep Python null and collect remaining evidence'
}
$TkbPythonQuery = 'import sys,platform,json,struct; print(json.dumps({"executable":sys.executable,"prefix":sys.prefix,"version":platform.python_version(),"bits":struct.calcsize("P")*8,"machine":platform.machine(),"sys_platform":sys.platform,"system":platform.system()}))'
Read-TkbNativeObservation 'python-identity' $TkbPython @('-I','-B','-X','utf8','-c',$TkbPythonQuery)

$TkbIntakeSummary = [ordered]@{
    status = 'OBSERVATIONS_ONLY'; windows_preflight_status = 'BLOCKED'
    machine_id = $TkbMachineId; collected_at_utc = [DateTime]::UtcNow.ToString('o')
    expected_payload_inventory_sha256 = '4cb49a7b6b173be0fcb7d277263df7a53c4418ea01f142ff7596e9887ec9988c'
    payload_received_or_verified = $false; approval_status = 'NOT_GRANTED'
    native_windows_verified = $null; native_windows_reason = 'REVIEW_CIM_PYTHON_AND_LAUNCH_CONTEXT'
    same_dual_boot_hardware = $TkbSameDualBootHardware
    comparison_reason = 'VERIFY_HARDWARE_AND_PYTHON_PATCH; LINUX_REFERENCE_3.12.3'
    virtualization_verified = $null; virtualization_reason = 'HYPERVISOR_FLAG_IS_NOT_COMPLETE_VIRTUALIZATION_PROOF'
    p_e_topology = $null; p_e_topology_reason = 'NOT_COLLECTED'
    manual_context = [ordered]@{ observed_at_utc = $TkbManualObservationUtc
        ac_or_battery = $TkbAcOrBattery; windows_power_mode = $TkbWindowsPowerMode
        competing_workload = $TkbWorkloadDescription; workload_status = 'UNKNOWN'
        null_reason = 'NOT_OBSERVED_OR_NOT_CONFIRMED; NO_IDLE_CLAIM' }
    staging_read_only_confirmed = $null; staging_read_only_reason = 'PROCEDURE_NOT_YET_REVIEWED'
    staging_read_only_procedure_reference = $null
    binary_wheel_availability = $null; binary_wheel_reason = 'NO_RESOLUTION_DOWNLOAD_OR_INSTALL'
    observations_reference = 'observations.json'
    native_units = [ordered]@{ os_memory_fields = 'kilobytes'; system_TotalPhysicalMemory = 'bytes'
        pagefile_size_fields = 'megabytes'; disk_Size_and_FreeSpace = 'bytes' }
}
$TkbIntakeObservations | ConvertTo-Json -Depth 12 | Set-Content -Encoding utf8 (Join-Path $TkbIntakeRoot 'observations.json')
$TkbIntakeSummary | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $TkbIntakeRoot 'intake-summary.json')
$TkbIntakeFiles = @(Get-ChildItem -LiteralPath $TkbIntakeRoot -File | ForEach-Object {
    [ordered]@{ path = $_.Name; size_bytes = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$TkbIntakeFiles | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $TkbIntakeRoot 'intake-files.sha256.json')
Write-Output "INTAKE_ONLY: $TkbIntakeRoot"
```

Không có battery/pagefile rows không tự chứng minh AC hoặc pagefile disabled.
`TotalVisibleMemorySize`/`FreePhysicalMemory` giữ native kilobytes, `TotalPhysicalMemory`
giữ bytes; pagefile size fields giữ native megabytes. Không gộp units hoặc coi RAM host
là solver peak. Snapshot CPU load/process count không là VERIFIED_IDLE hoặc
benchmark. Nguồn: [Microsoft Win32_OperatingSystem](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-operatingsystem),
[Win32_PageFileUsage](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-pagefileusage).

`powercfg /getactivescheme` chỉ đọc scheme hiện hành theo
[Microsoft powercfg](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/powercfg-command-line-options).
PowerShell cũ có thể decode/re-encode redirected logs; ở đây chỉ là context intake,
không tái sử dụng như raw native solve evidence. Capture Task2 theo runbook cần
PowerShell7.4+ và kiểm trên Windows; xem [Microsoft redirection](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_redirection).

## 3. Gửi lại evidence và điền thông tin thủ công

Giữ cả thư mục nếu có query fail; không xóa outputs lỗi để làm đẹp intake. Nếu
script bị dừng giữa chừng, ghi command/error/UTC và giữ thư mục partial; không
coi thiếu file là null hợp lệ hoặc intake hoàn tất. Chưa chạy lại để lấp chỗ trống
trước khi review lỗi. Không ghi credentials, hostname/serial/usernames hoặc
command lines của ứng dụng khác; các queries chỉ chọn thuộc tính cần thiết.

Gửi `intake-summary.json`, `observations.json`, ba cặp stdout/stderr, và
`intake-files.sha256.json` nếu có; tool không tồn tại có thể không tạo log và phải
có record UNAVAILABLE. Đây là **evidence intake**, không là payload wheel/bundle.
Có thể gửi nội dung JSON và logs cần thiết thay vì archive; chưa cần copy payload.

Kèm trả lời ngắn: (1) đã mở PowerShell trực tiếp từ Windows hay qua môi trường nào;
(2) virtualization có biết không; (3) cùng máy dual-boot Linux hay máy khác;
(4) xác nhận paths đề xuất có dùng được không và cách bàn giao sau khi duyệt;
(5) mô tả quy trình giữ staging read-only: ai được sửa, dev dùng working copy riêng,
không ghi outputs/venvs vào staging, recheck inventory trước execution.
Lời khai phải phân biệt với evidence query; không tự gán verified từ câu trả lời.

## 4. Review readiness và approval proposal

Dùng [báo cáo readiness hiện tại](phase-2a-windows-task2-readiness-report.md) để điền
actuals sau khi nhận evidence. Thu intake không là cấp quyền install hoặc solve.
Phân biệt prerequisites cần có trước approval (máy/paths/context/scope/inventory)
với checks chỉ thực hiện được sau approval (receiver/import/Core suite/probes).
Không yêu cầu đã solve PASS trước khi cho phép preflight, cũng không mặc định
preflight sẽ PASS khi inventory sender đã khớp.
