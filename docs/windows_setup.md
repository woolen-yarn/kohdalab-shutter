# Windows setup / Windowsの設定

The standard desktop application is the Rust version. See [Pico W setup and discovery](rust-client.md) for discovery and USB IP inspection.

PC側の標準アプリはRust版です。検索とUSBでのIP確認は[Pico Wの設定と検索](rust-client.md)を参照してください。

This checklist prepares a Windows PC for using KohdaLab Shutter and uploading
server files to the Pico W.

## 1. Install system tools / ツールの導入

Install Rust, Git, and uv:

```powershell
winget install --id Rustlang.Rustup -e
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
cargo --version
```

## 2. Clone and build / 取得とビルド

```powershell
New-Item -ItemType Directory -Force -Path $HOME\pythonKernel
Set-Location $HOME\pythonKernel
git clone https://github.com/woolen-yarn/kohdalab-shutter.git kohdalab-shutter
Set-Location kohdalab-shutter
cargo build --release --locked
uv sync --all-extras --frozen
```

## 3. Prepare Wi-Fi config / Wi-Fi設定の準備

```powershell
Copy-Item server\wifi_config.example.py server\wifi_config.py
```

Edit `server\wifi_config.py` with the local SSID and password. This file is
ignored by Git.

## 4. Upload to Pico W / Pico Wへの転送

Connect the Pico W by USB and confirm MicroPython is installed.

```powershell
uv run mpremote connect auto fs cp server/main.py :main.py
uv run mpremote connect auto fs cp server/pca9685.py :pca9685.py
uv run mpremote connect auto fs cp server/servo.py :servo.py
uv run mpremote connect auto fs cp server/discovery.py :discovery.py
uv run mpremote connect auto fs cp server/settings.py :settings.py
uv run mpremote connect auto fs cp server/wifi_config.py :wifi_config.py
uv run mpremote connect auto reset
```

## 5. First hardware smoke test / 最初の実機確認

1. Confirm servo power and common ground.
2. Confirm channel wiring.
3. Start the Pico W server.
4. Check status from the PC.
5. Open and close one channel with a safe optical path.

```powershell
cargo run --bin kohdalab-shutter -- discover
cargo run --bin kohdalab-shutter -- --host 10.32.145.232 status
cargo run --bin kohdalab-shutter -- --host 10.32.145.232 open 0
cargo run --bin kohdalab-shutter -- --host 10.32.145.232 close 0
```

## 6. Start GUI / GUIを起動

```powershell
cargo run --release --bin kohdalab-shutter-gui
```
