param(
    [Parameter(Mandatory = $true)][string]$Repository,
    [string]$PacketRoot = $PSScriptRoot
)

$ErrorActionPreference = "Stop"
if ($env:OS -ne "Windows_NT") { throw "Native Windows is required" }
$PacketRoot = (Resolve-Path -LiteralPath $PacketRoot).Path
$Repository = (Resolve-Path -LiteralPath $Repository).Path
$SourceRoot = Join-Path $PacketRoot "source"
$EvidenceRoot = Join-Path $PacketRoot "evidence"

function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed ($LASTEXITCODE): $Exe $($Arguments -join ' ')"
    }
}

# Verify the transported bytes before creating a worktree or executing its tooling.
$Inventory = Get-Content -Raw -LiteralPath (Join-Path $PacketRoot "inventory.json") | ConvertFrom-Json
if ($Inventory.schema_version -ne "1.0") { throw "Unsupported packet schema" }
foreach ($Row in $Inventory.files) {
    $File = [IO.Path]::GetFullPath((Join-Path $PacketRoot $Row.path))
    if (-not $File.StartsWith($PacketRoot + [IO.Path]::DirectorySeparatorChar,
                              [StringComparison]::OrdinalIgnoreCase)) {
        throw "Packet path escapes root"
    }
    if ((Get-Item -LiteralPath $File).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Packet contains a reparse point"
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $File).Hash.ToLowerInvariant() -ne $Row.sha256) {
        throw "Packet hash mismatch: $($Row.path)"
    }
}
if ((Test-Path -LiteralPath $SourceRoot) -or (Test-Path -LiteralPath $EvidenceRoot)) {
    throw "Fresh source/evidence directories required; no implicit resume or retry"
}

# Use local Git objects with LF bytes; keep the user's existing checkout intact.
Invoke-Checked -Exe "git" -Arguments @("-C", $Repository, "cat-file", "-e", "$($Inventory.base_commit)^{commit}")
Invoke-Checked -Exe "git" -Arguments @("-C", $Repository, "-c", "core.autocrlf=false", "worktree", "add", "--detach", $SourceRoot, $Inventory.base_commit)
Invoke-Checked -Exe "git" -Arguments @("-C", $SourceRoot, "-c", "core.autocrlf=false", "apply", "--check", (Join-Path $PacketRoot "changes.patch"))
Invoke-Checked -Exe "git" -Arguments @("-C", $SourceRoot, "-c", "core.autocrlf=false", "apply", (Join-Path $PacketRoot "changes.patch"))

New-Item -ItemType Directory -Path $EvidenceRoot | Out-Null
@{
    schema_version = "1.0"
    started_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    base_commit = $Inventory.base_commit
    wheel_sha256 = $Inventory.wheel_sha256
} | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $EvidenceRoot "run-start.json")
Start-Transcript -Path (Join-Path $EvidenceRoot "session.txt") | Out-Null
$Preflight = Join-Path $EvidenceRoot "preflight"
$Campaign = Join-Path $EvidenceRoot "campaign"
$Bundle = Join-Path $PacketRoot "bundle"
$Wheel = Join-Path $PacketRoot "wheel/vnedu_tkb_core-0.2.0-py3-none-any.whl"
$Plan = Join-Path $Campaign "plan.json"
$Launcher = "import sys;sys.path.insert(0,sys.argv.pop(1));from benchmarks.run_benchmarks import main;raise SystemExit(main())"

Push-Location $SourceRoot
try {
    Invoke-Checked -Exe "uv" -Arguments @("sync", "--locked", "--extra", "solver")
    Invoke-Checked -Exe "uv" -Arguments @(
        "run", "python", "-m", "benchmarks.phase2a_preflight", "setup",
        "--output", $Preflight, "--bundle", $Bundle,
        "--wheel", $Wheel, "--wheel-sha256", $Inventory.wheel_sha256
    )
    $Python = Join-Path $Preflight "venv-solver/Scripts/python.exe"
    Invoke-Checked -Exe $Python -Arguments @(
        "-I", "-c", $Launcher, $SourceRoot, "--phase", "prepare",
        "--bundle", $Bundle, "--preflight-dir", $Preflight, "--output", $Campaign,
        "--campaign-id", "current-windows-20261103-v2", "--machine-id", "windows-native-01"
    )
    foreach ($Phase in @("warmup", "pilot", "primary")) {
        Write-Host "PHASE $Phase (sequential; stop on safety/correctness or prerequisite failure)"
        Invoke-Checked -Exe $Python -Arguments @(
            "-I", "-c", $Launcher, $SourceRoot, "--phase", $Phase,
            "--plan", $Plan, "--preflight-dir", $Preflight
        )
    }
    $Aggregator = "import sys;sys.path.insert(0,sys.argv.pop(1));from benchmarks.aggregate_linux import main;raise SystemExit(main())"
    Invoke-Checked -Exe $Python -Arguments @(
        "-I", "-c", $Aggregator, $SourceRoot, $Campaign,
        "--output", (Join-Path $EvidenceRoot "summary.json")
    )
    $Summary = Get-Content -Raw -LiteralPath (Join-Path $EvidenceRoot "summary.json") | ConvertFrom-Json
    Write-Host "Correctness: $($Summary.summary.correctness_verdict)"
    Write-Host "Performance: $($Summary.summary.performance_verdict)"
    Write-Host "Cross-OS acceptance still requires Linux evidence and exchanged-result validation."
}
finally {
    Pop-Location
    Stop-Transcript | Out-Null
    # Return raw evidence even on failure, excluding installed venvs and caches.
    $ReturnRoot = Join-Path $PacketRoot "evidence-to-return"
    New-Item -ItemType Directory -Path $ReturnRoot | Out-Null
    foreach ($File in Get-ChildItem -LiteralPath $EvidenceRoot -Recurse -File) {
        $Relative = $File.FullName.Substring($EvidenceRoot.Length + 1)
        if ($Relative -match '(^|[\\/])(venv-solver|venv-no-solver|__pycache__)([\\/]|$)') { continue }
        $Target = Join-Path $ReturnRoot $Relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
        Copy-Item -LiteralPath $File.FullName -Destination $Target
    }
    Compress-Archive -LiteralPath $ReturnRoot -DestinationPath (Join-Path $PacketRoot "windows-evidence.zip")
    Write-Host "Return: $(Join-Path $PacketRoot 'windows-evidence.zip')"
    Write-Host "No commit, merge, push, worktree deletion or retry was performed."
}
