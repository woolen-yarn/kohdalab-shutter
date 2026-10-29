# Pico W setup and discovery / Pico Wの設定と検索

The desktop GUI and CLI use Rust; the Pico W remains on MicroPython. Existing servo wiring and TCP commands remain in place. The `client/` Python client is retained for compatibility.

PC側GUI・CLIはRustを使い、Pico WはMicroPythonのままです。既存のサーボ配線とTCPコマンドは維持します。`client/`のPythonクライアントは互換用に残します。

## Build the desktop app / PCアプリのビルド

[Rust公式インストーラー](https://www.rust-lang.org/tools/install)でstableを用意します。
WindowsではVisual Studio Build Toolsの「C++によるデスクトップ開発」も必要です。
Linuxではビルド用ツールとX11/Wayland/OpenGLの開発パッケージが必要です。

```sh
cargo build --release --locked
```

Windowsでは `target\release\kohdalab-shutter-gui.exe` を起動します。
`open_client_gui.bat` と `desktop/KohdaLab Shutter.vbs` もこの実行ファイルを起動します。
ビルド済みの実行ファイルはRustやPythonをインストールしていないPCでも利用できます。
macOS/Linuxでは `target/release/kohdalab-shutter-gui` を起動します。
CLIだけを作る場合はGUI用の依存を省けます。

```sh
cargo build --release --locked --no-default-features --bin kohdalab-shutter
```

## Layout and shutter states / 配置と開閉状態

シャッターは初期状態で横並びです。Horizontal／Verticalで切り替えられます。
写真の操作部に合わせたCHラベル・左右のLED・中央の押しボタンを表示します。
中央のPUSHはToggle、下部のOpen／Closeは明示的な開閉指令です。
右パネルはなく、接続情報・外部API・履歴は左パネルに集約しています。

Open／CloseはPicoの `CHANNELS` の校正値と、移動待ち・駆動・整定中の情報から判定します。
旧ファームウェアの `STATUS` だけでは角度の意味を推測せずUnknownにします。
`server/main.py` と `server/servo.py` を含む最新ファイルを再転送してください。
状態表示は指令・出力状態であり、物理的な開閉を位置センサーで検証したものではありません。

## External control / 外部制御

左のEnable local API、または起動時の `--gui-api` でPython/Jupyterからの制御を有効にできます。
複数台のPico検索とは別に、同じPCで起動しているGUIに接続するAPIです。
[Pythonクライアント](../bindings/python/README.md)と[API仕様](gui-api.md)を参照してください。

## Demo and screenshots / デモと画面画像

実機なしでGUIを試す場合は、ネットワークを使用しないデモを起動します。
デモ内の開閉操作はシミュレーションのみに反映されます。

```sh
cargo run --release --locked --bin kohdalab-shutter-gui -- --demo
```

READMEの画像は、実際のGUIを次のコマンドで起動して撮影できます。
`--screenshot` は `--demo` と併用したときだけ使用でき、PNGを保存して終了します。

```sh
cargo run --release --locked --bin kohdalab-shutter-gui -- --demo --screenshot docs/images/kohdalab-shutter.png
```

## First Pico W upload / 初回Pico W転送

自動検索には `server/discovery.py` を含む新しいサーバーファイルが必要です。
古いサーバーにもRust版からIPを指定してTCP接続できます。

1. Pico WのMicroPythonと `server/wifi_config.py` のSSID・パスワードを確認します。
2. 固定IPが今のネットワークに合っていなければ、`server/settings.py` の
   `USE_STATIC_IP = False` にしてDHCPでアドレスを取得させます。
   既存装置の設定を守るため、リポジトリの固定IP設定は維持しています。
3. USBで接続し `upload_server_to_pico.bat` を実行します。転送にはuv/mpremoteを使います。
   macOS/Linuxでは次のコマンドを使います。

```sh
uv run mpremote connect auto fs cp server/main.py :main.py fs cp server/pca9685.py :pca9685.py fs cp server/servo.py :servo.py fs cp server/discovery.py :discovery.py fs cp server/settings.py :settings.py fs cp server/wifi_config.py :wifi_config.py reset
```

4. 既存の操作どおり、スイッチを3秒長押ししてWi-Fiサーバーを開始します。
   電源投入時に開始したければ `AUTO_START_SERVER = True` にして再転送します。
5. PCも同じLANに接続します。

## Operate without entering an IP / IPを調べずに操作する

GUIの **Find Pico W** を押し、一覧のID・IPを確認して対象を選択し、**Connect** を押します。
複数台ある場合も勝手に別の装置へ接続しません。
チャンネルの一覧は `STATUS` から生成され、個別操作とOpen all / Close allに対応します。表示角は最後の指令値で、位置センサーによる確認ではありません。
通信中はボタン操作を止め、通信エラー時は表示角を消して再接続を促します。

CLIでは、以下の `cargo run ... --` 部分をビルド済みの `kohdalab-shutter` に置き換えられます。

```sh
cargo run --bin kohdalab-shutter -- discover
cargo run --bin kohdalab-shutter -- status
cargo run --bin kohdalab-shutter -- open 0
cargo run --bin kohdalab-shutter -- close 0
cargo run --bin kohdalab-shutter -- --device <discoverで表示されたID> status
cargo run --bin kohdalab-shutter -- --host 10.32.145.232 status
```

`--host` を省くと毎回検索するため、DHCPでIPが変わっても使えます。
複数台見つかったら `--device` または `--host` で対象を指定します。
サブコマンドを省くと対話モードになります。従来の先頭にIPを書く形式は
Rust版では `--host` に置き換えます。
`TOGGLE` は応答が失われても再送しません。結果が不明なら状態を確認してから操作します。

## When discovery is unavailable / 検索できない場合

検索にはUDP 12346、操作にはTCP 12345（設定変更可能）を使います。
検索はシャッターを動かしません。UDPブロードキャストが届く同一ネットワーク内が対象です。
研究室のWi-Fiで端末間通信やブロードキャストが禁止されている場合、検索できません。
PCのファイアウォール、Pico側サーバー起動、SSID、ネットワーク分離を確認してください。

有線・Wi-Fi・VPNなど複数のアダプターがあるPCでは、GUIの **Search settings** か
CLIの `--broadcast` で実験LANのサブネットのブロードキャストを指定します。
例えば `192.168.1.0/24` なら `192.168.1.255` です。ネットマスクが異なる場合はこの例を使わず、実際のネットワーク設定に合わせます。

```sh
cargo run --bin kohdalab-shutter -- --broadcast 192.168.1.255 discover
```

UDPだけが禁止されている場合は、以下のUSB経由でIPを確認し、GUIのIP欄やCLIの `--host` へ入力できます。
端末間のTCP通信自体が禁止されている場合はネットワーク管理者による接続環境の変更が必要です。

## Inspect the current IP over USB / USBで現在のIPを確認する

Pico WをUSBでつなげば、IPを知らなくても確認できます。
既存制御ループを中断する操作なので、装置を安全な状態にしてから行ってください。
`resume` は自動ソフトリセットを避けますが、実行中プログラムの中断は避けません。

```sh
uv run mpremote connect list
uv run mpremote connect auto resume exec "import network; w=network.WLAN(network.STA_IF); print('connected:', w.isconnected()); print('IP/netmask/gateway/DNS:', w.ifconfig())"
```

複数のUSBシリアル機器があるときは `connect auto` を `connect COM5` など、一覧で確認したポートに置き換えます。
`connected: False` や `0.0.0.0` は、Wi-Fi未接続です。SSID・パスワード、サーバーの開始操作を確認してください。
確認後は再起動し、スイッチの長押しでサーバーを再開します。

```sh
uv run mpremote connect auto reset
```

Wi-Fi開始時の表示を見たい場合は `uv run mpremote connect auto repl` で
USBコンソールを開き、装置のスイッチを3秒長押しします。
`Server listening on <IP>:<port>` と出ます。コンソールはCtrl+]で抜けます。

公式の操作説明: [MicroPython mpremote](https://docs.micropython.org/en/latest/reference/mpremote.html)。

## Development checks / 開発チェック

```sh
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked --all-targets
uv run ruff check .
uv run ruff format --check client server tests
uv run mypy
uv run pytest --cov --cov-report=term-missing
```

TCP/UDPのローカル模擬サーバーとMicroPython用モジュールのテストはハードウェアなしで実行できます。
実機では更新後、検索→ID選択→STATUS取得→安全な条件で1チャンネルの開閉の順で確認します。
