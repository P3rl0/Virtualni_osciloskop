"""Main frontend window for the virtual oscilloscope."""

from __future__ import annotations

import logging

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from frontend.backend_controller import BackendController, DataMode
from frontend.controls import ControlPanel
from frontend.formatting import normalize_backend_measurements
from frontend.measurement_panel import MeasurementPanel
from frontend.plot_display import PlotDisplay
from frontend.settings_dialog import SettingsDialog
from frontend.signal_gen_panel import SignalGenPanel
from frontend.status_panel import StatusPanel
from frontend.styles import STYLESHEET

logger = logging.getLogger(__name__)


class OscilloscopeWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DSO-1000  |  Virtual Oscilloscope")
        self.setMinimumSize(1240, 760)
        self.resize(1480, 900)
        self.running = True
        self._last_error_message = ""

        self.backend = BackendController(self)
        self.backend.daq_data_ready.connect(self._on_daq_data)
        self.backend.measurements_ready.connect(self._on_backend_measurements)
        self.backend.error_occurred.connect(self._on_backend_error)
        self.backend.status_changed.connect(self._on_backend_status)
        self.backend.single_capture_completed.connect(self._on_single_capture_completed)
        self.backend.daq_unavailable.connect(self._on_daq_unavailable)
        self.backend.preflight_completed.connect(self._on_preflight_completed)
        self.backend.sample_rate_changed.connect(lambda text: self.control_panel.set_status("SAMPLE RATE", text))
        self.backend.signal_gen_connection_changed.connect(self._on_signal_gen_connection_changed)

        self._daq_apply_timer = QTimer(self)
        self._daq_apply_timer.setSingleShot(True)
        self._daq_apply_timer.setInterval(250)
        self._daq_apply_timer.timeout.connect(self._apply_daq_controls)

        central = QWidget()
        self.setCentralWidget(central)

        outer = QHBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(10)

        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        self.plot_display = PlotDisplay()
        left_col.addWidget(self.plot_display, stretch=1)

        self.meas_panel = MeasurementPanel()
        left_col.addWidget(self.meas_panel, stretch=0)

        self.status_panel = StatusPanel()
        left_col.addWidget(self.status_panel, stretch=0)

        outer.addLayout(left_col, stretch=1)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        self.control_panel = ControlPanel(
            on_change_cb=self._on_controls_changed,
            runstop_cb=self._on_runstop_toggled,
            single_cb=self._single_capture,
            autoset_cb=self._autoset,
            settings_cb=self._open_settings,
        )
        right_col.addWidget(self.control_panel, stretch=1)

        self.signal_gen_panel = SignalGenPanel(self.backend)
        self.signal_gen_panel.setFixedWidth(335)
        right_col.addWidget(self.signal_gen_panel, stretch=0)

        outer.addLayout(right_col, stretch=0)

        self.setStyleSheet(STYLESHEET)
        self.control_panel.trigger().set_running(True)
        self._on_controls_changed()
        self.status_panel.info("Ready")

    def _channel_params(self) -> dict[int, dict]:
        control_panel = self.control_panel
        return {
            ch: {
                "vdiv": control_panel.ch(ch).vdiv_si(),
                "vdiv_label": control_panel.ch(ch).vdiv_label(),
                "offset_div": control_panel.ch(ch).offset_div(),
                "enabled": control_panel.ch(ch).is_enabled(),
                "coupling": control_panel.ch(ch).coupling_str(),
            }
            for ch in range(1, 5)
        }

    def _trigger_params(self) -> dict:
        trigger = self.control_panel.trigger()
        return {
            "source": trigger.source_channel(),
            "source_label": trigger.source_label(),
            "level_v": trigger.level_volts(),
            "rising": trigger.is_rising_edge(),
        }

    def _current_mode(self) -> DataMode:
        return DataMode.from_label(self.control_panel.data_mode_label())

    def _on_controls_changed(self) -> None:
        mode = self._current_mode()
        self.meas_panel.set_enabled_metrics(self.control_panel.selected_measurement_labels())

        if mode != self.backend.mode:
            self.backend.set_mode(mode)
            self.control_panel.set_status("MODE", mode.value)
            self.status_panel.set_status("MODE", mode.value)
            if mode == DataMode.SIMULATION:
                self.control_panel.set_status("BACKEND", "IDLE")
                self.status_panel.set_status("DAQ", "idle")
                self.plot_display.clear()
                self.meas_panel.clear()
            elif self.running:
                self.control_panel.set_status("BACKEND", "PREFLIGHT")
                self.status_panel.set_status("DAQ", "preflight")

        if mode == DataMode.SIMULATION:
            self._daq_apply_timer.stop()
            if self.running:
                measurements = self.plot_display.render_simulation(
                    self.control_panel.time_per_div(),
                    self._channel_params(),
                    self._trigger_params(),
                    self.control_panel.simulation_profile(),
                )
                self.meas_panel.update_measurements({ch: values or {} for ch, values in measurements.items()})
            return

        self.backend.apply_measurement_settings(self.control_panel.selected_measurement_backend_names())
        self._daq_apply_timer.start()

    def _apply_daq_controls(self) -> None:
        if self._current_mode() != DataMode.DAQ:
            return
        self.backend.apply_scope_settings(
            self.control_panel.time_label(),
            self._channel_params(),
            self._trigger_params(),
        )
        if self.running:
            started = self.backend.start_acquisition()
            if not started:
                self._fallback_to_simulation("DAQ did not start; switched back to simulation mode.")

    def _on_runstop_toggled(self, checked: bool) -> None:
        self.running = checked
        self.control_panel.trigger().set_running(checked)
        if self._current_mode() == DataMode.SIMULATION:
            if self.running:
                self._on_controls_changed()
            return

        if checked:
            self._daq_apply_timer.start()
        else:
            self._daq_apply_timer.stop()
            self.backend.stop_acquisition()
            self.control_panel.set_status("BACKEND", "STOPPED")
            self.status_panel.set_status("DAQ", "stopped")

    def _single_capture(self) -> None:
        if self._current_mode() == DataMode.SIMULATION:
            if self.running:
                self.running = False
                self.control_panel.trigger().set_running(False)
            self._on_controls_changed()
            self.control_panel.trigger().set_single_fired()
            self.status_panel.info("Simulation single capture displayed")
            return

        self.running = False
        self.control_panel.trigger().set_running(False)
        started = self.backend.single_capture()
        if started:
            self.control_panel.set_status("BACKEND", "SINGLE")
            self.status_panel.set_status("DAQ", "single armed")
        else:
            self._fallback_to_simulation("DAQ single capture could not start; switched back to simulation mode.")

    def _autoset(self) -> None:
        if self._current_mode() == DataMode.SIMULATION and self.running:
            # Ensure there is fresh data for the selected simulation profile.
            self.plot_display.render_simulation(
                self.control_panel.time_per_div(),
                self._channel_params(),
                self._trigger_params(),
                self.control_panel.simulation_profile(),
            )

        suggestion = self.plot_display.suggest_autoset(self._channel_params())
        if suggestion is None:
            self.status_panel.info("Autoset needs at least one visible waveform")
            return

        self.control_panel.set_time_label(suggestion.time_label, emit_change=False)
        for ch, label in suggestion.volts_labels.items():
            self.control_panel.set_channel_vdiv_label(ch, label, emit_change=False)
        self.control_panel.set_trigger_level_volts(suggestion.trigger_level_v, emit_change=False)
        self.status_panel.info("Autoset applied")
        self._on_controls_changed()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(parent=self)
        if dialog.exec_() == dialog.Accepted:
            self.backend.reload_configuration()
            self.status_panel.info("Settings saved. Hardware workers will reload config on next use.")
            logger.info("Settings dialog saved")

    def _on_daq_data(self, display_data: object, active_backend_indices: object) -> None:
        try:
            active = [int(ch) for ch in active_backend_indices]
            self.plot_display.update_live_data(
                display_data,
                active,
                self._channel_params(),
                self._trigger_params(),
            )
        except Exception as exc:  # noqa: BLE001
            self._on_backend_error(f"Plot update error: {exc}")

    def _on_backend_measurements(self, results: dict) -> None:
        normalized = normalize_backend_measurements(results)
        self.meas_panel.update_measurements(normalized)

    def _on_single_capture_completed(self) -> None:
        self.control_panel.trigger().set_single_fired()
        self.control_panel.set_status("BACKEND", "SINGLE DONE")
        self.status_panel.set_status("DAQ", "single done")

    def _on_backend_status(self, message: str) -> None:
        self.status_panel.info(message)
        if "running" in message.lower():
            self.control_panel.set_status("BACKEND", "RUNNING")
            self.status_panel.set_status("DAQ", "running")
        elif "stopped" in message.lower():
            self.control_panel.set_status("BACKEND", "STOPPED")
            self.status_panel.set_status("DAQ", "stopped")
        elif "unavailable" in message.lower():
            self.control_panel.set_status("BACKEND", "UNAVAILABLE")
            self.status_panel.set_status("DAQ", "unavailable")

    def _on_backend_error(self, message: str) -> None:
        # Non-blocking: record and show in the status panel, but do not pop up a
        # modal dialog. Duplicate hardware errors are common during failed init.
        if message == self._last_error_message:
            return
        self._last_error_message = message
        self.control_panel.set_status("BACKEND", "ERROR")
        self.status_panel.set_status("DAQ", "error")
        self.status_panel.error(message)
        logger.error(message)

    def _on_daq_unavailable(self, message: str) -> None:
        self._fallback_to_simulation("DAQ unavailable; switched back to simulation mode.")
        self._on_backend_error(message)

    def _on_preflight_completed(self, ok: bool, message: str) -> None:
        if ok:
            self.status_panel.info(message)
        else:
            self.status_panel.error(message)

    def _on_signal_gen_connection_changed(self, connected: bool) -> None:
        self.status_panel.set_status("SIG GEN", "connected" if connected else "disconnected")
        self.status_panel.info("Signal generator connected" if connected else "Signal generator disconnected")

    def _fallback_to_simulation(self, status_message: str) -> None:
        """Leave DAQ mode without recursively triggering another DAQ start."""
        self._daq_apply_timer.stop()
        self.backend.set_mode(DataMode.SIMULATION)
        self.control_panel.set_data_mode_label(DataMode.SIMULATION.value)
        self.control_panel.set_status("MODE", DataMode.SIMULATION.value)
        self.control_panel.set_status("BACKEND", "IDLE")
        self.status_panel.set_status("MODE", DataMode.SIMULATION.value)
        self.status_panel.set_status("DAQ", "idle")
        self.status_panel.info(status_message)
        QTimer.singleShot(0, self._on_controls_changed)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override name
        self.backend.close()
        event.accept()
