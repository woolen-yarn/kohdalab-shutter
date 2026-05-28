# Purchase List / 購入品リスト

Last checked / 確認日: 2026-05-28

This list is organized for the current 4-channel shutter controller. Amazon product titles, availability, and prices can change, so use the links as purchase references rather than fixed specifications.

このリストは現在の4CHシャッター制御装置を基準にしています。Amazonの商品名、在庫、価格は変わる可能性があるため、リンクは購入候補として扱ってください。

## Summary / 分類

- Controller board / 制御ボード周り
- Channel switch and LED boards / スイッチ・LED周り
- Servo and shutter mechanism / サーボ・シャッター機構
- Wiring and power / 配線・電源周り
- Additional required parts / リンク未指定だが必要なもの

## Controller Board / 制御ボード周り

| Item / 品名 | Buy Qty / 購入数 | Used Qty / 使用数 | Purpose / 用途 | Link |
| --- | ---: | ---: | --- | --- |
| PENGLIN USB 2.0 power cable, 2-core cut end, 30cm, 5-pack / USB 2.0 延長ケーブル 充電用 2芯 切りっぱなし 5本セット | 1 set | 1-2 cables | 5V/GND power input wiring for the controller or servo power rail. / 制御基板またはサーボ電源ラインへの5V/GND引き込み | [Amazon B0DR4265M7](https://www.amazon.co.jp/dp/B0DR4265M7?ref=fed_asin_title&th=1) |

## Channel Switch and LED Boards / スイッチ・LED周り

| Item / 品名 | Buy Qty / 購入数 | Used Qty / 使用数 | Purpose / 用途 | Link |
| --- | ---: | ---: | --- | --- |
| Audiofan mini breadboard, 170 tie-points, 47mm x 35mm, white, 2-pack / ミニサイズ ブレッドボード 170穴 2点セット | 2 sets | 4 boards | One small board per channel for switch, red LED, green LED, and label. / 各CHの押しボタン、赤LED、緑LED、チャンネル表示用 | [Amazon B09BDWQ1KZ](https://www.amazon.co.jp/dp/B09BDWQ1KZ?ref=fed_asin_title&th=1) |

## Servo and Shutter Mechanism / サーボ・シャッター機構

| Item / 品名 | Buy Qty / 購入数 | Used Qty / 使用数 | Purpose / 用途 | Link |
| --- | ---: | ---: | --- | --- |
| MG996R metal gear digital servo / MG996R メタルギア・デジタルサーボ | 4 pcs | 4 pcs | One servo per shutter channel. / 各シャッターを開閉する駆動用サーボ | [Amazon B010SLRAAS](https://www.amazon.co.jp/dp/B010SLRAAS?ref=fed_asin_title) |
| Servo motor bracket mount kit / サーボモーターブラケット・サーボマウントブラケット | 4 kits | 4 kits | Mechanical mounting for each servo. Confirm actual package contents before ordering. / 各サーボを固定するためのブラケット。購入前に内容物数を確認 | [Amazon B09535CQ59](https://www.amazon.co.jp/dp/B09535CQ59?ref=fed_asin_title) |
| Mallofusa round servo horn, 25T, 5-pack / マロフサ 丸型サーボホーン 25T 5個セット | 1 set | 4 horns | Coupling between servo shaft and shutter plate/linkage. One spare remains for 4CH. / サーボ軸とシャッター板・リンク機構の接続。4CHでは1個予備 | [Amazon B00NOGMK3M](https://www.amazon.co.jp/dp/B00NOGMK3M?ref=fed_asin_title) |

## Wiring and Power / 配線・電源周り

| Item / 品名 | Buy Qty / 購入数 | Used Qty / 使用数 | Purpose / 用途 | Link |
| --- | ---: | ---: | --- | --- |
| GTIWUNG 3-pin servo extension cable, male-female, 30-pack, mixed lengths / 3ピンサーボ延長ケーブル 30本セット | 1 set | 4 or more | Extends servo signal/power/GND wiring between the PCA9685/controller area and the servo locations. / PCA9685・制御基板側から各サーボ位置までの3線延長 | [Amazon B0833S1WJ2](https://www.amazon.co.jp/dp/B0833S1WJ2?ref=fed_asin_title&th=1) |
| PENGLIN USB 2.0 power cable, 2-core cut end, 30cm, 5-pack / USB 2.0 延長ケーブル 充電用 2芯 切りっぱなし 5本セット | 1 set | 1-2 cables | Also useful for power input harnesses and quick 5V test leads. / 電源引き込みハーネス、5V試験用リードとしても使用 | [Amazon B0DR4265M7](https://www.amazon.co.jp/dp/B0DR4265M7?ref=fed_asin_title&th=1) |

## Additional Required Parts / リンク未指定だが必要なもの

The Amazon links above do not cover every part visible in the photos or required by the code. Prepare the following separately.

上記リンクだけでは、写真やコード上で必要な部品をすべてはカバーしていません。次の部品は別途用意してください。

| Item / 品名 | Qty for 4CH / 4CH数量 | Purpose / 用途 | Notes / 備考 |
| --- | ---: | --- | --- |
| Raspberry Pi Pico W | 1 | Wi-Fi server and GPIO controller. / Wi-Fiサーバ、GPIO制御 | MicroPython firmware required. / MicroPythonを書き込み |
| PCA9685 16-channel PWM servo driver board | 1 | Servo PWM generation over I2C. / I2C経由でサーボPWMを生成 | Current code assumes one board at address `0x40`. / 現コードは`0x40`の1枚前提 |
| Main breadboard or prototyping board / メインブレッドボードまたはユニバーサル基板 | 1 | Pico W, PCA9685, terminal blocks, and power distribution. / Pico W、PCA9685、端子台、電源分配用 | Size depends on final enclosure. / ケース寸法に合わせる |
| Tactile switch or push button / 押しボタン | 4 | Local channel toggle and server start/stop long press. / CH切替、サーバ開始/停止長押し | 1 per channel. / 1CHあたり1個 |
| Red LED / 赤LED | 4 | CLOSE indicator. / CLOSE表示 | 1 per channel. / 1CHあたり1個 |
| Green LED / 緑LED | 4 | OPEN indicator. / OPEN表示 | 1 per channel. / 1CHあたり1個 |
| LED resistor / LED用抵抗 | 8 | Current limiting for LEDs. / LED電流制限 | 2 per channel. Value depends on LED and brightness. / 値はLEDと明るさに合わせる |
| Jumper wires / ジャンパ線 | as needed | GPIO, I2C, LED, switch wiring. / GPIO、I2C、LED、スイッチ配線 | Male-male / male-female as needed. / 必要な端子形状を選ぶ |
| 5V external servo power supply / 5V外部サーボ電源 | 1 | Power for MG996R servos. / MG996Rサーボ用電源 | Do not rely on Pico USB power for servo current. Common GND is required. / Pico USB給電だけに頼らずGND共通にする |
| Terminal block or connector / 端子台・コネクタ | as needed | Detachable wiring and power distribution. / 着脱可能な配線、電源分配 | Useful around the controller board. / 制御基板周りに便利 |

## n-Channel Scaling / nCH化時の数量目安

Let `N` be the number of channels.

`N` をチャンネル数とします。

| Part / 部品 | Scaling Rule / 数量目安 |
| --- | --- |
| MG996R servo / サーボ | `N` pcs |
| Servo bracket / サーボブラケット | `N` kits, if one kit mounts one servo |
| Servo horn 5-pack / サーボホーン5個セット | `ceil(N / 5)` sets |
| Mini breadboard 2-pack / ミニブレッドボード2点セット | `ceil(N / 2)` sets, if one board is used per channel |
| Servo extension cable 30-pack / サーボ延長ケーブル30本セット | `ceil(N / 30)` sets, plus spare cables if long routing is needed |
| Push button / 押しボタン | `N` pcs |
| Red LED / 赤LED | `N` pcs |
| Green LED / 緑LED | `N` pcs |
| LED resistor / LED用抵抗 | `2N` pcs |
| PCA9685 board / PCA9685基板 | `ceil(N / 16)` boards, but code changes are needed for multiple boards |

## Notes / 注意

- Prices are intentionally omitted because Amazon prices change frequently.
- Check connector shape, cable length, and package count before ordering.
- MG996R-class servos can draw high current. Use a dedicated 5V supply for servos and connect servo GND, PCA9685 GND, and Pico GND together.
- For more than 16 channels, multiple PCA9685 boards and code changes will be required.

- Amazonの価格は変動するため、このリストでは価格を固定していません。
- 注文前に、コネクタ形状、ケーブル長、入り数を確認してください。
- MG996R級のサーボは大きな電流を必要とします。サーボ用の5V外部電源を使い、サーボGND、PCA9685 GND、Pico GNDを共通にしてください。
- 16CHを超える場合は、PCA9685の複数枚化とコード変更が必要です。
