# Pico W USB setup / Pico Wへの初回転送・更新

Extract the [Shutter 1.0.1 source ZIP](https://github.com/woolen-yarn/kohdalab-shutter/releases/download/v1.0.1/kohdalab-shutter-1.0.1-source.zip). It contains the MicroPython firmware in `server/` and the USB updater. The USB updater requires uv on the PC.

[Shutter 1.0.1 のソース ZIP](https://github.com/woolen-yarn/kohdalab-shutter/releases/download/v1.0.1/kohdalab-shutter-1.0.1-source.zip) を展開してください。`server/` にファームウェア、ソース一式に USB 更新ツールが入っています。転送には PC 側で uv が必要です。

## Existing device: normal USB / 既存装置の更新は通常USB接続

**Do not hold BOOTSEL when updating an existing shutter.** Connect USB normally, select the serial Pico, then choose Update. If RPI-RP2/BOOTSEL appears, reconnect without pressing BOOTSEL. Do not reinstall MicroPython or erase stored settings to troubleshoot an ordinary update.

**既存装置の更新ではBOOTSELを押さないでください。** 普通にUSB接続し、一覧のPicoとUpdateを選択します。RPI-RP2／BOOTSELと表示された場合は一度抜き、BOOTSELを押さずにつなぎ直します。通常の更新のためにMicroPythonを入れ直したり、設定を消したりしないでください。

If transfer fails, record the error message and the step where it occurred. For a port-open error, close Thonny and any other serial tool before retrying. / 転送に失敗したら、エラー文と失敗した段階を控えます。ポートを開けない場合は Thonny などのシリアルツールを終了してから再試行します。

## Transfer / 転送

1. Close Shutter and Thonny. Connect the Pico using a USB data cable. / Shutter と Thonny を終了し、データ通信対応の USB ケーブルで Pico を接続します。
2. Run `upload_server_to_pico.bat` on Windows or `upload_server_to_pico.command` on macOS. On Linux, use the command below. / Windows では `upload_server_to_pico.bat`、macOS では `upload_server_to_pico.command`、Linux では下記のコマンドを使います。
3. Select the USB port and **Update** for an existing controller or **Initial setup** for a new one. Confirm the target and keep USB connected until completion. / USB ポートとモードを選びます。既存機は **Update**、新品は **Initial setup** です。対象を確認し、完了まで USB をつないでおきます。
4. Hold a channel switch for three seconds to start Wi-Fi if automatic startup is off, then use **Find Pico W** in Shutter. / 自動起動が無効なら CH スイッチを3秒長押しして Wi-Fi を起動し、Shutter の **Find Pico W** で探します。

```sh
uv run --no-project --python 3.13 --with 'mpremote>=1.25,<2' python scripts/upload_pico.py
```

**Both modes use automatic IP (DHCP).** Update preserves custom calibration, pins, Wi-Fi, labels, motion limits and startup behavior, adding missing compatibility constants and a DHCP override. For initial setup, the bundled calibration/pin defaults must match the new device; adapt `server/settings.py` and build from source for different hardware.

**初回・更新ともDHCPでIPを自動取得します。** 更新では校正・ピン・Wi-Fi・ラベル・駆動・自動起動設定を保持し、不足する定数とDHCP設定だけを補います。初回の配線・開閉角度は同梱の既定値を使います。異なる配線・校正の新品装置では、ソースの`server/settings.py`を合わせてビルドしてください。

## New Pico: install MicroPython once / 新品Pico：MicroPythonの初回導入

The USB tool transfers Python files; it does not install the MicroPython runtime. If MicroPython is absent, download the stable [Pico W UF2](https://micropython.org/download/RPI_PICO_W/) or [Pico 2 W UF2](https://micropython.org/download/RPI_PICO2_W/) for your board, hold **BOOTSEL** while connecting USB, and copy the UF2 onto the `RPI-RP2` drive. After it restarts, run the USB tool above. An existing working controller normally does not need this step. Do not use a filesystem-erasing UF2 on a configured device.

このツールはPythonファイルを転送します。MicroPython本体が未導入の場合だけ、基板に合う [Pico W 用 UF2](https://micropython.org/download/RPI_PICO_W/) または [Pico 2 W 用 UF2](https://micropython.org/download/RPI_PICO2_W/) を取得し、**BOOTSELを押しながらUSB接続**して表示される`RPI-RP2`へコピーします。再起動後に上のツールを実行してください。すでに動いている装置では通常この操作は不要です。保存済み設定を消すUF2は使わないでください。

## Backup and recovery / バックアップ・復旧

Before any write, the tool saves the known server modules, `settings.py`, `wifi_config.py` and `device_config.json` if present under `~/.kohdalab/shutter/pico-backups/<timestamp>/` (Windows: `%USERPROFILE%\.kohdalab\shutter\pico-backups\<timestamp>\`). These backups contain private Wi-Fi credentials; do not share them. Update never writes `wifi_config.py`, `device_config.json` or the existing `pca9685.py`. This retains driver-level `servo_min_us` / `servo_max_us` pulse calibration as well as settings-based angles. If the existing driver lacks the required API or its main-side initialization is customized, CALIBRATION_REVIEW stops the update before transfer. Review the backup instead of replacing the calibration with defaults. Initial mode refuses to overwrite an already configured controller.

書き込み前に、既存のサーバーファイル・`settings.py`・`wifi_config.py`・`device_config.json`をPCの日時付きフォルダーへ保存します。Wi-Fiパスワードを含むため、このバックアップを共有しないでください。更新では`wifi_config.py`・`device_config.json`・既存の`pca9685.py`を上書きしません。`servo_min_us`・`servo_max_us`などライブラリ内の個体別校正も残します。必要なAPIがない古いドライバーや、main側の独自初期化を確認できない場合はCALIBRATION_REVIEWで転送前に止めます。既定値で置き換えず、バックアップを確認してください。初回モードは設定済みPicoへの上書きを拒否します。

New files are staged, compared byte-for-byte and compiled by MicroPython before replacement, with `main.py` replaced last. A normal replacement error attempts rollback. A power loss during replacement cannot be made fully atomic across multiple files: rerun Update; if configuration files are missing, restore `settings.py`/`wifi_config.py` from the printed backup directory with Thonny before retrying. Cancelling before upload leaves the filesystem unchanged, but USB inspection stops the running program; restart the Pico to resume it.

転送内容の照合・MicroPythonでの構文確認後に置き換え、`main.py`は最後に切り替えます。通常の置き換えエラーでは元へ戻す処理を試みます。書き換え中の電源断は完全には保護できません。Updateを再実行し、設定ファイルがない場合は表示されたバックアップからThonnyで設定を戻してから再試行してください。書き込み前のキャンセルはファイルを変更しませんが、USB確認でプログラムは停止するため、再起動して運転を再開してください。

## Explicit USB port / USB ポートの指定

For a known USB port / USBポートを指定する場合:

```sh
uv run --no-project --python 3.13 --with 'mpremote>=1.25,<2' python scripts/upload_pico.py --mode update --port COM4
```

`--port` on Mac may be `/dev/cu.usbmodem...`. The tool still asks before writing. See the [official mpremote documentation](https://docs.micropython.org/en/latest/reference/mpremote.html) for manual USB access.

Validation: simulated file transfers, settings preservation, hidden-error output, transfer corruption, syntax failure and replacement rollback are covered by automated tests. Physical USB/Wi-Fi/servo qualification remains to be performed on the target device; no hardware is flashed automatically by the desktop GUI.

検証は模擬転送・設定保持・エラー出力・転送不一致・構文エラー・置き換え失敗時の復旧を対象にしています。実際のUSB転送・Wi-Fi・サーボの確認は対象実機で行ってください。PCのGUIから自動で実機を書き換えることはありません。
