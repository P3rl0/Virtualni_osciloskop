import queue
from collections import deque
from pathlib import Path
import nidaqmx
import numpy as np
from nidaqmx.constants import AcquisitionType, TerminalConfiguration
from nidaqmx.errors import DaqError
from PyQt5.QtCore import QObject, pyqtSignal
from config import (
    RING_BUFFER_SCREEN_MULTIPLIER,
    NIDAQMX_BUFFER_MULTIPLIER,
    NUM_HORIZONTAL_DIVS,
    TIMEBASE_MAP,
    MEASURING_RANGE_THRESHOLDS,
    VOLTS_PER_DIV,
    load_yaml,
)


class DaqWorker(QObject):
    path = Path(__file__).parent
    # signal to send acquired data to the main thread for plotting
    graph_data = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.settings = load_yaml(self.path / 'config.yaml')
        print(self.path)
        print(self.path / 'config.yaml')
        self.queue = queue.Queue()        
        self.task = None
        self.timebase = self.settings['daq_settings']['timebase']
        self._set_sample_rate()
        self.channels = self.settings['daq_settings']['channels']
        

    def _set_sample_rate(self):    
        self.sample_rate = TIMEBASE_MAP[self.timebase]        
        self.display_samples = int(self.sample_rate * self.timebase * NUM_HORIZONTAL_DIVS)
        self.buff_transfer = self.display_samples // NUM_HORIZONTAL_DIVS  # amount of samples transferred with every nidaqmx callback is the number of samples in one division
        self.nidaqmx_buffer_size = self.buff_transfer * NIDAQMX_BUFFER_MULTIPLIER
        self.ring_buffer = deque(maxlen=self.display_samples * RING_BUFFER_SCREEN_MULTIPLIER)  # data for plotting and calculating measurements

    def start_task(self):
        # create and configure nidaqmx task
        try:
            self.task = nidaqmx.Task()
            for channel in self.channels:
                if not channel['enable']:
                    continue
                self.task.ai_channels.add_ai_voltage_chan(channel['name'], min_val=channel['range']*(-1), max_val=channel['range'], terminal_config=TerminalConfiguration.NRSE)
            self.task.timing.cfg_samp_clk_timing(
                rate=self.sample_rate,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=self.nidaqmx_buffer_size
            )
            self.task.register_every_n_samples_acquired_into_buffer_event(self.buff_transfer, self._buff_callback)
            self.task.start()
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
        self.channels[chan_index]['volts_per_div'] = volts_per_div_val
        thresholds = sorted(MEASURING_RANGE_THRESHOLDS.keys())
        for treshold in thresholds:
            if volts_per_div_val <= treshold:
                new_range = MEASURING_RANGE_THRESHOLDS[treshold]
                break
        else:
            new_range = MEASURING_RANGE_THRESHOLDS[thresholds[-1]]
        if self.channels[chan_index]['range'] != new_range:
            self.channels[chan_index]['range'] = new_range
            self.restart_task()
     
    def _buff_callback(self, task_handle, event_type, n_samples, callback_data):
        try:
            data = self.task.read(n_samples) # type: ignore
            self.queue.put(np.array(data))
        except DaqError as e:
            self.error_occurred.emit(f"NIDAQmx Error: {e}")
        return 0
    
    def poll_queue(self):
        temp_data = []
        while not self.queue.empty():
            temp_data.append(self.queue.get_nowait())
        if not temp_data:
            return
        temp_data = np.concatenate(temp_data)
        self.ring_buffer.extend(temp_data)

        latest_data = np.array(self.ring_buffer)[-self.display_samples:]
        self.graph_data.emit(latest_data)