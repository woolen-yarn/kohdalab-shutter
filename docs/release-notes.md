## Changes / 変更内容

- Click the light window to toggle a shutter; separate Open/Close buttons are removed.
- Each CH number sits above its editable name box. Click to edit, Enter to apply. Escape or clicking elsewhere discards unconfirmed edits. Confirmed names save automatically and remain shared through the Pico.
- Disconnect is in the connection-name menu at the top. Status and version share one compact header; ··· opens Settings for Pico name, layout, order and local API.
- The connection picker places controllers on the left and a vertical CH list on the right, with a standard-sized Connect button at the bottom.
- A click during background polling waits for that refresh once. Commands are never retried after a lost reply. External API behavior is unchanged.

CH番号・名前欄・光の窓だけに操作画面を整理しました。名前はEnterで確定し自動保存、光の窓を押すと開閉を切り替えます。Disconnectは上部の接続名メニューにまとめました。接続画面は機器と縦並びのCH一覧を左右に配置しています。

## Pico update / Pico側の更新

**No Pico update is needed if v0.6.0 firmware is already installed.** This release changes only the desktop GUI. For firmware older than v0.6.0, follow the [Pico update instructions](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md#pico-firmware-update--pico側の更新). Existing calibration, Wi-Fi settings and saved names are preserved; no hardware is flashed automatically.

v0.6.0導入済みのPicoは再更新不要です。旧ファームウェアからは導入手順に従って更新してください。

## Downloads / ダウンロード

- Windows x64: `kohdalab-shutter-0.6.1-windows-x64-Setup.exe` (portable ZIP also available).
- macOS 13+, Apple Silicon/Intel: `kohdalab-shutter-0.6.1-macos-universal.dmg` (ZIP also available).

Windows remains unsigned; Mac remains ad-hoc signed and not notarized pending provider setup.

Validation includes actual egui pointer/keyboard interactions, single queued Toggle and failure cancellation, channel ownership, isolated multi-GUI/API sessions and native packaging checks. Images use simulated hardware; physical Pico/servo checks remain separate.

[Install/update](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/install.md)
