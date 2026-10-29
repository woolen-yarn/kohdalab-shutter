@echo off
setlocal

set "PROJECT_DIR=%~dp0"
if not exist "%PROJECT_DIR%server\main.py" (
    set "PROJECT_DIR=C:\pythonKernel\kohdalab-shutter\"
)

if not exist "%PROJECT_DIR%server\main.py" (
    echo [ERROR] Could not find server\main.py.
    echo Expected project folder:
    echo   %PROJECT_DIR%
    pause
    exit /b 1
)

cd /d "%PROJECT_DIR%"

where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv was not found.
    echo Install uv, then run this file again.
    pause
    exit /b 1
)

if not exist "server\wifi_config.py" (
    echo [ERROR] server\wifi_config.py was not found.
    echo Create it from server\wifi_config.example.py before uploading.
    pause
    exit /b 1
)

echo Uploading server files to Pico W...
uv run mpremote connect auto fs cp server/main.py :main.py fs cp server/discovery.py :discovery.py fs cp server/pca9685.py :pca9685.py fs cp server/servo.py :servo.py fs cp server/settings.py :settings.py fs cp server/wifi_config.py :wifi_config.py reset
if errorlevel 1 goto failed

echo.
echo Upload complete.
pause
exit /b 0

:failed
echo.
echo [ERROR] Upload failed.
pause
exit /b 1
