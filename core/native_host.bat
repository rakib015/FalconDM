@echo off
setlocal
set "DIR=%~dp0"
if exist "%DIR%..\FalconDM.exe" (
    "%DIR%..\FalconDM.exe" --native-host
    exit /b %errorlevel%
)
if exist "%DIR%..\.venv\Scripts\python.exe" (
    "%DIR%..\.venv\Scripts\python.exe" "%DIR%native_host.py"
    exit /b %errorlevel%
)
if exist "%DIR%..\venv\Scripts\python.exe" (
    "%DIR%..\venv\Scripts\python.exe" "%DIR%native_host.py"
    exit /b %errorlevel%
)
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3 "%DIR%native_host.py"
    exit /b %errorlevel%
)
python "%DIR%native_host.py"

