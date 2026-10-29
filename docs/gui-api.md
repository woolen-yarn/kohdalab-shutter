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

Protocol **2** uses one UTF-8 JSON request and response per TCP connection, each terminated by a newline. The listener binds only to `127.0.0.1` on an ephemeral port. An atomic private descriptor lives at `~/.kohdalab/control/shutter-<pid>-<instance>.json` (Windows: the user profile directory). It contains `app`, `protocol`, `pid`, `instance_id`, `host`, `port`, `address`, and an unpredictable instance `token`. Files are mode 0600 on Unix, and removed on normal API shutdown.

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

The first Python mutation, or entering `with GuiShutter()`, acquires one exclusive lease. The client heartbeats every two seconds and the GUI expires it after ten seconds without renewal. The header API indicator and the ··· menu identify the external controller; ordinary manual inputs are locked. **Take control** revokes that client after the current command task finishes. An expired/revoked client must create a new client UUID to acquire again. Voluntary release permits reuse.

変更操作は排他的な操作権を取得します。操作中の外部クライアント名をGUIに表示し、手動入力をロックします。Take controlで操作権を取り戻せます。失効・取り消し後の古いクライアントは再取得できません。

Release, client loss, and heartbeat expiry **hold the last requested state**. They do not automatically send Open or Close. An already accepted finite job may finish; manual controls remain unavailable while its command task is in flight. This policy is reported by `capabilities()` and the acquisition response. Dropping a Python object does not leave a self-retaining heartbeat thread.

解放・切断時にシャッターを勝手に動かさず、最後に要求した状態を維持します。受付済みの処理は完了する場合があり、その間は手動操作を待機させます。

## Receipts and state / 受付結果と開閉状態

Connection, discovery, shutter, and display mutations return `{id,kind,status,result,error,error_code}` receipts immediately. `status` is `running`, `completed`, or `error`. `result(id)` inspects the exact job; Python `wait(id)` polls and raises `GuiShutterError` on an error receipt. The same request ID and payload return the same receipt, including while running. Conflicting payloads return `request_id_conflict` and never run. Old IDs cannot be reused after their receipts expire.

操作ごとに受付IDを返し、そのIDで完了を照会します。同じIDの再送は二重実行せず、異なる内容の使い回しは拒否します。

The GUI retains the last **64** receipts and remembers **4096** action IDs until restart. Job completion means command acknowledgement, **not physical closure or completed motion**. `wait_for_state()` separately polls Open/Close after firmware-reported queued motion and settling finish. Following a new command, cached state is marked moving until a fresh device state arrives. Network loss never causes automatic retries of `TOGGLE`.

ジョブ完了はコマンド受付であり、移動完了とは区別します。`wait_for_state()` はPico側の移動・整定情報を確認します。新しい指令後は古い表示を完了扱いせず、最新の応答を待ちます。

Each `status().channels` entry contains `state`, `position`, `target`, `close_angle`, `open_angle`, and `busy`. Open/Close use the Pico's own per-channel calibration; busy/queued/settling is Moving. Older firmware without `STATE` is Unknown. All states are software-commanded/output states, not sensor confirmation. `status` also includes connection, demo mode, layout, order, the numeric `display_order` array, owner, command-task busy flag, endpoint and discovered devices.

Open/Close判定は各チャンネルの校正値を使います。移動待ち・駆動・整定中はMoving、校正情報のない旧ファームウェアはUnknownです。位置センサーによる確認ではありません。

The transport admits at most four peers and sixteen queued GUI requests. Input is bounded to 64 KiB with a two-second absolute read/response deadline. Expired requests are discarded before dispatch. After a lost response, use the same request ID or `result(id)`; do not invent a new ID for a blind Toggle retry.

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

Hardware `connect` requires an explicit nonempty `channels` array, e.g. `connect(host="192.168.1.42", channels=[0, 2])`. The GUI atomically acquires those channels on the Pico; another GUI can acquire disjoint channels. A busy/expired Pico lease fails the connection/action. `status().channels` and All actions are scoped to the acquired channels. Discovery results include shared `label` and channel availability; `status` includes `device_label` and `selected_channels`. The ten-second local API lease is separate from the fifteen-second Pico lease, which the GUI renews while connected. Releasing Python control returns manual control to this GUI; `disconnect()` releases the Pico channels.

実機の`connect`には使用CHを明示します。PicoがCH単位で操作権を管理し、別GUIは空きCHを利用できます。状態表示・一括開閉も取得CHに限定します。Python側の`release()`はGUI内の操作権を返し、`disconnect()`がPicoのCHを解放します。

Shared names appear as `status().device_label` and each `status().channels[CH].label`. These are confirmed Pico values. All API actions remain available for automation and are scoped to acquired CHs; the GUI omits All buttons. Local API opt-in auto-restores on restart with newly generated credentials. Descriptor files remain under `.kohdalab/control`, separate from `.kohdalab/shutter/config.json`.
