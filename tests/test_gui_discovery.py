"""GuiShutter default endpoint discovery with an isolated home directory.

Uses loopback fake GUI listeners only; no GUI, Pico W or hardware is needed.
"""

import json
import os
import socket
import threading
import uuid
from pathlib import Path

import pytest

from bindings.python import kohdalab_shutter as binding


class FakeGui:
    """Minimal loopback GUI answering ``capabilities`` for one token."""

    def __init__(self):
        self.token = str(uuid.uuid4())
        self.instance_id = str(uuid.uuid4())
        self._listener = socket.create_server(("127.0.0.1", 0))
        self._listener.settimeout(0.1)
        self.port = self._listener.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        while not self._stop.is_set():
            try:
                connection, _ = self._listener.accept()
            except (TimeoutError, socket.timeout):
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(1.0)
                data = b""
                while b"\n" not in data:
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                request = json.loads(data.split(b"\n", 1)[0])
                ok = request.get("token") == self.token
                reply = (
                    {"ok": True, "result": {"protocol": 2}}
                    if ok
                    else {"ok": False, "error": "bad token", "error_code": "auth"}
                )
                connection.sendall((json.dumps(reply) + "\n").encode())

    def descriptor(self):
        return {
            "protocol": 2,
            "app": "kohdalab-shutter",
            "host": "127.0.0.1",
            "port": self.port,
            "address": f"127.0.0.1:{self.port}",
            "token": self.token,
            "instance_id": self.instance_id,
            "pid": os.getpid(),
        }

    def write(self, directory: Path, name: str | None = None) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (name or f"shutter-{os.getpid()}-{self.instance_id}.json")
        path.write_text(json.dumps(self.descriptor()), encoding="utf-8")
        return path

    def close(self):
        self._stop.set()
        self._listener.close()
        self._thread.join(timeout=2)


@pytest.fixture
def home(tmp_path, monkeypatch):
    isolated = tmp_path / "home"
    isolated.mkdir()
    monkeypatch.setenv("HOME", str(isolated))
    monkeypatch.setenv("USERPROFILE", str(isolated))
    return isolated


@pytest.fixture
def guis():
    started = []

    def start():
        gui = FakeGui()
        started.append(gui)
        return gui

    yield start
    for gui in started:
        gui.close()


def current(home):
    return home / ".kohdalab" / "shutter" / "run"


def legacy(home):
    return home / ".kohdalab" / "control"


def stale_descriptor(directory: Path) -> Path:
    """A well-formed descriptor whose GUI has exited (port closed)."""
    with socket.create_server(("127.0.0.1", 0)) as closed:
        port = closed.getsockname()[1]
    directory.mkdir(parents=True, exist_ok=True)
    instance = str(uuid.uuid4())
    path = directory / f"shutter-1-{instance}.json"
    path.write_text(
        json.dumps(
            {
                "protocol": 2,
                "app": "kohdalab-shutter",
                "host": "127.0.0.1",
                "port": port,
                "token": str(uuid.uuid4()),
                "instance_id": instance,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_default_directories_prefer_gui_run_then_legacy_control(home):
    assert binding.GuiShutter.default_directories() == [current(home), legacy(home)]


def test_finds_descriptor_written_by_current_gui(home, guis):
    path = guis().write(current(home))
    assert binding.GuiShutter.discover(timeout=0.5) == path
    # The no-argument client attaches through the same default discovery.
    assert binding.GuiShutter(timeout=0.5).capabilities() == {"protocol": 2}


def test_still_finds_legacy_control_descriptor(home, guis):
    path = guis().write(legacy(home))
    assert binding.GuiShutter.discover(timeout=0.5) == path


def test_missing_directories_report_searched_paths(home):
    with pytest.raises(binding.GuiShutterError) as error:
        binding.GuiShutter.discover(timeout=0.2)
    assert error.value.code == "transport"
    assert str(current(home)) in str(error.value)
    assert str(legacy(home)) in str(error.value)


def test_stale_and_invalid_descriptors_are_skipped_not_deleted(home, guis):
    stale = stale_descriptor(current(home))
    broken = current(home) / "shutter-2-broken.json"
    broken.write_text("{not json", encoding="utf-8")
    wrong_app = legacy(home) / "shutter-3-other.json"
    legacy(home).mkdir(parents=True)
    wrong_app.write_text(json.dumps({"protocol": 2, "app": "x"}), encoding="utf-8")
    active = guis().write(legacy(home))

    assert binding.GuiShutter.discover(timeout=0.5) == active
    assert stale.exists() and broken.exists() and wrong_app.exists()


def test_only_stale_descriptors_mean_no_active_gui(home):
    stale_descriptor(current(home))
    stale_descriptor(legacy(home))
    with pytest.raises(binding.GuiShutterError) as error:
        binding.GuiShutter.discover(timeout=0.2)
    assert error.value.code == "transport"


def test_same_gui_in_both_directories_is_deduplicated(home, guis):
    gui = guis()
    preferred = gui.write(current(home))
    gui.write(legacy(home))
    assert binding.GuiShutter.discover(timeout=0.5) == preferred


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_symlinked_legacy_directory_is_deduplicated(home, guis):
    path = guis().write(current(home))
    legacy(home).parent.mkdir(parents=True, exist_ok=True)
    try:
        legacy(home).symlink_to(current(home), target_is_directory=True)
    except OSError:
        pytest.skip("cannot create directory symlink")
    assert binding.GuiShutter.discover(timeout=0.5) == path


def test_distinct_guis_across_directories_are_ambiguous(home, guis):
    first = guis().write(current(home))
    second = guis().write(legacy(home))
    with pytest.raises(binding.GuiShutterError) as error:
        binding.GuiShutter.discover(timeout=0.5)
    assert error.value.code == "multiple_endpoints"
    assert str(first) in str(error.value) and str(second) in str(error.value)


def test_explicit_directory_is_exact(home, guis, tmp_path):
    guis().write(current(home))
    guis().write(legacy(home))
    explicit = guis().write(tmp_path / "explicit")
    assert binding.GuiShutter.discover(tmp_path / "explicit", timeout=0.5) == explicit
    with pytest.raises(binding.GuiShutterError) as error:
        binding.GuiShutter.discover(tmp_path / "empty", timeout=0.2)
    assert error.value.code == "transport"


def test_explicit_endpoint_bypasses_ambiguous_defaults(home, guis):
    guis().write(current(home))
    chosen = guis().write(legacy(home))
    shutter = binding.GuiShutter(chosen, timeout=0.5)
    assert shutter.capabilities() == {"protocol": 2}


class _OsWithName:
    """``os`` as seen by the binding, with only ``os.name`` overridden.

    Patching the real ``os.name`` would also flip pathlib's flavour selection
    (``Path()`` would build ``WindowsPath`` on POSIX or vice versa), so the
    binding gets this view instead and the host's ``os`` stays untouched.
    """

    def __init__(self, name: str):
        self.name = name

    def __getattr__(self, attr):
        return getattr(os, attr)


def test_home_resolution_matches_gui(monkeypatch, tmp_path):
    monkeypatch.setattr(binding, "os", _OsWithName("posix"))
    monkeypatch.setenv("HOME", str(tmp_path / "h"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "p"))
    assert binding.GuiShutter._home() == tmp_path / "h"
    monkeypatch.setenv("HOME", "")
    assert binding.GuiShutter._home() == tmp_path / "p"
    monkeypatch.setattr(binding, "os", _OsWithName("nt"))
    monkeypatch.setenv("HOME", str(tmp_path / "h"))
    assert binding.GuiShutter._home() == tmp_path / "p"
