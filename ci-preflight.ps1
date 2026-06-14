# ci-preflight.ps1 - Run CI-equivalent checks locally.
$ErrorActionPreference = 'Continue'
$ProjectRoot = (Resolve-Path $PSScriptRoot).Path
$errors = 0
Write-Host "=== CI Preflight ==="
Write-Host ""

Write-Host "[1/4] AI Guard..."
$aiGuard = Join-Path $ProjectRoot "tools\ai_guard.py"
if (Test-Path $aiGuard) {
    Push-Location $ProjectRoot; try { & python $aiGuard full 2>&1 } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { $errors++; Write-Host "  FAILED" } else { Write-Host "  PASS" }
} else { Write-Host "  SKIP" }
Write-Host ""

Write-Host "[2/4] Drift Check..."
$drift = Join-Path $ProjectRoot "scripts\Test-GovernanceDrift.ps1"
if (Test-Path $drift) {
    Push-Location $ProjectRoot; try { & powershell -ExecutionPolicy Bypass -File $drift 2>&1 } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { $errors++; Write-Host "  FAILED" } else { Write-Host "  PASS" }
} else { Write-Host "  SKIP" }
Write-Host ""

Write-Host "[3/4] Governance Gate..."
$gate = Join-Path $ProjectRoot "scripts\Test-Governance.ps1"
if (Test-Path $gate) {
    Push-Location $ProjectRoot; try { & powershell -ExecutionPolicy Bypass -File $gate -Mode blocking 2>&1 } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { $errors++; Write-Host "  FAILED" } else { Write-Host "  PASS" }
} else { Write-Host "  SKIP" }
Write-Host ""

Write-Host "[4/4] Capability Probe..."
$capabilityEvidence = Join-Path $ProjectRoot "artifacts\capabilities.local.json"
Push-Location $ProjectRoot
try { & python -m cli.main check --capability all --evidence $capabilityEvidence 2>&1 } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { $errors++; Write-Host "  FAILED" } else { Write-Host "  PASS - capability probe completed; optional BLOCKED capabilities recorded" }
Write-Host ""

if ($errors -gt 0) { Write-Host "=== $errors check(s) FAILED ==="; exit 1 }
Write-Host "=== All checks PASSED ==="; exit 0
