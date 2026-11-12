<img src="assets/kohdalab-shutter.svg" width="64" height="64" align="right" alt="KohdaLab Shutter icon">

# KohdaLab Shutter

[![CI](https://github.com/woolen-yarn/kohdalab-shutter/actions/workflows/test.yml/badge.svg)](https://github.com/woolen-yarn/kohdalab-shutter/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Rust desktop controller and MicroPython Pico W firmware for servo-driven optical shutters.
Rust製デスクトップコントローラーと、サーボ式光シャッター用Pico W MicroPythonファームウェアです。

[Download / ダウンロード](https://github.com/woolen-yarn/kohdalab-shutter/releases) · [Documentation / ドキュメント](docs/README.md) · [Report an issue / 問題を報告](https://github.com/woolen-yarn/kohdalab-shutter/issues)

- Select a labelled Pico W and the channels you need in a separate connection screen.
- Locks selected channels on the Pico; other PCs can use the remaining channels.
- Shows only your channels in a compact dark control window, with editable names and clickable light-window switches.

- 接続画面で名前付きのPico Wと使用CHを選びます。
- Pico側で選択CHだけをロックし、残りのCHは他のPCから使用できます。
- 操作画面は使用CHだけを表示する小型の黒テーマです。

## Interface / 画面

![KohdaLab Shutter interface](docs/images/kohdalab-shutter.png)

Choose a named controller on the left and channels in the vertical list on the right, then Connect. In the compact control window, each CH number sits above its name box. Click the name to edit and press Enter to apply; Escape or clicking elsewhere discards unconfirmed text. Click the light window to toggle the shutter. The connection-name menu contains Disconnect; ··· opens Settings for the Pico name, layout, order and local API. Confirmed names and settings save automatically. Labels are shared through the Pico. The dark palette follows kohdalab-trkr; images use simulated hardware.

接続画面は左で機器、右の縦並びで使用CHを選び、Connectします。操作画面はCH番号の下に名前の入力欄を置き、クリックで編集・Enterで確定します。Escapeや欄外のクリックでは未確定の編集を戻します。光の窓を押すと開閉を切り替えます。上部の接続名メニューにDisconnect、「···」のSettingsにPico名・配置・並び順・外部APIをまとめました。確定した名前と設定は自動保存し、名前はPicoを通じて他のPCにも共有します。黒テーマはkohdalab-trkrと統一しています。画像は模擬接続です。

![Connection picker](docs/images/kohdalab-shutter-connect.png)

**Pico USB setup/update:** download the standalone [Pico Setup app](https://github.com/woolen-yarn/kohdalab-shutter/releases/tag/pico-tools-v1.2.0). Extract the ZIP and double-click the Windows exe or Mac app; no Python or uv installation is needed. Choose Initial setup or Update. Channel tuning offers per-CH endpoints and opt-in gentle approach. Both use DHCP; Update backs up and preserves calibration, pins, Wi-Fi and labels. [Instructions](docs/pico-upload.md)

**Picoへの初回転送・更新：** 専用の[Pico Setupアプリ](https://github.com/woolen-yarn/kohdalab-shutter/releases/tag/pico-tools-v1.2.0)を配布しています。ZIPを展開し、Windowsのexe／Macのappを開くだけで、Python・uvの別途インストールは不要です。初回／更新と、CH別の角度・終端減速の調整に対応し、どちらもDHCPです。更新はバックアップを取り、校正・配線・Wi-Fi・ラベルを保持します。[手順](docs/pico-upload.md)

<details>
<summary>Vertical layout / 縦並び</summary>

![KohdaLab Shutter vertical interface](docs/images/kohdalab-shutter-vertical.png)

</details>

<details>
<summary>Descending order / 降順</summary>

![KohdaLab Shutter descending channel order](docs/images/kohdalab-shutter-descending.png)

Ordering changes the display only; hardware channel identifiers stay fixed.

表示順だけが変わり、実機のCH番号は変わりません。

</details>

## Downloads / ダウンロード

Download the desktop app from [GitHub Releases](https://github.com/woolen-yarn/kohdalab-shutter/releases/latest). No Rust or Python installation is needed to run the GUI.

[GitHub Releases](https://github.com/woolen-yarn/kohdalab-shutter/releases/latest)から配布アプリをダウンロードできます。PCでGUIを使うためにRust・Pythonは不要です。

| Platform / OS | Download / ファイル |
| --- | --- |
| Windows 10/11 (x64) | `kohdalab-shutter-<version>-windows-x64-Setup.exe` — install and open from Start / インストール後、スタートメニューから起動 |
| macOS 13+ (Apple Silicon / Intel) | `kohdalab-shutter-<version>-macos-universal.dmg` — drag the app to Applications / アプリをApplicationsへドラッグ |

Windows packages are not publisher-signed; Mac packages are ad hoc signed and not Apple-notarized. See the [installation guide / 導入手順](docs/install.md) for first-launch prompts. Pico W firmware is installed and updated with the separate Pico Setup app above.

Windows版は発行元の署名がなく、Mac版はアドホック署名でAppleの公証を受けていないため、初回起動で確認が出ることがあります。[導入手順](docs/install.md)をご覧ください。Pico Wのファームウェアの転送・更新には、上記のPico Setupアプリを使います。

## Code signing / 署名・公証

Current desktop files retain their unsigned/ad-hoc status. Windows follows the same SignPath Foundation preparation/approval policy as TRKR/IV, with an exact two-executable scope. A protected manual Developer ID/notarization workflow is prepared for Mac and requires owner enrollment/certificate setup before activation. See [signing setup](docs/code-signing.md), [policy](CODE_SIGNING_POLICY.md) and [privacy](PRIVACY.md).

現行デスクトップ版の署名状態は変わりません。WindowsはTRKR・IVと同じSignPath申請準備・承認方針に統一し、Macは登録後に使用するDeveloper ID署名・公証ワークフローを用意しています。まだ本番の署名・公証は実行していません。[設定手順](docs/code-signing.md)を参照してください。

## Automatic settings / 設定の自動保存

Pico/channel names are shared and retained on the Pico in `device_config.json`. Only the owning GUI may rename a channel. After a short typing pause, valid changes save automatically; Settings shows Saving / Saved or an error without disconnecting the shutters. Calibration and Wi-Fi are kept separately.

PC layout, order, selected channels, endpoint/broadcast and Local control API opt-in are retained in `~/.kohdalab/shutter/config/config.json` (Windows: `%USERPROFILE%\.kohdalab\shutter\config\config.json`). On the first normal launch, a safe default file is created automatically when absent. Existing valid, corrupt or foreign files are never overwritten; loading does not acquire channels or move shutters. Authentication tokens are regenerated, not saved. Startup remembers the last device/available CHs but does not acquire channels or move shutters automatically. No old files are migrated or deleted.

Pico名・CH名はPico側に保存し、他のPCとも共有します。PC側の配置・昇降順・選択CH・接続設定・APIの有効無効も保存します。次回起動時に復元しますが、勝手に接続・駆動しません。API認証情報は保存せず、破損設定や他アプリの設定は上書きしません。

![Settings](docs/images/kohdalab-shutter-settings.png)

## Parallel motion / 並列動作

The updated Pico firmware defaults to moving all configured channels concurrently. Existing devices must also update `SERVO_MAX_ACTIVE` in their own `settings.py` (for example `4` for four channels) and restart; a desktop update alone cannot change the device's current concurrency limit. Preserve your calibrated angles, pins and network settings.

Pico W側も同時駆動数の更新が必要です。実機の既存`settings.py`で`SERVO_MAX_ACTIVE`をCH数（4台なら`4`）に変更し、再起動してください。校正角度・ピン・Wi-Fi/IP設定はそのまま保持します。配布ソースでは`CHANNELS`定義後に`SERVO_MAX_ACTIVE = len(CHANNELS)`としています。

## Supported hardware / 対応ハードウェア

| Role / 役割 | Current implementation / 現在の実装 |
| --- | --- |
| Controller / 制御器 | Raspberry Pi Pico W running MicroPython / MicroPythonを実行するRaspberry Pi Pico W |
| Servo PWM / サーボPWM | PCA9685, one board, up to 16 outputs / PCA9685 1枚、最大16出力 |
| Desktop / PC | Rust GUI and CLI on Windows, macOS, or Linux / Windows・macOS・Linux向けRust GUI・CLI |

### 4-channel build / 4CH構成の主要部品

| Part / 部品 | Quantity / 数量 |
| --- | ---: |
| Raspberry Pi Pico W or Pico 2 W / Raspberry Pi Pico W または Pico 2 W | 1 |
| PCA9685 PWM driver board / PCA9685 PWMドライバ基板 | 1 |
| Servo, mounting bracket, and horn / サーボ・取付ブラケット・ホーン | 4 each / 各4 |
| Push button, red LED, and green LED / 押しボタン・赤LED・緑LED | 4 each / 各4 |
| LED current-limiting resistors / LED電流制限抵抗 | 8 |
| Mini breadboard for channel controls / CH操作用ミニブレッドボード | 4 |
| External servo power supply / サーボ用外部電源 | 1 |
| Wiring and servo extension cables / 配線材・サーボ延長ケーブル | As needed / 必要数 |
| Beam block / ビームブロック | 1 per beam path / 光路ごとに1 |

See the [4-channel purchase list](docs/purchase-list.md) for part numbers and suppliers. / 詳しい型番と購入先は [4CH購入品リスト](docs/purchase-list.md) を参照してください。

## Quick start / はじめに

Explore the interface without connecting hardware / 実機に接続せず画面を試す:

```sh
cargo run --locked --bin kohdalab-shutter-gui -- --demo
```

1. Download and open the app from [Releases](https://github.com/woolen-yarn/kohdalab-shutter/releases/latest), or build from source. / Releasesからアプリを取得するか、ソースからビルドします。
2. Prepare `server/wifi_config.py`, connect the Pico W by USB, and upload the server once. / Wi-Fi設定を用意し、Pico WをUSB接続してサーバーを一度転送します。
3. Start the Pico W server by holding a channel switch for three seconds, unless `AUTO_START_SERVER` is enabled. / `AUTO_START_SERVER`が無効なら、チャンネルスイッチを3秒長押ししてサーバーを開始します。
4. Open KohdaLab Shutter, choose **Find Pico W**, select the intended device, then connect. / GUIを起動し、**Find Pico W**から対象機器を選んで接続します。

The first firmware upload and DHCP/fixed-IP choice are described in [Pico W setup and discovery / Pico Wの設定と検索](docs/rust-client.md). Discovery requires that the PC and Pico W can exchange local UDP traffic; use the USB fallback if the laboratory network blocks it.

初回転送とDHCP・固定IPの選択は[Pico Wの設定と検索](docs/rust-client.md)を参照してください。検索にはPCとPico WのローカルUDP通信が必要です。研究室ネットワークで遮断される場合はUSB確認を使用します。

## External control / 外部制御

Python/Jupyter can attach to the running GUI using an opt-in local API. The GUI owns the Pico connection, and GUI/API actions share the same serialized path and calibrated Open/Close states.

Python/Jupyterから起動中GUIへ接続できます。Pico接続はGUIが所有し、手動操作とAPI操作は同じ制御経路・Open/Close判定を使います。

```sh
cargo run --release --locked --bin kohdalab-shutter-gui -- --demo --gui-api
python -m pip install ./bindings/python
```

See the [Python client guide](bindings/python/README.md) and [GUI API reference](docs/gui-api.md). Open/Close display requires the updated Pico firmware; older firmware remains controllable and displays Unknown.

詳しくは[Pythonクライアント](bindings/python/README.md)と[GUI API仕様](docs/gui-api.md)を参照してください。Open/Close表示にはPico側も更新します。旧ファームウェアでは操作は可能ですが、状態はUnknownと表示します。

## Operation journal / 操作ジャーナル

Each normal GUI session appends JSON Lines under `~/.kohdalab/shutter/logs/` (Windows: `%USERPROFILE%\\.kohdalab\\shutter\\logs\\`). One file is created per session as `shutter-session-<UUID>.jsonl`, beginning with `session_started`. Each record includes a UTC Unix-millisecond timestamp (or explicit clock error), monotonic elapsed milliseconds, session UUID, app version, Pico device ID, endpoint and label. An operation has a UUID-linked `operation_requested` record followed by `operation_outcome` (`accepted` or `unresolved`); both carry the actual numeric CH IDs. Reported state is appended only when it changes, including reported servo position, target, busy flag and Open/Close calibration. The journal contains no control tokens or Wi-Fi credentials. A bounded background writer performs disk synchronization; queue/disk failures make provenance explicitly incomplete in the GUI and API status, but never delay or prevent Close/Stop safety actions.

On normal exit, after device release, the app records an unresolved in-flight operation if needed and requests an ordered `session_finished` marker. It waits at most 250 ms for writer acknowledgement; a timeout is reported as incomplete, never as a confirmed drain. The terminal record describes known record loss and writer ordering, not whether the GUI received the acknowledgement; a delayed writer may finish after the GUI timed out.

The records distinguish Pico-reported/commanded servo position from optical verification: this controller has no optical sensor, so an Open/Close record is not evidence of transmitted light. Retain the JSONL with the corresponding measurement record when provenance is required.

通常GUIの各セッションは `~/.kohdalab/shutter/logs/`（Windows: `%USERPROFILE%\\.kohdalab\\shutter\\logs\\`）にJSON Linesを追記します。セッションごとに `shutter-session-<UUID>.jsonl` を作成し、先頭は `session_started` です。各記録にはUTC Unixミリ秒時刻（時計異常時は明示的なエラー）、単調増加の経過ミリ秒、セッションUUID、アプリ版、Pico ID、接続先、ラベルを含めます。操作は同じUUIDの `operation_requested` と `operation_outcome`（`accepted` または `unresolved`）で結び、両方に実際の数値CH IDを記録します。状態記録には変化時のみPico報告のサーボ位置・目標・busy・Open/Close校正値を含めます。制御トークンとWi-Fi認証情報は保存しません。ディスク同期は上限付きのバックグラウンド書込みで行い、キュー/ディスク失敗はGUIとAPI状態に「来歴不完全」として明示しますが、Close/Stop等の安全操作を遅延・妨害しません。

通常終了では、機器のrelease後に未完了操作を必要に応じてunresolvedとして記録し、順序保証された `session_finished` マーカーを要求します。書込み側の確認待ちは最大250 msであり、タイムアウトは完了済みとは扱わず来歴不完全として扱います。終了レコードは既知の記録欠落と書込み順序を示し、GUI側の確認受信を保証しません。書込みがGUIのタイムアウト後に完了する場合もあります。

Pico報告/指令のサーボ位置と光学的な透過確認は明確に区別します。本コントローラーには光センサーがないため、Open/Close記録は透過光の確認ではありません。来歴が必要な測定では対応する測定記録とJSONLを一緒に保管してください。

## Development / 開発

```sh
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked --all-targets
uv run ruff check .
uv run mypy
uv run pytest --cov --cov-report=term-missing
```

Tests do not move a shutter or connect hardware. See [Contributing](CONTRIBUTING.md) and [Safety notes](SAFETY.md) before a physical test.

テストはシャッターを動かさず、実機にも接続しません。実機試験の前に[開発ガイド](CONTRIBUTING.md)と[安全上の注意](SAFETY.md)を確認してください。

## Related projects / 関連プロジェクト

- [KohdaLab IV](https://github.com/woolen-yarn/kohdalab-iv): DC I-V / V-I measurement desktop application.
- [KohdaLab TRKR](https://github.com/woolen-yarn/kohdalab-trkr): time-resolved Kerr rotation measurement desktop application.

## License / ライセンス

MIT. See [LICENSE](LICENSE).

## Common GUI control / 共通GUI制御

[Control Protocol 1 and Python/Notebook examples / 共通APIとPython・Notebook](docs/reference/common-control-api.md). The existing application API remains supported; operation payloads and safety policy are app-specific. Camera is read-only. / 既存APIは維持し、操作引数と安全方針は各アプリに従います。Cameraは読み取り専用です。

See [Measurement output bundles / 測定データの保存セット](docs/reference/measurement-output.md) for common file roles and unit conventions.
