@echo off
setlocal
set "HERMES_REPO=%~dp0"
pushd "%HERMES_REPO%" >nul
if /I "%~1"=="vaccine" (
  uv run python scripts\run_vaccine_regression.py
  set "ec=%ERRORLEVEL%"
  popd >nul
  exit /b %ec%
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%HERMES_REPO%scripts\hermes.ps1" %*
set "ec=%ERRORLEVEL%"
popd >nul
exit /b %ec%
