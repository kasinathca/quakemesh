param(
    [switch]$InstallMissing,
    [switch]$SkipDevTools
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Get-ToolState {
    param([string]$Name,[string[]]$VersionArguments=@('--version'))
    $command=Get-Command $Name -ErrorAction SilentlyContinue
    if(!$command){return [pscustomobject]@{Tool=$Name;Found=$false;Version='missing';Path=''}}
    $version=(& $command.Source @VersionArguments 2>&1 | Select-Object -First 1)
    return [pscustomobject]@{Tool=$Name;Found=$true;Version=[string]$version;Path=$command.Source}
}

$states=@(
    Get-ToolState 'python'
    Get-ToolState 'git'
    Get-ToolState 'node'
    Get-ToolState 'npm'
    Get-ToolState 'aws'
    Get-ToolState 'java' @('-version')
)
$pythonState=$states | Where-Object Tool -eq 'python'
if($pythonState.Found -and $pythonState.Path -match '\\msys(64)?\\'){
    $pythonState.Found=$false
    $pythonState.Version="$($pythonState.Version) (MSYS2; unsuitable for Windows venv)"
}
$states | Format-Table -AutoSize

if($InstallMissing){
    $winget=Get-Command winget -ErrorAction SilentlyContinue
    if(!$winget){throw 'winget is unavailable. Install missing prerequisites manually using docs/v2/QM-V2-FIRST-RUN-WINDOWS.md.'}
    $packages=@{python='Python.Python.3.12';git='Git.Git';node='OpenJS.NodeJS.LTS';aws='Amazon.AWSCLI'}
    foreach($name in @('python','git','node','aws')){
        if(!($states | Where-Object Tool -eq $name).Found){
            Write-Host "Installing $name with winget package $($packages[$name])" -ForegroundColor Cyan
            & $winget.Source install --id $packages[$name] --exact --source winget --accept-package-agreements --accept-source-agreements
            if($LASTEXITCODE -ne 0){throw "winget failed while installing $name"}
        }
    }
    Write-Host 'Open a new PowerShell terminal, then rerun this script without -InstallMissing.' -ForegroundColor Yellow
    exit 0
}

if(!($states | Where-Object Tool -eq 'python').Found){throw 'Python is required. Rerun with -InstallMissing or follow the first-run guide.'}
& (Join-Path $PSScriptRoot 'setup.ps1') -SkipDevTools:$SkipDevTools

if(!($states | Where-Object Tool -eq 'node').Found){Write-Host 'SKIPPED: Node/CDK setup (Node.js missing)' -ForegroundColor Yellow}
if(!($states | Where-Object Tool -eq 'aws').Found){Write-Host 'SKIPPED: AWS CLI authentication check (AWS CLI missing)' -ForegroundColor Yellow}
if(!($states | Where-Object Tool -eq 'java').Found){Write-Host 'SKIPPED: Android build prerequisites (JDK missing). Android Studio/SDK require manual setup.' -ForegroundColor Yellow}

Write-Host 'Windows setup finished. Run .\scripts\validate.ps1 next.' -ForegroundColor Green
