"""USB uploader regressions without opening serial ports or moving hardware."""

import ast
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from scripts.upload_pico import Pico, ROOT, backup, patch_settings, plan


def values(source):
    result = {}
    exec(source, result)  # noqa: S102 - fixed synthetic test settings only
    return result


def test_dhcp_patch_preserves_calibration_custom_fields_and_is_idempotent():
    old = b'USE_STATIC_IP = True\nCHANNELS = ({"close": 14, "open": 72},)\nCUSTOM = "keep"\nSERVO_MAX_ACTIVE = 1\n'
    defaults = (ROOT / "server/settings.py").read_text()
    updated = patch_settings(old, defaults)
    result = values(updated)
    assert result["USE_STATIC_IP"] is False
    assert result["CHANNELS"] == ({"close": 14, "open": 72},)
    assert result["SERVO_MAX_ACTIVE"] == 1
    assert result["CUSTOM"] == "keep"
    assert result["DISCOVERY_PORT"] == 12346
    assert patch_settings(updated, defaults) == updated


def test_update_keeps_wifi_labels_and_uploads_complete_current_program():
    current = {
        "settings.py": b"CHANNELS = ()\n",
        "wifi_config.py": b"private",
        "device_config.json": b"labels",
    }
    files = plan("update", current, ROOT / "server")
    assert "wifi_config.py" not in files and "device_config.json" not in files
    assert tuple(files)[-1] == "main.py"
    assert files["discovery.py"] == (ROOT / "server/discovery.py").read_bytes()
    assert files["sessions.py"] == (ROOT / "server/sessions.py").read_bytes()
    assert current["wifi_config.py"] == b"private"


def test_initial_wifi_quoting_and_existing_device_rejection():
    files = plan("initial", {}, ROOT / "server", 'Lab "A"', "a'\\b\nsecret")
    wifi = values(files["wifi_config.py"])
    assert wifi["SSID"] == 'Lab "A"'
    assert wifi["PASSWORD"] == "a'\\b\nsecret"
    assert values(files["settings.py"])["USE_STATIC_IP"] is False
    with pytest.raises(RuntimeError, match="already has files"):
        plan("initial", {"settings.py": b"old"}, ROOT / "server", "ssid", "password")
    with pytest.raises(RuntimeError, match="requires existing"):
        plan("update", {}, ROOT / "server")


def test_backup_is_unique_exact_and_preserves_binary_private_files(tmp_path):
    original = {"settings.py": b"old", "wifi_config.py": b"\x00\xffpassword"}
    first, second = backup(original, tmp_path), backup(original, tmp_path)
    assert first != second
    for name, data in original.items():
        assert (first / name).read_bytes() == data


class FakePico(Pico):
    def __init__(self, corrupt=False):
        super().__init__("test-port")
        self.calls = []
        self.staged = {}
        self.corrupt = corrupt

    def command(self, *arguments):
        self.calls.append(arguments)
        if arguments[:2] == ("fs", "cp"):
            self.staged[arguments[3][1:]] = Path(arguments[2]).read_bytes()
        return ""

    def read(self, names):
        return {} if self.corrupt else {name: self.staged[name] for name in names}

    def run(self, source):
        self.calls.append(("run-source", source))
        ast.parse(source)
        return ""


def test_stages_and_verifies_before_commit_with_main_last_and_reset_last():
    pico = FakePico()
    pico.install({"main.py": b"print(1)", "settings.py": b"USE_STATIC_IP=False"})
    assert all(call[3].endswith(".shutter-upload") for call in pico.calls[:2])
    commit = pico.calls[2][1]
    assert "['settings.py', 'main.py']" in commit
    assert commit.index("compile(") < commit.index("os.rename(")
    assert pico.calls[-1] == ("reset",)


def test_corrupt_transfer_never_commits_or_restarts():
    pico = FakePico(corrupt=True)
    with pytest.raises(RuntimeError, match="verification failed"):
        pico.install({"main.py": b"print(1)"})
    assert not any(call[0] in ("run-source", "reset") for call in pico.calls)


