"""Self-contained Pico USB wizard; opening the app never opens a serial port."""

from pathlib import Path
import queue
import sys
import threading

from PySide6.QtCore import QTimer
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
)

VERSION = "1.0.0"
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


class Setup(QWidget):
    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.busy = False
        self.events = queue.Queue()
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
        self.refresh.clicked.connect(self.scan)
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
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        footer = QHBoxLayout()
        self.help = QPushButton("New Pico?")
        self.help.clicked.connect(self.new_pico)
        footer.addWidget(self.help)
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

    def scan(self):
        # Enumerating USB metadata is read-only; never auto-select one of many.
        previous = self.device.currentData()
        self.device.clear()
        self.device.addItem("Select Pico W…", None)
        ports = (
            [("Demo Pico W · USB001", "demo")]
            if self.demo
            else [
                (f"{port.device} · {port.serial_number or 'Pico W'}", port.device)
                for port in list_ports.comports()
                if port.vid == 0x2E8A
            ]
        )
        for label, port in ports:
            self.device.addItem(label, port)
        index = (
            self.device.findData(previous)
            if previous
            else (1 if len(ports) == 1 else 0)
        )
        self.device.setCurrentIndex(max(0, index))

    def mode_changed(self):
        initial = self.mode.currentData() == "initial"
        self.ssid.setEnabled(initial and not self.busy)
        self.password.setEnabled(initial and not self.busy)
        self.start.setText("Install on Pico" if initial else "Update Pico")

    def new_pico(self):
        QMessageBox.information(
            self,
            "New Pico W",
            "MicroPython must be installed once on a new Pico W.\n"
            "Hold BOOTSEL while connecting USB and copy the Pico W UF2 to RPI-RP2.\n"
            "https://micropython.org/download/RPI_PICO_W/\n\n"
            "Then Refresh and choose Initial setup. Do not erase an existing controller.",
        )

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.device, self.refresh, self.mode, self.start, self.help):
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
        if (
            QMessageBox.question(
                self,
                "Upload to Pico W",
                f"{self.device.currentText()}\n\nBack up, upload and restart this Pico?\n"
                "Check wiring/calibration before initial setup. Keep USB connected.",
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
            target=self.work, args=(port, mode, ssid, password), daemon=True
        ).start()

    def work(self, port, mode, ssid, password):
        destination = None
        try:
            if self.demo:
                self.events.put(("done", "Demo complete · no hardware accessed."))
                return
            pico = Pico(port)
            current = pico.read(PROGRAMS + PRESERVED)
            destination = backup(
                current, Path.home() / ".kohdalab" / "shutter" / "pico-backups"
            )
            files = plan(mode, current, ROOT / "server", ssid, password)
            self.events.put(
                ("progress", "Uploading and verifying… Keep USB connected.")
            )
            pico.install(files)
            self.events.put(
                (
                    "done",
                    f"Complete · DHCP enabled.\nHold a CH switch for 3 seconds, then Find Pico W.\nBackup: {destination}",
                )
            )
        except (
            Exception
        ):  # USB errors can include private source; show no raw traceback.
            self.events.put(
                (
                    "error",
                    "Upload failed. Check USB, MicroPython, mode and configuration.\n"
                    "Original files are kept unless replacement was interrupted.\n"
                    + (
                        f"Backup: {destination}"
                        if destination
                        else "No backup was completed; no upload started."
                    ),
                )
            )

    def receive(self):
        while not self.events.empty():
            state, message = self.events.get_nowait()
            self.status.setText(message)
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
        if window.device.currentData() != "demo":
            raise RuntimeError("Smoke test must be isolated")
        QTimer.singleShot(100, app.quit)
    elif "--screenshot" in sys.argv:
        path = sys.argv[sys.argv.index("--screenshot") + 1]

        def capture():
            window.grab().save(path)
            app.quit()

        QTimer.singleShot(400, capture)
    return app.exec()
