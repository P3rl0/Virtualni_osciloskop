import math

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QGroupBox, QGridLayout, QHBoxLayout, QVBoxLayout,
    QCheckBox, QComboBox, QDoubleSpinBox, QLabel, QLineEdit, QPushButton, QWidget,
)
from nidaqmx.constants import Coupling, TerminalConfiguration
from backend.config import NUM_VERTICAL_DIVS, VOLTS_PER_DIV


def _decimals_for_step(step: float) -> int:
    if step <= 0 or not math.isfinite(step):
        return 4
    return max(1, min(6, -int(math.floor(math.log10(step))) + 1))


def _fmt_vdiv(v):
    if v < 1e-3:
        return f"{v * 1e6:.0f} µV/div"
    if v < 1.0:
        return f"{v * 1e3:.4g} mV/div"
    return f"{v:.4g} V/div"


_COUPLING_OPTIONS   = ["DC", "AC"]
_PROBE_OPTIONS      = ["1×", "10×"]
_PROBE_VALUES       = [1.0, 10.0]
_TERMINAL_OPTIONS   = ["RSE", "NRSE", "DIFF", "PSEUDO_DIFF"]
_TERM_TO_STR = {
    TerminalConfiguration.RSE:         "RSE",
    TerminalConfiguration.NRSE:        "NRSE",
    TerminalConfiguration.DIFF:        "DIFF",
    TerminalConfiguration.PSEUDO_DIFF: "PSEUDO_DIFF",
}


