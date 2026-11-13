# Maintained GUI stack / GUI依存の保守更新

Unreleased change: egui/eframe 0.34.3 replaces the old renderer dependency on
unmaintained `ttf-parser`. The minimum Rust version is 1.92. Existing shutter
commands, channel layout and safety policies remain unchanged. Root-UI lifecycle
and test harnesses follow the new API; existing assertions are retained.

未公開の変更としてegui/eframeを0.34.3へ更新し、描画経由の保守終了した`ttf-parser`を除きました。
最低Rust版は1.92です。開閉操作・チャンネル配置・安全方針は維持し、GUIとテストの
ライフサイクルを新APIへ移行しています。既存の期待値は変更していません。

Local validation: 69 Rust tests, strict Clippy, 16 package/installer tests, and
common-control API against the native Mac GUI in Demo mode passed. Pinned upstream
license notices are shipped with hash checks. Windows/Mac package CI is required
for the final commit; local results alone are not release certification.

ローカルではRust 69件、strict Clippy、配布・インストーラー16件、Mac実GUIのDemoによる
共通API検証が成功しました。上流コミットを固定したライセンス文をハッシュ検証して同梱します。
最終コミットのWindows/Mac配布CIを別途確認し、ローカル結果だけで品質保証とはしません。

New physical fault/stop tests were waived by the operator this round. Existing
operation history is not recorded as a newly passed hardware test.

利用者の指示により今回の新たな実機異常・停止試験は省略しました。
既存の運用実績を今回の実機試験合格として記録しません。

The idle GUI is explicitly woken after an authenticated API request enters its
queue. CLI startup, saved preferences and the settings toggle share this path.
A regression test proves unauthorized requests do not wake the GUI, and the
loopback fake-Pico test exercises three real GUI processes with separate channel leases.

認証済みAPI要求をキューへ入れた時に待機中GUIを起こす処理を追加しました。
CLI起動・保存設定・設定画面からの有効化で共通の起動経路を使用します。
未認証要求ではGUIを起こさない回帰試験と、疑似Pico・実GUI3個によるチャンネル別制御権の試験が成功しています。

## Common SDK lease race / 共通SDKの制御権競合

The Python SDK now serializes lease transitions and rejects retired heartbeat
workers by generation. A heartbeat queued before voluntary release cannot poison
the next acquisition. Real active-lease revocation remains an error. Deterministic
regression tests cover both cases; the common SDK suite passes 16 tests.

Python SDKでは制御権の遷移を排他化し、終了したheartbeatを世代で判別します。
正常な解放の前に待機していたheartbeatが次の制御権取得を誤って失敗させる競合を修正しました。
実際の制御権喪失は引き続きエラーとし、両ケースの再現試験を含む共通SDK 16件が成功しています。

## Hidden-window processing / ウィンドウ非表示時の処理

Background acquisition, API requests, stop handling and worker results run in
`App::logic`, separately from visible rendering in `App::ui`. This is required by
eframe 0.34 when a window is hidden or covered. A regression drives the logic
without drawing and verifies that worker/acquisition progress is still consumed.

測定・API・停止・ワーカー結果の処理を`App::logic`へ分離し、表示は`App::ui`で行います。
eframe 0.34で画面が非表示・被覆された場合も処理を継続するための対応です。
描画を実行せずlogicだけを動かし、処理の進行を受け取れることを回帰試験で確認します。
