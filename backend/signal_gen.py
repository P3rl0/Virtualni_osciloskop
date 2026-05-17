from PyQt5.QtCore import QObject, pyqtSignal
from pathlib import Path
from backend.config import (
    load_yaml,
    SIGGEN_AMP_UNITS,
    SIGGEN_WAVEFORMS,
    SIGGEN_LOAD,
    SIGGEN_FREQ_MIN,
    SIGGEN_FREQ_MAX,
    SIGGEN_AMP_MIN,
    SIGGEN_AMP_MAX,
    SIGGEN_OFFSET_MAX,
    SIGGEN_DUTY_MIN,
    SIGGEN_DUTY_MAX,
)


class SignalGenWorker(QObject):
    path = Path(__file__).parent
    error_occurred = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)  # True = connected, False = disconnected
    # After a unit change the device internally converts the amplitude; we
    # query it back and emit (new_value, new_unit) so the GUI can update
    # both the spinbox value and its suffix.
    amplitude_synced = pyqtSignal(float, str)
    # Emitted with the model substring of *IDN? right after a successful connect
    # (e.g. "33120A", "33220A"). GUI uses this to disable features the model
    # doesn't support (33120A has fixed-50% square-wave duty cycle).
    model_detected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.settings = load_yaml(self.path / "config.yaml", area="signal_gen")
        self.settings.setdefault("amplitude_unit", "VPP")
        self.rm = None  # pyvisa ResourceManager
        self.device = None  # pyvisa Resource
        self.model = ""  # populated on connect

    def connect_device(self):
        """Open VISA resource at the configured GPIB address and detect model."""
        try:
            import pyvisa  # lazy import — avoids loading VISA DLLs at app startup (conflicts with NI-DAQmx)
            self.rm = pyvisa.ResourceManager()
            addr = f"GPIB::{self.settings['gpib_address']}::INSTR"
            self.device = self.rm.open_resource(addr)
            self.device.timeout = 3000  # 3 s — avoids infinite hang on bad address
            # *CLS clears any stale errors before we start sending real commands.
            self._write("*CLS")
            idn = self._query("*IDN?") or ""
            self.model = self._parse_model(idn)
            self.connection_changed.emit(True)
            self.model_detected.emit(self.model)
        except Exception as e:
            self.error_occurred.emit(f"VISA connect error: {e}")
            self.device = None

    @staticmethod
    def _parse_model(idn: str) -> str:
        """Extract the model substring from an *IDN? response.
        Standard *IDN? format is "<vendor>,<model>,<serial>,<firmware>"."""
        parts = [p.strip() for p in idn.split(",")]
        return parts[1] if len(parts) >= 2 else ""

    def disconnect_device(self):
        if self.device is not None:
            self.device.close()
            self.device = None
        if self.rm is not None:
            self.rm.close()
            self.rm = None
        self.connection_changed.emit(False)

    def _write(self, cmd: str):
        """Send SCPI command; emit error_occurred on transport failure."""
        if self.device is None:
            return
        try:
            self.device.write(cmd)  # type: ignore
        except Exception as e:
            self.error_occurred.emit(f"VISA write error ({cmd!r}): {e}")

    def _write_checked(self, cmd: str) -> bool:
        """Send SCPI command and then query the device's error queue.
        Use for commands where you want to know whether the *device* (not just
        the transport) accepted the command — e.g. duty-cycle, unit change.
        Returns True if the device reported no error."""
        if self.device is None:
            return False
        try:
            self.device.write(cmd)  # type: ignore
        except Exception as e:
            self.error_occurred.emit(f"VISA write error ({cmd!r}): {e}")
            return False
        try:
            err = self.device.query("SYST:ERR?").strip()  # type: ignore  # "<code>,<msg>"
        except Exception:
            return True  # error queue unavailable; assume OK
        # "0,No error" or "+0,..." → no error.
        code = err.split(",", 1)[0].lstrip("+")
        if code != "0":
            self.error_occurred.emit(f"Device rejected {cmd!r}: {err}")
            return False
        return True

    def _query(self, cmd: str):
        """Send SCPI query; return stripped response string or None on failure."""
        if self.device is None:
            return None
        try:
            return self.device.query(cmd).strip()  # type: ignore
        except Exception as e:
            self.error_occurred.emit(f"VISA query error ({cmd!r}): {e}")
            return None

    @property
    def duty_supported(self) -> bool:
        """True if the connected model can set a non-50% square-wave duty cycle.
        False for the Agilent/HP 33120A (fixed 50% by hardware)."""
        return "33120A" not in self.model.upper()

    def apply_settings(self):
        """Push all current settings to the instrument in one go.
        Call this once after connect_device() to synchronise instrument state."""
        unit = self.settings.get("amplitude_unit", "VPP")
        self._write(f"FUNC {self.settings['waveform']}")
        self._write(f"FREQ {self.settings['frequency']}")
        self._write(f"VOLT:UNIT {unit}")
        self._write(f"VOLT {self.settings['amplitude']}")
        self._write(f"VOLT:OFFS {self.settings['offset']}")
        self._write(f"OUTP:LOAD {self.settings['load']}")
        if self.settings["waveform"] == "SQU" and self.duty_supported:
            # Models that support variable duty cycle: use checked write so
            # any device-side rejection (e.g. duty outside the allowed range
            # at the current frequency) surfaces in the status bar.
            self._write_checked(f"FUNC:SQU:DCYC {self.settings['duty_cycle']}")
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
        """Set amplitude in the currently-selected unit (VPP / VRMS / DBM)."""
        value = max(SIGGEN_AMP_MIN, min(SIGGEN_AMP_MAX, value))
        self.settings["amplitude"] = value
        # No VOLT:UNIT here — that's controlled by set_amplitude_unit. Forcing
        # it on every amplitude change would undo the user's chosen unit.
        self._write(f"VOLT {value}")

    def set_amplitude_unit(self, unit: str):
        """Switch the device's amplitude unit (VPP, VRMS, or DBM).
        The 33120A internally converts the current amplitude when the unit
        changes, so we query it back and emit `amplitude_synced` so the GUI
        can update both the spinbox value and its suffix."""
        if unit not in SIGGEN_AMP_UNITS:
            self.error_occurred.emit(f"Invalid amplitude unit: {unit!r}. Valid: {SIGGEN_AMP_UNITS}")
            return
        self.settings["amplitude_unit"] = unit
        if not self._write_checked(f"VOLT:UNIT {unit}"):
            return
        reply = self._query("VOLT?")
        if reply is None:
            return
        try:
            new_value = float(reply)
        except ValueError:
            self.error_occurred.emit(f"Could not parse VOLT? reply: {reply!r}")
            return
        self.settings["amplitude"] = new_value
        self.amplitude_synced.emit(new_value, unit)

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
        if not self.duty_supported:
            # Save the value for later (it'll be used if the user later
            # connects to a supporting model) but don't try to send.
            return
        # Checked write — if the device rejects the command (e.g. duty %
        # is out-of-range for the current frequency), the user sees why.
        self._write_checked(f"FUNC:SQU:DCYC {duty_pct}")

    def set_gpib_address(self, address: int):
        """Update stored GPIB address. Takes effect on the next connect_device() call."""
        self.settings["gpib_address"] = address
