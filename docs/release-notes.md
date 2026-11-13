# KohdaLab Shutter 1.0.0

The GUI shows **Disconnecting…** while it releases the selected Pico channels, and **Disconnected** after completion. The common GUI control API exposes Shutter discovery, connection, status and channel commands. Disconnecting leaves the shutters in their last commanded state.

The pre-release candidate was exercised on a Pico 3900S at Nautilus. CH0 reported 0°, 90°, then 0° after the open and close commands. The GUI layout was reviewed on Nautilus. The final 1.0.0 packages require their own verification before publishing.

## 日本語

GUIは選択したPicoチャンネルを解放している間に **Disconnecting…**、完了後に **Disconnected** を表示します。共通GUI制御APIで機器の検出・接続、状態取得、チャンネル操作ができます。切断後は最後に指令した開閉状態を保持します。

NautilusのPico 3900Sで公開前候補を試験し、CH0の開閉指令に対して0°、90°、0°の応答を確認しました。NautilusでGUIのレイアウトも確認しました。公開前に1.0.0の最終配布物を検証します。

---

# KohdaLab Shutter 0.6.13

- After a temporary failure to read status, Shutter retries with the same Pico lease while that lease may still be valid. During recovery, channel states display `Unknown` and the GUI rejects shutter commands without sending them. The operation journal records interruption and recovery.
- A refused TCP connection, a reported lease loss, or the end of the retry window still ends the connection. Existing Pico firmware, including the firmware from Pico Setup 1.2.2, can be used with this release.
- The release includes the source ZIP, build manifests, SHA-256 checksums and Linux GUI API simulation evidence. Windows packages are unsigned. macOS packages are ad hoc signed and not notarized. Recovery was tested with a simulated Pico. Physical-device Wi-Fi recovery was not tested.

## 日本語

- 状態取得が一時的に失敗したときは、Pico のチャンネル確保が有効な間、同じトークンで再試行します。復旧待ちの間は状態を `Unknown` と表示し、開閉指令の送信を止めます。中断と復旧は操作ジャーナルに記録します。
- 接続拒否、確保喪失の通知、再試行期限切れでは切断します。Pico Setup 1.2.2 を含む既存の Pico ファームウェアを利用できます。
- ソース ZIP、ビルド記録、SHA-256、Linux GUI API の模擬検証結果を同梱します。Windows 版は未署名、macOS 版はアドホック署名で未公証です。通信復帰は模擬 Pico で検証し、実機の Wi-Fi 復帰は未検証です。

---

# KohdaLab Shutter 0.6.12

