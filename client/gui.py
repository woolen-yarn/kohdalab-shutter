import sys
import time

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .protocol import DEFAULT_HOST, DEFAULT_PORT
from .transport import ShutterClient

POLL_MS = 1000
CLOSE_ANGLE = 0
OPEN_ANGLE = 90


class TaskSignals(QObject):
    finished = Signal(str, object, object, object)


class ClientTask(QRunnable):
    def __init__(self, name, client, callback, context=None):
        super().__init__()
        self.name = name
        self.client = client
        self.callback = callback
        self.context = context
        self.signals = TaskSignals()

    @Slot()
    def run(self):
        try:
            result = self.callback(self.client)
            self.signals.finished.emit(self.name, result, None, self.context)
        except Exception as exc:
            self.signals.finished.emit(self.name, None, exc, self.context)


class ChannelCard(QFrame):
    def __init__(self, channel, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.setObjectName("channelCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        state_row = QHBoxLayout()
        state_row.setSpacing(10)

        self.title = QLabel(f"CH{channel}")
        self.title.setObjectName("channelTitle")
        self.title.setMinimumWidth(56)

        self.badge = QLabel("UNKNOWN")
        self.badge.setObjectName("badgeUnknown")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setMinimumWidth(88)

        self.angle = QLabel("- deg")
        self.angle.setObjectName("mutedText")
        self.angle.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.angle.setMinimumWidth(56)

        self.close_button = QPushButton("Close")
        self.open_button = QPushButton("Open")
        self.toggle_button = QPushButton("Toggle")
        for button in (self.close_button, self.open_button, self.toggle_button):
            button.setMinimumHeight(34)
            button.setCursor(Qt.PointingHandCursor)

        state_row.addWidget(self.title)
        state_row.addWidget(self.badge)
        state_row.addStretch(1)
        state_row.addWidget(self.angle)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addWidget(self.close_button)
        action_row.addWidget(self.open_button)
        action_row.addWidget(self.toggle_button)

        layout.addLayout(state_row)
        layout.addLayout(action_row)

    def set_angle(self, angle):
        self.angle.setText(f"{angle} deg" if angle is not None else "- deg")
        if angle == OPEN_ANGLE:
            self.badge.setText("OPEN")
            self.badge.setObjectName("badgeOpen")
        elif angle == CLOSE_ANGLE:
            self.badge.setText("CLOSE")
            self.badge.setObjectName("badgeClose")
        else:
            self.badge.setText("UNKNOWN")
            self.badge.setObjectName("badgeUnknown")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)

    def set_error(self):
        self.badge.setText("ERROR")
        self.badge.setObjectName("badgeError")
        self.badge.style().unpolish(self.badge)
        self.badge.style().polish(self.badge)

    def set_actions_enabled(self, enabled):
        self.close_button.setEnabled(enabled)
        self.open_button.setEnabled(enabled)
        self.toggle_button.setEnabled(enabled)


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kohda Lab Shutter")
        self.resize(560, 780)
        self.setMinimumSize(420, 600)

        self.client = None
        self.current_status = {}
        self.channel_cards = {}
        self.thread_pool = QThreadPool.globalInstance()
        self.connect_inflight = False
        self.refresh_inflight = False
        self.command_inflight = False

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(POLL_MS)
        self.poll_timer.timeout.connect(self.refresh_status)

        self._build_ui()
        self._apply_styles()
        self._set_connected(False)

    def _build_ui(self):
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Disconnected")

        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(lambda: self.refresh_status(force=True))
        toolbar.addAction(refresh_action)
        self.refresh_action = refresh_action

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)

        header_layout = QVBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Kohda Lab Shutter")
        title.setObjectName("appTitle")
        subtitle = QLabel("Pico W servo shutter controller")
        subtitle.setObjectName("mutedText")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header_layout.addLayout(title_block)
        self.last_update_label = QLabel("Last update: -")
        self.last_update_label.setObjectName("mutedText")
        header_layout.addWidget(self.last_update_label)
        root_layout.addLayout(header_layout)

        connection_panel = QFrame()
        connection_panel.setObjectName("panel")
        connection_layout = QGridLayout(connection_panel)
        connection_layout.setContentsMargins(14, 12, 14, 12)
        connection_layout.setHorizontalSpacing(10)
        connection_layout.setVerticalSpacing(8)

        connection_layout.addWidget(QLabel("IP"), 0, 0)
        self.host_input = QLineEdit(DEFAULT_HOST)
        self.host_input.setMinimumWidth(170)
        connection_layout.addWidget(self.host_input, 0, 1, 1, 3)

        connection_layout.addWidget(QLabel("Port"), 1, 0)
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(DEFAULT_PORT)
        self.port_input.setMinimumWidth(90)
        connection_layout.addWidget(self.port_input, 1, 1)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.clicked.connect(self.connect_to_server)
        connection_layout.addWidget(self.connect_button, 1, 2)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_from_server)
        connection_layout.addWidget(self.disconnect_button, 1, 3)

        self.connection_label = QLabel("Disconnected")
        self.connection_label.setObjectName("mutedText")
        self.connection_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        connection_layout.addWidget(self.connection_label, 2, 0, 1, 4)
        connection_layout.setColumnStretch(1, 1)
        root_layout.addWidget(connection_panel)

        summary_layout = QVBoxLayout()
        self.summary_label = QLabel("No channels")
        self.summary_label.setObjectName("summaryText")
        summary_layout.addWidget(self.summary_label)

        self.open_all_button = QPushButton("Open All")
        self.open_all_button.clicked.connect(lambda: self.run_command("open", self._known_channels()))
        self.close_all_button = QPushButton("Close All")
        self.close_all_button.clicked.connect(lambda: self.run_command("close", self._known_channels()))
        summary_buttons = QHBoxLayout()
        summary_buttons.addWidget(self.open_all_button)
        summary_buttons.addWidget(self.close_all_button)
        summary_layout.addLayout(summary_buttons)
        root_layout.addLayout(summary_layout)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("scrollArea")
        self.channel_container = QWidget()
        self.channel_layout = QVBoxLayout(self.channel_container)
        self.channel_layout.setContentsMargins(0, 0, 8, 0)
        self.channel_layout.setSpacing(10)
        self.channel_layout.addStretch(1)
        self.scroll.setWidget(self.channel_container)
        root_layout.addWidget(self.scroll, 1)

        self.empty_label = QLabel("Connect to the Pico W server to load channels.")
        self.empty_label.setObjectName("emptyText")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.channel_layout.insertWidget(0, self.empty_label)

    def _apply_styles(self):
        self.setStyleSheet(
            """
            QMainWindow {
                background: #0f172a;
            }
            QWidget#root {
                background: #0f172a;
                color: #e5e7eb;
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
                font-size: 10.5pt;
            }
            QWidget {
                color: #e5e7eb;
            }
            QLabel#appTitle {
                font-size: 18pt;
                font-weight: 700;
                color: #f8fafc;
            }
            QLabel#mutedText {
                color: #94a3b8;
            }
            QLabel#summaryText {
                color: #cbd5e1;
                font-weight: 600;
            }
            QLabel#emptyText {
                color: #64748b;
                font-size: 12pt;
                padding: 36px;
            }
            QFrame#panel, QFrame#channelCard {
                background: #111827;
                border: 1px solid #253044;
                border-radius: 8px;
            }
            QLabel#channelTitle {
                color: #f8fafc;
                font-size: 13pt;
                font-weight: 700;
            }
            QLabel#badgeOpen, QLabel#badgeClose, QLabel#badgeUnknown, QLabel#badgeError {
                color: white;
                border-radius: 5px;
                padding: 5px 8px;
                font-weight: 700;
            }
            QLabel#badgeOpen {
                background: #16a34a;
            }
            QLabel#badgeClose {
                background: #dc2626;
            }
            QLabel#badgeUnknown {
                background: #ca8a04;
            }
            QLabel#badgeError {
                background: #64748b;
            }
            QLineEdit, QSpinBox {
                background: #0b1120;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #e5e7eb;
                padding: 7px 9px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #3b82f6;
            }
            QPushButton {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #e5e7eb;
                padding: 7px 12px;
            }
            QPushButton:hover {
                background: #273449;
            }
            QPushButton:disabled {
                color: #64748b;
                background: #111827;
                border-color: #1f2937;
            }
            QPushButton#primaryButton {
                background: #3b82f6;
                border-color: #3b82f6;
                color: #ffffff;
                font-weight: 700;
            }
            QPushButton#primaryButton:hover {
                background: #2563eb;
            }
            QScrollArea#scrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #0f172a;
                width: 12px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                border-radius: 6px;
                min-height: 36px;
            }
            QScrollBar::handle:vertical:hover {
                background: #475569;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QToolBar {
                background: #111827;
                border-bottom: 1px solid #253044;
                spacing: 6px;
            }
            QToolBar QToolButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                color: #cbd5e1;
                padding: 6px 10px;
            }
            QToolBar QToolButton:hover {
                background: #1e293b;
                border-color: #334155;
            }
            QToolBar QToolButton:disabled {
                color: #475569;
            }
            QStatusBar {
                background: #111827;
                color: #94a3b8;
                border-top: 1px solid #253044;
            }
            QMessageBox {
                background: #111827;
                color: #e5e7eb;
            }
            """
        )
        font = QFont("Segoe UI", 10)
        QApplication.instance().setFont(font)

    def connect_to_server(self):
        if self.connect_inflight:
            return

        host = self.host_input.text().strip() or DEFAULT_HOST
        port = self.port_input.value()
        self.connect_inflight = True
        self._set_busy_message("Connecting...")
        self._set_connected(False)

        client = ShutterClient(host, port)
        self._run_task("connect", client, lambda c: c.status(), {"client": client})

    def disconnect_from_server(self):
        self.client = None
        self.current_status = {}
        self.connect_inflight = False
        self.refresh_inflight = False
        self.command_inflight = False
        self.poll_timer.stop()
        self._clear_channels()
        self.empty_label.show()
        self.connection_label.setText("Disconnected")
        self.summary_label.setText("No channels")
        self.last_update_label.setText("Last update: -")
        self.statusBar().showMessage("Disconnected")
        self.setWindowTitle("Kohda Lab Shutter")
        self._set_connected(False)

    def refresh_status(self, force=False):
        if not self.client or self.refresh_inflight:
            return
        if self.command_inflight and not force:
            return

        self.refresh_inflight = True
        self._run_task("refresh", self.client, lambda c: c.status())

    def run_command(self, operation, channels):
        if not self.client or self.command_inflight or not channels:
            return

        self.command_inflight = True
        self._set_actions_enabled(False)
        self._set_busy_message(f"{operation.title()}...")

        def callback(client):
            for channel in channels:
                if operation == "open":
                    client.open(channel)
                elif operation == "close":
                    client.close(channel)
                elif operation == "toggle":
                    client.toggle(channel)
            return client.status()

        self._run_task("command", self.client, callback, {"operation": operation})

    def _run_task(self, name, client, callback, context=None):
        task = ClientTask(name, client, callback, context)
        task.signals.finished.connect(self._task_finished)
        self.thread_pool.start(task)

    @Slot(str, object, object, object)
    def _task_finished(self, name, result, error, context):
        if name == "connect":
            self.connect_inflight = False
            if error:
                self._set_connected(False)
                self._show_error("Connect failed", error)
                self.connection_label.setText("Connection failed")
                self.statusBar().showMessage("Connection failed")
                return
            self.client = context["client"]
            self.current_status = result
            self.connection_label.setText(f"Connected to {self.client.host}:{self.client.port}")
            self.statusBar().showMessage("Connected")
            self.setWindowTitle(f"Kohda Lab Shutter - {self.client.host}:{self.client.port}")
            self._sync_channels(result)
            self._apply_status(result)
            self._set_connected(True)
            self.poll_timer.start()
            return

        if name == "refresh":
            self.refresh_inflight = False
            if error:
                self._mark_error(error)
                return
            self.current_status = result
            self._sync_channels(result)
            self._apply_status(result)
            return

        if name == "command":
            self.command_inflight = False
            self._set_actions_enabled(True)
            if error:
                self._show_error("Command failed", error)
                self.statusBar().showMessage("Command failed")
                return
            self.current_status = result
            self._sync_channels(result)
            self._apply_status(result)

    def _set_connected(self, connected):
        self.host_input.setEnabled(not connected and not self.connect_inflight)
        self.port_input.setEnabled(not connected and not self.connect_inflight)
        self.connect_button.setEnabled(not connected and not self.connect_inflight)
        self.disconnect_button.setEnabled(connected)
        self.refresh_action.setEnabled(connected)
        self._set_actions_enabled(connected and not self.command_inflight)

    def _set_actions_enabled(self, enabled):
        self.open_all_button.setEnabled(enabled)
        self.close_all_button.setEnabled(enabled)
        for card in self.channel_cards.values():
            card.set_actions_enabled(enabled)

    def _set_busy_message(self, message):
        self.connection_label.setText(message)
        self.statusBar().showMessage(message)

    def _clear_channels(self):
        for card in self.channel_cards.values():
            self.channel_layout.removeWidget(card)
            card.deleteLater()
        self.channel_cards.clear()

    def _sync_channels(self, status):
        channels = sorted(status)
        if channels == sorted(self.channel_cards):
            return

        self.empty_label.hide()
        self._clear_channels()
        for index, channel in enumerate(channels):
            card = ChannelCard(channel)
            card.close_button.clicked.connect(lambda checked=False, ch=channel: self.run_command("close", [ch]))
            card.open_button.clicked.connect(lambda checked=False, ch=channel: self.run_command("open", [ch]))
            card.toggle_button.clicked.connect(lambda checked=False, ch=channel: self.run_command("toggle", [ch]))
            self.channel_layout.insertWidget(index, card)
            self.channel_cards[channel] = card
        self._set_actions_enabled(self.client is not None and not self.command_inflight)

    def _apply_status(self, status):
        open_count = close_count = unknown_count = 0
        for channel, card in self.channel_cards.items():
            angle = status.get(channel)
            card.set_angle(angle)
            if angle == OPEN_ANGLE:
                open_count += 1
            elif angle == CLOSE_ANGLE:
                close_count += 1
            else:
                unknown_count += 1

        self.summary_label.setText(
            f"{len(self.channel_cards)} channels | open {open_count} | close {close_count} | unknown {unknown_count}"
        )
        self.last_update_label.setText(f"Last update: {time.strftime('%H:%M:%S')}")
        if self.client:
            self.connection_label.setText(f"Connected to {self.client.host}:{self.client.port}")
        self.statusBar().showMessage("Status updated")

    def _mark_error(self, error):
        for card in self.channel_cards.values():
            card.set_error()
        self.last_update_label.setText("Last update: failed")
        self.connection_label.setText(f"Communication error: {error}")
        self.statusBar().showMessage("Communication error")

    def _known_channels(self):
        if self.current_status:
            return sorted(self.current_status)
        return sorted(self.channel_cards)

    def _show_error(self, title, error):
        QMessageBox.critical(self, title, str(error))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = App()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
