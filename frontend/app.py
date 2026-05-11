"""Application entry point for the virtual oscilloscope frontend."""

from __future__ import annotations

import logging
import sys

from PyQt5.QtWidgets import QApplication

from frontend.app_logging import setup_logging
from frontend.main_window import OscilloscopeWindow

logger = logging.getLogger(__name__)


def main() -> None:
    setup_logging()
    logger.info("Starting virtual oscilloscope frontend")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = OscilloscopeWindow()
    window.show()
    exit_code = app.exec_()
    logger.info("Virtual oscilloscope frontend exited with code %s", exit_code)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
