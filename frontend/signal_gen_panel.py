"""Signal-generator control panel.

This panel talks to ``BackendController`` only. It does not interact with DAQ
acquisition and keeps the signal-generator backend service separate.
"""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QPushButton,
)

from frontend.backend_controller import BackendController
from frontend.styles import dim_label

try:
    from backend.config import (
        SIGGEN_AMP_MAX,
        SIGGEN_AMP_MIN,
        SIGGEN_DUTY_MAX,
        SIGGEN_DUTY_MIN,
        SIGGEN_FREQ_MAX,
        SIGGEN_FREQ_MIN,
        SIGGEN_LOAD,
        SIGGEN_OFFSET_MAX,
        SIGGEN_WAVEFORMS,
    )
except Exception:  # noqa: BLE001 - allow frontend simulation without backend imports
    SIGGEN_WAVEFORMS = ["SIN", "SQU", "TRI", "RAMP"]
    SIGGEN_LOAD = ["INF", "50"]
    SIGGEN_FREQ_MIN = 100e-6
    SIGGEN_FREQ_MAX = 15e6
    SIGGEN_AMP_MIN = 0.01
    SIGGEN_AMP_MAX = 20.0
    SIGGEN_OFFSET_MAX = 5.0
    SIGGEN_DUTY_MIN = 20.0
    SIGGEN_DUTY_MAX = 80.0


class SignalGenPanel(QGroupBox):
    def __init__(self, backend: BackendController, parent=None):
        super().__init__("SIGNAL GENERATOR", parent)
        self.backend = backend
        self.connected = False

        grid = QGridLayout(self)
        grid.setSpacing(6)
        grid.setContentsMargins(8, 6, 8, 8)

        self.connect_btn = QPushButton("CONNECT")
        self.connect_btn.setCheckable(True)
        grid.addWidget(self.connect_btn, 0, 0, 1, 2)

        self.output_cb = QCheckBox("OUTPUT")
        grid.addWidget(self.output_cb, 0, 2, 1, 2)

        grid.addWidget(dim_label("WAVE"), 1, 0)
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(SIGGEN_WAVEFORMS)
        grid.addWidget(self.waveform_combo, 1, 1, 1, 3)

        grid.addWidget(dim_label("FREQ"), 2, 0)
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(float(SIGGEN_FREQ_MIN), float(SIGGEN_FREQ_MAX))
        self.freq_spin.setDecimals(3)
        self.freq_spin.setSingleStep(100.0)
        self.freq_spin.setValue(1000.0)
        self.freq_spin.setSuffix(" Hz")
        grid.addWidget(self.freq_spin, 2, 1, 1, 3)

        grid.addWidget(dim_label("AMPL"), 3, 0)
        self.ampl_spin = QDoubleSpinBox()
        self.ampl_spin.setRange(float(SIGGEN_AMP_MIN), float(SIGGEN_AMP_MAX))
        self.ampl_spin.setDecimals(3)
        self.ampl_spin.setSingleStep(0.1)
        self.ampl_spin.setValue(1.0)
        self.ampl_spin.setSuffix(" Vpp")
        grid.addWidget(self.ampl_spin, 3, 1, 1, 3)

        grid.addWidget(dim_label("OFFSET"), 4, 0)
        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-float(SIGGEN_OFFSET_MAX), float(SIGGEN_OFFSET_MAX))
        self.offset_spin.setDecimals(3)
        self.offset_spin.setSingleStep(0.1)
        self.offset_spin.setValue(0.0)
        self.offset_spin.setSuffix(" V")
        grid.addWidget(self.offset_spin, 4, 1, 1, 3)

        grid.addWidget(dim_label("LOAD"), 5, 0)
        self.load_combo = QComboBox()
        self.load_combo.addItems(SIGGEN_LOAD)
        grid.addWidget(self.load_combo, 5, 1)

        grid.addWidget(dim_label("DUTY"), 5, 2)
        self.duty_spin = QDoubleSpinBox()
        self.duty_spin.setRange(float(SIGGEN_DUTY_MIN), float(SIGGEN_DUTY_MAX))
        self.duty_spin.setDecimals(1)
        self.duty_spin.setSingleStep(1.0)
        self.duty_spin.setValue(50.0)
        self.duty_spin.setSuffix(" %")
        grid.addWidget(self.duty_spin, 5, 3)

        self.connect_btn.toggled.connect(self._toggle_connection)
        self.output_cb.toggled.connect(self.backend.set_signal_generator_output)
        self.waveform_combo.currentTextChanged.connect(self.backend.set_signal_generator_waveform)
        self.freq_spin.valueChanged.connect(self.backend.set_signal_generator_frequency)
        self.ampl_spin.valueChanged.connect(self.backend.set_signal_generator_amplitude)
        self.offset_spin.valueChanged.connect(self.backend.set_signal_generator_offset)
        self.load_combo.currentTextChanged.connect(self.backend.set_signal_generator_load)
        self.duty_spin.valueChanged.connect(self.backend.set_signal_generator_duty_cycle)

        self.backend.signal_gen_connection_changed.connect(self._on_connection_changed)

    def _toggle_connection(self, checked: bool) -> None:
        if checked:
            self.backend.connect_signal_generator()
        else:
            self.backend.disconnect_signal_generator()

    def _on_connection_changed(self, connected: bool) -> None:
        self.connected = connected
        self.connect_btn.blockSignals(True)
        self.connect_btn.setChecked(connected)
        self.connect_btn.setText("DISCONNECT" if connected else "CONNECT")
        self.connect_btn.blockSignals(False)
