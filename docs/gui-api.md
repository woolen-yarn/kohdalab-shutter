# GUI control API / GUI外部制御API

The Rust GUI owns the Pico connection. Manual controls and API actions use the same serialized command path; Python/Jupyter attaches to the GUI instead of opening another Pico connection. This is a local-PC API, separate from UDP discovery of Pico hardware.

Pico接続はRust GUIが所有します。手動操作と外部APIは同じ制御経路を使い、Python/JupyterはGUIへ接続します。Pico検索用UDPとは別の、同じPC内のAPIです。

## Enable and attach / 有効化と接続

Enable **Local control API** under **Settings** in the picker or **··· → Settings** in the controls, or launch with `--gui-api`. Add `--demo` to use an isolated simulation. `--api-directory DIR` overrides the endpoint descriptor directory, and explicit startup errors terminate the launch rather than silently disabling the requested API.

接続画面のSettingsまたは操作画面の「··· → Settings」で有効にするか、`--gui-api` を指定します。`--demo` を併用すると実機へ通信しません。接続情報の保存先は `--api-directory DIR` で変更できます。

```sh
cargo run --release --locked --bin kohdalab-shutter-gui -- --demo --gui-api
python -m pip install ./bindings/python
```

See the [Python client guide](../bindings/python/README.md) for complete examples. With real hardware, await the connect receipt before sending a shutter action:

実機では接続ジョブの完了を待ってから開閉を指示します。

```python
from kohdalab_shutter import GuiShutter

with GuiShutter() as shutter:
    connected = shutter.connect(host="192.168.1.42", channels=[0, 2])
    shutter.wait(connected["id"], timeout=10)
    action = shutter.open(0)
    shutter.wait(action["id"], timeout=10)
    shutter.wait_for_state(0, "Open", timeout=10)
```

## Protocol / 通信仕様

Protocol **2** uses one UTF-8 JSON request and response per TCP connection, each terminated by a newline. The listener binds only to `127.0.0.1` on an ephemeral port. An atomic private descriptor lives at `~/.kohdalab/shutter/run/shutter-<pid>-<instance>.json` (Windows: `%USERPROFILE%\\.kohdalab\\shutter\\run`). It contains `app`, `protocol`, `pid`, `instance_id`, `host`, `port`, `address`, and an unpredictable instance `token`. Files are mode 0600 on Unix, and removed on normal API shutdown.

通信は改行区切りJSONです。待受はlocalhostのみで、接続情報はユーザー領域の非公開ファイルに保存します。複数GUIがある場合はPython側で `endpoint=` を明示し、別のGUIを勝手に選択しません。

All requests include `token` and either `method` or the TRKR-style alias `action`. Mutation also requires `client` (UUID), the current `lease`, and a UUID `request_id`.

| Kind / 種別 | Methods / 操作 |
| --- | --- |
| Read-only / 参照 | `capabilities`, `status`, `config`, `result` (`id`) |
| Ownership / 操作権 | `acquire` (`client`, optional `label`), `heartbeat`, `release` |
| Connection / 接続 | `discover`, `connect` (`host` or `device_id`, required `channels`, optional `port`), `disconnect` |
| Shutters / 開閉 | `open`, `close`, `toggle` (`channel`); `open_all`, `close_all` |
| Display / 表示 | `set_layout` (`layout`: `horizontal` or `vertical`); `set_order` (`order`: `ascending` or `descending`) |

Success is `{"ok":true,"result":...,"data":...}`; `data` is a compatibility alias. Failure is `{"ok":false,"error_code":"...","error":"..."}`. No arbitrary shell commands, raw Pico commands, or file-writing methods are exposed.

成功応答の `result` と `data` は同じ内容です。失敗時は `error_code` と説明を返します。任意のシェル実行やPicoへの生コマンドは公開しません。

## Ownership / 操作権

The first Python mutation, or entering `with GuiShutter()`, acquires one exclusive lease. The client heartbeats every two seconds and the GUI expires it after ten seconds without renewal. The top External control banner and the ··· menu identify the external controller; ordinary manual inputs, including per-channel Open/Close, are locked. **Take control** (banner only) revokes that client after the current command task finishes. An expired/revoked client must create a new client UUID to acquire again. Voluntary release permits reuse.

変更操作は排他的な操作権を取得します。操作中の外部クライアント名をGUIに表示し、手動入力をロックします。Take controlで操作権を取り戻せます。失効・取り消し後の古いクライアントは再取得できません。

While a client owns the GUI, a top **External control** banner shows `Python owns control` (or `Python · <label> owns control`) and a summary of the commanded per-channel state, such as `Open 2 · Close 1`, marked `Command in progress` while a task runs. Its only action is **Take control**, which revokes the client and holds the last requested state; nothing is sent to the Pico. It is disabled while a command task is in flight. After takeover, use the existing per-channel Close.

