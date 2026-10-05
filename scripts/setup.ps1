param([switch]$SkipDevTools,[string]$PythonPath='')
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

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

Write-Host "QuakeMesh setup" -ForegroundColor Cyan
$Python = if($PythonPath){(Resolve-Path -LiteralPath $PythonPath).Path}else{(Get-Command python -ErrorAction Stop).Source}
if($Python -match '\\msys(64)?\\'){
    throw "MSYS2 Python at '$Python' is not supported for this Windows setup because it creates a bin/ virtual environment. Install native Python 3.12 or pass -PythonPath to a native python.exe."
}
Invoke-Checked -Executable $Python -Arguments @(
    "-c",
    "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'; print('Python', sys.version.split()[0])"
) -Label "Python version check"

if (!(Test-Path .venv)) {
    Invoke-Checked -Executable $Python -Arguments @("-m", "venv", ".venv") -Label "Virtual environment creation"
}

$Py = Join-Path $Root ".venv\Scripts\python.exe"
$venvHealthy = $false
if (Test-Path $Py) {
    try {
        & $Py -c "import sys; print(sys.executable)" 2>$null
        $venvHealthy = ($LASTEXITCODE -eq 0)
    }
    catch {
        $venvHealthy = $false
    }
}
if (!$venvHealthy) {
    Write-Host "Existing virtual environment is stale; rebuilding it with $Python" -ForegroundColor Yellow
    Invoke-Checked -Executable $Python -Arguments @("-m", "venv", "--clear", ".venv") -Label "Virtual environment rebuild"
}

Invoke-Checked -Executable $Py -Arguments @("-m", "pip", "install", "--upgrade", "pip") -Label "pip upgrade"

if ($SkipDevTools) {
    Invoke-Checked -Executable $Py -Arguments @("-m", "pip", "install", "-r", "requirements.txt") -Label "Runtime dependency installation"
} else {
    Invoke-Checked -Executable $Py -Arguments @("-m", "pip", "install", "-r", "requirements-dev.txt") -Label "Development dependency installation"
}

Invoke-Checked -Executable $Py -Arguments @(
    "-c",
    "import h3, fastapi, boto3; print('h3', h3.__version__); print('dependencies OK')"
) -Label "Dependency import check"

Write-Host "Setup complete. Next: .\scripts\validate.ps1" -ForegroundColor Green
