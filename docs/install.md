# Install the desktop app / デスクトップアプリの導入

Download the current version from [GitHub Releases](https://github.com/woolen-yarn/kohdalab-shutter/releases/latest). The desktop app does not require Rust or Python.

[GitHub Releases](https://github.com/woolen-yarn/kohdalab-shutter/releases/latest)からダウンロードします。PCでアプリを使うためにRust・Pythonを導入する必要はありません。

| Platform / OS | Download / 配布ファイル | Start / 起動方法 |
| --- | --- | --- |
| Windows 10/11, x64 | `kohdalab-shutter-<version>-windows-x64-Setup.exe` | Run Setup, then open KohdaLab Shutter from Start or the desktop. / Setupを実行後、スタートメニューまたはデスクトップから起動 |
| macOS 13+, Apple Silicon / Intel | `kohdalab-shutter-<version>-macos-universal.dmg` | Open the DMG, drag `KohdaLab Shutter.app` to Applications, then open the app. / DMGを開き、アプリをApplicationsへドラッグして起動 |

The Windows ZIP remains a portable alternative: extract it entirely and open `kohdalab-shutter-gui.exe`. Setup installs for the current user without administrator rights, under `%LOCALAPPDATA%\Programs\Kohdalab\KohdaLab Shutter`. Close the app before updating by running the new Setup. Remove it through **Settings → Apps → Installed apps → KohdaLab Shutter → Uninstall**; user settings and unrelated files are preserved.

WindowsのZIP版も引き続き利用できます。Setup版は管理者権限不要で現在のユーザーへインストールします。更新時はアプリを閉じて新しいSetupを実行します。削除は「設定 → アプリ → インストールされているアプリ → KohdaLab Shutter → アンインストール」から行い、ユーザー設定・無関係なファイルは保持します。

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

1. Prepare and start the Pico W server. Firmware setup remains a separate [MicroPython upload step](rust-client.md).
2. Open the desktop app, select **Find Pico W**, choose a controller and **Connect**.
3. Use **Open / Close**, or **Open all / Close all**. Horizontal / Vertical and CH ↑ / CH ↓ affect display only.

1. [Pico Wの設定手順](rust-client.md)に従ってサーバーを転送・起動します。初回転送にはPython/uv等が必要です。
2. PCアプリの **Find Pico W** から機器を選択し、**Connect**で接続します。
3. **Open／Close** または **Open all／Close all**で操作します。

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
