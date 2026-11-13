@echo off
setlocal
cd /d "%~dp0"
if not exist "target\release\kohdalab-shutter-gui.exe" (
    echo [ERROR] Rust GUI has not been built.
    echo Run: cargo build --release --locked
    pause
    exit /b 1
)
start "" "%~dp0target\release\kohdalab-shutter-gui.exe"
endlocal
