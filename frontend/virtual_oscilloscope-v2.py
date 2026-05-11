import sys
# import nidaqmx
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QSlider, QLabel
from PyQt5.QtCore import QTimer, Qt
import pyqtgraph as pg
import pyvisa

class VirtualOscilloscope(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Virtual Oscilloscope")
        self.setGeometry(100, 100, 800, 600)
        self.layout = QVBoxLayout()

        # Setup PyQtGraph for waveform display
        self.plot_widget = pg.PlotWidget()
        self.layout.addWidget(self.plot_widget)

        # Volts per division control
        self.volts_slider = QSlider(Qt.Horizontal)
        self.volts_slider.setRange(1, 20)
        self.volts_slider.setValue(10)
        self.layout.addWidget(QLabel("Volts/Div"))
        self.layout.addWidget(self.volts_slider)

        # Time per division control
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setRange(1, 100)
        self.time_slider.setValue(10)
        self.layout.addWidget(QLabel("Time/Div"))
        self.layout.addWidget(self.time_slider)

        # Trigger button
        self.trigger_button = QPushButton("Trigger")
        self.layout.addWidget(self.trigger_button)

        self.setLayout(self.layout)

        # Initialize the plot data
        self.x_data = []
        self.y_data = []

        # Setup communication with the hardware
        self.setup_hardware()

        # Start the plot update loop
        self.plot_data()

    def plot_data(self):
        # Example: Generate data for plotting (replace with actual DAQ acquisition)
        self.x_data = [i for i in range(100)]
        self.y_data = [5 * (1 if i % 2 == 0 else -1) for i in range(100)]

        # Plot the waveform
        self.plot_widget.plot(self.x_data, self.y_data, pen='g')

        # Re-run the update after 50ms
        QTimer.singleShot(50, self.plot_data)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VirtualOscilloscope()
    window.show()
    sys.exit(app.exec_())