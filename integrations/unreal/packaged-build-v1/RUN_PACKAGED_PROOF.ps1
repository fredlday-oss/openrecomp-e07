param(
    [Parameter(Mandatory=$true)][string]$ArchiveRoot,
    [int]$TimeoutSeconds = 90
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $ArchiveRoot)) { throw "Archive root not found: $ArchiveRoot" }

$Candidates = @(
    Get-ChildItem -Path $ArchiveRoot -Filter "*.exe" -File -Recurse |
        Where-Object {
            $_.FullName -match '\\Binaries\\Win64\\' -and
            $_.Name -notmatch 'CrashReportClient|UnrealPrereq|BootstrapPackagedGame|ShaderCompileWorker'
        }
)
if ($Candidates.Count -lt 1) {
    throw "Could not find packaged game executable under Binaries\\Win64"
}

$Exe = $Candidates | Sort-Object FullName | Select-Object -First 1
$StdOut = Join-Path $PSScriptRoot "PACKAGED_RUNTIME_STDOUT.txt"
$StdErr = Join-Path $PSScriptRoot "PACKAGED_RUNTIME_STDERR.txt"
Remove-Item -Force -ErrorAction SilentlyContinue $StdOut, $StdErr

$Args = @(
    "-OpenRecompPackagedProof",
    "-stdout",
    "-FullStdOutLogOutput",
    "-log",
    "-unattended",
    "-nullrhi",
    "-nosound",
    "-NoSplash"
)

$Process = Start-Process `
    -FilePath $Exe.FullName `
    -ArgumentList $Args `
    -WorkingDirectory $Exe.DirectoryName `
    -RedirectStandardOutput $StdOut `
    -RedirectStandardError $StdErr `
    -PassThru

$Expected = "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866"
$Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$Passed = $false
try {
    while ((Get-Date) -lt $Deadline) {
        Start-Sleep -Milliseconds 500
        if (Test-Path $StdOut) {
            $Text = Get-Content $StdOut -Raw -ErrorAction SilentlyContinue
            if ($Text -match [regex]::Escape($Expected)) {
                $Passed = $true
                break
            }
            if ($Text -match "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 FAIL") {
                break
            }
        }
        if ($Process.HasExited) {
            break
        }
    }
}
finally {
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
}

if (-not $Passed) {
    throw "Packaged runtime PASS marker not observed within $TimeoutSeconds seconds"
}

$PublicEvidence = Join-Path $PSScriptRoot "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_RUNTIME_PUBLIC_SAFE.txt"
$Collector = Join-Path $PSScriptRoot "COLLECT_PACKAGED_BUILD_V1_EVIDENCE.ps1"
try {
    & $Collector -InputFile $StdOut -OutputFile $PublicEvidence
}
catch {
    throw "Public-safe evidence collection failed: $($_.Exception.Message)"
}

if (-not (Test-Path $PublicEvidence)) {
    throw "Public-safe evidence collection failed: output file was not created"
}
$EvidenceText = Get-Content $PublicEvidence -Raw
if ($EvidenceText -notmatch [regex]::Escape($Expected)) {
    throw "Public-safe evidence collection failed: exact PASS marker missing from extracted evidence"
}

Write-Output $Expected
Write-Output "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_RUNTIME=PASS"
