param([int]$Port = 8080)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Dashboard = Join-Path $Root "dashboard"
$DistIndex = Join-Path $Dashboard "dist\index.html"
$PackageLock = Join-Path $Dashboard "package-lock.json"

if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Port must be between 1 and 65535."
}

$sourceFiles = Get-ChildItem `
    -Path (Join-Path $Dashboard "src"), (Join-Path $Dashboard "index.html"), (Join-Path $Dashboard "package.json"), $PackageLock `
    -File `
    -Recurse
$latestSource = ($sourceFiles | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1).LastWriteTimeUtc
$buildRequired = !(Test-Path $DistIndex)
if (!$buildRequired) {
    $buildRequired = (Get-Item $DistIndex).LastWriteTimeUtc -lt $latestSource
}

if ($buildRequired) {
    $node = Get-Command node -ErrorAction SilentlyContinue
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (!$node -or !$npm) {
        throw "The dashboard production build is missing or stale. Install Node.js 20+ and npm, then rerun this command."
    }
    Push-Location $Dashboard
    try {
        if (!(Test-Path (Join-Path $Dashboard "node_modules"))) {
            Write-Host "Installing locked dashboard dependencies..." -ForegroundColor Cyan
            & npm ci
            if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE" }
        }
        Write-Host "Building QuakeMesh dashboard..." -ForegroundColor Cyan
        & npm run build
        if ($LASTEXITCODE -ne 0) { throw "Dashboard build failed with exit code $LASTEXITCODE" }
    }
    finally {
        Pop-Location
    }
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}
Write-Host "Dashboard: http://127.0.0.1:$Port" -ForegroundColor Green
& $Python -m http.server $Port --bind 127.0.0.1 --directory (Join-Path $Dashboard "dist")
