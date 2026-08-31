param(
    [Parameter(Mandatory = $true)]
    [string]$UnrealProjectRoot,

    [Parameter(Mandatory = $true)]
    [string]$NativeModuleDll
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path $UnrealProjectRoot).Path
$ModuleDll = (Resolve-Path $NativeModuleDll).Path
$SourcePlugin = Join-Path $PSScriptRoot "OpenRecompRuntime"
$TargetPlugins = Join-Path $ProjectRoot "Plugins"
$TargetPlugin = Join-Path $TargetPlugins "OpenRecompRuntime"
$TargetBinaries = Join-Path $TargetPlugin "Binaries\Win64"
$TargetDll = Join-Path $TargetBinaries "openrecomp-e07-rv32i.dll"
$ManifestPath = Join-Path $ProjectRoot "OPENRECOMP_UNREAL_PLUGIN_V1_INSTALL_MANIFEST.txt"

if (-not (Test-Path $SourcePlugin -PathType Container)) {
    throw "OpenRecompRuntime plugin source not found: $SourcePlugin"
}
if (-not (Test-Path $ModuleDll -PathType Leaf)) {
    throw "Native AOT proof DLL not found: $ModuleDll"
}

$ProjectFiles = @(Get-ChildItem -LiteralPath $ProjectRoot -Filter "*.uproject" -File)
if ($ProjectFiles.Count -ne 1) {
    throw "Expected exactly one .uproject at project root; found $($ProjectFiles.Count)"
}
$ProjectFile = $ProjectFiles[0].FullName

New-Item -ItemType Directory -Path $TargetPlugins -Force | Out-Null
if (Test-Path $TargetPlugin) {
    Remove-Item -LiteralPath $TargetPlugin -Recurse -Force
}
Copy-Item -LiteralPath $SourcePlugin -Destination $TargetPlugin -Recurse -Force
New-Item -ItemType Directory -Path $TargetBinaries -Force | Out-Null
Copy-Item -LiteralPath $ModuleDll -Destination $TargetDll -Force

$ProjectJson = Get-Content -LiteralPath $ProjectFile -Raw | ConvertFrom-Json
$Plugins = @()
$PluginsProperty = $ProjectJson.PSObject.Properties["Plugins"]
if ($null -ne $PluginsProperty -and $null -ne $PluginsProperty.Value) {
    $Plugins = @($PluginsProperty.Value)
}

$Existing = @($Plugins | Where-Object {
    $NameProperty = $_.PSObject.Properties["Name"]
    $null -ne $NameProperty -and $NameProperty.Value -eq "OpenRecompRuntime"
})
if ($Existing.Count -gt 1) {
    throw "Project contains duplicate OpenRecompRuntime plugin entries"
}
if ($Existing.Count -eq 1) {
    if ($null -eq $Existing[0].PSObject.Properties["Enabled"]) {
        $Existing[0] | Add-Member -NotePropertyName "Enabled" -NotePropertyValue $true
    } else {
        $Existing[0].Enabled = $true
    }
} else {
    $Plugins += [pscustomobject]@{
        Name = "OpenRecompRuntime"
        Enabled = $true
    }
}
$ProjectJson | Add-Member -NotePropertyName "Plugins" -NotePropertyValue $Plugins -Force
$ProjectJson | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $ProjectFile -Encoding UTF8

$RoundTrip = Get-Content -LiteralPath $ProjectFile -Raw | ConvertFrom-Json
$RoundTripPluginsProperty = $RoundTrip.PSObject.Properties["Plugins"]
if ($null -eq $RoundTripPluginsProperty) {
    throw "Failed to add Plugins array to project descriptor"
}
$EnabledEntries = @($RoundTripPluginsProperty.Value | Where-Object {
    $NameProperty = $_.PSObject.Properties["Name"]
    $EnabledProperty = $_.PSObject.Properties["Enabled"]
    $null -ne $NameProperty -and
        $NameProperty.Value -eq "OpenRecompRuntime" -and
        $null -ne $EnabledProperty -and
        $EnabledProperty.Value -eq $true
})
if ($EnabledEntries.Count -ne 1) {
    throw "Failed to enable OpenRecompRuntime in project descriptor"
}

$ProjectPrefix = $ProjectRoot.TrimEnd('\') + '\'
$ManifestLines = @()
foreach ($File in (Get-ChildItem -LiteralPath $TargetPlugin -File -Recurse | Sort-Object FullName)) {
    $Relative = $File.FullName
    if ($Relative.StartsWith($ProjectPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        $Relative = $Relative.Substring($ProjectPrefix.Length)
    }
    $Hash = (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $ManifestLines += "$Hash  $Relative"
}
$ManifestLines | Set-Content -LiteralPath $ManifestPath -Encoding ASCII

Write-Output "OPENRECOMP_UNREAL_PLUGIN_V1_INSTALL=PASS"
Write-Output "PROJECT=$ProjectFile"
Write-Output "PLUGIN=$TargetPlugin"
Write-Output "NATIVE_MODULE=$TargetDll"
Write-Output "MANIFEST=$ManifestPath"
