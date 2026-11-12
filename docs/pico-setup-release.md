# KohdaLab Pico Setup 1.2.1

- Initial Wi-Fi connection attempts run in the background and retry while local buttons and servo updates continue. Hold a button for three seconds to cancel.
- The controller continues servicing local buttons and servos while waiting for TCP input. The firmware also supports a combined lease renewal, state and fault poll for Shutter 0.6.11. Existing clients remain compatible.
- The bundled firmware was tested with simulated hardware. The packaged setup app was smoke-tested without opening USB. Windows is unsigned. macOS is ad hoc signed and not notarized. [Setup instructions](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/pico-upload.md)

## 日本語

- 初回の Wi-Fi 接続と再試行をバックグラウンドで行い、物理ボタンとサーボの処理を続けます。3秒長押しで接続試行を中止できます。
- TCP 入力待ち中も物理ボタンとサーボを処理します。Shutter 0.6.11 は所有権更新・状態・異常を1回の要求で取得できます。既存クライアントも引き続き使えます。
- ファームウェアは模擬環境で検証し、配布アプリは USB を開かず起動確認しました。実機検証は未実施です。Windows 版は未署名、macOS 版はアドホック署名で未公証です。 [セットアップ手順](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/pico-upload.md)
