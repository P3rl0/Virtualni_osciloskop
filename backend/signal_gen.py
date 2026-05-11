"""PyVISA signal-generator worker for a GPIB-controlled function generator."""

from __future__ import annotations

from pathlib import Path

import pyvisa
from PyQt5.QtCore import QObject, pyqtSignal

from backend.config import (
    ConfigValidationError,
    SIGGEN_AMP_MIN,
    SIGGEN_DUTY_MAX,
    SIGGEN_DUTY_MIN,
    SIGGEN_FREQ_MAX,
    SIGGEN_FREQ_MIN,
    SIGGEN_GPIB_MAX,
    SIGGEN_GPIB_MIN,
    SIGGEN_LOAD,
    SIGGEN_OFFSET_MAX,
    SIGGEN_WAVEFORMS,
    load_yaml,
    siggen_amplitude_max_for_load,
    validate_signal_gen_settings,
)


class SignalGenWorker(QObject):
    """Owns VISA connection lifecycle and SCPI commands for the signal generator."""

    path = Path(__file__).parent

    error_occurred = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.rm: pyvisa.ResourceManager | None = None
        self.device = None
        self._config_error: str | None = None

        try:
            self.settings = load_yaml(self.path / "config.yaml", area="signal_gen")
        except ConfigValidationError as exc:
            self._config_error = f"Signal-generator configuration error: {exc}"
            self.settings = self._default_settings()

    def connect_device(self) -> None:
        """Open the configured VISA resource.

        Config is validated before creating the VISA ResourceManager, so invalid
        YAML cannot accidentally open or control hardware.
        """
        if not self._validate_current_settings():
            return
        if self.device is not None:
            self.connection_changed.emit(True)
            return

        rm = None
        device = None
        try:
            rm = pyvisa.ResourceManager()
            address = f"GPIB::{self.settings['gpib_address']}::INSTR"
            device = rm.open_resource(address)
            device.timeout = 3000
            idn = device.query("*IDN?").strip()
            if not idn:
                raise RuntimeError("empty *IDN? response")
            self.rm = rm
            self.device = device
            print(f"Signal generator connected: {idn}")
            self.connection_changed.emit(True)
        except Exception as exc:  # noqa: BLE001 - PyVISA backends raise several exception types
            self.error_occurred.emit(f"VISA connect error: {exc}")
            if device is not None:
                try:
                    device.close()
                except Exception as close_exc:  # noqa: BLE001
                    self.error_occurred.emit(f"VISA device close error after failed connect: {close_exc}")
            if rm is not None:
                try:
                    rm.close()
                except Exception as close_exc:  # noqa: BLE001
                    self.error_occurred.emit(f"VISA ResourceManager close error after failed connect: {close_exc}")
            self.device = None
            self.rm = None
            self.connection_changed.emit(False)

    def disconnect_device(self) -> None:
        """Close VISA resources without leaving stale object references behind."""
        errors: list[str] = []

        device = self.device
        self.device = None
        if device is not None:
            try:
                device.close()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"device close failed: {exc}")

        rm = self.rm
        self.rm = None
        if rm is not None:
            try:
                rm.close()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"ResourceManager close failed: {exc}")

        if errors:
            self.error_occurred.emit("VISA disconnect warning: " + "; ".join(errors))
        self.connection_changed.emit(False)

    def apply_settings(self) -> bool:
        """Validate and push all current settings to the instrument."""
        if not self._validate_current_settings():
            return False

        self._write(f"FUNC {self.settings['waveform']}")
        self._write(f"FREQ {self.settings['frequency']}")
        self._write("VOLT:UNIT VPP")
        self._write(f"VOLT {self.settings['amplitude']}")
        self._write(f"VOLT:OFFS {self.settings['offset']}")
        self._write(f"OUTP:LOAD {self.settings['load']}")
        if self.settings["waveform"] == "SQU":
            self._write(f"FUNC:SQU:DCYC {self.settings['duty_cycle']}")
        self._write(f"OUTPUT {'ON' if self.settings['output_enabled'] else 'OFF'}")
        return True

    def set_output(self, enabled: bool) -> None:
        self.settings["output_enabled"] = bool(enabled)
        self._write(f"OUTPUT {'ON' if enabled else 'OFF'}")

    def set_waveform(self, waveform: str) -> None:
        if waveform not in SIGGEN_WAVEFORMS:
            self.error_occurred.emit(f"Invalid waveform: {waveform!r}. Valid: {SIGGEN_WAVEFORMS}")
            return
        self.settings["waveform"] = waveform
        self._write(f"FUNC {waveform}")

    def set_frequency(self, freq_hz: float) -> None:
        freq_hz = max(SIGGEN_FREQ_MIN, min(SIGGEN_FREQ_MAX, float(freq_hz)))
        self.settings["frequency"] = freq_hz
        self._write(f"FREQ {freq_hz}")

    def set_amplitude(self, vpp: float) -> None:
        max_amp = siggen_amplitude_max_for_load(self.settings["load"])
        vpp = max(SIGGEN_AMP_MIN, min(max_amp, float(vpp)))
        self.settings["amplitude"] = vpp
        self._write("VOLT:UNIT VPP")
        self._write(f"VOLT {vpp}")

    def set_offset(self, offset_v: float) -> None:
        offset_v = max(-SIGGEN_OFFSET_MAX, min(SIGGEN_OFFSET_MAX, float(offset_v)))
        self.settings["offset"] = offset_v
        self._write(f"VOLT:OFFS {offset_v}")

    def set_load(self, load: str) -> None:
        if load not in SIGGEN_LOAD:
            self.error_occurred.emit(f"Invalid load: {load!r}. Valid: {SIGGEN_LOAD}")
            return
        self.settings["load"] = load
        self._write(f"OUTP:LOAD {load}")

        max_amp = siggen_amplitude_max_for_load(load)
        if self.settings["amplitude"] > max_amp:
            self.set_amplitude(max_amp)

    def set_duty_cycle(self, duty_pct: float) -> None:
        duty_pct = max(SIGGEN_DUTY_MIN, min(SIGGEN_DUTY_MAX, float(duty_pct)))
        self.settings["duty_cycle"] = duty_pct
        if self.settings["waveform"] == "SQU":
            self._write(f"FUNC:SQU:DCYC {duty_pct}")

    def set_gpib_address(self, address: int) -> None:
        if not isinstance(address, int) or isinstance(address, bool):
            self.error_occurred.emit("GPIB address must be an integer.")
            return
        if not SIGGEN_GPIB_MIN <= address <= SIGGEN_GPIB_MAX:
            self.error_occurred.emit(
                f"GPIB address must be between {SIGGEN_GPIB_MIN} and {SIGGEN_GPIB_MAX}."
            )
            return
        self.settings["gpib_address"] = address

    def _write(self, cmd: str) -> None:
        if self.device is None:
            return
        try:
            self.device.write(cmd)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"VISA write error ({cmd!r}): {exc}")

    def _query(self, cmd: str) -> str | None:
        if self.device is None:
            return None
        try:
            return self.device.query(cmd).strip()
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"VISA query error ({cmd!r}): {exc}")
            return None

    def _validate_current_settings(self) -> bool:
        if self._config_error is not None:
            self.error_occurred.emit(self._config_error)
            return False
        try:
            validate_signal_gen_settings(self.settings)
        except ConfigValidationError as exc:
            self.error_occurred.emit(f"Signal-generator settings are invalid: {exc}")
            return False
        return True

    @staticmethod
    def _default_settings() -> dict:
        return {
            "gpib_address": 10,
            "waveform": "SIN",
            "frequency": 1000.0,
            "amplitude": 1.0,
            "offset": 0.0,
            "load": "INF",
            "duty_cycle": 50.0,
            "output_enabled": False,
        }
