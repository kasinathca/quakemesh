$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Artifacts = (Resolve-Path (Join-Path $Root "artifacts")).Path
$Database = Join-Path $Artifacts "playwright-e2e.db"
if (!$Database.StartsWith($Artifacts, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean an E2E database outside the repository artifacts directory."
}
foreach ($path in @($Database, "$Database-wal", "$Database-shm")) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}
$env:PYTHONPATH = "$Root\src;$Root"
$env:QM_LOCAL_DB = $Database
$env:QM_GEO_ADAPTER = "synthetic"
$env:QM_ALLOW_SYNTHETIC_GEO = "1"
& (Join-Path $Root ".venv\Scripts\python.exe") -m uvicorn local_runtime.app:app --host 127.0.0.1 --port 8000
