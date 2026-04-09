import nidaqmx
from nidaqmx.constants import AcquisitionType

def create_ai_task(channels, sample_rate, samples_per_channel):
    task = nidaqmx.Task()
    
    for ch in channels:
        task.ai_channels.add_ai_voltage_chan(ch)
    
    task.timing.cfg_samp_clk_timing(
        rate=sample_rate,
        sample_mode=AcquisitionType.CONTINUOUS,
        samps_per_chan=samples_per_channel
    )
    
    return task