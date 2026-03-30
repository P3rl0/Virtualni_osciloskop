import nidaqmx
from nidaqmx.stream_readers import AnalogSingleChannelReader
import numpy as np

samples = 1000
data = np.zeros(samples)

with nidaqmx.Task() as task:
    task.ai_channels.add_ai_voltage_chan("Dev2/ai0")
    task.timing.cfg_samp_clk_timing(rate=10000, samps_per_chan=samples)

    reader = AnalogSingleChannelReader(task.in_stream)
    reader.read_many_sample(data, number_of_samples_per_channel=samples)
    print(data)