Shutter has no Stop. `capabilities()` keeps all existing fields; `safety` adds `supports_stop: false`, `lease_timeout_seconds` (10), and `on_release` / `on_disconnect` (`hold_last_state`, covering release, client loss and heartbeat expiry).

外部クライアントが操作権を持つ間、上部の「External control」に所有者と指令上の開閉状態を表示します。操作は「Take control」のみで、操作権を取り戻し最後の状態を保持します（Picoへは送信しません）。指令の処理中は押せません。閉じる場合は取り戻した後に既存のCH別Closeを使います。Stopはありません。`capabilities()`の既存項目は変えず、`safety`に`supports_stop: false`、`lease_timeout_seconds`、`on_release`・`on_disconnect`を追加しました。

Release, client loss, and heartbeat expiry **hold the last requested state**. They do not automatically send Open or Close. An already accepted finite job may finish; manual controls remain unavailable while its command task is in flight. This policy is reported by `capabilities()` and the acquisition response. Dropping a Python object does not leave a self-retaining heartbeat thread.

解放・切断時にシャッターを勝手に動かさず、最後に要求した状態を維持します。受付済みの処理は完了する場合があり、その間は手動操作を待機させます。

## Receipts and state / 受付結果と開閉状態

Connection, discovery, shutter, and display mutations return `{id,kind,status,result,error,error_code}` receipts immediately. `status` is `running`, `completed`, or `error`. `result(id)` inspects the exact job; Python `wait(id)` polls and raises `GuiShutterError` on an error receipt. The same request ID and payload return the same receipt, including while running. Conflicting payloads return `request_id_conflict` and never run. Old IDs cannot be reused after their receipts expire.

操作ごとに受付IDを返し、そのIDで完了を照会します。同じIDの再送は二重実行せず、異なる内容の使い回しは拒否します。

The GUI retains the last **64** receipts and remembers **4096** action IDs until restart. Remembered IDs are never discarded, so an old Toggle or Open cannot run again. Once 4096 IDs are used, every other mutation returns `capacity` (restart the GUI), but `close` and `close_all` stay available: such an ID is deduplicated only while its receipt is among the last 64, so a replay after that can at most repeat the close. Job completion means command acknowledgement, **not physical closure or completed motion**. `wait_for_state()` separately polls Open/Close after firmware-reported queued motion and settling finish. Following a new command, cached state is marked moving until a fresh device state arrives. Network loss never causes automatic retries of `TOGGLE`.

受付IDは4096件まで再起動まで記憶し、忘れないため古いToggle/Openは再実行されません。上限到達後は`close`/`close_all`以外が`capacity`になります（GUIを再起動）。`close`/`close_all`は上限後も受け付け、そのIDは直近64件の受付結果がある間だけ重複判定されます。それ以降に同じIDを再送すると閉操作が繰り返されることがあります。

ジョブ完了はコマンド受付であり、移動完了とは区別します。`wait_for_state()` はPico側の移動・整定情報を確認します。新しい指令後は古い表示を完了扱いせず、最新の応答を待ちます。

Through the common protocol, `control.status` returns `phase` (`ready`, `busy`, `reconnecting` or `disconnected`), `busy`, `ownership` (`owned`, `owner`), `cleanup` (`not_required`, the hold-last-state policy) and the native snapshot under `native`. The native snapshot fields are also kept at the top level for existing common clients. The native `status` method is unchanged.

共通プロトコルの`control.status`は`phase`・`busy`・`ownership`・`cleanup`と、`native`以下のネイティブ状態を返します。既存の共通クライアントのため、ネイティブの項目は最上位にも残します。ネイティブの`status`は変わりません。

Each `status().channels` entry contains `state`, `position`, `target`, `close_angle`, `open_angle`, `busy`, and boolean `fault`. Open/Close use the Pico's own per-channel calibration; busy/queued/settling is Moving. Older firmware without `STATE` is Unknown. All states are software-commanded/output states, not sensor confirmation. `status` also includes connection, demo mode, layout, order, the numeric `display_order` array, owner, command-task busy flag, endpoint and discovered devices.

Open/Close判定は各チャンネルの校正値を使います。移動待ち・駆動・整定中はMoving、校正情報のない旧ファームウェアはUnknownです。位置センサーによる確認ではありません。

`channels[CH].fault` reports the Pico channel fault independently of `state`; a faulted channel can still report `state: "Open"` or `"Close"` for script compatibility. Python `wait_for_state()` raises `GuiShutterError` with `code == "fault"` as soon as the target channel reports `fault: true`, even if `state` matches, without waiting for its timeout. Older GUIs without `fault` retain the previous waiting behavior; firmware without fault reporting yields `false`.

各CHの真偽値 `fault` はPicoの異常を示します。互換性のため `state` は異常中も従来のOpen/Close等の値を維持します。`wait_for_state()` は対象CHの `fault` が真なら、状態が一致していても待たずに `GuiShutterError`（`code == "fault"`）を送出します。`fault` のない旧GUIでは従来どおり待機し、異常報告のない旧ファームウェアでは `false` になります。

