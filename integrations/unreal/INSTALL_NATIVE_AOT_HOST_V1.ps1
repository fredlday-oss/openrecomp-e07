param(
    [Parameter(Mandatory = $true)]
    [string]$UnrealProjectRoot,

    [string]$NativeModuleDll = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$ProjectRoot = (Resolve-Path $UnrealProjectRoot).Path
$ModuleRoot = Join-Path $ProjectRoot "Source\OpenRecompHost"
$PublicDir = Join-Path $ModuleRoot "Public"
$PrivateDir = Join-Path $ModuleRoot "Private"

if (-not (Test-Path $PublicDir) -or -not (Test-Path $PrivateDir)) {
    throw "Expected Unreal module directories are missing under $ModuleRoot"
}

$AbiDir = Join-Path $PublicDir "openrecomp"
New-Item -ItemType Directory -Force -Path $AbiDir | Out-Null

$Copies = @(
    @((Join-Path $RepoRoot "include\openrecomp\native_aot_abi_v1.h"), (Join-Path $AbiDir "native_aot_abi_v1.h")),
    @((Join-Path $PSScriptRoot "OpenRecompNativeAotHostCoreV1.h"), (Join-Path $PublicDir "OpenRecompNativeAotHostCoreV1.h")),
    @((Join-Path $PSScriptRoot "OpenRecompNativeAotHostV1.h"), (Join-Path $PublicDir "OpenRecompNativeAotHostV1.h")),
    @((Join-Path $PSScriptRoot "OpenRecompNativeAotHostActor.h"), (Join-Path $PublicDir "OpenRecompNativeAotHostActor.h")),
    @((Join-Path $PSScriptRoot "OpenRecompNativeAotHostCoreV1.cpp"), (Join-Path $PrivateDir "OpenRecompNativeAotHostCoreV1.cpp")),
    @((Join-Path $PSScriptRoot "OpenRecompNativeAotHostV1.cpp"), (Join-Path $PrivateDir "OpenRecompNativeAotHostV1.cpp")),
    @((Join-Path $PSScriptRoot "OpenRecompNativeAotHostActor.cpp"), (Join-Path $PrivateDir "OpenRecompNativeAotHostActor.cpp"))
)

foreach ($Pair in $Copies) {
    $Source = $Pair[0]
    $Destination = $Pair[1]
    if (-not (Test-Path $Source)) {
        throw "Required source file missing: $Source"
    }
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

$InstalledDll = ""
if ($NativeModuleDll) {
    $ResolvedDll = (Resolve-Path $NativeModuleDll).Path
    $BinariesDir = Join-Path $ProjectRoot "Binaries\Win64"
    New-Item -ItemType Directory -Force -Path $BinariesDir | Out-Null
    $InstalledDll = Join-Path $BinariesDir "openrecomp-e07-rv32i.dll"
    Copy-Item -LiteralPath $ResolvedDll -Destination $InstalledDll -Force
}

$ManifestDir = Join-Path $ProjectRoot "Saved\OpenRecompNativeAotHostV1"
New-Item -ItemType Directory -Force -Path $ManifestDir | Out-Null
$Manifest = Join-Path $ManifestDir "INSTALL_MANIFEST.txt"

$Lines = @("OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1_INSTALL=PASS")
foreach ($Pair in $Copies) {
    $Destination = $Pair[1]
    $Hash = (Get-FileHash $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
    $Relative = [IO.Path]::GetRelativePath($ProjectRoot, $Destination)
    $Lines += "$Hash  $Relative"
}
if ($InstalledDll) {
    $Hash = (Get-FileHash $InstalledDll -Algorithm SHA256).Hash.ToLowerInvariant()
    $Relative = [IO.Path]::GetRelativePath($ProjectRoot, $InstalledDll)
    $Lines += "$Hash  $Relative"
}
$Lines | Set-Content -LiteralPath $Manifest -Encoding ascii

Write-Output "OPENRECOMP_UNREAL_NATIVE_AOT_HOST_V1_INSTALL=PASS"
Write-Output "PROJECT_ROOT=$ProjectRoot"
Write-Output "MANIFEST=$Manifest"
if ($InstalledDll) {
    Write-Output "MODULE_DLL=$InstalledDll"
} else {
    Write-Output "MODULE_DLL=NOT_INSTALLED"
}
