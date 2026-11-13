"""Per-channel edit dialog. Accepting queues a patch; it never accesses USB."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class AngleSpinBox(QSpinBox):
    def wheelEvent(self, event):
        # Scrolling the channel list must not silently change calibration.
        event.ignore()


class ChannelTuning(QDialog):
    def __init__(self, channels, parent=None):
        super().__init__(parent)
        self.original = channels
        self.editors = []
        self.changes = {}
        self.setWindowTitle("Channel tuning")
        self.resize(620, 340)
        layout = QVBoxLayout(self)
        hint = QLabel(
            "Change one channel at a time. Endpoints require checking the real shutter.\nGentle approach: last 12°, ≤1° per ≥40 ms. Pulse limits remain untouched."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget(len(channels), 5)
        self.table.setHorizontalHeaderLabels(
            ["Channel", "Close (°)", "Open (°)", "Soft Open", "Soft Close"]
        )
        self.table.verticalHeader().hide()
        for index, channel in enumerate(channels):
            label = f"CH{index:02}"
            if channel.get("label") and channel["label"] != label:
                label += " · " + str(channel["label"])
            item = QTableWidgetItem(label)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(index, 0, item)
            row = {}
            for column, field in enumerate(("close", "open"), 1):
                editor = AngleSpinBox()
                editor.setRange(0, 180)
                editor.setValue(channel[field])
                editor.setKeyboardTracking(False)
                self.table.setCellWidget(index, column, editor)
                row[field] = editor
            for column, field in enumerate(("soft_open", "soft_close"), 3):
                editor = QCheckBox()
                editor.setChecked(channel.get(field, False))
                editor.setToolTip(
                    "Reduce command speed only when approaching this endpoint. Other channels keep their own settings."
                )
                self.table.setCellWidget(index, column, editor)
                row[field] = editor
            self.editors.append(row)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 140)
        for column in range(1, 5):
            self.table.setColumnWidth(column, 98)
        layout.addWidget(self.table)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            "Queue changes"
        )
        self.buttons.accepted.connect(self.queue_changes)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def queue_changes(self):
        changes = {}
        for index, row in enumerate(self.editors):
            values = {
                field: (
                    editor.value() if field in ("close", "open") else editor.isChecked()
                )
                for field, editor in row.items()
            }
            if values["close"] == values["open"]:
                QMessageBox.warning(
                    self, "Channel tuning", f"CH{index:02}: Open and Close must differ."
                )
                return
            patch = {
                field: value
                for field, value in values.items()
                if value != self.original[index].get(field, False)
            }
            if patch:
                changes[index] = patch
        self.changes = changes
        self.accept()
