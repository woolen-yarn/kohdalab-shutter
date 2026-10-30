@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
    echo Install uv from https://docs.astral.sh/uv/getting-started/installation/ then run this file again.
    pause
    exit /b 1
)
uv run --no-project --python 3.13 --with "mpremote>=1.25,<2" python scripts/upload_pico.py %*
set "UPLOAD_RESULT=%ERRORLEVEL%"
pause
exit /b %UPLOAD_RESULT%
