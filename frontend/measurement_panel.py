"""Measurement display widget for simulation and DAQ modes."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel

from frontend.formatting import fmt_freq, fmt_time, fmt_volt
from frontend.styles import CH_COLORS


class MeasurementPanel(QGroupBox):
    METRICS = ["Mean", "Vpp", "Vrms", "Freq", "Period", "Rise", "Fall"]

    def __init__(self, parent=None):
        super().__init__("MEASUREMENTS")
        self._cells: dict[int, dict[str, QLabel]] = {}
        self._headers: dict[str, QLabel] = {}
        self._enabled_metrics = set(self.METRICS)

        grid = QGridLayout(self)
        grid.setSpacing(4)
        grid.setContentsMargins(8, 6, 8, 8)

        for col, metric in enumerate(self.METRICS, start=1):
            header = QLabel(metric)
            header.setObjectName("dim")
            header.setAlignment(Qt.AlignCenter)
            grid.addWidget(header, 0, col)
            self._headers[metric] = header

        for row, ch in enumerate(range(1, 5), start=1):
            color = CH_COLORS[ch]
            ch_label = QLabel(f"CH{ch}")
            ch_label.setStyleSheet(
                f"color: {color}; font-weight: 700; font-size: 11px;"
                "font-family: 'Courier New';"
            )
            ch_label.setAlignment(Qt.AlignCenter)
            grid.addWidget(ch_label, row, 0)

            self._cells[ch] = {}
            for col, metric in enumerate(self.METRICS, start=1):
                label = QLabel("---")
                label.setObjectName("meas_na")
                label.setAlignment(Qt.AlignCenter)
                label.setStyleSheet(f"color: {color}99;")
                grid.addWidget(label, row, col)
                self._cells[ch][metric] = label

        for column in range(len(self.METRICS) + 1):
            grid.setColumnStretch(column, 1)

    def set_enabled_metrics(self, labels: set[str]) -> None:
        """Show selected measurements while keeping the table layout stable."""
        enabled = set(labels)
        if "Freq" in enabled:
            enabled.add("Period")
        self._enabled_metrics = enabled
        for metric, header in self._headers.items():
            visible = metric in self._enabled_metrics
            header.setVisible(visible)
            for ch in range(1, 5):
                self._cells[ch][metric].setVisible(visible)

    def clear(self) -> None:
        for ch in range(1, 5):
            self.update_channel(ch, None)

    def update_measurements(self, measurements: dict[int, dict[str, float | None]]) -> None:
        for ch in range(1, 5):
            values = measurements.get(ch)
            self.update_channel(ch, values if values else None)

    def update_channel(self, ch: int, values: dict[str, float | None] | None) -> None:
        color = CH_COLORS[ch]
        cells = self._cells[ch]
        if not values:
            for label in cells.values():
                label.setText("---")
                label.setObjectName("meas_na")
                label.setStyleSheet(f"color: {color}44;")
            return

        cells["Mean"].setText(fmt_volt(values.get("Mean")))
        cells["Vpp"].setText(fmt_volt(values.get("Vpp")))
        cells["Vrms"].setText(fmt_volt(values.get("Vrms")))
        cells["Freq"].setText(fmt_freq(values.get("Freq")))
        cells["Period"].setText(fmt_time(values.get("Period")))
        cells["Rise"].setText(fmt_time(values.get("Rise")))
        cells["Fall"].setText(fmt_time(values.get("Fall")))

        for label in cells.values():
            label.setObjectName("meas_val")
            label.setStyleSheet(f"color: {color}dd;")
