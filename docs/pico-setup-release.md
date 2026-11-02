# KohdaLab Pico Setup 1.1.0

Add **Channel tuning** for per-channel Close/Open endpoints and opt-in **Soft Open / Soft Close**. No Python/uv installation is needed on the PC. The main Shutter control window/version is unchanged.

CHごとにClose／Open位置と **Soft Open／Soft Close** を調整する **Channel tuning** を追加しました。PCへのPython・uv導入は不要で、普段のShutter操作画面は変更しません。

## Use / 使い方

1. Extract the complete Windows/Mac ZIP, open Pico Setup, connect USB normally **without BOOTSEL**, and select Update.
2. Open **Channel tuning**. Reading stops the Pico program and saves a private backup; no settings are written yet. A fresh read replaces any previously queued edits.
3. Adjust only the channel you intend. For the reported cases, CH00 Soft Open provides a slower final approach; CH01 Close can be calibrated to a position that closes the shutter without pressing against a stop. No new endpoint is chosen automatically.
4. **Queue changes**, review the exact CH/field/value summary, then confirm **Update Pico**. Device identity and the original settings hash must still match. The updater preserves the existing `pca9685.py` and all its pulse calibration.
5. Restart initializes **all channels at their configured Close positions**, as existing firmware does. Check mechanical clearance before confirming Update; verify the real shutter afterward. GUI state remains commanded state, not position feedback.

1. ZIPをすべて展開してPico Setupを開き、**BOOTSELを押さずに**USB接続し、Updateを選びます。
2. **Channel tuning**で設定を読み込みます。Picoのプログラムを停止し、バックアップを保存します。この時点では書き込みません。再読込すると以前の未適用編集を置き換えます。
3. 必要なCHだけ変更します。CH00は **Soft Open** でOpen終端付近の指令をゆっくりにできます。CH01は、実物が閉じて機構を押し付けないClose位置を校正してください。角度は自動変更しません。
4. **Queue changes**で変更を準備し、CH・項目・値を確認して **Update Pico** を実行します。対象Picoや設定が読込時から変わっていれば書き込みを止めます。`pca9685.py`と`servo_min_us`／`servo_max_us`は上書きしません。
5. 更新後の再起動では、従来どおり**全CHを設定済みClose位置へ初期化**します。機構を確認してから更新を確定してください。設定後は実物を確認します。GUI表示は指令状態で、実測位置ではありません。

Soft motion is disabled by default. When explicitly enabled for a channel/direction, the final 12° uses at most 1° per at least 40 ms, while respecting already slower global settings. Other channels retain their own timing and endpoints; parallel capacity and PWM release/hold behavior are unchanged. This reduces commanded approach speed, but is not a confirmed cure for the reported physical stall/overshoot.

終端減速は既定で無効です。有効にしたCH・方向だけ、最後の12°を最大1°刻み・最短40ms間隔で進めます。既存設定がもっと遅い場合はその速度を保ちます。他CHのタイミング・角度、並列数、PWM解放／保持の方針は変えません。実機での行き過ぎ・停止が解消した確認ではありません。

Literal `CHANNELS` definitions are required for safe editing. Dynamic definitions/modifications are not executed or guessed. All unselected channel fields, pin mappings, Wi-Fi and labels are preserved. Cancelling the dialog does not write settings; restart the stopped Pico to resume its program, or finish Update.

安全な編集には定数で書かれた`CHANNELS`定義が必要です。動的な定義・変更は実行・推測せず止めます。未選択CH・ピン・Wi-Fi・ラベルを保持します。キャンセル時は設定を書き込まず、Picoのプログラム再開には再起動またはUpdate完了が必要です。

Native app smoke checks cover the bundled editor and USB helper success/failure without opening a serial port. Automated tests cover selective patches, stale-device/settings rejection, preserved pulse driver, exact endpoint bounds, retargeting and independent CH timing. MicroPython runtime verification exercises the actual motion scheduler. Physical USB/servo calibration remains unverified on the reported device.

Windows is unsigned; Mac is ad-hoc signed/not notarized. [Instructions](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/pico-upload.md)
