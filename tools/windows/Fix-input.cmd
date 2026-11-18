@echo off
setlocal
echo DhampirOS - Windows VirtualBox input compatibility repair
echo Keep the DhampirOS VM fully powered off. Administrator access is not needed.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Repair-DhampirOSInput.ps1"
if errorlevel 1 echo No successful repair was confirmed. Read the message above.
echo.
pause
