import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QComboBox, QGroupBox, QSizePolicy, QFrame, QCheckBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import pyqtgraph as pg


# ── Colour palette ──────────────────────────────────────────────────────────
BG_DARK      = "#0d0f14"
BG_MID       = "#12151c"
BG_PANEL     = "#181c26"
BG_WIDGET    = "#1e2330"
ACCENT_GREEN = "#00ff9f"   # CH1
ACCENT_BLUE  = "#00cfff"   # CH2
GRID_COLOR   = "#1e3040"
TEXT_PRIMARY = "#e0e8f0"
TEXT_DIM     = "#4a5568"
BORDER_COLOR = "#2a3448"

# ── Demo signal definitions (physical units) ─────────────────────────────────
# CH1: 1 kHz sine, ±2 V amplitude
CH1_FREQ_HZ  = 1_000
CH1_AMP_V    = 2.0

# CH2: 2.5 kHz sine, ±1.2 V amplitude, 45° phase offset
CH2_FREQ_HZ  = 2_500
CH2_AMP_V    = 1.2
CH2_PHASE    = np.pi / 4


# ── Scale parsing ────────────────────────────────────────────────────────────
_UNIT_TO_SI = {
    "ns": 1e-9, "µs": 1e-6, "us": 1e-6, "ms": 1e-3, "s": 1.0,
    "mV": 1e-3, "V": 1.0,
}

def parse_scale(text: str) -> float:
    """Convert e.g. '2 ms/div' -> 0.002  or  '500 mV/div' -> 0.5"""
    parts = text.strip().split()
    value = float(parts[0])
    unit  = parts[1].replace("/div", "")
    return value * _UNIT_TO_SI[unit]


