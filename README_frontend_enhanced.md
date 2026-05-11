# Frontend enhanced version

Run from the project root with:

```powershell
python -m frontend.app
```

Highlights:

- Simulation and DAQ modes remain separate.
- DAQ hardware errors are shown in a non-blocking diagnostics panel instead of modal popups.
- DAQ mode performs a preflight check before trying to start a hardware task.
- Scope control updates in DAQ mode are debounced to reduce repeated task restarts.
- Autoset works from the latest visible simulation or DAQ waveform.
- Simulation supports SINE, SQUARE, TRIANGLE, RAMP, NOISE, and PULSE profiles.
- Measurement selection is available from the control panel.
- Signal-generator controls remain separate from DAQ acquisition.
- A small settings dialog can update the NI device prefix, GPIB address, and save-on-exit flag in `backend/config.yaml`.
- Logging writes to `logs/oscilloscope.log`.

Manual hardware testing is still required for NI-DAQmx and PyVISA behavior.
