"""Formatting and lightweight value conversion helpers for the frontend."""

from __future__ import annotations

from typing import Any

_UNIT_SI = {
    "ns": 1e-9,
    "µs": 1e-6,
    "us": 1e-6,
    "ms": 1e-3,
    "s": 1.0,
    "µV": 1e-6,
    "uV": 1e-6,
    "mV": 1e-3,
    "V": 1.0,
}


def parse_scale(text: str) -> float:
    """Parse a UI label such as '1 ms/div' or '500 mV/div' into an SI value."""
    parts = text.strip().split()
    if len(parts) != 2:
        raise ValueError(f"Invalid scale label: {text!r}")
    unit = parts[1].replace("/div", "")
    if unit not in _UNIT_SI:
        raise ValueError(f"Unsupported unit in scale label: {text!r}")
    return float(parts[0]) * _UNIT_SI[unit]


def fmt_time(seconds: float | None) -> str:
    if seconds is None or seconds <= 0:
        return "---"
    if seconds < 1e-6:
        return f"{seconds * 1e9:.2f} ns"
    if seconds < 1e-3:
        return f"{seconds * 1e6:.2f} µs"
    if seconds < 1:
        return f"{seconds * 1e3:.2f} ms"
    return f"{seconds:.4f} s"


def fmt_freq(hertz: float | None) -> str:
    if hertz is None or hertz <= 0:
        return "---"
    if hertz >= 1e6:
        return f"{hertz / 1e6:.3f} MHz"
    if hertz >= 1e3:
        return f"{hertz / 1e3:.3f} kHz"
    return f"{hertz:.2f} Hz"


def fmt_volt(volts: float | None) -> str:
    if volts is None:
        return "---"
    if abs(volts) < 1:
        return f"{volts * 1e3:.2f} mV"
    return f"{volts:.4f} V"


def normalize_backend_measurements(results: dict[Any, Any]) -> dict[int, dict[str, float | None]]:
    """Convert backend measurement results to frontend CH1..CH4 display keys.

    Backend results are expected to be keyed by ``(backend_channel_index, measurement_name)``.
    Frontend display channels are 1-based.
    """
    normalized: dict[int, dict[str, float | None]] = {ch: {} for ch in range(1, 5)}

    for key, value in results.items():
        if not isinstance(key, tuple) or len(key) != 2:
            continue
        backend_ch, meas_name = key
        try:
            frontend_ch = int(backend_ch) + 1
        except (TypeError, ValueError):
            continue
        if frontend_ch not in normalized:
            continue

        if meas_name == "peak_to_peak":
            normalized[frontend_ch]["Vpp"] = value
        elif meas_name == "rms":
            normalized[frontend_ch]["Vrms"] = value
        elif meas_name == "frequency":
            normalized[frontend_ch]["Freq"] = value
            normalized[frontend_ch]["Period"] = 1.0 / value if value else None
        elif meas_name == "mean":
            normalized[frontend_ch]["Mean"] = value
        elif meas_name == "min":
            normalized[frontend_ch]["Min"] = value
        elif meas_name == "max":
            normalized[frontend_ch]["Max"] = value
        elif meas_name == "rise_time":
            normalized[frontend_ch]["Rise"] = value
        elif meas_name == "fall_time":
            normalized[frontend_ch]["Fall"] = value

    return normalized
