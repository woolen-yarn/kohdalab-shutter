# Install the desktop app / デスクトップアプリの導入

Download the current version from [GitHub Releases](https://github.com/woolen-yarn/kohdalab-shutter/releases/latest). The desktop app does not require Rust or Python.

[GitHub Releases](https://github.com/woolen-yarn/kohdalab-shutter/releases/latest)からダウンロードします。PCでアプリを使うためにRust・Pythonを導入する必要はありません。

| Platform / OS | Download / 配布ファイル | Start / 起動方法 |
| --- | --- | --- |
| Windows 10/11, x64 | `kohdalab-shutter-<version>-windows-x64-Setup.exe` | Run Setup, then open KohdaLab Shutter from Start or the desktop. / Setupを実行後、スタートメニューまたはデスクトップから起動 |
| macOS 13+, Apple Silicon / Intel | `kohdalab-shutter-<version>-macos-universal.dmg` | Open the DMG, drag `KohdaLab Shutter.app` to Applications, then open the app. / DMGを開き、アプリをApplicationsへドラッグして起動 |

The Windows ZIP remains a portable alternative: extract it entirely and open `kohdalab-shutter-gui.exe`. Setup installs for all users under `%ProgramFiles%\Kohdalab\KohdaLab Shutter` and requires administrator approval. Close the app before updating by running the new Setup. Remove it through **Settings → Apps → Installed apps → KohdaLab Shutter → Uninstall**; user settings and unrelated files are preserved.

WindowsのZIP版も引き続き利用できます。Setup版は管理者の許可を得て全ユーザー向けに `%ProgramFiles%\Kohdalab\KohdaLab Shutter` へ導入します。更新時はアプリを閉じて新しいSetupを実行します。削除は「設定 → アプリ → インストールされているアプリ → KohdaLab Shutter → アンインストール」から行い、ユーザー設定・無関係なファイルは保持します。

The Mac ZIP is an alternative to the DMG; both contain the same universal app. Windows ARM64 and Linux binaries are not provided in this release.

MacのZIP版はDMG版と同じUniversalアプリです。このリリースではWindows ARM64・Linux向けバイナリは配布していません。

For future trusted builds, see [signing setup](code-signing.md). The current downloads remain unsigned/ad-hoc until provider enrollment and activation.

今後の正規署名・公証の準備は[設定手順](code-signing.md)を参照してください。現在の配布版は、署名サービスの承認・設定が済むまでは未署名・アドホック署名です。

## First launch / 初回起動

These builds are not publisher-signed or Apple-notarized. The Mac app has a local ad-hoc signature for integrity and Apple Silicon execution; it does not identify a trusted publisher.

今回の配布物は発行元の署名・Appleの公証がありません。Mac版のアドホック署名は整合性と実行のためのもので、信頼済み発行元の署名ではありません。

- Windows may show an unknown-publisher or SmartScreen prompt. Confirm the download is from this repository and, if the system offers it and your organization permits it, choose **More info → Run anyway**.
- macOS may block the first launch. After verifying the source, use **System Settings → Privacy & Security → Open Anyway**, if available. Do not disable Gatekeeper or remove security settings globally. [Apple's instructions](https://support.apple.com/guide/mac-help/open-a-mac-app-from-an-unknown-developer-mh40616/mac).
- Allow local-network access when requested; **Find Pico W** needs local UDP communication. An OS permission does not override laboratory Wi-Fi restrictions.

- Windowsで警告が出た場合は、このリポジトリから取得したことを確認し、組織のルールとOSの選択肢に従って「詳細情報 → 実行」を選びます。
- Macでブロックされた場合は、入手元を確認して「システム設定 → プライバシーとセキュリティ → このまま開く」を使用します。OSがこの操作を許可しない管理環境では管理者に相談してください。
- ローカルネットワークへのアクセスを求められたら許可します。研究室Wi-Fi側で端末間通信が禁止されている場合は別途対処が必要です。

## Connect to Pico W / Pico Wへ接続

1. Update/start the Pico firmware as below, then choose **Find Pico W**.
2. Select a controller by its label. Names are shown on both connection and control screens.
3. Select the available channels and **Connect**. In-use channels are disabled; acquisition is atomic if another PC connects at the same time.
4. Click a light window to toggle its shutter. Edit its name below the CH number and press **Enter** to apply; Escape or clicking elsewhere cancels unconfirmed text. **··· → Settings** contains Pico name, layout, order and local API. Confirmed names and settings save automatically.
5. Choose **controller name ▾ → Disconnect**, or close the window, to release your channels. After a crash/network loss, the Pico releases them after 15 seconds; position is held.

1. 下記手順でPicoを更新・起動し、**Find Pico W**で検索します。
2. ラベルで機器を選びます。名前は接続後のSettingsで変更できます。
3. 空いているCHを選んで **Connect**。使用中CHは選べず、複数人が同時に取得しても重複使用しません。
4. 光の窓を押すと開閉を切り替えます。CH番号の下の名前欄を編集し、**Enter**で確定します。Escapeや欄外クリックは未確定の編集を戻します。**··· → Settings**にPico名・配置・順序・外部APIをまとめ、確定した名前と設定を自動保存します。
5. **接続名 ▾ → Disconnect**または画面を閉じて解放します。通信断・異常終了時は15秒で解放し、位置は維持します。

## Pico firmware update / Pico側の更新

Use the standalone [Pico Setup app](pico-upload.md) for initial USB transfer or updates. Download the native Windows/Mac ZIP and open the app; Python and uv are bundled. Initial setup and Update both use DHCP. Updates back up and preserve existing calibration, pins, Wi-Fi and labels. A fresh Pico still needs the one-time MicroPython UF2 installation.

初回転送・更新には専用の[Pico Setupアプリ](pico-upload.md)を使えます。Windows／Mac用ZIPを展開してアプリを開くだけで、Python・uvの導入は不要です。初回／更新ともDHCPで、更新は既存の校正・配線・Wi-Fi・ラベルをバックアップして保持します。新品PicoだけMicroPython本体の導入が一度必要です。

A connected CH repeats two short LED flashes with a pause, using green for Open and red for Close. An unclaimed CH keeps the waiting blink. Physical short presses cannot change a leased CH; long-press server stop remains available. Raw commands from old clients are also rejected for leased CHs.

接続CHは緑（Open）・赤（Close）で二連点滅し、未使用CHは待機点滅を続けます。使用中CHへの物理ボタン短押し・旧クライアントからの操作も拒否します。長押しによるサーバー停止は引き続き可能です。

For a hardware-free preview, Windows includes a **KohdaLab Shutter Demo** Start menu shortcut (or `Demo.cmd` in the portable ZIP). On Mac, run:

実機なしで試す場合、Windowsはスタートメニューの **KohdaLab Shutter Demo**（ZIP版は`Demo.cmd`）、Macは次のコマンドを使用します。

```sh
open -a 'KohdaLab Shutter' --args --demo
```

## CLI and automation / CLIと外部制御

The Windows installer and ZIP include `kohdalab-shutter.exe`. On Mac, the CLI is inside the app:

Windowsのインストール先とZIPには`kohdalab-shutter.exe`を同梱しています。MacのCLIはアプリ内にあります。

```sh
'/Applications/KohdaLab Shutter.app/Contents/MacOS/kohdalab-shutter' --help
```

The GUI's **Local control API** supports Python/Jupyter through the [Python client](../bindings/python/README.md). Python is needed only for that integration, not for operating the GUI.

## Checksums and contents / 配布物の確認

`SHA256SUMS.txt` lists checksums for the Setup/ZIP/DMG files. `BUILD-*.json` records the exact source commit and artifact hashes. Each app includes the project license and dependency/font notices. Do not copy the example Wi-Fi file into a release with real credentials.

`SHA256SUMS.txt`にSetup・ZIP・DMGのハッシュ、`BUILD-*.json`にビルド元コミットを記録しています。ライセンスと依存ライブラリ・フォントの表記も同梱します。Wi-Fiパスワード等の個人設定は含めません。

## Application directories

Windows Setup uses `C:\Program Files\Kohdalab\KohdaLab Shutter`;
macOS uses `/Applications/KohdaLab Shutter.app`. Local desktop preferences use
`~/.kohdalab/shutter/config/config.json` (Windows: `%USERPROFILE%\.kohdalab\shutter\config\config.json`).
Pico calibration, network settings, and shared device/channel names remain on the
controller. The application-owned `.kohdalab/shutter/run` directory is API discovery, not the
application settings file. Updating or uninstalling the desktop app preserves
these user settings and never resets the Pico.

## Automatic settings / 設定の自動保存

Edit a channel name directly below its CH number and press **Enter** to apply; Escape or clicking elsewhere discards unconfirmed text. Edit the Pico name in **··· → Settings**. Confirmed channel names save automatically, and valid Pico names save after a short pause; other connected PCs receive the new names on refresh. Only your acquired CHs can be renamed. Changes patch only edited fields, preserving other users' channel names, calibration, network and unknown config fields. Saving failures keep the control window open and display an error/Retry.

PC settings auto-save to the application-owned config file listed above. It includes layout/order, CH selection, broadcast/manual endpoint and API opt-in, plus a cache of confirmed names. It excludes session tokens and never automatically re-acquires channels. Unknown JSON fields survive; corrupt, unsupported and foreign application files remain untouched. Old settings/installations are not automatically migrated or deleted. If an older per-user shortcut launches v0.5.0, start the new Program Files application; remove the old installation manually only when you no longer need it.

CH名は操作画面の入力欄でEnterを押すと確定し、自動保存します。Pico名はSettings内で入力後、短く待つと自動保存します。名前はPicoへ、表示・接続・APIの設定はPCへ保存します。保存失敗時はエラーを表示し、開閉操作の接続は維持します。古いファイルやインストールは自動削除しません。旧ショートカットから旧版が起動する場合はProgram Files内の新版を使用してください。
