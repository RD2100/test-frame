# Test-Governance.ps1 - lightweight local governance gate.

param(
    [ValidateSet("blocking", "audit")]
    [string]$Mode = "blocking"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ExpectedPath = Join-Path $ProjectRoot "governance\expected-files.txt"

if (-not (Test-Path $ExpectedPath)) {
    Write-Error "Expected file manifest not found: $ExpectedPath"
    exit 1
}

$patterns = Get-Content -LiteralPath $ExpectedPath |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -and -not $_.StartsWith("#") }

function Convert-GlobToRegex {
    param([string]$Pattern)

    $normalized = $Pattern.Replace("\", "/")
    $escaped = [regex]::Escape($normalized)
    $escaped = $escaped.Replace("\*\*/", "(?:.*/)?")
    $escaped = $escaped.Replace("\*\*", ".*")
    $escaped = $escaped.Replace("\*", "[^/]*")
    return "^$escaped$"
}

$trackedFiles = & git -C $ProjectRoot ls-files --cached --others --exclude-standard
if ($LASTEXITCODE -ne 0) {
    Write-Error "git ls-files failed."
    exit 1
}

$errors = 0
foreach ($pattern in $patterns) {
    $regex = Convert-GlobToRegex $pattern
    $matches = $trackedFiles |
        Where-Object { $_.Replace("\", "/") -match $regex } |
        Select-Object -First 1

    if (-not $matches) {
        Write-Host "[MISSING] $pattern"
        $errors++
    }
}

$driftScript = Join-Path $PSScriptRoot "Test-GovernanceDrift.ps1"
& powershell -ExecutionPolicy Bypass -File $driftScript
if ($LASTEXITCODE -ne 0) {
    $errors++
}

if ($errors -gt 0) {
    $message = "Governance gate found $errors issue(s)."
    if ($Mode -eq "blocking") {
        Write-Host $message
        exit 1
    }
    Write-Warning $message
}

Write-Host "Governance gate: PASS"
exit 0
