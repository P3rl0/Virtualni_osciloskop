"""Helpers for loading the NI-DAQmx runtime DLL safely.

This module intentionally has no import-time side effects. Call
``load_nidaqmx_dll()`` before importing ``nidaqmx`` on Windows.
"""

from __future__ import annotations

import ctypes
import sys


class NidaqmxDllLoadError(RuntimeError):
    """Raised when the NI-DAQmx runtime DLL cannot be loaded."""


def load_nidaqmx_dll(dll_name: str = "nicaiu", *, required: bool = True) -> bool:
    """Load the NI-DAQmx runtime DLL on Windows.

    Args:
        dll_name: NI-DAQmx DLL name. ``nicaiu`` is the normal NI-DAQmx runtime DLL.
        required: If True, raise a clear exception when the DLL cannot be loaded.
            If False, return False instead.

    Returns:
        True when the DLL was loaded, False when no load was needed or when loading
        failed with ``required=False``.

    Raises:
        NidaqmxDllLoadError: On Windows, when the DLL cannot be loaded and
        ``required=True``.
    """
    if sys.platform != "win32":
        # NI's DLL-loading workaround is only relevant on Windows.
        return False

    try:
        ctypes.WinDLL(dll_name)
        return True
    except OSError as exc:
        message = (
            f"Could not load NI-DAQmx runtime DLL {dll_name!r}. "
            "Make sure NI-DAQmx is installed, the device driver is available, "
            "and the DLL is discoverable through the system PATH."
        )
        if required:
            raise NidaqmxDllLoadError(message) from exc
        return False
