"""GUI/embedded-backend checks with no physical USB access."""

import os
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
