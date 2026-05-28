@echo off
setlocal

set "PROJECT_DIR=%~dp0"
if not exist "%PROJECT_DIR%client\gui.py" (
    set "PROJECT_DIR=C:\pythonKernel\kohdalab-shutter\"
)

if not exist "%PROJECT_DIR%client\gui.py" (
    echo [ERROR] Could not find client\gui.py.
    echo Expected project folder:
    echo   %PROJECT_DIR%
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"
set "PYTHONPATH=%PROJECT_DIR%;%PYTHONPATH%"

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv was not found.
    echo Install uv, then run this file again.
    pause
    exit /b 1
)

echo Starting Kohda Lab Shutter GUI...
echo Project: %CD%
uv run python -m client.gui

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start the GUI.
    pause
    exit /b 1
)

endlocal
