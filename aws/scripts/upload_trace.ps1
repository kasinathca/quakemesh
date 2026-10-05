param(
    [Parameter(Mandatory=$true)][string]$Trace,
    [string]$Region="ap-south-1",
    [string]$Bucket="",
    [string]$Profile="",
    [switch]$DryRun
)
$ErrorActionPreference="Stop"
$Root=Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $Root
if($Profile){$env:AWS_PROFILE=$Profile}
$env:AWS_REGION=$Region;$env:AWS_DEFAULT_REGION=$Region
$Py=Join-Path $Root ".venv\Scripts\python.exe"
if(!(Test-Path $Py)){throw "Run .\scripts\setup.ps1 first"}
$argsList=@("aws/scripts/upload_trace.py","--trace",$Trace,"--region",$Region)
if($Bucket){$argsList += @("--bucket",$Bucket)}
if($DryRun){$argsList += "--dry-run"}
& $Py @argsList
