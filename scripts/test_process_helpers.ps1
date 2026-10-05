$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'process_helpers.ps1')

$testRoot = Join-Path ([IO.Path]::GetTempPath()) ("quakemesh-ps-" + [Guid]::NewGuid().ToString('N'))
$child = Join-Path $testRoot 'parameter child.ps1'
$result = Join-Path $testRoot 'result.txt'

try {
    New-Item -ItemType Directory -Path $testRoot | Out-Null
    @'
param([int]$Port)
[IO.File]::WriteAllText($env:QM_PROCESS_HELPER_RESULT, $Port.ToString())
'@ | Set-Content -LiteralPath $child -Encoding UTF8

    $env:QM_PROCESS_HELPER_RESULT = $result
    $encoded = New-EncodedPowerShellScriptCommand -ScriptPath $child -NamedArguments @{ Port = 8080 }
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand $encoded
    if ($LASTEXITCODE -ne 0) { throw "Child PowerShell exited with $LASTEXITCODE" }
    if ((Get-Content -LiteralPath $result -Raw) -ne '8080') {
        throw 'Named integer parameter was not bound correctly.'
    }
    Write-Host 'PASSED: nested PowerShell named-parameter binding' -ForegroundColor Green
}
finally {
    Remove-Item -LiteralPath $testRoot -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item Env:QM_PROCESS_HELPER_RESULT -ErrorAction SilentlyContinue
}
