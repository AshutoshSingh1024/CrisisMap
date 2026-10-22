from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


STYLE = """
* { font-family: "Segoe UI"; font-size: 11px; }

/* Base window */
QMainWindow, QWidget { background: #0a0c10; color: #e8eaed; }

/* Menu bar */
QMenuBar { background: #0a0c10; padding: 4px; border-bottom: 1px solid #1a1d23; }
QMenuBar::item { background: transparent; padding: 5px 9px; border: 1px solid transparent; border-radius: 5px; }
QMenuBar::item:selected { background: #1a1d23; color: #64b5f6; }
QMenu { background: #12151a; border: 1px solid #1a1d23; }
QMenu::item { padding: 7px 24px 7px 14px; color: #e8eaed; }
QMenu::item:selected { background: #1a1d23; color: #64b5f6; }
QMenu::separator { height: 1px; margin: 4px 0px; background: #1a1d23; }

/* Brand */
#brand { font-size: 18px; font-weight: 800; letter-spacing: 0.5px; color: #e8eaed; }
#subtitle { color: #8a8f98; font-size: 11px; }

/* Panels */
#panel { background: #12151a; border: 1px solid #1a1d23; border-radius: 10px; padding: 10px; }
#sideScroll { border: none; background: transparent; }

/* Titles and labels */
#panelTitle { font-size: 14px; font-weight: 700; color: #e8eaed; }
#sectionLabel { color: #8a8f98; font-size: 9px; font-weight: 700; letter-spacing: 0.5px; margin-top: 8px; text-transform: uppercase; }
#selectionCard { background: #1a1d23; border: 1px solid #232933; border-radius: 8px; padding: 10px; color: #e8eaed; }
#hint { color: #8a8f98; font-size: 10px; }

/* Tabs */
QTabWidget::pane { background: #12151a; border: 1px solid #1a1d23; border-radius: 8px; margin-top: 8px; }
QTabBar::tab { background: #1a1d23; color: #8a8f98; padding: 10px 18px; border: 1px solid transparent; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; font-size: 10px; font-weight: 700; }
QTabBar::tab:selected { background: #0a0c10; color: #64b5f6; border-bottom: 2px solid #64b5f6; }
QTabBar::tab:hover { background: #1e232c; color: #e8eaed; }

/* Inputs */
QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox { background: #0a0c10; border: 1px solid #232933; border-radius: 6px; padding: 7px 10px; color: #e8eaed; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus { border: 1px solid #64b5f6; }

/* Buttons */
QPushButton { background: #1a1d23; border: 1px solid #232933; border-radius: 6px; padding: 7px 16px; font-weight: 600; color: #e8eaed; }
QPushButton:hover { background: #232933; border-color: #64b5f6; }
QPushButton:pressed { background: #232933; }

#primaryButton { background: #1e7d32; color: #ffffff; border: none; border-radius: 6px; padding: 10px 20px; font-weight: 700; font-size: 11px; }
#primaryButton:hover { background: #2e9e40; }
#primaryButton:pressed { background: #186a28; }

#primaryButton { background: #1e7d32; color: #ffffff; border: none; border-radius: 6px; padding: 8px 16px; font-weight: 700; font-size: 10px; }
#primaryButton:hover { background: #2e9e40; }
#primaryButton:pressed { background: #186a28; }

#toggleButton { background: #1a1d23; border: 1px solid #232933; border-radius: 6px; padding: 5px 12px; font-weight: 600; color: #e8eaed; font-size: 10px; }
#toggleButton:checked { background: #1e7d32; border-color: #1e7d32; color: #ffffff; }
#toggleButton:hover { background: #232933; border-color: #64b5f6; }

#quickButton { background: #1a1d23; border: 1px solid #232933; border-radius: 6px; padding: 7px 14px; font-weight: 600; color: #e8eaed; font-size: 10px; }
#quickButton:hover { background: #232933; border-color: #64b5f6; }

#zoomButton { background: #1a1d23; border: 1px solid #232933; border-radius: 4px; padding: 4px 10px; font-weight: 700; color: #e8eaed; font-size: 11px; min-width: 34px; }
#zoomButton:hover { background: #232933; border-color: #64b5f6; }

/* Risk badge */
#riskBadge { background: #1a1d23; color: #e8eaed; border: 1px solid #232933; border-radius: 10px; padding: 10px; font-weight: 700; }
#score { font-size: 36px; font-weight: 800; color: #e8eaed; margin-top: 4px; font-family: "Segoe UI"; }
#metricLabel { color: #8a8f98; font-size: 10px; font-weight: 700; }

QProgressBar { background: #1a1d23; border: 1px solid #232933; border-radius: 6px; height: 14px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #64b5f6; border: none; border-radius: 5px; }

#summary { background: #1a1d23; border: 1px solid #232933; border-radius: 8px; padding: 10px; color: #e8eaed; font-size: 10px; }
#actions { color: #e8eaed; line-height: 1.5; font-size: 10px; }
#suggestions { color: #e8eaed; line-height: 1.5; font-size: 10px; font-weight: 700; }

QStatusBar { color: #8a8f98; background: #0a0c10; border-top: 1px solid #1a1d23; }

/* Splitter */
QSplitter::handle { width: 2px; background: #1a1d23; }

/* Scrollbars */
QScrollBar:vertical { width: 12px; background: #0a0c10; border: none; }
QScrollBar::handle:vertical { background: #232933; border-radius: 6px; min-height: 20px; }
QScrollBar::handle:vertical:pressed { background: #4a4f58; }

/* Sliders */
QSlider::groove:horizontal { background: #232933; border: none; height: 5px; border-radius: 2px; }
QSlider::handle:horizontal { background: #64b5f6; border: none; width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }
QSlider::handle:horizontal:pressed { background: #42a5f5; }

/* Scroll areas */
QScrollArea { border: none; }
QScrollArea > QScrollAreaWidget > QWidget { background: transparent; }

/* Table */
QTableWidget { background: #0a0c10; border: 1px solid #1a1d23; border-radius: 8px; color: #e8eaed; gridline-color: #1a1d23; }
QTableWidget::item { padding: 8px; border: none; }
QTableWidget::item:selected { background: #1e7d32; color: #ffffff; }
QHeaderView::section { background: #12151a; color: #8a8f98; border: none; border-bottom: 1px solid #1a1d23; padding: 8px; font-weight: 700; font-size: 9px; text-transform: uppercase; }

/* Tab widget specific */
QTabBar::tab { background: #12151a; color: #8a8f98; padding: 10px 20px; border: 1px solid #1a1d23; border-bottom: none; border-top-left-radius: 7px; border-top-right-radius: 7px; font-size: 11px; font-weight: 700; min-width: 100px; }
QTabBar::tab:selected { background: #0a0c10; color: #64b5f6; border-bottom: 3px solid #64b5f6; }
QTabBar::tab:hover { background: #1e232c; color: #e8eaed; }

/* Metric cards */
#metricCard { background: #12151a; border: 1px solid #1a1d23; border-radius: 8px; }
#metricCard:hover { background: #1a1d23; border-color: #64b5f6; }
#metricTitle { color: #8a8f98; font-size: 9px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase; }
#metricValue { color: #e8eaed; font-size: 20px; font-weight: 800; }
#metricSubtitle { color: #8a8f98; font-size: 8px; }

/* Location card */
#locationCard { background: #12151a; border: 1px solid #1a1d23; border-radius: 8px; }

/* Analysis header */
#analysisHeader { color: #e8eaed; }

/* Table container */
#tableContainer { background: #12151a; border-radius: 8px; }

/* Map view */
QGraphicsView { background: #0a0c10; border: 1px solid #1a1d23; border-radius: 8px; }
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
