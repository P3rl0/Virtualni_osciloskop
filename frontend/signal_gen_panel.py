import math

from PyQt5.QtWidgets import (
    QGroupBox, QGridLayout, QHBoxLayout, QVBoxLayout,
    QComboBox, QDoubleSpinBox, QLabel, QPushButton, QSpinBox,
)
from backend.config import (
    SIGGEN_WAVEFORMS, SIGGEN_FREQ_MAX, SIGGEN_FREQ_MIN,
    SIGGEN_AMP_MIN, SIGGEN_AMP_MAX, SIGGEN_AMP_MAX_VRMS,
)

_UNIT_OPTIONS = ["Hz", "kHz", "MHz"]
_UNIT_MULT    = [1.0, 1e3, 1e6]
_LOAD_LABELS  = ["Hi-Z (INF)", "50 Ω"]
_LOAD_VALUES  = ["INF", "50"]
_AMP_UNIT_LABELS = ["Vpp", "Vrms"]
_AMP_UNIT_VALUES = ["VPP", "VRMS"]

# Vpp / Vrms ratio per waveform — used to convert the displayed amplitude when
# the unit toggle flips, so the physical output level stays the same.
# (Assumes 50% duty for SQU; close enough for the toggle UX.)
_VPP_OVER_VRMS = {
    "SIN":  2.0 * math.sqrt(2.0),   # ≈ 2.828
    "SQU":  2.0,
    "TRI":  2.0 * math.sqrt(3.0),   # ≈ 3.464
    "RAMP": 2.0 * math.sqrt(3.0),
}


