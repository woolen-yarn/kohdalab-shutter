# Pico W USB setup / Pico Wへの初回転送・更新

Download the [current source ZIP](https://github.com/woolen-yarn/kohdalab-shutter/archive/refs/heads/main.zip) and extract it completely. The USB tool is separate from the published desktop installer; it does not need a Rust build. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) once; the launcher obtains Python and mpremote automatically. Network access is needed for that first dependency download.

[最新ソースZIP](https://github.com/woolen-yarn/kohdalab-shutter/archive/refs/heads/main.zip)をダウンロードし、すべて展開してください。書き込みツールはデスクトップアプリとは別で、Rustのビルドは不要です。[uv](https://docs.astral.sh/uv/getting-started/installation/)だけ最初にインストールします。Pythonとmpremoteは起動ファイルが用意します。初回の取得にはインターネット接続が必要です。

## Start / 起動

1. Close all Shutter GUIs and Thonny. Connect the intended Pico W with a USB data cable.
2. Windows: double-click `upload_server_to_pico.bat`. Mac: open `upload_server_to_pico.command` in Terminal. If execution permission is missing after extraction, run `sh upload_server_to_pico.command` from that folder. Linux can use the same shell command.
3. Choose **1. Initial setup** for a new Pico, or **2. Update** for an existing controller. When several Picos are connected, select the USB device by port and USB ID.
4. Initial setup asks for the Wi-Fi SSID and a hidden password. Update retains the Wi-Fi credentials already on the Pico.
5. Review the USB device and mode, then enter `y` to upload. Do not unplug during this operation.
6. After completion, hold a CH switch for 3 seconds to start Wi-Fi, then use **Find Pico W** in the desktop GUI. If `AUTO_START_SERVER` is already enabled, Wi-Fi starts at boot.

1. ShutterのGUIとThonnyを終了し、対象Pico Wをデータ通信対応USBケーブルで接続します。
2. Windowsは `upload_server_to_pico.bat`、Macは `upload_server_to_pico.command` を起動します。Macで実行権限がない場合は、そのフォルダーのターミナルで `sh upload_server_to_pico.command` を実行します。Linuxも同じコマンドを使えます。
3. 新品は **1. Initial setup**、使用中の装置は **2. Update** を選択します。複数台ある場合はUSBポート・USB IDから対象を選びます。
4. 初回だけWi-Fi名とパスワードを入力します。パスワードは画面に表示しません。更新ではPico内のWi-Fi情報を保持します。
5. 対象とモードを確認し、`y`で書き込みます。処理中はUSBを抜かないでください。
6. 完了後、CHスイッチを3秒長押ししてWi-Fiを開始し、PCのGUIで **Find Pico W** を押します。`AUTO_START_SERVER`が有効なら電源投入時に接続します。

**IP addressing is automatic (DHCP) in both modes.** The updater appends an explicit `USE_STATIC_IP = False` override to the existing `settings.py`; custom calibration, pin assignments, motion/current limits and startup behavior remain intact. Missing compatibility constants are added from the current defaults. Do not copy the repository's default calibration over a working device. For a new controller, check the default `server/settings.py` against its wiring and calibrated open/close angles before initial upload.

**初回・更新ともIPはDHCPで自動取得します。** 更新では既存の`settings.py`末尾に `USE_STATIC_IP = False` を追記し、校正角度・ピン・動作速度・同時駆動数・自動起動設定を保持します。不足する定数だけ現行の既定値で補います。使用中装置の設定をサンプルで置き換えないでください。新品装置では、初回転送前に`server/settings.py`の配線・開閉角度が実機に合っていることを確認してください。

## New Pico: install MicroPython once / 新品Pico：MicroPythonの初回導入

The USB tool transfers Python files; it does not install the MicroPython runtime. If MicroPython is absent, download the stable [Pico W UF2](https://micropython.org/download/RPI_PICO_W/), hold **BOOTSEL** while connecting USB, and copy the UF2 onto the `RPI-RP2` drive. After it restarts, run the USB tool above. An existing working controller normally does not need this step. Do not use a filesystem-erasing UF2 on a configured device.

このツールはPythonファイルを転送します。MicroPython本体が未導入の場合だけ、[Pico W用UF2](https://micropython.org/download/RPI_PICO_W/)を取得し、**BOOTSELを押しながらUSB接続**して表示される`RPI-RP2`へコピーします。再起動後に上のツールを実行してください。すでに動いている装置では通常この操作は不要です。保存済み設定を消すUF2は使わないでください。

## Backup and recovery / バックアップ・復旧

Before any write, the tool saves the known server modules, `settings.py`, `wifi_config.py` and `device_config.json` if present under `~/.kohdalab/shutter/pico-backups/<timestamp>/` (Windows: `%USERPROFILE%\.kohdalab\shutter\pico-backups\<timestamp>\`). These backups contain private Wi-Fi credentials; do not share them. Update never writes `wifi_config.py` or `device_config.json`. Initial mode refuses to overwrite an already configured controller.

書き込み前に、既存のサーバーファイル・`settings.py`・`wifi_config.py`・`device_config.json`をPCの日時付きフォルダーへ保存します。Wi-Fiパスワードを含むため、このバックアップを共有しないでください。更新では`wifi_config.py`と`device_config.json`を上書きしません。初回モードは設定済みPicoへの上書きを拒否します。

New files are staged, compared byte-for-byte and compiled by MicroPython before replacement, with `main.py` replaced last. A normal replacement error attempts rollback. A power loss during replacement cannot be made fully atomic across multiple files: rerun Update; if configuration files are missing, restore `settings.py`/`wifi_config.py` from the printed backup directory with Thonny before retrying. Cancelling before upload leaves the filesystem unchanged, but USB inspection stops the running program; restart the Pico to resume it.

転送内容の照合・MicroPythonでの構文確認後に置き換え、`main.py`は最後に切り替えます。通常の置き換えエラーでは元へ戻す処理を試みます。書き換え中の電源断は完全には保護できません。Updateを再実行し、設定ファイルがない場合は表示されたバックアップからThonnyで設定を戻してから再試行してください。書き込み前のキャンセルはファイルを変更しませんが、USB確認でプログラムは停止するため、再起動して運転を再開してください。

For a known USB port / USBポートを指定する場合:

```sh
uv run --no-project --python 3.13 --with 'mpremote>=1.25,<2' python scripts/upload_pico.py --mode update --port COM4
```

`--port` on Mac may be `/dev/cu.usbmodem...`. The tool still asks before writing. See the [official mpremote documentation](https://docs.micropython.org/en/latest/reference/mpremote.html) for manual USB access.

Validation: simulated file transfers, settings preservation, hidden-error output, transfer corruption, syntax failure and replacement rollback are covered by automated tests. Physical USB/Wi-Fi/servo qualification remains to be performed on the target device; no hardware is flashed automatically by the desktop GUI.

検証は模擬転送・設定保持・エラー出力・転送不一致・構文エラー・置き換え失敗時の復旧を対象にしています。実際のUSB転送・Wi-Fi・サーボの確認は対象実機で行ってください。PCのGUIから自動で実機を書き換えることはありません。
