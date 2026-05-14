from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMainWindow,
    QScrollArea, QStatusBar, QVBoxLayout, QWidget,
)
import pyqtgraph.exporters

from backend.config import (
    CHANNEL_COLORS, NUM_HORIZONTAL_DIVS, TIMEBASE_MAP,
    load_yaml, pack_settings, save_yaml,
)
from backend.daq import DaqWorker
from backend.signal_gen import SignalGenWorker
from frontend.actions_panel import ActionsPanel
from frontend.channel_controls import ChannelPanel
from frontend.cursor_panel import CursorPanel
from frontend.measurement_panel import MeasurementPanel
from frontend.plot_widget import OscilloscopeWidget
from frontend.signal_gen_panel import SignalGenPanel
from frontend.trigger_controls import TriggerPanel

_SCREENSHOT_DIR = Path(__file__).resolve().parents[1] / "screenshots"

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "backend" / "config.yaml"


def _fmt_timebase(v):
    if v < 1e-3:
        return f"{v * 1e6:.4g} µs/div"
    if v < 1.0:
        return f"{v * 1e3:.4g} ms/div"
    return f"{v:.4g} s/div"


_TIMEBASE_KEYS    = sorted(TIMEBASE_MAP.keys())
_TIMEBASE_LABELS  = [_fmt_timebase(v) for v in _TIMEBASE_KEYS]


class OscilloscopeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Virtual Oscilloscope — DSO-1000")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 860)

        self._config_path = _CONFIG_PATH
        self._app_cfg = load_yaml(self._config_path, area="app")

        # ── Backend workers ──────────────────────────────────────────────
        self.daq = DaqWorker()
        self.sg  = SignalGenWorker()

        # ── Poll timer (main thread, drives poll_queue) ──────────────────
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(33)

        # ── Status bar ───────────────────────────────────────────────────
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

        # ── Central widget ───────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        # ── Left column: plot + measurements ────────────────────────────
        left_col = QVBoxLayout()
        left_col.setSpacing(4)

        self.plot = OscilloscopeWidget()
        left_col.addWidget(self.plot, stretch=1)

        self.meas_panel = MeasurementPanel(self.daq)
        left_col.addWidget(self.meas_panel, stretch=0)

        outer.addLayout(left_col, stretch=1)

        # ── Right panel: controls in a scroll area ───────────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFixedWidth(310)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(6)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_scroll.setWidget(right_widget)
        outer.addWidget(right_scroll, stretch=0)

        # Timebase row
        tb_row = QHBoxLayout()
        tb_row.addWidget(QLabel("Timebase:"))
        self._timebase_combo = QComboBox()
        for label in _TIMEBASE_LABELS:
            self._timebase_combo.addItem(label)
        # set current timebase from backend
        tb_sec = self.daq.timebase
        if tb_sec in _TIMEBASE_KEYS:
            self._timebase_combo.setCurrentIndex(_TIMEBASE_KEYS.index(tb_sec))
        tb_row.addWidget(self._timebase_combo, stretch=1)
        right_layout.addLayout(tb_row)

        # Channel panels
        self._ch_panels = []
        for i in range(len(self.daq.channels)):
            panel = ChannelPanel(i, CHANNEL_COLORS[i], self.daq)
            panel.channel_settings_changed.connect(self._refresh_overlay)
            right_layout.addWidget(panel)
            self._ch_panels.append(panel)

        # Trigger panel
        self.trigger_panel = TriggerPanel(self.daq, self._poll_timer)
        right_layout.addWidget(self.trigger_panel)

        # Cursor panel
        self.cursor_panel = CursorPanel(self.plot, self.daq)
        right_layout.addWidget(self.cursor_panel)

        # Signal generator panel
        self.sig_gen_panel = SignalGenPanel(self.sg)
        right_layout.addWidget(self.sig_gen_panel)

        # App-level actions (save settings, screenshot)
        self.actions_panel = ActionsPanel(self._app_cfg.get("save_on_exit", True))
        self.actions_panel.save_on_exit_changed.connect(self._on_save_on_exit_toggled)
        self.actions_panel.save_now_requested.connect(self._save_settings_now)
        self.actions_panel.screenshot_requested.connect(self._save_screenshot)
        right_layout.addWidget(self.actions_panel)

        right_layout.addStretch(1)

        # ── Wire signals ─────────────────────────────────────────────────
        self.daq.graph_data.connect(self._on_graph_data)
        self.daq.measurements_data.connect(self.meas_panel.update_measurements)
        self.daq.error_occurred.connect(self._on_error)
        self.sg.error_occurred.connect(self._on_error)

        self._poll_timer.timeout.connect(self._on_poll_tick)
        self._timebase_combo.currentIndexChanged.connect(self._on_timebase)
        self.plot.trigger_position_dragged.connect(self._on_trigger_pos_dragged)
        self.trigger_panel.trigger_settings_changed.connect(self._on_trigger_settings_changed)

        self._data_received = False

    # ── Acquisition (call after show() so Qt is fully initialised) ───────

    def start_acquisition(self):
        try:
            self.daq.start_task()
        except Exception as e:
            self._status.showMessage(f"DAQ unavailable: {e}", 0)
        self._poll_timer.start()

    # ── Poll tick ─────────────────────────────────────────────────────────

    def _on_poll_tick(self):
        self.daq.poll_queue()
        self.trigger_panel.on_poll_tick()

    # ── Data handler ──────────────────────────────────────────────────────

    def _current_overlay_state(self):
        """Snapshot what the plot overlay needs to draw correctly."""
        active_indices = [i for i, ch in enumerate(self.daq.channels) if ch["enable"]]
        channel_params = {
            i: {
                "volts_per_div":    ch["volts_per_div"],
                "vertical_offset":  ch["vertical_offset"],
            }
            for i, ch in enumerate(self.daq.channels)
        }
        return active_indices, channel_params, self.daq.trigger.settings

    def _refresh_overlay(self):
        """Reposition trigger lines, channel-zero arrows, etc. from current backend state.
        Called when settings change so indicators don't wait for the next frame."""
        active_indices, channel_params, trig = self._current_overlay_state()
        self.plot.update_overlay(
            active_indices, channel_params,
            trig["trigger_level"], trig["trigger_channel"],
            trig["trigger_offset"], self.daq.timebase,
        )

    def _on_graph_data(self, display_data):
        if not self._data_received:
            self._data_received = True
            self._status.showMessage("Acquisition running", 0)
        active_indices, channel_params, _ = self._current_overlay_state()
        self._refresh_overlay()
        self.plot.update_traces(display_data, active_indices, channel_params)
        self.cursor_panel.on_data_update()

    # ── Control handlers ──────────────────────────────────────────────────

    def _on_timebase(self, index):
        self.daq.set_timebase(_TIMEBASE_KEYS[index])
        # Trigger arrow x-position is `6 + offset/timebase`, so a timebase
        # change moves it even if offset didn't change. Reposition immediately.
        self._refresh_overlay()

    def _on_trigger_settings_changed(self):
        # Reposition the lines from the new backend values, then flash them.
        self._refresh_overlay()
        self.plot.show_trigger_lines()

    def _on_trigger_pos_dragged(self, x_div: float):
        # Convert division position back to seconds offset and push to backend.
        timebase = self.daq.timebase
        offset_s = (x_div - NUM_HORIZONTAL_DIVS / 2) * timebase
        self.daq.trigger.set_trigger_offset(offset_s)
        self.trigger_panel.set_offset_external(offset_s)

    def _on_error(self, msg: str):
        self._status.showMessage(f"Error: {msg}", 0)

    # ── App actions ───────────────────────────────────────────────────────

    def _on_save_on_exit_toggled(self, on: bool):
        self._app_cfg["save_on_exit"] = bool(on)

    def _pack_current_settings(self) -> dict:
        return pack_settings(
            self.daq.settings,
            self.daq.trigger.settings,
            self.daq.measurements.measurements,
            self.sg.settings,
            self._app_cfg,
        )

    def _save_settings_now(self):
        try:
            save_yaml(self._pack_current_settings(), self._config_path)
        except Exception as e:
            self._status.showMessage(f"Settings save failed: {e}", 0)
            return
        self._status.showMessage(f"Settings saved to {self._config_path.name}", 4000)

    def _save_screenshot(self):
        try:
            _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            path = _SCREENSHOT_DIR / f"oscilloscope_{ts}.png"
            exporter = pyqtgraph.exporters.ImageExporter(self.plot.getPlotItem())
            # Pin width so the file isn't whatever the live window happens to be.
            exporter.parameters()["width"] = 1600
            exporter.export(str(path))
        except Exception as e:
            self._status.showMessage(f"Screenshot failed: {e}", 0)
            return
        self._status.showMessage(f"Screenshot saved: {path.name}", 4000)

    # ── Close ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._poll_timer.stop()
        self.daq.stop_task()
        self.sg.disconnect_device()
        if self._app_cfg.get("save_on_exit", True):
            try:
                save_yaml(self._pack_current_settings(), self._config_path)
            except Exception as e:
                self._status.showMessage(f"Settings save failed: {e}")
        event.accept()
