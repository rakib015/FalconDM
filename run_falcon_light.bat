@echo off
setlocal
title FalconDM Light - Ultra-Low Spec Background Mode

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo ========================================================================
echo        FalconDM Light - Ultra-Low Spec / Battery Saver Mode
echo        RAM: ~15-20 MB  CPU Idle: 0.0%%  Full Turbo Acceleration
echo ========================================================================
echo.
echo [*] Starting FalconDM silently in System Tray...
echo [*] Browser Webhook Bridge active on http://127.0.0.1:9666
echo.

where pythonw >nul 2>&1
if %errorlevel% equ 0 (
    start "" pythonw main.py --tray
    echo [OK] FalconDM is running quietly in your Windows System Tray (Taskbar).
    echo      Double-click the tray icon anytime to open the full UI.
    timeout /t 2 >nul
    exit /b 0
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    start "" pyw -3 main.py --tray 2>nul || start "" py -3 main.py --tray
    echo [OK] FalconDM is running quietly in your Windows System Tray.
    timeout /t 2 >nul
    exit /b 0
)

start "" python main.py --tray
echo [OK] FalconDM is running in your System Tray.
timeout /t 2 >nul

