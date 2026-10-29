# GUI control API / GUI外部制御API

The optional Python/Jupyter client attaches to the running Rust GUI. The GUI owns the Pico connection; Python does not create a second hardware controller. No Python runtime dependency is required by this client.

任意のPython/Jupyterクライアントから起動中のRust GUIへ接続します。Pico接続はGUIが所有し、Pythonが別のハードウェア接続を作ることはありません。クライアントに追加の実行時ライブラリは不要です。

## Setup / 準備

Install the client in your Python environment / 使用するPython環境へインストールします:

```sh
python -m pip install ./bindings/python
```

Start the GUI with `--gui-api`, or enable **Local control API** in the left panel. For hardware-free exploration / 実機なしで確認する場合:

```sh
cargo run --release --locked --bin kohdalab-shutter-gui -- --demo --gui-api
```

```python
from kohdalab_shutter import GuiShutter

with GuiShutter() as shutter:
    # In demo mode the GUI already has a simulated connection.
    job = shutter.open(0)
    shutter.wait(job["id"], timeout=5)
    shutter.wait_for_state(0, "Open", timeout=5)
    print(shutter.status()["channels"]["0"]["state"])
    shutter.wait(shutter.set_layout("vertical")["id"], timeout=5)
    shutter.wait(shutter.set_order("descending")["id"], timeout=5)
    shutter.wait(shutter.close(0)["id"], timeout=5)
```

For real hardware, connect in the GUI first, or await `connect(host="...")` before another operation. `find_devices()` returns a discovery job; its completed `result.devices` lists IDs and addresses for `connect(device_id=...)`.

実機では先にGUIで接続するか、`connect(host="...")` が返すジョブの完了を待ってから次の操作を行います。`find_devices()` は検索ジョブを返し、完了後の `result.devices` にIDとアドレスが入ります。IDは `connect(device_id=...)` に渡せます。

## Ownership and results / 操作権と結果

`GuiShutter()` discovers exactly one active GUI endpoint. If multiple GUIs are running, pass `endpoint="/path/to/shutter-…json"`; it never chooses one silently. Read-only `capabilities()`, `status()`, `config()` and `result(id)` do not acquire control. Mutating calls acquire a ten-second lease and heartbeat every two seconds. Manual controls are locked until release or operator takeover.

複数のGUIが起動している場合は `endpoint=` で指定します。参照操作は操作権を取得しません。変更操作は10秒の操作権を取得し、2秒ごとに更新します。操作権の解放またはGUIのTake controlまで手動操作をロックします。

Each mutation accepts a UUID `request_id`. Retrying the identical request with the same ID returns its existing receipt; a conflicting payload is rejected. `toggle()` is never automatically retried. `result(id)` inspects a receipt and `wait(id)` waits for its terminal state. `wait()` raises `GuiShutterError` for an error receipt; `result()` retains the receipt for inspection. An error does not mean the shutter stayed still.

同じ `request_id` と内容を再送すると既存の受付結果を返し、二重実行しません。`toggle()` は自動再送しません。`result(id)` で照会し、`wait(id)` で完了を待ち、エラー時は `GuiShutterError` を返します。エラーでも、すでに受け付けた動作がないとは限りません。

Job completion means command acknowledgement. `wait_for_state(channel, "Open" | "Close", timeout=...)` separately polls the calibrated firmware state, including queued motion and settling; Unknown or disconnection is an error. These remain commanded states, not position-sensor proof. Updated Pico firmware with `STATE` is required for Open/Close inference; older firmware displays Unknown.

ジョブ完了はコマンド受付です。`wait_for_state()` は校正値・移動待ち・整定を含むPicoの状態を別途確認します。Unknownや切断はエラーです。どちらも位置センサーによる物理的な開閉確認ではありません。Open/Close判定には `STATE` 対応のPicoファームウェアが必要です。

`close(channel)` closes a shutter. `close()` without a channel, context exit, and `release()` release API ownership; they do not send Close to hardware. Accepted finite jobs may finish after release or heartbeat expiry; the last requested shutter state is retained. Take control revokes the old client, which must create a new instance to reacquire.

`close(channel)` はシャッターを閉じます。引数なしの `close()`、with終了、`release()` は操作権の解放であり、実機へCloseを送りません。受付済みの処理は解放・接続失効後も完了する場合があり、最後に要求した状態を維持します。Take control後、古いクライアントは再取得できず、新しいインスタンスが必要です。

Wire protocol and validation / 通信仕様と検証: [GUI API reference](../../docs/gui-api.md).

`set_order("ascending" | "descending")` changes display order only. `status()["display_order"]` returns the sequence; channel IDs passed to `open`, `close`, and `toggle` always identify the same hardware.

`set_order()` は表示順だけを変えます。`open`・`close`・`toggle` のCH番号は常に同じ実機に対応します。
