"""PyQtGraph oscilloscope display.

The widget supports two rendering paths:
- simulation: generates local deterministic test signals;
- DAQ: renders backend-provided voltage data.

Vertical offsets are applied only here as display offsets.  Measurements and
backend trigger decisions continue to use physical voltage values.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from frontend.formatting import parse_scale
from frontend.styles import BG_MID, BORDER_COLOR, CH_COLORS, GRID_COLOR, TEXT_DIM

try:
    from backend.control_adapter import supported_timebase_labels, supported_volts_per_div_labels
except Exception:  # noqa: BLE001
    def supported_timebase_labels() -> list[str]:
        return ["100 µs/div", "200 µs/div", "500 µs/div", "1 ms/div", "2 ms/div", "5 ms/div", "10 ms/div", "20 ms/div", "50 ms/div", "100 ms/div", "200 ms/div", "500 ms/div", "1 s/div", "5 s/div"]

    def supported_volts_per_div_labels() -> list[str]:
        return ["100 µV/div", "200 µV/div", "500 µV/div", "1 mV/div", "2 mV/div", "5 mV/div", "10 mV/div", "20 mV/div", "50 mV/div", "100 mV/div", "200 mV/div", "500 mV/div", "1 V/div", "2 V/div", "5 V/div"]


SIM_SIGNALS = {
    1: dict(freq=1_000.0, amp=2.0, phase=0.0),
    2: dict(freq=2_500.0, amp=1.2, phase=np.pi / 4),
    3: dict(freq=500.0, amp=3.0, phase=np.pi),
    4: dict(freq=5_000.0, amp=0.8, phase=np.pi * 1.5),
}


@dataclass(slots=True)
class AutosetSuggestion:
    time_label: str
    volts_labels: dict[int, str]
    trigger_level_v: float


class PlotDisplay(QWidget):
    H_DIVS = 12
    V_DIVS = 10
    N_PTS = 5000
    MAX_DRAW_POINTS = 6000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_voltage_by_channel: dict[int, np.ndarray] = {}
        self.last_time_per_div = 1e-3

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
            curve = self.plot_widget.plot([], [], pen=pen)
            curve.setDownsampling(auto=True, method="peak")
            curve.setClipToView(True)
            self.curves[ch] = curve

        self.trigger_line = pg.InfiniteLine(
            pos=0.0,
            angle=0,
            pen=pg.mkPen("#ffd166", width=1, style=Qt.DashLine),
            movable=False,
        )
        self.center_time_line = pg.InfiniteLine(
            pos=self.H_DIVS / 2,
            angle=90,
            pen=pg.mkPen("#ffd166", width=1, style=Qt.DotLine),
            movable=False,
        )
        self.plot_widget.addItem(self.trigger_line)
        self.plot_widget.addItem(self.center_time_line)
        self.trigger_line.setVisible(False)
        self.center_time_line.setVisible(True)

    def _configure_plot(self) -> None:
        plot_item = self.plot_widget.getPlotItem()
        plot_item.hideAxis("bottom")
        plot_item.hideAxis("left")
        plot_item.setMenuEnabled(False)
        plot_item.setMouseEnabled(x=False, y=False)
        self.plot_widget.setStyleSheet(f"border: 1px solid {BORDER_COLOR}; border-radius: 4px;")
        plot_item.setXRange(0, self.H_DIVS, padding=0)
        plot_item.setYRange(-self.V_DIVS / 2, self.V_DIVS / 2, padding=0)
        self._draw_grid(plot_item)
        self._draw_axis_labels(plot_item)

    def _draw_grid(self, plot_item) -> None:
        pen_major = pg.mkPen(color=GRID_COLOR, width=1)
        pen_center = pg.mkPen(color="#152030", width=1, style=Qt.DashLine)
        pen_tick = pg.mkPen(color=GRID_COLOR, width=1, style=Qt.DotLine)

        for x in range(self.H_DIVS + 1):
            plot_item.addItem(pg.InfiniteLine(pos=x, angle=90, pen=pen_center if x == self.H_DIVS // 2 else pen_major, movable=False))
        for y in range(-self.V_DIVS // 2, self.V_DIVS // 2 + 1):
            plot_item.addItem(pg.InfiniteLine(pos=y, angle=0, pen=pen_center if y == 0 else pen_major, movable=False))
        for x in np.arange(0, self.H_DIVS, 0.2):
            if abs(x - round(x)) > 1e-9:
                plot_item.addItem(pg.InfiniteLine(pos=x, angle=90, pen=pen_tick, movable=False))

    def _draw_axis_labels(self, plot_item) -> None:
        font = QFont("Courier New", 7)
        for x in range(1, self.H_DIVS + 1):
            text = pg.TextItem(str(x), color=TEXT_DIM, anchor=(0.5, 1))
            text.setFont(font)
            text.setPos(x, -self.V_DIVS / 2 + 0.15)
            plot_item.addItem(text)
        for y in range(-self.V_DIVS // 2, self.V_DIVS // 2 + 1):
            if y == 0:
                continue
            text = pg.TextItem(f"{y:+d}", color=TEXT_DIM, anchor=(0, 0.5))
            text.setFont(font)
            text.setPos(0.1, y)
            plot_item.addItem(text)

    def clear(self) -> None:
        for curve in self.curves.values():
            curve.setData([], [])
            curve.setVisible(False)
        self.trigger_line.setVisible(False)
        self.last_voltage_by_channel.clear()

    def render_simulation(
        self,
        time_per_div: float,
        channel_params: dict[int, dict],
        trigger_cfg: dict,
        profile: str = "SINE",
    ) -> dict[int, dict[str, float | None] | None]:
        """Render deterministic local simulation data and return measurements."""
        self.last_time_per_div = time_per_div
        total_time = time_per_div * self.H_DIVS
        trigger_source = int(trigger_cfg["source"])
        trigger_level_v = float(trigger_cfg["level_v"])
        trigger_rising = bool(trigger_cfg["rising"])

        t_search = np.linspace(0, total_time * 3.0, self.N_PTS * 3)
        source_v = _generate_signal(trigger_source, t_search, profile)
        trigger_time = _find_trigger_time(t_search, source_v, trigger_level_v, trigger_rising)
        window_start = 0.0 if trigger_time is None else max(0.0, trigger_time - total_time / 2.0)

        t = np.linspace(window_start, window_start + total_time, self.N_PTS)
        x_div = (t - window_start) / time_per_div
        measurements: dict[int, dict[str, float | None] | None] = {}
        self.last_voltage_by_channel.clear()

        for ch in range(1, 5):
            params = channel_params[ch]
            if not params["enabled"]:
                self.curves[ch].setVisible(False)
                measurements[ch] = None
                continue
            voltage = _generate_signal(ch, t, profile)
            self.last_voltage_by_channel[ch] = voltage
            y_div = voltage / params["vdiv"] + params["offset_div"]
            self.curves[ch].setData(x_div, y_div)
            self.curves[ch].setVisible(True)
            measurements[ch] = _compute_measurements(voltage, t)

        self._update_trigger_line(channel_params, trigger_source, trigger_level_v)
        return measurements

    def update_live_data(
        self,
        display_data: np.ndarray,
        active_backend_indices: list[int],
        channel_params: dict[int, dict],
        trigger_cfg: dict,
    ) -> None:
        """Render DAQ data emitted by the backend.

        ``display_data`` rows are expected to be parallel to ``active_backend_indices``.
        Backend channel indices are 0-based; frontend display channels are 1-based.
        """
        if display_data is None or display_data.size == 0:
            return

        active_frontend_channels = {backend_index + 1 for backend_index in active_backend_indices}
        for ch in range(1, 5):
            if ch not in active_frontend_channels or not channel_params[ch]["enabled"]:
                self.curves[ch].setVisible(False)

        self.last_voltage_by_channel.clear()
        for row, backend_index in enumerate(active_backend_indices):
            frontend_ch = backend_index + 1
            if frontend_ch not in channel_params or row >= display_data.shape[0]:
                continue
            params = channel_params[frontend_ch]
            if not params["enabled"]:
                self.curves[frontend_ch].setVisible(False)
                continue

            voltage = np.asarray(display_data[row], dtype=float)
            if voltage.size == 0:
                self.curves[frontend_ch].setVisible(False)
                continue

            self.last_voltage_by_channel[frontend_ch] = voltage
            x_div = np.linspace(0, self.H_DIVS, voltage.size)
            y_div = voltage / params["vdiv"] + params["offset_div"]
            x_draw, y_draw = _downsample_for_plot(x_div, y_div, self.MAX_DRAW_POINTS)
            self.curves[frontend_ch].setData(x_draw, y_draw)
            self.curves[frontend_ch].setVisible(True)

        self._update_trigger_line(channel_params, int(trigger_cfg["source"]), float(trigger_cfg["level_v"]))

    def suggest_autoset(self, channel_params: dict[int, dict]) -> AutosetSuggestion | None:
        """Suggest display scales from the latest simulation or DAQ data."""
        active = [ch for ch, data in self.last_voltage_by_channel.items() if channel_params.get(ch, {}).get("enabled") and data.size]
        if not active:
            return None

        volts_labels: dict[int, str] = {}
        midpoint_values = []
        best_freq: float | None = None
        for ch in active:
            data = self.last_voltage_by_channel[ch]
            v_min = float(np.min(data))
            v_max = float(np.max(data))
            vpp = max(v_max - v_min, 1e-9)
            volts_labels[ch] = _choose_volts_label(vpp / 6.0)
            midpoint_values.append((v_max + v_min) / 2.0)
            metrics = _compute_measurements(data, np.linspace(0, self.last_time_per_div * self.H_DIVS, len(data)))
            freq = metrics.get("Freq")
            if freq and freq > 0:
                best_freq = freq if best_freq is None else max(best_freq, freq)

        time_label = _choose_time_label(best_freq)
        trigger_level = float(np.mean(midpoint_values)) if midpoint_values else 0.0
        return AutosetSuggestion(time_label=time_label, volts_labels=volts_labels, trigger_level_v=trigger_level)

    def _update_trigger_line(self, channel_params: dict[int, dict], trigger_source: int, trigger_level_v: float) -> None:
        source_params = channel_params.get(trigger_source)
        if not source_params or not source_params["enabled"]:
            self.trigger_line.setVisible(False)
            return
        trigger_y_div = trigger_level_v / source_params["vdiv"] + source_params["offset_div"]
        self.trigger_line.setPos(trigger_y_div)
        self.trigger_line.setVisible(True)


def _generate_signal(ch: int, t: np.ndarray, profile: str = "SINE") -> np.ndarray:
    spec = SIM_SIGNALS[ch]
    freq = spec["freq"]
    amp = spec["amp"]
    phase = spec["phase"]
    angle = 2 * np.pi * freq * t + phase
    profile = profile.upper()
    if profile == "SQUARE":
        return amp * np.sign(np.sin(angle))
    if profile == "TRIANGLE":
        return amp * (2 / np.pi) * np.arcsin(np.sin(angle))
    if profile == "RAMP":
        phase_cycles = (freq * t + phase / (2 * np.pi)) % 1.0
        return amp * (2.0 * phase_cycles - 1.0)
    if profile == "NOISE":
        rng = np.random.default_rng(ch)
        return 0.35 * amp * rng.standard_normal(t.size)
    if profile == "PULSE":
        phase_cycles = (freq * t + phase / (2 * np.pi)) % 1.0
        return np.where(phase_cycles < 0.12, amp, -0.15 * amp)
    return amp * np.sin(angle)


def _find_trigger_time(t: np.ndarray, voltage: np.ndarray, level_v: float, rising: bool) -> float | None:
    shifted = voltage - level_v
    if rising:
        indices = np.where((shifted[:-1] < 0.0) & (shifted[1:] >= 0.0))[0]
    else:
        indices = np.where((shifted[:-1] > 0.0) & (shifted[1:] <= 0.0))[0]
    if len(indices) == 0:
        return None
    idx = int(indices[0])
    t0, t1 = t[idx], t[idx + 1]
    y0, y1 = shifted[idx], shifted[idx + 1]
    if y1 == y0:
        return float(t0)
    fraction = -y0 / (y1 - y0)
    return float(t0 + fraction * (t1 - t0))


def _compute_measurements(voltage: np.ndarray, t: np.ndarray) -> dict[str, float | None]:
    v_min = float(np.min(voltage))
    v_max = float(np.max(voltage))
    vpp = v_max - v_min
    vrms = float(np.sqrt(np.mean(voltage**2)))
    mean = float(np.mean(voltage))

    midpoint = (v_max + v_min) / 2.0
    shifted = voltage - midpoint
    crossings = np.where(np.diff(np.signbit(shifted)))[0]
    if len(crossings) >= 2:
        avg_half_period = float(np.mean(np.diff(t[crossings])))
        period = avg_half_period * 2.0
        freq = 1.0 / period if period > 0 else None
    else:
        period = None
        freq = None

    return {
        "Mean": mean,
        "Vpp": vpp,
        "Vrms": vrms,
        "Freq": freq,
        "Period": period,
        "Rise": _transition_time(voltage, t, rising=True),
        "Fall": _transition_time(voltage, t, rising=False),
    }


def _transition_time(voltage: np.ndarray, t: np.ndarray, rising: bool) -> float | None:
    v_min = float(np.min(voltage))
    v_max = float(np.max(voltage))
    vpp = v_max - v_min
    if vpp < 1e-9:
        return None
    low = v_min + 0.1 * vpp
    high = v_min + 0.9 * vpp
    if rising:
        start = None
        seen_low = False
        for i, v in enumerate(voltage):
            if not seen_low and v <= low:
                seen_low = True
            elif seen_low and start is None and v >= low:
                start = i
            elif start is not None and v >= high:
                return float(t[i] - t[start])
    else:
        start = None
        seen_high = False
        for i, v in enumerate(voltage):
            if not seen_high and v >= high:
                seen_high = True
            elif seen_high and start is None and v <= high:
                start = i
            elif start is not None and v <= low:
                return float(t[i] - t[start])
    return None


def _downsample_for_plot(x: np.ndarray, y: np.ndarray, max_points: int) -> tuple[np.ndarray, np.ndarray]:
    if y.size <= max_points:
        return x, y
    step = int(np.ceil(y.size / max_points))
    return x[::step], y[::step]


def _choose_volts_label(required_v_per_div: float) -> str:
    labels = supported_volts_per_div_labels()
    for label in labels:
        if parse_scale(label) >= required_v_per_div:
            return label
    return labels[-1]


def _choose_time_label(freq_hz: float | None) -> str:
    labels = supported_timebase_labels()
    if not freq_hz or freq_hz <= 0:
        return "1 ms/div" if "1 ms/div" in labels else labels[0]
    # Show about three periods across the screen.
    target = (3.0 / freq_hz) / PlotDisplay.H_DIVS
    for label in labels:
        if parse_scale(label) >= target:
            return label
    return labels[-1]
