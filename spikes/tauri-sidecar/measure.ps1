<#
.SYNOPSIS
  Measure the Tauri 2 sidecar spike on Windows 10/11 (run build.ps1 first).
.DESCRIPTION
  For each variant (onedir, onefile): silent-install the NSIS installer into a per-user folder, then
  measure installer and installed size, Core start-up, Core run directly and through the app (time,
  RAM of the app + WebView2 + Core process trees), app idle RAM, a Vietnamese path with spaces, and
  cancelling a running job. Uninstalls afterwards. Runs one job at a time on purpose: the question is
  how one app behaves on one school PC, and parallel jobs would distort its RAM and time.
  Output: results\results-<computer>.json
#>
param(
    [Parameter(Mandatory = $true)][string]$Inputs,
    [string]$Repo = '',
    [string[]]$Variants = @('onedir', 'onefile'),
    [int]$Workers = 4,
    [int]$TimeLimit = 180,
    [int]$IdleSeconds = 30
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$Spike = $PSScriptRoot
$Results = Join-Path $Spike 'results'
$Work = Join-Path $env:TEMP 'tkb-spike-runs'
New-Item -ItemType Directory -Force $Results, $Work | Out-Null
$StartedAt = Get-Date

$In38 = Join-Path $Inputs 'TR38-input.json'
$In13 = Join-Path $Inputs 'TR13-input.json'
$RepIn = Join-Path $Inputs 'TR13-repair-input.json'
$RepPrev = Join-Path $Inputs 'TR13-repair-previous.json'
$RepReq = Join-Path $Inputs 'TR13-repair-request.json'
foreach ($f in $In38, $In13, $RepIn, $RepPrev, $RepReq) { if (-not (Test-Path -LiteralPath $f)) { throw "Missing input: $f" } }

function Join-Args([string[]]$List) {
    ($List | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
}

function Get-Tree([int]$RootId) {
    $all = @(Get-CimInstance Win32_Process -Property ProcessId, ParentProcessId, Name, WorkingSetSize, PeakWorkingSetSize)
    $ids = @{ $RootId = $true }
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($p in $all) {
            if (-not $ids.ContainsKey([int]$p.ProcessId) -and $ids.ContainsKey([int]$p.ParentProcessId)) { $ids[[int]$p.ProcessId] = $true; $changed = $true }
        }
    }
    return @($all | Where-Object { $ids.ContainsKey([int]$_.ProcessId) })
}

function Get-Group([string]$Name) {
    switch -Regex ($Name) {
        '^(tkb-core|python)\.exe$' { 'core' }
        '^msedgewebview2\.exe$' { 'webview' }
        default { 'shell' }
    }
}

# Start a process and sample its whole tree until it exits. Returns time, exit code and RAM (MB):
# peak of the sampled sum per group, and the sum of each process's own peak working set per group.
function Watch-Run([string]$Exe, [string[]]$ArgList, [switch]$ShowWindow, [int]$IntervalMs = 500) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    # The app keeps its normal window (WebView2 behaves as in real use); console runs stay hidden.
    if ($ShowWindow) { $style = 'Normal' } else { $style = 'Hidden' }
    $p = Start-Process -FilePath $Exe -ArgumentList (Join-Args $ArgList) -PassThru -WindowStyle $style
    $null = $p.Handle  # keeps ExitCode readable after exit
    $peakSum = @{ shell = 0.0; webview = 0.0; core = 0.0; total = 0.0 }
    $procPeak = @{}
    while (-not $p.HasExited) {
        $tree = Get-Tree $p.Id
        $sum = @{ shell = 0.0; webview = 0.0; core = 0.0 }
        foreach ($t in $tree) {
            $g = Get-Group $t.Name
            $sum[$g] += $t.WorkingSetSize / 1MB
            $procPeak["$($t.ProcessId)"] = @{ group = $g; mb = $t.PeakWorkingSetSize / 1KB }
        }
        foreach ($g in 'shell', 'webview', 'core') { if ($sum[$g] -gt $peakSum[$g]) { $peakSum[$g] = $sum[$g] } }
        $total = $sum.shell + $sum.webview + $sum.core
        if ($total -gt $peakSum.total) { $peakSum.total = $total }
        Start-Sleep -Milliseconds $IntervalMs
    }
    $p.WaitForExit()
    $sw.Stop()
    $own = @{ shell = 0.0; webview = 0.0; core = 0.0 }
    foreach ($v in $procPeak.Values) { $own[$v.group] += $v.mb }
    $r = [ordered]@{ exit = $p.ExitCode; wall_s = [math]::Round($sw.Elapsed.TotalSeconds, 2); sampled_peak_mb = [ordered]@{}; process_peak_sum_mb = [ordered]@{} }
    foreach ($g in 'shell', 'webview', 'core', 'total') { $r.sampled_peak_mb[$g] = [math]::Round($peakSum[$g], 1) }
    foreach ($g in 'shell', 'webview', 'core') { $r.process_peak_sum_mb[$g] = [math]::Round($own[$g], 1) }
    return $r
}

