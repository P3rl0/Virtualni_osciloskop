"""Non-blocking status and error display.

Hardware errors can arrive in bursts during startup/cleanup.  Showing modal
message boxes for every backend error is dangerous because it can trap the user
in a dialog loop.  This panel records the latest state and a short history while
keeping the UI usable.
"""

from __future__ import annotations

from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QPlainTextEdit

from frontend.styles import TEXT_DIM, TEXT_MED, dim_label


class StatusPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("STATUS / DIAGNOSTICS", parent)
        self._rows: dict[str, QLabel] = {}

        grid = QGridLayout(self)
        grid.setContentsMargins(8, 6, 8, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(5)

        for row, (key, value) in enumerate(
            [
                ("MODE", "SIMULATION"),
                ("DAQ", "idle"),
                ("SIG GEN", "disconnected"),
                ("LAST", "Ready"),
            ]
        ):
            grid.addWidget(dim_label(key), row, 0)
            label = QLabel(value)
            label.setObjectName("dim")
            label.setStyleSheet(f"color: {TEXT_MED}; letter-spacing: 0px;")
            grid.addWidget(label, row, 1)
            self._rows[key] = label

        self.history = QPlainTextEdit()
        self.history.setReadOnly(True)
        self.history.setMaximumBlockCount(80)
        self.history.setFixedHeight(92)
        self.history.setStyleSheet(
            f"color: {TEXT_DIM}; font-family: 'Courier New'; font-size: 10px;"
            "border: 1px solid #232d3e; border-radius: 4px; padding: 3px;"
        )
        grid.addWidget(self.history, 4, 0, 1, 2)

    def set_status(self, key: str, value: str) -> None:
        key = key.upper()
        if key in self._rows:
            self._rows[key].setText(value)

    def info(self, message: str) -> None:
        self.set_status("LAST", message)
        self.history.appendPlainText(f"INFO  {message}")

    def error(self, message: str) -> None:
        self.set_status("LAST", message)
        self.history.appendPlainText(f"ERROR {message}")
