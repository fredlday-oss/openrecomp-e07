param(
    [Parameter(Mandatory = $true)]
    [string]$UnrealProjectRoot,

    [Parameter(Mandatory = $true)]
    [string]$UnrealEngineRoot,

    [string]$NativeModuleDll = (Join-Path $PSScriptRoot "openrecomp-e07-rv32i.dll"),

    [string]$ResultZip
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Installer = Join-Path $PSScriptRoot "INSTALL_UNREAL_PLUGIN_V1.ps1"
$PackagedProof = Join-Path $PSScriptRoot "RUN_UNREAL_PLUGIN_V1_PACKAGED_PROOF.ps1"

if (-not (Test-Path $Installer -PathType Leaf)) {
    throw "OpenRecomp plugin installer is missing: $Installer"
}
if (-not (Test-Path $PackagedProof -PathType Leaf)) {
    throw "OpenRecomp packaged proof runner is missing: $PackagedProof"
}
if (-not (Test-Path $NativeModuleDll -PathType Leaf)) {
    throw "OpenRecomp synthetic Native AOT DLL is missing: $NativeModuleDll"
}

# These are PowerShell scripts, not native executables. Both scripts use
# terminating errors and therefore fail closed under StrictMode without
# consulting a native-process exit-code variable.
& $Installer `
    -UnrealProjectRoot $UnrealProjectRoot `
    -NativeModuleDll $NativeModuleDll

$ProofArgs = @{
    UnrealProjectRoot = $UnrealProjectRoot
    UnrealEngineRoot = $UnrealEngineRoot
}
if (-not [string]::IsNullOrWhiteSpace($ResultZip)) {
    $ProofArgs.ResultZip = $ResultZip
}

& $PackagedProof @ProofArgs

Write-Output "OPENRECOMP_UNREAL_PLUGIN_V1_HANDOFF_RUN=COMPLETE"
