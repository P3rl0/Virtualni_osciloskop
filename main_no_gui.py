import sys
from backend.daq import DaqWorker
from PyQt5.QtCore import QCoreApplication, QTimer
from PyQt5.QtWidgets import QApplication
import numpy as np
import matplotlib.pyplot as plt

app = QApplication(sys.argv)

test = DaqWorker()
test.stop_task()
test.start_task()

# setup plot
plt.ion()  # interactive mode
fig, ax = plt.subplots()
line, = ax.plot([], [])
ax.set_title("DAQ Data")
ax.set_xlabel("Samples")
ax.set_ylabel("Voltage")

def tick():
    test.poll_queue()
    data = np.array(test.ring_buffer)[-test.display_samples:]
    if data.size == 0:
        return

    line.set_xdata(np.arange(len(data)))
    line.set_ydata(data)

    ax.relim()
    ax.autoscale_view()

    fig.canvas.draw()
    fig.canvas.flush_events()

timer = QTimer()
timer.timeout.connect(tick)
timer.start(33)

sys.exit(app.exec_())