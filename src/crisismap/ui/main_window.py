from __future__ import annotations

import random
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..data_repository import MapDataset, bundled_dataset, load_geojson, procedural_dataset
from ..export import save_assessment
from ..models import Assessment, DisasterType, LocationProfile, Scenario
from ..simulation import assess
from .map_view import MapView, RISK_COLORS


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CrisisMap · Offline Impact Assessment")
        self.resize(1440, 850)
        self.setMinimumSize(1080, 680)
        self.dataset: MapDataset | None = None
        self.location: LocationProfile | None = None
        self.assessment: Assessment | None = None
        self._build_menu()
        self._build_ui()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Offline mode · no network services are used")
        self.load_dataset(bundled_dataset())

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = QAction("Open GeoJSON…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_geojson)
        export_action = QAction("Export assessment…", self)
        export_action.setShortcut(QKeySequence.StandardKey.Save)
        export_action.triggered.connect(self.export_assessment)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addActions([open_action, export_action])
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        map_menu = self.menuBar().addMenu("&Map")
        demo_action = QAction("Load demo region", self)
        demo_action.triggered.connect(lambda: self.load_dataset(bundled_dataset()))
        terrain_action = QAction("Generate procedural terrain", self)
        terrain_action.triggered.connect(self.generate_terrain)
        map_menu.addActions([demo_action, terrain_action])

        help_menu = self.menuBar().addMenu("&Help")
        about_action = QAction("About CrisisMap", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 14, 18, 16)
        root_layout.setSpacing(12)

        header = QHBoxLayout()
        brand = QLabel("CRISIS<span style='color:#22d3ee'>MAP</span>")
        brand.setObjectName("brand")
        subtitle = QLabel("Offline disaster impact assessment")
        subtitle.setObjectName("subtitle")
        mode = QLabel("●  OFFLINE READY")
        mode.setObjectName("modePill")
        header.addWidget(brand)
        header.addSpacing(12)
        header.addWidget(subtitle)
        header.addStretch()
        header.addWidget(mode)
        root_layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._control_panel())

        map_container = QFrame()
        map_container.setObjectName("panel")
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        self.map_view = MapView()
        self.map_view.location_selected.connect(self._select_location)
        map_layout.addWidget(self.map_view)
        self.map_caption = QLabel("Drag to pan · Wheel to zoom · Click to select nearest area")
        self.map_caption.setObjectName("mapCaption")
        map_layout.addWidget(self.map_caption)
        splitter.addWidget(map_container)
        splitter.addWidget(self._results_panel())
        splitter.setSizes([300, 800, 330])
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

    def _control_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("sideScroll")
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(13)
        title = QLabel("Scenario setup")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        layout.addWidget(self._section_label("01  LOCATION"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search loaded places…")
        self.search.returnPressed.connect(self.search_location)
        layout.addWidget(self.search)
        self.location_label = QLabel("Select an area on the map")
        self.location_label.setObjectName("selectionCard")
        self.location_label.setWordWrap(True)
        layout.addWidget(self.location_label)

        layout.addWidget(self._section_label("02  HAZARD"))
        form = QFormLayout()
        form.setVerticalSpacing(12)
        self.disaster = QComboBox()
        self.disaster.addItems([item.value for item in DisasterType])
        self.disaster.currentTextChanged.connect(self._update_parameter_help)
        self.intensity = QDoubleSpinBox()
        self.intensity.setRange(0, 10)
        self.intensity.setSingleStep(.5)
        self.intensity.setValue(6.5)
        self.intensity.setSuffix(" / 10")
        self.duration = QDoubleSpinBox()
        self.duration.setRange(.5, 168)
        self.duration.setValue(24)
        self.duration.setSuffix(" h")
        form.addRow("Disaster", self.disaster)
        form.addRow("Intensity", self.intensity)
        form.addRow("Duration", self.duration)
        layout.addLayout(form)
        self.parameter_help = QLabel()
        self.parameter_help.setWordWrap(True)
        self.parameter_help.setObjectName("hint")
        layout.addWidget(self.parameter_help)

        layout.addWidget(self._section_label("03  PREPAREDNESS"))
        prep_row = QHBoxLayout()
        self.preparedness = QSlider(Qt.Orientation.Horizontal)
        self.preparedness.setRange(0, 100)
        self.preparedness.setValue(45)
        self.preparedness.valueChanged.connect(lambda value: self.preparedness_value.setText(f"{value}%"))
        self.preparedness_value = QLabel("45%")
        prep_row.addWidget(self.preparedness)
        prep_row.addWidget(self.preparedness_value)
        layout.addLayout(prep_row)

        self.run_button = QPushButton("Run assessment")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.run_assessment)
        layout.addWidget(self.run_button)
        clear_button = QPushButton("Clear result")
        clear_button.clicked.connect(self.clear_result)
        layout.addWidget(clear_button)
        layout.addStretch()
        scroll.setWidget(panel)
        self._update_parameter_help()
        return scroll

    def _results_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        title = QLabel("Assessment")
        title.setObjectName("panelTitle")
        layout.addWidget(title)
        self.risk_badge = QLabel("NO RESULT")
        self.risk_badge.setObjectName("riskBadge")
        self.risk_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.risk_badge)
        self.score = QLabel("—")
        self.score.setObjectName("score")
        self.score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.score)
        score_caption = QLabel("COMPOSITE RISK SCORE")
        score_caption.setObjectName("sectionLabel")
        score_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(score_caption)

        self.metrics: dict[str, QProgressBar] = {}
        for key in ("Hazard", "Exposure", "Vulnerability"):
            metric_label = QLabel(key)
            metric_label.setObjectName("metricLabel")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFormat("%v")
            layout.addWidget(metric_label)
            layout.addWidget(bar)
            self.metrics[key] = bar
        self.summary = QLabel("Configure a scenario and select a location to generate an assessment.")
        self.summary.setWordWrap(True)
        self.summary.setObjectName("summary")
        layout.addWidget(self.summary)
        self.actions = QLabel("")
        self.actions.setWordWrap(True)
        self.actions.setObjectName("actions")
        layout.addWidget(self.actions)
        layout.addStretch()
        notice = QLabel("Educational model · assessment, not prediction")
        notice.setWordWrap(True)
        notice.setObjectName("notice")
        layout.addWidget(notice)
        return panel

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    def load_dataset(self, dataset: MapDataset) -> None:
        self.dataset = dataset
        self.location = None
        self.assessment = None
        self.map_view.set_dataset(dataset)
        self.location_label.setText("Select an area on the map")
        self.search.clear()
        self.map_caption.setText(f"{dataset.name} · {dataset.source} · {len(dataset.locations)} searchable places")
        self.clear_result()
        self.statusBar().showMessage(f"Loaded {dataset.name} locally · offline mode")

    def _select_location(self, location: LocationProfile) -> None:
        self.location = location
        self.search.setText(location.name)
        self.location_label.setText(
            f"<b>{location.name}</b><br>"
            f"{location.latitude:.4f}, {location.longitude:.4f}<br>"
            f"Elevation {location.elevation_m:.0f} m"
        )
        self.statusBar().showMessage(f"Selected {location.name}")

    def search_location(self) -> None:
        if not self.dataset:
            return
        query = self.search.text().strip().casefold()
        matches = [loc for loc in self.dataset.locations if query in loc.name.casefold()]
        if not query or not matches:
            self.statusBar().showMessage("No matching place in the loaded offline dataset")
            self.search.setFocus()
            return
        self.map_view.select_location(matches[0], emit=True)

    def _update_parameter_help(self) -> None:
        help_text = {
            "Flood": "Intensity represents rainfall/runoff severity; elevation and water proximity affect the result.",
            "Wildfire": "Intensity represents fire-weather severity; vegetation and duration affect spread risk.",
            "Earthquake": "Intensity represents ground-shaking severity; soft soil increases amplification.",
        }
        if hasattr(self, "parameter_help"):
            self.parameter_help.setText(help_text.get(self.disaster.currentText(), ""))

    def run_assessment(self) -> None:
        if not self.location:
            QMessageBox.information(self, "Select a location", "Click an area on the map or search for a loaded place first.")
            return
        scenario = Scenario(
            disaster=DisasterType(self.disaster.currentText()),
            intensity=self.intensity.value(),
            duration_hours=self.duration.value(),
            preparedness=self.preparedness.value() / 100,
        )
        self.assessment = assess(self.location, scenario)
        self.map_view.show_assessment(self.assessment)
        self._show_result(self.assessment)
        self.statusBar().showMessage(f"Assessment complete · {self.assessment.risk_level.value} risk")

    def _show_result(self, result: Assessment) -> None:
        color = RISK_COLORS[result.risk_level].name()
        self.risk_badge.setText(f"{result.risk_level.value.upper()} RISK")
        self.risk_badge.setStyleSheet(f"background:{color}; color:#07131f; border-radius:8px; padding:8px; font-weight:800;")
        self.score.setText(f"{result.overall_score:.0f}<span style='font-size:18px;color:#7890a0'>/100</span>")
        self.metrics["Hazard"].setValue(round(result.hazard_score))
        self.metrics["Exposure"].setValue(round(result.exposure_score))
        self.metrics["Vulnerability"].setValue(round(result.vulnerability_score))
        self.summary.setText(result.summary + f" Estimated affected radius: {result.affected_radius_km:.1f} km.")
        self.actions.setText("<b>Suggested actions</b><br>• " + "<br>• ".join(result.recommendations))

    def clear_result(self) -> None:
        self.assessment = None
        if hasattr(self, "map_view"):
            self.map_view.clear_assessment()
        if hasattr(self, "risk_badge"):
            self.risk_badge.setText("NO RESULT")
            self.risk_badge.setStyleSheet("")
            self.score.setText("—")
            for bar in self.metrics.values():
                bar.setValue(0)
            self.summary.setText("Configure a scenario and select a location to generate an assessment.")
            self.actions.clear()

    def open_geojson(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open local GeoJSON", str(Path.home()), "GeoJSON (*.geojson *.json)")
        if not path:
            return
        try:
            self.load_dataset(load_geojson(path))
        except ValueError as exc:
            QMessageBox.critical(self, "Could not load map", str(exc))

    def generate_terrain(self) -> None:
        seed, accepted = self._seed_dialog()
        if accepted:
            self.load_dataset(procedural_dataset(seed))

    def _seed_dialog(self) -> tuple[int, bool]:
        from PySide6.QtWidgets import QInputDialog
        return QInputDialog.getInt(self, "Procedural terrain", "Random seed", random.randint(1, 9999), 0, 999999)

    def export_assessment(self) -> None:
        if not self.assessment:
            QMessageBox.information(self, "Nothing to export", "Run an assessment before exporting a report.")
            return
        safe_name = "".join(ch if ch.isalnum() else "-" for ch in self.assessment.location.name.lower()).strip("-")
        path, _ = QFileDialog.getSaveFileName(self, "Export assessment", f"crisismap-{safe_name}.json", "JSON (*.json)")
        if path:
            try:
                save_assessment(self.assessment, path)
                self.statusBar().showMessage(f"Saved report locally to {path}")
            except OSError as exc:
                QMessageBox.critical(self, "Could not save report", str(exc))

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About CrisisMap",
            "<b>CrisisMap 0.1.0</b><br><br>Fully offline educational disaster-impact assessment.<br>"
            "Local GeoJSON rendering · deterministic simulation · no network access.<br><br>"
            "Assessment only — not prediction or emergency advice.",
        )
