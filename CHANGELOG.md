# Changelog

## 0.6.10 — 2026-11-11

- Show `Fault` in the GUI and in CLI `info` for a channel whose Pico reports an I2C write fault, and record fault transitions in the operation journal. Requires the firmware in Pico Setup 1.2.0; older firmware is displayed as before. / PicoがI2C書き込み異常を報告したCHを、GUIとCLIの`info`で`Fault`と表示し、操作ジャーナルに記録します。Pico Setup 1.2.0のファームウェアが必要で、旧ファームウェアは従来どおり表示します。
- Add a boolean `fault` to each channel of GUI API `status`; the existing `state` value is unchanged. Python `wait_for_state()` raises `GuiShutterError` with code `fault` immediately for a faulted channel. The Python client package is 0.6.10. / GUI APIの`status`の各CHに真偽値`fault`を追加しました。`state`の値は変わりません。Pythonの`wait_for_state()`は異常中のCHに対して待たずに`fault`エラーを出します。
- Run the shared control protocol crate's tests in CI through a Cargo workspace. / 共通制御プロトコルcrateのテストをCIで実行します。
- Publish release evidence with the packages: a source archive of the release commit, `RELEASE-VERIFICATION.json`, the GUI API simulation report, and `SHA256SUMS.txt` covering every published file. / 配布物と一緒に、リリースcommitのソースアーカイブ、`RELEASE-VERIFICATION.json`、GUI APIの模擬検証結果、全ファイルを含む`SHA256SUMS.txt`を公開します。
- Shutter commands, `STATE`/`STATUS`, profiles and lease policy are unchanged. No physical-device qualification was performed. / 指令、`STATE`/`STATUS`、設定形式、lease方針は変わりません。実機での検証は行っていません。

## Pico Setup 1.2.0 — 2026-11-11

- Run a TCP command only after its complete line arrives. A request cut off before the newline is answered with `UNKNOWN` and moves nothing. / TCPコマンドは改行まで届いたときだけ実行します。途中で止まった要求は`UNKNOWN`を返し、何も動かしません。
- Isolate an I2C write fault to its channel: keep the last successfully written angle, stop that channel, alternate its red and green LEDs, and retry only on the next operator command. Other channels, buttons and the network keep working. The Pico does not reboot automatically. / I2C書き込み異常をそのCHだけに留めます。最後に成功した角度を保持して停止し、赤と緑のLEDを交互に点灯し、次の操作で再試行します。他のCH・ボタン・通信は動き続けます。自動再起動はしません。
- If the PCA9685 cannot be initialized at startup, show the fault pattern on every channel and keep servo drive and the network off until power is cycled. / 起動時にPCA9685を初期化できない場合は、全CHを異常表示にして駆動と通信を開始しません。
- Detect Wi-Fi loss while the server runs, clear channel leases, and reconnect in the background while buttons and servo motion continue. A one-second on/off state LED indicates reconnection. / サーバー動作中のWi-Fi切断を検出してCHの確保を解除し、ボタンとサーボを動かしたまま再接続します。再接続中は状態LEDが1秒周期で点滅します。
- Document that every power-on or reset drives all channels to their Close angle. This behaviour is unchanged. / 電源投入・リセットのたびに全CHをClose角へ動かすことを文書に明記しました。挙動は変わりません。
- This firmware has not been run on a physical Pico W or servos. / このファームウェアは実機のPico W・サーボでは動かしていません。

## 0.6.9 — 2026-11-10

- Move the GUI to the maintained eframe/egui 0.34 stack and drop the unmaintained font parser. Process API requests and controller polling independently of drawing so a covered window keeps responding. / GUIを保守中のeframe/egui 0.34系へ更新し、保守終了したフォント解析を除去。描画と切り離してAPI要求と状態照会を処理します。
- Serialize lease release and reacquisition in the shared Python control client. / 共通Python制御クライアントで制御権の解放・再取得を直列化しました。
- Make journal-content tests wait for an ordered writer acknowledgement. The 250 ms exit budget is unchanged. / 操作履歴の内容試験を順序付き完了通知に同期しました。終了時の上限250 msは変わりません。

## 0.6.8 — not published / 未公開

- Tag `v0.6.8` points at a commit whose CI failed, so no release was published. Its changes were released as 0.6.9. / tag `v0.6.8` はCIが失敗したcommitを指すため公開していません。内容は0.6.9として公開しました。

## 0.6.7 — 2026-11-06

- Refresh state after 100 ms instead of one second while a selected shutter reports Moving, and repaint every 50 ms during motion. Open/Close still comes from controller feedback. / 選択したシャッターがMovingの間は状態取得を1秒から100 ms間隔にし、50 msごとに再描画します。Open/Closeは引き続きコントローラーの報告で確定します。

## 0.6.6 — 2026-11-06

