@echo off
setlocal
echo DhampirOS - verified USB ISO launcher
echo VirtualBox must be installed on this Windows desktop.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-DhampirOS.ps1"
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
pause
exit /b 1
