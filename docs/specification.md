# Kohda Lab Shutter Controller Specification / 仕様書

## Purpose / 目的

**JP:** Pico W をサーバ、PC をクライアントとして、光学系のサーボ式シャッターを Wi-Fi 経由で操作します。各チャンネルは物理ボタン、赤/緑 LED、サーボ 1 個で構成します。

**EN:** The Pico W acts as the server and the PC acts as the client. The system controls servo-driven optical shutters over Wi-Fi. Each channel consists of one physical button, one red LED, one green LED, and one servo.

## Responsibility Split / 役割分担

| Area | Path | Role / 役割 |
| --- | --- | --- |
| Pico server | `server/main.py` | GPIO, LEDs, buttons, Wi-Fi, TCP command handling / GPIO、LED、ボタン、Wi-Fi、TCPコマンド処理 |
| Servo driver | `server/pca9685.py` | PCA9685 50 Hz PWM generation / PCA9685 の 50Hz PWM 生成 |
| Server settings | `server/settings.py` | Pins, IP, port, channel definitions / ピン、IP、ポート、チャンネル定義 |
| Wi-Fi secret | `server/wifi_config.py` | SSID and password, do not share / SSID とパスワード。共有しない |
| PC CLI | `client/cli.py` | Command-line operation / コマンドライン操作 |
| PC GUI | `client/gui.py` | PySide6 / Qt operation screen / PySide6 / Qt 操作画面 |
| PC transport | `client/transport.py` | TCP one-line command communication / TCP 1行コマンド通信 |

## Network / ネットワーク

| Item | Value |
| --- | --- |
| Pico IP | `10.32.145.232` |
| TCP port | `12345` |
| Protocol | TCP, line-based text |
| Encoding | UTF-8 |
| Connection model | 1 connection = 1 command |

**JP:** サーバは 1 接続につき 1 行のコマンドを読み、1 行の応答を返して接続を閉じます。

**EN:** The server reads one line of command per TCP connection, returns one line of response, and then closes the connection.

## Commands / コマンド

| Command | Response | Meaning / 意味 |
| --- | --- | --- |
| `STATUS` | `CH0=0,CH1=90,...` | Return all channel angles / 全チャンネルの現在角度を返す |
| `OPEN n` | `OK` / `ERR` | Move channel n to the open angle / チャンネル n を open 角へ動かす |
| `CLOSE n` | `OK` / `ERR` | Move channel n to the close angle / チャンネル n を close 角へ動かす |
| `TOGGLE n` | `OK` / `ERR` | Toggle channel n / チャンネル n を反転する |
| Unknown | `UNKNOWN` | Undefined command / 未定義コマンド |

**JP:** `n` は 0 始まりのチャンネル番号です。現在の 4CH 構成では `0..3` です。

**EN:** `n` is a zero-based channel number. In the current 4-channel setup, valid values are `0..3`.

## Channel Model / チャンネルモデル

**JP:** チャンネルは `server/settings.py` の `CHANNELS` で定義します。

**EN:** Channels are defined in `CHANNELS` inside `server/settings.py`.

| Key | Meaning / 意味 |
| --- | --- |
| `label` | Display label / 表示用ラベル |
| `servo` | PCA9685 output channel / PCA9685 の出力チャンネル |
| `switch` | Pico GPIO, pull-up input, active low / Pico GPIO。プルアップ入力、押下時 Low |
| `green` | Pico GPIO for OPEN LED / OPEN 状態表示 LED |
| `red` | Pico GPIO for CLOSE LED / CLOSE 状態表示 LED |
| `close` | CLOSE angle, currently 0 deg / CLOSE 角度。現在は 0 度 |
| `open` | OPEN angle, currently 90 deg / OPEN 角度。現在は 90 度 |

**JP:** サーバの `STATUS` は `CHANNELS` の順番で `CH0`, `CH1`, ... を返します。PC 側 GUI は `STATUS` のチャンネル一覧から操作行を生成します。

**EN:** The server returns `CH0`, `CH1`, ... in the order of `CHANNELS`. The PC GUI creates its control rows from the channel list returned by `STATUS`.

## LED Behavior / LED 仕様

