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

$ExpectedPass = "OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866"
$PassPattern = 'OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_PASS module=[A-Za-z0-9._-]+ arch=[A-Za-z0-9._-]+ observed_state=[0-9]+ checksum=[0-9]+ operations=[0-9]+'
$DiagnosticPattern = 'OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_FAIL stage=validate metadata=[01] execution=[01] observed_state=-?[0-9]+ has_return=[01] function_return=-?[0-9]+ operations=-?[0-9]+ checksum=[0-9]+ callbacks=[01] tick=[0-9]+ graphics=[0-9]+ audio=[0-9]+ input=[0-9]+ system=[0-9]+'

$Text = Get-Content -LiteralPath $LogPath -Raw
$PassMatches = @([regex]::Matches($Text, $PassPattern) | ForEach-Object { $_.Value } | Select-Object -Unique)
$DiagnosticMatches = @([regex]::Matches($Text, $DiagnosticPattern) | ForEach-Object { $_.Value } | Select-Object -Unique)
$Matches = @($PassMatches + $DiagnosticMatches | Select-Object -Unique)

if ($Matches.Count -ne 1) {
    throw "Expected exactly one unique OpenRecomp packaged PASS or safe validation diagnostic marker; found $($Matches.Count)"
}

$Marker = $Matches[0]
if ($Marker -match '^OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_PASS ' -and $Marker -ne $ExpectedPass) {
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
    if ($Marker.IndexOf($Token, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
        throw "Forbidden marker survived public evidence extraction"
    }
}

$Marker | Set-Content -LiteralPath $OutputPath -Encoding ASCII
if ($Marker -match '^OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_PASS ') {
    Write-Output "OPENRECOMP_UNREAL_PLUGIN_V1_PUBLIC_SAFE=PASS"
} else {
    Write-Output "OPENRECOMP_UNREAL_PLUGIN_V1_PUBLIC_SAFE=DIAGNOSTIC"
}
Write-Output "EVIDENCE=$OutputPath"
