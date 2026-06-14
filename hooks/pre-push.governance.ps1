# pre-push.governance.ps1 — Pre-push governance gate.
# Exit 0: allow push. Exit 1: block push.

$ErrorActionPreference = 'Continue'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$errors = 0

Write-Host "=== Pre-Push Governance Gate ==="

# ---- 1. Secret scan ----
Write-Host "[1/4] Secret scan..."
$aiGuard = Join-Path $ProjectRoot "tools\ai_guard.py"
if (Test-Path $aiGuard) {
    Push-Location $ProjectRoot
    try { & python $aiGuard full 2>&1 } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { $errors++; Write-Host "[BLOCKED] ai_guard failed" } else { Write-Host "  PASS" }
} else { Write-Host "  SKIP" }
Write-Host ""

# ---- 2. Drift check ----
Write-Host "[2/4] Drift check..."
$drift = Join-Path $ProjectRoot "scripts\Test-GovernanceDrift.ps1"
if (Test-Path $drift) {
    Push-Location $ProjectRoot
    try { & powershell -ExecutionPolicy Bypass -File $drift 2>&1 } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { $errors++; Write-Host "[BLOCKED] Drift check failed" } else { Write-Host "  PASS" }
} else { Write-Host "  SKIP" }
Write-Host ""

# ---- 3. Governance gate ----
Write-Host "[3/4] Governance gate..."
$gate = Join-Path $ProjectRoot "scripts\Test-Governance.ps1"
if (Test-Path $gate) {
    Push-Location $ProjectRoot
    try { & powershell -ExecutionPolicy Bypass -File $gate -Mode blocking 2>&1 } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { $errors++; Write-Host "[BLOCKED] Gate failed" } else { Write-Host "  PASS" }
} else { Write-Host "  SKIP" }
Write-Host ""

# ---- 4. Capability probe ----
Write-Host "[4/4] Capability probe..."
$capabilityEvidence = Join-Path $ProjectRoot "artifacts\capabilities.local.json"
Push-Location $ProjectRoot
try { & python -m cli.main check --capability all --evidence $capabilityEvidence 2>&1 } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { $errors++; Write-Host "[BLOCKED] Capability probe failed" } else { Write-Host "  PASS - capability probe completed; optional BLOCKED capabilities recorded" }
Write-Host ""

if ($errors -gt 0) {
    Write-Host "=== BLOCKED: $errors check(s) failed ==="
    exit 1
}
Write-Host "=== PASS ==="
exit 0
