"""Contract tests for the standalone GUI API client (no Pico hardware)."""

from __future__ import annotations

import gc
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
import uuid
import weakref
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "bindings" / "python"))
from kohdalab_shutter import GuiShutter, GuiShutterError  # noqa: E402


class FakeGui:
    def __init__(self, directory: Path, *, token: str = "secret") -> None:  # noqa: S107
        self.token, self.calls, self.stop = token, [], threading.Event()
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(0.1)
        self.port = self.listener.getsockname()[1]
        self.path = directory / f"shutter-1-{uuid.uuid4()}.json"
        self.path.write_text(
            json.dumps(
                {
                    "protocol": 2,
                    "app": "kohdalab-shutter",
                    "host": "127.0.0.1",
                    "port": self.port,
                    "token": token,
                    "instance_id": str(uuid.uuid4()),
                    "pid": 1,
                }
            )
        )
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while not self.stop.is_set():
            try:
                client, _ = self.listener.accept()
            except TimeoutError:
                continue
            with client:
                raw = b""
                while b"\n" not in raw:
                    raw += client.recv(4096)
                request = json.loads(raw.split(b"\n", 1)[0])
                self.calls.append(request)
                if request.get("token") != self.token:
                    response = {
                        "ok": False,
                        "error_code": "authentication",
                        "error": "bad token",
                    }
                elif request["method"] == "capabilities":
                    response = {"ok": True, "result": {"api": 2}, "data": {"api": 2}}
                elif request["method"] == "acquire":
                    response = {
                        "ok": True,
                        "result": {"lease": "lease-1"},
                        "data": {"lease": "lease-1"},
                    }
                elif request["method"] == "heartbeat":
                    response = {
                        "ok": True,
                        "result": {"owned": True},
                        "data": {"owned": True},
                    }
                elif request["method"] == "release":
                    response = {
                        "ok": True,
                        "result": {"owned": False},
                        "data": {"owned": False},
                    }
                elif request["method"] == "result":
                    status = (
                        "completed"
                        if sum(x.get("method") == "result" for x in self.calls) > 1
                        else "running"
                    )
                    response = {
                        "ok": True,
                        "result": {"id": request["id"], "status": status},
                        "data": {},
                    }
                elif request["method"] == "status":
                    response = {
                        "ok": False,
                        "error_code": "offline",
                        "error": "not connected",
                    }
                else:
                    result = {
                        "id": request["request_id"],
                        "kind": request["method"],
                        "status": "running",
                        "error": None,
                        "error_code": None,
                        "result": None,
                    }
                    response = {"ok": True, "result": result, "data": result}
                client.sendall((json.dumps(response) + "\n").encode())

    def close(self) -> None:
        self.stop.set()
        self.thread.join(timeout=1)
        self.listener.close()


class GuiClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.server = FakeGui(self.directory)

    def tearDown(self) -> None:
        self.server.close()
        self.temp.cleanup()

    def test_discover_auth_framing_and_mutation(self) -> None:
        endpoint = GuiShutter.discover(self.directory)
        client = GuiShutter(endpoint, timeout=1)
        receipt = client.open(3)
        self.assertEqual(receipt["kind"], "open")
        call = next(item for item in self.server.calls if item["method"] == "open")
        self.assertEqual(call["channel"], 3)
        self.assertEqual(call["lease"], "lease-1")
        uuid.UUID(call["request_id"])
        client.close()
        self.assertEqual(self.server.calls[-1]["method"], "release")

    def test_errors_wait_and_heartbeat(self) -> None:
        client = GuiShutter(self.server.path, timeout=1)
        with self.assertRaisesRegex(GuiShutterError, "not connected") as caught:
            client.status()
        self.assertEqual(caught.exception.code, "offline")
        client.acquire()
        time.sleep(2.05)
        self.assertIn("heartbeat", [call["method"] for call in self.server.calls])
        result = client.wait("job-1", timeout=1)
        self.assertEqual(result["status"], "completed")
        client.close()

    def test_multiple_active_endpoints_are_not_selected(self) -> None:
        other = FakeGui(self.directory, token="other")  # noqa: S106
        try:
            with self.assertRaises(GuiShutterError) as caught:
                GuiShutter.discover(self.directory)
            self.assertEqual(caught.exception.code, "multiple_endpoints")
        finally:
            other.close()

    def test_connect_keeps_the_discovered_port_unless_explicitly_overridden(
        self,
    ) -> None:
        client = GuiShutter(self.server.path, timeout=1)
        client.connect(device_id="abcd")
        request = next(
            call for call in self.server.calls if call["method"] == "connect"
        )
        self.assertNotIn("port", request)
        client.close()

    def test_discarded_client_does_not_keep_heartbeat_alive(self) -> None:
        client = GuiShutter(self.server.path, timeout=1)
        client.acquire()
        reference = weakref.ref(client)
        stop = client._heartbeat_stop
        worker = client._heartbeat_thread
        del client
        gc.collect()
        self.assertIsNone(reference())
        stop.set()
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())

    def test_authentication_envelope_is_reported(self) -> None:
        descriptor = json.loads(self.server.path.read_text())
        descriptor["token"] = "incorrect"  # noqa: S105
        wrong = self.directory / "wrong.json"
        wrong.write_text(json.dumps(descriptor))
        with self.assertRaises(GuiShutterError) as caught:
            GuiShutter(wrong, timeout=1).capabilities()
        self.assertEqual(caught.exception.code, "authentication")


if __name__ == "__main__":
    unittest.main()
