import sys
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QLabel, QLineEdit
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QDoubleValidator
import pyqtgraph as pg

class OscilloscopeApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Virtual Oscilloscope")
        self.setGeometry(100, 100, 1200, 800)  # Width, Height, X Position, Y Position

        # Central Widget and Layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QHBoxLayout(self.central_widget)

        # Create the plot area using PyQtGraph
        self.plot_widget = pg.PlotWidget(title="Signal Plot")
        self.layout.addWidget(self.plot_widget, 1)  # Plot takes up most of the space

        # Create the control panel
        self.create_controls()

        # Initialize time and signal data
        self.time = np.linspace(0, 1, 1000)  # Time vector (1 second)
        self.amplitude = np.sin(2 * np.pi * 5 * self.time)  # Initial sine wave (5 Hz)

        # Plot the initial signal
        self.plot_curve = self.plot_widget.plot(self.time, self.amplitude)

        # Set up a timer to update the plot every 50 ms
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(50)  # Update every 50ms (20 Hz)

        self.show()

    def create_controls(self):
        # Control Panel Layout
        self.control_panel = QWidget(self)
        self.control_layout = QVBoxLayout(self.control_panel)

        self.control_panel.setFixedWidth(250)  # Control panel width
        self.layout.addWidget(self.control_panel)

        # Timebase Control (Text box and arrows)
        self.timebase_label = QLabel("Timebase (ms/div): ", self)
        self.control_layout.addWidget(self.timebase_label)

        self.timebase_input = QLineEdit(self)
        self.timebase_input.setText(str(10))  # Default value
        self.timebase_input.setAlignment(Qt.AlignCenter)
        self.timebase_input.setValidator(QDoubleValidator())  # Ensure valid float input
        self.control_layout.addWidget(self.timebase_input)

        self.timebase_arrows_layout = QHBoxLayout()
        self.increase_timebase_btn = QPushButton("↑", self)
        self.decrease_timebase_btn = QPushButton("↓", self)
        self.timebase_arrows_layout.addWidget(self.decrease_timebase_btn)
        self.timebase_arrows_layout.addWidget(self.increase_timebase_btn)
        self.control_layout.addLayout(self.timebase_arrows_layout)

        self.increase_timebase_btn.clicked.connect(self.increase_timebase)
        self.decrease_timebase_btn.clicked.connect(self.decrease_timebase)

        # Volts per division control (Text box and arrows)
        self.volts_label = QLabel("Volts/div: ", self)
        self.control_layout.addWidget(self.volts_label)

        self.volts_input = QLineEdit(self)
        self.volts_input.setText(str(10))  # Default value
        self.volts_input.setAlignment(Qt.AlignCenter)
        self.volts_input.setValidator(QDoubleValidator())  # Ensure valid float input
        self.control_layout.addWidget(self.volts_input)

        self.volts_arrows_layout = QHBoxLayout()
        self.increase_volts_btn = QPushButton("↑", self)
        self.decrease_volts_btn = QPushButton("↓", self)
        self.volts_arrows_layout.addWidget(self.decrease_volts_btn)
        self.volts_arrows_layout.addWidget(self.increase_volts_btn)
        self.control_layout.addLayout(self.volts_arrows_layout)

        self.increase_volts_btn.clicked.connect(self.increase_volts)
        self.decrease_volts_btn.clicked.connect(self.decrease_volts)

        # Start Button
        self.start_button = QPushButton("Start", self)
        self.start_button.clicked.connect(self.start_signal)
        self.control_layout.addWidget(self.start_button)

        # Save Button
        self.save_button = QPushButton("Save", self)
        self.save_button.clicked.connect(self.save_signal)
        self.control_layout.addWidget(self.save_button)

    def increase_timebase(self):
        current_value = float(self.timebase_input.text())
        new_value = current_value + 1  # Increase by 1ms per division
        self.timebase_input.setText(str(new_value))
        self.update_plot()

    def decrease_timebase(self):
        current_value = float(self.timebase_input.text())
        if current_value > 1:  # Ensure timebase doesn't go below 1ms/div
            new_value = current_value - 1  # Decrease by 1ms per division
            self.timebase_input.setText(str(new_value))
            self.update_plot()

    def increase_volts(self):
        current_value = float(self.volts_input.text())
        new_value = current_value + 1  # Increase by 1V per division
        self.volts_input.setText(str(new_value))
        self.update_plot()

    def decrease_volts(self):
        current_value = float(self.volts_input.text())
        if current_value > 1:  # Ensure volts/div doesn't go below 1V/div
            new_value = current_value - 1  # Decrease by 1V per division
            self.volts_input.setText(str(new_value))
            self.update_plot()

    def start_signal(self):
        # Start or restart the signal generation
        self.time = np.linspace(0, 1, 1000)
        self.amplitude = np.sin(2 * np.pi * 5 * self.time)  # 5 Hz default
        self.plot_curve.setData(self.time, self.amplitude)

    def save_signal(self):
        # Save the current waveform data to a file (e.g., CSV or image)
        np.savetxt("signal.csv", np.column_stack((self.time, self.amplitude)))
        print("Signal Saved")

    def update_plot(self):
        # Get current control values
        timebase = float(self.timebase_input.text())  # Timebase in ms/div
        volts = float(self.volts_input.text())  # Volts per division

        # Modify the signal properties based on control values
        frequency = 1 / timebase  # Set frequency inversely proportional to timebase
        self.amplitude = volts * np.sin(2 * np.pi * frequency * self.time)
        self.plot_curve.setData(self.time, self.amplitude)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    oscilloscope = OscilloscopeApp()
    sys.exit(app.exec_())