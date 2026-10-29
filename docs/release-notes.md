## Changes / 変更内容

- **Windows Setup.exe:** install KohdaLab Shutter for the current user without administrator rights. Launch from the Start menu or desktop; a Demo shortcut is also included.
- Run the new Setup with the app closed to update. Uninstall through Windows Settings → Apps. User settings and unrelated files are preserved.
- WindowsのSetup形式に対応しました。インストール後はスタートメニュー・デスクトップから起動できます。更新は新しいSetupの実行、削除はWindowsの「設定 → アプリ」から行えます。
- The portable Windows ZIP and Mac Universal DMG/ZIP remain available. Parallel All actions, Connect/Disconnect and the stable dark GUI from v0.4.2 are included.

**Pico update required for parallel movement:** edit `SERVO_MAX_ACTIVE` in the device's existing `settings.py` to the channel count (e.g. `4` for four channels), then restart. Preserve calibrated angles, wiring and Wi-Fi/IP settings. The source default is `SERVO_MAX_ACTIVE = len(CHANNELS)` after the channel definitions. Updating only the desktop cannot change the device's current limit.

**並列動作にはPico側の設定変更も必要です。** 実機の既存`settings.py`で`SERVO_MAX_ACTIVE`をCH数（4台なら`4`）へ変更し、再起動してください。校正角度・ピン・Wi-Fi/IP設定は変更しません。GUIだけの更新では実機の同時駆動数は変わりません。

## Downloads / ダウンロード

- **Windows 10/11 (x64):** `kohdalab-shutter-0.4.3-windows-x64-Setup.exe`. The ZIP is an alternative for portable use.
- **Mac (macOS 13+, Apple Silicon + Intel):** `kohdalab-shutter-0.4.3-macos-universal.dmg`. Drag KohdaLab Shutter.app to Applications; the ZIP contains the same app.

**No Rust or Python installation is needed to run the desktop app.** Initial Pico firmware setup and Python/Jupyter integration remain separate steps.

Windows Setup, its uninstaller and application executables are **unsigned**. The Mac app is ad-hoc signed and **not Apple-notarized**. Existing first-launch prompts may remain; SignPath acceptance and Apple enrollment/credentials are pending. See the [installation guide](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md).

Release checks include native Windows installation/reinstallation/uninstallation, shortcuts and registry entries, packaged CLI startup, platform tests/builds, Mac app verification and SHA-256 verification before publication. Physical Pico/Wi-Fi/servo checks remain separate.

[Installation / 導入](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md) · [Pico W setup / 実機設定](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/rust-client.md) · [External API / 外部制御](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/gui-api.md)
