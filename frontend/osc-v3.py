import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QComboBox, QGroupBox, QSizePolicy, QFrame, QCheckBox,
    QScrollArea, QDoubleSpinBox, QGridLayout, QPushButton, QDial
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import pyqtgraph as pg


# ── Colour palette ────────────────────────────────────────────────────────────
BG_DARK      = "#0d0f14"
BG_MID       = "#0f1219"
BG_PANEL     = "#13161f"
BG_WIDGET    = "#1a1e2a"
BG_WIDGET2   = "#1e2330"
GRID_COLOR   = "#182030"
TEXT_PRIMARY = "#d8e4f0"
TEXT_DIM     = "#3d5068"
TEXT_MED     = "#6a7f96"
BORDER_COLOR = "#232d3e"

CH_COLORS = {
    1: "#00ff9f",
    2: "#00cfff",
    3: "#ff9f00",
    4: "#cf6aff",
}

SIGNALS = {
    1: dict(freq=1_000,   amp=2.0,  phase=0,          label="1 kHz  sine"),
    2: dict(freq=2_500,   amp=1.2,  phase=np.pi/4,    label="2.5 kHz sine"),
    3: dict(freq=500,     amp=3.0,  phase=np.pi,      label="500 Hz sine"),
    4: dict(freq=5_000,   amp=0.8,  phase=np.pi*1.5,  label="5 kHz  sine"),
}

DEFAULT_VDIV = {1: "1 V/div", 2: "500 mV/div", 3: "2 V/div", 4: "200 mV/div"}

_UNIT_SI = {
    "ns": 1e-9, "µs": 1e-6, "us": 1e-6,
    "ms": 1e-3, "s":  1.0,
    "mV": 1e-3, "V":  1.0,
}


def parse_scale(text: str) -> float:
    parts = text.strip().split()
    return float(parts[0]) * _UNIT_SI[parts[1].replace("/div", "")]


# ── Measurement helpers ───────────────────────────────────────────────────────
def compute_measurements(v: np.ndarray, t: np.ndarray) -> dict:
    vpp = float(np.max(v) - np.min(v))
    vrms = float(np.sqrt(np.mean(v ** 2)))

    zero_crossings = np.where(np.diff(np.sign(v)))[0]
    if len(zero_crossings) >= 2:
        avg_half_period = np.mean(np.diff(t[zero_crossings]))
        period = float(avg_half_period * 2)
        freq = 1.0 / period if period > 0 else 0.0
    else:
        period = 0.0
        freq = 0.0

    return {"vpp": vpp, "vrms": vrms, "freq": freq, "period": period}


def fmt_time(t: float) -> str:
    if t == 0:
        return "---"
    if t < 1e-6:
        return f"{t * 1e9:.2f} ns"
    if t < 1e-3:
        return f"{t * 1e6:.2f} µs"
    if t < 1:
        return f"{t * 1e3:.2f} ms"
    return f"{t:.4f} s"


def fmt_freq(f: float) -> str:
    if f == 0:
        return "---"
    if f >= 1e6:
        return f"{f / 1e6:.3f} MHz"
    if f >= 1e3:
        return f"{f / 1e3:.3f} kHz"
    return f"{f:.2f} Hz"


def fmt_volt(v: float) -> str:
    if abs(v) < 1:
        return f"{v * 1e3:.2f} mV"
    return f"{v:.4f} V"


# ── Signal helpers ────────────────────────────────────────────────────────────
def generate_signal(ch: int, t: np.ndarray) -> np.ndarray:
    sig = SIGNALS[ch]
    return sig["amp"] * np.sin(2 * np.pi * sig["freq"] * t + sig["phase"])


def find_trigger_time(t: np.ndarray, v: np.ndarray, level_v: float, rising: bool) -> float | None:
    shifted = v - level_v

    if rising:
        idxs = np.where((shifted[:-1] < 0.0) & (shifted[1:] >= 0.0))[0]
    else:
        idxs = np.where((shifted[:-1] > 0.0) & (shifted[1:] <= 0.0))[0]

    if len(idxs) == 0:
        return None

    idx = idxs[0]
    t0, t1 = t[idx], t[idx + 1]
    y0, y1 = shifted[idx], shifted[idx + 1]

    if y1 == y0:
        return float(t0)

    frac = -y0 / (y1 - y0)
    return float(t0 + frac * (t1 - t0))


