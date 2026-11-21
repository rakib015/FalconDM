@echo off
title FalconDM - High-Speed Turbo Download Accelerator
cd /d "%~dp0"
echo ====================================================
echo  Starting FalconDM (Free IDM Alternative)...
echo ====================================================

set "PY_EXE=python"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)

:: Check if Python is available
"%PY_EXE%" --version >nul 2>&1
if errorlevel 1 (
    where py >nul 2>&1
    if not errorlevel 1 (
        set "PY_EXE=py -3"
    ) else (
        echo [ERROR] Python 3 was not found on your system!
        echo Please install Python 3.10+ from https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

:: Auto-install dependencies if missing
"%PY_EXE%" -c "import customtkinter, yt_dlp, requests, PIL, pystray, bs4" >nul 2>&1
if errorlevel 1 (
    echo [*] First-time setup: Installing required libraries...
    "%PY_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies. Check your internet connection.
        pause
        exit /b 1
    )
)

"%PY_EXE%" main.py %*
if errorlevel 1 (
    echo.
    echo FalconDM encountered an error. Press any key to exit...
    pause >nul
)
