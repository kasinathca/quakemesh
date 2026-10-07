param([Parameter(Mandatory = $true)][string]$Directory, [Parameter(Mandatory = $true)][int]$Port)
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (!(Test-Path -LiteralPath $Python)) { throw "Python environment is missing." }
& $Python -m http.server $Port --bind 127.0.0.1 --directory $Directory
if ($LASTEXITCODE -ne 0) { throw "Dashboard server exited with $LASTEXITCODE" }
