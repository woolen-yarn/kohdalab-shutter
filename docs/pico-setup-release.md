# KohdaLab Pico Setup 1.1.1

Restore physical CH buttons while connected over LAN. A short press toggles its channel even when a PC holds the channel lease. The connected Shutter GUI follows the commanded state on its next refresh, normally about one second. Other PCs remain locked out; a physical press does not disconnect the owner or release its channels. Long-press server start/stop and connected LED patterns are unchanged.

LAN接続中も物理CHボタンを使用できるように修正しました。PCが使用中のCHも短押しで切り替えられ、GUIは次回更新（通常約1秒）で指令状態に追従します。他PCへのロックは維持し、物理操作で接続やロックは解除しません。長押しでのサーバー開始・停止と接続中LEDパターンは従来どおりです。

## Update / 更新

1. Extract the complete ZIP and open Pico Setup 1.1.1. Connect USB normally **without BOOTSEL** and close other applications using the Pico.
2. Select **Update · keep settings** and the target Pico, then **Update Pico**. No channel tuning is needed for this fix.
3. Confirm completion, start Wi-Fi and reconnect the usual Shutter GUI. Test a short press of the corresponding physical CH button.

1. ZIPをすべて展開してPico Setup 1.1.1を開きます。**BOOTSELを押さずに**USB接続し、Picoを使用する他のアプリを終了します。
2. 対象Picoと **Update · keep settings** を選び、**Update Pico**を実行します。この修正のためのChannel tuning操作は不要です。
3. 完了後にWi-Fiを開始し、普段のShutter GUIで接続して対応CHの物理ボタン短押しを確認してください。

Update preserves existing per-CH calibration, gentle approach settings, Wi-Fi, labels and the existing `pca9685.py`, including individually edited pulse limits. The desktop control app does not need an update. As before, restarting the Pico initializes **all CHs at their configured Close positions**; check mechanical clearance before confirming Update.

更新はCH別校正・終端減速設定・Wi-Fi・ラベル・既存の`pca9685.py`（個別のパルス幅設定を含む）を保持します。PCの操作GUIの更新は不要です。再起動時には従来どおり**全CHが設定済みClose位置へ初期化**されるため、機構を確認してから更新を確定してください。

Automated tests exercise local toggles during an active lease, the state returned to a connected client, retained ownership, and continued rejection of unauthorized network commands. Native package smoke tests do not open USB. Physical Pico/servo operation remains unverified.

Windows is unsigned; Mac is ad-hoc signed/not notarized. [Instructions](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/pico-upload.md)
