from pathlib import Path
from nidaqmx.constants import TerminalConfiguration, AcquisitionType, Coupling
import yaml

def load_yaml(file_path: Path, area: str = 'all') -> dict:
    with open(file_path, 'r') as file:
        settings = yaml.safe_load(file)
    # map conversions
    for channel in settings['daq_settings']['channels']:
        channel['terminal_config'] = TERMINAL_CONFIG_MAP[channel['terminal_config']]
        channel['coupling'] = COUPLING_MAP[channel['coupling']]

    if area == 'all':
        return settings
    if area == 'daq':
        return settings['daq_settings']
    if area == 'processing':
        return settings['processor_settings']
    else:   # default to all if area is not recognized
        return settings

def save_yaml(data: dict, file_path: Path):
    with open(file_path, 'w') as file:
        yaml.dump(data, file)

def pack_settings():
    # TODO - pack settings dict for saving
    pass

##################################################################
#  region BACKEND CONFIG
RING_BUFFER_SCREEN_MULTIPLIER = 4  # ring buffer size is display_samples * this multiplier
NIDAQMX_BUFFER_MULTIPLIER = 20  # nidaqmx buffer size is buff_transfer * this multiplier
NUM_HORIZONTAL_DIVS = 12
NUM_VERTICAL_DIVS = 10
VOLTS_PER_DIV = [100e-6, 200e-6, 500e-6, 1e-3, 2e-3, 5e-3, 10e-3, 20e-3, 50e-3, 100e-3, 200e-3, 500e-3, 1.0, 2.0, 5.0]  # in volts/div
MEASURING_RANGE_THRESHOLDS = {
    # volts_per_div : +-min/max_val
    0.005: 0.1,
    0.01: 0.2,
    0.025: 0.5,
    0.05:   1,
    0.1:   2,
    0.25:   5,
    0.5:  10,
}
TIMEBASE_MAP = {
    # seconds_per_div : sample_rate
    0.0001:  1_000_000,   # 100µs/div
    0.0002:  500_000,     # 200µs/div
    0.0005:  200_000,     # 500µs/div
    0.001:   100_000,     # 1ms/div
    0.002:   50_000,      # 2ms/div
    0.005:   20_000,      # 5ms/div
    0.010:   10_000,      # 10ms/div
    0.020:   5_000,       # 20ms/div
    0.050:   2_000,       # 50ms/div
    0.100:   1_000,       # 100ms/div
    0.200:   500,         # 200ms/div
    0.500:   200,         # 500ms/div
    1.000:   100,         # 1s/div
    5.000:   20,          # 5s/div
}
TERMINAL_CONFIG_MAP = {
    'RSE': TerminalConfiguration.RSE,
    'NRSE': TerminalConfiguration.NRSE,
    'DIFF': TerminalConfiguration.DIFF,
    'PSEUD_ODIFF': TerminalConfiguration.PSEUDO_DIFF
}
COUPLING_MAP = {
    'DC': Coupling.DC,
    'AC': Coupling.AC
}
PROBE_ATTENUATION = [1.0, 10.0]
# endregion BACKEND CONFIG

# region PROCESSING CONFIG
TRIGGER_TYPE = ['auto', 'normal', 'single']
TRIGG_SLOPE = ['rising', 'falling']
# endregion PROCESSING CONFIG

# region FRONTEND CONFIG
CHANNEL_COLORS = ['#FF0000', '#00FF00', "#2A61F6", '#FFFF00']
# endregion FRONTEND CONFIG