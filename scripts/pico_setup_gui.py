"""Self-contained Pico USB wizard; opening the app never opens a serial port."""

from pathlib import Path
import hashlib
import queue
import sys
import threading

from PySide6.QtCore import QStorageInfo, QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from serial.tools import list_ports

from scripts.upload_pico import (
    ROOT,
    PROGRAMS,
    PRESERVED,
    Pico,
    backup,
    plan,
    run_mpremote,
    tuning_channels,
)

VERSION = "1.2.2"
STYLE = """
QWidget { background: #121317; color: #EBECF1; font-size: 13px; }
QLineEdit, QComboBox { background: #1A1B20; border: 1px solid #383A43; border-radius: 6px; padding: 7px; }
QPushButton { background: #2D2E35; border: 1px solid #383A43; border-radius: 6px; padding: 7px 16px; }
QPushButton:disabled { color: #777A85; }
QPushButton#primary { background: #306BD6; }
QLabel#muted { color: #A0A3B0; }
QProgressBar { border: 1px solid #383A43; border-radius: 4px; text-align: center; }
QProgressBar::chunk { background: #305B9E; }
"""


def bootsel_drives():
    """Inspect only labelled BOOTSEL volumes; never write or reflash them."""
    found = []
    for volume in QStorageInfo.mountedVolumes():
        if not volume.isReady() or volume.name() not in ("RPI-RP2", "RP2350"):
            continue
        try:
            with (Path(volume.rootPath()) / "INFO_UF2.TXT").open(
                encoding="utf-8", errors="replace"
            ) as stream:
                info = stream.read(2048)
            if "UF2 Bootloader" in info and "Board-ID:" in info:
                found.append(f"{volume.name()} · {volume.rootPath()}")
        except OSError:
            continue
    return sorted(found)


