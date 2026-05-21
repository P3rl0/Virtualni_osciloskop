from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QLabel, QCheckBox, QSizePolicy,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from backend.config import CHANNEL_COLORS

_MEASUREMENTS = [
    ("mean",         "Mean"),
    ("rms",          "RMS"),
    ("min",          "Min"),
    ("max",          "Max"),
    ("peak_to_peak", "Pk-Pk"),
    ("frequency",    "Freq"),
    ("rise_time",    "Rise"),
    ("fall_time",    "Fall"),
]
_NUM_CHANNELS = 4


def _fmt(name, value):
    if value is None:
        return "---"
    if name == "frequency":
        if value >= 1e6:
            return f"{value / 1e6:.3f} MHz"
        if value >= 1e3:
            return f"{value / 1e3:.3f} kHz"
        return f"{value:.4f} Hz"
    if name in ("rise_time", "fall_time"):
        if value < 1e-3:
            return f"{value * 1e6:.3f} µs"
        return f"{value * 1e3:.3f} ms"
    # voltage
    if abs(value) < 1e-3:
        return f"{value * 1e6:.3f} µV"
    if abs(value) < 1.0:
        return f"{value * 1e3:.3f} mV"
    return f"{value:.4f} V"


class MeasurementPanel(QWidget):
    def __init__(self, daq_worker, parent=None):
        super().__init__(parent)
        self._daq = daq_worker

        grid = QGridLayout(self)
        grid.setSpacing(2)
        grid.setContentsMargins(4, 4, 4, 4)

        bold = QFont()
        bold.setBold(True)

        # Column headers (CH1..CH4)
        grid.addWidget(QLabel(""), 0, 0)  # top-left corner spacer
        for ch in range(_NUM_CHANNELS):
            hdr = QLabel(f"CH{ch + 1}")
            hdr.setFont(bold)
            hdr.setStyleSheet(f"color: {CHANNEL_COLORS[ch]};")
            hdr.setAlignment(Qt.AlignCenter)
            # each channel takes 2 columns: checkbox + value
            grid.addWidget(hdr, 0, 1 + ch * 2, 1, 2, alignment=Qt.AlignCenter)

        self._labels = {}    # (ch, name) -> QLabel
        self._checks = {}    # (ch, name) -> QCheckBox

        for row, (meas_key, meas_label) in enumerate(_MEASUREMENTS, start=1):
            lbl = QLabel(meas_label)
            lbl.setFont(bold)
            grid.addWidget(lbl, row, 0)

            for ch in range(_NUM_CHANNELS):
                cb = QCheckBox()
                cb.setFixedWidth(18)
                # initialise from backend
                enabled = self._daq.measurements.measurements[ch].get(meas_key, False)
                cb.blockSignals(True)
                cb.setChecked(enabled)
                cb.blockSignals(False)
                cb.stateChanged.connect(
                    lambda state, c=ch, k=meas_key: self._on_toggle(c, k, bool(state))
                )
                grid.addWidget(cb, row, 1 + ch * 2, alignment=Qt.AlignRight)

                val_lbl = QLabel("---")
                val_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                val_lbl.setMinimumWidth(70)
                val_lbl.setStyleSheet(f"color: {CHANNEL_COLORS[ch]};")
                grid.addWidget(val_lbl, row, 2 + ch * 2)

                self._labels[(ch, meas_key)] = val_lbl
                self._checks[(ch, meas_key)] = cb

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # Reflect initial channel-enable state (e.g. channels disabled in YAML
        # should show greyed-out checkboxes + "---" values from the start).
        self.refresh_channel_state()

    def _on_toggle(self, ch, meas_key, enabled):
        self._daq.measurements.set_measurement(ch, meas_key, enabled)
        if not enabled:
            self._labels[(ch, meas_key)].setText("---")

    def update_measurements(self, results: dict):
        """results keyed by (phys_idx, meas_name) -> float | None"""
        for (ch, name), value in results.items():
            lbl = self._labels.get((ch, name))
            if lbl is not None:
                lbl.setText(_fmt(name, value))

    def refresh_channel_state(self):
        """Sync the panel to which channels are currently enabled.
        Call when any channel's enable flag changes. Disabled channels get:
          - all value labels cleared to "---"
          - all checkboxes greyed out (the checked state is preserved so it
            returns when the channel is re-enabled)."""
        enabled_channels = {i for i, ch in enumerate(self._daq.channels) if ch["enable"]}
        for (ch, name), lbl in self._labels.items():
            cb = self._checks[(ch, name)]
            if ch in enabled_channels:
                cb.setEnabled(True)
            else:
                cb.setEnabled(False)
                lbl.setText("---")
