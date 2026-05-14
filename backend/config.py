from pathlib import Path
from nidaqmx.constants import TerminalConfiguration, Coupling
import yaml


def load_yaml(file_path: Path, area: str = "all") -> dict:
    with open(file_path, "r") as file:
        settings = yaml.safe_load(file)
    # map conversions + derive range from volts_per_div
    thresholds = sorted(MEASURING_RANGE_THRESHOLDS.keys())
    for channel in settings["daq_settings"]["channels"]:
        channel["terminal_config"] = TERMINAL_CONFIG_MAP[channel["terminal_config"]]
        channel["coupling"] = COUPLING_MAP[channel["coupling"]]
        vpd = channel["volts_per_div"]
        for t in thresholds:
            if vpd <= t:
                channel["range"] = MEASURING_RANGE_THRESHOLDS[t]
                break
        else:
            channel["range"] = MEASURING_RANGE_THRESHOLDS[thresholds[-1]]

    if area == "all":
        return settings
    if area == "daq":
        return settings["daq_settings"]
    if area == "processing":
        return settings["processor_settings"]
    if area == "signal_gen":
        return settings["signal_gen_settings"]
    if area == "app":
        return settings["app_settings"]
    else:  # default to all if area is not recognized
        return settings


def save_yaml(data: dict, file_path: Path):
    with open(file_path, "w") as file:
        yaml.dump(data, file, default_flow_style=False, sort_keys=False)


def pack_settings(
    daq_settings: dict,
    processor_settings: dict,
    measurements: list,
    signal_gen_settings: dict,
    app_settings: dict,
) -> dict:
    """Convert live settings dicts into a YAML-serializable dict.

    Reverses the enum conversions done by load_yaml (terminal_config, coupling)
    and strips the derived 'range' field so the output can round-trip through
    save_yaml → load_yaml without corruption.

    Args:
        daq_settings:        DaqWorker.settings
        processor_settings:  TriggerProcessor.settings
        measurements:        Measurements.measurements  — kept separate because
                             TriggerProcessor and Measurements each load their own
                             copy of processor_settings, so trigger.settings["measurements"]
                             is never updated at runtime; the live list lives in
                             Measurements.measurements instead.
        signal_gen_settings: SignalGenWorker.settings
        app_settings:        dict loaded with load_yaml(area="app")

    Returns:
        dict ready to pass directly to save_yaml()
    """
    inv_terminal = {v: k for k, v in TERMINAL_CONFIG_MAP.items()}
    inv_coupling = {v: k for k, v in COUPLING_MAP.items()}

    channels = []
    for ch in daq_settings["channels"]:
        channels.append(
            {
                "enable": ch["enable"],
                "name": ch["name"],
                "terminal_config": inv_terminal[ch["terminal_config"]],
                "probe_attenuation": ch["probe_attenuation"],
                "coupling": inv_coupling[ch["coupling"]],
                "volts_per_div": ch["volts_per_div"],
                "vertical_offset": ch["vertical_offset"],
                # "range" is derived from volts_per_div in load_yaml — do NOT save
            }
        )

    return {
        "daq_settings": {
            "timebase": daq_settings["timebase"],
            "channels": channels,
        },
        "processor_settings": {
            "trigger_type": processor_settings["trigger_type"],
            "trigger_level": processor_settings["trigger_level"],
            "trigger_offset": processor_settings["trigger_offset"],
            "trigger_slope": processor_settings["trigger_slope"],
            "trigger_channel": processor_settings["trigger_channel"],
            "measurements": measurements,
        },
        "signal_gen_settings": dict(signal_gen_settings),
        "app_settings": dict(app_settings),
    }


##################################################################
#  region BACKEND CONFIG
RING_BUFFER_SCREEN_MULTIPLIER = 4  # ring buffer size is display_samples * this multiplier
NIDAQMX_BUFFER_MULTIPLIER = 20  # nidaqmx buffer size is buff_transfer * this multiplier
NUM_HORIZONTAL_DIVS = 12
NUM_VERTICAL_DIVS = 10
VOLTS_PER_DIV = [
    100e-6,
    200e-6,
    500e-6,
    1e-3,
    2e-3,
    5e-3,
    10e-3,
    20e-3,
    50e-3,
    100e-3,
    200e-3,
    500e-3,
    1.0,
    2.0,
    5.0,
]  # in volts/div
MEASURING_RANGE_THRESHOLDS = {
    # volts_per_div : +-min/max_val
    0.005: 0.1,
    0.01: 0.2,
    0.025: 0.5,
    0.05: 1,
    0.1: 2,
    0.25: 5,
    0.5: 10,
}
TIMEBASE_MAP = {
    # seconds_per_div : sample_rate
    0.0001: 1_000_000,  # 100µs/div
    0.0002: 500_000,  # 200µs/div
    0.0005: 200_000,  # 500µs/div
    0.001: 100_000,  # 1ms/div
    0.002: 50_000,  # 2ms/div
    0.005: 20_000,  # 5ms/div
    0.010: 10_000,  # 10ms/div
    0.020: 5_000,  # 20ms/div
    0.050: 2_000,  # 50ms/div
    0.100: 1_000,  # 100ms/div
    0.200: 500,  # 200ms/div
    0.500: 200,  # 500ms/div
    1.000: 100,  # 1s/div
    5.000: 20,  # 5s/div
}
TERMINAL_CONFIG_MAP = {
    "RSE": TerminalConfiguration.RSE,
    "NRSE": TerminalConfiguration.NRSE,
    "DIFF": TerminalConfiguration.DIFF,
    # "PSEUD_ODIFF" accepted as legacy alias on load; PSEUDO_DIFF is canonical on save.
    "PSEUD_ODIFF": TerminalConfiguration.PSEUDO_DIFF,
    "PSEUDO_DIFF": TerminalConfiguration.PSEUDO_DIFF,
}
COUPLING_MAP = {"DC": Coupling.DC, "AC": Coupling.AC}
PROBE_ATTENUATION = [1.0, 10.0]
# endregion BACKEND CONFIG

# region PROCESSING CONFIG
TRIGGER_TYPE = ["auto", "normal", "single"]
TRIGG_SLOPE = ["rising", "falling"]
HYST_MULTIPLIER = 0.03
# endregion PROCESSING CONFIG

# region SIGNAL GEN CONFIG
SIGGEN_WAVEFORMS = ["SIN", "SQU", "TRI", "RAMP"]  # 33120A standard waveforms
SIGGEN_LOAD = ["INF", "50"]  # High-Z = INF, 50 Ω = 50
SIGGEN_FREQ_MIN = 100e-6  # 100 µHz (33120A spec)
SIGGEN_FREQ_MAX = 15e6  # 15 MHz (33120A spec)
SIGGEN_AMP_MIN = 0.01  # 10 mVpp into 50 Ω
SIGGEN_AMP_MAX = 20.0  # 20 Vpp into Hi-Z (10 Vpp into 50 Ω)
SIGGEN_OFFSET_MAX = 5.0  # ± 5 V max offset
SIGGEN_DUTY_MIN = 20.0  # 20% duty cycle (33120A limit)
SIGGEN_DUTY_MAX = 80.0  # 80% duty cycle (33120A limit)
# endregion SIGNAL GEN CONFIG

# region FRONTEND CONFIG
CHANNEL_COLORS = ["#FF0000", "#00FF00", "#2A61F6", "#FFFF00"]
# endregion FRONTEND CONFIG
