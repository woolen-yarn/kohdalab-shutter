# Windows PC Setup

This checklist prepares a Windows PC for using KohdaLab Shutter and uploading
server files to the Pico W.

## 1. Install System Tools

Install Git:

```powershell
winget install --id Git.Git -e --source winget
```

Install uv:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new PowerShell and check:

```powershell
git --version
uv --version
```

## 2. Clone and Sync

```powershell
New-Item -ItemType Directory -Force -Path $HOME\pythonKernel
Set-Location $HOME\pythonKernel
git clone https://github.com/Kohdalab/kohdalab-shutter.git kohdalab-shutter
Set-Location kohdalab-shutter
uv sync
```

## 3. Prepare Wi-Fi Config

```powershell
Copy-Item server\wifi_config.example.py server\wifi_config.py
```

Edit `server\wifi_config.py` with the local SSID and password. This file is
ignored by Git.

## 4. Upload to Pico W

Connect the Pico W by USB and confirm MicroPython is installed.

```powershell
uv run mpremote connect auto fs cp server/main.py :main.py
uv run mpremote connect auto fs cp server/pca9685.py :pca9685.py
uv run mpremote connect auto fs cp server/settings.py :settings.py
uv run mpremote connect auto fs cp server/wifi_config.py :wifi_config.py
uv run mpremote connect auto reset
```

## 5. First Hardware Smoke Test

1. Confirm servo power and common ground.
2. Confirm channel wiring.
3. Start the Pico W server.
4. Check status from the PC.
5. Open and close one channel with a safe optical path.

```powershell
uv run python -m client.cli status
uv run python -m client.cli open 0
uv run python -m client.cli close 0
```

## 6. Start GUI

```powershell
uv run python -m client.gui
```
