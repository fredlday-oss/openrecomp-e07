param(
    [Parameter(Mandatory = $true)]
    [string]$LogPath,

    [string]$OutputPath = "evidence\OPENRECOMP_UNREAL_PLUGIN_V1_PUBLIC_SAFE.txt"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $LogPath)) {
    throw "Unreal log does not exist: $LogPath"
}

$AllowedPrefix = "OPENRECOMP_UNREAL_PLUGIN_V1 PASS "
$Lines = Get-Content $LogPath | Where-Object { $_ -like "*$AllowedPrefix*" }
if ($Lines.Count -ne 1) {
    throw "Expected exactly one OPENRECOMP_UNREAL_PLUGIN_V1 PASS line; found $($Lines.Count)"
}

$Line = $Lines[0]
$MarkerIndex = $Line.IndexOf($AllowedPrefix)
if ($MarkerIndex -lt 0) {
    throw "PASS marker prefix not found"
}
$SafeLine = $Line.Substring($MarkerIndex)

$Expected = "OPENRECOMP_UNREAL_PLUGIN_V1 PASS module=e07.rv32i.fixture-full.ir-v1 arch=riscv32-rv32i observed_state=48 checksum=122010428 operations=3866"
if ($SafeLine -ne $Expected) {
    throw "Unexpected plugin runtime marker: $SafeLine"
}

$Forbidden = @(
    "AUTH_PASSWORD",
    "AUTH_LOGIN",
    "exchangecode",
    "epicusername",
    "epicuserid",
    "loginid"
)
foreach ($Token in $Forbidden) {
    if ($SafeLine.IndexOf($Token, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
        throw "Forbidden token survived public-safe extraction: $Token"
    }
}

$Directory = Split-Path -Parent $OutputPath
if ($Directory) {
    New-Item -ItemType Directory -Path $Directory -Force | Out-Null
}
Set-Content -Path $OutputPath -Value $SafeLine -Encoding ascii

Write-Output $SafeLine
Write-Output "OPENRECOMP_UNREAL_PLUGIN_V1_PUBLIC_SAFE=PASS"
Write-Output "OUTPUT=$OutputPath"
