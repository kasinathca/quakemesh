$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Dashboard = Join-Path $Root "dashboard"
$PytestBaseTemp = Join-Path $Root "artifacts\pytest-validation"
$script:Passed = 0
$script:Skipped = 0

function Invoke-Gate {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )
    Write-Host "RUN  $Label" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
    $script:Passed++
    Write-Host "PASS $Label" -ForegroundColor Green
}

function Skip-Gate {
    param([string]$Label, [string]$Reason)
    $script:Skipped++
    Write-Host "SKIP $Label - $Reason" -ForegroundColor Yellow
}

if (!(Test-Path $Python)) {
    throw "Run .\scripts\setup.ps1 first"
}

$env:PYTHONPATH = "$Root\src;$Root"
Set-Location $Root

Invoke-Gate "Python compilation" { & $Python scripts/release_audit.py --compile-only }
Invoke-Gate "pytest" { & $Python -m pytest -q --basetemp $PytestBaseTemp }
Invoke-Gate "Ruff repository critical rules" {
    & $Python -m ruff check src local_runtime simulator aws scripts tests
}
Invoke-Gate "Ruff professional rules for V2-modified modules" {
    & $Python -m ruff check `
        local_runtime/app.py `
        local_runtime/contracts.py `
        local_runtime/errors.py `
        local_runtime/repository.py `
        local_runtime/scenario_catalog.py `
        local_runtime/scenarios.py `
        local_runtime/service.py `
        simulator/fleet.py `
        simulator/transports.py `
        scripts/release_audit.py `
        scripts/validate_schemas.py `
        tests/test_v2_control_plane.py `
        --select E4,E7,E9,F
}
Invoke-Gate "Secret scan" { & $Python scripts/check_secrets.py }
Invoke-Gate "JSON schema validation" { & $Python scripts/validate_schemas.py }
Invoke-Gate "PowerShell process-launch tests" { & (Join-Path $Root "scripts\test_process_helpers.ps1") }

$Node = Get-Command node -ErrorAction SilentlyContinue
$Npm = Get-Command npm -ErrorAction SilentlyContinue
if (!$Node -or !$Npm) {
    Skip-Gate "Frontend dependency verification" "Node.js/npm unavailable"
    Skip-Gate "TypeScript, lint, unit tests, production build" "Node.js/npm unavailable"
    Skip-Gate "Browser E2E" "Node.js/npm unavailable"
}
else {
    Push-Location $Dashboard
    try {
        Invoke-Gate "Frontend locked dependency install" { & npm ci --ignore-scripts }
        Invoke-Gate "TypeScript typecheck" { & npm run typecheck }
        Invoke-Gate "Frontend lint" { & npm run lint }
        Invoke-Gate "Frontend unit tests" { & npm test }
        Invoke-Gate "Frontend production build" { & npm run build }
        if ($env:QM_SKIP_BROWSER_E2E -eq "1") {
            Skip-Gate "Browser E2E" "QM_SKIP_BROWSER_E2E=1"
        }
        else {
            $browserList = & npx playwright install --list 2>$null
            if ($LASTEXITCODE -eq 0 -and ($browserList -join "`n") -match "chromium") {
                Invoke-Gate "Browser E2E" { & npm run test:e2e }
            }
            else {
                Skip-Gate "Browser E2E" "Playwright Chromium is not installed; run npx playwright install chromium"
                $global:LASTEXITCODE = 0
            }
        }
    }
    finally {
        Pop-Location
    }
}

Invoke-Gate "Repository audit" { & $Python scripts/release_audit.py }
Skip-Gate "Android V2 validation" "outside this phase"
Skip-Gate "AWS live validation" "outside this phase; no deployment performed"
Skip-Gate "FCM live delivery" "outside this phase; no credentials/device used"

Write-Host "Validation complete: $script:Passed PASS, $script:Skipped SKIP, 0 FAIL" -ForegroundColor Green
