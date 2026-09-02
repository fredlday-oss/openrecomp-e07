param(
    [Parameter(Mandatory=$true)][string]$ProjectFile,
    [Parameter(Mandatory=$true)][string]$UE5Root,
    [Parameter(Mandatory=$true)][string]$ArchiveRoot
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ProjectFile)) { throw "Project file not found: $ProjectFile" }
$RunUAT = Join-Path $UE5Root "Engine\Build\BatchFiles\RunUAT.bat"
if (-not (Test-Path $RunUAT)) { throw "RunUAT.bat not found: $RunUAT" }

if (Test-Path $ArchiveRoot) {
    Remove-Item -Recurse -Force $ArchiveRoot
}
New-Item -ItemType Directory -Force -Path $ArchiveRoot | Out-Null

& $RunUAT BuildCookRun `
    "-project=$ProjectFile" `
    -noP4 `
    -platform=Win64 `
    -clientconfig=Development `
    -build `
    -cook `
    -allmaps `
    -stage `
    -pak `
    -package `
    -archive `
    "-archivedirectory=$ArchiveRoot" `
    -utf8output

if ($LASTEXITCODE -ne 0) {
    throw "BuildCookRun failed with exit code $LASTEXITCODE"
}

$Dlls = @(Get-ChildItem -Path $ArchiveRoot -Filter "openrecomp-e07-rv32i.dll" -File -Recurse)
if ($Dlls.Count -lt 1) {
    throw "Packaged archive does not contain openrecomp-e07-rv32i.dll"
}

$DllHash = (Get-FileHash $Dlls[0].FullName -Algorithm SHA256).Hash.ToLowerInvariant()
$ResultPath = Join-Path $PSScriptRoot "PACKAGED_BUILD_RESULT.txt"
@(
    "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_PACKAGE=PASS",
    "CONFIGURATION=Development",
    "PLATFORM=Win64",
    "STAGED_DLL_SHA256=$DllHash"
) | Set-Content -Encoding ascii $ResultPath

Write-Output "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_PACKAGE=PASS"
Write-Output "OPENRECOMP_UNREAL_PACKAGED_BUILD_V1_STAGED_DLL_SHA256=$DllHash"