The transport admits at most four peers and sixteen queued GUI requests. Input is bounded to 64 KiB with a two-second absolute read/response deadline. Expired requests are discarded before dispatch. After a lost response, use the same request ID or `result(id)`; do not invent a new ID for a blind Toggle retry.

While the GUI is waiting for a refresh or a previous command, shutter actions (including `close_all`) are answered `busy` immediately and are never run later by the GUI. `busy` is returned before any receipt exists, so resending the same request ID cannot run an action twice. The Python `GuiShutter` therefore resends `open`/`close`/`toggle`/`open_all`/`close_all` with the same request ID on `busy` for at most two seconds, then raises `busy`. It does not retry any other error, and a busy `connect`/`discover` is returned at once. Other clients should do the same or handle `busy` themselves.

状態更新や前の指令の応答待ちの間、開閉操作（`close_all`を含む）は直ちに`busy`を返し、GUIが後から勝手に実行することはありません。`busy`は受付記録より前に返るため、同じrequest IDの再送で二重実行は起きません。Pythonの`GuiShutter`は開閉操作に限り、`busy`のとき同じIDで最大2秒間再送し、それでも`busy`なら例外を送出します。他のエラーは再送せず、`connect`/`discover`の`busy`はすぐ返します。

## Validation / 検証

```sh
cargo test --locked --all-targets
python scripts/verify_gui_api.py target/release/kohdalab-shutter-gui --output docs/validation/gui-api.json
```

The native script launches its own demo GUI in an isolated temporary API directory. It exercises real socket authentication, Python attachment, state queries, open/close, toggle deduplication, conflicting IDs, exclusive ownership, layout/order changes that preserve channel IDs and states, batch actions, discovery/reconnect, heartbeats and release. Linux CI runs it inside Xvfb. See [recorded simulation result](validation/gui-api.json). These checks do not establish physical Pico/Wi-Fi/servo validation.

検証スクリプトは専用のデモGUIを起動し、実機へ接続しません。実機動作の確認は別途必要です。

Display order changes are session preferences. `set_order` never renumbers channels or sends a hardware command. JSON `channels` remains keyed by the physical CH number; use `display_order` to reproduce the on-screen sequence.

表示順はセッション内の設定です。`set_order` はCH番号を変更せず、実機へ指令を送りません。画面順を再現するときは `display_order` を使用します。

## Shared Pico channels / 複数PCでの使用

Hardware `connect` requires an explicit nonempty `channels` array, e.g. `connect(host="192.168.1.42", channels=[0, 2])`. The GUI atomically acquires those channels on the Pico; another GUI can acquire disjoint channels. A busy/expired Pico lease fails the connection/action. `status().channels` and All actions are scoped to the acquired channels. Discovery results include shared `label` and channel availability; `status` includes `device_label` and `selected_channels`. The ten-second local API lease is separate from the fifteen-second Pico lease, which the GUI renews while connected. If a status poll times out or the link drops, the GUI keeps the Pico lease and retries until the lease would expire; meanwhile `status` reports `connected: false` with every channel `Unknown`, and actions fail with `disconnected` without sending anything. During recovery, a new `connect` request returns `busy`. A refused connection or `lease_lost` still disconnects immediately. Releasing Python control returns manual control to this GUI; `disconnect()` releases the Pico channels.

実機の`connect`には使用CHを明示します。PicoがCH単位で操作権を管理し、別GUIは空きCHを利用できます。状態表示・一括開閉も取得CHに限定します。状態取得が一時的に失敗した場合はPicoのlease期限まで確保を保ったまま再試行し、その間は`connected: false`・全CH`Unknown`とし、操作は何も送らず`disconnected`で失敗します。復旧待ちの間に新たに`connect`すると`busy`が返ります。接続拒否と`lease_lost`は従来どおり直ちに切断します。Python側の`release()`はGUI内の操作権を返し、`disconnect()`がPicoのCHを解放します。

Shared names appear as `status().device_label` and each `status().channels[CH].label`. These are confirmed Pico values and are unchanged. Each `status().channels[CH]` and each discovered `devices[].channels[]` entry also has `display_label`: the name the GUI shows, i.e. this PC's name for that Pico and CH, otherwise the shared `label`, otherwise `CHnn`. PC names are never written to the Pico.

共有名は`status().device_label`と各`status().channels[CH].label`で、Picoで確定した値です（従来どおり）。各`status().channels[CH]`と`devices[].channels[]`には`display_label`も加わります。GUIに表示する名前で、そのPicoとCHに対するこのPCの名前、なければ共有`label`、それもなければ`CHnn`です。PC側の名前はPicoへ書き込みません。

All API actions remain available for automation and are scoped to acquired CHs; the GUI omits All buttons. Local API opt-in auto-restores on restart with newly generated credentials. Descriptor files remain under `.kohdalab/shutter/run`, separate from `.kohdalab/shutter/config/config.json`.
