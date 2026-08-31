param(
    [Parameter(Mandatory = $true)]
    [string]$UnrealProjectRoot,

    [Parameter(Mandatory = $true)]
    [string]$UnrealEngineRoot,

    [string]$ArchiveRoot,

    [string]$ResultZip,

    [int]$TimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path $UnrealProjectRoot).Path
$EngineRoot = (Resolve-Path $UnrealEngineRoot).Path
$ProjectFiles = @(Get-ChildItem -LiteralPath $ProjectRoot -Filter "*.uproject" -File)
if ($ProjectFiles.Count -ne 1) {
    throw "Expected exactly one .uproject at project root; found $($ProjectFiles.Count)"
}
$ProjectFile = $ProjectFiles[0].FullName
$ProjectName = $ProjectFiles[0].BaseName
$EditorTarget = "${ProjectName}Editor"

$PluginRoot = Join-Path $ProjectRoot "Plugins\OpenRecompRuntime"
$InstalledDll = Join-Path $PluginRoot "Binaries\Win64\openrecomp-e07-rv32i.dll"
if (-not (Test-Path (Join-Path $PluginRoot "OpenRecompRuntime.uplugin") -PathType Leaf)) {
    throw "OpenRecompRuntime plugin is not installed in the project"
}
if (-not (Test-Path $InstalledDll -PathType Leaf)) {
    throw "Synthetic Native AOT proof DLL is not installed in plugin Binaries/Win64"
}

$BuildBat = Join-Path $EngineRoot "Engine\Build\BatchFiles\Build.bat"
$RunUat = Join-Path $EngineRoot "Engine\Build\BatchFiles\RunUAT.bat"
if (-not (Test-Path $BuildBat -PathType Leaf)) {
    throw "Unreal Build.bat not found: $BuildBat"
}
if (-not (Test-Path $RunUat -PathType Leaf)) {
    throw "Unreal RunUAT.bat not found: $RunUat"
}

if ([string]::IsNullOrWhiteSpace($ArchiveRoot)) {
    $ArchiveRoot = Join-Path $ProjectRoot "Saved\OpenRecompPluginV1Package"
}
if ([string]::IsNullOrWhiteSpace($ResultZip)) {
    $ResultZip = Join-Path $ProjectRoot "OPENRECOMP_UNREAL_PLUGIN_V1_RUNTIME_RESULT.zip"
}

