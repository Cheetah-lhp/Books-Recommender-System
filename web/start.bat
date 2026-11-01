@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\launch-demo.ps1" %*
set "demoExitCode=%errorlevel%"
if not "%demoExitCode%"=="0" (
    echo.
    echo Demo chua khoi dong thanh cong. Xem loi o tren va trong cac cua so service.
    pause
)
exit /b %demoExitCode%