class SignalGenPanel(QGroupBox):
    def __init__(self, signal_gen_worker, parent=None):
        super().__init__("Signal Generator", parent)
        self._sg = signal_gen_worker
        self._connected = False

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(6, 14, 6, 6)

        # Connect row
        conn_row = QHBoxLayout()
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setCheckable(True)
        self._connect_btn.setStyleSheet(
            "QPushButton:checked { background-color: #2a7a2a; color: white; font-weight: bold; }"
            "QPushButton:!checked { background-color: #555; }"
        )
        conn_row.addWidget(self._connect_btn, stretch=1)

        conn_row.addWidget(QLabel("GPIB:"))
        self._gpib_spin = QSpinBox()
        self._gpib_spin.setRange(0, 30)
        self._gpib_spin.setValue(self._sg.settings.get("gpib_address", 10))
        self._gpib_spin.setFixedWidth(50)
        conn_row.addWidget(self._gpib_spin)
        layout.addLayout(conn_row)

        # Settings grid
        grid = QGridLayout()
        grid.setSpacing(4)

        grid.addWidget(QLabel("Waveform"), 0, 0)
        self._wave_combo = QComboBox()
        self._wave_combo.addItems(SIGGEN_WAVEFORMS)
        grid.addWidget(self._wave_combo, 0, 1, 1, 2)

        grid.addWidget(QLabel("Frequency"), 1, 0)
        self._freq_spin = QDoubleSpinBox()
        self._freq_spin.setDecimals(3)
        self._freq_spin.setValue(1.0)
        grid.addWidget(self._freq_spin, 1, 1)
        self._freq_unit = QComboBox()
        self._freq_unit.addItems(_UNIT_OPTIONS)
        self._freq_unit.setFixedWidth(55)
        grid.addWidget(self._freq_unit, 1, 2)
        # Spinbox range depends on the selected unit so that
        # (value × multiplier) can never exceed hardware limits.
        self._apply_freq_range()

        grid.addWidget(QLabel("Amplitude"), 2, 0)
        self._amp_spin = QDoubleSpinBox()
        self._amp_spin.setSingleStep(0.01)
        self._amp_spin.setDecimals(3)
        grid.addWidget(self._amp_spin, 2, 1)
        self._amp_unit_combo = QComboBox()
        self._amp_unit_combo.addItems(_AMP_UNIT_LABELS)
        self._amp_unit_combo.setFixedWidth(55)
        grid.addWidget(self._amp_unit_combo, 2, 2)
        # Initial range/suffix; _load_from_backend resets these to match the
        # stored amplitude_unit, but we set defaults here so the widget is
        # valid before _load_from_backend runs.
        self._apply_amp_range("VPP")

        grid.addWidget(QLabel("Offset"), 3, 0)
        self._offset_spin = QDoubleSpinBox()
        self._offset_spin.setRange(-5.0, 5.0)
        self._offset_spin.setSingleStep(0.01)
        self._offset_spin.setDecimals(3)
        self._offset_spin.setSuffix(" V")
        grid.addWidget(self._offset_spin, 3, 1, 1, 2)

        grid.addWidget(QLabel("Load"), 4, 0)
        self._load_combo = QComboBox()
        self._load_combo.addItems(_LOAD_LABELS)
        grid.addWidget(self._load_combo, 4, 1, 1, 2)

        self._duty_label = QLabel("Duty")
        self._duty_spin = QDoubleSpinBox()
        self._duty_spin.setRange(20.0, 80.0)
        self._duty_spin.setSingleStep(1.0)
        self._duty_spin.setDecimals(1)
        self._duty_spin.setSuffix(" %")
        grid.addWidget(self._duty_label, 5, 0)
        grid.addWidget(self._duty_spin, 5, 1, 1, 2)

        layout.addLayout(grid)

        # Output button
        self._output_btn = QPushButton("OUTPUT OFF")
        self._output_btn.setCheckable(True)
        self._output_btn.setStyleSheet(
            "QPushButton:checked { background-color: #cc4400; color: white; font-weight: bold; }"
            "QPushButton:!checked { background-color: #444; }"
        )
        layout.addWidget(self._output_btn)

        # Initialise from YAML defaults
        self._load_from_backend()

        # Disable controls until connected
        self._set_controls_enabled(False)

        # Connect signals
        self._connect_btn.clicked.connect(self._on_connect_toggle)
        self._gpib_spin.valueChanged.connect(lambda v: self._sg.set_gpib_address(v))
        self._wave_combo.currentIndexChanged.connect(self._on_waveform)
        self._freq_spin.valueChanged.connect(self._on_frequency)
        self._freq_unit.currentIndexChanged.connect(self._on_frequency)
        self._amp_spin.valueChanged.connect(lambda v: self._sg.set_amplitude(v))
        self._amp_unit_combo.currentIndexChanged.connect(self._on_amp_unit)
        self._offset_spin.valueChanged.connect(lambda v: self._sg.set_offset(v))
        self._load_combo.currentIndexChanged.connect(lambda i: self._sg.set_load(_LOAD_VALUES[i]))
        self._duty_spin.valueChanged.connect(lambda v: self._sg.set_duty_cycle(v))
        self._output_btn.clicked.connect(self._on_output)

        # Wire backend signal
        self._sg.connection_changed.connect(self._on_connection_changed)

    # ── Init ─────────────────────────────────────────────────────────────

    def _load_from_backend(self):
        s = self._sg.settings
        self._block(True)

        wave = s.get("waveform", "SIN")
        if wave in SIGGEN_WAVEFORMS:
            self._wave_combo.setCurrentIndex(SIGGEN_WAVEFORMS.index(wave))

        freq_hz = s.get("frequency", 1000.0)
        if freq_hz >= 1e6:
            self._freq_unit.setCurrentIndex(2)
            self._apply_freq_range()
            self._freq_spin.setValue(freq_hz / 1e6)
        elif freq_hz >= 1e3:
            self._freq_unit.setCurrentIndex(1)
            self._apply_freq_range()
            self._freq_spin.setValue(freq_hz / 1e3)
        else:
            self._freq_unit.setCurrentIndex(0)
            self._apply_freq_range()
            self._freq_spin.setValue(freq_hz)

        amp_unit = s.get("amplitude_unit", "VPP")
        if amp_unit not in _AMP_UNIT_VALUES:
            amp_unit = "VPP"
        self._amp_unit_combo.setCurrentIndex(_AMP_UNIT_VALUES.index(amp_unit))
        self._apply_amp_range(amp_unit)
        self._amp_spin.setValue(s.get("amplitude", 1.0))
        self._offset_spin.setValue(s.get("offset", 0.0))

        load = s.get("load", "INF")
        load_idx = _LOAD_VALUES.index(load) if load in _LOAD_VALUES else 0
        self._load_combo.setCurrentIndex(load_idx)

        self._duty_spin.setValue(s.get("duty_cycle", 50.0))
        self._update_duty_visibility(wave)

        self._output_btn.setChecked(s.get("output_enabled", False))
        self._output_btn.setText("OUTPUT ON" if s.get("output_enabled") else "OUTPUT OFF")

        self._block(False)

    def _block(self, state: bool):
        for w in (self._wave_combo, self._freq_spin, self._freq_unit,
                  self._amp_spin, self._amp_unit_combo, self._offset_spin,
                  self._load_combo, self._duty_spin, self._output_btn):
            w.blockSignals(state)

    def _update_duty_visibility(self, waveform: str):
        visible = (waveform == "SQU")
        self._duty_label.setVisible(visible)
        self._duty_spin.setVisible(visible)

    def _set_controls_enabled(self, enabled: bool):
        for w in (self._wave_combo, self._freq_spin, self._freq_unit,
                  self._amp_spin, self._amp_unit_combo, self._offset_spin,
                  self._load_combo, self._duty_spin, self._output_btn):
            w.setEnabled(enabled)

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_connect_toggle(self, checked: bool):
        if checked:
            self._sg.set_gpib_address(self._gpib_spin.value())
            self._sg.connect_device()
            self._sg.apply_settings()
        else:
            self._sg.disconnect_device()

    def _on_connection_changed(self, connected: bool):
        self._connected = connected
        self._connect_btn.blockSignals(True)
        self._connect_btn.setChecked(connected)
        self._connect_btn.setText("Disconnect" if connected else "Connect")
        self._connect_btn.blockSignals(False)
        self._set_controls_enabled(connected)

    def _on_waveform(self, index):
        waveform = SIGGEN_WAVEFORMS[index]
        self._sg.set_waveform(waveform)
        self._update_duty_visibility(waveform)

    def _on_frequency(self):
        # The unit combo also fires this slot; reapply spin range so the
        # max displayable value tracks the selected unit before reading.
        self._apply_freq_range()
        mult = _UNIT_MULT[self._freq_unit.currentIndex()]
        freq_hz = self._freq_spin.value() * mult
        self._sg.set_frequency(freq_hz)

    def _apply_freq_range(self):
        """Pin the freq spinbox min/max so value × multiplier stays inside
        [SIGGEN_FREQ_MIN, SIGGEN_FREQ_MAX]. Called when the unit changes."""
        mult = _UNIT_MULT[self._freq_unit.currentIndex()]
        lo = max(SIGGEN_FREQ_MIN / mult, 1e-6)
        hi = SIGGEN_FREQ_MAX / mult
        self._freq_spin.blockSignals(True)
        self._freq_spin.setRange(lo, hi)
        self._freq_spin.blockSignals(False)

    def _on_output(self, checked: bool):
        self._output_btn.setText("OUTPUT ON" if checked else "OUTPUT OFF")
        self._sg.set_output(checked)

    def _apply_amp_range(self, unit: str):
        """Set the amplitude spinbox suffix and range to match the unit."""
        self._amp_spin.blockSignals(True)
        if unit == "VRMS":
            self._amp_spin.setRange(0.001, SIGGEN_AMP_MAX_VRMS)
            self._amp_spin.setSuffix(" Vrms")
        else:
            self._amp_spin.setRange(SIGGEN_AMP_MIN, SIGGEN_AMP_MAX)
            self._amp_spin.setSuffix(" Vpp")
        self._amp_spin.blockSignals(False)

    def _on_amp_unit(self, index: int):
        new_unit = _AMP_UNIT_VALUES[index]
        old_unit = self._sg.settings.get("amplitude_unit", "VPP")
        if new_unit == old_unit:
            return
        # Convert the displayed value so the physical output level is preserved.
        waveform = self._sg.settings.get("waveform", "SIN")
        ratio = _VPP_OVER_VRMS.get(waveform, _VPP_OVER_VRMS["SIN"])
        old_value = self._amp_spin.value()
        if old_unit == "VPP" and new_unit == "VRMS":
            new_value = old_value / ratio
        elif old_unit == "VRMS" and new_unit == "VPP":
            new_value = old_value * ratio
        else:
            new_value = old_value
        # Order matters: tell the instrument the new unit first so the
        # following VOLT command is interpreted in the new unit.
        self._sg.set_amplitude_unit(new_unit)
        self._apply_amp_range(new_unit)
        self._amp_spin.blockSignals(True)
        self._amp_spin.setValue(new_value)
        self._amp_spin.blockSignals(False)
        # Push the converted value (clamped to the new range by the spinbox).
        self._sg.set_amplitude(self._amp_spin.value())