$ResultRoot = Join-Path $ProjectRoot "OPENRECOMP_UNREAL_PLUGIN_V1_RUNTIME_RESULT"
if (Test-Path $ResultRoot) {
    Remove-Item -LiteralPath $ResultRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $ResultRoot -Force | Out-Null

Write-Output "===== UE5 EDITOR BUILD ====="
& $BuildBat $EditorTarget "Win64" "Development" "-Project=$ProjectFile" "-WaitMutex" "-NoHotReloadFromIDE"
if ($LASTEXITCODE -ne 0) {
    throw "UE5 Editor build failed with exit code $LASTEXITCODE"
}
"OPENRECOMP_UNREAL_PLUGIN_V1_EDITOR_BUILD=PASS" | Set-Content -LiteralPath (Join-Path $ResultRoot "EDITOR_BUILD.txt") -Encoding ASCII

if (Test-Path $ArchiveRoot) {
    Remove-Item -LiteralPath $ArchiveRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $ArchiveRoot -Force | Out-Null

Write-Output "===== UE5 WIN64 PACKAGE ====="
$UatArgs = @(
    "BuildCookRun",
    "-project=$ProjectFile",
    "-noP4",
    "-platform=Win64",
    "-clientconfig=Development",
    "-build",
    "-cook",
    "-stage",
    "-pak",
    "-package",
    "-archive",
    "-archivedirectory=$ArchiveRoot",
    "-utf8output"
)
& $RunUat @UatArgs
if ($LASTEXITCODE -ne 0) {
    throw "UE5 BuildCookRun failed with exit code $LASTEXITCODE"
}

$Executables = @(Get-ChildItem -LiteralPath $ArchiveRoot -Filter "${ProjectName}.exe" -File -Recurse)
if ($Executables.Count -ne 1) {
    throw "Expected exactly one packaged ${ProjectName}.exe; found $($Executables.Count)"
}
$PackagedExe = $Executables[0]

$PackagedDlls = @(Get-ChildItem -LiteralPath $ArchiveRoot -Filter "openrecomp-e07-rv32i.dll" -File -Recurse)
if ($PackagedDlls.Count -ne 1) {
    throw "Expected exactly one staged OpenRecomp proof DLL; found $($PackagedDlls.Count)"
}
$PackagedDll = $PackagedDlls[0]
$InstalledDllHash = (Get-FileHash -LiteralPath $InstalledDll -Algorithm SHA256).Hash.ToLowerInvariant()
$PackagedDllHash = (Get-FileHash -LiteralPath $PackagedDll.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
if ($InstalledDllHash -ne $PackagedDllHash) {
    throw "Packaged Native AOT DLL differs from the installed validated DLL"
}

@(
    "OPENRECOMP_UNREAL_PLUGIN_V1_PACKAGE=PASS",
    "PACKAGED_EXE=$($PackagedExe.Name)",
    "NATIVE_MODULE_SHA256=$PackagedDllHash"
) | Set-Content -LiteralPath (Join-Path $ResultRoot "PACKAGE_RESULT.txt") -Encoding ASCII

$RawLog = Join-Path ([System.IO.Path]::GetTempPath()) ("openrecomp-plugin-v1-" + [guid]::NewGuid().ToString("N") + ".log")
try {
    Write-Output "===== PACKAGED RUNTIME PROOF ====="
    $StartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $StartInfo.FileName = $PackagedExe.FullName
    $StartInfo.WorkingDirectory = $PackagedExe.DirectoryName
    $StartInfo.UseShellExecute = $false
    $StartInfo.Arguments = "-OpenRecompPluginProof -unattended -nosplash -nullrhi -nosound -abslog=`"$RawLog`""

    $Process = [System.Diagnostics.Process]::Start($StartInfo)
    if ($null -eq $Process) {
        throw "Failed to start packaged OpenRecomp proof process"
    }
    if (-not $Process.WaitForExit($TimeoutSeconds * 1000)) {
        try { $Process.Kill() } catch {}
        throw "Packaged OpenRecomp proof timed out after $TimeoutSeconds seconds"
    }

    if (-not (Test-Path $RawLog -PathType Leaf)) {
        throw "Packaged Unreal log was not created"
    }

    $SafeEvidence = Join-Path $ResultRoot "OPENRECOMP_UNREAL_PLUGIN_V1_PUBLIC_SAFE.txt"
    & (Join-Path $PSScriptRoot "COLLECT_UNREAL_PLUGIN_V1_EVIDENCE.ps1") -UnrealLog $RawLog -OutputPath $SafeEvidence
    if ($LASTEXITCODE -ne 0) {
        throw "Public-safe evidence collector failed"
    }
} finally {
    if (Test-Path $RawLog) {
        Remove-Item -LiteralPath $RawLog -Force
    }
}

$InstallManifest = Join-Path $ProjectRoot "OPENRECOMP_UNREAL_PLUGIN_V1_INSTALL_MANIFEST.txt"
if (Test-Path $InstallManifest -PathType Leaf) {
    Copy-Item -LiteralPath $InstallManifest -Destination (Join-Path $ResultRoot "INSTALL_MANIFEST.txt") -Force
}

@(
    "OPENRECOMP_UNREAL_PLUGIN_V1_EDITOR_BUILD=PASS",
    "OPENRECOMP_UNREAL_PLUGIN_V1_PACKAGE=PASS",
    "OPENRECOMP_UNREAL_PLUGIN_V1_PACKAGED_RUNTIME=PASS",
    "NATIVE_MODULE_SHA256=$PackagedDllHash"
) | Set-Content -LiteralPath (Join-Path $ResultRoot "RESULT.txt") -Encoding ASCII

if (Test-Path $ResultZip) {
    Remove-Item -LiteralPath $ResultZip -Force
}
Compress-Archive -Path (Join-Path $ResultRoot "*") -DestinationPath $ResultZip -CompressionLevel Optimal

Write-Output "OPENRECOMP_UNREAL_PLUGIN_V1_RUNTIME_RESULT=READY"
Write-Output "RESULT_ZIP=$ResultZip"
