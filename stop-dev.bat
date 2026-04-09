@echo off
setlocal
echo Stopping processes listening on ports 8000 and 3000...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-dev.ps1"
if errorlevel 1 (
  echo If that failed, close the two server windows manually ^(API / Web^).
) else (
  echo Done.
)
timeout /t 3 >nul