- Record each normal GUI session as a JSON Lines operation journal under `~/.kohdalab/shutter/logs`, with linked request/outcome records, device identity, UTC and monotonic timing. A bounded background writer keeps disk I/O off the control path. / 通常GUIの各セッションを`~/.kohdalab/shutter/logs`のJSON Lines操作ジャーナルに記録します。書き込みは上限付きの別スレッドで行い、操作を妨げません。

## Pico Setup 1.1.1 — 2026-11-04

- Restore physical channel buttons while a PC holds the channel lease. Other PCs stay locked out. / PCがCHを確保している間も物理ボタンを使えるようにしました。他のPCへのロックは維持します。

## 0.6.5 — 2026-11-05

- Ignore empty home-directory environment values and use the valid platform fallback consistently in the GUI and common Python client. / GUIと共通Pythonクライアントで、空のホーム環境変数を除外して有効な代替先を使います。
- Search only newly received bytes for the common API response delimiter, preserving existing size limits and error handling. / 共通APIの受信済みデータを繰り返し走査せず、新しい断片だけで区切りを検出します。サイズ制限とエラー処理は維持します。
- Retry failed PC preference saves after a five-second delay while preserving the visible error until success. / PC設定の保存失敗後は5秒間隔で再試行し、成功までエラーを表示します。
- Check local documentation links in CI using the same suite conventions. / 他アプリと同じ方針で、CIにローカル文書リンク検証を追加します。

## Pico Setup 1.1.0

- Add USB-backed per-channel Close/Open editing and opt-in Soft Open/Soft Close, with private backups, queued changes, exact update review, device ID/settings-hash checks and preserved PWM-driver calibration. No automatic endpoint change.
- Add independent soft approach within the selected endpoint's final 12° (≤1° per ≥40 ms), preserving defaults, other CH timing, concurrency and PWM release policy. Verify under CPython and actual MicroPython. Hardware stall/overshoot resolution remains unconfirmed.

## Pico Setup 1.0.1

- Leave the existing pca9685.py driver out of Update transfers, preserving device-specific servo_min_us/servo_max_us pulse calibration byte-for-byte. Reject incompatible/ambiguous legacy initialization before upload. No servo drive/retry policy changes.

- Explain existing-controller Update without BOOTSEL, detect UF2 boot drives read-only, and refresh USB selection automatically after reconnection. No firmware reflashing or configuration reset is introduced.
- Propagate the bundled backend return code; stop on failed commands instead of continuing through ignored errors. Show safe failed-step/code diagnostics without raw credentials, retain/copy status, and test both backend success/failure in native app smoke checks. The reported Windows device failure remains unconfirmed pending its new diagnostic code.

## Pico Setup 1.0.0 — standalone USB tool

- Added native Windows exe and Mac arm64/Intel app bundles containing Python, Qt and mpremote, with a compact dark Initial setup / Update GUI. No Python or uv installation is required on the user PC.
- Reuse the staged/verified USB updater, preservation and private backups; isolate bundled backend processes and prevent closing the GUI during upload. Native packaging smoke tests never open a serial port. The main desktop version is unchanged.

## Unreleased — Pico USB tools

- Added Windows/Mac launchers for first-time Pico setup and settings-preserving updates, with explicit USB selection, private backups, staged transfer verification and rollback on ordinary replacement failure.
- Defaulted fresh Pico configuration and updater migrations to automatic IP addressing (DHCP), preserving calibration, wiring, Wi-Fi credentials and shared labels. Desktop v0.6.4 and its existing downloads are unchanged.

## 0.6.4

- Use the common app-owned directory layout: config/config.json, run, results and logs beneath ~/.kohdalab/shutter.
- Align normal startup, file selection, external API/Notebook discovery and documentation. Preserve operator-selected paths and all old files without automatic migration.
- Common control SDK 1.0.1 discovers app-owned run directories; wire protocol and instrument safety are unchanged.


## 0.6.3

- Automatically create the missing application-specific default configuration on first normal GUI launch.
- Preserve existing/corrupt profiles with atomic no-clobber creation and report initialization errors. Do not connect hardware or enable outputs.


## 0.6.2 — 2026-10-29

- Add the authenticated local Control Protocol 1 adapter and shared Python SDK. Camera exposes read-only status/configuration; other apps retain their native ownership and safety policies.
- Align common discovery, receipts, structured errors, PR templates and release categories. Existing measurement data and native clients remain supported.
- GUI共通API・独立したPython SDK・PR/Releaseの記載項目を統一。既存測定とデータ形式を維持します。

## 0.6.1 — 2026-10-29

- Simplified each shutter to a CH number, Enter-to-apply name box and clickable light-window Toggle. Unconfirmed text is discarded on Escape or clicking elsewhere.
- Moved Disconnect into the connection-name menu, compacted the status/version header, and arranged the connection picker as controllers beside a vertical channel list with a standard-sized Connect button.
- Queued one manual Toggle during background polling without retrying commands after a transport failure. External API behavior and v0.6.0 Pico firmware remain unchanged.

