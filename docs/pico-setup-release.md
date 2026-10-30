# KohdaLab Pico Setup 1.0.0

Standalone USB installer/updater for the Shutter Pico W. Python, uv, Thonny and a Rust build are **not required on the user's PC**. The runtime, USB tools and Shutter server files are bundled.

ShutterのPico Wに初回転送・更新する専用アプリです。**利用するPCにPython・uv・Thonnyをインストールする必要はありません。** 実行環境・USB転送機能・Pico側プログラムを同梱しています。

- Windows x64: extract the entire Windows ZIP, then double-click `KohdaLab Pico Setup.exe`. Keep `_internal` beside it.
- Mac: choose arm64 (Apple Silicon) or x64 (Intel), extract the ZIP and open `KohdaLab Pico Setup.app`.
- Select the USB Pico and Initial setup or Update. Initial setup asks for Wi-Fi details; Update keeps them. Both use automatic IP addressing (DHCP).
- Existing files are backed up. Calibration, pins, motion limits and shared labels are preserved on Update. New files are staged, verified and compiled before replacement.

WindowsはZIPをすべて展開し、`KohdaLab Pico Setup.exe`をダブルクリックします。MacはApple Silicon用／Intel用を選び、ZIP内の`.app`を開きます。対象Picoと初回／更新を選び、初回だけWi-Fi情報を入力します。どちらもDHCPです。更新時の校正・配線・Wi-Fi・ラベル保持とバックアップは従来のUSBツールと同じです。

A fresh Pico still needs the one-time Pico W MicroPython UF2 installation using BOOTSEL; the app's **New Pico?** button explains it. No PC dependency installation is needed. The app never flashes hardware on launch. Physical USB/Wi-Fi/servo qualification must be performed on the target; automated smoke tests use demo mode and the embedded backend's version command only.

新品Picoには、BOOTSELを使うMicroPython本体の初回導入が一度必要です。アプリの **New Pico?** に案内があります。アプリ起動だけで実機を書き換えることはありません。実機USB・Wi-Fi・サーボは未検証で、配布チェックはデモ起動と同梱転送機能の起動確認です。

Windows is unsigned; Mac is ad-hoc signed, not notarized. Existing provider enrollment is still pending. This dedicated tool release does not replace the main Shutter desktop download or its version. SHA256SUMS and BUILD files record the three native app archives and exact source commit. Qt/Python/USB dependency notices are bundled with the replaceable shared libraries.

[Instructions / 手順](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/pico-upload.md)