# ── Stylesheet ───────────────────────────────────────────────────────────────
STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
}}
QGroupBox {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    margin-top: 22px;
    padding: 8px 6px 6px 6px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1.5px;
    color: {TEXT_DIM};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: {TEXT_DIM};
}}
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}
QLabel#value_label_ch1 {{
    color: {ACCENT_GREEN};
    font-size: 14px; font-weight: 700;
    font-family: 'Courier New', monospace;
    letter-spacing: 1px;
}}
QLabel#value_label_ch2 {{
    color: {ACCENT_BLUE};
    font-size: 14px; font-weight: 700;
    font-family: 'Courier New', monospace;
    letter-spacing: 1px;
}}
QLabel#section_title {{
    color: {TEXT_DIM};
    font-size: 9px; font-weight: 600;
    letter-spacing: 2px;
}}
QLabel#readout {{
    color: {ACCENT_BLUE};
    font-family: 'Courier New', monospace;
    font-size: 11px; font-weight: 600;
}}
QComboBox {{
    background-color: {BG_WIDGET};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 4px 8px;
    color: {TEXT_PRIMARY};
    font-size: 12px;
    min-width: 90px; min-height: 26px;
}}
QComboBox:hover  {{ border: 1px solid {ACCENT_GREEN}; }}
QComboBox:focus  {{ border: 1px solid {ACCENT_GREEN}; outline: none; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_DIM};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_WIDGET};
    border: 1px solid {BORDER_COLOR};
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_GREEN};
    selection-color: {BG_DARK};
    outline: none;
}}
QCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: 11px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {BORDER_COLOR};
    border-radius: 3px;
    background: {BG_WIDGET};
}}
QCheckBox#ch1::indicator:checked  {{ background: {ACCENT_GREEN}; border-color: {ACCENT_GREEN}; }}
QCheckBox#ch2::indicator:checked  {{ background: {ACCENT_BLUE};  border-color: {ACCENT_BLUE};  }}
QFrame#hsep {{
    background: {BORDER_COLOR};
    max-height: 1px; border: none;
}}
"""


def make_separator():
    sep = QFrame()
    sep.setObjectName("hsep")
    sep.setFrameShape(QFrame.HLine)
    return sep


# ── ScaleControl ─────────────────────────────────────────────────────────────
class ScaleControl(QWidget):
    """Labelled combo + readout for a single scale axis."""

    def __init__(self, title, options, readout_id, default=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(title)
        lbl.setObjectName("section_title")
        layout.addWidget(lbl)

        self.combo = QComboBox()
        for opt in options:
            self.combo.addItem(opt)
        if default:
            self.combo.setCurrentText(default)
        layout.addWidget(self.combo)

        self.readout = QLabel(self.combo.currentText())
        self.readout.setObjectName(readout_id)
        layout.addWidget(self.readout)

        self.combo.currentTextChanged.connect(self.readout.setText)

    def current_si(self):
        return parse_scale(self.combo.currentText())


# ── ChannelGroup ─────────────────────────────────────────────────────────────
class ChannelGroup(QGroupBox):
    VOLT_OPTIONS = [
        "1 mV/div",  "2 mV/div",  "5 mV/div",
        "10 mV/div", "20 mV/div", "50 mV/div",
        "100 mV/div","200 mV/div","500 mV/div",
        "1 V/div",   "2 V/div",   "5 V/div",
        "10 V/div",  "20 V/div",  "50 V/div",
        "100 V/div",
    ]

    def __init__(self, ch, default_vdiv="1 V/div", parent=None):
        super().__init__(f"VERTICAL — CH{ch}", parent)
        self.ch = ch
        label_color = ACCENT_GREEN if ch == 1 else ACCENT_BLUE

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.enable_cb = QCheckBox(f"CH{ch}  enabled")
        self.enable_cb.setObjectName(f"ch{ch}")
        self.enable_cb.setChecked(True)
        self.enable_cb.setStyleSheet(f"color: {label_color}; font-weight: 600;")
        layout.addWidget(self.enable_cb)

        self.scale_ctrl = ScaleControl(
            "Volts / Div", self.VOLT_OPTIONS,
            readout_id=f"value_label_ch{ch}",
            default=default_vdiv,
        )
        layout.addWidget(self.scale_ctrl)

    def is_enabled(self):
        return self.enable_cb.isChecked()

    def vdiv_si(self):
        return self.scale_ctrl.current_si()


# ── ControlPanel ─────────────────────────────────────────────────────────────
class ControlPanel(QWidget):
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

    def __init__(self, on_change_cb, parent=None):
        super().__init__(parent)
        self._cb = on_change_cb
        self.setFixedWidth(230)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(12)
        root.setAlignment(Qt.AlignTop)

        # Title
        title = QLabel("OSCILLOSCOPE")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Courier New", 11, QFont.Bold))
        title.setStyleSheet(f"color: {ACCENT_GREEN}; letter-spacing: 3px;")
        root.addWidget(title)
        sub = QLabel("DSO-1000 Virtual Bench")
        sub.setAlignment(Qt.AlignCenter)
        sub.setObjectName("section_title")
        root.addWidget(sub)
        root.addWidget(make_separator())

        # Horizontal
        grp_h = QGroupBox("HORIZONTAL")
        vb_h = QVBoxLayout(grp_h)
        self.time_ctrl = ScaleControl(
            "Time / Div", self.TIME_OPTIONS,
            readout_id="value_label_ch1", default="1 ms/div")
        vb_h.addWidget(self.time_ctrl)
        root.addWidget(grp_h)

        # CH1 + CH2
        self.ch1_grp = ChannelGroup(ch=1, default_vdiv="1 V/div")
        self.ch2_grp = ChannelGroup(ch=2, default_vdiv="500 mV/div")
        root.addWidget(self.ch1_grp)
        root.addWidget(self.ch2_grp)

        root.addWidget(make_separator())

        # Status
        status_grp = QGroupBox("STATUS")
        sl = QVBoxLayout(status_grp)
        sl.setSpacing(6)
        self._row(sl, "SAMPLE RATE",  "1 GSa/s")
        self._row(sl, "MEMORY DEPTH", "1 Mpts")
        self._row(sl, "COUPLING",     "DC")
        root.addWidget(status_grp)
        root.addStretch()

        badge = QLabel("● RUNNING")
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"color: {ACCENT_GREEN}; font-size: 10px; font-weight: 700;"
            f"letter-spacing: 2px; font-family: 'Courier New';")
        root.addWidget(badge)

        # Connect everything
        for sig in [
            self.time_ctrl.combo.currentTextChanged,
            self.ch1_grp.scale_ctrl.combo.currentTextChanged,
            self.ch2_grp.scale_ctrl.combo.currentTextChanged,
        ]:
            sig.connect(lambda _: self._cb())
        self.ch1_grp.enable_cb.stateChanged.connect(lambda _: self._cb())
        self.ch2_grp.enable_cb.stateChanged.connect(lambda _: self._cb())

    def _row(self, layout, key, value):
        row = QHBoxLayout()
        k = QLabel(key); k.setObjectName("section_title")
        v = QLabel(value); v.setObjectName("readout"); v.setAlignment(Qt.AlignRight)
        row.addWidget(k); row.addStretch(); row.addWidget(v)
        layout.addLayout(row)

    def time_per_div(self): return self.time_ctrl.current_si()
    def ch1_vdiv(self):     return self.ch1_grp.vdiv_si()
    def ch2_vdiv(self):     return self.ch2_grp.vdiv_si()
    def ch1_on(self):       return self.ch1_grp.is_enabled()
    def ch2_on(self):       return self.ch2_grp.is_enabled()


# ── PlotDisplay ───────────────────────────────────────────────────────────────
class PlotDisplay(QWidget):
    H_DIVS = 10
    V_DIVS = 8
    N_PTS  = 4000

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOption("background", BG_MID)
        pg.setConfigOption("foreground", TEXT_DIM)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setMinimumSize(600, 400)
        self.plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._configure_plot()
        layout.addWidget(self.plot_widget)

        pen1 = pg.mkPen(color=ACCENT_GREEN, width=1.5)
        pen2 = pg.mkPen(color=ACCENT_BLUE,  width=1.5)
        self.curve1 = self.plot_widget.plot([], [], pen=pen1)
        self.curve2 = self.plot_widget.plot([], [], pen=pen2)

    def _configure_plot(self):
        pi = self.plot_widget.getPlotItem()
        pi.hideAxis("bottom")
        pi.hideAxis("left")
        pi.setMenuEnabled(False)
        pi.setMouseEnabled(x=False, y=False)
        self.plot_widget.setStyleSheet(
            f"border: 1px solid {BORDER_COLOR}; border-radius: 4px;")
        pi.setXRange(0, self.H_DIVS, padding=0)
        pi.setYRange(-self.V_DIVS / 2, self.V_DIVS / 2, padding=0)
        self._draw_grid(pi)
        self._draw_axis_labels(pi)

    def _draw_grid(self, pi):
        pen_major  = pg.mkPen(color=GRID_COLOR, width=1)
        pen_center = pg.mkPen(color="#1a4060", width=1, style=Qt.DashLine)
        pen_tick   = pg.mkPen(color=GRID_COLOR, width=1, style=Qt.DotLine)

        for x in range(self.H_DIVS + 1):
            pen = pen_center if x == self.H_DIVS // 2 else pen_major
            pi.addItem(pg.InfiniteLine(pos=x, angle=90, pen=pen, movable=False))
        for y in range(-self.V_DIVS // 2, self.V_DIVS // 2 + 1):
            pen = pen_center if y == 0 else pen_major
            pi.addItem(pg.InfiniteLine(pos=y, angle=0, pen=pen, movable=False))
        for x in np.arange(0, self.H_DIVS, 0.2):
            if x % 1 != 0:
                pi.addItem(pg.InfiniteLine(pos=x, angle=90, pen=pen_tick, movable=False))

    def _draw_axis_labels(self, pi):
        font = QFont("Courier New", 7)
        for x in range(1, self.H_DIVS + 1):
            t = pg.TextItem(str(x), color=TEXT_DIM, anchor=(0.5, 1))
            t.setFont(font); t.setPos(x, -self.V_DIVS / 2 + 0.15)
            pi.addItem(t)
        for y in range(-self.V_DIVS // 2, self.V_DIVS // 2 + 1):
            if y == 0: continue
            t = pg.TextItem(f"{y:+d}", color=TEXT_DIM, anchor=(0, 0.5))
            t.setFont(font); t.setPos(0.1, y)
            pi.addItem(t)

    def refresh(self, time_per_div,
                ch1_vdiv, ch1_on,
                ch2_vdiv, ch2_on):
        """
        Re-render both channels in division space.

        The key idea:
          x_div = t_seconds / time_per_div     → 0 … H_DIVS
          y_div = v_volts   / volts_per_div    → ±V_DIVS/2

        The grid is fixed; only the mapping from physical units to
        divisions changes, so the wave compresses/stretches visually.
        """
        total_time = time_per_div * self.H_DIVS
        t = np.linspace(0, total_time, self.N_PTS)

        if ch1_on:
            v1 = CH1_AMP_V * np.sin(2 * np.pi * CH1_FREQ_HZ * t)
            self.curve1.setData(t / time_per_div, v1 / ch1_vdiv)
            self.curve1.setVisible(True)
        else:
            self.curve1.setVisible(False)

        if ch2_on:
            v2 = CH2_AMP_V * np.sin(2 * np.pi * CH2_FREQ_HZ * t + CH2_PHASE)
            self.curve2.setData(t / time_per_div, v2 / ch2_vdiv)
            self.curve2.setVisible(True)
        else:
            self.curve2.setVisible(False)


# ── Main window ───────────────────────────────────────────────────────────────
class OscilloscopeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DSO-1000  |  Virtual Oscilloscope")
        self.setMinimumSize(920, 580)

        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.plot_display  = PlotDisplay()
        self.control_panel = ControlPanel(on_change_cb=self._redraw)

        layout.addWidget(self.plot_display, stretch=1)
        layout.addWidget(self.control_panel)

        self.setStyleSheet(STYLESHEET)
        self._redraw()   # initial render

    def _redraw(self):
        cp = self.control_panel
        self.plot_display.refresh(
            time_per_div = cp.time_per_div(),
            ch1_vdiv     = cp.ch1_vdiv(),
            ch1_on       = cp.ch1_on(),
            ch2_vdiv     = cp.ch2_vdiv(),
            ch2_on       = cp.ch2_on(),
        )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = OscilloscopeWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()