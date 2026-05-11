"""Frontend-owned controller for backend workers.

This module is intentionally the bridge between UI widgets and backend services.
UI widgets should not talk to DAQmx or VISA workers directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
from PyQt5.QtCore import QObject, QTimer, pyqtSignal

logger = logging.getLogger(__name__)


class DataMode(Enum):
    SIMULATION = "SIMULATION"
    DAQ = "DAQ"

    @classmethod
    def from_label(cls, label: str) -> "DataMode":
        normalized = label.strip().upper()
        if normalized == cls.DAQ.value:
            return cls.DAQ
        return cls.SIMULATION


@dataclass(slots=True)
class PreflightResult:
    ok: bool
    message: str


class BackendController(QObject):
    """Owns backend workers, timers, and frontend-safe backend operations."""

    daq_data_ready = pyqtSignal(object, object)  # display_data, active_backend_indices
    measurements_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)
    single_capture_completed = pyqtSignal()
    signal_gen_connection_changed = pyqtSignal(bool)
    daq_unavailable = pyqtSignal(str)
    preflight_completed = pyqtSignal(bool, str)
    sample_rate_changed = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.mode = DataMode.SIMULATION
        self._daq: Any | None = None
        self._daq_adapter: Any | None = None
        self._signal_gen: Any | None = None
        self._signal_gen_adapter: Any | None = None
        self._daq_running = False
        self._pending_single = False
        self._last_scope_state: dict[str, Any] = {}
        self._last_daq_error: str | None = None
        self._last_measurement_state: set[str] | None = None

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_daq)
        self._poll_timer.setInterval(33)

    @property
    def daq_worker(self) -> Any | None:
        return self._daq

    @property
    def signal_gen_worker(self) -> Any | None:
        return self._signal_gen

    def set_mode(self, mode: DataMode) -> None:
        if self.mode == mode:
            return
        if self.mode == DataMode.DAQ:
            self.stop_acquisition()
        self.mode = mode
        self._last_daq_error = None
        self.status_changed.emit(f"Mode: {mode.value}")
        logger.info("Mode changed to %s", mode.value)

    def preflight_daq(self) -> PreflightResult:
        """Validate DAQ prerequisites without creating a running hardware task."""
        try:
            from backend.config import load_yaml
        except Exception as exc:  # noqa: BLE001
            result = PreflightResult(False, f"Backend config could not be imported: {exc}")
            self.preflight_completed.emit(result.ok, result.message)
            logger.warning("DAQ preflight failed: %s", result.message)
            return result

        config_path = Path.cwd() / "backend" / "config.yaml"
        if not config_path.exists():
            config_path = Path(__file__).resolve().parents[1] / "backend" / "config.yaml"

        try:
            daq_settings = load_yaml(config_path, area="daq")
        except Exception as exc:  # noqa: BLE001
            result = PreflightResult(False, f"Invalid DAQ configuration: {exc}")
            self.preflight_completed.emit(result.ok, result.message)
            logger.warning("DAQ preflight failed: %s", result.message)
            return result

        channels = daq_settings.get("channels", [])
        enabled = [ch for ch in channels if ch.get("enable")]
        if not enabled:
            result = PreflightResult(False, "No DAQ channels are enabled in config.yaml.")
            self.preflight_completed.emit(result.ok, result.message)
            logger.warning("DAQ preflight failed: %s", result.message)
            return result

        try:
            import nidaqmx.system

            devices = nidaqmx.system.System.local().devices
            device_names = {device.name for device in devices}
        except Exception as exc:  # noqa: BLE001
            result = PreflightResult(False, f"NI-DAQmx device discovery failed: {exc}")
            self.preflight_completed.emit(result.ok, result.message)
            logger.warning("DAQ preflight failed: %s", result.message)
            return result

        if not device_names:
            result = PreflightResult(False, "No NI-DAQmx devices were detected.")
            self.preflight_completed.emit(result.ok, result.message)
            logger.warning("DAQ preflight failed: %s", result.message)
            return result

        configured_devices = {str(ch.get("name", "")).split("/")[0] for ch in enabled}
        missing = sorted(name for name in configured_devices if name and name not in device_names)
        if missing:
            result = PreflightResult(
                False,
                f"Configured DAQ device(s) {missing} not found. Detected devices: {sorted(device_names)}.",
            )
            self.preflight_completed.emit(result.ok, result.message)
            logger.warning("DAQ preflight failed: %s", result.message)
            return result

        result = PreflightResult(True, f"DAQ preflight OK. Detected devices: {sorted(device_names)}.")
        self.preflight_completed.emit(result.ok, result.message)
        logger.info(result.message)
        return result

    def apply_scope_settings(self, time_label: str, channel_params: dict[int, dict], trigger_cfg: dict) -> None:
        """Apply changed UI settings to the DAQ backend only in DAQ mode."""
        if self.mode != DataMode.DAQ:
            return
        try:
            self._ensure_daq()
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Could not initialize DAQ backend: {exc}")
            return

        assert self._daq_adapter is not None
        state = {
            "time_label": time_label,
            "channels": {
                ch: {
                    "enabled": bool(params["enabled"]),
                    "vdiv_label": params["vdiv_label"],
                    "coupling": params["coupling"],
                    "offset_div": float(params["offset_div"]),
                }
                for ch, params in channel_params.items()
            },
            "trigger": {
                "source": int(trigger_cfg["source"]),
                "level_v": float(trigger_cfg["level_v"]),
                "rising": bool(trigger_cfg["rising"]),
            },
        }

        try:
            if self._last_scope_state.get("time_label") != state["time_label"]:
                self._daq_adapter.set_timebase_from_label(time_label)
                self._emit_sample_rate()

            old_channels = self._last_scope_state.get("channels", {})
            for ch, ch_state in state["channels"].items():
                old = old_channels.get(ch, {})
                if old.get("enabled") != ch_state["enabled"]:
                    self._daq_adapter.set_channel_enabled(ch, ch_state["enabled"])
                if old.get("vdiv_label") != ch_state["vdiv_label"]:
                    self._daq_adapter.set_channel_volts_per_div_from_label(ch, ch_state["vdiv_label"])
                if old.get("coupling") != ch_state["coupling"]:
                    self._daq_adapter.set_channel_coupling(ch, ch_state["coupling"])
                if old.get("offset_div") != ch_state["offset_div"]:
                    self._daq_adapter.set_channel_vertical_offset(ch, ch_state["offset_div"])

            old_trigger = self._last_scope_state.get("trigger", {})
            trigger = state["trigger"]
            if old_trigger.get("source") != trigger["source"]:
                self._daq_adapter.set_trigger_source(trigger["source"])
            if old_trigger.get("level_v") != trigger["level_v"]:
                self._daq_adapter.set_trigger_level(trigger["level_v"])
            if old_trigger.get("rising") != trigger["rising"]:
                self._daq_adapter.set_trigger_slope(trigger["rising"])

            self._last_scope_state = state
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(str(exc))

    def apply_measurement_settings(self, enabled_backend_names: set[str]) -> None:
        """Apply measurement selection to all backend channels.

        The first version uses a global measurement selection.  The backend still
        stores measurements per channel, so this method writes the same selection
        to all configured channels.
        """
        if self.mode != DataMode.DAQ:
            self._last_measurement_state = set(enabled_backend_names)
            return
        if self._last_measurement_state == enabled_backend_names:
            return
        try:
            self._ensure_daq()
            assert self._daq is not None
            all_names = {"mean", "rms", "min", "max", "peak_to_peak", "frequency", "rise_time", "fall_time"}
            for channel_index in range(len(self._daq.channels)):
                for name in all_names:
                    self._daq.measurements.set_measurement(channel_index, name, name in enabled_backend_names)
            self._last_measurement_state = set(enabled_backend_names)
            logger.info("Measurement selection applied: %s", sorted(enabled_backend_names))
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Measurement settings error: {exc}")

    def start_acquisition(self) -> bool:
        """Start DAQ acquisition and return True only if a task is running."""
        if self.mode != DataMode.DAQ:
            return False
        preflight = self.preflight_daq()
        if not preflight.ok:
            self.daq_unavailable.emit(preflight.message)
            return False
        try:
            self._ensure_daq()
            assert self._daq is not None
            if not self._pending_single and self._daq_adapter is not None:
                self._daq_adapter.set_trigger_type("normal")
            self._daq.trigger.set_run_stop(True)
            if not self._daq_running:
                self._last_daq_error = None
                self._daq.start_task()
                if getattr(self._daq, "task", None) is None:
                    self._daq_running = False
                    if self._poll_timer.isActive():
                        self._poll_timer.stop()
                    message = self._last_daq_error or "DAQ task could not be started. Check NI hardware, device name, and channel configuration."
                    self.status_changed.emit("DAQ unavailable")
                    self.daq_unavailable.emit(message)
                    return False
                self._daq_running = True
                self._emit_sample_rate()
            if not self._poll_timer.isActive():
                self._poll_timer.start()
            self.status_changed.emit("DAQ running")
            logger.info("DAQ acquisition started")
            return True
        except Exception as exc:  # noqa: BLE001
            message = f"Could not start DAQ acquisition: {exc}"
            self._last_daq_error = message
            self.error_occurred.emit(message)
            self.daq_unavailable.emit(message)
            logger.exception("DAQ acquisition failed")
            return False

    def stop_acquisition(self) -> None:
        if self._poll_timer.isActive():
            self._poll_timer.stop()
        if self._daq is not None:
            try:
                self._daq.trigger.set_run_stop(False)
                self._daq.stop_task()
            except Exception as exc:  # noqa: BLE001
                self.error_occurred.emit(f"DAQ stop error: {exc}")
                logger.exception("DAQ stop failed")
        self._daq_running = False
        self._pending_single = False
        self.status_changed.emit("DAQ stopped")
        logger.info("DAQ acquisition stopped")

    def single_capture(self) -> bool:
        if self.mode != DataMode.DAQ:
            return False
        try:
            self._ensure_daq()
            assert self._daq_adapter is not None
            assert self._daq is not None
            self._pending_single = True
            self._daq_adapter.set_trigger_type("single")
            self._daq.trigger.set_run_stop(True)
            started = self.start_acquisition()
            if started:
                self.status_changed.emit("DAQ single armed")
            else:
                self._pending_single = False
            return started
        except Exception as exc:  # noqa: BLE001
            message = f"Could not start single capture: {exc}"
            self.error_occurred.emit(message)
            self.daq_unavailable.emit(message)
            self._pending_single = False
            logger.exception("Single capture failed")
            return False

    def connect_signal_generator(self) -> None:
        try:
            self._ensure_signal_gen()
            assert self._signal_gen is not None
            self._signal_gen.connect_device()
            self._signal_gen.apply_settings()
            logger.info("Signal generator connect requested")
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Could not connect signal generator: {exc}")
            logger.exception("Signal generator connection failed")

    def disconnect_signal_generator(self) -> None:
        if self._signal_gen is None:
            self.signal_gen_connection_changed.emit(False)
            return
        try:
            self._signal_gen.disconnect_device()
            logger.info("Signal generator disconnected")
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Signal generator disconnect error: {exc}")
            logger.exception("Signal generator disconnect failed")

    def set_signal_generator_output(self, enabled: bool) -> None:
        self._call_signal_gen("set_output", bool(enabled))

    def set_signal_generator_waveform(self, waveform: str) -> None:
        self._call_signal_gen("set_waveform", waveform)

    def set_signal_generator_frequency(self, frequency_hz: float) -> None:
        self._call_signal_gen("set_frequency", float(frequency_hz))

    def set_signal_generator_amplitude(self, amplitude_vpp: float) -> None:
        self._call_signal_gen("set_amplitude", float(amplitude_vpp))

    def set_signal_generator_offset(self, offset_v: float) -> None:
        self._call_signal_gen("set_offset", float(offset_v))

    def set_signal_generator_load(self, load: str) -> None:
        self._call_signal_gen("set_load", load)

    def set_signal_generator_duty_cycle(self, duty_pct: float) -> None:
        self._call_signal_gen("set_duty_cycle", float(duty_pct))

    def reload_configuration(self) -> None:
        """Drop hardware workers so changed config.yaml is reloaded lazily."""
        self.stop_acquisition()
        self.disconnect_signal_generator()
        self._daq = None
        self._daq_adapter = None
        self._signal_gen = None
        self._signal_gen_adapter = None
        self._last_scope_state = {}
        self._last_measurement_state = None
        self.status_changed.emit("Configuration reloaded")

    def close(self) -> None:
        self.stop_acquisition()
        self.disconnect_signal_generator()

    def _poll_daq(self) -> None:
        if self._daq is None:
            return
        try:
            self._daq.poll_queue()
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"DAQ polling error: {exc}")
            self.stop_acquisition()
            logger.exception("DAQ polling failed")

    def _on_graph_data(self, payload: object) -> None:
        if isinstance(payload, dict):
            display = payload.get("display")
            active_indices = list(payload.get("active_indices", []))
        else:
            display = payload
            active_indices = self._current_active_backend_indices()

        if isinstance(display, np.ndarray):
            self.daq_data_ready.emit(display, active_indices)

        if self._pending_single and self._daq is not None and not self._daq.trigger.run_stop:
            self._pending_single = False
            self.single_capture_completed.emit()
            self.stop_acquisition()

    def _current_active_backend_indices(self) -> list[int]:
        if self._daq is None:
            return []
        return [i for i, ch in enumerate(self._daq.channels) if ch.get("enable")]

    def _ensure_daq(self) -> None:
        if self._daq is not None:
            return
        from backend.control_adapter import DaqControlAdapter
        from backend.daq import DaqWorker

        self._daq = DaqWorker()
        self._daq_adapter = DaqControlAdapter(self._daq)
        self._daq.graph_data.connect(self._on_graph_data)
        self._daq.measurements_data.connect(self.measurements_ready.emit)
        self._daq.error_occurred.connect(self._on_daq_error)
        self._emit_sample_rate()

    def _emit_sample_rate(self) -> None:
        if self._daq is None:
            return
        sample_rate = getattr(self._daq, "sample_rate", None)
        if sample_rate:
            self.sample_rate_changed.emit(f"{sample_rate:g} S/s")

    def _on_daq_error(self, message: str) -> None:
        self._last_daq_error = message
        self.error_occurred.emit(message)
        logger.error("DAQ error: %s", message)

    def _ensure_signal_gen(self) -> None:
        if self._signal_gen is not None:
            return
        from backend.control_adapter import SignalGenControlAdapter
        from backend.signal_gen import SignalGenWorker

        self._signal_gen = SignalGenWorker()
        self._signal_gen_adapter = SignalGenControlAdapter(self._signal_gen)
        self._signal_gen.error_occurred.connect(self.error_occurred.emit)
        self._signal_gen.connection_changed.connect(self.signal_gen_connection_changed.emit)

    def _call_signal_gen(self, method_name: str, *args: object) -> None:
        try:
            self._ensure_signal_gen()
            assert self._signal_gen is not None
            method = getattr(self._signal_gen, method_name)
            method(*args)
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Signal generator error: {exc}")
            logger.exception("Signal generator call failed: %s", method_name)