function Read-Outcome([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return [ordered]@{ present = $false } }
    $j = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($j.PSObject.Properties.Name -contains 'result') { $j = $j.result }  # RepairResult wraps the schedule
    $tiers = $null; $optimal = $null
    if ($j.PSObject.Properties.Name -contains 'quality' -and $null -ne $j.quality) {
        $tiers = @($j.quality.score.tiers); $optimal = @($j.quality.optimal_prefix)
    }
    return [ordered]@{ present = $true; status = $j.status; valid_schedule = $j.valid_schedule; tiers = $tiers; optimal_prefix = $optimal }
}

function Get-SizeMB([string]$Path, [string]$Filter = '*') {
    $sum = (Get-ChildItem -LiteralPath $Path -Recurse -File -Force -Filter $Filter -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sum) { $sum = 0 }
    return [math]::Round($sum / 1MB, 1)
}

function Get-InstalledBreakdown([string]$Dir) {
    $core = Join-Path $Dir 'core'
    $r = [ordered]@{ total_mb = (Get-SizeMB $Dir); core_mb = (Get-SizeMB $core) }
    $r.shell_mb = [math]::Round($r.total_mb - $r.core_mb, 1)
    $internal = Join-Path $core '_internal'
    if (Test-Path $internal) {
        $items = Get-ChildItem -LiteralPath $internal -Force
        $part = [ordered]@{ ortools = 0.0; numpy = 0.0; pandas = 0.0; python = 0.0; other = 0.0 }
        foreach ($i in $items) {
            if ($i.PSIsContainer) { $mb = Get-SizeMB $i.FullName } else { $mb = [math]::Round($i.Length / 1MB, 1) }
            if ($i.Name -match '^ortools') { $part.ortools += $mb }
            elseif ($i.Name -match '^numpy') { $part.numpy += $mb }
            elseif ($i.Name -match '^pandas') { $part.pandas += $mb }
            elseif ($i.Name -match '^(python3\d*\.dll|base_library\.zip|lib-dynload|vcruntime|_.*\.pyd)') { $part.python += $mb }
            else { $part.other += $mb }
        }
        foreach ($k in @($part.Keys)) { $part[$k] = [math]::Round($part[$k], 1) }
        $r.core_internal_mb = $part
    }
    return $r
}

function Stop-Tree([int]$ProcessId) { $ErrorActionPreference = 'Continue'; & taskkill.exe /PID $ProcessId /T /F 2>&1 | Out-Null }

function New-Cases([string]$OutDir, [string]$Tag) {
    $common = @('--workers', "$Workers", '--time-limit', "$TimeLimit", '--seed', '42')
    return @(
        [ordered]@{ name = 'TR38-solve'; kind = 'solve'; input = $In38; output = (Join-Path $OutDir "TR38-$Tag.json")
            args = @('solve', $In38, '--output', (Join-Path $OutDir "TR38-$Tag.json")) + $common },
        [ordered]@{ name = 'TR13-solve'; kind = 'solve'; input = $In13; output = (Join-Path $OutDir "TR13-$Tag.json")
            args = @('solve', $In13, '--output', (Join-Path $OutDir "TR13-$Tag.json")) + $common },
        [ordered]@{ name = 'TR13-repair'; kind = 'repair'; input = $RepIn; output = (Join-Path $OutDir "TR13-repair-$Tag.json")
            args = @('repair', $RepIn, $RepPrev, '--request', $RepReq, '--output', (Join-Path $OutDir "TR13-repair-$Tag.json")) + $common }
    )
}

function Test-Output([string]$CoreExe, $Case) {
    $ErrorActionPreference = 'Continue'
    if ($Case.kind -eq 'solve') { & $CoreExe validate-schedule $Case.input $Case.output 2>&1 | Out-Null }
    else { & $CoreExe evaluate-repair $Case.input $RepPrev $Case.output 2>&1 | Out-Null }
    return $LASTEXITCODE
}

