"""GUI/embedded-backend checks with no physical USB access."""

import os
from pathlib import Path
import sys
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest  # noqa: E402
from PySide6.QtGui import QCloseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
from scripts.pico_setup_gui import Setup  # noqa: E402
from scripts.pico_setup_entry import remote_child  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_launch_never_opens_usb_and_requires_explicit_selection(app):
    with (
        patch("scripts.pico_setup_gui.list_ports.comports", return_value=[]),
        patch("scripts.pico_setup_gui.Pico") as pico,
    ):
        window = Setup()
        window.begin()
        assert "Select a Pico" in window.status.text()
        pico.assert_not_called()
        assert not window.busy
        window.close()


def test_initial_mode_enables_wifi_and_update_does_not(app):
    window = Setup(demo=True)
    assert not window.password.isEnabled()
    window.mode.setCurrentIndex(1)
    assert window.password.isEnabled() and window.ssid.isEnabled()
    window.ssid.setText("Lab")
    window.password.setText("fixture only")
    with (
        patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.No
        ),
        patch("scripts.pico_setup_gui.threading.Thread") as thread,
    ):
        window.begin()
        thread.assert_not_called()
        assert not window.busy
    window.close()


def test_busy_blocks_close_and_repeated_upload_and_demo_never_accesses_hardware(app):
    window = Setup(demo=True)
    window.set_busy(True)
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    with patch("scripts.pico_setup_gui.Pico") as pico:
        window.begin()
        window.work("demo", "update", "", "")
        pico.assert_not_called()
    window.receive()
    assert not window.busy
    assert "no hardware" in window.status.text()
    window.close()


def test_private_backend_version_uses_result_file_without_usb(tmp_path, monkeypatch):
    path = tmp_path / "result.txt"
    monkeypatch.setattr(sys, "argv", list(sys.argv))
    monkeypatch.setattr(sys, "stdin", sys.stdin)
    assert remote_child([str(path), "version"]) == 0
    assert "mpremote" in path.read_text().lower()


def test_private_backend_preserves_failed_exit_and_separates_stderr(
    tmp_path, monkeypatch
):
    path = tmp_path / "result.txt"
    previous = sys.argv

    def fail():
        print("failed to access COM4", file=sys.stderr)
        return 1

    with patch("mpremote.main.main", side_effect=fail):
        assert remote_child([str(path), "version"]) == 1
    assert sys.argv is previous
    assert path.read_text() == ""
    assert "failed to access" in Path(str(path) + ".err").read_text()


def test_bootsel_visible_but_never_uploaded_and_reconnect_updates_list(app):
    from types import SimpleNamespace

    ports = []
    boot = ["RPI-RP2 · E:/"]
    with (
        patch("scripts.pico_setup_gui.list_ports.comports", side_effect=lambda: ports),
        patch("scripts.pico_setup_gui.bootsel_drives", side_effect=lambda: boot),
        patch("scripts.pico_setup_gui.Pico") as pico,
    ):
        window = Setup()
        assert "BOOTSEL" in window.device.currentText()
        assert "WITHOUT" in window.hint.text()
        assert not window.start.isEnabled()
        pico.assert_not_called()
        boot.clear()
        ports.append(SimpleNamespace(device="COM4", serial_number="ID-A", vid=0x2E8A))
        window.status.setText("Previous error must remain readable")
        window.scan(force=False)
        assert window.device.currentData() == "COM4"
        assert window.mode.currentData() == "update"
        assert window.start.isEnabled()
        assert window.status.text() == "Previous error must remain readable"
        window.set_busy(True)
        ports.clear()
        window.scan(force=True)
        assert window.device.currentData() == "COM4"
        window.set_busy(False)
        window.close()


def test_bootsel_detector_only_reads_valid_labelled_metadata(tmp_path):
    from scripts.pico_setup_gui import bootsel_drives
    from types import SimpleNamespace

    (tmp_path / "INFO_UF2.TXT").write_text("UF2 Bootloader v3.0\nBoard-ID: RPI-RP2\n")
    volume = SimpleNamespace(
        isReady=lambda: True, name=lambda: "RPI-RP2", rootPath=lambda: str(tmp_path)
    )
    with patch(
        "scripts.pico_setup_gui.QStorageInfo.mountedVolumes", return_value=[volume]
    ):
        assert bootsel_drives() == [f"RPI-RP2 · {tmp_path}"]
        (tmp_path / "INFO_UF2.TXT").write_text("unrelated drive")
        assert bootsel_drives() == []


def test_worker_exposes_safe_error_stage_without_starting_upload(app):
    from scripts.upload_pico import UsbFailure

    window = Setup(demo=True)
    window.demo = False
    with (
        patch("scripts.pico_setup_gui.Pico") as pico,
        patch("scripts.pico_setup_gui.backup") as save,
    ):
        pico.return_value.read.side_effect = UsbFailure(
            "USB_ACCESS", "Cannot open USB port"
        )
        window.work("COM4", "update", "", "")
        window.receive()
        assert "Read Pico / backup" in window.status.text()
        assert "USB_ACCESS" in window.status.text()
        save.assert_not_called()
        pico.return_value.install.assert_not_called()
    window.demo = True
    window.close()
