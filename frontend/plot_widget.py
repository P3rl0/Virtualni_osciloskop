import os
# Pin pyqtgraph to PyQt5 before its first import. Without this, pyqtgraph
# auto-detects in the order PyQt6 -> PySide6 -> PyQt5 -> PySide2 and can
# crash on machines with a partial PyQt6/PySide6 install lying around.
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt5")

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from backend.config import CHANNEL_COLORS, NUM_HORIZONTAL_DIVS, NUM_VERTICAL_DIVS

_TRIGGER_LINES_TIMEOUT_MS = 2000  # how long the trigger lines stay visible after a change

_HALF_V = NUM_VERTICAL_DIVS / 2
_INDICATOR_FONT = QFont()
_INDICATOR_FONT.setPointSize(14)
_INDICATOR_FONT.setBold(True)


class OscilloscopeWidget(pg.PlotWidget):
    # Emitted when user drags the trigger-position line. Value is x in divisions.
    trigger_position_dragged = pyqtSignal(float)

    def __init__(self, parent=None):
        pg.setConfigOption("background", "#111118")
        pg.setConfigOption("foreground", "#cccccc")
        super().__init__(parent)

        self.setAntialiasing(False)
        self.showGrid(x=True, y=True, alpha=0.25)

        for ax in ("bottom", "left"):
            self.getAxis(ax).setTickSpacing(major=1, minor=0.2)

        # Default view = fully zoomed out, i.e. exactly NUM_HORIZONTAL_DIVS
        # wide × NUM_VERTICAL_DIVS tall. setLimits uses the SAME bounds so
        # scroll-wheel zoom-out can't expand past the natural range — the
        # trigger arrow at y=_HALF_V then sits flush with the top edge in
        # every zoom state. User can still zoom IN with the wheel.
        self.disableAutoRange()
        self.setRange(
            xRange=[0, NUM_HORIZONTAL_DIVS],
            yRange=[-_HALF_V, _HALF_V],
            padding=0,
        )
        self.setLimits(
            xMin=0, xMax=NUM_HORIZONTAL_DIVS,
            yMin=-_HALF_V, yMax=_HALF_V,
        )
        self.getAxis("bottom").setLabel("Divisions")
        self.getAxis("left").setLabel("Divisions")

        self._curves = [
            self.plot(pen=pg.mkPen(color, width=1.5))
            for color in CHANNEL_COLORS
        ]
        for c in self._curves:
            c.setData([], [])

        self._trigger_line = pg.InfiniteLine(
            angle=0,
            movable=False,
            pen=pg.mkPen(color="#ffff00", style=Qt.DashLine, width=1),
        )
        self._trigger_line.setVisible(False)  # hidden until user touches trigger settings
        self.addItem(self._trigger_line)

        # ── Trigger horizontal position (draggable; vertical line) ──────
        self._trigger_pos_line = pg.InfiniteLine(
            pos=NUM_HORIZONTAL_DIVS / 2,
            angle=90,
            movable=True,
            bounds=[0, NUM_HORIZONTAL_DIVS],
            pen=pg.mkPen(color="#ffff00", style=Qt.DashLine, width=1),
        )
        self._trigger_pos_line.setVisible(False)  # hidden until user touches trigger settings
        self.addItem(self._trigger_pos_line)
        self._trigger_pos_line.sigPositionChanged.connect(self._on_trigger_pos_dragged)

        # Auto-hide timer for the trigger lines; the top arrow stays visible always.
        self._trigger_lines_timer = QTimer(self)
        self._trigger_lines_timer.setInterval(_TRIGGER_LINES_TIMEOUT_MS)
        self._trigger_lines_timer.setSingleShot(True)
        self._trigger_lines_timer.timeout.connect(self._hide_trigger_lines)

        # Trigger-position arrow on top edge (▼)
        self._trigger_pos_arrow = pg.TextItem("▼", color="#ffff00", anchor=(0.5, 0))
        self._trigger_pos_arrow.setFont(_INDICATOR_FONT)
        self._trigger_pos_arrow.setPos(NUM_HORIZONTAL_DIVS / 2, _HALF_V)
        self.addItem(self._trigger_pos_arrow)

        # ── Channel zero-volt indicators on left edge (►) ───────────────
        self._zero_arrows = []
        for color in CHANNEL_COLORS:
            arr = pg.TextItem("►", color=color, anchor=(0, 0.5))
            arr.setFont(_INDICATOR_FONT)
            arr.setVisible(False)
            self._zero_arrows.append(arr)
            self.addItem(arr)

        # ── Cursors (in divisions; hidden by default) ───────────────────
        cur_pen_t = pg.mkPen(color="#00d0ff", style=Qt.DashLine, width=1)
        cur_pen_v = pg.mkPen(color="#ff66cc", style=Qt.DashLine, width=1)
        self.t_cursor_a = pg.InfiniteLine(pos=4, angle=90, movable=True, pen=cur_pen_t,
                                          label="T1", labelOpts={"position": 0.95, "color": "#00d0ff"})
        self.t_cursor_b = pg.InfiniteLine(pos=8, angle=90, movable=True, pen=cur_pen_t,
                                          label="T2", labelOpts={"position": 0.95, "color": "#00d0ff"})
        self.v_cursor_a = pg.InfiniteLine(pos=-2, angle=0, movable=True, pen=cur_pen_v,
                                          label="V1", labelOpts={"position": 0.05, "color": "#ff66cc"})
        self.v_cursor_b = pg.InfiniteLine(pos=2, angle=0, movable=True, pen=cur_pen_v,
                                          label="V2", labelOpts={"position": 0.05, "color": "#ff66cc"})
        for c in (self.t_cursor_a, self.t_cursor_b, self.v_cursor_a, self.v_cursor_b):
            c.setVisible(False)
            self.addItem(c)

    def set_time_cursors_visible(self, visible: bool):
        self.t_cursor_a.setVisible(visible)
        self.t_cursor_b.setVisible(visible)

    def set_voltage_cursors_visible(self, visible: bool):
        self.v_cursor_a.setVisible(visible)
        self.v_cursor_b.setVisible(visible)

    def update_overlay(self, active_indices, channel_params,
                       trigger_level_v, trigger_chan_idx,
                       trigger_offset_s, timebase_s):
        """Reposition non-trace items: channel zero-volt arrows, trigger level
        line, trigger-position line, and trigger arrow. Cheap; safe to call
        on every settings change so the indicators don't go stale when no
        frame is being emitted (normal/single mode awaiting a trigger).

        Args:
            active_indices:    list of physical channel indices (0..3)
            channel_params:    dict {phys_idx: {'volts_per_div': float, 'vertical_offset': float}}
            trigger_level_v:   trigger level in volts
            trigger_chan_idx:  physical index of the trigger source channel
            trigger_offset_s:  trigger horizontal offset in seconds (0 = centered)
            timebase_s:        current timebase in seconds/division
        """
        active_set = set(active_indices)
        for i, arr in enumerate(self._zero_arrows):
            if i in active_set:
                params = channel_params.get(i, {})
                vdiv   = params.get("volts_per_div", 1.0)
                offset = params.get("vertical_offset", 0.0)
                if vdiv > 0:
                    arr.setPos(0, offset / vdiv)
                    arr.setVisible(True)
            else:
                arr.setVisible(False)

        if timebase_s > 0:
            x_trig = NUM_HORIZONTAL_DIVS / 2 + trigger_offset_s / timebase_s
            x_trig = max(0.0, min(float(NUM_HORIZONTAL_DIVS), x_trig))
            self._trigger_pos_line.blockSignals(True)
            self._trigger_pos_line.setValue(x_trig)
            self._trigger_pos_line.blockSignals(False)
            self._trigger_pos_arrow.setPos(x_trig, _HALF_V)

        trig_params = channel_params.get(trigger_chan_idx, {})
        trig_vdiv   = trig_params.get("volts_per_div", 1.0)
        trig_offset = trig_params.get("vertical_offset", 0.0)
        if trig_vdiv:
            self._trigger_line.setValue((trigger_level_v + trig_offset) / trig_vdiv)

    def update_traces(self, display_data, active_indices, channel_params):
        """Redraw the four channel curves. Indicator overlay is updated separately
        via update_overlay()."""
        if display_data.size == 0:
            for c in self._curves:
                c.setData([], [])
            return

        n_samples = display_data.shape[1]
        x = np.linspace(0, NUM_HORIZONTAL_DIVS, n_samples)

        active_set = set(active_indices)
        for j, c in enumerate(self._curves):
            if j not in active_set:
                c.setData([], [])

        for i, phys_idx in enumerate(active_indices):
            params = channel_params.get(phys_idx, {})
            vdiv   = params.get("volts_per_div", 1.0)
            offset = params.get("vertical_offset", 0.0)
            if vdiv == 0:
                continue
            y_div = (display_data[i] + offset) / vdiv
            self._curves[phys_idx].setData(x, y_div)

    def _on_trigger_pos_dragged(self):
        x = float(self._trigger_pos_line.value())
        self._trigger_pos_arrow.setPos(x, _HALF_V)
        # Keep the lines visible while the user is actively dragging.
        self.show_trigger_lines()
        self.trigger_position_dragged.emit(x)

    def show_trigger_lines(self):
        """Reveal the trigger level + position lines and (re)start the auto-hide timer.
        Call this from any handler that mutates trigger settings."""
        self._trigger_line.setVisible(True)
        self._trigger_pos_line.setVisible(True)
        self._trigger_lines_timer.start()

    def _hide_trigger_lines(self):
        self._trigger_line.setVisible(False)
        self._trigger_pos_line.setVisible(False)

    def clear_traces(self):
        for c in self._curves:
            c.setData([], [])
