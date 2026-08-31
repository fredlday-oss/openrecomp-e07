param(
    [Parameter(Mandatory = $true)]
    [string]$UnrealLog,

    [string]$OutputDirectory = ".\OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1_EVIDENCE"
)

$ErrorActionPreference = "Stop"

$LogPath = (Resolve-Path $UnrealLog).Path
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputPath = Join-Path $OutputDirectory "OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1_PUBLIC_SAFE.txt"

$Raw = Get-Content -LiteralPath $LogPath
$Allowed = $Raw | Where-Object {
    $_ -match "OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 (PASS|FAIL)" -or
    $_ -match "OPENRECOMP_GATE_B (PASS|FAIL)" -or
    $_ -match "OPENRECOMP_DEMO (PASS|FAIL)"
}

$Safe = foreach ($Line in $Allowed) {
    if ($Line -match "OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 (PASS|FAIL).*" ) {
        $Matches[0]
    } elseif ($Line -match "OPENRECOMP_GATE_B (PASS|FAIL).*" ) {
        $Matches[0]
    } elseif ($Line -match "OPENRECOMP_DEMO (PASS|FAIL).*" ) {
        $Matches[0]
    }
}

$Forbidden = @(
    "AUTH_PASSWORD",
    "AUTH_LOGIN",
    "AUTH_TYPE",
    "exchangecode",
    "epicusername",
    "epicuserid",
    "loginid",
    "access_token",
    "refresh_token",
    "Bearer "
)

$Joined = ($Safe -join "`n")
foreach ($Term in $Forbidden) {
    if ($Joined.IndexOf($Term, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
        throw "Public-safe evidence contains a forbidden authentication/account marker"
    }
}

if ($Joined -notmatch "OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1 PASS") {
    throw "Required Native AOT Unreal PASS marker was not found"
}

$Safe | Set-Content -LiteralPath $OutputPath -Encoding ascii

Write-Output "OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1_PUBLIC_SAFE=PASS"
Write-Output "EVIDENCE=$OutputPath"
