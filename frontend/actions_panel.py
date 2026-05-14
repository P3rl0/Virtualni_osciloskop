from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QGroupBox, QPushButton, QVBoxLayout


class ActionsPanel(QGroupBox):
    """Right-column panel for app-level actions: save settings (manual + on-exit)
    and PNG screenshot. Pure UI — emits signals; main_window does the work."""

    save_now_requested      = pyqtSignal()
    screenshot_requested    = pyqtSignal()
    save_on_exit_changed    = pyqtSignal(bool)

    def __init__(self, save_on_exit: bool, parent=None):
        super().__init__("App", parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 14, 6, 6)

        self._save_on_exit_chk = QCheckBox("Auto-save settings on exit")
        self._save_on_exit_chk.setChecked(bool(save_on_exit))
        layout.addWidget(self._save_on_exit_chk)

        self._save_now_btn = QPushButton("Save settings now")
        layout.addWidget(self._save_now_btn)

        self._shot_btn = QPushButton("📷 Screenshot plot")
        self._shot_btn.setToolTip("Save the plot area as a timestamped PNG in the project root.")
        layout.addWidget(self._shot_btn)

        self._save_on_exit_chk.toggled.connect(self.save_on_exit_changed.emit)
        self._save_now_btn.clicked.connect(self.save_now_requested.emit)
        self._shot_btn.clicked.connect(self.screenshot_requested.emit)

    def set_save_on_exit(self, on: bool):
        """Used to programmatically reflect a value loaded from config without
        triggering save_on_exit_changed."""
        self._save_on_exit_chk.blockSignals(True)
        self._save_on_exit_chk.setChecked(bool(on))
        self._save_on_exit_chk.blockSignals(False)