| Mode | Condition / 条件 | Behavior / 動作 |
| --- | --- | --- |
| NORMAL | Server stopped or normal idle / サーバ停止中、通常待機 | Red for CLOSE, green for OPEN / CLOSE なら赤点灯、OPEN なら緑点灯 |
| BLINK | TCP server running / TCP サーバ起動中 | Blink the state LED at about 250 ms / 現在状態に対応する LED を約 250 ms 周期で点滅 |
| FAST | Button long-press in progress / ボタン長押し中 | Blink all red/green LEDs at about 60 ms / 全チャンネルの赤/緑 LED を約 60 ms 周期で高速点滅 |

## Button Behavior / ボタン仕様

| Input | Behavior / 動作 |
| --- | --- |
| Short press / 短押し | Toggle the corresponding channel / 対応チャンネルをトグル |
| Long press for 3 seconds or more / 3秒以上長押し | Start or stop the TCP server / TCP サーバ開始/停止 |

**JP:** 長押し中は FAST 点滅し、ボタンを離したタイミングでサーバ開始/停止を実行します。

**EN:** While a button is held long enough, the LEDs enter FAST blinking mode. The server start/stop action is executed when the button is released.

## Servo Behavior / サーボ仕様

**JP:** PCA9685 は 50Hz で動作します。標準設定ではサーボパルス幅を 500us から 2500us へ線形変換し、0 度から 180 度に対応させます。現在のシャッター制御では `close=0`, `open=90` を使います。

**EN:** The PCA9685 runs at 50 Hz. By default, servo pulse width is mapped linearly from 500 us to 2500 us, corresponding to 0 to 180 degrees. The current shutter control uses `close=0` and `open=90`.

## n-Channel Expansion Rules / nCH 拡張ルール

1. **JP:** `server/settings.py` の `CHANNELS` にチャンネル定義を追加します。  
   **EN:** Add channel definitions to `CHANNELS` in `server/settings.py`.
2. **JP:** 追加した PCA9685 出力へサーボ信号線を接続します。  
   **EN:** Connect each new servo signal line to the assigned PCA9685 output.
3. **JP:** 追加した GPIO へスイッチ、赤 LED、緑 LED を接続します。  
   **EN:** Connect the switch, red LED, and green LED to the assigned GPIO pins.
4. **JP:** Pico へ `settings.py` を再転送して再起動します。  
   **EN:** Upload the updated `settings.py` to the Pico and reboot it.
5. **JP:** PC 側 GUI/CLI は原則変更不要です。  
   **EN:** The PC GUI/CLI usually does not require changes.

## Constraints / 制約

- **JP:** PCA9685 1 枚のサーボ出力は最大 16CH です。  
  **EN:** One PCA9685 board supports up to 16 servo outputs.
- **JP:** Pico GPIO はボタンと LED で 1CH あたり 3 本使います。GPIO 数に注意してください。  
  **EN:** Each channel uses three Pico GPIO pins for the button and LEDs, so watch the GPIO count.
- **JP:** サーボの電流は Pico の USB 給電だけでは不足しやすいです。サーボ用外部電源と GND 共通化を前提にしてください。  
  **EN:** Servo current often exceeds what Pico USB power can comfortably provide. Use an external servo supply and share ground.
- **JP:** 16CH を超える場合は PCA9685 の I2C アドレスを変えて複数枚化する設計が必要です。現コードは PCA9685 1 枚を前提にしています。  
  **EN:** For more than 16 channels, multiple PCA9685 boards with different I2C addresses are required. The current code assumes one PCA9685 board.

## Troubleshooting / エラーと確認ポイント

| Symptom / 症状 | Check / 確認 |
| --- | --- |
| PC cannot connect / PC から接続できない | Check that the Pico server was started by long press and that the IP is `10.32.145.232` / Pico 側サーバが長押しで起動しているか、IP が `10.32.145.232` か |
| `Wi-Fi config missing` | Check that `server/wifi_config.py` was uploaded to the Pico / `server/wifi_config.py` を Pico へ転送したか |
| LEDs work but servo does not / LED は動くがサーボが動かない | Check PCA9685 power, I2C, servo power, and common GND / PCA9685 電源、I2C、サーボ電源、GND 共通を確認 |
| Channel order is wrong / チャンネルがずれる | Check `CHANNELS` order, PCA9685 channel numbers, and physical labels / `CHANNELS` の順番、PCA9685 チャンネル、物理ラベルを確認 |
| GUI shows `ERROR` or `UNKNOWN` / GUI に `ERROR` または `UNKNOWN` が出る | `STATUS` failed or the angle is not equal to the configured open/close angle / `STATUS` 取得失敗、または角度が open/close 以外 |
