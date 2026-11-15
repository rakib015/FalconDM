@echo off
setlocal EnableDelayedExpansion
title FalconDM - Native Host Registration

echo ========================================================
echo   FalconDM Native Messaging Host Auto-Registration
echo ========================================================
echo.

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"

set "NATIVE_HOST_BAT=%BASE_DIR%\core\native_host.bat"
set "CHROME_MANIFEST=%BASE_DIR%\core\com.falcondm.downloader.json"
set "FIREFOX_MANIFEST=%BASE_DIR%\core\com.falcondm.downloader_firefox.json"

:: Use python if available to dynamically inject the absolute path
where python >nul 2>&1
if %errorlevel% equ 0 (
    python -c "from core.platform_utils import register_browser_integration; register_browser_integration()" >nul 2>&1
)

echo [1/5] Registering Google Chrome Native Host...
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%CHROME_MANIFEST%" /f >nul 2>&1

echo [2/5] Registering Microsoft Edge Native Host...
reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%CHROME_MANIFEST%" /f >nul 2>&1

echo [3/5] Registering Brave Browser Native Host...
reg add "HKCU\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%CHROME_MANIFEST%" /f >nul 2>&1

echo [4/5] Registering Opera / Opera GX Native Host...
reg add "HKCU\Software\Opera Software\Opera Stable\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%CHROME_MANIFEST%" /f >nul 2>&1
reg add "HKCU\Software\Opera Software\Opera GX Stable\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%CHROME_MANIFEST%" /f >nul 2>&1

echo [5/5] Registering Mozilla Firefox Native Host...
reg add "HKCU\Software\Mozilla\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%FIREFOX_MANIFEST%" /f >nul 2>&1

echo.
echo [OK] FalconDM Native Messaging Hosts registered successfully!
echo The browser extension will now auto-communicate with FalconDM.
echo.

