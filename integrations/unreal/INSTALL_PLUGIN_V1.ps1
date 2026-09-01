param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot,

    [switch]$ForceReplace
)

$ErrorActionPreference = "Stop"

$SourcePlugin = Join-Path $PSScriptRoot "Plugins\OpenRecompRuntime"
$DestinationPlugins = Join-Path $ProjectRoot "Plugins"
$DestinationPlugin = Join-Path $DestinationPlugins "OpenRecompRuntime"

if (-not (Test-Path (Join-Path $SourcePlugin "OpenRecompRuntime.uplugin"))) {
    throw "OpenRecompRuntime source plugin is missing: $SourcePlugin"
}
if (-not (Test-Path $ProjectRoot)) {
    throw "Unreal project root does not exist: $ProjectRoot"
}

if (Test-Path $DestinationPlugin) {
    if (-not $ForceReplace) {
        throw "Destination plugin already exists: $DestinationPlugin. Re-run with -ForceReplace to replace it."
    }
    Remove-Item $DestinationPlugin -Recurse -Force
}

New-Item -ItemType Directory -Path $DestinationPlugins -Force | Out-Null
Copy-Item $SourcePlugin $DestinationPlugin -Recurse -Force

$CanonicalAbi = Resolve-Path (Join-Path $PSScriptRoot "..\..\include\openrecomp\native_aot_abi_v1.h")
$InstalledAbi = Join-Path $DestinationPlugin "Source\OpenRecompRuntime\Public\openrecomp\native_aot_abi_v1.h"
if ((Get-FileHash $CanonicalAbi -Algorithm SHA256).Hash -ne (Get-FileHash $InstalledAbi -Algorithm SHA256).Hash) {
    throw "Installed plugin ABI header does not match the canonical Native AOT ABI V1 header"
}

Write-Output "OPENRECOMP_UNREAL_PLUGIN_V1_INSTALL=PASS"
Write-Output "PLUGIN=$DestinationPlugin"
