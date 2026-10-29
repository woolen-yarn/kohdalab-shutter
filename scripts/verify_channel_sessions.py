#!/usr/bin/env python3
"""Exercise the Rust CLI against Pico-compatible multi-user session handling.

This deliberately uses the production ``server.sessions.Sessions`` class, but
replaces GPIO and Wi-Fi with a bounded loopback TCP server.  It is intended for
release validation after building ``kohdalab-shutter``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.sessions import DeviceLabel, LEASE_MS, Sessions  # noqa: E402
from bindings.python.kohdalab_shutter import GuiShutter, GuiShutterError  # noqa: E402


class FakeServoBoard:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[int, ...]]] = []
        self.positions = {channel: 0 for channel in range(4)}

    def operate(self, action: str, channels: tuple[int, ...]) -> bool:
        self.calls.append((action, channels))
        for channel in channels:
            if action == "open":
                self.positions[channel] = 90
            elif action == "close":
                self.positions[channel] = 0
            else:
                self.positions[channel] = 0 if self.positions[channel] else 90
        return True

    def state_text(self) -> str:
        return ",".join(
            f"CH{channel}={position}/{position}/0/90/0"
            for channel, position in self.positions.items()
        )


class PicoMock:
    def __init__(self) -> None:
        self.servos = FakeServoBoard()
        self.directory = tempfile.TemporaryDirectory(prefix="shutter-pico-labels-")
        self.store = DeviceLabel(
            "Unlabelled shutter", str(Path(self.directory.name) / "device_config.json")
        )
        self._origin = time.monotonic()
        self.sessions = Sessions(
            [
                {"label": "Sample"},
                {"label": "Reference"},
                {"label": "Pump"},
                {"label": "Gate"},
            ],
            "a0ff",
            "Unlabelled shutter",
            self._ticks_ms,
            lambda now, then: now - then,
            self._save_label,
            config_store=self.store,
        )
        self.saved_labels: list[str] = []
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(8)
        self.listener.settimeout(0.1)
        self.address = self.listener.getsockname()
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)

    def _ticks_ms(self) -> int:
        return int((time.monotonic() - self._origin) * 1000)

    def _save_label(self, label: str) -> None:
        self.store.save(label)
        self.saved_labels.append(label)

    def __enter__(self) -> "PicoMock":
        self.thread.start()
        return self

    def __exit__(self, *_unused: object) -> None:
        self.stopped.set()
        self.thread.join(timeout=2)
        self.listener.close()
        self.directory.cleanup()

    def _serve(self) -> None:
        while not self.stopped.is_set():
            try:
                connection, _address = self.listener.accept()
            except TimeoutError:
                continue
            with connection:
                connection.settimeout(1)
                data = bytearray()
                while len(data) <= 4096:
                    chunk = connection.recv(1)
                    if not chunk or chunk == b"\n":
                        break
                    data += chunk
                response = self._handle(data.decode("utf-8"))
                connection.sendall(response.encode("utf-8") + b"\n")

    def _handle(self, line: str) -> str:
        if line.startswith("SESSION "):
            try:
                body = json.loads(line[8:])
            except json.JSONDecodeError:
                body = None
            result = self.sessions.request(body, self.servos.operate)
            return json.dumps(result, separators=(",", ":"))
        parts = line.upper().split()
        if len(parts) == 2 and parts[0] in {"OPEN", "CLOSE", "TOGGLE"}:
            try:
                channel = int(parts[1])
            except ValueError:
                return "ERR"
            if self.sessions.is_locked(channel):
                return "ERR"
            return "OK" if self.servos.operate(parts[0].lower(), (channel,)) else "ERR"
        if parts == ["STATUS"]:
            return "CH0=0,CH1=0,CH2=0,CH3=0"
        if parts == ["STATE"]:
            return self.servos.state_text()
        return "UNKNOWN"


def request(address: tuple[str, int], body: dict[str, object]) -> dict[str, object]:
    with socket.create_connection(address, timeout=2) as connection:
        connection.sendall(b"SESSION " + json.dumps(body).encode("utf-8") + b"\n")
        reply = connection.makefile("rb").readline()
    return json.loads(reply)


def raw(address: tuple[str, int], line: str) -> str:
    with socket.create_connection(address, timeout=2) as connection:
        connection.sendall(line.encode("ascii") + b"\n")
        return connection.makefile("rb").readline().decode("ascii").strip()


def run_cli(
    binary: Path, address: tuple[str, int], *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - explicit local release/debug binary
        [str(binary), "--host", address[0], "--port", str(address[1]), *arguments],
        check=False,
        text=True,
        capture_output=True,
        timeout=10,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def verify(binary: Path) -> None:
    if not binary.is_file():
        raise RuntimeError(f"Rust CLI was not found: {binary}")
    first = "1" * 32
    second = "2" * 32
    third = "3" * 32
    with PicoMock() as pico:
        address = pico.address
        info = run_cli(binary, address, "info")
        require(
            info.returncode == 0 and "Unlabelled shutter" in info.stdout,
            "CLI info failed",
        )
        label = run_cli(binary, address, "label", "Optics Bay A")
        require(label.returncode == 0, f"CLI label failed: {label.stderr}")
        require(
            DeviceLabel("Default", pico.store.path).value == "Optics Bay A",
            "CLI did not persist label to disk",
        )

        require(
            request(address, {"op": "claim", "token": first, "channels": [0, 1]})["ok"],
            "first claim failed",
        )
        require(
            request(address, {"op": "claim", "token": second, "channels": [2]})["ok"],
            "disjoint claim failed",
        )
        collision = request(
            address, {"op": "claim", "token": third, "channels": [1, 3]}
        )
        require(
            collision.get("error") == "busy", "overlapping atomic claim was accepted"
        )
        require(raw(address, "OPEN 0") == "ERR", "legacy command bypassed CH lock")
        require(
            request(
                address,
                {
                    "op": "set_config",
                    "token": first,
                    "channel_labels": {"0": "Probe beam"},
                },
            )["ok"],
            "first owner name save failed",
        )
        require(
            request(
                address,
                {
                    "op": "set_config",
                    "token": second,
                    "channel_labels": {"2": "Reference"},
                },
            )["ok"],
            "second owner name save failed",
        )
        require(
            not request(
                address,
                {
                    "op": "set_config",
                    "token": first,
                    "channel_labels": {"2": "Not owned"},
                },
            )["ok"],
            "unowned name was changed",
        )
        saved = DeviceLabel(
            "Default", str(Path(pico.directory.name) / "device_config.json")
        )
        require(
            saved.channel_labels == {"0": "Probe beam", "2": "Reference"},
            "disjoint names were not retained on disk",
        )

        require(request(address, {"op": "renew", "token": first})["ok"], "renew failed")
        require(
            request(
                address,
                {"op": "operate", "token": second, "action": "open", "channels": [2]},
            )["ok"],
            "owned operation failed",
        )
        require(
            pico.servos.calls == [("open", (2,))], "session moved an unexpected channel"
        )
        require(
            request(address, {"op": "release", "token": first})["ok"],
            "first release failed",
        )
        require(
            request(address, {"op": "release", "token": second})["ok"],
            "second release failed",
        )

        command = run_cli(binary, address, "open", "0")
        require(
            command.returncode == 0,
            f"CLI claim/operate/release failed: {command.stderr}",
        )
        require(
            pico.servos.calls[-1] == ("open", (0,)),
            "CLI did not issue owned channel action",
        )
        final = request(address, {"op": "info"})
        require(
            not any(channel["locked"] for channel in final["channels"]),
            "CLI left a lease behind",
        )
        require(final["lease_ms"] == LEASE_MS, "lease duration changed")
    print(
        "Verified Rust CLI ↔ Pico session protocol: labels, atomic CH leases, lock enforcement, renewal and release."
    )


def endpoint(directory: Path, process: subprocess.Popen[str]) -> GuiShutter:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"GUI exited during startup with {process.returncode}")
        candidates = list(directory.glob("shutter-*.json"))
        if candidates:
            try:
                client = GuiShutter(candidates[0])
                client.capabilities()
                return client
            except (GuiShutterError, ValueError):
                pass
        time.sleep(0.1)
    raise RuntimeError("GUI API endpoint did not become available")


def wait(client: GuiShutter, request: object) -> object:
    require(
        isinstance(request, dict) and isinstance(request.get("id"), str),
        "Missing GUI job",
    )
    return client.wait(request["id"], timeout=8)


def expect_gui_failure(client: GuiShutter, request: object) -> None:
    try:
        wait(client, request)
    except GuiShutterError:
        return
    raise RuntimeError("GUI accepted an overlapping channel claim")


def verify_gui(gui: Path) -> None:
    if not gui.is_file():
        raise RuntimeError(f"Rust GUI was not found: {gui}")
    processes: list[subprocess.Popen[str]] = []
    clients: list[GuiShutter] = []
    with (
        PicoMock() as pico,
        tempfile.TemporaryDirectory(prefix="shutter-gui-session-") as temp,
    ):
        root = Path(temp)
        try:
            for name in ("a", "b", "c"):
                directory = root / name
                directory.mkdir()
                process = subprocess.Popen(  # noqa: S603 - explicit built GUI, loopback-only API
                    [
                        str(gui),
                        "--gui-api",
                        "--api-directory",
                        str(directory),
                        "--preferences",
                        str(directory / "preferences.json"),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                processes.append(process)
                clients.append(endpoint(directory, process))
            first, second, third = clients
            address = pico.address
            wait(
                first, first.connect(host=address[0], port=address[1], channels=[0, 1])
            )
            wait(
                second,
                second.connect(host=address[0], port=address[1], channels=[2, 3]),
            )
            expect_gui_failure(
                third, third.connect(host=address[0], port=address[1], channels=[1, 2])
            )
            first_status = first.status()
            second_status = second.status()
            require(
                set(first_status["channels"]) == {"0", "1"},
                "GUI A showed unclaimed channels",
            )
            require(
                set(second_status["channels"]) == {"2", "3"},
                "GUI B showed unclaimed channels",
            )

            wait(first, first.open_all())
            require(
                pico.servos.positions == {0: 90, 1: 90, 2: 0, 3: 0},
                "GUI A open_all changed channels owned by GUI B",
            )
            wait(first, first.disconnect())
            first.release()
            wait(third, third.connect(host=address[0], port=address[1], channels=[0]))
            require(
                set(third.status()["channels"]) == {"0"},
                "GUI C did not acquire immediately released channel",
            )
            wait(second, second.disconnect())
            second.release()
            info = request(address, {"op": "info"})
            require(
                not any(
                    channel["locked"]
                    for channel in info["channels"]
                    if channel["id"] in (1, 2, 3)
                ),
                "GUI B disconnect did not release its channels",
            )
        finally:
            for client in clients:
                try:
                    client.release()
                except GuiShutterError:
                    pass
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
    print(
        "Verified three real GUIs: split CH leases, atomic conflict rejection, scoped controls and immediate disconnect release."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path, help="built kohdalab-shutter CLI")
    parser.add_argument(
        "--gui", type=Path, help="built kohdalab-shutter-gui for real-GUI checks"
    )
    args = parser.parse_args()
    verify(args.binary.resolve())
    if args.gui is not None:
        verify_gui(args.gui.resolve())


if __name__ == "__main__":
    main()
