"""Exercise the real desktop API in isolated simulation; never attach hardware."""

import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bindings" / "python"))
from kohdalab_shutter import GuiShutter, GuiShutterError  # noqa: E402


def require(value, message):
    if not value:
        raise RuntimeError(message)


def verify(binary, output):
    with tempfile.TemporaryDirectory(prefix="kohdalab-shutter-api-") as directory:
        with (Path(directory) / "gui.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(  # noqa: S603 - explicit binary, fixed demo-only arguments
                [
                    str(binary.resolve()),
                    "--demo",
                    "--gui-api",
                    "--api-directory",
                    directory,
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 20
                endpoint = None
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError("Demo GUI exited before API startup")
                    candidates = list(Path(directory).glob("shutter-*.json"))
                    if candidates:
                        try:
                            GuiShutter(candidates[0]).capabilities()
                            endpoint = candidates[0]
                            break
                        except GuiShutterError:
                            pass
                    time.sleep(0.1)
                require(endpoint is not None, "Demo API did not become ready")
                client = GuiShutter(endpoint)
                require(client.capabilities()["protocol"] == 2, "Unexpected protocol")
                initial = client.status()
                require(
                    initial["demo"] and initial["connected"],
                    "Expected connected simulation",
                )
                require(
                    len(initial["channels"]) == 4, "Expected four simulated channels"
                )
                with client:
                    client.wait(client.close(0)["id"], timeout=5)
                    client.wait_for_state(0, "Close", timeout=5)
                    request_id = str(uuid.uuid4())
                    first = client.toggle(0, request_id=request_id)
                    client.wait(first["id"], timeout=5)
                    client.wait_for_state(0, "Open", timeout=5)
                    require(
                        client.toggle(0, request_id=request_id) == first,
                        "Duplicate receipt changed",
                    )
                    require(
                        client.status()["channels"]["0"]["state"] == "Open",
                        "Toggle ran twice",
                    )
                    try:
                        client.toggle(1, request_id=request_id)
                        raise RuntimeError("Conflicting request ID was accepted")
                    except GuiShutterError as error:
                        require(
                            error.code == "request_id_conflict", "Wrong conflict error"
                        )
                    other = GuiShutter(endpoint)
                    try:
                        other.acquire()
                        raise RuntimeError("Second controller acquired an active lease")
                    except GuiShutterError as error:
                        require(error.code == "busy", "Wrong ownership error")
                    for layout in ("vertical", "horizontal"):
                        client.wait(client.set_layout(layout)["id"], timeout=5)
                        require(
                            client.status()["layout"] == layout, "Layout did not switch"
                        )
                    client.wait(client.close_all()["id"], timeout=5)
                    require(
                        all(
                            ch["state"] == "Close"
                            for ch in client.status()["channels"].values()
                        ),
                        "Close all failed",
                    )
                    client.wait(client.open_all()["id"], timeout=5)
                    require(
                        all(
                            ch["state"] == "Open"
                            for ch in client.status()["channels"].values()
                        ),
                        "Open all failed",
                    )
                    client.wait(client.disconnect()["id"], timeout=5)
                    require(not client.status()["connected"], "Disconnect failed")
                    found = client.wait(client.find_devices()["id"], timeout=5)[
                        "result"
                    ]["devices"]
                    require(len(found) == 2, "Demo discovery missing devices")
                    client.wait(
                        client.connect(device_id=found[1]["id"])["id"], timeout=5
                    )
                    require(client.status()["connected"], "Reconnect failed")
                    declaration = json.loads(endpoint.read_text())
                    with socket.create_connection(
                        ("127.0.0.1", declaration["port"]), timeout=2
                    ) as connection:
                        connection.sendall(
                            b'{"token":"wrong","method":"open","channel":0}\n'
                        )
                        denied = json.loads(connection.makefile("rb").readline())
                    require(
                        denied["error_code"] == "authentication",
                        "Missing token accepted",
                    )
                    # At least one heartbeat runs against the actual GUI.
                    time.sleep(2.2)
                    require(
                        client.status()["owner"] is not None, "Ownership heartbeat lost"
                    )
                require(
                    client.status()["owner"] is None,
                    "Release did not return manual control",
                )
                summary = {
                    "result": "passed",
                    "mode": "simulation",
                    "protocol": 2,
                    "checks": [
                        "attach",
                        "calibrated-state",
                        "open-close",
                        "toggle-dedup",
                        "request-conflict",
                        "exclusive-control",
                        "layout-switch",
                        "open-close-all",
                        "discovery-reconnect",
                        "authentication",
                        "heartbeat-release",
                    ],
                    "hardware_connected": False,
                }
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps(summary, indent=2) + "\n", encoding="utf-8"
                )
                print(json.dumps(summary))
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path("docs/validation/gui-api.json")
    )
    args = parser.parse_args()
    verify(args.binary, args.output)