- Device replies wake the GUI as soon as the background task completes. This reduces the time between receiving a reply and processing it on the GUI thread.
- [Pico Setup 1.2.2](https://github.com/woolen-yarn/kohdalab-shutter/releases/tag/pico-tools-v1.2.2) fixes USB updates for Pico 2 W and verifies backups before writing. A controller already running the 1.2.1 firmware can continue to use it.
- The release includes the source ZIP, build manifests, SHA-256 checksums and Linux GUI API simulation evidence. Windows packages are unsigned. macOS packages are ad hoc signed and not notarized. The GUI wake-up change was tested in software.

## 日本語

- 機器からの応答をバックグラウンド処理が受け取ると GUI を即座に起こし、状態反映までの待ち時間を減らします。
- [Pico Setup 1.2.2](https://github.com/woolen-yarn/kohdalab-shutter/releases/tag/pico-tools-v1.2.2) は Pico 2 W の USB 更新を修正し、書き込み前にバックアップを検証します。すでに 1.2.1 のファームウェアで稼働中の Pico はそのまま使えます。
- ソース ZIP、ビルド記録、SHA-256、Linux GUI API 模擬検証結果を同梱します。Windows 版は未署名、macOS 版はアドホック署名で未公証です。GUI の変更はソフトウェアで検証しました。

---

# KohdaLab Shutter 0.6.11

- GUI API requests received during a device refresh wait in the existing bounded queue until the refresh finishes, subject to their request deadline.
- With [Pico Setup 1.2.1 firmware](https://github.com/woolen-yarn/kohdalab-shutter/releases/tag/pico-tools-v1.2.1), each refresh uses one TCP connection to renew the lease and read state and faults. Older firmware uses the existing three requests.
- The release includes the source ZIP, build manifests, SHA-256 checksums and Linux GUI API simulation evidence tied to the tagged commit. Windows packages are unsigned. macOS packages are ad hoc signed and not notarized. This release was tested in simulation without a physical Pico or shutter.

## 日本語

- 機器の定期更新中に届いた GUI API の要求は、期限内であれば既存のキューで待機し、更新後に処理されます。
- [Pico Setup 1.2.1 のファームウェア](https://github.com/woolen-yarn/kohdalab-shutter/releases/tag/pico-tools-v1.2.1)では、定期更新1回につき TCP 接続1回で所有権を延長し、状態と異常を取得します。旧ファームウェアでは従来の3要求を使います。
- ソース ZIP、ビルド記録、SHA-256、タグのコミットに紐付いた Linux GUI API 模擬検証結果を同梱します。Windows 版は未署名、macOS 版はアドホック署名で未公証です。実機の Pico とシャッターによる検証は行っていません。

---

# KohdaLab Shutter 0.6.10

## Changes

- **Channel faults are visible.** When the Pico reports an I2C write fault on a channel, the GUI shows `Fault` in red on that shutter and CLI `info` marks the channel. The operation journal records when a channel enters and leaves the fault state. Clicking a faulted shutter sends a new command, which is how the Pico retries the channel.
- **Scripts can see faults.** Each channel in GUI API `status` has a boolean `fault`. The `state` value keeps its existing meaning, so existing scripts read the same strings. Python `wait_for_state()` raises `GuiShutterError` with `code == "fault"` immediately instead of waiting for its timeout. The Python client package `kohdalab-shutter-api` is 0.6.10.
- **Release evidence is published with the packages.** See Validation and provenance.

## Compatibility and migration

- Fault reporting needs the firmware in [Pico Setup 1.2.0](https://github.com/woolen-yarn/kohdalab-shutter/releases/tag/pico-tools-v1.2.0). With older firmware this desktop version works as 0.6.9 did and never shows `Fault`. Older desktop versions work with the new firmware and ignore the fault report.
- Shutter commands, `STATE`/`STATUS`, the profile format, lease policy and safety behaviour are unchanged. Existing profiles and operation journals remain usable.
- Journal records of type `reported_state_changed` gain a `faulted_channel_ids` array.

## Downloads

| Platform | File |
| --- | --- |
| Windows 10/11 (x64), installer | `kohdalab-shutter-0.6.10-windows-x64-Setup.exe` |
| Windows 10/11 (x64), portable | `kohdalab-shutter-0.6.10-windows-x64.zip` |
| macOS 13+ (Apple Silicon / Intel) | `kohdalab-shutter-0.6.10-macos-universal.dmg` or `.zip` |
| Source of the release commit | `kohdalab-shutter-0.6.10-source.zip` |

Windows binaries are unsigned. Mac applications are ad hoc signed and not notarized. Checksums show that a file is the one built here; they are not a publisher signature. Pico W firmware is installed with the separate Pico Setup app.

## Validation and provenance

- `RELEASE-VERIFICATION.json` records the release commit, its source tree, the validation and release workflow runs, the signing state, and the SHA-256 of every other published file. `SHA256SUMS.txt` covers every published file, including `BUILD-*.json` and `RELEASE-VERIFICATION.json`.
- The publish job accepts the four packages only when each platform's `BUILD-*.json` names the release commit and version and its digests match the bytes.
- `validation-linux-gui-api.json` is the isolated-simulation run of the real GUI and its API, built from the release commit on Linux. The Windows and Mac packages are built, installed or opened, and version-checked in the release workflow, including an Intel Mac run; the GUI API simulation is not repeated on those packages.
- No physical Pico W, servo or optical measurement was involved. Fault display was exercised with simulated controller responses only.

## 日本語

- **CHの異常が見えるようになりました。** PicoがCHのI2C書き込み異常を報告すると、GUIはそのシャッターを赤い`Fault`で表示し、CLIの`info`にも印が付きます。異常の発生と解消は操作ジャーナルに記録します。異常中のシャッターをクリックすると新しい指令が送られ、Picoがそのチャンネルを再試行します。
- **スクリプトから異常が分かります。** GUI APIの`status`の各CHに真偽値`fault`があります。`state`の意味は変わらないので、既存のスクリプトが読む文字列は同じです。Pythonの`wait_for_state()`はtimeoutを待たずに`GuiShutterError`（`code == "fault"`）を出します。Pythonクライアント`kohdalab-shutter-api`は0.6.10です。
- **互換性：** 異常の報告には[Pico Setup 1.2.0](https://github.com/woolen-yarn/kohdalab-shutter/releases/tag/pico-tools-v1.2.0)のファームウェアが必要です。旧ファームウェアでは0.6.9と同じ動作で、`Fault`は表示されません。旧デスクトップ版は新ファームウェアでも動き、異常の報告を無視します。指令、`STATE`/`STATUS`、設定形式、lease方針、安全動作は変わりません。
- **配布物：** Windows版は未署名、Mac版はアドホック署名でApple公証は受けていません。リリースcommitのソースを`kohdalab-shutter-0.6.10-source.zip`として同梱します。
- **検証と来歴：** `RELEASE-VERIFICATION.json`にリリースcommit、ソースtree、検証・配布workflowの実行、署名状態、各ファイルのSHA-256を記録します。`SHA256SUMS.txt`は公開する全ファイルを含みます。`validation-linux-gui-api.json`は、リリースcommitをLinuxでビルドした実GUIとAPIの模擬検証です。WindowsとMacの配布物はビルド・インストールまたは起動・版の確認までで、GUI APIの模擬検証は繰り返していません。実機のPico W・サーボ・光学測定は使用していません。

## 0.6.9 — Maintained GUI runtime and responsive API / GUI実行基盤とAPI応答

The desktop GUI now uses the maintained eframe/egui 0.34 stack and no longer ships the unmaintained font parser. Authenticated API requests wake an idle GUI on every startup path. Controller polling and API processing run independently of visible drawing, so a covered window keeps processing requests and operation outcomes.

Desktop GUIを保守中のeframe/egui 0.34系へ更新し、保守終了したフォント解析を除去しました。認証済みAPI要求はすべての起動経路で待機中GUIを起こします。制御照会・API処理を描画から分離し、ウィンドウが隠れた場合も要求と操作結果の処理を継続します。

The shared Python control client now serializes lease release/reacquisition and ignores retired heartbeat workers. A queued heartbeat from a voluntarily released lease cannot break a later acquisition; real active-lease revocation remains an error.

共通Python制御クライアントでは、制御権の解放・再取得を直列化し、終了済みheartbeatを無視します。正常に解放した制御権の待機heartbeatが次の取得を失敗させることはなく、実際の制御権喪失は引き続きエラーです。

Journal-content tests now wait for an ordered writer acknowledgement before inspecting records. The production 250 ms exit acknowledgement budget is unchanged, and timeout still marks provenance incomplete. This separates record-content verification from disk-speed-dependent scheduling.

操作履歴の内容試験はwriterからの順序付き完了通知を待ってから記録を確認します。実アプリの終了ack上限250 msは変更せず、時間切れは引き続き証跡不完全として記録します。記録内容の検証とディスク速度に依存するスケジューリングを分離しました。

## Compatibility and checks / 互換性と検証

Shutter commands, Pico firmware, profile format, lease policy and safety behavior are unchanged. Existing profiles and operation journals remain usable. Windows Setup/portable and macOS universal ZIP/DMG are verified in CI, including an Intel Mac package smoke test and a native Demo control API test. Windows binaries are unsigned; macOS applications use ad hoc signatures and are not notarized. No new physical-device qualification was performed.

シャッター指令、Pico firmware、設定形式、lease方針、安全動作は変更していません。既存設定・操作履歴は継続して使えます。Windows Setup／portableとmacOS universal ZIP／DMGをCIで検証し、Intel Macの配布アプリ確認とDemo制御API試験も実施しました。Windows版は未署名、macOS版はアドホック署名でApple公証は受けていません。今回、新たな実機適合試験は実施していません。

## 0.6.7 — Faster shutter feedback / 開閉表示の応答改善

### Faster shutter feedback / 開閉表示の応答改善

While selected shutters report Moving, the GUI requests another state update after 100 ms instead of one second. Active tasks and motion repaint every 50 ms; settled shutters return to the existing idle intervals. Transport latency is additional, and only one request task runs at a time. Open/Close remains based on controller feedback; the schematic is not an optical measurement. Motor commands, firmware, lease and safety policies are unchanged.

選択したシャッターがMovingの間は、次の状態取得までの待ちを1秒から100 msに短縮します。処理中・移動中は50 ms間隔で再描画し、停止後は従来の待機間隔に戻します。通信時間は別途かかり、照会は重ねて実行しません。Open／Closeは引き続きコントローラーの報告で確定し、図は光学的な実測ではありません。モーター指令・firmware・lease・安全方針は維持します。

A regression test covers moving, endpoint-but-still-busy, settled and unselected-channel feedback. The operation journal introduced in 0.6.6 remains included.

移動中、端点到達後もbusy、停止確定、未選択チャンネルの状態を回帰テストで確認します。0.6.6で追加した操作履歴の保存も含みます。

## 0.6.6 — Persistent recording / 操作履歴の保存

## Persistent operation history / 操作履歴の保存

Normal GUI sessions now record a host-side JSONL journal under `~/.kohdalab/shutter/logs`. Each operation preserves numeric channel IDs, a linked request/outcome ID, device identity, UTC and monotonic timing. Changed reported servo states and calibration are retained. These are controller reports, not optical measurements. No access tokens or Wi-Fi credentials are recorded.

通常GUIの操作を`~/.kohdalab/shutter/logs`のJSONLへ保存します。実チャンネル番号、要求・結果を結ぶID、機器情報、UTC・単調時計の時刻、変化したサーボ報告値と校正を記録します。コントローラーの報告であり、光学的な開閉測定ではありません。アクセストークン・Wi-Fi認証情報は保存しません。

A bounded background queue keeps disk synchronization off the control path. Storage/queue errors are visible in GUI/API without blocking Close. Normal exit records unresolved operations and requests an ordered terminal record, with a maximum 250 ms acknowledgement wait. Missing terminal records, known record loss and unresolved outcomes remain distinguishable; a journal is not a guarantee of physical shutter closure.

上限付きの別スレッドで書き込み、disk同期が操作を妨げない構成にしました。記録失敗はGUI／APIへ表示し、Closeを妨げません。通常終了時は未確定操作を記録し、終了レコードの確認を最大250 ms待ちます。終了レコード欠落・既知の記録欠落・操作結果未確定を区別し、実際の光学的閉鎖を保証した記録とは扱いません。

## Compatibility and checks / 互換性と検証

Shutter commands, Pico firmware, lease and safety policies are unchanged. Existing profiles are retained. Tests cover event identities, deduplication, disk failure, immediate exit and bounded writer timeout. Windows Setup/portable and Mac packages are verified in release CI. No new hardware qualification is claimed.

指令、Pico firmware、lease、安全方針、既存設定は維持します。操作ID・重複抑制・書込失敗・直後終了・書込み待機上限をテストし、Windows Setup／portableとMac配布物をCIで検証します。新たな実機検証ではありません。
