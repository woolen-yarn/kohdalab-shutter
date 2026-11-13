"""USB uploader regressions without opening serial ports or moving hardware."""

import ast
import hashlib
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
        "main.py": (ROOT / "server/main.py").read_bytes(),
        "pca9685.py": (ROOT / "server/pca9685.py").read_bytes(),
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
    assert wifi["PASSWORD"] == "a'\\b\nsecret"  # noqa: S105 - synthetic quoting regression
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


@pytest.mark.parametrize(
    "board", ["Raspberry Pi Pico W with RP2040", "Raspberry Pi Pico 2 W with RP2350"]
)
def test_read_distinguishes_absent_files_from_read_errors_and_checks_board(board):
    pico = Pico("test")
    with patch.object(
        pico,
        "run",
        return_value='{ "machine":"'
        + board
        + '"}\n{"name":"settings.py","data":"61"}\n{"name":"settings.py","data":"62"}'
        + '\n{"name":"settings.py","sha256":"'
        + hashlib.sha256(b"ab").hexdigest()
        + '"}',
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


def test_read_rejects_corrupt_or_truncated_backup():
    pico = Pico("test")
    header = '{"machine":"Raspberry Pi Pico 2 W with RP2350"}'
    chunk = '{"name":"main.py","data":"6162"}'
    footer = '{"name":"main.py","sha256":"' + hashlib.sha256(b"abc").hexdigest() + '"}'
    for lines in ((header, chunk), (header, chunk, footer)):
        with (
            patch.object(pico, "run", return_value="\n".join(lines)),
            pytest.raises(RuntimeError, match="no originals are committed"),
        ):
            pico.read(("main.py",))


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


@pytest.mark.parametrize(
    "raw,code",
    [
        ("failed to access COM4 (it may be in use by another program)", "USB_ACCESS"),
        ("could not enter raw repl", "PICO_RESPONSE"),
        ("MemoryError: private-secret", "PICO_MEMORY"),
        ("ImportError: private-secret", "PICO_MODULE"),
        ("SyntaxError: private-secret", "PICO_SYNTAX"),
        ("OSError: 28 private-secret", "PICO_SPACE"),
        ("unknown private-secret", "USB_COMMAND"),
    ],
)
def test_usb_diagnostics_use_safe_codes_never_echo_source(raw, code):
    from scripts.upload_pico import usb_failure

    failure = usb_failure(raw)
    assert failure.code == code
    assert "private-secret" not in str(failure)


def test_commit_failure_does_not_restart_or_report_success():
    from scripts.upload_pico import UsbFailure

    pico = FakePico()
    with (
        patch.object(
            pico, "run", side_effect=UsbFailure("PICO_MEMORY", "Out of memory")
        ),
        pytest.raises(UsbFailure),
    ):
        pico.install({"main.py": b"print(1)"})
    assert not any(call[0] == "reset" for call in pico.calls)


def calibration_current(minimum=610, maximum=2310):
    return {
        "settings.py": (ROOT / "server/settings.py").read_bytes(),
        "main.py": (ROOT / "server/main.py").read_bytes(),
        "pca9685.py": (ROOT / "server/pca9685.py")
        .read_bytes()
        .replace(b"servo_min_us=500", f"servo_min_us={minimum}".encode())
        .replace(b"servo_max_us=2500", f"servo_max_us={maximum}".encode()),
        "wifi_config.py": b'SSID="private"\nPASSWORD="private"\n',
        "device_config.json": b'{"label":"keep"}',
    }


def test_update_leaves_custom_pwm_driver_out_of_upload_entirely():
    old = calibration_current()
    before = dict(old)
    files = plan("update", old, ROOT / "server")
    assert "pca9685.py" not in files
    assert b"servo_min_us=610" in old["pca9685.py"]
    assert b"servo_max_us=2310" in old["pca9685.py"]
    assert old == before
    assert "wifi_config.py" not in files and "device_config.json" not in files


def test_unknown_legacy_driver_or_custom_main_stops_before_upload():
    old = calibration_current()
    old["pca9685.py"] = old["pca9685.py"].replace(b"def disable(", b"def old_disable(")
    with pytest.raises(RuntimeError, match="CALIBRATION_REVIEW"):
        plan("update", old, ROOT / "server")
    old = calibration_current()
    old["main.py"] += b"\npwm.servo_min_us = 700\n"
    with pytest.raises(RuntimeError, match="CALIBRATION_REVIEW"):
        plan("update", old, ROOT / "server")
    old = calibration_current()
    old["main.py"] = b"pwm=PCA9685(i2c,servo_min_us=700)\n"
    with pytest.raises(RuntimeError, match="CALIBRATION_REVIEW"):
        plan("update", old, ROOT / "server")
    old = calibration_current()
    del old["pca9685.py"]
    with pytest.raises(RuntimeError, match="CALIBRATION_REVIEW"):
        plan("update", old, ROOT / "server")


def test_custom_driver_binding_or_address_is_not_guessed():
    for extra in (
        b"PCA9685 = wrapper\n",
        b"PCA9685_ADDRESS = 65\n",
        b"from unrelated import PCA9685\n",
    ):
        old = calibration_current()
        old["main.py"] = old["main.py"].replace(
            b"pwm = PCA9685(", extra + b"pwm = PCA9685("
        )
        with pytest.raises(RuntimeError, match="CALIBRATION_REVIEW"):
            plan("update", old, ROOT / "server")


def test_initial_setup_refuses_a_preexisting_calibrated_driver():
    old = {"pca9685.py": b"custom pulse calibration"}
    with pytest.raises(RuntimeError, match="already has files"):
        plan("initial", old, ROOT / "server", "ssid", "fixture")
    assert old["pca9685.py"] == b"custom pulse calibration"


def test_tuning_changes_only_chosen_fields_preserving_other_channels_and_config():
    from scripts.upload_pico import apply_channel_tuning, tuning_channels

    source = (ROOT / "server/settings.py").read_bytes()
    original, _ = tuning_channels(source)
    updated = apply_channel_tuning(source, {0: {"soft_open": True}, 1: {"close": 5}})
    channels, _ = tuning_channels(updated)
    assert channels[0] == {**original[0], "soft_open": True}
    assert channels[1] == {**original[1], "close": 5}
    assert channels[2:] == original[2:]
    assert updated.split(b"CHANNELS =")[0] == source.split(b"CHANNELS =")[0]
    assert (
        updated.split(b"# Drive every configured")[1]
        == source.split(b"# Drive every configured")[1]
    )
    assert apply_channel_tuning(source, {0: {"close": 0, "soft_open": False}}) == source


@pytest.mark.parametrize(
    "changes",
    [
        {0: {"open": 0}},
        {True: {"open": 40}},
        {99: {"close": 1}},
        {0: {"servo_min_us": 800}},
        {0: {"soft_open": 1}},
        {0: {"close": -1}},
    ],
)
def test_bad_channel_edits_fail_without_upload_or_calibration_change(changes):
    from scripts.upload_pico import apply_channel_tuning

    with pytest.raises(RuntimeError, match="CHANNEL_TUNING"):
        apply_channel_tuning((ROOT / "server/settings.py").read_bytes(), changes)


def test_plan_tuning_keeps_pwm_driver_and_current_settings_untouched():
    old = calibration_current()
    from scripts.upload_pico import tuning_channels

    before = dict(old)
    files = plan(
        "update",
        old,
        ROOT / "server",
        channel_changes={0: {"soft_open": True}, 1: {"close": 4}},
    )
    assert old == before and "pca9685.py" not in files
    channels, _ = tuning_channels(files["settings.py"])
    assert channels[0]["soft_open"] is True and channels[1]["close"] == 4


def test_settings_parser_does_not_execute_dynamic_channels():
    from scripts.upload_pico import tuning_channels

    with pytest.raises(RuntimeError, match="CHANNEL_TUNING"):
        tuning_channels(b"CHANNELS = run_arbitrary_code()")


def test_dynamic_post_definition_channel_changes_are_not_guessed():
    from scripts.upload_pico import tuning_channels

    source = (
        ROOT / "server/settings.py"
    ).read_bytes() + b'\nCHANNELS[1]["close"] = 10\n'
    with pytest.raises(RuntimeError, match="CHANNEL_TUNING"):
        tuning_channels(source)


def test_device_identity_must_still_match_before_committing_staged_files():
    pico = FakePico()
    pico.device_id = "first"
    read = pico.read

    def switched(names):
        pico.device_id = "second"
        return read(names)

    with (
        patch.object(pico, "read", side_effect=switched),
        pytest.raises(RuntimeError, match="DEVICE_CHANGED"),
    ):
        pico.install({"main.py": b"print(1)"})
    assert not any(call[0] in ("reset", "run-source") for call in pico.calls)
