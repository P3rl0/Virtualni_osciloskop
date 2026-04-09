# Osciloskop
- Texas Instruments PCI-6251
- Nidaqmx

### Gradivo
- https://nidaqmx-python.readthedocs.io/en/stable/
- https://www.pythonguis.com/pyqt5-tutorial/

### TODO
- analog in -> graf
- računanje
	- average
	- RMS
	- rise time
	- max
	- min
	- amplitued
	- p2p
	- freq
- auto range
- triggering


# Signalni generator
- PyVISA


# Random

virtual_oscilloscope/
│
├── main.py                 # Entry point; initializes backend & GUI
├── backend/
│   ├── __init__.py
│   ├── daq_manager.py      # Handles DAQ tasks, acquisition, triggers
│   ├── buffer.py           # Circular buffer or data storage class
│   └── config.py           # Default sampling rates, channels, voltage ranges
│
├── frontend/
│   ├── __init__.py
│   ├── gui.py              # PyQt5 window, layouts, and widgets
│   ├── plot_widget.py      # PyQtGraph plotting widget class
│   └── controls.py         # Sliders, buttons, triggers, UI controls
│
├── utils/
│   ├── __init__.py
│   └── helpers.py          # Utility functions, e.g., triggers, conversions
│
└── requirements.txt        # Required Python packages