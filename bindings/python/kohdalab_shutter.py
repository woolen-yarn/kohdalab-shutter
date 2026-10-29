"""Small stdlib-only client for the GUI-owned KohdaLab shutter API."""

from __future__ import annotations

import json
import os
import socket
import threading
import time
import uuid
import weakref
from pathlib import Path
from typing import Any


class GuiShutterError(RuntimeError):
    """A GUI API error; ``code`` is stable enough for program handling."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class GuiShutter:
    """Attach to exactly one GUI started with ``--gui-api``.

    The GUI remains the only process that can talk to the Pico W.  Mutations
    acquire a renewable ten-second GUI lease; ``close()`` only releases it.
    """

    _MAX_RESPONSE = 64 * 1024
    _TERMINAL = {"completed", "error"}

    def __init__(
        self,
        endpoint: str | os.PathLike[str] | None = None,
        *,
        timeout: float = 3.0,
        client: str | None = None,
        label: str = "Python",
    ) -> None:
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or timeout <= 0
        ):
            raise ValueError("timeout must be positive")
        self._endpoint = Path(endpoint).expanduser() if endpoint is not None else None
        self.timeout = float(timeout)
        self.client = (
            self._uuid(client, "client") if client is not None else str(uuid.uuid4())
        )
        if not isinstance(label, str) or not label:
            raise ValueError("label must be a non-empty string")
        self.label = label
        self._descriptor: dict[str, Any] | None = None
        self._lease: str | None = None
        self._closed = False
        self._heartbeat_stop = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    @staticmethod
    def _uuid(value: str | None, name: str = "request_id") -> str:
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a UUID string")
        try:
            uuid.UUID(value)
        except ValueError as exc:
            raise ValueError(f"{name} must be a UUID string") from exc
        return value

    @staticmethod
    def _validate_descriptor(value: Any, path: Path) -> dict[str, Any]:
        if (
            not isinstance(value, dict)
            or value.get("protocol") != 2
            or value.get("app") != "kohdalab-shutter"
        ):
            raise ValueError(f"Invalid shutter GUI endpoint: {path}")
        if (
            value.get("host") != "127.0.0.1"
            or not isinstance(value.get("port"), int)
            or not 1 <= value["port"] <= 65535
        ):
            raise ValueError(f"Invalid shutter GUI endpoint: {path}")
        if not all(
            isinstance(value.get(key), str) and value[key]
            for key in ("token", "instance_id")
        ):
            raise ValueError(f"Invalid shutter GUI endpoint: {path}")
        return value

    @classmethod
    def _load(cls, path: Path) -> dict[str, Any]:
        try:
            return cls._validate_descriptor(
                json.loads(path.read_text(encoding="utf-8")), path
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise GuiShutterError(
                f"Cannot read GUI endpoint: {path}", "transport"
            ) from exc

    @classmethod
    def discover(
        cls, directory: str | os.PathLike[str] | None = None, *, timeout: float = 1.0
    ) -> Path:
        """Return the one active endpoint; never choose among multiple GUIs."""
        base = (
            Path(directory).expanduser()
            if directory is not None
            else Path.home() / ".kohdalab" / "control"
        )
        active: list[Path] = []
        for candidate in sorted(base.glob("shutter-*.json")) if base.is_dir() else []:
            try:
                probe = cls(candidate, timeout=timeout)
                probe.capabilities()
            except (GuiShutterError, ValueError):
                continue
            active.append(candidate)
        if not active:
            raise GuiShutterError(
                "No active KohdaLab Shutter GUI API was found", "transport"
            )
        if len(active) != 1:
            raise GuiShutterError(
                "Multiple active GUI APIs found; pass endpoint=", "multiple_endpoints"
            )
        return active[0]

    def _descriptor_for_request(self) -> dict[str, Any]:
        if self._descriptor is None:
            self._descriptor = (
                self._load(self._endpoint)
                if self._endpoint
                else self._load(self.discover(timeout=min(1.0, self.timeout)))
            )
        return self._descriptor

    def _request(self, method: str, **body: Any) -> Any:
        if self._closed:
            raise GuiShutterError("GuiShutter is closed", "closed")
        descriptor = self._descriptor_for_request()
        wire = {"token": descriptor["token"], "method": method, **body}
        encoded = (json.dumps(wire, separators=(",", ":")) + "\n").encode()
        try:
            with socket.create_connection(
                (descriptor["host"], descriptor["port"]), self.timeout
            ) as connection:
                connection.settimeout(self.timeout)
                connection.sendall(encoded)
                response = bytearray()
                while b"\n" not in response:
                    chunk = connection.recv(4096)
                    if not chunk:
                        raise GuiShutterError(
                            "GUI API closed without a response", "transport"
                        )
                    response.extend(chunk)
                    if len(response) > self._MAX_RESPONSE:
                        raise GuiShutterError(
                            "GUI API response is too large", "protocol"
                        )
        except OSError as exc:
            raise GuiShutterError(
                "Could not reach the KohdaLab Shutter GUI", "transport"
            ) from exc
        try:
            decoded = json.loads(response.split(b"\n", 1)[0].decode())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GuiShutterError("Invalid GUI API response", "protocol") from exc
        if not isinstance(decoded, dict) or not isinstance(decoded.get("ok"), bool):
            raise GuiShutterError("Invalid GUI API envelope", "protocol")
        if not decoded["ok"]:
            raise GuiShutterError(
                str(decoded.get("error", "GUI rejected request")),
                decoded.get("error_code"),
            )
        if "result" not in decoded:
            raise GuiShutterError("GUI response omitted result", "protocol")
        return decoded["result"]

    def capabilities(self) -> Any:
        return self._request("capabilities")

    def status(self) -> Any:
        return self._request("status")

    def config(self) -> Any:
        return self._request("config")

    def result(self, id: str) -> Any:
        if not isinstance(id, str) or not id:
            raise ValueError("id must be non-empty")
        return self._request("result", id=id)

    def acquire(self, label: str | None = None) -> Any:
        result = self._request(
            "acquire", client=self.client, label=self.label if label is None else label
        )
        if not isinstance(result, dict) or not isinstance(result.get("lease"), str):
            raise GuiShutterError("Invalid lease response", "protocol")
        self._lease = result["lease"]
        self._start_heartbeat()
        return result

    def _start_heartbeat(self) -> None:
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()

        reference = weakref.ref(self)
        stopped = self._heartbeat_stop

        def heartbeat() -> None:
            while not stopped.wait(2.0):
                client = reference()
                if client is None:
                    return
                try:
                    if client._lease is None:
                        return
                    client._request(
                        "heartbeat", client=client.client, lease=client._lease
                    )
                except GuiShutterError:
                    client._lease = None
                    return
                finally:
                    del client

        self._heartbeat_thread = threading.Thread(
            target=heartbeat, name="shutter-gui-heartbeat", daemon=True
        )
        self._heartbeat_thread.start()

    def release(self) -> Any | None:
        self._heartbeat_stop.set()
        thread = self._heartbeat_thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.5)
        self._heartbeat_thread = None
        if self._lease is None:
            return None
        lease, self._lease = self._lease, None
        return self._request("release", client=self.client, lease=lease)

    def _mutation(
        self, method: str, *, request_id: str | None = None, **body: Any
    ) -> Any:
        if self._lease is None:
            self.acquire()
        if self._lease is None:
            raise GuiShutterError("GUI did not return a control lease", "protocol")
        body.update(
            client=self.client,
            lease=self._lease,
            request_id=str(uuid.uuid4())
            if request_id is None
            else self._uuid(request_id),
        )
        return self._request(method, **body)

    def connect(
        self,
        host: str | None = None,
        port: int | None = None,
        device_id: str | None = None,
        *,
        channels: list[int] | None = None,
        request_id: str | None = None,
    ) -> Any:
        parameters: dict[str, Any] = {"host": host, "device_id": device_id}
        if channels is not None:
            if (
                not channels
                or any(type(ch) is not int or not 0 <= ch < 16 for ch in channels)
                or len(set(channels)) != len(channels)
            ):
                raise ValueError("channels must be unique channel numbers in 0..15")
            parameters["channels"] = channels
        if port is not None:
            parameters["port"] = port
        return self._mutation("connect", request_id=request_id, **parameters)

    def find_devices(self, *, request_id: str | None = None) -> Any:
        """Ask the GUI to discover Pico W devices on the local network."""
        return self._mutation("discover", request_id=request_id)

    def disconnect(self, *, request_id: str | None = None) -> Any:
        return self._mutation("disconnect", request_id=request_id)

    def open(self, channel: int, *, request_id: str | None = None) -> Any:
        return self._mutation("open", channel=channel, request_id=request_id)

    def close(
        self, channel: int | None = None, *, request_id: str | None = None
    ) -> Any:
        return (
            self.release()
            if channel is None
            else self._mutation("close", channel=channel, request_id=request_id)
        )

    def toggle(self, channel: int, *, request_id: str | None = None) -> Any:
        return self._mutation("toggle", channel=channel, request_id=request_id)

    def open_all(self, *, request_id: str | None = None) -> Any:
        return self._mutation("open_all", request_id=request_id)

    def close_all(self, *, request_id: str | None = None) -> Any:
        return self._mutation("close_all", request_id=request_id)

    def set_layout(self, layout: str, *, request_id: str | None = None) -> Any:
        if layout not in {"horizontal", "vertical"}:
            raise ValueError("layout must be 'horizontal' or 'vertical'")
        return self._mutation("set_layout", layout=layout, request_id=request_id)

    def set_order(self, order: str, *, request_id: str | None = None) -> Any:
        """Change display ordering without renumbering hardware channels."""
        if order not in {"ascending", "descending"}:
            raise ValueError("order must be 'ascending' or 'descending'")
        return self._mutation("set_order", order=order, request_id=request_id)

    def wait(self, id: str, timeout: float | None = None) -> Any:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            receipt = self.result(id)
            if isinstance(receipt, dict) and receipt.get("status") in self._TERMINAL:
                if receipt["status"] == "error":
                    raise GuiShutterError(
                        str(receipt.get("error", "Shutter action failed")),
                        receipt.get("error_code"),
                    )
                return receipt
            if deadline is not None and time.monotonic() >= deadline:
                raise GuiShutterError("Timed out waiting for job", "timeout")
            time.sleep(0.05)

    def wait_for_state(
        self, channel: int, state: str, timeout: float | None = None
    ) -> Any:
        """Poll GUI state without issuing another shutter command.

        ``Open`` and ``Close`` are accepted only after the firmware reports a
        calibrated state.  ``Unknown`` and a dropped connection fail rather
        than implying a physical result from a command acknowledgement.
        """
        if not isinstance(channel, int) or isinstance(channel, bool) or channel < 0:
            raise ValueError("channel must be a non-negative integer")
        if state not in {"Open", "Close"}:
            raise ValueError("state must be 'Open' or 'Close'")
        if timeout is not None and (
            not isinstance(timeout, (int, float)) or timeout < 0
        ):
            raise ValueError("timeout must be non-negative or None")
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            snapshot = self.status()
            if not isinstance(snapshot, dict) or not snapshot.get("connected", False):
                raise GuiShutterError("Shutter is disconnected", "disconnected")
            channels = snapshot.get("channels")
            current = channels.get(str(channel)) if isinstance(channels, dict) else None
            observed = current.get("state") if isinstance(current, dict) else "Unknown"
            if observed == state:
                return snapshot
            if observed == "Unknown":
                raise GuiShutterError("Shutter state is unknown", "unknown_state")
            if deadline is not None and time.monotonic() >= deadline:
                raise GuiShutterError("Timed out waiting for shutter state", "timeout")
            time.sleep(0.05)

    def __enter__(self) -> "GuiShutter":
        self.acquire()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
