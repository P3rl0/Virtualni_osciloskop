"""Frontend controls for oscilloscope acquisition and display settings."""

from __future__ import annotations

from collections.abc import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDial,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from frontend.formatting import parse_scale
from frontend.styles import BG_PANEL, CH_COLORS, TEXT_MED, dim_label, make_sep

try:
    from backend.control_adapter import supported_timebase_labels, supported_volts_per_div_labels
except Exception:  # noqa: BLE001 - keep simulation UI usable without backend dependencies
    def supported_timebase_labels() -> list[str]:
        return [
            "100 µs/div", "200 µs/div", "500 µs/div",
            "1 ms/div", "2 ms/div", "5 ms/div",
            "10 ms/div", "20 ms/div", "50 ms/div",
            "100 ms/div", "200 ms/div", "500 ms/div",
            "1 s/div", "5 s/div",
        ]

    def supported_volts_per_div_labels() -> list[str]:
        return [
            "100 µV/div", "200 µV/div", "500 µV/div",
            "1 mV/div", "2 mV/div", "5 mV/div",
            "10 mV/div", "20 mV/div", "50 mV/div",
            "100 mV/div", "200 mV/div", "500 mV/div",
            "1 V/div", "2 V/div", "5 V/div",
        ]


COUPLING_OPTIONS = ["DC", "AC"]
DEFAULT_VDIV = {1: "1 V/div", 2: "500 mV/div", 3: "2 V/div", 4: "200 mV/div"}
SIGNAL_LABELS = {
    1: "simulation / DAQ",
    2: "simulation / DAQ",
    3: "simulation / DAQ",
    4: "simulation / DAQ",
}
SIMULATION_PROFILES = ["SINE", "SQUARE", "TRIANGLE", "RAMP", "NOISE", "PULSE"]
MEASUREMENT_LABEL_TO_BACKEND = {
    "Mean": "mean",
    "Vpp": "peak_to_peak",
    "Vrms": "rms",
    "Freq": "frequency",
    "Rise": "rise_time",
    "Fall": "fall_time",
}


class ChannelGroup(QGroupBox):
    """Controls for one oscilloscope channel.

    Channel numbers are frontend-facing and therefore 1-based.
    """

    def __init__(self, ch: int, on_change_cb: Callable[[], None], parent: QWidget | None = None):
        super().__init__(f"CH{ch}  ·  {SIGNAL_LABELS[ch]}", parent)
        self.ch = ch
        self.color = CH_COLORS[ch]
        self._cb = on_change_cb

        self.setStyleSheet(
            f"""
            QGroupBox {{
                border-color: {self.color}28;
                background-color: {BG_PANEL};
            }}
            QGroupBox::title {{ color: {self.color}cc; }}
            """
        )

        grid = QGridLayout(self)
        grid.setSpacing(6)
        grid.setContentsMargins(8, 6, 8, 8)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)

        self.enable_cb = QCheckBox(f"CH{ch}")
        self.enable_cb.setObjectName(f"ch{ch}")
        self.enable_cb.setChecked(ch == 1)
        grid.addWidget(self.enable_cb, 0, 0, 1, 2)

        grid.addWidget(dim_label("COUPLING"), 0, 2)
        self.coupling = QComboBox()
        self.coupling.addItems(COUPLING_OPTIONS)
        grid.addWidget(self.coupling, 0, 3)

        grid.addWidget(dim_label("V / DIV"), 1, 0)
        self.vdiv_combo = QComboBox()
        self.vdiv_combo.addItems(supported_volts_per_div_labels())
        self.vdiv_combo.setCurrentText(DEFAULT_VDIV[ch])
        grid.addWidget(self.vdiv_combo, 1, 1, 1, 3)

        grid.addWidget(dim_label("OFFSET"), 2, 0)
        self.offset_spin = QDoubleSpinBox()
        self.offset_spin.setRange(-5.0, 5.0)
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

    def vdiv_label(self) -> str:
        return self.vdiv_combo.currentText()

    def set_vdiv_label(self, label: str, emit_change: bool = True) -> None:
        self.vdiv_combo.blockSignals(not emit_change)
        self.vdiv_combo.setCurrentText(label)
        self.vdiv_combo.blockSignals(False)

    def vdiv_si(self) -> float:
        return parse_scale(self.vdiv_label())

    def offset_div(self) -> float:
        return float(self.offset_spin.value())

    def coupling_str(self) -> str:
        return self.coupling.currentText()


