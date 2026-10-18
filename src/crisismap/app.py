from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


STYLE = """
* { font-family: "Segoe UI"; font-size: 13px; }
QMainWindow, QWidget { background: #091722; color: #dceaf2; }
QMenuBar { background: #091722; padding: 3px; }
QMenuBar::item:selected, QMenu::item:selected { background: #174156; }
QMenu { background: #102431; border: 1px solid #284657; }
#brand { font-size: 23px; font-weight: 900; letter-spacing: 2px; }
#subtitle { color: #7890a0; font-size: 13px; }
#modePill { color: #86efac; background: #10352c; border: 1px solid #1e604d; border-radius: 11px; padding: 5px 11px; font-size: 11px; font-weight: 700; }
#panel { background: #0e2130; border: 1px solid #203b4c; border-radius: 12px; }
#sideScroll { border: none; background: transparent; }
#panelTitle { font-size: 20px; font-weight: 750; }
#sectionLabel { color: #6f8da0; font-size: 10px; font-weight: 800; letter-spacing: 1px; margin-top: 8px; }
#selectionCard { background: #112c3c; border-left: 3px solid #22d3ee; border-radius: 5px; padding: 10px; color: #bcd2df; }
#hint { color: #7890a0; font-size: 11px; }
#mapCaption { background: #0b1b27; color: #7890a0; padding: 8px 14px; }
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox { background: #0a1924; border: 1px solid #294657; border-radius: 6px; padding: 8px; selection-background-color: #0891b2; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border: 1px solid #22d3ee; }
QPushButton { background: #173447; border: 1px solid #2b5065; border-radius: 7px; padding: 9px; font-weight: 650; }
QPushButton:hover { background: #20485e; }
#primaryButton { background: #0891b2; color: #ffffff; border: none; padding: 12px; font-weight: 800; }
#primaryButton:hover { background: #06b6d4; }
#riskBadge { background: #142c3b; color: #7890a0; border-radius: 8px; padding: 8px; font-weight: 800; }
#score { font-size: 47px; font-weight: 850; color: #f1f7fa; margin-top: 6px; }
#metricLabel { color: #9bb1bf; font-size: 11px; }
QProgressBar { background: #091722; border: none; border-radius: 4px; height: 9px; text-align: right; color: transparent; }
QProgressBar::chunk { background: #22d3ee; border-radius: 4px; }
#summary { background: #0a1924; border-radius: 7px; padding: 12px; color: #bcd2df; }
#actions { color: #a9c2d0; line-height: 1.4; }
#notice { background: #292317; color: #fbbf24; border: 1px solid #59451a; border-radius: 6px; padding: 9px; font-size: 10px; }
QStatusBar { color: #7890a0; }
QSplitter::handle { width: 8px; background: transparent; }
QScrollBar:vertical { width: 8px; background: #091722; }
QScrollBar::handle:vertical { background: #294657; border-radius: 4px; min-height: 30px; }
"""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CrisisMap")
    app.setOrganizationName("CrisisMap")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
    window = MainWindow()
    window.show()
    return app.exec()
