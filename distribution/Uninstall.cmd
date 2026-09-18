@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Patch.ps1" -Action Uninstall -GameDir "%~1"
set "patch_exit=%ERRORLEVEL%"
pause
exit /b %patch_exit%