class TriggerGroup(QGroupBox):
    def __init__(
        self,
        on_change_cb: Callable[[], None],
        runstop_cb: Callable[[bool], None],
        single_cb: Callable[[], None],
        parent: QWidget | None = None,
    ):
        super().__init__("TRIGGER")
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
        self.trigger_dial.setValue(1)
        self.trigger_dial.setFixedSize(78, 78)
        mid.addWidget(self.trigger_dial, 1, 0, 2, 1, alignment=Qt.AlignCenter)

        right_col = QVBoxLayout()
        right_col.addWidget(dim_label("LEVEL"))
        self.level_readout = QLabel("0.10 V")
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
        self._refresh_state_style()

    def _toggle_edge_mode(self) -> None:
        self.edge_btn.setText("EDGE ↑" if self.is_rising_edge() else "EDGE ↓")
        self.mode_readout.setText("EDGE  ·  RISING" if self.is_rising_edge() else "EDGE  ·  FALLING")
        self._change_cb()

    def _on_level_changed(self) -> None:
        self.level_readout.setText(f"{self.level_volts():.2f} V")
        self._change_cb()

    def source_channel(self) -> int:
        return int(self.source_combo.currentText().replace("CH", ""))

    def source_label(self) -> str:
        return self.source_combo.currentText()

    def level_volts(self) -> float:
        return float(self.trigger_dial.value()) / 10.0

    def set_level_volts(self, level_v: float, emit_change: bool = True) -> None:
        dial_value = max(self.trigger_dial.minimum(), min(self.trigger_dial.maximum(), int(round(level_v * 10))))
        self.trigger_dial.blockSignals(not emit_change)
        self.trigger_dial.setValue(dial_value)
        self.level_readout.setText(f"{self.level_volts():.2f} V")
        self.trigger_dial.blockSignals(False)

    def is_rising_edge(self) -> bool:
        return self.edge_btn.isChecked()

    def set_running(self, running: bool) -> None:
        self.run_btn.blockSignals(True)
        self.run_btn.setChecked(running)
        self.run_btn.setText("RUN" if running else "STOP")
        self.run_btn.setObjectName("run_btn" if running else "stop_btn")
        self.run_btn.style().unpolish(self.run_btn)
        self.run_btn.style().polish(self.run_btn)
        self.state_badge.setText("ARMED" if running else "STOPPED")
        self._refresh_state_style()
        self.run_btn.blockSignals(False)

    def set_single_fired(self) -> None:
        self.state_badge.setText("SINGLE")
        self._refresh_state_style()

    def _refresh_state_style(self) -> None:
        text = self.state_badge.text()
        if text == "ARMED":
            self.state_badge.setStyleSheet("color: #8ef0b8;")
        elif text == "STOPPED":
            self.state_badge.setStyleSheet("color: #ff9a9a;")
        else:
            self.state_badge.setStyleSheet("color: #ffd166;")


