"""NI-DAQmx acquisition worker for the virtual oscilloscope backend."""

from __future__ import annotations

import queue
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from utils.dll_fix import load_nidaqmx_dll

try:
    load_nidaqmx_dll(required=True)
    import nidaqmx
    from nidaqmx.constants import AcquisitionType
    from nidaqmx.errors import DaqError

    _NIDAQMX_ERROR: Exception | None = None
except Exception as exc:  # noqa: BLE001 - defer user-facing report to DaqWorker.start_task
    nidaqmx = None  # type: ignore[assignment]
    AcquisitionType = None  # type: ignore[assignment]
    DaqError = Exception  # type: ignore[assignment]
    _NIDAQMX_ERROR = exc

from backend.config import (
    COUPLING_MAP,
    MEASURING_RANGE_THRESHOLDS,
    NIDAQMX_BUFFER_MULTIPLIER,
    NUM_HORIZONTAL_DIVS,
    PROBE_ATTENUATION,
    RING_BUFFER_SCREEN_MULTIPLIER,
    TERMINAL_CONFIG_MAP,
    TIMEBASE_MAP,
    VOLTS_PER_DIV,
    ConfigValidationError,
    load_yaml,
    measuring_range_for_volts_per_div,
)
from backend.processing import Measurements, TriggerProcessor


