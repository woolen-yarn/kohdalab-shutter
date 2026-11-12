# KohdaLab Pico Setup 1.2.2

- The USB updater recognizes both Raspberry Pi Pico W and Pico 2 W running MicroPython.
- Files are read in small chunks and checked against SHA-256 computed on the Pico. If the read is incomplete or corrupt, the updater stops before replacing any files.
- The corrected updater was used on a Pico 2 W with MicroPython 1.28.0. The server firmware is unchanged from 1.2.1. Windows is unsigned. macOS is ad hoc signed and not notarized. [Setup instructions](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/pico-upload.md)

## 日本語

- MicroPython が動作する Raspberry Pi Pico W と Pico 2 W の両方を USB 更新ツールが認識します。
- ファイルを小分けに読み取り、Pico 側で計算した SHA-256 と照合します。読み取りに欠落や破損があれば、Pico のファイルを置き換える前に停止します。
- 修正した更新ツールを MicroPython 1.28.0 の Pico 2 W 実機で確認しました。Pico 上で動作するファームウェアは 1.2.1 と同じです。Windows 版は未署名、macOS 版はアドホック署名で未公証です。 [セットアップ手順](https://github.com/woolen-yarn/kohdalab-shutter/blob/main/docs/pico-upload.md)
