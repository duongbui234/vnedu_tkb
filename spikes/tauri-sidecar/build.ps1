<#
.SYNOPSIS
  Build the Tauri 2 sidecar spike on Windows 10/11.
.DESCRIPTION
  1. Packages Scheduling Core with PyInstaller twice: --onedir and --onefile. Each build runs
     `tkb-core self-check`; if the slim build cannot import the solver, it is rebuilt with
     --collect-all ortools and the fallback is recorded.
  2. Builds one Tauri installer (NSIS .exe and MSI) per Core variant, with that variant staged
     as the bundle resource `core/`.
  Output: out\<variant>\ (installers) and out\build-info.json.
#>
param(
    [string]$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [string]$PyInstallerVersion = '6.16.0'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2

$Spike = $PSScriptRoot
$Build = Join-Path $Spike 'build'
$Out = Join-Path $Spike 'out'
New-Item -ItemType Directory -Force $Build, $Out | Out-Null

foreach ($tool in 'uv', 'cargo', 'rustc', 'node', 'npm') {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Missing tool: $tool (see README.md)" }
}

function Invoke-Native([string]$What, [scriptblock]$Block) {
    & $Block
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit $LASTEXITCODE)" }
}

function Get-DirSizeMB([string]$Path) {
    $sum = (Get-ChildItem -LiteralPath $Path -Recurse -File -Force | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sum) { $sum = 0 }
    return [math]::Round($sum / 1MB, 1)
}

function Build-Core([string]$Mode, [bool]$CollectAll) {
    $dist = Join-Path $Build "core-$Mode"
    $work = Join-Path $Build "work-$Mode"
    foreach ($d in $dist, $work) { if (Test-Path $d) { Remove-Item -Recurse -Force $d } }
    $pyArgs = @('run', '--extra', 'solver', '--with', "pyinstaller==$PyInstallerVersion", 'pyinstaller',
        '--noconfirm', '--clean', '--log-level', 'WARN', '--name', 'tkb-core', "--$Mode",
        '--copy-metadata', 'ortools', '--copy-metadata', 'pydantic',
        '--distpath', $dist, '--workpath', $work, '--specpath', $work)
    if ($CollectAll) { $pyArgs += @('--collect-all', 'ortools') }
    $pyArgs += (Join-Path $Spike 'core\pyinstaller_entry.py')
    Invoke-Native "PyInstaller --$Mode" { & uv @pyArgs }
    if ($Mode -eq 'onedir') { $exe = Join-Path $dist 'tkb-core\tkb-core.exe' } else { $exe = Join-Path $dist 'tkb-core.exe' }
    # PowerShell 5.1 turns redirected native stderr into errors under 'Stop'; keep it as text here.
    $ErrorActionPreference = 'Continue'
    $check = (& $exe self-check 2>&1 | Out-String).Trim()
    return [ordered]@{ mode = $Mode; collect_all = $CollectAll; self_check_ok = ($LASTEXITCODE -eq 0);
        self_check = $check; exe = $exe; size_mb = $(if ($Mode -eq 'onedir') { Get-DirSizeMB (Split-Path $exe) } else { [math]::Round((Get-Item $exe).Length / 1MB, 1) }) }
}

# 1. Core
Push-Location $Repo
try {
    Invoke-Native 'uv sync' { uv sync --locked --extra solver }
    $cores = @()
    foreach ($mode in 'onedir', 'onefile') {
        $core = Build-Core $mode $false
        if (-not $core.self_check_ok) {
            Write-Warning "Slim $mode build failed self-check; rebuilding with --collect-all ortools"
            $core = Build-Core $mode $true
        }
        if (-not $core.self_check_ok) { throw "tkb-core $mode self-check failed:`n$($core.self_check)" }
        $cores += $core
    }
} finally { Pop-Location }

# 2. Tauri, once per Core variant
Push-Location $Spike
try {
    Invoke-Native 'npm install' { npm install --no-fund --no-audit }
    Invoke-Native 'tauri icon' { npx tauri icon app-icon.png }
    $staged = Join-Path $Spike 'src-tauri\core'
    $bundles = @()
    foreach ($core in $cores) {
        if (Test-Path $staged) { Remove-Item -Recurse -Force $staged }
        New-Item -ItemType Directory -Force $staged | Out-Null
        if ($core.mode -eq 'onedir') { Copy-Item -Recurse -Force (Join-Path (Split-Path $core.exe) '*') $staged }
        else { Copy-Item -Force $core.exe $staged }
        Invoke-Native "tauri build ($($core.mode))" { npx tauri build }
        $dest = Join-Path $Out $core.mode
        if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
        New-Item -ItemType Directory -Force $dest | Out-Null
        $bundleDir = Join-Path $Spike 'src-tauri\target\release\bundle'
        Get-ChildItem (Join-Path $bundleDir 'nsis\*.exe'), (Join-Path $bundleDir 'msi\*.msi') | Copy-Item -Destination $dest
        $bundles += [ordered]@{ variant = $core.mode; files = @(Get-ChildItem $dest | ForEach-Object { [ordered]@{ name = $_.Name; size_mb = [math]::Round($_.Length / 1MB, 1) } }) }
    }
    Push-Location (Join-Path $Spike 'src-tauri')
    $tauriCrate = & { $ErrorActionPreference = 'Continue'; cargo tree -p tauri --depth 0 2>$null | Select-Object -First 1 }
    Pop-Location
    $info = [ordered]@{
        built_at = (Get-Date).ToString('o'); repo = $Repo
        repo_commit = (git -C $Repo rev-parse --short HEAD); repo_dirty = [bool](git -C $Repo status --porcelain -- src spikes)
        rustc = (rustc --version); node = (node --version); tauri_cli = (npx tauri --version); tauri_crate = $tauriCrate
        pyinstaller = $PyInstallerVersion; cores = $cores; bundles = $bundles
    }
    $info | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 (Join-Path $Out 'build-info.json')
    Write-Host "Done. Installers in $Out; details in out\build-info.json"
} finally { Pop-Location }
