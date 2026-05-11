"""Configuration loading, validation, conversion, and persistence.

The YAML file stores plain serializable values. ``load_yaml`` validates those
values before hardware workers use them, then converts DAQ-specific strings to
NI-DAQmx enum values only for the DAQ runtime path.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

try:
    from utils.dll_fix import load_nidaqmx_dll

    load_nidaqmx_dll(required=False)
    from nidaqmx.constants import Coupling, TerminalConfiguration

    _NIDAQMX_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # noqa: BLE001 - keep config importable for non-DAQ code paths
    Coupling = None  # type: ignore[assignment]
    TerminalConfiguration = None  # type: ignore[assignment]
    _NIDAQMX_IMPORT_ERROR = exc


class ConfigValidationError(ValueError):
    """Raised when config.yaml contains invalid or unsupported values."""


##################################################################
# region BACKEND CONFIG
RING_BUFFER_SCREEN_MULTIPLIER = 4
NIDAQMX_BUFFER_MULTIPLIER = 20
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
]

MEASURING_RANGE_THRESHOLDS = {
    0.005: 0.1,
    0.01: 0.2,
    0.025: 0.5,
    0.05: 1,
    0.1: 2,
    0.25: 5,
    0.5: 10,
}

TIMEBASE_MAP = {
    0.0001: 1_000_000,
    0.0002: 500_000,
    0.0005: 200_000,
    0.001: 100_000,
    0.002: 50_000,
    0.005: 20_000,
    0.010: 10_000,
    0.020: 5_000,
    0.050: 2_000,
    0.100: 1_000,
    0.200: 500,
    0.500: 200,
    1.000: 100,
    5.000: 20,
}

TERMINAL_CONFIG_NAMES = ("RSE", "NRSE", "DIFF", "PSEUDO_DIFF", "PSEUD_ODIFF")
COUPLING_NAMES = ("DC", "AC")

if TerminalConfiguration is not None and Coupling is not None:
    TERMINAL_CONFIG_MAP = {
        "RSE": TerminalConfiguration.RSE,
        "NRSE": TerminalConfiguration.NRSE,
        "DIFF": TerminalConfiguration.DIFF,
        "PSEUDO_DIFF": TerminalConfiguration.PSEUDO_DIFF,
        # Backwards-compatible spelling used in the older project file.
        "PSEUD_ODIFF": TerminalConfiguration.PSEUDO_DIFF,
    }
    COUPLING_MAP = {"DC": Coupling.DC, "AC": Coupling.AC}
else:
    TERMINAL_CONFIG_MAP = {}
    COUPLING_MAP = {}

PROBE_ATTENUATION = [1.0, 10.0]
# endregion BACKEND CONFIG

# region PROCESSING CONFIG
TRIGGER_TYPE = ["auto", "normal", "single"]
TRIGG_SLOPE = ["rising", "falling"]
HYST_MULTIPLIER = 0.03
MEASUREMENT_NAMES = (
    "mean",
    "rms",
    "min",
    "max",
    "peak_to_peak",
    "frequency",
    "rise_time",
    "fall_time",
)
# endregion PROCESSING CONFIG

# region SIGNAL GEN CONFIG
SIGGEN_WAVEFORMS = ["SIN", "SQU", "TRI", "RAMP"]
SIGGEN_LOAD = ["INF", "50"]
SIGGEN_FREQ_MIN = 100e-6
SIGGEN_FREQ_MAX = 15e6
SIGGEN_AMP_MIN = 0.01
SIGGEN_AMP_MAX = 20.0
SIGGEN_AMP_MAX_50_OHM = 10.0
SIGGEN_OFFSET_MAX = 5.0
SIGGEN_DUTY_MIN = 20.0
SIGGEN_DUTY_MAX = 80.0
SIGGEN_GPIB_MIN = 0
SIGGEN_GPIB_MAX = 30
# endregion SIGNAL GEN CONFIG

# region FRONTEND CONFIG
CHANNEL_COLORS = ["#FF0000", "#00FF00", "#2A61F6", "#FFFF00"]
# endregion FRONTEND CONFIG


VALID_AREAS = {"all", "daq", "processing", "signal_gen", "app"}


def load_yaml(file_path: Path, area: str = "all") -> dict[str, Any]:
    """Load, validate, and convert a config YAML file.

    ``area`` lets hardware workers validate only the section they need. This is
    important because signal-generator code should not require NI-DAQmx to be
    importable, and DAQ code should not open hardware until its config is known
    to be valid.
    """
    if area not in VALID_AREAS:
        raise ConfigValidationError(
            f"Unknown config area {area!r}. Valid areas: {sorted(VALID_AREAS)}"
        )

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            settings = yaml.safe_load(file)
    except OSError as exc:
        raise ConfigValidationError(f"Could not read config file {file_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigValidationError(f"Invalid YAML in {file_path}: {exc}") from exc

    if not isinstance(settings, dict):
        raise ConfigValidationError("config.yaml must contain a top-level mapping.")

    if area == "daq":
        daq_settings = _require_mapping(settings, "daq_settings")
        validate_daq_settings(daq_settings)
        return _convert_daq_settings(daq_settings)

    if area == "processing":
        processor_settings = _require_mapping(settings, "processor_settings")
        channels = _require_list(_require_mapping(settings, "daq_settings"), "channels")
        validate_processor_settings(processor_settings, channel_count=len(channels))
        return deepcopy(processor_settings)

    if area == "signal_gen":
        signal_gen_settings = _require_mapping(settings, "signal_gen_settings")
        validate_signal_gen_settings(signal_gen_settings)
        return deepcopy(signal_gen_settings)

    if area == "app":
        app_settings = _require_mapping(settings, "app_settings")
        validate_app_settings(app_settings)
        return deepcopy(app_settings)

    validate_config(settings)
    converted = deepcopy(settings)
    converted["daq_settings"] = _convert_daq_settings(settings["daq_settings"])
    return converted


def save_yaml(data: dict[str, Any], file_path: Path) -> None:
    """Atomically save a YAML-serializable settings dictionary."""
    tmp_path = file_path.with_suffix(file_path.suffix + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, default_flow_style=False, sort_keys=False)
        tmp_path.replace(file_path)
    except OSError as exc:
        raise ConfigValidationError(f"Could not save config file {file_path}: {exc}") from exc


def pack_settings(
    daq_settings: dict[str, Any],
    processor_settings: dict[str, Any],
    measurements: list[dict[str, bool]],
    signal_gen_settings: dict[str, Any],
    app_settings: dict[str, Any],
) -> dict[str, Any]:
    """Convert live settings into a YAML-serializable dictionary."""
    channels = []
    for index, ch in enumerate(daq_settings["channels"]):
        channels.append(
            {
                "enable": ch["enable"],
                "name": ch["name"],
                "terminal_config": _terminal_config_to_string(ch["terminal_config"]),
                "probe_attenuation": float(ch["probe_attenuation"]),
                "coupling": _coupling_to_string(ch["coupling"]),
                "volts_per_div": float(ch["volts_per_div"]),
                "vertical_offset": float(ch["vertical_offset"]),
            }
        )
        _validate_channel(channels[-1], index)

    packed = {
        "daq_settings": {
            "timebase": float(daq_settings["timebase"]),
            "channels": channels,
        },
        "processor_settings": {
            "trigger_type": processor_settings["trigger_type"],
            "trigger_level": float(processor_settings["trigger_level"]),
            "trigger_offset": float(processor_settings["trigger_offset"]),
            "trigger_slope": processor_settings["trigger_slope"],
            "trigger_channel": int(processor_settings["trigger_channel"]),
            "measurements": measurements,
        },
        "signal_gen_settings": dict(signal_gen_settings),
        "app_settings": dict(app_settings),
    }
    validate_config(packed)
    return packed


def validate_config(settings: dict[str, Any]) -> None:
    daq_settings = _require_mapping(settings, "daq_settings")
    processor_settings = _require_mapping(settings, "processor_settings")
    signal_gen_settings = _require_mapping(settings, "signal_gen_settings")
    app_settings = _require_mapping(settings, "app_settings")

    validate_daq_settings(daq_settings)
    channel_count = len(daq_settings["channels"])
    validate_processor_settings(processor_settings, channel_count=channel_count)
    validate_signal_gen_settings(signal_gen_settings)
    validate_app_settings(app_settings)


def validate_daq_settings(settings: dict[str, Any]) -> None:
    _require_keys(settings, ["timebase", "channels"], "daq_settings")
    timebase = _require_number(settings, "timebase", "daq_settings")
    if float(timebase) not in TIMEBASE_MAP:
        raise ConfigValidationError(
            f"daq_settings.timebase={timebase!r} is not supported. "
            f"Valid values: {sorted(TIMEBASE_MAP)}"
        )

    channels = _require_list(settings, "channels")
    if not channels:
        raise ConfigValidationError("daq_settings.channels must contain at least one channel.")
    for index, channel in enumerate(channels):
        if not isinstance(channel, dict):
            raise ConfigValidationError(f"daq_settings.channels[{index}] must be a mapping.")
        _validate_channel(channel, index)


def validate_processor_settings(settings: dict[str, Any], *, channel_count: int) -> None:
    _require_keys(
        settings,
        [
            "trigger_type",
            "trigger_level",
            "trigger_offset",
            "trigger_slope",
            "trigger_channel",
            "measurements",
        ],
        "processor_settings",
    )
    _require_choice(settings, "trigger_type", TRIGGER_TYPE, "processor_settings")
    _require_number(settings, "trigger_level", "processor_settings")
    _require_number(settings, "trigger_offset", "processor_settings")
    _require_choice(settings, "trigger_slope", TRIGG_SLOPE, "processor_settings")

    trigger_channel = settings["trigger_channel"]
    if not isinstance(trigger_channel, int) or isinstance(trigger_channel, bool):
        raise ConfigValidationError("processor_settings.trigger_channel must be an integer.")
    if not 0 <= trigger_channel < channel_count:
        raise ConfigValidationError(
            f"processor_settings.trigger_channel={trigger_channel} is outside "
            f"the available channel range 0..{channel_count - 1}."
        )

    measurements = _require_list(settings, "measurements")
    if len(measurements) != channel_count:
        raise ConfigValidationError(
            "processor_settings.measurements length must match daq_settings.channels length."
        )
    for channel_index, entry in enumerate(measurements):
        if not isinstance(entry, dict):
            raise ConfigValidationError(
                f"processor_settings.measurements[{channel_index}] must be a mapping."
            )
        unknown = set(entry) - set(MEASUREMENT_NAMES)
        if unknown:
            raise ConfigValidationError(
                f"Unknown measurement(s) for channel {channel_index}: {sorted(unknown)}. "
                f"Valid measurements: {list(MEASUREMENT_NAMES)}"
            )
        for measurement, enabled in entry.items():
            if not isinstance(enabled, bool):
                raise ConfigValidationError(
                    f"processor_settings.measurements[{channel_index}].{measurement} must be true/false."
                )


def validate_signal_gen_settings(settings: dict[str, Any]) -> None:
    _require_keys(
        settings,
        [
            "gpib_address",
            "waveform",
            "frequency",
            "amplitude",
            "offset",
            "load",
            "duty_cycle",
            "output_enabled",
        ],
        "signal_gen_settings",
    )
    gpib = settings["gpib_address"]
    if not isinstance(gpib, int) or isinstance(gpib, bool):
        raise ConfigValidationError("signal_gen_settings.gpib_address must be an integer.")
    if not SIGGEN_GPIB_MIN <= gpib <= SIGGEN_GPIB_MAX:
        raise ConfigValidationError(
            f"signal_gen_settings.gpib_address={gpib} is outside "
            f"{SIGGEN_GPIB_MIN}..{SIGGEN_GPIB_MAX}."
        )

    _require_choice(settings, "waveform", SIGGEN_WAVEFORMS, "signal_gen_settings")
    frequency = _require_number(settings, "frequency", "signal_gen_settings")
    if not SIGGEN_FREQ_MIN <= float(frequency) <= SIGGEN_FREQ_MAX:
        raise ConfigValidationError(
            f"signal_gen_settings.frequency={frequency!r} is outside "
            f"{SIGGEN_FREQ_MIN}..{SIGGEN_FREQ_MAX} Hz."
        )

    load = _require_choice(settings, "load", SIGGEN_LOAD, "signal_gen_settings")
    amplitude = _require_number(settings, "amplitude", "signal_gen_settings")
    amp_max = siggen_amplitude_max_for_load(load)
    if not SIGGEN_AMP_MIN <= float(amplitude) <= amp_max:
        raise ConfigValidationError(
            f"signal_gen_settings.amplitude={amplitude!r} is outside "
            f"{SIGGEN_AMP_MIN}..{amp_max} Vpp for load={load!r}."
        )

    offset = _require_number(settings, "offset", "signal_gen_settings")
    if abs(float(offset)) > SIGGEN_OFFSET_MAX:
        raise ConfigValidationError(
            f"signal_gen_settings.offset={offset!r} exceeds ±{SIGGEN_OFFSET_MAX} V."
        )

    duty = _require_number(settings, "duty_cycle", "signal_gen_settings")
    if not SIGGEN_DUTY_MIN <= float(duty) <= SIGGEN_DUTY_MAX:
        raise ConfigValidationError(
            f"signal_gen_settings.duty_cycle={duty!r} is outside "
            f"{SIGGEN_DUTY_MIN}..{SIGGEN_DUTY_MAX} %."
        )

    if not isinstance(settings["output_enabled"], bool):
        raise ConfigValidationError("signal_gen_settings.output_enabled must be true/false.")


def validate_app_settings(settings: dict[str, Any]) -> None:
    _require_keys(settings, ["save_on_exit"], "app_settings")
    if not isinstance(settings["save_on_exit"], bool):
        raise ConfigValidationError("app_settings.save_on_exit must be true/false.")


def siggen_amplitude_max_for_load(load: str) -> float:
    if load == "50":
        return SIGGEN_AMP_MAX_50_OHM
    return SIGGEN_AMP_MAX


def measuring_range_for_volts_per_div(volts_per_div: float) -> float:
    thresholds = sorted(MEASURING_RANGE_THRESHOLDS.keys())
    for threshold in thresholds:
        if volts_per_div <= threshold:
            return MEASURING_RANGE_THRESHOLDS[threshold]
    return MEASURING_RANGE_THRESHOLDS[thresholds[-1]]


def _convert_daq_settings(settings: dict[str, Any]) -> dict[str, Any]:
    if _NIDAQMX_IMPORT_ERROR is not None:
        raise ConfigValidationError(
            "NI-DAQmx is not available, so DAQ settings cannot be converted for hardware use. "
            f"Original import/DLL error: {_NIDAQMX_IMPORT_ERROR}"
        )

    converted = deepcopy(settings)
    converted["timebase"] = float(converted["timebase"])
    for channel in converted["channels"]:
        channel["terminal_config"] = TERMINAL_CONFIG_MAP[channel["terminal_config"]]
        channel["coupling"] = COUPLING_MAP[channel["coupling"]]
        channel["probe_attenuation"] = float(channel["probe_attenuation"])
        channel["volts_per_div"] = float(channel["volts_per_div"])
        channel["vertical_offset"] = float(channel["vertical_offset"])
        channel["range"] = measuring_range_for_volts_per_div(channel["volts_per_div"])
    return converted


def _validate_channel(channel: dict[str, Any], index: int) -> None:
    prefix = f"daq_settings.channels[{index}]"
    _require_keys(
        channel,
        [
            "enable",
            "name",
            "terminal_config",
            "probe_attenuation",
            "coupling",
            "volts_per_div",
            "vertical_offset",
        ],
        prefix,
    )
    if not isinstance(channel["enable"], bool):
        raise ConfigValidationError(f"{prefix}.enable must be true/false.")
    if not isinstance(channel["name"], str) or not channel["name"].strip():
        raise ConfigValidationError(f"{prefix}.name must be a non-empty string.")
    _require_choice(channel, "terminal_config", TERMINAL_CONFIG_NAMES, prefix)
    attenuation = _require_number(channel, "probe_attenuation", prefix)
    if float(attenuation) not in PROBE_ATTENUATION:
        raise ConfigValidationError(
            f"{prefix}.probe_attenuation={attenuation!r} is not supported. "
            f"Valid values: {PROBE_ATTENUATION}"
        )
    _require_choice(channel, "coupling", COUPLING_NAMES, prefix)
    volts_per_div = _require_number(channel, "volts_per_div", prefix)
    if float(volts_per_div) not in VOLTS_PER_DIV:
        raise ConfigValidationError(
            f"{prefix}.volts_per_div={volts_per_div!r} is not supported. "
            f"Valid values: {VOLTS_PER_DIV}"
        )
    _require_number(channel, "vertical_offset", prefix)


def _terminal_config_to_string(value: Any) -> str:
    for name, enum_value in TERMINAL_CONFIG_MAP.items():
        if value == enum_value:
            return "PSEUDO_DIFF" if name == "PSEUD_ODIFF" else name
    if isinstance(value, str) and value in TERMINAL_CONFIG_NAMES:
        return "PSEUDO_DIFF" if value == "PSEUD_ODIFF" else value
    raise ConfigValidationError(f"Unsupported terminal configuration value: {value!r}")


def _coupling_to_string(value: Any) -> str:
    for name, enum_value in COUPLING_MAP.items():
        if value == enum_value:
            return name
    if isinstance(value, str) and value in COUPLING_NAMES:
        return value
    raise ConfigValidationError(f"Unsupported coupling value: {value!r}")


def _require_keys(mapping: dict[str, Any], required: list[str], prefix: str) -> None:
    missing = [key for key in required if key not in mapping]
    if missing:
        raise ConfigValidationError(f"{prefix} is missing required key(s): {missing}")


def _require_mapping(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    value = mapping.get(key)
    if not isinstance(value, dict):
        raise ConfigValidationError(f"{key} must be a mapping.")
    return value


def _require_list(mapping: dict[str, Any], key: str) -> list[Any]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise ConfigValidationError(f"{key} must be a list.")
    return value


def _require_number(mapping: dict[str, Any], key: str, prefix: str) -> int | float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigValidationError(f"{prefix}.{key} must be a number.")
    return value


def _require_choice(
    mapping: dict[str, Any], key: str, valid_values: list[str] | tuple[str, ...], prefix: str
) -> str:
    value = mapping.get(key)
    if value not in valid_values:
        raise ConfigValidationError(
            f"{prefix}.{key}={value!r} is invalid. Valid values: {list(valid_values)}"
        )
    return str(value)
