$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"

function Invoke-Checked {
    param(
        [Parameter(Mandatory=$true)][string]$Executable,
        [Parameter(Mandatory=$true)][string[]]$Arguments,
        [Parameter(Mandatory=$true)][string]$Label
    )
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

if (!(Test-Path $Py)) {
    throw "Run .\scripts\setup.ps1 first"
}

$env:PYTHONPATH = "$Root\src;$Root"
Set-Location $Root

Write-Host "[1/6] Python compilation" -ForegroundColor Cyan
Invoke-Checked -Executable $Py -Arguments @("scripts/release_audit.py", "--compile-only") -Label "Python compilation"

Write-Host "[2/6] Tests" -ForegroundColor Cyan
Invoke-Checked -Executable $Py -Arguments @("-m", "pytest", "-q") -Label "Tests"

Write-Host "[3/6] Ruff critical checks" -ForegroundColor Cyan
# Lint only QuakeMesh-owned Python paths. Never lint .venv/site-packages.
Invoke-Checked -Executable $Py -Arguments @(
    "-m", "ruff", "check",
    "src", "local_runtime", "simulator", "aws", "scripts", "tests"
) -Label "Ruff"

Write-Host "[4/6] Secret scan" -ForegroundColor Cyan
Invoke-Checked -Executable $Py -Arguments @("scripts/check_secrets.py") -Label "Secret scan"

Write-Host "[5/6] PowerShell process-launch smoke test" -ForegroundColor Cyan
& (Join-Path $Root 'scripts\test_process_helpers.ps1')
if ($LASTEXITCODE -ne 0) { throw "PowerShell process-launch smoke test failed with exit code $LASTEXITCODE" }

Write-Host "[6/6] Repository audit" -ForegroundColor Cyan
Invoke-Checked -Executable $Py -Arguments @("scripts/release_audit.py") -Label "Repository audit"

Write-Host "Validation complete: all gates passed" -ForegroundColor Green
