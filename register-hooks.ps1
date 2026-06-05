# register-hooks.ps1 — Activate CI preflight hooks. Run once per clone.
$ErrorActionPreference = 'Stop'
$HookDir = "$PSScriptRoot\hooks"
$RepoRoot = (Resolve-Path (Join-Path $HookDir "..")).Path
Write-Host "=== CI Preflight Registration ==="
foreach ($f in @("pre-commit","pre-commit.governance.ps1","pre-push","pre-push.governance.ps1")) {
    if (-not (Test-Path (Join-Path $HookDir $f))) { Write-Error "Missing: hooks/$f"; exit 1 }
}
Push-Location $RepoRoot
try { git config core.hooksPath hooks; Write-Host "[OK] core.hooksPath = hooks" } finally { Pop-Location }
Write-Host "Next: edit governance/expected-files.txt, then verify with ci-preflight.ps1"
