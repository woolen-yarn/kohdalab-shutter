Rust desktop controller with the light-window interface, Pico W discovery and external GUI API.

## Downloads / ダウンロード

- **Windows 10/11 (x64):** download `kohdalab-shutter-0.4.1-windows-x64.zip`, extract it, then open `kohdalab-shutter-gui.exe`. `Demo.cmd` opens a hardware-free preview.
- **Mac (macOS 13+, Apple Silicon + Intel):** download `kohdalab-shutter-0.4.1-macos-universal.dmg`, then drag `KohdaLab Shutter.app` to Applications. The ZIP is an alternative containing the same app.

**No Rust or Python installation is needed to run the desktop app.** The Pico W keeps its MicroPython firmware; initial firmware upload is a separate step.

PCでGUIを使うだけならRust・Pythonは不要です。Pico W側はMicroPythonを継続し、初回転送は別途必要です。

## Included / 内容

- Front-facing light window: Open reveals light, Close covers it; Moving / Unknown remain explicit.
- KohdaLab dark theme, concise English controls, version at the top.
- Horizontal / vertical layouts and ascending / descending channel order.
- Find Pico W, explicit selection among multiple controllers, calibrated shutter states.
- GUI-owned local API v2 and Python/Jupyter client support.
- Native GUI + CLI, license notices, build origin and SHA-256 checksums.

Builds are **not publisher-signed or Apple-notarized**; Windows or macOS may prompt on first launch. Read the [installation guide](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md) for platform instructions. The Mac app is ad-hoc signed for integrity, not trusted-publisher identification.

Validation includes native builds/tests on Windows, Mac and Linux; packaged CLI entry points on Windows, Apple Silicon and Intel; universal Mach-O and app-signature verification; DMG integrity; and simulated GUI/API checks. This does not establish physical Pico/Wi-Fi/servo validation.

[Installation / 導入](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md) · [Pico W setup / 実機設定](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/rust-client.md) · [External API / 外部制御](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/gui-api.md)
