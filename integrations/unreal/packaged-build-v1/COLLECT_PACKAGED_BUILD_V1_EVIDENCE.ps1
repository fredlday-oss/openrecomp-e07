param(
    [Parameter(Mandatory=$true)][string]$InputFile,
    [Parameter(Mandatory=$true)][string]$OutputFile
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $InputFile)) { throw "Input file missing: $InputFile" }

$Text = Get-Content $InputFile -Raw
$Pattern = 'OPENRECOMP_UNREAL_PACKAGED_BUILD_V1 PASS module=e07\.rv32i\.fixture-full\.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866'
$Match = [regex]::Match($Text, $Pattern)
if (-not $Match.Success) {
    throw "Exact packaged-build PASS marker not found"
}

$Output = @(
    "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_RUNTIME_EVIDENCE",
    "Evidence classification: PASS — local packaged runtime evidence",
    "Environment: Unreal Engine 5.8, Windows x64, Development packaged build",
    $Match.Value
) -join "`r`n"
$Output += "`r`n"

$Forbidden = @(
    "AUTH_PASSWORD",
    "AUTH_LOGIN",
    "exchangecode",
    "epicusername",
    "epicuserid",
    "loginid"
)
foreach ($Token in $Forbidden) {
    if ($Output.ToLowerInvariant().Contains($Token.ToLowerInvariant())) {
        throw "Forbidden marker survived public-safe extraction: $Token"
    }
}

$Output | Set-Content -Encoding utf8 $OutputFile
Write-Output "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_PUBLIC_SAFE_EVIDENCE=PASS"
