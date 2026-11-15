@echo off
title FalconDM - Build Windows Installer
cd /d "%~dp0"

echo ========================================================
echo    FalconDM Windows Setup Installer Builder
echo ========================================================
echo.

echo [1/3] Cleaning previous build artifacts...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"

echo [2/3] Compiling FalconDM with PyInstaller...
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m PyInstaller --clean --noconfirm build_falcondm.spec
) else (
    python -m PyInstaller --clean --noconfirm build_falcondm.spec
)

if not exist "dist\FalconDM\FalconDM.exe" (
    echo [ERROR] PyInstaller compilation failed!
    pause
    exit /b 1
)

echo.
echo [3/3] Generating Setup Installer with Inno Setup...
set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"

"%ISCC_PATH%" setup.iss

if exist "dist_installer\FalconDM-Setup-v2.8.0.exe" (
    echo.
    echo ========================================================
    echo   [SUCCESS] FalconDM Setup Installer created!
    echo   File: dist_installer\FalconDM-Setup-v2.8.0.exe
    echo ========================================================
) else (
    echo [ERROR] Inno Setup compilation failed!
)

echo.
pause

