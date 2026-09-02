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

function Write-ResultZip {
    if (Test-Path $ResultZip) {
        Remove-Item -LiteralPath $ResultZip -Force
    }
    Compress-Archive -Path (Join-Path $ResultRoot "*") -DestinationPath $ResultZip -CompressionLevel Optimal
}

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

# UE may emit both a root bootstrap executable and the actual staged runtime
# executable under Binaries/Win64. Prefer the latter so command-line proof
# arguments and absolute logging are applied directly to the game process.
$Executables = @(Get-ChildItem -LiteralPath $ArchiveRoot -Filter "${ProjectName}.exe" -File -Recurse)
$RuntimeExecutables = @($Executables | Where-Object {
    $_.FullName -match '[\\/]Binaries[\\/]Win64[\\/]'
})
if ($RuntimeExecutables.Count -eq 1) {
    $PackagedExe = $RuntimeExecutables[0]
} elseif ($Executables.Count -eq 1) {
    $PackagedExe = $Executables[0]
} else {
    $Candidates = ($Executables | ForEach-Object { $_.FullName }) -join '; '
    throw "Could not identify one packaged runtime ${ProjectName}.exe; total=$($Executables.Count) runtime=$($RuntimeExecutables.Count) candidates=$Candidates"
}

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
    "PACKAGED_EXE=$($PackagedExe.FullName)",
    "PACKAGED_EXE_CANDIDATES=$($Executables.Count)",
    "NATIVE_MODULE_SHA256=$PackagedDllHash"
) | Set-Content -LiteralPath (Join-Path $ResultRoot "PACKAGE_RESULT.txt") -Encoding ASCII

$RawLog = Join-Path ([System.IO.Path]::GetTempPath()) ("openrecomp-plugin-v1-" + [guid]::NewGuid().ToString("N") + ".log")
$RuntimeMarker = $null
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
    $RuntimeMarker = (Get-Content -LiteralPath $SafeEvidence -Raw).Trim()
} finally {
    if (Test-Path $RawLog) {
        Remove-Item -LiteralPath $RawLog -Force
    }
}

if ($RuntimeMarker -notmatch '^OPENRECOMP_UNREAL_PLUGIN_V1 PACKAGED_PASS ') {
    @(
        "OPENRECOMP_UNREAL_PLUGIN_V1_EDITOR_BUILD=PASS",
        "OPENRECOMP_UNREAL_PLUGIN_V1_PACKAGE=PASS",
        "OPENRECOMP_UNREAL_PLUGIN_V1_PACKAGED_RUNTIME=FAIL",
        "NATIVE_MODULE_SHA256=$PackagedDllHash",
        "SAFE_MARKER=$RuntimeMarker"
    ) | Set-Content -LiteralPath (Join-Path $ResultRoot "RESULT.txt") -Encoding ASCII
    Write-ResultZip
    Write-Output "OPENRECOMP_UNREAL_PLUGIN_V1_RUNTIME_DIAGNOSTIC=READY"
    Write-Output "RESULT_ZIP=$ResultZip"
    throw "Packaged OpenRecomp plugin proof did not reach the bounded PASS marker"
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

Write-ResultZip

Write-Output "OPENRECOMP_UNREAL_PLUGIN_V1_RUNTIME_RESULT=READY"
Write-Output "RESULT_ZIP=$ResultZip"
