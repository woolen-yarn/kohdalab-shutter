# KohdaLab Shutter 0.6.5

## Changes

PC preference saves now remain pending after a transient failure and retry after five seconds. The visible error clears only after a successful save.

The bundled common Python control client now ignores an empty native home-directory environment variable and uses a valid platform fallback. Its JSON Lines response reader scans only newly received bytes, while retaining the established response-size limit and error behavior.

## Compatibility and safety

The common SDK remains 1.0.1 and the control wire protocol remains version 1. Shutter command semantics, channel state, lease behavior, Pico firmware, and safety policy are unchanged. Existing settings remain preserved; this release does not migrate or delete profiles.

## Downloads and validation

This release provides Windows Setup and portable artifacts, supported macOS distribution, and corresponding source/build evidence. Windows artifacts are unsigned; supported macOS applications are ad hoc signed and not notarized. CI checks the packaged software, installer evidence, and artifact/source hashes. It does not constitute new physical Pico, wiring, or optical-path qualification.

## 日本語

PC設定の保存が一時的に失敗した場合は未保存状態を保持し、5秒後に再試行します。表示上のエラーは保存に成功した後だけ消えます。

同梱の共通Python制御クライアントは、OS固有のホームディレクトリ環境変数が空の場合に有効なプラットフォーム側フォールバックを使用します。JSON Lines応答は新しく受信したバイト列だけを走査し、既存の応答サイズ上限とエラー動作を維持します。

## 互換性と安全性

共通SDKは1.0.1、制御通信プロトコルはv1のままです。シャッター指令の意味、チャンネル状態、leaseの動作、Pico firmware、安全方針は変更しません。既存設定は保持し、プロファイルの移行・削除は行いません。

## 配布と検証

Windows Setupとportable成果物、対応するmacOS配布物、source/build証跡を提供します。Windows成果物は未署名で、対応するmacOS appはad hoc署名・未notarizeです。CIはパッケージソフトウェア、installer証跡、成果物とソースのハッシュを検証しますが、新たなPico、配線、光路の実機認定を意味しません。
