@echo off
setlocal EnableDelayedExpansion
title FalconDM - Native Host Registration

echo ========================================================
echo   FalconDM Native Messaging Host Auto-Registration
echo ========================================================
echo.

set "BASE_DIR=%~dp0"
if "%BASE_DIR:~-1%"=="\" set "BASE_DIR=%BASE_DIR:~0,-1%"

:: Resolve host binary (prefer FalconDM.exe if present, else native_host.bat)
set "HOST_BIN="
if exist "%BASE_DIR%\FalconDM.exe" (
    set "HOST_BIN=%BASE_DIR%\FalconDM.exe"
) else if exist "%BASE_DIR%\dist\FalconDM\FalconDM.exe" (
    set "HOST_BIN=%BASE_DIR%\dist\FalconDM\FalconDM.exe"
) else if exist "%BASE_DIR%\core\native_host.bat" (
    set "HOST_BIN=%BASE_DIR%\core\native_host.bat"
) else (
    set "HOST_BIN=%BASE_DIR%\native_host.bat"
)

:: Prepare AppData target directory
set "TARGET_DIR=%APPDATA%\FalconDM\native_messaging"
if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%" >nul 2>&1

set "CHROME_MANIFEST=%TARGET_DIR%\com.falcondm.downloader.json"
set "FIREFOX_MANIFEST=%TARGET_DIR%\com.falcondm.downloader_firefox.json"

:: Write absolute-path manifests using PowerShell (100%% native on every Windows PC)
powershell -NoProfile -Command ^
  "$bin = '%HOST_BIN%'.Replace('\', '\\');" ^
  "$c = @{ name = 'com.falcondm.downloader'; description = 'FalconDM Native Messaging Host'; path = $bin; type = 'stdio'; allowed_origins = @('chrome-extension://kbekmfgcpjeiiiehpffkapbpncbpfjcj/') };" ^
  "$c | ConvertTo-Json -Depth 4 | Set-Content -Path '%CHROME_MANIFEST%' -Encoding UTF8;" ^
  "$f = @{ name = 'com.falcondm.downloader'; description = 'FalconDM Native Messaging Host for Firefox'; path = $bin; type = 'stdio'; allowed_extensions = @('falcondm-turbo@falcondm.local') };" ^
  "$f | ConvertTo-Json -Depth 4 | Set-Content -Path '%FIREFOX_MANIFEST%' -Encoding UTF8;"

echo [1/5] Registering Google Chrome Native Host...
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%CHROME_MANIFEST%" /f >nul 2>&1

echo [2/5] Registering Microsoft Edge Native Host...
reg add "HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%CHROME_MANIFEST%" /f >nul 2>&1

echo [3/5] Registering Brave Browser Native Host...
reg add "HKCU\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%CHROME_MANIFEST%" /f >nul 2>&1

echo [4/5] Registering Opera / Opera GX Native Host...
reg add "HKCU\Software\Opera Software\Opera Stable\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%CHROME_MANIFEST%" /f >nul 2>&1
reg add "HKCU\Software\Opera Software\Opera GX Stable\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%CHROME_MANIFEST%" /f >nul 2>&1
reg add "HKCU\Software\Vivaldi\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%CHROME_MANIFEST%" /f >nul 2>&1

echo [5/5] Registering Mozilla Firefox Native Host...
reg add "HKCU\Software\Mozilla\NativeMessagingHosts\com.falcondm.downloader" /ve /t REG_SZ /d "%FIREFOX_MANIFEST%" /f >nul 2>&1

echo.
echo [OK] FalconDM Native Messaging Hosts registered successfully!
echo The browser extension will now auto-communicate with FalconDM.
echo.

