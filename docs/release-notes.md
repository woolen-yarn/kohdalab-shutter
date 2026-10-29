# KohdaLab Shutter 0.6.2

## Changes / 変更内容

Add Control Protocol 1 with opaque ownership, canonical operation receipts and the same standalone Python SDK as the desktop suite. Keep the compact light-window GUI and native API. Package common SDK sources and align GitHub maintenance conventions.

## Compatibility and migration / 互換性と移行

Hold-last-state release is unchanged and reports cleanup `not_required`; commanded position is not measured optical transmission. No Pico update is needed when compatible v0.6.0 firmware is already installed. Firmware and desktop versions remain separate. No hardware is flashed automatically.

## Downloads / ダウンロード

Windows x64 Setup/portable ZIP; macOS universal ZIP/DMG; corresponding source, dependency notices and checksums. Windows is unsigned; Mac is ad hoc signed, not Developer ID signed or notarized.

[Release packages](https://github.com/woolen-yarn/kohdalab-shutter/releases). Existing older releases remain available.

## Validation and provenance / 検証と出所

Local Rust application/common suites: 63 passed. Actual Demo GUI covered native regression plus common open/result/wait, duplicate receipts and truthful release cleanup. Package/installer tests passed. Platform CI validates Windows/macOS packages.

The common Python SDK has seven device-free tests. Source/build identifiers, package manifests and SHA-256 evidence accompany the release. These checks do not newly qualify physical instruments, optical closure, camera calibration or scientific accuracy.

## 日本語

共通GUI APIを追加しました。解放時の状態保持と既存操作を維持し、光学センサーによる確認とは区別します。互換ファームウェアv0.6.0導入済みならPicoの更新は不要です。実機を新たに動かした検証は行っていません。