def test_remote_failure_never_prints_private_source():
    result = subprocess.CompletedProcess([], 1, "", "PASSWORD = private-secret")
    with (
        patch("scripts.upload_pico.subprocess.run", return_value=result),
        pytest.raises(RuntimeError) as error,
    ):
        Pico("COM4").command("run", "operation.py")
    assert "private-secret" not in str(error.value)


def test_read_distinguishes_absent_files_from_read_errors_and_checks_board():
    pico = Pico("test")
    with patch.object(
        pico,
        "run",
        return_value='{ "machine":"Raspberry Pi Pico W with RP2040"}\n{"name":"settings.py","data":"6162"}',
    ):
        assert pico.read(("settings.py",)) == {"settings.py": b"ab"}
    with (
        patch.object(pico, "run", return_value='{"machine":"other board","files":{}}'),
        pytest.raises(RuntimeError, match="Pico W"),
    ):
        pico.read(("settings.py",))
    with (
        patch.object(pico, "run", return_value="invalid"),
        pytest.raises(RuntimeError, match="no originals are committed"),
    ):
        pico.read(("settings.py",))


@pytest.mark.parametrize("existing", [True, False])
def test_remote_commit_rolls_back_rename_failure(tmp_path, monkeypatch, existing):
    import os

    pico = FakePico()
    pico.install({"settings.py": b"NEW = 1", "main.py": b"NEW = 2"})
    source = pico.calls[-2][1]
    monkeypatch.chdir(tmp_path)
    for name in ("settings.py", "main.py"):
        if existing:
            Path(name).write_bytes(b"OLD = 1")
        Path(name + ".shutter-upload").write_bytes(b"NEW = 1")
    replace = os.replace

    def rename(source, destination):
        if source == "main.py.shutter-upload":
            raise OSError("simulated commit failure")
        replace(source, destination)

    monkeypatch.setattr(os, "rename", rename)
    with pytest.raises(OSError, match="simulated"):
        exec(source, {})  # noqa: S102 - execute generated installer against tmp files, no hardware
    for name in ("settings.py", "main.py"):
        if existing:
            assert Path(name).read_bytes() == b"OLD = 1"
        else:
            assert not Path(name).exists()


def test_remote_compile_failure_preserves_originals(tmp_path, monkeypatch):
    pico = FakePico()
    pico.install({"settings.py": b"NEW = 1", "main.py": b"NEW = 2"})
    source = pico.calls[-2][1]
    monkeypatch.chdir(tmp_path)
    Path("settings.py").write_bytes(b"OLD = 1")
    Path("settings.py.shutter-upload").write_bytes(b"NEW = 1")
    Path("main.py.shutter-upload").write_bytes(b"invalid python !")
    with pytest.raises(SyntaxError):
        exec(source, {})  # noqa: S102 - fixed generated code, temporary filesystem only
    assert Path("settings.py").read_bytes() == b"OLD = 1"
    assert not Path("main.py").exists()


def test_conditional_and_imported_settings_are_not_overwritten():
    old = b'if True:\n    CHANNELS = ({"close": 12},)\nfrom custom import I2C_SDA_PIN\n'
    defaults = (ROOT / "server/settings.py").read_text()
    updated = patch_settings(old, defaults).decode()
    assert "I2C_SDA_PIN = " not in updated
    assert updated.count("CHANNELS =") == 1
    with pytest.raises(RuntimeError, match="no CHANNELS"):
        patch_settings(b"CUSTOM = 1", defaults)


def test_multiple_usb_devices_require_explicit_selection(monkeypatch):
    from types import SimpleNamespace
    from scripts.upload_pico import choose_port

    ports = [
        SimpleNamespace(
            device=f"COM{i}", vid=0x2E8A, description="Pico", serial_number=str(i)
        )
        for i in (4, 5)
    ]
    monkeypatch.setattr("serial.tools.list_ports.comports", lambda: ports)
    monkeypatch.setattr("builtins.input", lambda _: "2")
    assert choose_port(None) == "COM5"
    monkeypatch.setattr("builtins.input", lambda _: "")
    with pytest.raises(RuntimeError, match="Cancelled"):
        choose_port(None)
    monkeypatch.setattr("serial.tools.list_ports.comports", list)
    with pytest.raises(RuntimeError, match="No USB Pico"):
        choose_port(None)
