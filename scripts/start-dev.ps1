$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

Write-Host "Starting API on http://127.0.0.1:8000 ..."
Start-Process cmd -ArgumentList @(
    "/k",
    "pushd `"$Backend`" && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
) -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "Starting web on http://127.0.0.1:3000 ..."
Start-Process cmd -ArgumentList @(
    "/k",
    "pushd `"$Frontend`" && npm run dev"
) -WindowStyle Normal

Write-Host ""
Write-Host "Opened two windows. Run stop-dev.bat to stop both, or close each window."
Start-Sleep -Seconds 3
