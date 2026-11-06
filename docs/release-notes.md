# KohdaLab Shutter 0.6.7

## Faster shutter feedback / 開閉表示の応答改善

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
