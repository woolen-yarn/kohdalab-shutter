# KohdaLab Pico Setup 1.0.1

For an **existing shutter update, connect USB normally without holding BOOTSEL**, then select Update. BOOTSEL exposes a UF2 mass-storage drive, not the USB serial interface used to update Python files. Do not reinstall MicroPython merely to update an existing controller.

**既存シャッターの更新はBOOTSELを押さずにUSB接続し、Updateを選んでください。** BOOTSELはMicroPython本体を書き込むUF2ドライブのモードで、プログラム更新用のUSB通信とは別です。更新のためにMicroPythonを入れ直す必要はありません。

- Detect labelled BOOTSEL drives and explain how to reconnect for Update. Never write to or reflash a BOOTSEL drive automatically.
- Refresh USB metadata automatically after reconnection, retaining explicit selection when several devices are present. Disable upload when there is no serial target; keep the last result readable.
- Correctly propagate the embedded backend's returned failure code. A failed verification/commit no longer continues to automatic restart or reports success through an ignored backend result.
- Preserve the existing `pca9685.py` driver byte-for-byte on Update, including individually tuned `servo_min_us` / `servo_max_us`. Unsupported legacy APIs or custom main-side initialization stop with CALIBRATION_REVIEW before uploading, rather than guessing or overwriting calibration. Initial setup remains unchanged.
- Show the failed step and a safe diagnostic code (USB_ACCESS, USB_TIMEOUT, PICO_RESPONSE, PICO_MEMORY, PICO_MODULE, PICO_SYNTAX, PICO_SPACE or USB_COMMAND). Status text can be selected/copied. Private device output and Wi-Fi source are never displayed or saved as public logs.

更新では既存の`pca9685.py`を転送対象から外し、`servo_min_us`・`servo_max_us`などの個体別調整を残します。古いドライバーや独自の初期化を自動確認できなければ、上書きせずCALIBRATION_REVIEWで止めます。

BOOTSEL接続時の案内・つなぎ直し時の自動検出・失敗段階とエラーコードを追加しました。同梱転送プログラムの失敗結果を取りこぼしていた問題も修正しています。1.0.0で報告された実機の失敗原因は、旧表示だけでは断定できません。修正版のエラーコードで切り分けられるようにしています。

Python/uv installation on the PC is still unnecessary. Download and extract the native Windows x64, Mac Apple Silicon (arm64), or Mac Intel (x64) ZIP and open the exe/app. Keep the Windows folder together. DHCP, backups, existing Wi-Fi/calibration/pins/motion settings and labels retain their previous behavior. The main Shutter desktop app/version is unchanged.

PCへのPython・uv導入は引き続き不要です。Windows／Mac用ZIPをすべて展開してexe／appを開きます。DHCP・バックアップ・既存設定保持の動作は変更していません。メインのShutterアプリもそのまま使えます。

Native smoke tests now verify both backend success and expected failure without opening a USB port. Automated tests cover failure propagation, no restart after failed commit, BOOTSEL metadata, reconnection and safe error output. Physical USB/Wi-Fi/servo validation and confirmation of the reported Windows device failure remain pending; no hardware was flashed automatically.

配布テストは転送機能の成功・失敗を両方確認し、USBポートは開きません。BOOTSEL判別・再検出・失敗後の再起動防止・エラー表示は自動テスト済みです。報告されたWindows実機での再確認は未実施です。

Windows remains unsigned; Mac remains ad-hoc signed and not notarized. First-launch OS confirmation can still appear.

[Instructions / 手順](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/pico-upload.md)

A separate report of one shutter becoming unresponsive while other channels work, recovering only after power cycling, is not diagnosed by this release. Software tests verify that full-off is cleared on a subsequent PWM command without disturbing other channels; physical servo/power/driver behavior still needs checking. No automatic repeated drive, wider pulse limits or changed release/torque policy is introduced.

一つのCHだけ動かなくなり、電源再投入で戻る症状は未解決です。PWM停止後の再指令で停止ビットが解除され、他CHに書き込まないことはテストしていますが、実際のサーボ・電源・ドライバーの原因は未確定です。自動再駆動・パルス幅拡大・保持トルク設定変更は行いません。