## 0.6.0 — 2026-10-29

- Removed All buttons from the compact GUI and promoted shared channel names above small physical CH identifiers.
- Consolidated Pico/channel names, layout, order and API settings in Settings, with debounced automatic saving and explicit failure/retry state.
- Added atomic shared-name patches on Pico and application-identified PC preferences at ~/.kohdalab/shutter/config.json; restored choices never auto-acquire hardware. Preserved unknown fields and protected corrupt/foreign settings.
- Unified Windows installation under Program Files with admin/HKLM and all-user shortcuts, matching the other KohdaLab apps. Existing data/old installations are not deleted or migrated.

## 0.5.0 — 2026-10-29

- Split connection selection from compact controls: shared Pico labels, explicit available-CH selection, only acquired channels displayed, small status/version header, and layout/order/API settings in the overflow menu.
- Added authoritative atomic per-CH Pico leases, renewal/release/expiry, legacy-client and physical-button lock enforcement, shared label persistence, and double-flash connected LEDs. Requires updated Pico main.py and new sessions.py; existing calibration/Wi-Fi settings remain intact.
- Scoped external API and All actions to acquired channels. Verified three real GUIs sharing a simulated Pico without operating hardware.

## 0.4.3 — 2026-10-29

- Added a Windows x64 Setup.exe with per-user installation, Start menu/Desktop shortcuts, in-place updates and an Apps uninstaller that preserves user settings and unrelated files. The portable ZIP remains available.
- Added native Windows installation/reinstallation/uninstallation verification and included Setup in release provenance and SHA-256 checks. Installer and uninstaller remain unsigned pending provider approval.

## 0.4.2 — 2026-10-29

- Defaulted Pico motion concurrency to every configured channel, allowing All actions to overlap instead of waiting for each channel's settling delay. Existing device settings require updating; movement stepping and PWM release stay configurable.
- Added paired Connect / Disconnect controls and removed the transient polling message above the shutters. Reserved fixed spinner geometry so neither layout moves during periodic refreshes.
- Added a real egui geometry regression for polling and a same-tick parallel firmware regression.

- Prepared the same SignPath approval/first-party policy as TRKR/IV, exact unsigned GUI/CLI review artifacts, Windows product/version resources, and strict signature/publisher/timestamp verification.
- Added an owner-activated protected Mac Developer ID/notarization workflow with hardened runtime, Accepted receipts, stapling, Gatekeeper checks and final checksums. Real provider execution remains pending owner enrollment/approval/credentials; v0.4.1 downloads remain unchanged.

## 0.4.1 — 2026-10-29

- Added downloadable Windows x64 ZIP and macOS Universal app/DMG packages, including dependency/font licenses, build origins and SHA-256 checksums.
- Added tag-driven GitHub Releases publication after platform/package validation, with native Apple Silicon and Intel smoke checks.

- Added numeric ascending/descending display order, CLI `--order`, and GUI API `set_order`; hardware channel identities stay fixed.
- Added front-facing light-window graphics: sliding leaves reveal light for Open and cover it for Close, with distinct Moving / Unknown states.
- Matched TRKR's dark surfaces, borders, compact button corners, and blue selection color; grouped all-channel actions in the sidebar, reduced persistent help text, and kept the version beside the app title.
- Kept numeric ordering, both layouts, and external API behavior unchanged.

- Added the authenticated GUI API v2 with exclusive ownership, idempotent action receipts, and a stdlib Python/Jupyter client.
- Simplified the desktop to a left sidebar and horizontal/vertical shutter switches inspired by the physical controller.
- Replaced primary angle readouts with calibrated Open / Close / Moving / Unknown states; added the Pico `STATE` command.
- Added native GUI/API simulation validation and weak-reference heartbeat cleanup.

- Added the Rust `0.3.0` desktop GUI and CLI with automatic Pico W discovery and explicit device selection.
- Added bounded nonblocking UDP discovery on Pico W while retaining MicroPython servo control.
- Added USB IP-inspection instructions and a DHCP migration path.
- Switched Windows desktop launchers to the Rust executable; Python clients remain for compatibility.

- Added non-blocking, stepped servo motion with one-at-a-time current limiting.
- Added automatic PWM release after motion to prevent continuous endpoint stall current.
- Added channel and angle validation before hardware outputs are enabled.
- Added physical-button debouncing and explicit moving-state LED/GUI feedback.
- Prevented ambiguous `TOGGLE` commands from being retried after a lost response.
- Added strict protocol parsing and actionable connection and command errors.
- Added installable CLI/GUI entry points and Python 3.13/3.14 package metadata.
- Added linting, strict core type checks, dependency auditing, and 100% core branch coverage.
