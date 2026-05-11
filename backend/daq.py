import utils.dll_fix  # noqa: F401 must be imported before nidaqmx to fix DLL loading issues on Windows
import queue
from collections import deque
from pathlib import Path
import numpy as np
import nidaqmx
from nidaqmx.constants import AcquisitionType
from nidaqmx.errors import DaqError
from PyQt5.QtCore import QObject, pyqtSignal
from backend.processing import TriggerProcessor, Measurements
from backend.config import (
    COUPLING_MAP,
    PROBE_ATTENUATION,
    RING_BUFFER_SCREEN_MULTIPLIER,
    NIDAQMX_BUFFER_MULTIPLIER,
    NUM_HORIZONTAL_DIVS,
    TERMINAL_CONFIG_MAP,
    TIMEBASE_MAP,
    MEASURING_RANGE_THRESHOLDS,
    VOLTS_PER_DIV,
    load_yaml,
)


class DaqWorker(QObject):
    path = Path(__file__).parent
    # signal to send acquired data to the main thread for plotting
    graph_data = pyqtSignal(np.ndarray)
    measurements_data = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.settings = load_yaml(self.path / "config.yaml", area="daq")
        print(self.path)
        print(self.path / "config.yaml")
        self.queue = queue.Queue()
        self.task = None
        self.timebase = self.settings["timebase"]
        self.channels = self.settings["channels"]
        self._set_sample_rate()
        self.trigger = TriggerProcessor()
        self.measurements = Measurements()

    def _set_sample_rate(self):
        self.sample_rate = TIMEBASE_MAP[self.timebase]
        self.display_samples = int(self.sample_rate * self.timebase * NUM_HORIZONTAL_DIVS)
        self.buff_transfer = min(
            self.display_samples // NUM_HORIZONTAL_DIVS, self.sample_rate // 10
        )  # amount of samples transferred with every nidaqmx callback is the number of samples in one division
        self.nidaqmx_buffer_size = self.buff_transfer * NIDAQMX_BUFFER_MULTIPLIER
        self.ring_buffer = [
            deque(maxlen=self.display_samples * RING_BUFFER_SCREEN_MULTIPLIER) for _ in range(len(self.channels))
        ]  # data for plotting and calculating measurements

    def start_task(self):
        # create and configure nidaqmx task
        try:
            self.task = nidaqmx.Task()
            for channel in self.channels:
                if not channel["enable"]:
                    continue
                self.task.ai_channels.add_ai_voltage_chan(
                    channel["name"],
                    min_val=channel["range"] * (-1),
                    max_val=channel["range"],
                    terminal_config=channel["terminal_config"],
                )
                self.task.ai_channels[-1].ai_coupling = channel["coupling"]  # type: ignore

            if len(self.task.ai_channels) == 0:
                self.task = None
                return
            self.task.timing.cfg_samp_clk_timing(
                rate=self.sample_rate, sample_mode=AcquisitionType.CONTINUOUS, samps_per_chan=self.nidaqmx_buffer_size
            )
            self.task.register_every_n_samples_acquired_into_buffer_event(self.buff_transfer, self._buff_callback)
            self.task.start()
            print(
                f"DAQ task started with sample rate: {self.sample_rate} S/s, buffer transfer size: {self.buff_transfer} samples, nidaqmx buffer size: {self.nidaqmx_buffer_size} samples"
            )
        except DaqError as e:
            self.error_occurred.emit(f"NIDAQmx Error: {e}")
            print(f"NIDAQmx Error: {e}")
            self.stop_task()

    def stop_task(self):
        if self.task is not None:
            self.task.stop()
            self.task.close()
            self.task = None

    def restart_task(self):
        self.stop_task()
        self.start_task()

    def set_timebase(self, timebase_val):
        if timebase_val not in TIMEBASE_MAP:
            self.error_occurred.emit(f"Invalid timebase value: {timebase_val}")
            return
        self.timebase = timebase_val
        self._set_sample_rate()
        self.restart_task()

    def set_volts_per_div(self, volts_per_div_val, chan_index):
        if chan_index < 0 or chan_index >= len(self.channels):
            self.error_occurred.emit(f"Invalid channel index: {chan_index}")
            return
        if volts_per_div_val not in VOLTS_PER_DIV:
            self.error_occurred.emit(f"Invalid volts/div value: {volts_per_div_val}")
            return
        self.channels[chan_index]["volts_per_div"] = volts_per_div_val
        thresholds = sorted(MEASURING_RANGE_THRESHOLDS.keys())
        for treshold in thresholds:
            if volts_per_div_val <= treshold:
                new_range = MEASURING_RANGE_THRESHOLDS[treshold]
                break
        else:
            new_range = MEASURING_RANGE_THRESHOLDS[thresholds[-1]]
        if self.channels[chan_index]["range"] != new_range:
            self.channels[chan_index]["range"] = new_range
            self.restart_task()

    def set_attenuation(self, attenuation_val, chan_index):
        if chan_index < 0 or chan_index >= len(self.channels):
            self.error_occurred.emit(f"Invalid channel index: {chan_index}")
            return
        if attenuation_val not in PROBE_ATTENUATION:
            self.error_occurred.emit(f"Invalid attenuation value: {attenuation_val}")
            return
        self.channels[chan_index]["probe_attenuation"] = attenuation_val
        self.restart_task()

    def set_coupling(self, coupling_val, chan_index):
        if chan_index < 0 or chan_index >= len(self.channels):
            self.error_occurred.emit(f"Invalid channel index: {chan_index}")
            return
        if coupling_val not in COUPLING_MAP.keys():
            self.error_occurred.emit(f"Invalid coupling value: {coupling_val}")
            return
        self.channels[chan_index]["coupling"] = COUPLING_MAP[coupling_val]
        self.restart_task()

    def set_terminal_config(self, terminal_config_val, chan_index):
        if chan_index < 0 or chan_index >= len(self.channels):
            self.error_occurred.emit(f"Invalid channel index: {chan_index}")
            return
        if terminal_config_val not in TERMINAL_CONFIG_MAP.keys():
            self.error_occurred.emit(f"Invalid terminal config value: {terminal_config_val}")
            return
        self.channels[chan_index]["terminal_config"] = TERMINAL_CONFIG_MAP[terminal_config_val]
        self.restart_task()

    def set_channel_enable(self, enable: bool, chan_index: int):
        if chan_index < 0 or chan_index >= len(self.channels):
            self.error_occurred.emit(f"Invalid channel index: {chan_index}")
            return
        self.channels[chan_index]["enable"] = enable
        self.restart_task()

    def set_vertical_offset(self, offset, chan_index):
        if chan_index < 0 or chan_index >= len(self.channels):
            self.error_occurred.emit(f"Invalid channel index: {chan_index}")
            return
        self.channels[chan_index]["vertical_offset"] = offset

    def _buff_callback(self, task_handle, event_type, n_samples, callback_data):
        try:
            data = np.atleast_2d(self.task.read(n_samples))  # type: ignore
            self.queue.put(data)
        except DaqError as e:
            self.error_occurred.emit(f"NIDAQmx Error: {e}")
        return 0

    def poll_queue(self):
        if self.queue.empty():
            return

        active_indices = [i for i, ch in enumerate(self.channels) if ch["enable"]]
        temp_data = [[] for _ in range(len(active_indices))]

        while not self.queue.empty():
            data = self.queue.get_nowait()  # shape (n_active, n_samples)
            for active_idx in range(len(active_indices)):
                temp_data[active_idx].append(data[active_idx])

        for active_idx, phys_idx in enumerate(active_indices):
            combined = np.concatenate(temp_data[active_idx]) * self.channels[phys_idx]["probe_attenuation"]
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