# Machine
$os = Get-CimInstance Win32_OperatingSystem
$cpu = @(Get-CimInstance Win32_Processor)[0]
$wv = $null
foreach ($key in 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
    'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}') {
    if (-not $wv -and (Test-Path $key)) { $wv = (Get-ItemProperty $key).pv }
}
$result = [ordered]@{
    started_at = $StartedAt.ToString('o')
    machine = [ordered]@{ computer = $env:COMPUTERNAME; os = $os.Caption; version = $os.Version; build = $os.BuildNumber
        cpu = $cpu.Name.Trim(); cores = $cpu.NumberOfCores; threads = $cpu.NumberOfLogicalProcessors
        ram_gb = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1); webview2 = $wv; power_plan = ((powercfg /getactivescheme) -join ' ') }
    layout = 'one job at a time; Core uses --workers ' + $Workers + ' --time-limit ' + $TimeLimit
    build_info = $null; variants = @(); source_cli = $null; defender = $null
}
$bi = Join-Path $Spike 'out\build-info.json'
if (Test-Path $bi) { $result.build_info = Get-Content $bi -Raw -Encoding UTF8 | ConvertFrom-Json }

foreach ($v in $Variants) {
    Write-Host "=== $v"
    $vr = [ordered]@{ variant = $v }
    $setup = @(Get-ChildItem (Join-Path $Spike "out\$v") -Filter '*-setup.exe')[0]
    $msi = @(Get-ChildItem (Join-Path $Spike "out\$v") -Filter '*.msi')
    $vr.installer_mb = [ordered]@{ nsis = [math]::Round($setup.Length / 1MB, 1) }
    if ($msi.Count -gt 0) { $vr.installer_mb.msi = [math]::Round($msi[0].Length / 1MB, 1) }

    $dir = Join-Path $env:LOCALAPPDATA "tkb-spike-$v"
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Start-Process -FilePath $setup.FullName -ArgumentList "/S /D=$dir" -Wait
    $vr.install_s = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    $app = @(Get-ChildItem -LiteralPath $dir -Filter '*.exe' | Where-Object { $_.Name -notmatch 'uninstall' })[0].FullName
    $coreExe = Join-Path $dir 'core\tkb-core.exe'
    $vr.installed = Get-InstalledBreakdown $dir

    $ErrorActionPreference = 'Continue'
    $vr.self_check = (& $coreExe self-check 2>&1 | Out-String).Trim()
    $times = @()
    for ($i = 0; $i -lt 5; $i++) {
        $t = Measure-Command { & $coreExe validate-input $In38 2>&1 | Out-Null }
        $times += $t.TotalMilliseconds
    }
    $ErrorActionPreference = 'Stop'
    $vr.startup_validate_input_ms = [ordered]@{ runs = @($times | ForEach-Object { [math]::Round($_) }); median = [math]::Round(($times | Sort-Object)[2]) }

    $out = Join-Path $Work $v
    New-Item -ItemType Directory -Force $out | Out-Null
    $runs = @()
    foreach ($pair in @(@{ via = 'direct'; cases = (New-Cases $out "$v-direct") }, @{ via = 'app'; cases = (New-Cases $out "$v-app") })) {
        foreach ($case in $pair.cases) {
            Write-Host "  $($pair.via) $($case.name)"
            if ($pair.via -eq 'direct') { $w = Watch-Run $coreExe $case.args }
            else {
                $auto = Join-Path $out "$($case.name)-$v-app-run.json"
                $w = Watch-Run $app (@('--auto', $auto, '--') + $case.args) -ShowWindow
                if (Test-Path $auto) { $w.app_run = Get-Content $auto -Raw -Encoding UTF8 | ConvertFrom-Json }
            }
            $w.via = $pair.via; $w.case = $case.name
            $w.outcome = Read-Outcome $case.output
            $w.independent_check_exit = Test-Output $coreExe $case
            $runs += $w
        }
    }
    $vr.runs = $runs
    $vr.same_as_direct = @(foreach ($name in 'TR38-solve', 'TR13-solve', 'TR13-repair') {
            $d = @($runs | Where-Object { $_.case -eq $name -and $_.via -eq 'direct' })[0]
            $a = @($runs | Where-Object { $_.case -eq $name -and $_.via -eq 'app' })[0]
            [ordered]@{ case = $name; same_status = ($d.outcome.status -eq $a.outcome.status)
                same_tiers = ((@($d.outcome.tiers) -join ',') -eq (@($a.outcome.tiers) -join ','))
                direct = $d.outcome; app = $a.outcome }
        })

    Write-Host '  idle'
    $p = Start-Process -FilePath $app -PassThru
    Start-Sleep -Seconds ([math]::Max(0, $IdleSeconds - 10))
    $samples = @()
    for ($i = 0; $i -lt 10; $i++) {
        $s = @{ shell = 0.0; webview = 0.0; core = 0.0 }
        foreach ($t in (Get-Tree $p.Id)) { $s[(Get-Group $t.Name)] += $t.WorkingSetSize / 1MB }
        $samples += , $s
        Start-Sleep -Seconds 1
    }
    Stop-Tree $p.Id
    $vr.idle_mb = [ordered]@{}
    foreach ($g in 'shell', 'webview') {
        $vals = @($samples | ForEach-Object { $_[$g] })
        $vr.idle_mb[$g] = [ordered]@{ mean = [math]::Round(($vals | Measure-Object -Average).Average, 1); max = [math]::Round(($vals | Measure-Object -Maximum).Maximum, 1) }
    }
    $tot = @($samples | ForEach-Object { $_.shell + $_.webview })
    $vr.idle_mb.total_mean = [math]::Round(($tot | Measure-Object -Average).Average, 1)

    Write-Host '  vietnamese path with spaces'
    $vn = Join-Path $env:TEMP 'Thử nghiệm TKB'
    New-Item -ItemType Directory -Force $vn | Out-Null
    $vnIn = Join-Path $vn 'đầu vào.json'
    $vnOut = Join-Path $vn "kết quả $v.json"
    Copy-Item -LiteralPath $In38 -Destination $vnIn -Force
    $auto = Join-Path $vn "chạy $v.json"
    $w = Watch-Run $app @('--auto', $auto, '--', 'solve', $vnIn, '--output', $vnOut, '--workers', "$Workers", '--time-limit', '30', '--seed', '42') -ShowWindow
    $w.outcome = Read-Outcome $vnOut
    if (Test-Path -LiteralPath $auto) { $w.app_run = Get-Content -LiteralPath $auto -Raw -Encoding UTF8 | ConvertFrom-Json }
    $vr.vietnamese_path = $w

    Write-Host '  cancel after 5 s'
    $auto = Join-Path $out "cancel-$v.json"
    $cancelOut = Join-Path $out "cancel-$v-out.json"
    $w = Watch-Run $app @('--auto', $auto, '--cancel-after', '5', '--', 'solve', $In13, '--output', $cancelOut, '--workers', "$Workers", '--time-limit', "$TimeLimit", '--seed', '42') -ShowWindow
    Start-Sleep -Seconds 2
    $left = @(Get-CimInstance Win32_Process -Filter "Name='tkb-core.exe'" | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($dir) })
    $w.core_processes_left = $left.Count
    if (Test-Path $auto) { $w.app_run = Get-Content $auto -Raw -Encoding UTF8 | ConvertFrom-Json }
    $vr.cancel = $w

    Start-Process -FilePath (Join-Path $dir 'uninstall.exe') -ArgumentList '/S' -Wait
    Start-Sleep -Seconds 3
    $vr.uninstalled = -not (Test-Path (Join-Path $dir 'core'))
    $result.variants += $vr
}

if ($Repo) {
    Write-Host '=== source CLI (uv run)'
    $src = Join-Path $Work 'source'
    New-Item -ItemType Directory -Force $src | Out-Null
    $uv = (Get-Command uv).Source
    $sr = @()
    Push-Location $Repo
    foreach ($case in (New-Cases $src 'source')) {
        Write-Host "  $($case.name)"
        $w = Watch-Run $uv (@('run', '--extra', 'solver', 'tkb-core') + $case.args)
        $w.case = $case.name
        $w.outcome = Read-Outcome $case.output
        $sr += $w
    }
    Pop-Location
    $result.source_cli = $sr
}

try {
    $result.defender = @(Get-MpThreatDetection -ErrorAction Stop | Where-Object { $_.InitialDetectionTime -ge $StartedAt } |
        ForEach-Object { [ordered]@{ resources = $_.Resources; time = $_.InitialDetectionTime.ToString('o') } })
} catch { $result.defender = "unavailable: $($_.Exception.Message)" }

$result.finished_at = (Get-Date).ToString('o')
$file = Join-Path $Results "results-$env:COMPUTERNAME.json"
$result | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $file
Write-Host "Done: $file"
