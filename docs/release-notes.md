## Changes / 変更内容

- Removed the GUI All buttons; each shutter is identified primarily by its name, with a small CH number.
- **··· → Settings** now groups Pico name, CH names, layout, order and Local control API. Valid edits save automatically after a short pause; Saved is shown only after acknowledgement. Save failures leave controls connected and allow Retry.
- Pico/CH names are persisted on the Pico and shared with other PCs. Atomic patches preserve other users' names, calibration, Wi-Fi and unrelated config keys.
- PC preferences use `~/.kohdalab/shutter/config.json` (`%USERPROFILE%\.kohdalab\shutter\config.json` on Windows). Layout/order/CH selection/network/API opt-in restore automatically; ownership and credentials never persist, and startup does not automatically acquire hardware.
- Windows Setup now installs to `C:\Program Files\Kohdalab\KohdaLab Shutter` for all users and requires administrator approval. Mac uses `/Applications/KohdaLab Shutter.app`. Existing files/installations are not automatically migrated or deleted.

## Pico update / Pico側の更新

Update both `server/main.py` and `server/sessions.py` from v0.6.0. Preserve existing `settings.py`, Wi-Fi credentials and `device_config.json`; the existing device name is retained. Desktop update alone cannot provide persistent CH names.

Pico側の`main.py`と`sessions.py`も更新してください。既存の校正・Wi-Fi・保存済みラベルは上書きしません。実機への自動転送は行いません。

## Downloads / ダウンロード

- Windows x64: `kohdalab-shutter-0.6.0-windows-x64-Setup.exe` (portable ZIP also available).
- macOS 13+, Apple Silicon/Intel: `kohdalab-shutter-0.6.0-macos-universal.dmg` (ZIP also available).

Windows remains unsigned; Mac remains ad-hoc signed and not notarized pending provider setup.

Validation covers atomic label persistence, ownership checks, rapid edits/late acknowledgements, save failure, restart restoration, corrupt/foreign config preservation, MicroPython runtime compatibility, and native packaging/install tests. Physical Pico/servo/LED checks remain separate; no hardware was flashed automatically.

[Install/update](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md)
