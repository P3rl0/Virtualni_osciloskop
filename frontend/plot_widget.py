import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt
from backend.config import CHANNEL_COLORS, NUM_HORIZONTAL_DIVS, NUM_VERTICAL_DIVS

_HALF_V = NUM_VERTICAL_DIVS / 2


class OscilloscopeWidget(pg.PlotWidget):
    def __init__(self, parent=None):
        pg.setConfigOption("background", "#111118")
        pg.setConfigOption("foreground", "#cccccc")
        super().__init__(parent)

        self.setAntialiasing(False)
        self.showGrid(x=True, y=True, alpha=0.25)

        for ax in ("bottom", "left"):
            self.getAxis(ax).setTickSpacing(major=1, minor=0.2)

        self.setRange(
            xRange=[0, NUM_HORIZONTAL_DIVS],
            yRange=[-_HALF_V, _HALF_V],
            disableAutoRange=True,
        )
        self.setLimits(
            xMin=0, xMax=NUM_HORIZONTAL_DIVS,
            yMin=-_HALF_V * 2, yMax=_HALF_V * 2,
        )
        self.getAxis("bottom").setLabel("Divisions")
        self.getAxis("left").setLabel("Divisions")

        self._curves = [
            self.plot(pen=pg.mkPen(color, width=1.5))
            for color in CHANNEL_COLORS
        ]
        for c in self._curves:
            c.setVisible(False)

        self._trigger_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(color="#ffff00", style=Qt.DashLine, width=1),
        )
        self.addItem(self._trigger_line)

    def update_traces(self, display_data, active_indices, channel_params,
                      trigger_level_v, trigger_chan_idx):
        """Update all channel traces and the trigger level line.

        Args:
            display_data:      np.ndarray shape (n_active, display_samples)
            active_indices:    list of physical channel indices (0..3)
            channel_params:    dict {phys_idx: {'volts_per_div': float, 'vertical_offset': float}}
            trigger_level_v:   trigger level in volts
            trigger_chan_idx:  physical index of the trigger source channel
        """
        for c in self._curves:
            c.setVisible(False)

        if display_data.size == 0:
            return

        n_samples = display_data.shape[1]
        x = np.linspace(0, NUM_HORIZONTAL_DIVS, n_samples)

        for i, phys_idx in enumerate(active_indices):
            params = channel_params.get(phys_idx, {})
            vdiv   = params.get("volts_per_div", 1.0)
            offset = params.get("vertical_offset", 0.0)
            if vdiv == 0:
                continue
            y_div = (display_data[i] + offset) / vdiv
            self._curves[phys_idx].setData(x, y_div)
            self._curves[phys_idx].setVisible(True)

        trig_params = channel_params.get(trigger_chan_idx, {})
        trig_vdiv   = trig_params.get("volts_per_div", 1.0)
        trig_offset = trig_params.get("vertical_offset", 0.0)
        if trig_vdiv:
            self._trigger_line.setValue((trigger_level_v + trig_offset) / trig_vdiv)

    def clear_traces(self):
        for c in self._curves:
            c.setVisible(False)