class Setup(QWidget):
    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.busy = False
        self.events = queue.Queue()
        self.device_signature = None
        self.connection_hint = ""
        self.tuning_profile = None
        self.tuning_changes = {}
        self.editing_tuning = False
        self.setWindowTitle("KohdaLab Shutter · Pico Setup")
        self.setMinimumWidth(470)
        self.resize(520, 430)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        title = QHBoxLayout()
        label = QLabel("Pico Setup")
        label.setStyleSheet("font-size: 22px; font-weight: 600;")
        title.addWidget(label)
        title.addStretch()
        title.addWidget(QLabel("v" + VERSION))
        layout.addLayout(title)
        self.hint = QLabel("Connect Pico W by USB. Close Shutter and Thonny.")
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        form = QFormLayout()
        form.setSpacing(12)
        self.device = QComboBox()
        self.refresh = QPushButton("Refresh")
        self.refresh.clicked.connect(lambda: self.scan(force=True))
        self.device.currentIndexChanged.connect(self.mode_changed)
        row = QHBoxLayout()
        row.addWidget(self.device, 1)
        row.addWidget(self.refresh)
        form.addRow("Device", row)
        self.mode = QComboBox()
        self.mode.addItem("Update · keep settings", "update")
        self.mode.addItem("Initial setup · new Pico", "initial")
        self.mode.currentIndexChanged.connect(self.mode_changed)
        form.addRow("Mode", self.mode)
        self.ssid = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Wi-Fi name", self.ssid)
        form.addRow("Password", self.password)
        layout.addLayout(form)
        self.network = QLabel("IP address: Automatic (DHCP)")
        self.network.setObjectName("muted")
        layout.addWidget(self.network)
        self.status = QLabel("Ready")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        footer = QHBoxLayout()
        self.help = QPushButton("New Pico?")
        self.help.clicked.connect(self.new_pico)
        footer.addWidget(self.help)
        self.tuning = QPushButton("Channel tuning…")
        self.tuning.clicked.connect(self.load_tuning)
        footer.addWidget(self.tuning)
        footer.addStretch()
        self.start = QPushButton("Update Pico")
        self.start.setObjectName("primary")
        self.start.clicked.connect(self.begin)
        footer.addWidget(self.start)
        layout.addLayout(footer)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.receive)
        self.timer.start(100)
        self.scan()
        self.mode_changed()
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(lambda: self.scan(force=False))
        self.scan_timer.start(1500)

    def scan(self, force=True):
        if self.busy or self.editing_tuning:
            return
        # Metadata only. Neither BOOTSEL drives nor serial ports are written/opened.
        previous = self.device.currentData()
        try:
            ports = (
                [("Demo Pico W · USB001", "demo")]
                if self.demo
                else [
                    (f"{port.device} · {port.serial_number or 'Pico W'}", port.device)
                    for port in list_ports.comports()
                    if port.vid == 0x2E8A
                ]
            )
            boot = [] if self.demo else bootsel_drives()
        except OSError:
            self.hint.setText("USB scan failed. Reconnect USB and press Refresh.")
            return
        signature = (tuple(ports), tuple(boot))
        if not force and signature == self.device_signature:
            return
        self.device_signature = signature
        self.device.blockSignals(True)
        self.device.clear()
        self.device.addItem("Select Pico W…", None)
        for label, port in ports:
            self.device.addItem(label, port)
        for drive in boot:
            self.device.addItem(drive + " · BOOTSEL", None)
            self.device.model().item(self.device.count() - 1).setEnabled(False)
        selected = self.device.findData(previous) if previous else -1
        if selected < 0:
            selected = (
                1 if len(ports) == 1 else (len(ports) + 1 if boot and not ports else 0)
            )
        self.device.setCurrentIndex(selected)
        self.device.blockSignals(False)
        if boot:
            self.connection_hint = "BOOTSEL detected. For Update, unplug USB and reconnect WITHOUT holding BOOTSEL. The list refreshes automatically."
        elif not ports:
            self.connection_hint = "No USB Pico found. For Update, connect normally without BOOTSEL. Use a data cable and close Thonny."
        else:
            self.connection_hint = "USB device found. Choose Update for an existing shutter; keep BOOTSEL released."
        self.mode_changed()

    def mode_changed(self):
        initial = self.mode.currentData() == "initial"
        self.ssid.setEnabled(initial and not self.busy)
        self.password.setEnabled(initial and not self.busy)
        self.start.setText("Install on Pico" if initial else "Update Pico")
        self.start.setEnabled(not self.busy and bool(self.device.currentData()))
        self.hint.setText(self.connection_hint)
        self.tuning.setEnabled(
            not self.busy and not initial and bool(self.device.currentData())
        )

    def new_pico(self):
        QMessageBox.information(
            self,
            "New Pico W",
            "Existing shutter update: reconnect USB normally, WITHOUT BOOTSEL, then select Update. Do not reinstall MicroPython.\n\n"
            "Only a NEW Pico W needs MicroPython installed once.\n"
            "Hold BOOTSEL while connecting USB and copy the Pico W UF2 to RPI-RP2.\n"
            "https://micropython.org/download/RPI_PICO_W/\n\n"
            "Then Refresh and choose Initial setup. Do not erase an existing controller.",
        )

    def set_busy(self, busy):
        self.busy = busy
        for widget in (
            self.device,
            self.refresh,
            self.mode,
            self.start,
            self.help,
            self.tuning,
        ):
            widget.setEnabled(not busy)
        self.progress.setRange(0, 0 if busy else 1)
        self.mode_changed()

    def begin(self):
        port, mode = self.device.currentData(), self.mode.currentData()
        ssid, password = self.ssid.text(), self.password.text()
        if self.busy:
            return
        if not port or (mode == "initial" and (not ssid or not password)):
            self.status.setText(
                "Select a Pico and enter Wi-Fi details for initial setup."
            )
            return
        summary = ""
        tuning_context = None
        if self.tuning_changes and mode == "update":
            if not self.tuning_profile or self.tuning_profile["port"] != port:
                self.status.setText(
                    "CHANNEL_TUNING: Read settings from the selected Pico again."
                )
                return
            tuning_context = {
                **self.tuning_profile,
                "changes": {
                    ch: dict(patch) for ch, patch in self.tuning_changes.items()
                },
            }
            summary = (
                "\nChannel changes: "
                + "; ".join(
                    f"CH{ch:02}: "
                    + ", ".join(f"{key}={value}" for key, value in patch.items())
                    for ch, patch in self.tuning_changes.items()
                )
                + "\n"
            )
        if (
            QMessageBox.question(
                self,
                "Upload to Pico W",
                f"{self.device.currentText()}{summary}\n\nBack up, upload and restart this Pico?\n"
                "Restart initializes all channels at their Close positions.\nCheck wiring/calibration and keep USB connected.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.set_busy(True)
        self.status.setText("Reading Pico and saving backup…")
        self.password.clear()
        threading.Thread(
            target=self.work,
            args=(port, mode, ssid, password, tuning_context),
            daemon=True,
        ).start()

    def work(self, port, mode, ssid, password, tuning_context=None):
        destination = None
        pico = None
        stage = "Read Pico / backup"
        try:
            if self.demo:
                self.events.put(("done", "Demo complete · no hardware accessed."))
                return
            pico = Pico(port)
            current = pico.read(PROGRAMS + PRESERVED)
            stage = "Save backup on PC"
            destination = backup(
                current, Path.home() / ".kohdalab" / "shutter" / "pico-backups"
            )
            stage = "Prepare update / check existing settings"
            self.events.put(("progress", stage))
            changes = None
            if tuning_context:
                if (
                    pico.device_id != tuning_context["device_id"]
                    or hashlib.sha256(current["settings.py"]).hexdigest()
                    != tuning_context["settings_hash"]
                ):
                    raise RuntimeError(
                        "SETTINGS_CHANGED: Device or settings changed since reading. Read channel tuning again; nothing was uploaded."
                    )
                changes = tuning_context["changes"]
            files = plan(
                mode, current, ROOT / "server", ssid, password, channel_changes=changes
            )
            stage = "Upload / verify / commit"
            self.events.put(
                ("progress", "Uploading and verifying… Keep USB connected.")
            )
            pico.install(files)
            self.events.put(
                (
                    "done",
                    f"Complete · DHCP enabled.{(' PWM calibration preserved.' if mode == 'update' else '')}\nHold a CH switch for 3 seconds, then Find Pico W.\nBackup: {destination}",
                )
            )
        except RuntimeError as error:
            # Uploader RuntimeErrors contain fixed safe diagnostics, never device source.
            self.events.put(
                (
                    "error",
                    f"Failed step: {getattr(pico, 'phase', stage) if stage == 'Upload / verify / commit' else stage}\n{error}\n"
                    + (
                        f"Backup: {destination}"
                        if destination
                        else "No backup completed; no upload started."
                    ),
                )
            )
        except Exception:
            self.events.put(
                (
                    "error",
                    f"Failed step: {getattr(pico, 'phase', stage) if stage == 'Upload / verify / commit' else stage}\nLOCAL_ERROR: Could not read or save the required files. No raw device output is shown.\n"
                    + (
                        f"Backup: {destination}"
                        if destination
                        else "No backup completed; no upload started."
                    ),
                )
            )

    def load_tuning(self):
        port = self.device.currentData()
        if self.busy or not port or self.mode.currentData() != "update":
            return
        if (
            QMessageBox.question(
                self,
                "Read channel settings",
                "Reading settings stops the running Pico program and saves a backup.\nAny previously queued edits are replaced by this fresh read.\nNo settings are written until Update Pico is confirmed.\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.tuning_changes = {}
        self.tuning_profile = None
        self.set_busy(True)
        self.status.setText("Reading channel settings and saving backup…")
        threading.Thread(target=self.read_tuning, args=(port,), daemon=True).start()

    def read_tuning(self, port):
        try:
            if self.demo:
                settings = (ROOT / "server/settings.py").read_bytes()
                device_id, destination = "demo", "Demo · no USB access"
            else:
                pico = Pico(port)
                current = pico.read(PROGRAMS + PRESERVED)
                destination = backup(
                    current, Path.home() / ".kohdalab" / "shutter" / "pico-backups"
                )
                settings, device_id = current["settings.py"], pico.device_id
                if not device_id:
                    raise RuntimeError(
                        "CHANNEL_TUNING: Could not identify the Pico; no upload started."
                    )
            channels, _ = tuning_channels(settings)
            self.events.put(
                (
                    "tuning",
                    {
                        "port": port,
                        "device_id": device_id,
                        "settings_hash": hashlib.sha256(settings).hexdigest(),
                        "channels": channels,
                        "backup": str(destination),
                    },
                )
            )
        except RuntimeError as error:
            self.events.put(("error", f"Read channel settings failed: {error}"))
        except Exception:
            self.events.put(
                (
                    "error",
                    "CHANNEL_TUNING: Could not read channel settings or save backup. No upload started.",
                )
            )

    def edit_tuning(self, profile):
        from scripts.pico_tuning import ChannelTuning

        self.set_busy(False)
        if profile["port"] != self.device.currentData():
            self.status.setText(
                "CHANNEL_TUNING: Selected Pico changed. Read settings again."
            )
            return
        self.editing_tuning = True
        try:
            dialog = ChannelTuning(profile["channels"], self)
            if dialog.exec():
                self.tuning_profile = profile
                self.tuning_changes = dialog.changes
                self.status.setText(
                    f"{len(dialog.changes)} channel(s) queued. Confirm Update Pico to apply.\nBackup: {profile['backup']}"
                )
            else:
                self.status.setText(
                    "No channel settings written. Restart the Pico to resume its program, or use Update Pico."
                )
        finally:
            self.editing_tuning = False

    def receive(self):
        while not self.events.empty():
            state, message = self.events.get_nowait()
            if state == "tuning":
                self.edit_tuning(message)
                continue
            self.status.setText(message)
            if state == "done":
                self.tuning_changes = {}
                self.tuning_profile = None
            if state != "progress":
                self.set_busy(False)
                self.progress.setValue(1 if state == "done" else 0)

    def closeEvent(self, event):
        if self.busy:
            self.status.setText(
                "Upload in progress. Keep this window open and USB connected."
            )
            event.ignore()
        else:
            event.accept()


def run():
    demo = (
        "--demo" in sys.argv or "--smoke-test" in sys.argv or "--screenshot" in sys.argv
    )
    app = QApplication([sys.argv[0]])
    window = Setup(demo=demo)
    window.show()
    if "--smoke-test" in sys.argv:
        # No serial port is opened, even in packaged smoke tests.
        if not (ROOT / "server/main.py").is_file():
            raise RuntimeError("Bundled firmware missing")
        if "mpremote" not in run_mpremote(["version"]).lower():
            raise RuntimeError("Bundled USB backend failed")
        try:
            run_mpremote(["__pico_setup_invalid_command__"])
        except RuntimeError:
            pass
        else:
            raise RuntimeError("Backend failure was incorrectly reported as success")
        if window.device.currentData() != "demo":
            raise RuntimeError("Smoke test must be isolated")
        from scripts.pico_tuning import ChannelTuning

        channels, _ = tuning_channels((ROOT / "server/settings.py").read_bytes())
        tuning = ChannelTuning(channels, window)
        if tuning.table.rowCount() != len(channels):
            raise RuntimeError("Bundled channel tuning failed")
        tuning.reject()
        QTimer.singleShot(100, app.quit)
    elif "--screenshot" in sys.argv:
        path = sys.argv[sys.argv.index("--screenshot") + 1]

        def capture():
            window.grab().save(path)
            app.quit()

        QTimer.singleShot(400, capture)
    return app.exec()
