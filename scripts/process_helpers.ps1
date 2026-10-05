Set-StrictMode -Version Latest

function ConvertTo-PowerShellLiteral {
    param([AllowNull()][object]$Value)

    if ($null -eq $Value) { return '$null' }
    if ($Value -is [bool]) { return $(if ($Value) { '$true' } else { '$false' }) }
    if ($Value -is [byte] -or $Value -is [int16] -or $Value -is [int32] -or $Value -is [int64]) {
        return ([Convert]::ToString($Value, [Globalization.CultureInfo]::InvariantCulture))
    }

    return "'" + ([string]$Value).Replace("'", "''") + "'"
}

function New-EncodedPowerShellScriptCommand {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [hashtable]$NamedArguments = @{}
    )

    $scriptLiteral = ConvertTo-PowerShellLiteral -Value $ScriptPath
    $assignments = foreach ($name in ($NamedArguments.Keys | Sort-Object)) {
        if ([string]$name -notmatch '^[A-Za-z][A-Za-z0-9_-]*$') {
            throw "Unsafe PowerShell parameter name: $name"
        }
        $nameLiteral = ConvertTo-PowerShellLiteral -Value ([string]$name)
        $valueLiteral = ConvertTo-PowerShellLiteral -Value $NamedArguments[$name]
        "`$childParameters[$nameLiteral] = $valueLiteral"
    }

    $command = "`$ErrorActionPreference = 'Stop'; `$childParameters = @{}; " +
        ($assignments -join '; ') + 
        "; & $scriptLiteral @childParameters"
    return [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
}

function Start-PowerShellScriptSafely {
    param(
        [Parameter(Mandatory = $true)][string]$ScriptPath,
        [hashtable]$NamedArguments = @{},
        [string]$WorkingDirectory = (Get-Location).Path,
        [switch]$NoExit
    )

    $encoded = New-EncodedPowerShellScriptCommand -ScriptPath $ScriptPath -NamedArguments $NamedArguments
    $arguments = @('-NoProfile', '-ExecutionPolicy', 'Bypass')
    if ($NoExit) { $arguments += '-NoExit' }
    $arguments += @('-EncodedCommand', $encoded)
    Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WorkingDirectory $WorkingDirectory -PassThru
}