# ── Stylesheet ────────────────────────────────────────────────────────────────
def _ch_checkbox_css(ch):
    c = CH_COLORS[ch]
    return f"""
QCheckBox#ch{ch} {{ color: {c}; font-weight: 700; font-size: 12px; spacing: 6px; }}
QCheckBox#ch{ch}::indicator {{
    width: 13px; height: 13px;
    border: 1px solid {c}55;
    border-radius: 3px;
    background: {BG_WIDGET};
}}
QCheckBox#ch{ch}::indicator:checked {{
    background: {c};
    border-color: {c};
}}"""


STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {BG_WIDGET}; width: 6px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_COLOR}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QGroupBox {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    margin-top: 20px;
    padding: 6px 6px 6px 6px;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.8px;
    color: {TEXT_DIM};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px; padding: 0 4px;
    color: {TEXT_MED};
}}
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}
QLabel#dim {{
    color: {TEXT_DIM};
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 1.8px;
}}
QLabel#meas_val {{
    font-family: 'Courier New', monospace;
    font-size: 12px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
QLabel#meas_na {{
    font-family: 'Courier New', monospace;
    font-size: 12px;
    font-weight: 700;
    color: {TEXT_DIM};
}}
QLabel#time_readout {{
    color: #aac8e0;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#trigger_readout {{
    color: #ffd166;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#status_badge {{
    color: {TEXT_PRIMARY};
    font-family: 'Courier New', monospace;
    font-size: 11px;
    font-weight: 700;
}}
QComboBox {{
    background-color: {BG_WIDGET};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 3px 8px;
    color: {TEXT_PRIMARY};
    font-size: 11px;
    min-width: 86px;
    min-height: 24px;
}}
QComboBox:hover {{ border: 1px solid #2a4060; }}
QComboBox:focus {{ border: 1px solid #2a5080; outline: none; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_DIM};
    margin-right: 5px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_WIDGET2};
    border: 1px solid {BORDER_COLOR};
    color: {TEXT_PRIMARY};
    selection-background-color: #1e3a58;
    selection-color: {TEXT_PRIMARY};
    outline: none;
    font-size: 11px;
}}
QDoubleSpinBox {{
    background-color: {BG_WIDGET};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 3px 6px;
    color: {TEXT_PRIMARY};
    font-size: 11px;
    min-height: 24px;
}}
QDoubleSpinBox:hover {{ border: 1px solid #2a4060; }}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {BG_WIDGET2}; border: none; width: 16px;
}}
QDoubleSpinBox::up-arrow {{
    border-bottom: 4px solid {TEXT_DIM};
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
}}
QDoubleSpinBox::down-arrow {{
    border-top: 4px solid {TEXT_DIM};
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
}}
QCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: 11px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 13px;
    height: 13px;
    border: 1px solid {BORDER_COLOR};
    border-radius: 3px;
    background: {BG_WIDGET};
}}
QCheckBox::indicator:checked {{
    background: #2a5080;
    border-color: #3a70b0;
}}
QPushButton {{
    background-color: {BG_WIDGET};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    min-height: 28px;
    padding: 4px 10px;
    color: {TEXT_PRIMARY};
    font-size: 11px;
    font-weight: 700;
}}
QPushButton:hover {{
    border: 1px solid #35527a;
}}
QPushButton:checked {{
    background-color: #1f324a;
    border: 1px solid #4a7db5;
}}
QPushButton#run_btn:checked {{
    background-color: #153725;
    border: 1px solid #22a060;
    color: #8ef0b8;
}}
QPushButton#stop_btn:checked {{
    background-color: #3a1717;
    border: 1px solid #c04a4a;
    color: #ff9a9a;
}}
QDial {{
    background: transparent;
}}
QFrame#hsep {{
    background: {BORDER_COLOR};
    max-height: 1px;
    border: none;
}}
""" + "".join(_ch_checkbox_css(i) for i in range(1, 5))


def make_sep():
    f = QFrame()
    f.setObjectName("hsep")
    f.setFrameShape(QFrame.HLine)
    return f


def dim_label(text):
    l = QLabel(text)
    l.setObjectName("dim")
    return l


# ── ChannelGroup ──────────────────────────────────────────────────────────────
VOLT_OPTIONS = [
    "1 mV/div",  "2 mV/div",  "5 mV/div",
    "10 mV/div", "20 mV/div", "50 mV/div",
    "100 mV/div","200 mV/div","500 mV/div",
    "1 V/div",   "2 V/div",   "5 V/div",
    "10 V/div",  "20 V/div",  "50 V/div",
    "100 V/div",
]
COUPLING_OPTIONS = ["DC", "AC", "GND"]


class ChannelGroup(QGroupBox):
    def __init__(self, ch: int, on_change_cb, parent=None):
        super().__init__(f"CH{ch}  ·  {SIGNALS[ch]['label']}", parent)
        self.ch = ch
        self.color = CH_COLORS[ch]
        self._cb = on_change_cb

        self.setStyleSheet(f"""
            QGroupBox {{
                border-color: {self.color}28;
                background-color: {BG_PANEL};
            }}
            QGroupBox::title {{ color: {self.color}cc; }}
        """)

        grid = QGridLayout(self)
        grid.setSpacing(6)
        grid.setContentsMargins(8, 6, 8, 8)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.enable_cb = QCheckBox(f"CH{ch}")
        self.enable_cb.setObjectName(f"ch{ch}")
        self.enable_cb.setChecked(True)
        grid.addWidget(self.enable_cb, 0, 0, 1, 2)

        grid.addWidget(dim_label("COUPLING"), 0, 2)
        self.coupling = QComboBox()
        for o in COUPLING_OPTIONS:
            self.coupling.addItem(o)
        grid.addWidget(self.coupling, 0, 3)

        grid.addWidget(dim_label("V / DIV"), 1, 0)
        self.vdiv_combo = QComboBox()
        for o in VOLT_OPTIONS:
            self.vdiv_combo.addItem(o)
        self.vdiv_combo.setCurrentText(DEFAULT_VDIV[ch])
        grid.addWidget(self.vdiv_combo, 1, 1, 1, 3)

        grid.addWidget(dim_label("OFFSET"), 2, 0)
        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-10.0, 10.0)
        self.offset_spin.setSingleStep(0.1)
        self.offset_spin.setDecimals(2)
        self.offset_spin.setSuffix(" div")
        self.offset_spin.setValue(0.0)
        grid.addWidget(self.offset_spin, 2, 1, 1, 3)

        self.enable_cb.stateChanged.connect(lambda _: self._cb())
        self.vdiv_combo.currentTextChanged.connect(lambda _: self._cb())
        self.offset_spin.valueChanged.connect(lambda _: self._cb())
        self.coupling.currentTextChanged.connect(lambda _: self._cb())

    def is_enabled(self) -> bool:
        return self.enable_cb.isChecked()

    def vdiv_si(self) -> float:
        return parse_scale(self.vdiv_combo.currentText())

    def offset_div(self) -> float:
        return self.offset_spin.value()

    def coupling_str(self) -> str:
        return self.coupling.currentText()


# ── TriggerGroup ──────────────────────────────────────────────────────────────
class TriggerGroup(QGroupBox):
    def __init__(self, on_change_cb, runstop_cb, single_cb, parent=None):
        super().__init__("TRIGGER", parent)
        self._change_cb = on_change_cb
        self._runstop_cb = runstop_cb
        self._single_cb = single_cb

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.edge_btn = QPushButton("EDGE ↑")
        self.edge_btn.setCheckable(True)
        self.edge_btn.setChecked(True)
        top_row.addWidget(self.edge_btn, 1)

        self.single_btn = QPushButton("SINGLE")
        top_row.addWidget(self.single_btn, 1)

        self.run_btn = QPushButton("RUN")
        self.run_btn.setObjectName("run_btn")
        self.run_btn.setCheckable(True)
        self.run_btn.setChecked(True)
        top_row.addWidget(self.run_btn, 1)

        root.addLayout(top_row)

        mid = QGridLayout()
        mid.setHorizontalSpacing(8)
        mid.setVerticalSpacing(6)

        mid.addWidget(dim_label("SOURCE"), 0, 0)
        self.source_combo = QComboBox()
        self.source_combo.addItems(["CH1", "CH2", "CH3", "CH4"])
        mid.addWidget(self.source_combo, 0, 1)

        self.trigger_dial = QDial()
        self.trigger_dial.setNotchesVisible(True)
        self.trigger_dial.setRange(-50, 50)
        self.trigger_dial.setSingleStep(1)
        self.trigger_dial.setValue(0)
        self.trigger_dial.setFixedSize(78, 78)
        mid.addWidget(self.trigger_dial, 1, 0, 2, 1, alignment=Qt.AlignCenter)

        right_col = QVBoxLayout()
        right_col.addWidget(dim_label("LEVEL"))
        self.level_readout = QLabel("0.00 V")
        self.level_readout.setObjectName("trigger_readout")
        self.level_readout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        right_col.addWidget(self.level_readout)

        self.mode_readout = QLabel("EDGE  ·  RISING")
        self.mode_readout.setObjectName("dim")
        right_col.addWidget(self.mode_readout)

        self.state_badge = QLabel("ARMED")
        self.state_badge.setObjectName("status_badge")
        right_col.addWidget(self.state_badge)

        right_col.addStretch()
        mid.addLayout(right_col, 1, 1, 2, 1)

        root.addLayout(mid)

        self.edge_btn.clicked.connect(self._toggle_edge_mode)
        self.single_btn.clicked.connect(self._single_cb)
        self.run_btn.toggled.connect(self._runstop_cb)
        self.source_combo.currentTextChanged.connect(lambda _: self._change_cb())
        self.trigger_dial.valueChanged.connect(self._on_level_changed)

    def _toggle_edge_mode(self):
        self.edge_btn.setText("EDGE ↑" if self.is_rising_edge() else "EDGE ↓")
        self.mode_readout.setText("EDGE  ·  RISING" if self.is_rising_edge() else "EDGE  ·  FALLING")
        self._change_cb()

    def _on_level_changed(self):
        self.level_readout.setText(f"{self.level_volts():.2f} V")
        self._change_cb()

    def source_channel(self) -> int:
        return int(self.source_combo.currentText().replace("CH", ""))

    def level_volts(self) -> float:
        return self.trigger_dial.value() / 10.0

    def is_rising_edge(self) -> bool:
        return self.edge_btn.isChecked()

    def set_running(self, running: bool):
        self.run_btn.blockSignals(True)
        self.run_btn.setChecked(running)
        self.run_btn.setText("RUN" if running else "STOP")
        self.run_btn.setObjectName("run_btn" if running else "stop_btn")
        self.run_btn.style().unpolish(self.run_btn)
        self.run_btn.style().polish(self.run_btn)
        self.state_badge.setText("ARMED" if running else "STOPPED")
        self._refresh_state_style()
        self.run_btn.blockSignals(False)

    def set_single_fired(self):
        self.state_badge.setText("SINGLE")
        self._refresh_state_style()

    def _refresh_state_style(self):
        text = self.state_badge.text()
        if text == "ARMED":
            self.state_badge.setStyleSheet("color: #8ef0b8;")
        elif text == "STOPPED":
            self.state_badge.setStyleSheet("color: #ff9a9a;")
        else:
            self.state_badge.setStyleSheet("color: #ffd166;")


# ── MeasurementPanel ──────────────────────────────────────────────────────────
class MeasurementPanel(QGroupBox):
    METRICS = ["Vpp", "Vrms", "Freq", "Period"]

    def __init__(self, parent=None):
        super().__init__("MEASUREMENTS", parent)
        self._cells: dict[int, dict[str, QLabel]] = {}

        grid = QGridLayout(self)
        grid.setSpacing(4)
        grid.setContentsMargins(8, 6, 8, 8)

        for col, metric in enumerate(self.METRICS, start=1):
            hdr = QLabel(metric)
            hdr.setObjectName("dim")
            hdr.setAlignment(Qt.AlignCenter)
            grid.addWidget(hdr, 0, col)

        for row, ch in enumerate(range(1, 5), start=1):
            color = CH_COLORS[ch]
            ch_lbl = QLabel(f"CH{ch}")
            ch_lbl.setStyleSheet(
                f"color: {color}; font-weight: 700; font-size: 11px;"
                f"font-family: 'Courier New';"
            )
            ch_lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(ch_lbl, row, 0)

            self._cells[ch] = {}
            for col, metric in enumerate(self.METRICS, start=1):
                lbl = QLabel("---")
                lbl.setObjectName("meas_na")
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet(f"color: {color}99;")
                grid.addWidget(lbl, row, col)
                self._cells[ch][metric] = lbl

        for c in range(5):
            grid.setColumnStretch(c, 1)

    def update_channel(self, ch: int, meas: dict | None):
        color = CH_COLORS[ch]
        cells = self._cells[ch]
        if meas is None:
            for lbl in cells.values():
                lbl.setText("---")
                lbl.setObjectName("meas_na")
                lbl.setStyleSheet(f"color: {color}44;")
        else:
            cells["Vpp"].setText(fmt_volt(meas["vpp"]))
            cells["Vrms"].setText(fmt_volt(meas["vrms"]))
            cells["Freq"].setText(fmt_freq(meas["freq"]))
            cells["Period"].setText(fmt_time(meas["period"]))
            for lbl in cells.values():
                lbl.setObjectName("meas_val")
                lbl.setStyleSheet(f"color: {color}dd;")


# ── ControlPanel ──────────────────────────────────────────────────────────────
TIME_OPTIONS = [
    "1 ns/div",  "2 ns/div",  "5 ns/div",
    "10 ns/div", "20 ns/div", "50 ns/div",
    "100 ns/div","200 ns/div","500 ns/div",
    "1 µs/div",  "2 µs/div",  "5 µs/div",
    "10 µs/div", "20 µs/div", "50 µs/div",
    "100 µs/div","200 µs/div","500 µs/div",
    "1 ms/div",  "2 ms/div",  "5 ms/div",
    "10 ms/div", "20 ms/div", "50 ms/div",
    "100 ms/div","200 ms/div","500 ms/div",
    "1 s/div",   "2 s/div",   "5 s/div",
]


class ControlPanel(QWidget):
    def __init__(self, on_change_cb, runstop_cb, single_cb, parent=None):
        super().__init__(parent)
        self._cb = on_change_cb
        self.setFixedWidth(335)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)
        root.setAlignment(Qt.AlignTop)

        scroll.setWidget(inner)
        outer.addWidget(scroll)

        title = QLabel("OSCILLOSCOPE")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Courier New", 11, QFont.Bold))
        title.setStyleSheet(f"color: {CH_COLORS[1]}; letter-spacing: 3px;")
        root.addWidget(title)

        sub = QLabel("DSO-1000  ·  Virtual Bench")
        sub.setAlignment(Qt.AlignCenter)
        sub.setObjectName("dim")
        root.addWidget(sub)

        root.addWidget(make_sep())

        self.trigger_group = TriggerGroup(
            on_change_cb=self._cb,
            runstop_cb=runstop_cb,
            single_cb=single_cb
        )
        root.addWidget(self.trigger_group)

        grp_h = QGroupBox("HORIZONTAL")
        vb_h = QVBoxLayout(grp_h)
        vb_h.setSpacing(6)

        vb_h.addWidget(dim_label("TIME / DIV"))
        self.time_combo = QComboBox()
        for o in TIME_OPTIONS:
            self.time_combo.addItem(o)
        self.time_combo.setCurrentText("1 ms/div")
        vb_h.addWidget(self.time_combo)

        self.time_readout = QLabel("1 ms/div")
        self.time_readout.setObjectName("time_readout")
        self.time_readout.setAlignment(Qt.AlignCenter)
        vb_h.addWidget(self.time_readout)

        self.time_combo.currentTextChanged.connect(self.time_readout.setText)
        self.time_combo.currentTextChanged.connect(lambda _: self._cb())
        root.addWidget(grp_h)

        root.addWidget(make_sep())

        self.ch_groups: dict[int, ChannelGroup] = {}
        for ch in range(1, 5):
            grp = ChannelGroup(ch, on_change_cb=self._cb)
            self.ch_groups[ch] = grp
            root.addWidget(grp)

        root.addWidget(make_sep())

        status_grp = QGroupBox("STATUS")
        sl = QVBoxLayout(status_grp)
        sl.setSpacing(5)
        self._srow(sl, "SAMPLE RATE", "1 GSa/s")
        self._srow(sl, "MEMORY DEPTH", "1 Mpts")
        self._srow(sl, "TRIG MODE", "EDGE")
        root.addWidget(status_grp)

        root.addStretch()

    def _srow(self, layout, key, val):
        row = QHBoxLayout()
        k = QLabel(key)
        k.setObjectName("dim")
        v = QLabel(val)
        v.setObjectName("dim")
        v.setStyleSheet(f"color: {TEXT_MED}; letter-spacing: 0px;")
        v.setAlignment(Qt.AlignRight)
        row.addWidget(k)
        row.addStretch()
        row.addWidget(v)
        layout.addLayout(row)

    def time_per_div(self) -> float:
        return parse_scale(self.time_combo.currentText())

    def ch(self, n: int) -> ChannelGroup:
        return self.ch_groups[n]

    def trigger(self) -> TriggerGroup:
        return self.trigger_group


# ── PlotDisplay ───────────────────────────────────────────────────────────────
class PlotDisplay(QWidget):
    H_DIVS = 10
    V_DIVS = 8
    N_PTS = 5000

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        pg.setConfigOption("background", BG_MID)
        pg.setConfigOption("foreground", TEXT_DIM)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMinimumSize(540, 380)
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._configure_plot()
        layout.addWidget(self.plot_widget)

        self.curves: dict[int, pg.PlotDataItem] = {}
        for ch in range(1, 5):
            pen = pg.mkPen(color=CH_COLORS[ch], width=1.6)
            self.curves[ch] = self.plot_widget.plot([], [], pen=pen)

        self.trigger_line = pg.InfiniteLine(
            pos=0.0,
            angle=0,
            pen=pg.mkPen("#ffd166", width=1, style=Qt.DashLine),
            movable=False
        )
        self.plot_widget.addItem(self.trigger_line)
        self.trigger_line.setVisible(False)

    def _configure_plot(self):
        pi = self.plot_widget.getPlotItem()
        pi.hideAxis("bottom")
        pi.hideAxis("left")
        pi.setMenuEnabled(False)
        pi.setMouseEnabled(x=False, y=False)
        self.plot_widget.setStyleSheet(
            f"border: 1px solid {BORDER_COLOR}; border-radius: 4px;"
        )
        pi.setXRange(0, self.H_DIVS, padding=0)
        pi.setYRange(-self.V_DIVS / 2, self.V_DIVS / 2, padding=0)
        self._draw_grid(pi)
        self._draw_axis_labels(pi)

    def _draw_grid(self, pi):
        pen_maj = pg.mkPen(color=GRID_COLOR, width=1)
        pen_ctr = pg.mkPen(color="#152030", width=1, style=Qt.DashLine)
        pen_tck = pg.mkPen(color=GRID_COLOR, width=1, style=Qt.DotLine)

        for x in range(self.H_DIVS + 1):
            pi.addItem(pg.InfiniteLine(
                pos=x,
                angle=90,
                pen=pen_ctr if x == self.H_DIVS // 2 else pen_maj,
                movable=False
            ))

        for y in range(-self.V_DIVS // 2, self.V_DIVS // 2 + 1):
            pi.addItem(pg.InfiniteLine(
                pos=y,
                angle=0,
                pen=pen_ctr if y == 0 else pen_maj,
                movable=False
            ))

        for x in np.arange(0, self.H_DIVS, 0.2):
            if x % 1 != 0:
                pi.addItem(pg.InfiniteLine(pos=x, angle=90, pen=pen_tck, movable=False))

    def _draw_axis_labels(self, pi):
        font = QFont("Courier New", 7)
        for x in range(1, self.H_DIVS + 1):
            t = pg.TextItem(str(x), color=TEXT_DIM, anchor=(0.5, 1))
            t.setFont(font)
            t.setPos(x, -self.V_DIVS / 2 + 0.15)
            pi.addItem(t)

        for y in range(-self.V_DIVS // 2, self.V_DIVS // 2 + 1):
            if y == 0:
                continue
            t = pg.TextItem(f"{y:+d}", color=TEXT_DIM, anchor=(0, 0.5))
            t.setFont(font)
            t.setPos(0.1, y)
            pi.addItem(t)

    def refresh(self, time_per_div: float, ch_params: dict, trigger_cfg: dict) -> dict[int, dict | None]:
        total_time = time_per_div * self.H_DIVS

        trigger_source = trigger_cfg["source"]
        source_vdiv = ch_params[trigger_source]["vdiv"]
        source_offset = ch_params[trigger_source]["offset_div"]
        trigger_level_v = trigger_cfg["level_v"]
        trigger_rising = trigger_cfg["rising"]

        t_search = np.linspace(0, total_time * 3.0, self.N_PTS * 3)
        source_v = generate_signal(trigger_source, t_search)
        trigger_time = find_trigger_time(t_search, source_v, trigger_level_v, trigger_rising)

        if trigger_time is None:
            window_start = 0.0
        else:
            window_start = max(0.0, trigger_time - total_time / 2.0)

        t = np.linspace(window_start, window_start + total_time, self.N_PTS)
        x_div = (t - window_start) / time_per_div

        measurements = {}

        for ch in range(1, 5):
            p = ch_params[ch]
            if not p["enabled"]:
                self.curves[ch].setVisible(False)
                measurements[ch] = None
                continue

            v = generate_signal(ch, t)
            y_div = v / p["vdiv"] + p["offset_div"]

            self.curves[ch].setData(x_div, y_div)
            self.curves[ch].setVisible(True)
            measurements[ch] = compute_measurements(v, t)

        if ch_params[trigger_source]["enabled"]:
            trigger_y_div = trigger_level_v / source_vdiv + source_offset
            self.trigger_line.setPos(trigger_y_div)
            self.trigger_line.setVisible(True)
        else:
            self.trigger_line.setVisible(False)

        return measurements


# ── Main window ───────────────────────────────────────────────────────────────
class OscilloscopeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DSO-1000  |  Virtual Oscilloscope")
        self.setMinimumSize(1240, 760)
        self.resize(1380, 840)

        self.running = True

        central = QWidget()
        self.setCentralWidget(central)

        outer = QHBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        self.plot_display = PlotDisplay()
        left_col.addWidget(self.plot_display, stretch=1)

        self.meas_panel = MeasurementPanel()
        left_col.addWidget(self.meas_panel, stretch=0)

        outer.addLayout(left_col, stretch=1)

        self.control_panel = ControlPanel(
            on_change_cb=self._redraw_from_controls,
            runstop_cb=self._on_runstop_toggled,
            single_cb=self._single_capture,
        )
        outer.addWidget(self.control_panel, stretch=0)

        self.setStyleSheet(STYLESHEET)
        self.control_panel.trigger().set_running(True)
        self._force_redraw()

    def _channel_params(self):
        cp = self.control_panel
        return {
            ch: {
                "vdiv": cp.ch(ch).vdiv_si(),
                "offset_div": cp.ch(ch).offset_div(),
                "enabled": cp.ch(ch).is_enabled(),
                "coupling": cp.ch(ch).coupling_str(),
            }
            for ch in range(1, 5)
        }

    def _trigger_params(self):
        trig = self.control_panel.trigger()
        return {
            "source": trig.source_channel(),
            "level_v": trig.level_volts(),
            "rising": trig.is_rising_edge(),
        }

    def _apply_measurements(self, measurements):
        for ch in range(1, 5):
            self.meas_panel.update_channel(ch, measurements[ch])

    def _force_redraw(self):
        cp = self.control_panel
        tpd = cp.time_per_div()
        ch_params = self._channel_params()
        trig_params = self._trigger_params()

        measurements = self.plot_display.refresh(tpd, ch_params, trig_params)
        self._apply_measurements(measurements)

    def _redraw_from_controls(self):
        if self.running:
            self._force_redraw()

    def _on_runstop_toggled(self, checked: bool):
        self.running = checked
        self.control_panel.trigger().set_running(checked)
        if self.running:
            self._force_redraw()

    def _single_capture(self):
        if self.running:
            self.running = False
            self.control_panel.trigger().set_running(False)

        self._force_redraw()
        self.control_panel.trigger().set_single_fired()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = OscilloscopeWindow()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()