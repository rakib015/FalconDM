@echo off
title FalconDM - Turbo Download Accelerator
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" main.py
) else (
    python main.py
)
pause
