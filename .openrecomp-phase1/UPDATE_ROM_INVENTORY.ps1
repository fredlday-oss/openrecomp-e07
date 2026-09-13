param(
    [string]$RomRoot = "D:\OpenRecomp\roms\phase1",
    [string]$Output = ""
)
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Output)) {
    $Output = Join-Path $PSScriptRoot "ROM_INVENTORY.json"
}

$platforms = [ordered]@{
    "gameboy"       = @(".gb")
    "gameboy-color" = @(".gbc")
    "master-system" = @(".sms", ".bin")
    "nes"           = @(".nes")
}

$result = [ordered]@{
    generated_at = (Get-Date -Format o)
    rom_root = $RomRoot
    policy = "external-local-verification-input-only"
    platforms = [ordered]@{}
}

foreach ($platform in $platforms.Keys) {
    $entries = @()
    foreach ($bucket in @("primary", "additional")) {
        $dir = Join-Path (Join-Path $RomRoot $platform) $bucket
        if (!(Test-Path -LiteralPath $dir)) {
            continue
        }

        Get-ChildItem -LiteralPath $dir -File | Sort-Object Name | ForEach-Object {
            $ext = $_.Extension.ToLowerInvariant()
            if ($platforms[$platform] -notcontains $ext) {
                return
            }

            $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
            $entries += [ordered]@{
                bucket = $bucket
                filename = $_.Name
                extension = $ext
                bytes = $_.Length
                sha256 = $hash.Hash.ToLowerInvariant()
                full_path = $_.FullName
                repository_copy = $false
            }
        }
    }
    $result.platforms[$platform] = $entries
}

$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Output -Encoding UTF8
Write-Host "OPENRECOMP_PHASE1_ROM_INVENTORY=PASS" -ForegroundColor Green
Write-Host "Output: $Output"
