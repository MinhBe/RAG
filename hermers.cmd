@echo off
setlocal
if /I "%~1"=="vaccine" (
  uv run --project "%~dp0" python "%~dp0scripts\run_vaccine_regression.py"
  exit /b %ERRORLEVEL%
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\hermes.ps1" %*