class ChannelPanel(QGroupBox):
    # Emitted whenever the user mutates something that affects the plot
    # overlay (V/div, vertical offset, probe attenuation, enable, terminal,
    # coupling). main_window uses this to call _refresh_overlay so the zero
    # arrow and trigger-level line don't wait for the next frame.
    channel_settings_changed = pyqtSignal()

    def __init__(self, channel_index: int, color: str, daq_worker, parent=None):
        super().__init__(parent)
        self._idx = channel_index
        self._daq = daq_worker
        self._color = color
        self._expanded = False

        self.setTitle(f"CH{channel_index + 1}")
        self.setStyleSheet(
            f"QGroupBox::title {{ color: {color}; font-weight: bold; }}"
        )

        outer = QVBoxLayout(self)
        outer.setSpacing(4)
        outer.setContentsMargins(6, 14, 6, 6)

        # ── Header row ──────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(4)

        self._enable_cb = QCheckBox("ON")
        self._enable_cb.setStyleSheet(f"color: {color};")
        header.addWidget(self._enable_cb)

        self._vdiv_combo = QComboBox()
        for v in VOLTS_PER_DIV:
            self._vdiv_combo.addItem(_fmt_vdiv(v), v)
        header.addWidget(self._vdiv_combo, stretch=1)

        # Range/step retargeted by update_scales() based on the channel's V/div.
        self._offset_spin = QDoubleSpinBox()
        self._offset_spin.setSuffix(" V")
        self._offset_spin.setFixedWidth(80)
        header.addWidget(self._offset_spin)

        self._expand_btn = QPushButton("▾")
        self._expand_btn.setFixedWidth(22)
        self._expand_btn.setFlat(True)
        self._expand_btn.setToolTip("Advanced settings")
        header.addWidget(self._expand_btn)

        outer.addLayout(header)

        # ── Advanced row (hidden by default) ────────────────────────────
        self._adv_widget = QWidget()
        adv = QGridLayout(self._adv_widget)
        adv.setSpacing(4)
        adv.setContentsMargins(0, 2, 0, 2)

        adv.addWidget(QLabel("Coupling"), 0, 0)
        self._coupling_combo = QComboBox()
        self._coupling_combo.addItems(_COUPLING_OPTIONS)
        adv.addWidget(self._coupling_combo, 0, 1)

        adv.addWidget(QLabel("Probe"), 0, 2)
        self._probe_combo = QComboBox()
        self._probe_combo.addItems(_PROBE_OPTIONS)
        adv.addWidget(self._probe_combo, 0, 3)

        adv.addWidget(QLabel("Terminal"), 1, 0)
        self._terminal_combo = QComboBox()
        self._terminal_combo.addItems(_TERMINAL_OPTIONS)
        adv.addWidget(self._terminal_combo, 1, 1)

        adv.addWidget(QLabel("Name"), 1, 2)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Dev2/ai0")
        adv.addWidget(self._name_edit, 1, 3)

        self._adv_widget.setVisible(False)
        outer.addWidget(self._adv_widget)

        # ── Initialise from backend ──────────────────────────────────────
        self._load_from_backend()
        # Retarget the offset spinbox's range/step to current V/div BEFORE
        # signals are wired so the setValue() inside _load_from_backend
        # didn't trip a slot with stale range.
        self.update_scales()

        # ── Connect signals ──────────────────────────────────────────────
        self._enable_cb.stateChanged.connect(self._on_enable)
        self._vdiv_combo.currentIndexChanged.connect(self._on_vdiv)
        self._offset_spin.valueChanged.connect(self._on_offset)
        self._coupling_combo.currentIndexChanged.connect(self._on_coupling)
        self._probe_combo.currentIndexChanged.connect(self._on_probe)
        self._terminal_combo.currentIndexChanged.connect(self._on_terminal)
        self._name_edit.editingFinished.connect(self._on_name)
        self._expand_btn.clicked.connect(self._toggle_advanced)

    # ── Init helpers ────────────────────────────────────────────────────

    def _load_from_backend(self):
        ch = self._daq.channels[self._idx]

        self._block(True)

        self._enable_cb.setChecked(ch["enable"])

        vpd = ch["volts_per_div"]
        idx = min(range(len(VOLTS_PER_DIV)), key=lambda i: abs(VOLTS_PER_DIV[i] - vpd))
        self._vdiv_combo.setCurrentIndex(idx)

        # Use a permissive range while writing the value so QDoubleSpinBox
        # doesn't silently clamp (its default range is [0, 99.99] — a saved
        # negative offset would be wiped). update_scales tightens after.
        self._offset_spin.setRange(-1e9, 1e9)
        self._offset_spin.setValue(ch["vertical_offset"])

        coupling_str = "DC" if ch["coupling"] == Coupling.DC else "AC"
        self._coupling_combo.setCurrentIndex(_COUPLING_OPTIONS.index(coupling_str))

        att = ch["probe_attenuation"]
        probe_idx = _PROBE_VALUES.index(att) if att in _PROBE_VALUES else 0
        self._probe_combo.setCurrentIndex(probe_idx)

        term_str = _TERM_TO_STR.get(ch["terminal_config"], "RSE")
        self._terminal_combo.setCurrentIndex(_TERMINAL_OPTIONS.index(term_str))

        self._name_edit.setText(ch["name"])

        self._block(False)

    def _block(self, state: bool):
        for w in (self._enable_cb, self._vdiv_combo, self._offset_spin,
                  self._coupling_combo, self._probe_combo,
                  self._terminal_combo, self._name_edit):
            w.blockSignals(state)

    def _toggle_advanced(self):
        self._expanded = not self._expanded
        self._adv_widget.setVisible(self._expanded)
        self._expand_btn.setText("▴" if self._expanded else "▾")

    # ── Slots ────────────────────────────────────────────────────────────

    def _on_enable(self, state):
        self._daq.set_channel_enable(bool(state), self._idx)
        self.channel_settings_changed.emit()

    def _on_vdiv(self, index):
        self._daq.set_volts_per_div(VOLTS_PER_DIV[index], self._idx)
        # V/div changed -> retarget offset spinbox so it stays at sane
        # resolution relative to the new vertical scale.
        self.update_scales()
        self.channel_settings_changed.emit()

    def _on_offset(self, value):
        self._daq.set_vertical_offset(value, self._idx)
        self.channel_settings_changed.emit()

    def _on_coupling(self, index):
        self._daq.set_coupling(_COUPLING_OPTIONS[index], self._idx)
        self.channel_settings_changed.emit()

    def _on_probe(self, index):
        self._daq.set_attenuation(_PROBE_VALUES[index], self._idx)
        self.channel_settings_changed.emit()

    def _on_terminal(self, index):
        self._daq.set_terminal_config(_TERMINAL_OPTIONS[index], self._idx)
        self.channel_settings_changed.emit()

    def _on_name(self):
        self._daq.set_channel_name(self._name_edit.text().strip(), self._idx)
        self.channel_settings_changed.emit()

    def update_scales(self):
        """Retarget the vertical-offset spinbox's range/step/decimals to match
        the channel's current V/div. Range = ±10 divisions worth of volts;
        step = 1/100 of a division (so a single click is a tiny visible nudge).

        If setRange actually clamps the current spinbox value (because the
        new tighter range no longer accommodates it), push the clamped value
        back to the backend so the trace position matches the spinbox.
        Crucially, do NOT sync on mere mismatch — that would clobber a
        backend value that was legitimately set out-of-band (e.g. by autoset).
        """
        try:
            vdiv = max(1e-9, float(self._daq.channels[self._idx]["volts_per_div"]))
        except (KeyError, IndexError):
            vdiv = 1.0

        off_range = vdiv * NUM_VERTICAL_DIVS
        off_step  = vdiv * 0.01

        self._offset_spin.blockSignals(True)
        self._offset_spin.setDecimals(_decimals_for_step(off_step))
        pre = self._offset_spin.value()
        self._offset_spin.setRange(-off_range, off_range)
        self._offset_spin.setSingleStep(off_step)
        post = self._offset_spin.value()
        self._offset_spin.blockSignals(False)

        if pre != post:
            self._daq.set_vertical_offset(post, self._idx)

    def refresh(self):
        """Reload all widget values from the backend and retarget scales.
        Used by main_window after an autoset (or any out-of-band backend mutation)."""
        self._load_from_backend()
        self.update_scales()
