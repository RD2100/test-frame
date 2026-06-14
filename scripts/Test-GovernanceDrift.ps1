# Test-GovernanceDrift.ps1 - verify hash-locked governance files.

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ManifestPath = Join-Path $ProjectRoot "docs\agent-runtime\governance-manifest.md"

if (-not (Test-Path $ManifestPath)) {
    Write-Error "Governance manifest not found: $ManifestPath"
    exit 1
}

$manifest = Get-Content -Raw -LiteralPath $ManifestPath
$rows = [regex]::Matches(
    $manifest,
    '^\| (?<id>[A-Z0-9_]+) \| `(?<file>[^`]+)`.*\| (?<hash>[A-F0-9]{64}) \|$',
    [System.Text.RegularExpressions.RegexOptions]::Multiline
)

if ($rows.Count -eq 0) {
    Write-Error "No protected hash rows found in governance manifest."
    exit 1
}

$errors = 0
foreach ($row in $rows) {
    $id = $row.Groups["id"].Value
    $file = $row.Groups["file"].Value
    $expected = $row.Groups["hash"].Value
    $path = Join-Path $ProjectRoot $file

    if (-not (Test-Path $path)) {
        Write-Host "[DRIFT] $id missing file: $file"
        $errors++
        continue
    }

    $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    if ($actual -ne $expected) {
        Write-Host "[DRIFT] $id hash mismatch: $file"
        Write-Host "        expected: $expected"
        Write-Host "        actual:   $actual"
        $errors++
    } else {
        Write-Host "[OK] $id $file"
    }
}

if ($errors -gt 0) {
    Write-Host "Governance drift detected: $errors issue(s)."
    exit 1
}

Write-Host "Governance drift check: PASS"
exit 0
