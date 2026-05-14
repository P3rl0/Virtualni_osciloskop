"""Force NI-DAQmx's nicaiu.dll to load with the correct dependency search order.

Must run BEFORE the first `import nidaqmx` (or any nidaqmx submodule like
nidaqmx.constants). If something else — typically PyQt5 — loads first, Windows'
DLL search may resolve nicaiu.dll's MSVC runtime dependencies to incompatible
versions, causing an access violation when DAQmx C functions are later called.

Import this from `backend/__init__.py` so any `from backend.* import ...`
triggers it transparently.
"""
import sys

if sys.platform == "win32":
    import ctypes
    try:
        ctypes.WinDLL("nicaiu")
    except OSError:
        pass  # NI-DAQmx not installed — nidaqmx import will fail with a clearer error
