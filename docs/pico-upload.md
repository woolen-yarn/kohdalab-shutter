# Pico W USB setup / Pico Wへの初回転送・更新

Download the dedicated [Pico Setup app](https://github.com/woolen-yarn/kohdalab-shutter/releases/tag/pico-tools-v1.0.0). No Python, uv or Thonny installation is needed on the PC. The app bundles the runtime, USB transfer backend and Pico server files. It is separate from the main Shutter control GUI.

専用の[Pico Setupアプリ](https://github.com/woolen-yarn/kohdalab-shutter/releases/tag/pico-tools-v1.0.0)を使う場合、PCへPython・uv・Thonnyを入れる必要はありません。実行環境・USB転送機能・Pico側プログラムを同梱しています。普段使うShutter操作GUIとは別のアプリです。

## Start / 起動

1. Download and extract the entire ZIP. Windows x64: open `KohdaLab Pico Setup.exe` with its `_internal` folder kept alongside it. Mac: choose Apple Silicon (arm64) or Intel (x64), then open `KohdaLab Pico Setup.app`.
2. Close Shutter GUIs and Thonny. Connect the Pico W with a USB data cable, then Refresh and select its USB port/ID.
3. Choose **Update · keep settings** for an existing controller, or **Initial setup · new Pico**. Enter Wi-Fi name/password for initial setup only.
4. Press Update Pico / Install on Pico, check the target, then confirm. Keep the app open and USB connected until completion.
5. Hold a CH switch for 3 seconds to start Wi-Fi and use **Find Pico W** in the control GUI. If `AUTO_START_SERVER` is enabled, Wi-Fi starts at boot.

1. ZIPをすべて展開します。Windowsは`KohdaLab Pico Setup.exe`を開き、隣の`_internal`フォルダーを残します。MacはApple Silicon用／Intel用を選び、`KohdaLab Pico Setup.app`を開きます。
2. ShutterのGUIとThonnyを終了し、対象Pico WをUSB接続します。RefreshでUSBポート・USB IDを確認して選びます。
3. 使用中装置は **Update · keep settings**、新品は **Initial setup · new Pico** を選び、初回だけWi-Fi名・パスワードを入力します。
4. 書き込みボタンを押し、対象を確認して実行します。完了までアプリを開いたままUSBを接続してください。
5. CHスイッチを3秒長押ししてWi-Fiを開始し、操作GUIの **Find Pico W** で探します。自動起動設定が有効なら長押しは不要です。

**Both modes use automatic IP (DHCP).** Update preserves custom calibration, pins, Wi-Fi, labels, motion limits and startup behavior, adding missing compatibility constants and a DHCP override. For initial setup, the bundled calibration/pin defaults must match the new device; adapt `server/settings.py` and build from source for different hardware.

**初回・更新ともDHCPでIPを自動取得します。** 更新では校正・ピン・Wi-Fi・ラベル・駆動・自動起動設定を保持し、不足する定数とDHCP設定だけを補います。初回の配線・開閉角度は同梱の既定値を使います。異なる配線・校正の新品装置では、ソースの`server/settings.py`を合わせてビルドしてください。

Windows is unsigned and Mac is ad-hoc signed, not notarized; first-launch OS approval may still be needed. No claim of warning-free signed distribution is made. Signing enrollment remains pending as for the main app.

Windowsは未署名、Macはアドホック署名・未公証です。PCへの追加ツール導入は不要ですが、初回のOS確認が出る場合があります。署名の登録状況はメインアプリと同じです。

## New Pico: install MicroPython once / 新品Pico：MicroPythonの初回導入

The USB tool transfers Python files; it does not install the MicroPython runtime. If MicroPython is absent, download the stable [Pico W UF2](https://micropython.org/download/RPI_PICO_W/), hold **BOOTSEL** while connecting USB, and copy the UF2 onto the `RPI-RP2` drive. After it restarts, run the USB tool above. An existing working controller normally does not need this step. Do not use a filesystem-erasing UF2 on a configured device.

このツールはPythonファイルを転送します。MicroPython本体が未導入の場合だけ、[Pico W用UF2](https://micropython.org/download/RPI_PICO_W/)を取得し、**BOOTSELを押しながらUSB接続**して表示される`RPI-RP2`へコピーします。再起動後に上のツールを実行してください。すでに動いている装置では通常この操作は不要です。保存済み設定を消すUF2は使わないでください。

## Backup and recovery / バックアップ・復旧

Before any write, the tool saves the known server modules, `settings.py`, `wifi_config.py` and `device_config.json` if present under `~/.kohdalab/shutter/pico-backups/<timestamp>/` (Windows: `%USERPROFILE%\.kohdalab\shutter\pico-backups\<timestamp>\`). These backups contain private Wi-Fi credentials; do not share them. Update never writes `wifi_config.py` or `device_config.json`. Initial mode refuses to overwrite an already configured controller.

書き込み前に、既存のサーバーファイル・`settings.py`・`wifi_config.py`・`device_config.json`をPCの日時付きフォルダーへ保存します。Wi-Fiパスワードを含むため、このバックアップを共有しないでください。更新では`wifi_config.py`と`device_config.json`を上書きしません。初回モードは設定済みPicoへの上書きを拒否します。

New files are staged, compared byte-for-byte and compiled by MicroPython before replacement, with `main.py` replaced last. A normal replacement error attempts rollback. A power loss during replacement cannot be made fully atomic across multiple files: rerun Update; if configuration files are missing, restore `settings.py`/`wifi_config.py` from the printed backup directory with Thonny before retrying. Cancelling before upload leaves the filesystem unchanged, but USB inspection stops the running program; restart the Pico to resume it.

転送内容の照合・MicroPythonでの構文確認後に置き換え、`main.py`は最後に切り替えます。通常の置き換えエラーでは元へ戻す処理を試みます。書き換え中の電源断は完全には保護できません。Updateを再実行し、設定ファイルがない場合は表示されたバックアップからThonnyで設定を戻してから再試行してください。書き込み前のキャンセルはファイルを変更しませんが、USB確認でプログラムは停止するため、再起動して運転を再開してください。

## Source alternative / ソース版

Developers may still use the [current source ZIP](https://github.com/woolen-yarn/kohdalab-shutter/archive/refs/heads/main.zip) and `upload_server_to_pico.bat` / `.command`. These source launchers require uv; the downloadable **Pico Setup app above does not**. To change calibration before a first upload, edit `server/settings.py` in this source checkout.

ソース版のバッチ・commandも残しています。こちらだけはuvが必要です。上の配布アプリでは不要です。初回転送前に校正・ピンを変えたい場合はソースの`server/settings.py`を編集できます。

For a known USB port / USBポートを指定する場合:

```sh
uv run --no-project --python 3.13 --with 'mpremote>=1.25,<2' python scripts/upload_pico.py --mode update --port COM4
```

`--port` on Mac may be `/dev/cu.usbmodem...`. The tool still asks before writing. See the [official mpremote documentation](https://docs.micropython.org/en/latest/reference/mpremote.html) for manual USB access.

Validation: simulated file transfers, settings preservation, hidden-error output, transfer corruption, syntax failure and replacement rollback are covered by automated tests. Physical USB/Wi-Fi/servo qualification remains to be performed on the target device; no hardware is flashed automatically by the desktop GUI.

検証は模擬転送・設定保持・エラー出力・転送不一致・構文エラー・置き換え失敗時の復旧を対象にしています。実際のUSB転送・Wi-Fi・サーボの確認は対象実機で行ってください。PCのGUIから自動で実機を書き換えることはありません。
