import os
# Force pyqtgraph to use PyQt5. Without this it auto-detects in the order
# PyQt6 -> PySide6 -> PyQt5 -> PySide2 and can crash on machines that have
# a partial PyQt6/PySide6 install lying around from other projects.
os.environ["PYQTGRAPH_QT_LIB"] = "PyQt5"

import utils.dll_fix  # noqa: F401  MUST be early — loads nicaiu.dll before PyQt/nidaqmx
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt
from frontend.main_window import OscilloscopeWindow


def _dark_palette():
    p = QPalette()
    p.setColor(QPalette.Window, QColor(30, 30, 40))
    p.setColor(QPalette.WindowText, Qt.white)  # type: ignore
    p.setColor(QPalette.Base, QColor(20, 20, 28))
    p.setColor(QPalette.AlternateBase, QColor(35, 35, 48))
    p.setColor(QPalette.ToolTipBase, Qt.white)  # type: ignore
    p.setColor(QPalette.ToolTipText, Qt.white)  # type: ignore
    p.setColor(QPalette.Text, Qt.white)  # type: ignore
    p.setColor(QPalette.Button, QColor(45, 45, 60))
    p.setColor(QPalette.ButtonText, Qt.white)  # type: ignore
    p.setColor(QPalette.BrightText, Qt.red)  # type: ignore
    p.setColor(QPalette.Link, QColor(42, 130, 218))
    p.setColor(QPalette.Highlight, QColor(42, 130, 218))
    p.setColor(QPalette.HighlightedText, Qt.black)  # type: ignore
    return p


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(_dark_palette())
    window = OscilloscopeWindow()
    window.show()
    window.start_acquisition()
    sys.exit(app.exec_())
