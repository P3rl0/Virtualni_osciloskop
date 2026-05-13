from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QMainWindow,
    QScrollArea, QSizePolicy, QStatusBar, QVBoxLayout, QWidget,
)

from backend.config import (
    TIMEBASE_MAP, load_yaml, pack_settings, save_yaml,
)
from backend.daq import DaqWorker
from backend.signal_gen import SignalGenWorker
from frontend.channel_controls import ChannelPanel
from frontend.measurement_panel import MeasurementPanel
from frontend.plot_widget import OscilloscopeWidget
from frontend.signal_gen_panel import SignalGenPanel
from frontend.trigger_controls import TriggerPanel

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
        from backend.config import CHANNEL_COLORS
        for i in range(len(self.daq.channels)):
            panel = ChannelPanel(i, CHANNEL_COLORS[i], self.daq)
            right_layout.addWidget(panel)
            self._ch_panels.append(panel)

        # Trigger panel
        self.trigger_panel = TriggerPanel(self.daq, self._poll_timer)
        right_layout.addWidget(self.trigger_panel)

        # Signal generator panel
        self.sig_gen_panel = SignalGenPanel(self.sg)
        right_layout.addWidget(self.sig_gen_panel)

        right_layout.addStretch(1)

        # ── Wire signals ─────────────────────────────────────────────────
        self.daq.graph_data.connect(self._on_graph_data)
        self.daq.measurements_data.connect(self.meas_panel.update_measurements)
        self.daq.error_occurred.connect(self._on_error)
        self.sg.error_occurred.connect(self._on_error)

        self._poll_timer.timeout.connect(self._on_poll_tick)
        self._timebase_combo.currentIndexChanged.connect(self._on_timebase)

        # ── Start acquisition ─────────────────────────────────────────────
        self.daq.start_task()
        self._poll_timer.start()

    # ── Poll tick ─────────────────────────────────────────────────────────

    def _on_poll_tick(self):
        self.daq.poll_queue()
        self.trigger_panel.on_poll_tick()

    # ── Data handler ──────────────────────────────────────────────────────

    def _on_graph_data(self, display_data):
        active_indices = [i for i, ch in enumerate(self.daq.channels) if ch["enable"]]
        channel_params = {
            i: {
                "volts_per_div":    ch["volts_per_div"],
                "vertical_offset":  ch["vertical_offset"],
            }
            for i, ch in enumerate(self.daq.channels)
        }
        trigger_level = self.daq.trigger.settings["trigger_level"]
        trigger_chan  = self.daq.trigger.settings["trigger_channel"]
        self.plot.update_traces(
            display_data, active_indices, channel_params,
            trigger_level, trigger_chan,
        )

    # ── Control handlers ──────────────────────────────────────────────────

    def _on_timebase(self, index):
        self.daq.set_timebase(_TIMEBASE_KEYS[index])

    def _on_error(self, msg: str):
        self._status.showMessage(f"Error: {msg}", 8000)

    # ── Close ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._poll_timer.stop()
        self.daq.stop_task()
        self.sg.disconnect_device()
        if self._app_cfg.get("save_on_exit", True):
            try:
                data = pack_settings(
                    self.daq.settings,
                    self.daq.trigger.settings,
                    self.daq.measurements.measurements,
                    self.sg.settings,
                    self._app_cfg,
                )
                save_yaml(data, self._config_path)
            except Exception as e:
                self._status.showMessage(f"Settings save failed: {e}")
        event.accept()
