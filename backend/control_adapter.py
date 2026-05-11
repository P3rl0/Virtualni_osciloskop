"""Small UI-to-backend adapter helpers.

The frontend can keep using human-oriented values such as "CH1", "1 ms/div",
and "500 mV/div". This module converts those values to backend-safe channel
indices and numeric settings before calling hardware workers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.config import COUPLING_NAMES, TIMEBASE_MAP, VOLTS_PER_DIV

_UNIT_SI = {
    "ns": 1e-9,
    "µs": 1e-6,
    "us": 1e-6,
    "ms": 1e-3,
    "s": 1.0,
    "mV": 1e-3,
    "V": 1.0,
}


class FrontendAdapterError(ValueError):
    """Raised when a frontend control value cannot be mapped safely."""


def parse_scale_label(text: str) -> float:
    """Parse labels like '1 ms/div' or '500 mV/div' into SI floats."""
    parts = text.strip().split()
    if len(parts) != 2:
        raise FrontendAdapterError(f"Invalid scale label: {text!r}")
    unit = parts[1].replace("/div", "")
    if unit not in _UNIT_SI:
        raise FrontendAdapterError(f"Unsupported unit in scale label {text!r}")
    try:
        value = float(parts[0]) * _UNIT_SI[unit]
    except ValueError as exc:
        raise FrontendAdapterError(f"Invalid numeric value in scale label {text!r}") from exc
    return value


def frontend_channel_to_backend(channel: int | str) -> int:
    """Convert CH1..CH4 / 1..4 frontend channels to 0..3 backend indices."""
    if isinstance(channel, str):
        channel = channel.strip().upper().replace("CH", "")
    try:
        frontend_index = int(channel)
    except (TypeError, ValueError) as exc:
        raise FrontendAdapterError(f"Invalid channel value: {channel!r}") from exc
    backend_index = frontend_index - 1
    if backend_index < 0:
        raise FrontendAdapterError(f"Frontend channels are 1-based; got {frontend_index}.")
    return backend_index


def backend_channel_to_frontend(channel_index: int) -> int:
    if channel_index < 0:
        raise FrontendAdapterError(f"Backend channel index must be >= 0; got {channel_index}.")
    return channel_index + 1


def parse_supported_timebase(label: str) -> float:
    value = parse_scale_label(label)
    if value not in TIMEBASE_MAP:
        raise FrontendAdapterError(
            f"Unsupported timebase {label!r} ({value:g} s/div). "
            f"Supported values: {supported_timebase_labels()}"
        )
    return value


def parse_supported_volts_per_div(label: str) -> float:
    value = parse_scale_label(label)
    if value not in VOLTS_PER_DIV:
        raise FrontendAdapterError(
            f"Unsupported volts/div {label!r} ({value:g} V/div). "
            f"Supported values: {supported_volts_per_div_labels()}"
        )
    return value


def supported_timebase_labels() -> list[str]:
    return [_format_timebase(value) for value in sorted(TIMEBASE_MAP)]


def supported_volts_per_div_labels() -> list[str]:
    return [_format_voltage(value) + "/div" for value in VOLTS_PER_DIV]


@dataclass(slots=True)
class DaqControlAdapter:
    """Thin adapter from frontend controls to DaqWorker/TriggerProcessor setters."""

    daq_worker: Any

    def set_timebase_from_label(self, label: str) -> None:
        self.daq_worker.set_timebase(parse_supported_timebase(label))

    def set_channel_enabled(self, frontend_channel: int | str, enabled: bool) -> None:
        self.daq_worker.set_channel_enable(bool(enabled), frontend_channel_to_backend(frontend_channel))

    def set_channel_volts_per_div_from_label(self, frontend_channel: int | str, label: str) -> None:
        self.daq_worker.set_volts_per_div(
            parse_supported_volts_per_div(label),
            frontend_channel_to_backend(frontend_channel),
        )

    def set_channel_coupling(self, frontend_channel: int | str, coupling: str) -> None:
        if coupling not in COUPLING_NAMES:
            raise FrontendAdapterError(
                f"Unsupported coupling {coupling!r}. Backend supports {list(COUPLING_NAMES)}."
            )
        self.daq_worker.set_coupling(coupling, frontend_channel_to_backend(frontend_channel))

    def set_channel_vertical_offset(self, frontend_channel: int | str, offset_div: float) -> None:
        self.daq_worker.set_vertical_offset(float(offset_div), frontend_channel_to_backend(frontend_channel))

    def set_trigger_source(self, frontend_channel: int | str) -> None:
        self.daq_worker.trigger.set_trigger_channel(frontend_channel_to_backend(frontend_channel))

    def set_trigger_level(self, level_v: float) -> None:
        self.daq_worker.trigger.set_trigger_level(float(level_v))

    def set_trigger_slope(self, rising: bool) -> None:
        self.daq_worker.trigger.set_trigger_slope("rising" if rising else "falling")

    def set_trigger_type(self, trigger_type: str) -> None:
        self.daq_worker.trigger.set_trigger_type(trigger_type)


@dataclass(slots=True)
class SignalGenControlAdapter:
    """Separate adapter for signal-generator controls.

    Keep this separate from DaqControlAdapter so DAQ acquisition and signal
    generation remain independent backend services.
    """

    signal_gen_worker: Any

    def set_waveform(self, waveform: str) -> None:
        self.signal_gen_worker.set_waveform(waveform)

    def set_frequency(self, frequency_hz: float) -> None:
        self.signal_gen_worker.set_frequency(float(frequency_hz))

    def set_amplitude(self, amplitude_vpp: float) -> None:
        self.signal_gen_worker.set_amplitude(float(amplitude_vpp))

    def set_offset(self, offset_v: float) -> None:
        self.signal_gen_worker.set_offset(float(offset_v))

    def set_output(self, enabled: bool) -> None:
        self.signal_gen_worker.set_output(bool(enabled))


def _format_timebase(value: float) -> str:
    if value < 1e-6:
        return f"{value * 1e9:g} ns/div"
    if value < 1e-3:
        return f"{value * 1e6:g} µs/div"
    if value < 1:
        return f"{value * 1e3:g} ms/div"
    return f"{value:g} s/div"


def _format_voltage(value: float) -> str:
    if abs(value) < 1:
        return f"{value * 1e3:g} mV"
    return f"{value:g} V"