class DaqWorker(QObject):
    """Owns DAQ task lifecycle, buffering, triggering, and measurement emission."""

    path = Path(__file__).parent

    graph_data = pyqtSignal(np.ndarray)
    measurements_data = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.task: Any | None = None
        self.queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=100)
        self._config_error: str | None = None

        try:
            self.settings = load_yaml(self.path / "config.yaml", area="daq")
        except ConfigValidationError as exc:
            self._config_error = f"DAQ configuration error: {exc}"
            # Safe fallback so the object can still be constructed and report errors.
            self.settings = {"timebase": next(iter(TIMEBASE_MAP)), "channels": []}

        self.timebase = self.settings["timebase"]
        self.channels = self.settings["channels"]
        self.sample_rate = 0
        self.display_samples = 0
        self.buff_transfer = 0
        self.nidaqmx_buffer_size = 0
        self.ring_buffer: list[deque[float]] = []
        self._set_sample_rate()

        self.trigger = TriggerProcessor()
        self.measurements = Measurements()

    def _set_sample_rate(self) -> None:
        if self.timebase not in TIMEBASE_MAP:
            raise ConfigValidationError(f"Invalid timebase value: {self.timebase!r}")

        self.sample_rate = TIMEBASE_MAP[self.timebase]
        self.display_samples = int(self.sample_rate * self.timebase * NUM_HORIZONTAL_DIVS)
        self.buff_transfer = max(
            1,
            min(self.display_samples // NUM_HORIZONTAL_DIVS, self.sample_rate // 10),
        )
        self.nidaqmx_buffer_size = self.buff_transfer * NIDAQMX_BUFFER_MULTIPLIER
        self._reset_ring_buffers()

    def _reset_ring_buffers(self) -> None:
        self.ring_buffer = [
            deque(maxlen=self.display_samples * RING_BUFFER_SCREEN_MULTIPLIER)
            for _ in range(len(self.channels))
        ]

    def _clear_queue(self) -> None:
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    def start_task(self) -> None:
        """Create, configure, and start the NI-DAQmx task."""
        if self._config_error is not None:
            self.error_occurred.emit(self._config_error)
            return
        if _NIDAQMX_ERROR is not None or nidaqmx is None or AcquisitionType is None:
            self.error_occurred.emit(f"NI-DAQmx is not available: {_NIDAQMX_ERROR}")
            return
        if self.task is not None:
            return

        enabled_channels = [ch for ch in self.channels if ch["enable"]]
        if not enabled_channels:
            self.error_occurred.emit("DAQ task not started: no channels are enabled.")
            self._clear_queue()
            self._reset_ring_buffers()
            return

        task = nidaqmx.Task()
        try:
            for channel in enabled_channels:
                task.ai_channels.add_ai_voltage_chan(
                    channel["name"],
                    min_val=-channel["range"],
                    max_val=channel["range"],
                    terminal_config=channel["terminal_config"],
                )
                task.ai_channels[-1].ai_coupling = channel["coupling"]  # type: ignore[attr-defined]

            task.timing.cfg_samp_clk_timing(
                rate=self.sample_rate,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=self.nidaqmx_buffer_size,
            )
            task.register_every_n_samples_acquired_into_buffer_event(
                self.buff_transfer,
                self._buff_callback,
            )
            self.task = task
            task.start()
        except DaqError as exc:
            self.error_occurred.emit(f"NI-DAQmx error while starting task: {exc}")
            self.task = None
            try:
                task.close()
            except DaqError as close_exc:
                self.error_occurred.emit(f"NI-DAQmx error while closing failed task: {close_exc}")
        except Exception as exc:  # noqa: BLE001 - hardware libraries may raise non-DaqError exceptions
            self.error_occurred.emit(f"Unexpected DAQ start error: {exc}")
            self.task = None
            try:
                task.close()
            except Exception as close_exc:  # noqa: BLE001
                self.error_occurred.emit(f"Unexpected DAQ close error after failed start: {close_exc}")

    def stop_task(self) -> None:
        """Stop and close the current DAQ task, even if one cleanup step fails."""
        task = self.task
        self.task = None
        if task is None:
            return

        try:
            task.stop()
        except DaqError as exc:
            self.error_occurred.emit(f"NI-DAQmx error while stopping task: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Unexpected error while stopping DAQ task: {exc}")
        finally:
            try:
                task.close()
            except DaqError as exc:
                self.error_occurred.emit(f"NI-DAQmx error while closing task: {exc}")
            except Exception as exc:  # noqa: BLE001
                self.error_occurred.emit(f"Unexpected error while closing DAQ task: {exc}")

    def restart_task(self) -> None:
        self.stop_task()
        self._clear_queue()
        self._reset_ring_buffers()
        self.start_task()

    def set_timebase(self, timebase_val: float) -> None:
        timebase_val = float(timebase_val)
        if timebase_val not in TIMEBASE_MAP:
            self.error_occurred.emit(f"Invalid timebase value: {timebase_val}")
            return
        self.timebase = timebase_val
        self.settings["timebase"] = timebase_val
        self._set_sample_rate()
        self.restart_task()

    def set_volts_per_div(self, volts_per_div_val: float, chan_index: int) -> None:
        if not self._valid_channel_index(chan_index):
            return
        volts_per_div_val = float(volts_per_div_val)
        if volts_per_div_val not in VOLTS_PER_DIV:
            self.error_occurred.emit(f"Invalid volts/div value: {volts_per_div_val}")
            return

        self.channels[chan_index]["volts_per_div"] = volts_per_div_val
        new_range = measuring_range_for_volts_per_div(volts_per_div_val)
        if self.channels[chan_index]["range"] != new_range:
            self.channels[chan_index]["range"] = new_range
            self.restart_task()

    def set_attenuation(self, attenuation_val: float, chan_index: int) -> None:
        if not self._valid_channel_index(chan_index):
            return
        attenuation_val = float(attenuation_val)
        if attenuation_val not in PROBE_ATTENUATION:
            self.error_occurred.emit(f"Invalid attenuation value: {attenuation_val}")
            return
        self.channels[chan_index]["probe_attenuation"] = attenuation_val
        self.restart_task()

    def set_coupling(self, coupling_val: str, chan_index: int) -> None:
        if not self._valid_channel_index(chan_index):
            return
        if coupling_val not in COUPLING_MAP:
            self.error_occurred.emit(f"Invalid coupling value: {coupling_val}")
            return
        self.channels[chan_index]["coupling"] = COUPLING_MAP[coupling_val]
        self.restart_task()

    def set_terminal_config(self, terminal_config_val: str, chan_index: int) -> None:
        if not self._valid_channel_index(chan_index):
            return
        if terminal_config_val not in TERMINAL_CONFIG_MAP:
            self.error_occurred.emit(f"Invalid terminal config value: {terminal_config_val}")
            return
        self.channels[chan_index]["terminal_config"] = TERMINAL_CONFIG_MAP[terminal_config_val]
        self.restart_task()

    def set_channel_enable(self, enable: bool, chan_index: int) -> None:
        if not self._valid_channel_index(chan_index):
            return
        self.channels[chan_index]["enable"] = bool(enable)
        self.restart_task()

    def set_channel_name(self, name: str, chan_index: int) -> None:
        if not self._valid_channel_index(chan_index):
            return
        if not name.strip():
            self.error_occurred.emit("Channel name must be a non-empty string.")
            return
        self.channels[chan_index]["name"] = name.strip()
        self.restart_task()

    def set_vertical_offset(self, offset: float, chan_index: int) -> None:
        """Store UI display offset in divisions.

        The DAQ data remains physically measured voltage. The frontend should
        apply this offset when plotting, not before measurement computation.
        """
        if not self._valid_channel_index(chan_index):
            return
        self.channels[chan_index]["vertical_offset"] = float(offset)

    def _buff_callback(self, task_handle, event_type, n_samples, callback_data):  # noqa: ANN001
        task = self.task
        if task is None:
            return 0
        try:
            data = np.atleast_2d(task.read(n_samples))
            try:
                self.queue.put_nowait(data)
            except queue.Full:
                # Drop the oldest unread block to keep memory bounded and prefer fresh data.
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    pass
                self.queue.put_nowait(data)
        except DaqError as exc:
            self.error_occurred.emit(f"NI-DAQmx read error: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(f"Unexpected DAQ callback error: {exc}")
        return 0

    def poll_queue(self) -> None:
        if self.queue.empty():
            return

        active_indices = [i for i, ch in enumerate(self.channels) if ch["enable"]]
        if not active_indices:
            self._clear_queue()
            return

        temp_data: list[list[np.ndarray]] = [[] for _ in active_indices]
        while not self.queue.empty():
            try:
                data = self.queue.get_nowait()
            except queue.Empty:
                break
            for active_idx in range(len(active_indices)):
                if active_idx < data.shape[0]:
                    temp_data[active_idx].append(data[active_idx])

        for active_idx, phys_idx in enumerate(active_indices):
            if not temp_data[active_idx]:
                continue
            combined = (
                np.concatenate(temp_data[active_idx])
                * self.channels[phys_idx]["probe_attenuation"]
            )
            self.ring_buffer[phys_idx].extend(combined)

        channel_ranges = [ch["range"] for ch in self.channels]
        display = self.trigger.process_trigger(
            data=self.ring_buffer,
            display_samples=self.display_samples,
            sample_rate=self.sample_rate,
            active_indices=active_indices,
            channel_ranges=channel_ranges,
        )
        if display is not None:
            self.graph_data.emit(display)
            results = self.measurements.compute(display, self.sample_rate, active_indices)
            self.measurements_data.emit(results)

    def _valid_channel_index(self, chan_index: int) -> bool:
        if chan_index < 0 or chan_index >= len(self.channels):
            self.error_occurred.emit(f"Invalid channel index: {chan_index}")
            return False
        return True
