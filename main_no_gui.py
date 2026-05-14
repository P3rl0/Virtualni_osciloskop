import sys
from backend.daq import DaqWorker
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
import numpy as np
import matplotlib.pyplot as plt

app = QApplication(sys.argv)

test = DaqWorker()
test.start_task()

# setup plot
plt.ion()  # interactive mode
fig, ax = plt.subplots()
(line,) = ax.plot([], [])
ax.set_title("DAQ Data")
ax.set_xlabel("Samples")
ax.set_ylabel("Voltage")


def on_data(display):
    if display.size == 0:
        return
    channel_data = display[0]  # first active channel
    line.set_xdata(np.arange(len(channel_data)))
    line.set_ydata(channel_data)
    ax.relim()
    ax.autoscale_view()
    fig.canvas.draw()
    fig.canvas.flush_events()


test.graph_data.connect(on_data)
test.measurements_data.connect(lambda r: print(r))


def tick():
    test.poll_queue()


timer = QTimer()
timer.timeout.connect(tick)
timer.start(33)

sys.exit(app.exec_())
