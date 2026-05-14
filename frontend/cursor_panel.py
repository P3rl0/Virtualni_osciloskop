from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QGroupBox, QGridLayout, QHBoxLayout, QVBoxLayout,
    QCheckBox, QComboBox, QLabel,
)
from backend.config import CHANNEL_COLORS


def _fmt_time(s):
    a = abs(s)
    if a < 1e-6:
        return f"{s * 1e9:.2f} ns"
    if a < 1e-3:
        return f"{s * 1e6:.3f} µs"
    if a < 1.0:
        return f"{s * 1e3:.3f} ms"
    return f"{s:.4f} s"


def _fmt_freq(hz):
    a = abs(hz)
    if a >= 1e6:
        return f"{hz / 1e6:.3f} MHz"
    if a >= 1e3:
        return f"{hz / 1e3:.3f} kHz"
    return f"{hz:.3f} Hz"


def _fmt_volts(v):
    a = abs(v)
    if a < 1e-3:
        return f"{v * 1e6:.3f} µV"
    if a < 1.0:
        return f"{v * 1e3:.3f} mV"
    return f"{v:.4f} V"


class CursorPanel(QGroupBox):
    def __init__(self, plot_widget, daq_worker, parent=None):
        super().__init__("Cursors", parent)
        self._plot = plot_widget
        self._daq = daq_worker

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 14, 6, 6)

        # ── Time cursors ──────────────────────────────────────────────────
        t_row = QHBoxLayout()
        self._t_enable = QCheckBox("Time cursors")
        self._t_enable.setStyleSheet("color: #00d0ff;")
        t_row.addWidget(self._t_enable)
        t_row.addStretch(1)
        layout.addLayout(t_row)

        t_grid = QGridLayout()
        t_grid.setSpacing(2)
        t_grid.addWidget(QLabel("T1:"), 0, 0)
        self._t1_lbl = QLabel("---");  t_grid.addWidget(self._t1_lbl, 0, 1)
        t_grid.addWidget(QLabel("T2:"), 0, 2)
        self._t2_lbl = QLabel("---");  t_grid.addWidget(self._t2_lbl, 0, 3)
        t_grid.addWidget(QLabel("ΔT:"), 1, 0)
        self._dt_lbl = QLabel("---");  t_grid.addWidget(self._dt_lbl, 1, 1)
        t_grid.addWidget(QLabel("1/ΔT:"), 1, 2)
        self._df_lbl = QLabel("---");  t_grid.addWidget(self._df_lbl, 1, 3)
        layout.addLayout(t_grid)

        # ── Voltage cursors ───────────────────────────────────────────────
        v_row = QHBoxLayout()
        self._v_enable = QCheckBox("Voltage cursors")
        self._v_enable.setStyleSheet("color: #ff66cc;")
        v_row.addWidget(self._v_enable)
        v_row.addWidget(QLabel("Ref:"))
        self._v_chan = QComboBox()
        for i in range(len(self._daq.channels)):
            self._v_chan.addItem(f"CH{i + 1}")
            self._v_chan.setItemData(i, QColor(CHANNEL_COLORS[i]), Qt.ForegroundRole)
        v_row.addWidget(self._v_chan)
        layout.addLayout(v_row)

        v_grid = QGridLayout()
        v_grid.setSpacing(2)
        v_grid.addWidget(QLabel("V1:"), 0, 0)
        self._v1_lbl = QLabel("---");  v_grid.addWidget(self._v1_lbl, 0, 1)
        v_grid.addWidget(QLabel("V2:"), 0, 2)
        self._v2_lbl = QLabel("---");  v_grid.addWidget(self._v2_lbl, 0, 3)
        v_grid.addWidget(QLabel("ΔV:"), 1, 0)
        self._dv_lbl = QLabel("---");  v_grid.addWidget(self._dv_lbl, 1, 1, 1, 3)
        layout.addLayout(v_grid)

        # ── Wire signals ──────────────────────────────────────────────────
        self._t_enable.toggled.connect(self._plot.set_time_cursors_visible)
        self._t_enable.toggled.connect(self._refresh)
        self._v_enable.toggled.connect(self._plot.set_voltage_cursors_visible)
        self._v_enable.toggled.connect(self._refresh)
        self._v_chan.currentIndexChanged.connect(self._refresh)
        for cur in (self._plot.t_cursor_a, self._plot.t_cursor_b,
                    self._plot.v_cursor_a, self._plot.v_cursor_b):
            cur.sigPositionChanged.connect(self._refresh)

    def _refresh(self, *_):
        if self._t_enable.isChecked():
            timebase = self._daq.timebase
            t1 = self._plot.t_cursor_a.value() * timebase
            t2 = self._plot.t_cursor_b.value() * timebase
            dt = t2 - t1
            self._t1_lbl.setText(_fmt_time(t1))
            self._t2_lbl.setText(_fmt_time(t2))
            self._dt_lbl.setText(_fmt_time(dt))
            self._df_lbl.setText(_fmt_freq(1.0 / dt) if dt != 0 else "---")
        else:
            for lbl in (self._t1_lbl, self._t2_lbl, self._dt_lbl, self._df_lbl):
                lbl.setText("---")

        if self._v_enable.isChecked():
            ch = self._v_chan.currentIndex()
            vdiv   = self._daq.channels[ch]["volts_per_div"]
            offset = self._daq.channels[ch]["vertical_offset"]
            v1 = self._plot.v_cursor_a.value() * vdiv - offset
            v2 = self._plot.v_cursor_b.value() * vdiv - offset
            self._v1_lbl.setText(_fmt_volts(v1))
            self._v2_lbl.setText(_fmt_volts(v2))
            self._dv_lbl.setText(_fmt_volts(v2 - v1))
        else:
            for lbl in (self._v1_lbl, self._v2_lbl, self._dv_lbl):
                lbl.setText("---")

    def on_data_update(self):
        """Called when new data arrives or settings change — keeps readouts in sync."""
        self._refresh()
