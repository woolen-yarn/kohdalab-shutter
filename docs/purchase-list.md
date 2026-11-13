# Purchase List / 購入品リスト

Last checked / 確認日: 2026-05-28

This list is organized for the current 4-channel shutter controller. Amazon product titles, availability, and prices can change, so use the links as purchase references rather than fixed specifications.

このリストは現在の4CHシャッター制御装置を基準にしています。Amazonの商品名、在庫、価格は変わる可能性があるため、リンクは購入候補として扱ってください。

## Summary / 分類

- Controller board / 制御ボード周り
- Channel switch and LED boards / スイッチ・LED周り
- Servo and shutter mechanism / サーボ・シャッター機構
- Optical safety / 光学安全
- Wiring and power / 配線・電源周り
- Additional required parts / 追加で必要なもの

## Controller Board / 制御ボード周り

| Item / 品名 | Buy Qty / 購入数 | Used Qty / 使用数 | Purpose / 用途 | Link |
| --- | ---: | ---: | --- | --- |
| Freenove Raspberry Pi Pico 2 W board, pre-soldered headers / ヘッダーはんだ付け済み Raspberry Pi Pico 2 W ボード | 1 pc | 1 pc | Wi-Fi MicroPython server/controller. Use the correct firmware for the actual board. / Wi-Fi MicroPythonサーバ、GPIO制御。実ボードに合うファームウェアを使用 | [Amazon B0DRJXPPWL](https://www.amazon.co.jp/dp/B0DRJXPPWL?ref=fed_asin_title&th=1) |
| DiGiYes PCA9685 16-channel PWM servo motor driver, 12-bit I2C module / PCA9685 16CH PWM サーボモータードライバー 12bit I2Cモジュール | 1 pc | 1 pc | I2C PWM driver for the servo channels. / サーボ各CHのPWM生成 | [Amazon B0BKG7QSSR](https://www.amazon.co.jp/dp/B0BKG7QSSR?ref=fed_asin_title) |
| PENGLIN USB 2.0 power cable, 2-core cut end, 30cm, 5-pack / USB 2.0 延長ケーブル 充電用 2芯 切りっぱなし 5本セット | 1 set | 1-2 cables | 5V/GND power input wiring for the controller or servo power rail. / 制御基板またはサーボ電源ラインへの5V/GND引き込み | [Amazon B0DR4265M7](https://www.amazon.co.jp/dp/B0DR4265M7?ref=fed_asin_title&th=1) |

## Channel Switch and LED Boards / スイッチ・LED周り

| Item / 品名 | Buy Qty / 購入数 | Used Qty / 使用数 | Purpose / 用途 | Link |
| --- | ---: | ---: | --- | --- |
| Audiofan mini breadboard, 170 tie-points, 47mm x 35mm, white, 2-pack / ミニサイズ ブレッドボード 170穴 2点セット | 2 sets | 4 boards | One small board per channel for switch, red LED, green LED, and label. / 各CHの押しボタン、赤LED、緑LED、チャンネル表示用 | [Amazon B09BDWQ1KZ](https://www.amazon.co.jp/dp/B09BDWQ1KZ?ref=fed_asin_title&th=1) |
| Marutsu TVDP01-6.5 tactile switch / タクトスイッチ TVDP01-6.5 | 4 pcs | 4 pcs | Local channel switch input. / 各CHのローカル操作スイッチ入力 | [Marutsu 111214](https://www.marutsu.co.jp/pc/i/111214/) |
| Marutsu 503VD2E-1B 5mm red LED / 5mm赤色LED カラーレンズ | 4 pcs | 4 pcs | CLOSE indicator for each channel. / 各CHのCLOSE表示 | [Marutsu 2348061](https://www.marutsu.co.jp/pc/i/2348061/) |
| Marutsu 504PGC2EG4-2BC 5mm green LED / 5mm緑色高輝度LED クリアレンズ | 4 pcs | 4 pcs | OPEN indicator for each channel. / 各CHのOPEN表示 | [Marutsu 2348116](https://www.marutsu.co.jp/pc/i/2348116) |

## Servo and Shutter Mechanism / サーボ・シャッター機構

| Item / 品名 | Buy Qty / 購入数 | Used Qty / 使用数 | Purpose / 用途 | Link |
| --- | ---: | ---: | --- | --- |
| MG996R metal gear digital servo / MG996R メタルギア・デジタルサーボ | 4 pcs | 4 pcs | One servo per shutter channel. / 各シャッターを開閉する駆動用サーボ | [Amazon B010SLRAAS](https://www.amazon.co.jp/dp/B010SLRAAS?ref=fed_asin_title) |
| Servo motor bracket mount kit / サーボモーターブラケット・サーボマウントブラケット | 4 kits | 4 kits | Mechanical mounting for each servo. Confirm actual package contents before ordering. / 各サーボを固定するためのブラケット。購入前に内容物数を確認 | [Amazon B09535CQ59](https://www.amazon.co.jp/dp/B09535CQ59?ref=fed_asin_title) |
| Mallofusa round servo horn, 25T, 5-pack / マロフサ 丸型サーボホーン 25T 5個セット | 1 set | 4 horns | Coupling between servo shaft and shutter plate/linkage. One spare remains for 4CH. / サーボ軸とシャッター板・リンク機構の接続。4CHでは1個予備 | [Amazon B00NOGMK3M](https://www.amazon.co.jp/dp/B00NOGMK3M?ref=fed_asin_title) |

## Optical Safety / 光学安全

| Item / 品名 | Buy Qty / 購入数 | Used Qty / 使用数 | Purpose / 用途 | Link |
| --- | ---: | ---: | --- | --- |
| Thorlabs LB1/M beam block, 400 nm - 2 um, 10 W max average power, includes TR75/M post / ビームブロック 400 nm～2 um 最大平均パワー10 W TR75/Mポスト付属 | 4 pcs | 4 pcs, if one block is used per beam path | Beam block or beam dump for each shutter channel. Confirm wavelength, power, beam size, and safety requirements before use. / 各シャッターCHのビームブロック・ビームダンプ。使用前に波長、パワー、ビーム径、安全要件を確認 | [Thorlabs LB1/M](https://www.thorlabs.co.jp/ja/item/LB1_M) |

## Wiring and Power / 配線・電源周り

| Item / 品名 | Buy Qty / 購入数 | Used Qty / 使用数 | Purpose / 用途 | Link |
| --- | ---: | ---: | --- | --- |
| GTIWUNG 3-pin servo extension cable, male-female, 30-pack, mixed lengths / 3ピンサーボ延長ケーブル 30本セット | 1 set | 4 or more | Extends servo signal/power/GND wiring between the PCA9685/controller area and the servo locations. / PCA9685・制御基板側から各サーボ位置までの3線延長 | [Amazon B0833S1WJ2](https://www.amazon.co.jp/dp/B0833S1WJ2?ref=fed_asin_title&th=1) |
| ELEGOO 120 pcs multicolor Dupont jumper wires / 多色デュポンワイヤー 120本セット | 1 set | as needed | GPIO, I2C, LED, switch, and breadboard wiring. / GPIO、I2C、LED、スイッチ、ブレッドボード配線 | [Amazon B06Y48V9DL](https://www.amazon.co.jp/dp/B06Y48V9DL?ref=fed_asin_title) |
| Samcos 400-point breadboard and jumper wire set, 2-pack / 400穴ブレッドボード・ジャンパーワイヤーセット 2個入り | 1 set | as needed | Extra breadboards and jumper wires for controller and channel-board prototyping. / 制御基板・CH基板の試作、追加配線 | [Amazon B0C3TNP1RG](https://www.amazon.co.jp/dp/B0C3TNP1RG?ref=fed_asin_title&th=1) |
| PENGLIN USB 2.0 power cable, 2-core cut end, 30cm, 5-pack / USB 2.0 延長ケーブル 充電用 2芯 切りっぱなし 5本セット | 1 set | 1-2 cables | Also useful for power input harnesses and quick 5V test leads. / 電源引き込みハーネス、5V試験用リードとしても使用 | [Amazon B0DR4265M7](https://www.amazon.co.jp/dp/B0DR4265M7?ref=fed_asin_title&th=1) |
| Marutsu JK125381-2P 2-pin terminal block / ターミナルブロック 2P | as needed | 1 or more | Detachable 5V/GND input or simple power distribution. / 5V/GND入力の着脱、簡易電源分配 | [Marutsu 62241](https://www.marutsu.co.jp/pc/i/62241/?srsltid=AfmBOopPhmWsJsHPadIMrDNIXoah1m1SUPLr8F-iBRQY667_PcrJhO-H) |

## Additional Required Parts / 追加で必要なもの

The links above now cover the main controller, switch/LED, servo, and wiring parts. Prepare the following separately because they are still not fixed to a specific product link.

上記リンクで、制御ボード、スイッチ・LED、サーボ、配線周りの主要部品はおおむね揃います。次の部品はまだ具体的な購入リンクを固定していないため、別途用意してください。

| Item / 品名 | Qty for 4CH / 4CH数量 | Purpose / 用途 | Notes / 備考 |
| --- | ---: | --- | --- |
| LED resistor / LED用抵抗 | 8 | Current limiting for LEDs. / LED電流制限 | 2 per channel. Value depends on LED and brightness. / 値はLEDと明るさに合わせる |

## n-Channel Scaling / nCH化時の数量目安

Let `N` be the number of channels.

`N` をチャンネル数とします。

| Part / 部品 | Scaling Rule / 数量目安 |
| --- | --- |
| MG996R servo / サーボ | `N` pcs |
| Servo bracket / サーボブラケット | `N` kits, if one kit mounts one servo |
| Servo horn 5-pack / サーボホーン5個セット | `ceil(N / 5)` sets |
| Beam block / ビームブロック | `N` pcs, if each channel needs an independent beam block |
| Mini breadboard 2-pack / ミニブレッドボード2点セット | `ceil(N / 2)` sets, if one board is used per channel |
| Servo extension cable 30-pack / サーボ延長ケーブル30本セット | `ceil(N / 30)` sets, plus spare cables if long routing is needed |
| Dupont jumper wire set / デュポンワイヤーセット | as needed, based on routing length and board layout |
| Tactile switch / タクトスイッチ | `N` pcs |
| Red LED / 赤LED | `N` pcs |
| Green LED / 緑LED | `N` pcs |
| LED resistor / LED用抵抗 | `2N` pcs |
| PCA9685 board / PCA9685基板 | `ceil(N / 16)` boards, but code changes are needed for multiple boards |

## Notes / 注意

- Prices are intentionally omitted because Amazon prices change frequently.
- Check connector shape, cable length, and package count before ordering.
- The linked Pico board is Pico 2 W. If you use Pico W instead, flash the firmware for that exact board.
- Optical safety parts must be selected for the actual laser wavelength, power, pulse condition, beam diameter, and lab safety rules.
- MG996R-class servos can draw high current. Use a dedicated 5V supply for servos and connect servo GND, PCA9685 GND, and Pico GND together.
- For more than 16 channels, multiple PCA9685 boards and code changes will be required.

- Amazonの価格は変動するため、このリストでは価格を固定していません。
- 注文前に、コネクタ形状、ケーブル長、入り数を確認してください。
- リンクしたPico基板はPico 2 Wです。Pico Wを使う場合は、その基板に合ったファームウェアを書き込んでください。
- 光学安全部品は、実際のレーザー波長、パワー、パルス条件、ビーム径、実験室の安全ルールに合わせて選定してください。
- MG996R級のサーボは大きな電流を必要とします。サーボ用の5V外部電源を使い、サーボGND、PCA9685 GND、Pico GNDを共通にしてください。
- 16CHを超える場合は、PCA9685の複数枚化とコード変更が必要です。
