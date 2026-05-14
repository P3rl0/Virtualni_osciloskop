import math

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QGroupBox, QGridLayout, QHBoxLayout, QVBoxLayout,
    QComboBox, QDoubleSpinBox, QLabel, QPushButton,
)
from backend.config import NUM_VERTICAL_DIVS, NUM_HORIZONTAL_DIVS, TRIGGER_TYPE


def _decimals_for_step(step: float) -> int:
    """How many decimals does a QDoubleSpinBox need so a single step is visible?
    Avoid 0 (hides sub-unit motion) and cap at 6 (Qt's practical precision)."""
    if step <= 0 or not math.isfinite(step):
        return 4
    return max(1, min(6, -int(math.floor(math.log10(step))) + 1))


class TriggerPanel(QGroupBox):
    # Emitted whenever the user touches any trigger setting (level, slope,
    # source, mode, offset). main_window uses this to flash the trigger
    # overlay lines on the plot.
    trigger_settings_changed = pyqtSignal()

    def __init__(self, daq_worker, poll_timer, parent=None):
        """
        Args:
            daq_worker:  DaqWorker instance
            poll_timer:  QTimer that drives poll_queue() — started/stopped by Run/Stop
        """
        super().__init__("Trigger", parent)
        self._daq = daq_worker
        self._poll_timer = poll_timer
        self._running = True

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 14, 6, 6)

        grid = QGridLayout()
        grid.setSpacing(4)

        # Source
        grid.addWidget(QLabel("Source"), 0, 0)
        self._source_combo = QComboBox()
        self._source_combo.addItems(["CH1", "CH2", "CH3", "CH4"])
        grid.addWidget(self._source_combo, 0, 1)

        # Slope
        grid.addWidget(QLabel("Slope"), 0, 2)
        self._slope_btn = QPushButton("↑ Rising")
        self._slope_btn.setCheckable(True)
        grid.addWidget(self._slope_btn, 0, 3)

        # Level
        grid.addWidget(QLabel("Level"), 1, 0)
        self._level_spin = QDoubleSpinBox()
        self._level_spin.setRange(-20.0, 20.0)
        self._level_spin.setSingleStep(0.01)
        self._level_spin.setDecimals(3)
        self._level_spin.setSuffix(" V")
        grid.addWidget(self._level_spin, 1, 1)

        # Mode
        grid.addWidget(QLabel("Mode"), 1, 2)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([t.capitalize() for t in TRIGGER_TYPE])
        grid.addWidget(self._mode_combo, 1, 3)

        # Offset — ±60 s covers slowest timebase (5 s/div × 6 divisions = 30 s
        # either side of centre), with margin so a drag on the plot can't push
        # the backend past a value the spinbox can still display.
        grid.addWidget(QLabel("Offset"), 2, 0)
        self._offset_spin = QDoubleSpinBox()
        self._offset_spin.setRange(-60.0, 60.0)
        self._offset_spin.setSingleStep(0.001)
        self._offset_spin.setDecimals(4)
        self._offset_spin.setSuffix(" s")
        grid.addWidget(self._offset_spin, 2, 1)

        layout.addLayout(grid)

        # Run/Stop + Single shot. Single is a separate button (not a mode)
        # so the user can fire one capture without abandoning their current
        # auto/normal mode preference.
        btn_row = QHBoxLayout()
        self._runstop_btn = QPushButton("▶ RUN")
        self._runstop_btn.setCheckable(True)
        self._runstop_btn.setChecked(True)
        self._runstop_btn.setStyleSheet(
            "QPushButton:checked { background-color: #2a7a2a; color: white; font-weight: bold; }"
            "QPushButton:!checked { background-color: #7a2a2a; color: white; font-weight: bold; }"
        )
        btn_row.addWidget(self._runstop_btn, stretch=2)
        self._single_btn = QPushButton("◉ Single")
        self._single_btn.setToolTip("Arm one single-shot capture")
        btn_row.addWidget(self._single_btn, stretch=1)
        layout.addLayout(btn_row)

        # Initialise from backend
        self._load_from_backend()
        # Adapt step + range to current timebase / trigger-channel V/div.
        self.update_scales()

        # Connect signals
        self._source_combo.currentIndexChanged.connect(self._on_source)
        self._slope_btn.clicked.connect(self._on_slope)
        self._level_spin.valueChanged.connect(self._on_level)
        self._mode_combo.currentIndexChanged.connect(self._on_mode)
        self._offset_spin.valueChanged.connect(self._on_offset)
        self._runstop_btn.clicked.connect(self._on_runstop)
        self._single_btn.clicked.connect(self._on_single)

    # ── Init ─────────────────────────────────────────────────────────────

    def _load_from_backend(self):
        s = self._daq.trigger.settings
        for w in (self._source_combo, self._slope_btn, self._level_spin,
                  self._mode_combo, self._offset_spin):
            w.blockSignals(True)

        self._source_combo.setCurrentIndex(s["trigger_channel"])
        rising = s["trigger_slope"] == "rising"
        self._slope_btn.setChecked(not rising)
        self._slope_btn.setText("↓ Falling" if not rising else "↑ Rising")
        self._level_spin.setValue(s["trigger_level"])
        mode_idx = TRIGGER_TYPE.index(s["trigger_type"]) if s["trigger_type"] in TRIGGER_TYPE else 0
        self._mode_combo.setCurrentIndex(mode_idx)
        self._offset_spin.setValue(s["trigger_offset"])

        for w in (self._source_combo, self._slope_btn, self._level_spin,
                  self._mode_combo, self._offset_spin):
            w.blockSignals(False)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_source(self, index):
        # Preserve the line's on-screen y position across source switches.
        # The plot draws the level at y_div = (level + ch_offset) / ch_vdiv.
        # When the source channel changes, the new channel has its own
        # vdiv/offset — keeping the level in volts unchanged would yank
        # the line wildly off-screen. Compute the current y_div from the
        # OLD channel and back-solve a new level so y_div stays the same.
        old_idx = self._daq.trigger.settings["trigger_channel"]
        try:
            old_vdiv   = self._daq.channels[old_idx]["volts_per_div"]
            old_offset = self._daq.channels[old_idx]["vertical_offset"]
            old_level  = self._daq.trigger.settings["trigger_level"]
            y_div = (old_level + old_offset) / old_vdiv if old_vdiv > 0 else 0.0
            new_vdiv   = self._daq.channels[index]["volts_per_div"]
            new_offset = self._daq.channels[index]["vertical_offset"]
            new_level  = y_div * new_vdiv - new_offset
        except (KeyError, IndexError, ZeroDivisionError):
            new_level = self._daq.trigger.settings["trigger_level"]

        # Order is important:
        #   1. Switch channel so update_scales reads the new channel's vdiv.
        #   2. update_scales — adjusts spinbox range + clamp-syncs to backend.
        #   3. Override level with our preserved-y_div value (fits new range).
        self._daq.trigger.set_trigger_channel(index)
        self.update_scales()
        self._level_spin.blockSignals(True)
        self._level_spin.setValue(new_level)
        self._level_spin.blockSignals(False)
        self._daq.trigger.set_trigger_level(self._level_spin.value())
        self.trigger_settings_changed.emit()

    def update_scales(self):
        """Retarget the level and offset spinboxes' range, step, and decimals
        to match the current timebase and the current trigger channel's V/div.

        Call this when:
          - timebase changes
          - trigger source channel changes
          - the trigger channel's V/div or vertical offset changes
        """
        tb = max(1e-9, float(self._daq.timebase))
        chan_idx = self._daq.trigger.settings["trigger_channel"]
        try:
            vdiv = max(1e-9, float(self._daq.channels[chan_idx]["volts_per_div"]))
        except (KeyError, IndexError):
            vdiv = 1.0

        # Offset: cover ±half the plot width in seconds. Step = 1/100 of a
        # division so a single click is a tiny visible nudge.
        half_x_div = NUM_HORIZONTAL_DIVS / 2.0
        off_range  = half_x_div * tb
        off_step   = tb * 0.01
        self._offset_spin.blockSignals(True)
        self._offset_spin.setDecimals(_decimals_for_step(off_step))
        self._offset_spin.setRange(-off_range, off_range)
        self._offset_spin.setSingleStep(off_step)
        self._offset_spin.blockSignals(False)

        # Level: cover ±plot-height worth of volts (allowing some headroom
        # past the visible 5-div edge). Step = 1/100 of a division of V.
        half_y_div = NUM_VERTICAL_DIVS / 2.0
        lvl_range  = half_y_div * vdiv * 2.0  # 2× the visible range = headroom
        lvl_step   = vdiv * 0.01
        self._level_spin.blockSignals(True)
        self._level_spin.setDecimals(_decimals_for_step(lvl_step))
        self._level_spin.setRange(-lvl_range, lvl_range)
        self._level_spin.setSingleStep(lvl_step)
        self._level_spin.blockSignals(False)

        # The spinboxes silently clamp their value to the new range. If a
        # channel V/div change pushed the level outside the new bounds, the
        # backend would still hold the old (now-invisible) value. Sync.
        cur_lvl = self._level_spin.value()
        if cur_lvl != self._daq.trigger.settings["trigger_level"]:
            self._daq.trigger.set_trigger_level(cur_lvl)
        cur_off = self._offset_spin.value()
        if cur_off != self._daq.trigger.settings["trigger_offset"]:
            self._daq.trigger.set_trigger_offset(cur_off)

    def _on_slope(self, checked):
        falling = checked
        self._slope_btn.setText("↓ Falling" if falling else "↑ Rising")
        self._daq.trigger.set_trigger_slope("falling" if falling else "rising")
        self.trigger_settings_changed.emit()

    def _on_level(self, value):
        self._daq.trigger.set_trigger_level(value)
        self.trigger_settings_changed.emit()

    def _on_mode(self, index):
        trigger_type = TRIGGER_TYPE[index]
        self._daq.trigger.set_trigger_type(trigger_type)
        # Switching INTO single while running — discard stale samples
        # so we wait for a fresh edge rather than firing on history.
        if trigger_type == "single" and self._running:
            self._daq.clear_buffers()
        self.trigger_settings_changed.emit()

    def _on_offset(self, value):
        self._daq.trigger.set_trigger_offset(value)
        self.trigger_settings_changed.emit()

    def set_offset_external(self, offset_s):
        """Update offset spinbox without firing _on_offset (used by plot drag)."""
        self._offset_spin.blockSignals(True)
        self._offset_spin.setValue(offset_s)
        self._offset_spin.blockSignals(False)

    def _on_runstop(self, checked):
        # Keep poll_timer running regardless — it drains the DAQ queue. The
        # trigger processor's run_stop flag controls whether new frames are
        # emitted; stopping the timer would let the queue grow unbounded.
        if checked and self._daq.trigger.settings["trigger_type"] == "single":
            self._daq.clear_buffers()
        self._running = checked
        self._runstop_btn.setText("▶ RUN" if checked else "■ STOP")
        self._daq.trigger.set_run_stop(checked)
        if checked and not self._poll_timer.isActive():
            self._poll_timer.start()

    def _on_single(self):
        """One-shot: switch to single mode, drop stale samples, arm."""
        self._mode_combo.blockSignals(True)
        self._mode_combo.setCurrentIndex(TRIGGER_TYPE.index("single"))
        self._mode_combo.blockSignals(False)
        self._daq.trigger.set_trigger_type("single")
        self._daq.clear_buffers()
        self._daq.trigger.set_run_stop(True)
        self._running = True
        self._runstop_btn.blockSignals(True)
        self._runstop_btn.setChecked(True)
        self._runstop_btn.setText("▶ RUN")
        self._runstop_btn.blockSignals(False)
        if not self._poll_timer.isActive():
            self._poll_timer.start()
        self.trigger_settings_changed.emit()

    def on_poll_tick(self):
        """Detect single-capture completion — trigger processor auto-clears run_stop."""
        if self._daq.trigger.settings["trigger_type"] == "single" \
                and self._running and not self._daq.trigger.run_stop:
            self._running = False
            self._runstop_btn.blockSignals(True)
            self._runstop_btn.setChecked(False)
            self._runstop_btn.setText("■ STOP")
            self._runstop_btn.blockSignals(False)
