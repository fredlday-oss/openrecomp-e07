param(
    [Parameter(Mandatory=$true)][string]$ProjectDir,
    [switch]$ForceReplace
)

$ErrorActionPreference = "Stop"

$SourcePlugin = Join-Path $PSScriptRoot "OpenRecompRuntime"
$Descriptor = Join-Path $SourcePlugin "OpenRecompRuntime.uplugin"
if (-not (Test-Path $Descriptor)) {
    throw "OpenRecompRuntime handoff plugin is missing: $Descriptor"
}

$ProjectPlugins = Join-Path $ProjectDir "Plugins"
$DestinationPlugin = Join-Path $ProjectPlugins "OpenRecompRuntime"

if (Test-Path $DestinationPlugin) {
    if (-not $ForceReplace) {
        throw "Destination plugin already exists. Re-run with -ForceReplace after confirming the target project."
    }
    Remove-Item -Recurse -Force $DestinationPlugin
}

New-Item -ItemType Directory -Force -Path $ProjectPlugins | Out-Null
Copy-Item -Recurse -Force $SourcePlugin $DestinationPlugin

$Manifest = Join-Path $DestinationPlugin "OPENRECOMP_PACKAGED_BUILD_V1_SHA256SUMS.txt"
if (-not (Test-Path $Manifest)) {
    throw "Handoff manifest missing after install"
}

$Dll = Join-Path $DestinationPlugin "Binaries\Win64\openrecomp-e07-rv32i.dll"
if (-not (Test-Path $Dll)) {
    throw "Validated Native AOT DLL missing after install"
}

Write-Output "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_INSTALL=PASS"
