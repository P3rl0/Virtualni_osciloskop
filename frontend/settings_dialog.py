"""Small hardware/app settings dialog backed by config.yaml.

This dialog intentionally edits only stable connection-level settings.  Runtime
oscilloscope controls such as volts/div, trigger level, and measurements remain
in the main UI.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)


class SettingsDialog(QDialog):
    def __init__(self, config_path: Path | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Virtual oscilloscope settings")
        self.config_path = config_path or Path.cwd() / "backend" / "config.yaml"
        self._data: dict = {}

        root = QVBoxLayout(self)
        root.addWidget(QLabel("Connection settings are saved to backend/config.yaml."))

        form = QFormLayout()
        self.device_prefix_edit = QLineEdit("Dev2")
        self.gpib_spin = QSpinBox()
        self.gpib_spin.setRange(0, 30)
        self.gpib_spin.setValue(10)
        self.save_on_exit_cb = QCheckBox("Save settings automatically on exit")
        form.addRow("NI device", self.device_prefix_edit)
        form.addRow("Signal generator GPIB address", self.gpib_spin)
        form.addRow("", self.save_on_exit_cb)
        root.addLayout(form)

        self.note = QLabel("DAQ mode should be restarted after changing hardware settings.")
        self.note.setWordWrap(True)
        root.addWidget(self.note)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            return
        with open(self.config_path, "r", encoding="utf-8") as file:
            self._data = yaml.safe_load(file) or {}

        channels = self._data.get("daq_settings", {}).get("channels", [])
        if channels and isinstance(channels[0].get("name"), str):
            first = channels[0]["name"]
            self.device_prefix_edit.setText(first.split("/")[0])

        sig = self._data.get("signal_gen_settings", {})
        if "gpib_address" in sig:
            self.gpib_spin.setValue(int(sig["gpib_address"]))

        app = self._data.get("app_settings", {})
        self.save_on_exit_cb.setChecked(bool(app.get("save_on_exit", True)))

    def accept(self) -> None:  # noqa: D102 - Qt override
        device = self.device_prefix_edit.text().strip()
        if not device:
            self.note.setText("Device name cannot be empty.")
            return

        data = self._data or {}
        data.setdefault("daq_settings", {}).setdefault("channels", [])
        for idx, channel in enumerate(data["daq_settings"]["channels"]):
            channel["name"] = f"{device}/ai{idx}"

        data.setdefault("signal_gen_settings", {})["gpib_address"] = int(self.gpib_spin.value())
        data.setdefault("app_settings", {})["save_on_exit"] = bool(self.save_on_exit_cb.isChecked())

        with open(self.config_path, "w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, sort_keys=False, allow_unicode=True)
        super().accept()
