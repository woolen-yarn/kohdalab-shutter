# KohdaLab Pico Setup 1.2.0

## Changes

- **Incomplete commands are rejected.** The Pico runs a TCP command only after the complete line arrives. A request cut off before its newline is answered with `UNKNOWN` and moves nothing.
- **An I2C fault stops one channel, not the controller.** If a PWM write fails, that channel keeps its last successfully written angle and stops. Its red and green LEDs alternate every 100 ms. The Pico tries once to release the PWM output. Other channels, the buttons and the network keep working. The next command for that channel, from its button or from a PC, clears the fault and tries again. There is no automatic retry and no automatic reboot.
- **A missing PCA9685 at startup is shown.** All channels show the fault pattern, and servo drive and the network stay off until you check the hardware and cycle power.
- **Wi-Fi loss is detected.** While the server runs, the Pico checks the connection every two seconds. On loss it closes its sockets, clears channel leases, and reconnects in the background, with a new attempt every ten seconds. The state LED is on for one second and off for one second during reconnection. Buttons and servo motion continue. A three-second long press cancels reconnection.
- The safety notes and specification now state that every power-on or reset drives all channels to their Close angle. This behaviour is unchanged.

## Compatibility and migration

1. Make the optical path safe. Extract the complete ZIP and open Pico Setup 1.2.0. Connect USB normally **without BOOTSEL** and close other applications using the Pico.
2. Select **Update · keep settings** and the target Pico, then **Update Pico**. No channel tuning is needed.
3. Confirm completion, start Wi-Fi and reconnect the Shutter GUI.

Update preserves per-channel calibration, gentle approach settings, Wi-Fi, labels and the existing `pca9685.py`, including individually edited pulse limits. It keeps a private backup. Restarting the Pico drives **all channels to their configured Close positions**; check mechanical clearance before confirming Update.

Desktop 0.6.10 is needed to see `Fault` in the GUI, the CLI and the GUI API. Older desktop versions keep working with this firmware and ignore the fault report. After Wi-Fi returns, reconnect from the desktop manually; rediscover the Pico if its address changed. To return to the previous firmware, run Update from Pico Setup 1.1.1.

## Validation and provenance

**This firmware has not been run on a physical Pico W or servos.** Automated tests cover fault isolation and recovery, startup failure, Wi-Fi loss and reconnection, and command framing with simulated hardware, and the session and motion logic also runs under MicroPython 1.24.1 on Linux. Native package smoke tests do not open USB. Try it on low-risk hardware first and watch the first motions.

Windows is unsigned; Mac is ad hoc signed and not notarized. [Instructions](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/pico-upload.md)

## 日本語

- **途中で切れたコマンドを実行しません。** TCPコマンドは改行まで届いたときだけ実行します。途中で止まった要求には`UNKNOWN`を返し、何も動かしません。
- **I2C異常で止まるのはそのCHだけです。** PWMの書き込みに失敗すると、そのCHは最後に書き込みが成功した角度を保持して止まり、赤と緑のLEDが100 msごとに交互に点灯します。PWM出力の解放を1回試みます。他のCH・ボタン・通信は動き続けます。そのCHへの次の指令（ボタンまたはPC）で異常を解除して再試行します。自動の再試行と自動再起動はありません。
- **起動時にPCA9685が見つからない場合：** 全CHが異常表示になり、駆動と通信を開始しません。機器を確認して電源を入れ直してください。
- **Wi-Fi切断を検出します。** サーバー動作中は2秒ごとに接続を確認します。切断するとソケットを閉じてCHの確保を解除し、10秒ごとに再接続を試みます。再接続中は状態LEDが1秒点灯・1秒消灯します。ボタンとサーボは動き続けます。3秒長押しで再接続を中止できます。
- 電源投入・リセットのたびに全CHをClose角へ動かすことを、安全上の注意と仕様書に明記しました。挙動は変わりません。

**更新手順：** 光路を安全な状態にします。ZIPをすべて展開してPico Setup 1.2.0を開き、**BOOTSELを押さずに**USB接続して、Picoを使用する他のアプリを終了します。対象Picoと **Update · keep settings** を選び、**Update Pico**を実行します。Channel tuningの操作は不要です。完了後にWi-Fiを開始し、Shutter GUIで接続し直してください。

更新はCH別校正・終端減速設定・Wi-Fi・ラベル・既存の`pca9685.py`（個別のパルス幅設定を含む）を保持し、バックアップを残します。再起動時には**全CHが設定済みClose位置へ動く**ため、機構を確認してから更新を確定してください。

GUI・CLI・GUI APIで`Fault`を見るにはデスクトップ0.6.10が必要です。旧デスクトップ版もこのファームウェアで動作し、異常の報告を無視します。Wi-Fi復帰後はPCから手動で接続し直してください。以前のファームウェアへ戻すには、Pico Setup 1.1.1でUpdateを実行します。

**このファームウェアは実機のPico W・サーボでは動かしていません。** 自動テストは模擬ハードウェアで、異常の隔離と復帰、起動時の失敗、Wi-Fiの切断と再接続、コマンドの区切りを確認しています。セッションと駆動のロジックはLinux上のMicroPython 1.24.1でも実行しています。配布アプリの起動確認ではUSBを開きません。まず影響の小さい機器で試し、最初の動作を見守ってください。

Windows版は未署名、Mac版はアドホック署名でApple公証は受けていません。[手順](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/pico-upload.md)
