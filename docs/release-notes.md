## Changes / 変更内容

- **Separate connection screen:** select a labelled Pico W, choose available CHs, then Connect. Labels are saved on the Pico and shared by every PC.
- **CH locking:** selected channels are locked on the Pico. Other users can use the remaining CHs; overlapping selections are rejected atomically.
- **Compact controls:** only selected CHs, a small status/version header, Open/Close and scoped All actions. Layout/order/API options are in ···.
- **Connected LEDs:** each acquired CH repeats two short flashes. Disconnect releases immediately; network loss/crashes release after 15 seconds while holding shutter state.

## Pico update required / Pico側の更新が必要です

Upload v0.5.0 `server/main.py` and new `server/sessions.py` by USB, then restart. Preserve your calibrated `settings.py`, Wi-Fi credentials and saved `device_config.json`. Old firmware is refused by the new GUI because it cannot enforce these locks. [Update instructions](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md#pico-firmware-update--pico側の更新)

Picoの`main.py`と新しい`sessions.py`を転送してください。既存の校正・ピン・Wi-Fi/IP設定は保持します。GUIだけの更新ではCHロック・二連点滅は使えません。

## Downloads / ダウンロード

- Windows x64: `kohdalab-shutter-0.5.0-windows-x64-Setup.exe` (portable ZIP also available).
- macOS 13+, Apple Silicon/Intel: `kohdalab-shutter-0.5.0-macos-universal.dmg` (ZIP also available).

No Rust/Python is required for the desktop app. Windows remains unsigned; Mac is ad-hoc signed and not notarized, pending provider setup.

Validated with multi-PC protocol simulations and three real GUI processes connected to a simulated Pico: disjoint CH sharing, overlap rejection, scoped All actions and disconnect release. Physical Pico/LED/servo validation remains a separate hardware check; no hardware is flashed automatically.

[Installation](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md) · [External API](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/gui-api.md)
