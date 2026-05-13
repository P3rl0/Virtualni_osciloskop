from PyQt5.QtWidgets import (
    QGroupBox, QGridLayout, QHBoxLayout, QVBoxLayout,
    QComboBox, QDoubleSpinBox, QLabel, QPushButton,
)
from backend.config import TRIGGER_TYPE, TRIGG_SLOPE


class TriggerPanel(QGroupBox):
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
        self._single_armed = False

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

        # Offset
        grid.addWidget(QLabel("Offset"), 2, 0)
        self._offset_spin = QDoubleSpinBox()
        self._offset_spin.setRange(-10.0, 10.0)
        self._offset_spin.setSingleStep(0.001)
        self._offset_spin.setDecimals(4)
        self._offset_spin.setSuffix(" s")
        grid.addWidget(self._offset_spin, 2, 1)

        layout.addLayout(grid)

        # Run/Stop + Single buttons
        btn_row = QHBoxLayout()
        self._runstop_btn = QPushButton("■ STOP")
        self._runstop_btn.setCheckable(True)
        self._runstop_btn.setChecked(True)
        self._runstop_btn.setStyleSheet(
            "QPushButton:checked { background-color: #2a7a2a; color: white; font-weight: bold; }"
            "QPushButton:!checked { background-color: #7a2a2a; color: white; font-weight: bold; }"
        )
        btn_row.addWidget(self._runstop_btn, stretch=1)

        self._single_btn = QPushButton("◉ SINGLE")
        btn_row.addWidget(self._single_btn, stretch=1)
        layout.addLayout(btn_row)

        # Initialise from backend
        self._load_from_backend()

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
        self._daq.trigger.set_trigger_channel(index)

    def _on_slope(self, checked):
        falling = checked
        self._slope_btn.setText("↓ Falling" if falling else "↑ Rising")
        self._daq.trigger.set_trigger_slope("falling" if falling else "rising")

    def _on_level(self, value):
        self._daq.trigger.set_trigger_level(value)

    def _on_mode(self, index):
        self._daq.trigger.set_trigger_type(TRIGGER_TYPE[index])

    def _on_offset(self, value):
        self._daq.trigger.set_trigger_offset(value)

    def _on_runstop(self, checked):
        self._running = checked
        self._runstop_btn.setText("▶ RUN" if checked else "■ STOP")
        self._daq.trigger.set_run_stop(checked)
        if checked:
            if not self._poll_timer.isActive():
                self._poll_timer.start()
        else:
            self._poll_timer.stop()

    def _on_single(self):
        self._single_armed = True
        self._daq.trigger.set_trigger_type("single")
        self._mode_combo.blockSignals(True)
        self._mode_combo.setCurrentIndex(TRIGGER_TYPE.index("single"))
        self._mode_combo.blockSignals(False)
        self._daq.trigger.set_run_stop(True)
        if not self._poll_timer.isActive():
            self._poll_timer.start()
        self._running = True
        self._runstop_btn.blockSignals(True)
        self._runstop_btn.setChecked(True)
        self._runstop_btn.setText("▶ RUN")
        self._runstop_btn.blockSignals(False)

    def on_poll_tick(self):
        """Called every timer tick by main_window to detect single-capture completion."""
        if self._single_armed and not self._daq.trigger.run_stop:
            self._single_armed = False
            self._poll_timer.stop()
            self._running = False
            self._runstop_btn.blockSignals(True)
            self._runstop_btn.setChecked(False)
            self._runstop_btn.setText("■ STOP")
            self._runstop_btn.blockSignals(False)
