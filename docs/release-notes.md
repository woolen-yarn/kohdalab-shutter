## Changes / 変更内容

- **Parallel All actions:** updated Pico settings allow all configured channels to move concurrently instead of waiting for the previous channel's movement and settling delay.
- **Connect / Disconnect:** both controls are visible in the Connection panel.
- **Stable layout:** background status polling no longer inserts a Connected message above the shutter cards, and the progress indicator uses fixed geometry. Horizontal and Vertical layouts stay in place during refreshes.
- Includes the shared KohdaLab signing-policy preparation and Windows product metadata. These binaries are still not publisher-signed/Apple-notarized; no production signing is claimed.

**Pico update required for parallel movement:** edit `SERVO_MAX_ACTIVE` in the device's existing `settings.py` to the channel count (e.g. `4` for four channels), then restart. Preserve calibrated angles, wiring and Wi-Fi/IP settings. The source default is `SERVO_MAX_ACTIVE = len(CHANNELS)` after the channel definitions. Updating only the desktop cannot change the device's current limit.

**並列動作にはPico側の設定変更も必要です。** 実機の既存`settings.py`で`SERVO_MAX_ACTIVE`をCH数（4台なら`4`）へ変更し、再起動してください。校正角度・ピン・Wi-Fi/IP設定は変更しません。GUIだけの更新では実機の同時駆動数は変わりません。

## Downloads / ダウンロード

- **Windows 10/11 (x64):** download `kohdalab-shutter-0.4.2-windows-x64.zip`, extract it, then open `kohdalab-shutter-gui.exe`. `Demo.cmd` opens a hardware-free preview.
- **Mac (macOS 13+, Apple Silicon + Intel):** download `kohdalab-shutter-0.4.2-macos-universal.dmg`, then drag `KohdaLab Shutter.app` to Applications. The ZIP is an alternative containing the same app.

**No Rust or Python installation is needed to run the desktop app.** Initial Pico firmware setup and Python/Jupyter integration remain separate steps.

Builds are **not publisher-signed or Apple-notarized**; Windows or macOS may prompt on first launch. Read the [installation guide](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md). The Mac app is ad-hoc signed for integrity; SignPath acceptance and Apple enrollment/credentials remain pending.

Validation includes Windows/Mac/Linux tests and builds, native packaging/metadata checks, Intel Mac package checks, simulated GUI/API checks, fixed-position egui rendering during pending refreshes and simulated parallel Pico movement. Physical Pico/Wi-Fi/servo validation remains an owner hardware check.

[Installation / 導入](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md) · [Pico W setup / 実機設定](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/rust-client.md) · [External API / 外部制御](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/gui-api.md)
