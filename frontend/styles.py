"""Visual constants and small Qt style helpers."""

from __future__ import annotations

from PyQt5.QtWidgets import QLabel, QFrame

BG_DARK = "#0d0f14"
BG_MID = "#0f1219"
BG_PANEL = "#13161f"
BG_WIDGET = "#1a1e2a"
BG_WIDGET2 = "#1e2330"
GRID_COLOR = "#182030"
TEXT_PRIMARY = "#d8e4f0"
TEXT_DIM = "#3d5068"
TEXT_MED = "#6a7f96"
BORDER_COLOR = "#232d3e"

CH_COLORS = {
    1: "#00ff9f",
    2: "#00cfff",
    3: "#ff9f00",
    4: "#cf6aff",
}


def _ch_checkbox_css(ch: int) -> str:
    color = CH_COLORS[ch]
    return f"""
QCheckBox#ch{ch} {{ color: {color}; font-weight: 700; font-size: 12px; spacing: 6px; }}
QCheckBox#ch{ch}::indicator {{
    width: 13px; height: 13px;
    border: 1px solid {color}55;
    border-radius: 3px;
    background: {BG_WIDGET};
}}
QCheckBox#ch{ch}::indicator:checked {{
    background: {color};
    border-color: {color};
}}"""


STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG_DARK};
    color: {TEXT_PRIMARY};
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
}}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: {BG_WIDGET}; width: 6px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_COLOR}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QGroupBox {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_COLOR};
    border-radius: 6px;
    margin-top: 20px;
    padding: 6px 6px 6px 6px;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.8px;
    color: {TEXT_DIM};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px; padding: 0 4px;
    color: {TEXT_MED};
}}
QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}
QLabel#dim {{
    color: {TEXT_DIM};
    font-size: 9px;
    font-weight: 600;
    letter-spacing: 1.8px;
}}
QLabel#meas_val {{
    font-family: 'Courier New', monospace;
    font-size: 12px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
QLabel#meas_na {{
    font-family: 'Courier New', monospace;
    font-size: 12px;
    font-weight: 700;
    color: {TEXT_DIM};
}}
QLabel#time_readout, QLabel#trigger_readout {{
    font-family: 'Courier New', monospace;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#time_readout {{ color: #aac8e0; }}
QLabel#trigger_readout {{ color: #ffd166; }}
QLabel#status_badge {{
    color: {TEXT_PRIMARY};
    font-family: 'Courier New', monospace;
    font-size: 11px;
    font-weight: 700;
}}
QComboBox, QDoubleSpinBox {{
    background-color: {BG_WIDGET};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    padding: 3px 8px;
    color: {TEXT_PRIMARY};
    font-size: 11px;
    min-height: 24px;
}}
QComboBox:hover, QDoubleSpinBox:hover {{ border: 1px solid #2a4060; }}
QComboBox:focus, QDoubleSpinBox:focus {{ border: 1px solid #2a5080; outline: none; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT_DIM};
    margin-right: 5px;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_WIDGET2};
    border: 1px solid {BORDER_COLOR};
    color: {TEXT_PRIMARY};
    selection-background-color: #1e3a58;
    selection-color: {TEXT_PRIMARY};
    outline: none;
    font-size: 11px;
}}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {BG_WIDGET2}; border: none; width: 16px;
}}
QCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: 11px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 13px;
    height: 13px;
    border: 1px solid {BORDER_COLOR};
    border-radius: 3px;
    background: {BG_WIDGET};
}}
QCheckBox::indicator:checked {{
    background: #2a5080;
    border-color: #3a70b0;
}}
QPushButton {{
    background-color: {BG_WIDGET};
    border: 1px solid {BORDER_COLOR};
    border-radius: 4px;
    min-height: 28px;
    padding: 4px 10px;
    color: {TEXT_PRIMARY};
    font-size: 11px;
    font-weight: 700;
}}
QPushButton:hover {{ border: 1px solid #35527a; }}
QPushButton:checked {{
    background-color: #1f324a;
    border: 1px solid #4a7db5;
}}
QPushButton#run_btn:checked {{
    background-color: #153725;
    border: 1px solid #22a060;
    color: #8ef0b8;
}}
QPushButton#stop_btn:checked {{
    background-color: #3a1717;
    border: 1px solid #c04a4a;
    color: #ff9a9a;
}}
QFrame#hsep {{
    background: {BORDER_COLOR};
    max-height: 1px;
    border: none;
}}
""" + "".join(_ch_checkbox_css(i) for i in range(1, 5))


def make_sep() -> QFrame:
    frame = QFrame()
    frame.setObjectName("hsep")
    frame.setFrameShape(QFrame.HLine)
    return frame


def dim_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("dim")
    return label
