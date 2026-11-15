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

"%PY_EXE%" main.py
if errorlevel 1 (
    echo.
    echo FalconDM encountered an error. Press any key to exit...
    pause >nul
)
