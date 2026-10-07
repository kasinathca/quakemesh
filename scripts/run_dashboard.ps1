param([int]$Port = 8080, [string]$ConfigPath = "")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Dashboard = Join-Path $Root "dashboard"
$DistIndex = Join-Path $Dashboard "dist\index.html"
$PackageLock = Join-Path $Dashboard "package-lock.json"

if ($Port -lt 1 -or $Port -gt 65535) {
    throw "Port must be between 1 and 65535."
}

$sourceFiles = Get-ChildItem `
    -Path (Join-Path $Dashboard "src"), (Join-Path $Dashboard "public"), (Join-Path $Dashboard "index.html"), (Join-Path $Dashboard "package.json"), $PackageLock `
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

$DistConfig = Join-Path $Dashboard "dist\config.js"
if ($ConfigPath) {
    $resolvedConfig = Resolve-Path $ConfigPath -ErrorAction Stop
    $runtime = Get-Content $resolvedConfig -Raw | ConvertFrom-Json
    if (!$runtime.api_base_url -or !$runtime.api_key -or !$runtime.session_id) {
        throw "AWS V2 runtime config is missing api_base_url, api_key, or session_id."
    }
    $browserConfig = [ordered]@{
        apiBaseUrl = $runtime.api_base_url
        apiKey = $runtime.api_key
        environmentLabel = "AWS V2 Demo"
        region = $runtime.region
        sessionId = $runtime.session_id
        expiresAt = $runtime.expires_at
    } | ConvertTo-Json -Compress
    Set-Content -LiteralPath $DistConfig -Value "window.QUAKEMESH_CONFIG = $browserConfig;" -Encoding UTF8
    Write-Host "Dashboard mode: AWS V2 Demo ($($runtime.region), session $($runtime.session_id))" -ForegroundColor Yellow
} else {
    Copy-Item -LiteralPath (Join-Path $Dashboard "public\config.js") -Destination $DistConfig -Force
    Write-Host "Dashboard mode: Local V2" -ForegroundColor Cyan
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}
Write-Host "Dashboard: http://127.0.0.1:$Port" -ForegroundColor Green
& $Python -m http.server $Port --bind 127.0.0.1 --directory (Join-Path $Dashboard "dist")
