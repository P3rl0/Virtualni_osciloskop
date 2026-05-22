from PyQt5.QtCore import QObject, pyqtSignal
from pathlib import Path
from backend.config import (
    load_yaml,
    SIGGEN_WAVEFORMS,
    SIGGEN_LOAD,
    SIGGEN_FREQ_MIN,
    SIGGEN_FREQ_MAX,
    SIGGEN_AMP_MIN,
    SIGGEN_AMP_MAX,
    SIGGEN_AMP_UNITS,
    SIGGEN_AMP_MAX_VRMS,
    SIGGEN_OFFSET_MAX,
    SIGGEN_DUTY_MIN,
    SIGGEN_DUTY_MAX,
)


class SignalGenWorker(QObject):
    path = Path(__file__).parent
    error_occurred = pyqtSignal(str)  # mirrors DaqWorker pattern
    connection_changed = pyqtSignal(bool)  # True = connected, False = disconnected

    def __init__(self):
        super().__init__()
        self.settings = load_yaml(self.path / "config.yaml", area="signal_gen")
        self.rm = None  # pyvisa ResourceManager
        self.device = None  # pyvisa Resource

    def connect_device(self):
        """Open VISA resource for the 33120A at the configured GPIB address."""
        try:
            import pyvisa  # lazy import — avoids loading VISA DLLs at app startup (conflicts with NI-DAQmx)
            self.rm = pyvisa.ResourceManager()
            addr = f"GPIB::{self.settings['gpib_address']}::INSTR"
            self.device = self.rm.open_resource(addr)
            self.device.timeout = 3000  # 3 s — avoids infinite hang on bad address
            self._query("*IDN?")  # warm-up read; result currently ignored
            self.connection_changed.emit(True)
        except Exception as e:
            self.error_occurred.emit(f"VISA connect error: {e}")
            self.device = None

    def disconnect_device(self):
        if self.device is not None:
            self.device.close()
            self.device = None
        if self.rm is not None:
            self.rm.close()
            self.rm = None
        self.connection_changed.emit(False)

    def _write(self, cmd: str):
        """Send SCPI command; emit error_occurred on failure."""
        if self.device is None:
            return
        try:
            self.device.write(cmd)  # type: ignore
        except Exception as e:
            self.error_occurred.emit(f"VISA write error ({cmd!r}): {e}")

    def _query(self, cmd: str):
        """Send SCPI query; return stripped response string or None on failure."""
        if self.device is None:
            return None
        try:
            return self.device.query(cmd).strip()  # type: ignore
        except Exception as e:
            self.error_occurred.emit(f"VISA query error ({cmd!r}): {e}")
            return None

    def apply_settings(self):
        """Push all current settings to the instrument in one go.
        Call this once after connect_device() to synchronise instrument state."""
        self._write(f"FUNC {self.settings['waveform']}")
        self._write(f"FREQ {self.settings['frequency']}")
        self._write(f"VOLT:UNIT {self.settings.get('amplitude_unit', 'VPP')}")
        self._write(f"VOLT {self.settings['amplitude']}")
        self._write(f"VOLT:OFFS {self.settings['offset']}")
        self._write(f"OUTP:LOAD {self.settings['load']}")
        if self.settings["waveform"] == "SQU":
            # 33120A uses PULS:DCYC for square-wave duty cycle (the newer 33220A
            # uses FUNC:SQU:DCYC — historical naming quirk).
            self._write(f"PULS:DCYC {self.settings['duty_cycle']}")
        out = "ON" if self.settings["output_enabled"] else "OFF"
        self._write(f"OUTPUT {out}")

    def set_output(self, enabled: bool):
        self.settings["output_enabled"] = enabled
        self._write(f"OUTPUT {'ON' if enabled else 'OFF'}")

    def set_waveform(self, waveform: str):
        if waveform not in SIGGEN_WAVEFORMS:
            self.error_occurred.emit(f"Invalid waveform: {waveform!r}. Valid: {SIGGEN_WAVEFORMS}")
            return
        self.settings["waveform"] = waveform
        self._write(f"FUNC {waveform}")

    def set_frequency(self, freq_hz: float):
        freq_hz = max(SIGGEN_FREQ_MIN, min(SIGGEN_FREQ_MAX, freq_hz))
        self.settings["frequency"] = freq_hz
        self._write(f"FREQ {freq_hz}")

    def set_amplitude(self, value: float):
        # Clamp range depends on the currently selected unit. VRMS limits are
        # waveform-dependent; we use the most permissive (square wave) here and
        # let the instrument error if the user picks a value the active
        # waveform can't reach.
        if self.settings.get("amplitude_unit", "VPP") == "VRMS":
            value = max(0.001, min(SIGGEN_AMP_MAX_VRMS, value))
        else:
            value = max(SIGGEN_AMP_MIN, min(SIGGEN_AMP_MAX, value))
        self.settings["amplitude"] = value
        self._write(f"VOLT {value}")

    def set_amplitude_unit(self, unit: str):
        if unit not in SIGGEN_AMP_UNITS:
            self.error_occurred.emit(f"Invalid amplitude unit: {unit!r}. Valid: {SIGGEN_AMP_UNITS}")
            return
        self.settings["amplitude_unit"] = unit
        self._write(f"VOLT:UNIT {unit}")

    def set_offset(self, offset_v: float):
        offset_v = max(-SIGGEN_OFFSET_MAX, min(SIGGEN_OFFSET_MAX, offset_v))
        self.settings["offset"] = offset_v
        self._write(f"VOLT:OFFS {offset_v}")

    def set_load(self, load: str):
        if load not in SIGGEN_LOAD:
            self.error_occurred.emit(f"Invalid load: {load!r}. Valid: {SIGGEN_LOAD}")
            return
        self.settings["load"] = load
        self._write(f"OUTP:LOAD {load}")

    def set_duty_cycle(self, duty_pct: float):
        duty_pct = max(SIGGEN_DUTY_MIN, min(SIGGEN_DUTY_MAX, duty_pct))
        self.settings["duty_cycle"] = duty_pct
        self._write(f"PULS:DCYC {duty_pct}")

    def set_gpib_address(self, address: int):
        """Update stored GPIB address. Takes effect on the next connect_device() call."""
        self.settings["gpib_address"] = address
