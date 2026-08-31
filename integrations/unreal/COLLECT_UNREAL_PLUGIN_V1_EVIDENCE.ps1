param(
    [Parameter(Mandatory = $true)]
    [string]$UnrealLog,

    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$LogPath = (Resolve-Path $UnrealLog).Path
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path (Split-Path -Parent $LogPath) "OPENRECOMP_UNREAL_PLUGIN_V1_PUBLIC_SAFE.txt"
}

$Expected = "OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866"
$Pattern = 'OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_PASS module=[A-Za-z0-9._-]+ arch=[A-Za-z0-9._-]+ observed_state=[0-9]+ checksum=[0-9]+ operations=[0-9]+'
$Text = Get-Content -LiteralPath $LogPath -Raw
$Matches = [regex]::Matches($Text, $Pattern) | ForEach-Object { $_.Value } | Select-Object -Unique

if ($Matches.Count -ne 1) {
    throw "Expected exactly one unique OpenRecomp packaged PASS marker; found $($Matches.Count)"
}
if ($Matches[0] -ne $Expected) {
    throw "OpenRecomp packaged PASS marker does not match the expected bounded result"
}

$Forbidden = @(
    "AUTH_PASSWORD",
    "AUTH_LOGIN",
    "exchangecode",
    "epicusername",
    "epicuserid",
    "loginid",
    "BEGIN PRIVATE KEY"
)
foreach ($Token in $Forbidden) {
    if ($Matches[0].IndexOf($Token, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
        throw "Forbidden marker survived public evidence extraction"
    }
}

$Matches[0] | Set-Content -LiteralPath $OutputPath -Encoding ASCII
Write-Output "OPENRECOMP_UNREAL_PLUGIN_V1_PUBLIC_SAFE=PASS"
Write-Output "EVIDENCE=$OutputPath"
