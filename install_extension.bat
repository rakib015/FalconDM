@echo off
setlocal EnableDelayedExpansion
title FalconDM - 1-Click Browser Extension Installer
color 0B

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "EXT_DIR=%ROOT_DIR%\browser_extension"

cls
echo ========================================================================
echo        FalconDM Turbo Accelerator - 1-Click Extension Setup
echo        100%% Free  Open Source  No Chrome Web Store Payment Needed
echo ========================================================================
echo.

:: 1. Run Native Host Registration
echo [*] Step 1/3: Registering Native Messaging Host in Windows Registry...
call "%ROOT_DIR%\register_native_host.bat" >nul 2>&1
echo     [OK] Native Messaging Host linked for Chrome, Edge, Brave and Firefox!
echo.

:: 2. Copy extension path to clipboard
echo [*] Step 2/3: Copying Extension Path to Windows Clipboard...
powershell -NoProfile -Command "Set-Clipboard -Value '%EXT_DIR%'" >nul 2>&1
if %errorlevel% equ 0 (
    echo     [OK] Path copied to clipboard:
    echo          %EXT_DIR%
) else (
    echo     [!] Note: Folder path is: %EXT_DIR%
)
echo.

:: 3. Detect Browsers
echo [*] Step 3/3: Detecting Installed Browsers...

set "CHROME_EXE="
set "EDGE_EXE="
set "BRAVE_EXE="
set "FIREFOX_EXE="
set "OPERA_EXE="

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"

if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "EDGE_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "EDGE_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"

if exist "%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe" set "BRAVE_EXE=%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"
if exist "%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe" set "BRAVE_EXE=%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe"

if exist "%ProgramFiles%\Mozilla Firefox\firefox.exe" set "FIREFOX_EXE=%ProgramFiles%\Mozilla Firefox\firefox.exe"
if exist "%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe" set "FIREFOX_EXE=%ProgramFiles(x86)%\Mozilla Firefox\firefox.exe"

if exist "%LocalAppData%\Programs\Opera\launcher.exe" set "OPERA_EXE=%LocalAppData%\Programs\Opera\launcher.exe"
if exist "%ProgramFiles%\Opera\launcher.exe" set "OPERA_EXE=%ProgramFiles%\Opera\launcher.exe"

if defined CHROME_EXE ( echo     [+] Detected: Google Chrome )
if defined EDGE_EXE ( echo     [+] Detected: Microsoft Edge )
if defined BRAVE_EXE ( echo     [+] Detected: Brave Browser )
if defined FIREFOX_EXE ( echo     [+] Detected: Mozilla Firefox )
if defined OPERA_EXE ( echo     [+] Detected: Opera )

echo.
echo ========================================================================
echo  SELECT YOUR BROWSER TO OPEN EXTENSION MANAGER:
echo ========================================================================
echo   [1] Google Chrome          (chrome://extensions)
echo   [2] Microsoft Edge         (edge://extensions)
echo   [3] Brave Browser          (brave://extensions)
echo   [4] Mozilla Firefox        (about:debugging)
echo   [5] Opera / Opera GX       (opera://extensions)
echo   [6] Open Extension Folder in Windows Explorer
echo   [0] Exit
echo.

set /p BROWSER_CHOICE="Enter choice [Default: 1]: "
if "%BROWSER_CHOICE%"=="" set BROWSER_CHOICE=1

if "%BROWSER_CHOICE%"=="1" (
    echo Opening Chrome Extensions...
    start "" chrome "chrome://extensions" 2>nul || (
        if defined CHROME_EXE ( start "" "%CHROME_EXE%" "chrome://extensions" ) else ( start chrome://extensions )
    )
)
if "%BROWSER_CHOICE%"=="2" (
    echo Opening Edge Extensions...
    start "" msedge "edge://extensions" 2>nul || (
        if defined EDGE_EXE ( start "" "%EDGE_EXE%" "edge://extensions" ) else ( start edge://extensions )
    )
)
if "%BROWSER_CHOICE%"=="3" (
    echo Opening Brave Extensions...
    start "" brave "brave://extensions" 2>nul || (
        if defined BRAVE_EXE ( start "" "%BRAVE_EXE%" "brave://extensions" ) else ( start brave://extensions )
    )
)
if "%BROWSER_CHOICE%"=="4" (
    echo Opening Firefox Debugging...
    start "" firefox "about:debugging#/runtime/this-firefox" 2>nul || (
        if defined FIREFOX_EXE ( start "" "%FIREFOX_EXE%" "about:debugging#/runtime/this-firefox" ) else ( start about:debugging#/runtime/this-firefox )
    )
)
if "%BROWSER_CHOICE%"=="5" (
    echo Opening Opera Extensions...
    start "" opera "opera://extensions" 2>nul || (
        if defined OPERA_EXE ( start "" "%OPERA_EXE%" "opera://extensions" ) else ( start opera://extensions )
    )
)
if "%BROWSER_CHOICE%"=="6" (
    explorer "%EXT_DIR%"
    goto :INSTRUCTIONS
)
if "%BROWSER_CHOICE%"=="0" (
    exit /b 0
)

:INSTRUCTIONS
echo.
echo ========================================================================
echo              HOW TO LOAD (Takes Only 5 Seconds!)
echo ========================================================================
echo   1. Turn ON the [Developer mode] toggle switch at the top-right.
echo   2. Click the [Load unpacked] button on the top-left.
echo   3. Press Ctrl + V in the file dialog (path is already on clipboard!)
echo   4. Click 'Select Folder' or press Enter.
echo.
echo   THAT'S IT! FalconDM is now fully integrated into your browser.
echo ========================================================================
echo.
pause