class ControlPanel(QWidget):
    def __init__(
        self,
        on_change_cb: Callable[[], None],
        runstop_cb: Callable[[bool], None],
        single_cb: Callable[[], None],
        autoset_cb: Callable[[], None],
        settings_cb: Callable[[], None],
        parent: QWidget | None = None,
    ):
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

        mode_grp = QGroupBox("DATA SOURCE")
        mode_layout = QGridLayout(mode_grp)
        mode_layout.setSpacing(6)
        mode_layout.addWidget(dim_label("MODE"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["SIMULATION", "DAQ"])
        mode_layout.addWidget(self.mode_combo, 0, 1, 1, 2)
        mode_layout.addWidget(dim_label("SIM"), 1, 0)
        self.sim_profile_combo = QComboBox()
        self.sim_profile_combo.addItems(SIMULATION_PROFILES)
        mode_layout.addWidget(self.sim_profile_combo, 1, 1, 1, 2)
        self.autoset_btn = QPushButton("AUTOSET")
        self.settings_btn = QPushButton("SETTINGS")
        mode_layout.addWidget(self.autoset_btn, 2, 0, 1, 1)
        mode_layout.addWidget(self.settings_btn, 2, 1, 1, 2)
        self.mode_combo.currentTextChanged.connect(lambda _: self._cb())
        self.sim_profile_combo.currentTextChanged.connect(lambda _: self._cb())
        self.autoset_btn.clicked.connect(autoset_cb)
        self.settings_btn.clicked.connect(settings_cb)
        root.addWidget(mode_grp)

        self.trigger_group = TriggerGroup(
            on_change_cb=self._cb,
            runstop_cb=runstop_cb,
            single_cb=single_cb,
        )
        root.addWidget(self.trigger_group)

        grp_h = QGroupBox("HORIZONTAL")
        vb_h = QVBoxLayout(grp_h)
        vb_h.setSpacing(6)
        vb_h.addWidget(dim_label("TIME / DIV"))
        self.time_combo = QComboBox()
        self.time_combo.addItems(supported_timebase_labels())
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
            group = ChannelGroup(ch, on_change_cb=self._cb)
            self.ch_groups[ch] = group
            root.addWidget(group)

        root.addWidget(make_sep())

        meas_grp = QGroupBox("MEASUREMENT SELECT")
        meas_grid = QGridLayout(meas_grp)
        meas_grid.setSpacing(4)
        self.measurement_checks: dict[str, QCheckBox] = {}
        defaults = {"Vpp", "Vrms", "Freq"}
        for i, label in enumerate(MEASUREMENT_LABEL_TO_BACKEND):
            cb = QCheckBox(label)
            cb.setChecked(label in defaults)
            cb.toggled.connect(lambda _: self._cb())
            self.measurement_checks[label] = cb
            meas_grid.addWidget(cb, i // 3, i % 3)
        root.addWidget(meas_grp)

        root.addWidget(make_sep())

        status_grp = QGroupBox("STATUS")
        status_layout = QVBoxLayout(status_grp)
        status_layout.setSpacing(5)
        self.status_rows: dict[str, QLabel] = {}
        self._srow(status_layout, "MODE", "SIMULATION")
        self._srow(status_layout, "SAMPLE RATE", "---")
        self._srow(status_layout, "BACKEND", "IDLE")
        root.addWidget(status_grp)
        root.addStretch()

    def _srow(self, layout: QVBoxLayout, key: str, val: str) -> None:
        row = QHBoxLayout()
        key_label = QLabel(key)
        key_label.setObjectName("dim")
        value_label = QLabel(val)
        value_label.setObjectName("dim")
        value_label.setStyleSheet(f"color: {TEXT_MED}; letter-spacing: 0px;")
        value_label.setAlignment(Qt.AlignRight)
        row.addWidget(key_label)
        row.addStretch()
        row.addWidget(value_label)
        layout.addLayout(row)
        self.status_rows[key] = value_label

    def set_status(self, key: str, value: str) -> None:
        if key in self.status_rows:
            self.status_rows[key].setText(value)

    def data_mode_label(self) -> str:
        return self.mode_combo.currentText()

    def set_data_mode_label(self, label: str) -> None:
        """Set the data source without recursively triggering the change callback."""
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentText(label)
        self.mode_combo.blockSignals(False)

    def simulation_profile(self) -> str:
        return self.sim_profile_combo.currentText()

    def selected_measurement_backend_names(self) -> set[str]:
        return {
            MEASUREMENT_LABEL_TO_BACKEND[label]
            for label, checkbox in self.measurement_checks.items()
            if checkbox.isChecked()
        }

    def selected_measurement_labels(self) -> set[str]:
        labels = {label for label, checkbox in self.measurement_checks.items() if checkbox.isChecked()}
        if "Freq" in labels:
            labels.add("Period")
        return labels

    def time_label(self) -> str:
        return self.time_combo.currentText()

    def set_time_label(self, label: str, emit_change: bool = True) -> None:
        self.time_combo.blockSignals(not emit_change)
        self.time_combo.setCurrentText(label)
        self.time_readout.setText(self.time_combo.currentText())
        self.time_combo.blockSignals(False)

    def time_per_div(self) -> float:
        return parse_scale(self.time_label())

    def set_channel_vdiv_label(self, ch: int, label: str, emit_change: bool = True) -> None:
        self.ch(ch).set_vdiv_label(label, emit_change=emit_change)

    def set_trigger_level_volts(self, level_v: float, emit_change: bool = True) -> None:
        self.trigger_group.set_level_volts(level_v, emit_change=emit_change)

    def ch(self, n: int) -> ChannelGroup:
        return self.ch_groups[n]

    def trigger(self) -> TriggerGroup:
        return self.trigger_group
