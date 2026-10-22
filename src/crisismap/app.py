from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


STYLE = """
* { font-family: "Segoe UI"; font-size: 11px; }
QMainWindow, QWidget { background: #0f1115; color: #e8eaed; }
QMenuBar { background: #0f1115; padding: 2px; border-bottom: 1px solid #22252b; }
QMenuBar::item { background: transparent; padding: 4px 8px; border: 1px solid transparent; border-radius: 4px; }
QMenuBar::item:selected { background: #1e222a; color: #64b5f6; }
QMenu { background: #15181c; border: 1px solid #22252b; }
QMenu::item { padding: 6px 24px 6px 12px; color: #e8eaed; }
QMenu::item:selected { background: #1e222a; color: #64b5f6; }
QMenu::separator { height: 1px; margin: 4px 0px; background: #22252b; }
#brand { font-size: 17px; font-weight: 700; letter-spacing: 0.5px; color: #e8eaed; }
#subtitle { color: #8a8f98; font-size: 11px; }
#panel { background: #15181c; border: 1px solid #22252b; border-radius: 8px; padding: 8px; }
#sideScroll { border: none; background: transparent; }
#panelTitle { font-size: 13px; font-weight: 600; color: #e8eaed; }
#sectionLabel { color: #8a8f98; font-size: 9px; font-weight: 600; letter-spacing: 0.5px; margin-top: 6px; text-transform: uppercase; }
#selectionCard { background: #1e222a; border: 1px solid #22252b; border-radius: 6px; padding: 8px; color: #e8eaed; }
#hint { color: #8a8f98; font-size: 10px; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox { background: #0f1115; border: 1px solid #22252b; border-radius: 4px; padding: 5px 8px; color: #e8eaed; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border: 1px solid #64b5f6; }
QPushButton { background: #1e222a; border: 1px solid #22252b; border-radius: 4px; padding: 6px 12px; font-weight: 600; color: #e8eaed; }
QPushButton:hover { background: #262b34; border-color: #64b5f6; }
QPushButton:pressed { background: #22252b; }
#primaryButton { background: #1e7d32; color: #ffffff; border: none; border-radius: 4px; padding: 8px 16px; font-weight: 600; }
#primaryButton:hover { background: #2e9e40; }
#primaryButton:pressed { background: #186a28; }
#toggleButton { background: #1e222a; border: 1px solid #22252b; border-radius: 4px; padding: 5px 10px; font-weight: 600; color: #e8eaed; font-size: 10px; }
#toggleButton:checked { background: #1e7d32; border-color: #1e7d32; color: #ffffff; }
#toggleButton:hover { background: #262b34; border-color: #64b5f6; }
#quickButton { background: #1e222a; border: 1px solid #22252b; border-radius: 4px; padding: 6px 12px; font-weight: 600; color: #e8eaed; font-size: 10px; }
#quickButton:hover { background: #262b34; border-color: #64b5f6; }
#mapControls { background: #1e222a; border: 1px solid #22252b; border-radius: 4px; padding: 6px; }
#zoomButton { background: #1e222a; border: 1px solid #22252b; border-radius: 4px; padding: 4px 8px; font-weight: 700; color: #e8eaed; font-size: 11px; min-width: 32px; }
#zoomButton:hover { background: #262b34; border-color: #64b5f6; }
#riskBadge { background: #1e222a; color: #e8eaed; border: 1px solid #22252b; border-radius: 8px; padding: 8px; font-weight: 700; }
#score { font-size: 32px; font-weight: 700; color: #e8eaed; margin-top: 4px; font-family: "Segoe UI"; }
#metricLabel { color: #8a8f98; font-size: 10px; font-weight: 600; }
QProgressBar { background: #22252b; border: 1px solid #2d3239; border-radius: 4px; height: 12px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #64b5f6; border: none; border-radius: 3px; }
#summary { background: #1e222a; border: 1px solid #22252b; border-radius: 6px; padding: 8px; color: #e8eaed; font-size: 10px; }
#actions { color: #e8eaed; line-height: 1.4; font-size: 10px; }
#suggestions { color: #e8eaed; line-height: 1.4; font-size: 10px; font-weight: 600; }
#chartCard { background: #1a1d24; border: 1px solid #2d3239; border-radius: 8px; padding: 8px; }
QStatusBar { color: #8a8f98; background: #0f1115; border-top: 1px solid #22252b; }
QSplitter::handle { width: 2px; background: #22252b; }
QScrollBar:vertical { width: 12px; background: #0f1115; border: none; }
QScrollBar::handle:vertical { background: #2d3239; border-radius: 6px; min-height: 20px; }
QScrollBar::handle:vertical:pressed { background: #4a4f58; }
QSlider::groove:horizontal { background: #2d3239; border: none; height: 4px; border-radius: 2px; }
QSlider::handle:horizontal { background: #64b5f6; border: none; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
QSlider::handle:horizontal:pressed { background: #42a5f5; }
QScrollArea { border: none; }
QScrollArea > QScrollAreaWidget > QWidget { background: transparent; }
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CrisisMap")
    app.setOrganizationName("CrisisMap")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 9))
    window = MainWindow()
    window.show()
    return app.exec()
