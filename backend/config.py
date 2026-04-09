# backend/config.py

# -----------------------------
# Device and Channel Settings
# -----------------------------

# List of analog input channels to use (DAQ device name / channel number)
# Example: ['Dev1/ai0', 'Dev1/ai1'] for two channels
CHANNELS = ['Dev1/ai0', 'Dev1/ai1']

# Analog input voltage range for all channels (tuple: min, max)
VOLTAGE_RANGE = (-10.0, 10.0)

# -----------------------------
# Sampling Settings
# -----------------------------

# Sampling rate in Hz
SAMPLE_RATE = 10000  # 10 kHz default

# Number of samples per channel in DAQ internal buffer
# Should be larger than the chunk you want to read each time
SAMPLES_PER_CHANNEL = 5000

# -----------------------------
# Trigger Settings (optional)
# -----------------------------

# Software trigger threshold in volts
TRIGGER_THRESHOLD = 0.0

# Trigger type: 'rising', 'falling', or None
TRIGGER_TYPE = 'rising'

# Pre-trigger samples (number of samples to keep before trigger)
PRE_TRIGGER_SAMPLES = 500

# -----------------------------
# Buffer Settings
# -----------------------------

# How many samples to keep in the circular buffer per channel
BUFFER_SIZE = 10000