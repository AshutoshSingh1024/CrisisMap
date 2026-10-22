from __future__ import annotations

import json
import random
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QCheckBox,
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
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..data_repository import MapDataset, bundled_dataset, load_geojson, pune_dataset, procedural_dataset, flood_zones_dataset, shelters_dataset
from ..export import save_assessment
from ..export_pdf import export_pdf
from ..models import Assessment, DisasterType, LocationProfile, RiskLevel, Scenario
from ..simulation import assess, simulate_time_series
from ..assistant_model import AssistantWorker
from .analysis_panel import AnalysisPanel
from .chart_widgets import BarChartWidget, RiskBreakdownWidget, RiskGaugeWidget
from .osm_map import OSMMap as MapView
from .map_view import RISK_COLORS


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CrisisMap - Pune Impact Assessment")
        self.resize(1440, 850)
        self.setMinimumSize(1080, 680)
        self.dataset: MapDataset | None = None
        self.location: LocationProfile | None = None
        self.assessment: Assessment | None = None
        self._assistant_context_revision = 0
        self._comparison: Assessment | None = None
        self._assistant_history: list[tuple[str, str]] = []
        self._anim_timer: QTimer | None = None
        self._heat_enabled: bool = False
        self._grid_enabled: bool = False
        self._build_menu()
        self._build_ui()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("")
        self.load_dataset(pune_dataset())

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = QAction("Open GeoJSONâ€¦", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_geojson)
        save_action = QAction("Save scenarioâ€¦", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_scenario)
        load_action = QAction("Load scenarioâ€¦", self)
        load_action.setShortcut(QKeySequence("Ctrl+O"))
        load_action.triggered.connect(self.load_scenario)
        export_action = QAction("Export assessmentâ€¦", self)
        export_action.triggered.connect(self.export_assessment)
        export_pdf_action = QAction("Export PDF reportâ€¦", self)
        export_pdf_action.triggered.connect(self.export_pdf_report)
        export_charts_action = QAction("Export charts to PNGâ€¦", self)
        export_charts_action.triggered.connect(self.export_charts_report)
        export_html_action = QAction("Export HTML reportâ€¦", self)
        export_html_action.triggered.connect(self.export_html_report)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addActions([open_action, save_action, load_action, export_action, export_pdf_action, export_charts_action, export_html_action])
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        map_menu = self.menuBar().addMenu("&Map")
        demo_action = QAction("Load demo region", self)
        demo_action.triggered.connect(lambda: self.load_dataset(bundled_dataset()))
        pune_action = QAction("Load Pune wards (real map)", self)
        pune_action.triggered.connect(lambda: self.load_dataset(pune_dataset()))
        flood_action = QAction("Load Pune flood zones", self)
        flood_action.triggered.connect(lambda: self.load_dataset(flood_zones_dataset()))
        shelter_action = QAction("Load Pune shelters", self)
        shelter_action.triggered.connect(lambda: self.load_dataset(shelters_dataset()))
        terrain_action = QAction("Generate procedural terrain", self)
        terrain_action.triggered.connect(self.generate_terrain)
        map_menu.addActions([demo_action, pune_action, flood_action, shelter_action, terrain_action])

        view_menu = self.menuBar().addMenu("&View")
        self.heat_action = QAction("Heatmap layer", self, checkable=True)
        self.heat_action.setChecked(False)
        self.heat_action.triggered.connect(self._toggle_heatmap)
        self.grid_action = QAction("Coordinate grid", self, checkable=True)
        self.grid_action.setChecked(False)
        self.grid_action.triggered.connect(self._toggle_grid)
        self.multihazard_action = QAction("Multi-hazard overlay", self, checkable=True)
        self.multihazard_action.triggered.connect(self._toggle_multi_hazard)
        view_menu.addActions([self.heat_action, self.grid_action, self.multihazard_action])

        help_menu = self.menuBar().addMenu("&Help")
        about_action = QAction("About CrisisMap", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(2)

        header = QHBoxLayout()
        brand = QLabel("CRISIS<span style='color:#64b5f6'>MAP</span>")
        brand.setObjectName("brand")
        subtitle = QLabel("Disaster impact assessment")
        subtitle.setObjectName("subtitle")
        header.addWidget(brand)
        header.addSpacing(8)
        header.addWidget(subtitle)
        header.addStretch()

        header.addStretch()
        root_layout.addLayout(header)

        # Tabbed interface: Map tab and Analysis tab
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")

        # Tab 1: Map view (large, full screen)
        map_tab = QWidget()
        map_layout = QVBoxLayout(map_tab)
        map_layout.setContentsMargins(2, 2, 2, 2)
        map_layout.setSpacing(2)

        self.map_view = MapView()
        self.map_view.location_selected.connect(self._select_location)
        self.map_view.hovered_location.connect(self._on_hover_location)
        self.map_view.evacuation_message.connect(lambda msg: self.statusBar().showMessage(msg))
        map_layout.addWidget(self.map_view)

        zoom_row = QHBoxLayout()
        zoom_in = QPushButton("+")
        zoom_in.setObjectName("zoomButton")
        zoom_in.setToolTip("Zoom in")
        zoom_in.clicked.connect(self.map_view.zoom_in)
        zoom_out = QPushButton("-")
        zoom_out.setObjectName("zoomButton")
        zoom_out.setToolTip("Zoom out")
        zoom_out.clicked.connect(self.map_view.zoom_out)
        zoom_reset = QPushButton("â†º")
        zoom_reset.setObjectName("zoomButton")
        zoom_reset.setToolTip("Reset view")
        zoom_reset.clicked.connect(self._reset_map_view)
        zoom_row.addWidget(zoom_in)
        zoom_row.addWidget(zoom_out)
        zoom_row.addWidget(zoom_reset)
        zoom_row.addStretch()
        map_layout.addLayout(zoom_row)

        self.tabs.addTab(map_tab, "Map")

        # Tab 2: Analysis / control panel
        analysis_tab = QWidget()
        analysis_layout = QVBoxLayout(analysis_tab)
        analysis_layout.setContentsMargins(4, 4, 4, 4)
        analysis_layout.setSpacing(2)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._control_panel())
        splitter.addWidget(self._results_panel())
        splitter.setSizes([340, 760])
        analysis_layout.addWidget(splitter)

        self.tabs.addTab(analysis_tab, "Analysis")

        root_layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

    def _control_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("sideScroll")
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        title = QLabel("Scenario setup")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        layout.addWidget(self._section_label("01  LOCATION"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search Pune localityâ€¦")
        self.search.returnPressed.connect(self.search_location)
        layout.addWidget(self.search)
        self.location_label = QLabel("Select an area on the map")
        self.location_label.setWordWrap(True)
        self.location_label.setObjectName("selectionCard")
        layout.addWidget(self.location_label)

        # MITWPU preset button
        mitwpu_button = QPushButton("Load MIT-WPU Kothrud")
        mitwpu_button.setToolTip("Load MIT World Peace University, Kothrud as test location")
        mitwpu_button.clicked.connect(self._load_mitwpu)
        layout.addWidget(mitwpu_button)

        # Quick scenario buttons
        layout.addWidget(self._section_label("QUICK SCENARIOS"))
        quick_row = QHBoxLayout()
        flood_btn = QPushButton("Flood 7/10")
        flood_btn.setObjectName("quickButton")
        flood_btn.clicked.connect(lambda: self._quick_scenario(DisasterType.FLOOD, 7.0, 24, 0.45))
        fire_btn = QPushButton("Wildfire 6/10")
        fire_btn.setObjectName("quickButton")
        fire_btn.clicked.connect(lambda: self._quick_scenario(DisasterType.WILDFIRE, 6.0, 12, 0.50))
        quake_btn = QPushButton("Earthquake 7/10")
        quake_btn.setObjectName("quickButton")
        quake_btn.clicked.connect(lambda: self._quick_scenario(DisasterType.EARTHQUAKE, 7.0, 2, 0.55))
        quick_row.addWidget(flood_btn)
        quick_row.addWidget(fire_btn)
        quick_row.addWidget(quake_btn)
        layout.addLayout(quick_row)

        # Scenario save/load
        layout.addWidget(self._section_label("SCENARIO FILES"))
        scenario_row = QHBoxLayout()
        save_btn = QPushButton("Save scenario")
        save_btn.setToolTip("Save current scenario to local JSON file")
        save_btn.clicked.connect(self.save_scenario)
        load_btn = QPushButton("Load scenario")
        load_btn.setToolTip("Load scenario from local JSON file")
        load_btn.clicked.connect(self.load_scenario)
        scenario_row.addWidget(save_btn)
        scenario_row.addWidget(load_btn)
        layout.addLayout(scenario_row)

        layout.addWidget(self._section_label("02  HAZARD"))
        form = QFormLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)
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
        self.time_of_day = QSpinBox()
        self.time_of_day.setRange(0, 23)
        self.time_of_day.setValue(12)
        self.time_of_day.setSuffix(":00")
        self.time_of_day.setToolTip("Hour of day (0-23)")
        self.season = QComboBox()
        self.season.addItems(["Dry", "Monsoon", "Winter", "Summer", "Mixed"])
        self.season.setCurrentText("Mixed")
        self.season.setToolTip("Seasonal condition")
        form.addRow("Disaster", self.disaster)
        form.addRow("Intensity", self.intensity)
        form.addRow("Duration", self.duration)
        form.addRow("Time of day", self.time_of_day)
        form.addRow("Season", self.season)
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

        layout.addWidget(self._section_label("04  RISK FACTOR WEIGHTS"))
        ahp_form = QFormLayout()
        ahp_form.setHorizontalSpacing(8)
        ahp_form.setVerticalSpacing(4)
        self.w_hazard = QDoubleSpinBox()
        self.w_hazard.setRange(0, 1)
        self.w_hazard.setSingleStep(0.05)
        self.w_hazard.setValue(0.52)
        self.w_hazard.setDecimals(2)
        self.w_exposure = QDoubleSpinBox()
        self.w_exposure.setRange(0, 1)
        self.w_exposure.setSingleStep(0.05)
        self.w_exposure.setValue(0.25)
        self.w_exposure.setDecimals(2)
        self.w_vulnerability = QDoubleSpinBox()
        self.w_vulnerability.setRange(0, 1)
        self.w_vulnerability.setSingleStep(0.05)
        self.w_vulnerability.setValue(0.23)
        self.w_vulnerability.setDecimals(2)
        self.w_hazard.valueChanged.connect(self._normalize_ahp)
        self.w_exposure.valueChanged.connect(self._normalize_ahp)
        self.w_vulnerability.valueChanged.connect(self._normalize_ahp)
        ahp_form.addRow("Physical hazard", self.w_hazard)
        ahp_form.addRow("People exposure", self.w_exposure)
        ahp_form.addRow("Social vulnerability", self.w_vulnerability)
        layout.addLayout(ahp_form)

        self.run_button = QPushButton("Run assessment")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.run_assessment)
        layout.addWidget(self.run_button)
        self.auto_assess = QCheckBox("Assess automatically when I click the map")
        self.auto_assess.setChecked(False)
        layout.addWidget(self.auto_assess)
        clear_button = QPushButton("Clear result")
        clear_button.clicked.connect(self.clear_result)
        layout.addWidget(clear_button)

        # Scenario comparison
        self._comparison: Assessment | None = None
        compare_button = QPushButton("Save as Baseline")
        compare_button.setToolTip("Save current assessment as baseline for comparison")
        compare_button.clicked.connect(self._save_baseline)
        layout.addWidget(compare_button)
        show_compare_button = QPushButton("Show Comparison")
        show_compare_button.setToolTip("Show comparison with baseline scenario")
        show_compare_button.clicked.connect(self._show_comparison)
        layout.addWidget(show_compare_button)

        # Keyboard shortcut hints
        layout.addWidget(self._section_label("KEYBOARD SHORTCUTS"))
        shortcuts = QLabel(
            "F1 About Â· F5 Run Â· Esc Clear<br>"
            "1 Flood Â· 2 Wildfire Â· 3 Earthquake Â· H Heatmap Â· G Grid"
        )
        shortcuts.setObjectName("hint")
        shortcuts.setWordWrap(True)
        shortcuts.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(shortcuts)
        # Evacuation routing
        layout.addWidget(self._section_label("EVACUATION"))
        evac_row = QHBoxLayout()
        evac_route_btn = QPushButton("Compute Evacuation Route")
        evac_route_btn.setToolTip("Compute evacuation route from selected location to nearest shelter")
        evac_route_btn.clicked.connect(self._compute_evacuation_route)
        evac_clear_btn = QPushButton("Clear Route")
        evac_clear_btn.clicked.connect(lambda: self.map_view.clear_evacuation_route())
        evac_row.addWidget(evac_route_btn)
        evac_row.addWidget(evac_clear_btn)
        layout.addLayout(evac_row)

        layout.addStretch()
        scroll.setWidget(panel)
        self._update_parameter_help()
        return scroll

    def _results_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("Assessment")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        # Tabbed view: Quick Assessment + Detailed Analysis
        self.results_tabs = QTabWidget()
        self.results_tabs.setObjectName("resultsTabs")

        # Tab 1: Quick Assessment
        quick_tab = QWidget()
        quick_layout = QVBoxLayout(quick_tab)
        quick_layout.setContentsMargins(6, 6, 6, 6)
        quick_layout.setSpacing(6)

        self.risk_badge = QLabel("NO RESULT")
        self.risk_badge.setObjectName("riskBadge")
        self.risk_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        quick_layout.addWidget(self.risk_badge)

        self.score = QLabel("â€”")
        self.score.setObjectName("score")
        self.score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        quick_layout.addWidget(self.score)

        score_caption = QLabel("COMPOSITE RISK SCORE")
        score_caption.setObjectName("sectionLabel")
        score_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        quick_layout.addWidget(score_caption)

        self.confidence = QLabel("")
        self.confidence.setObjectName("hint")
        self.confidence.setAlignment(Qt.AlignmentFlag.AlignCenter)
        quick_layout.addWidget(self.confidence)

        self.weights_label = QLabel("")
        self.weights_label.setObjectName("hint")
        self.weights_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        quick_layout.addWidget(self.weights_label)

        self.metrics: dict[str, QProgressBar] = {}
        for key in ("Hazard", "Exposure", "Vulnerability"):
            metric_label = QLabel(key)
            metric_label.setObjectName("metricLabel")
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFormat("%v")
            quick_layout.addWidget(metric_label)
            quick_layout.addWidget(bar)
            self.metrics[key] = bar

        self.summary = QLabel("Configure a scenario and select a location to generate an assessment.")
        self.summary.setWordWrap(True)
        self.summary.setObjectName("summary")
        quick_layout.addWidget(self.summary)

        self.actions = QLabel("")
        self.actions.setWordWrap(True)
        self.actions.setObjectName("actions")
        quick_layout.addWidget(self.actions)

        self.suggestions = QLabel("")
        self.suggestions.setWordWrap(True)
        self.suggestions.setObjectName("suggestions")
        quick_layout.addWidget(self.suggestions)

        quick_layout.addStretch()
        self.results_tabs.addTab(quick_tab, "Quick Assessment")

        # Tab 2: Full Analysis
        self.analysis_panel = AnalysisPanel()
        self.results_tabs.addTab(self.analysis_panel, "Detailed Analysis")

        assistant_tab = QWidget()
        assistant_layout = QVBoxLayout(assistant_tab)
        assistant_layout.setContentsMargins(12, 12, 12, 12)
        assistant_layout.setSpacing(10)
        assistant_title = QLabel("CrisisMap AI Assistant")
        assistant_title.setObjectName("panelTitle")
        assistant_layout.addWidget(assistant_title)
        assistant_note = QLabel("Qwen2.5-0.5B local model Â· concise answers grounded in assessment, map, shelter and route data.")
        assistant_note.setWordWrap(True)
        assistant_note.setObjectName("hint")
        assistant_layout.addWidget(assistant_note)
        self.assistant_chat = QTextBrowser()
        self.assistant_chat.setReadOnly(True)
        self.assistant_chat.setOpenExternalLinks(False)
        self.assistant_chat.setStyleSheet(
            "QTextBrowser { background:#0b111a; border:1px solid #263447; border-radius:10px; padding:8px; color:#e8eef7; }"
        )
        self.assistant_chat.setPlaceholderText("Ask about risk, scenario assumptions, locations, shelters, routes, or recommendationsâ€¦")
        self._append_chat_message(
            "system",
            "Available Help Prompts\nSummarize my assessment Â· Explain the risk score Â· Identify risk factors Â· Suggest preparation steps Â· Find the nearest listed shelter",
        )
        assistant_layout.addWidget(self.assistant_chat, 1)
        ask_row = QHBoxLayout()
        self.assistant_question = QLineEdit()
        self.assistant_question.setPlaceholderText("Ask a question about the current map or assessmentâ€¦")
        ask_row.addWidget(self.assistant_question, 1)
        self.assistant_button = QPushButton("Ask")
        self.assistant_button.clicked.connect(self._answer_question)
        self.assistant_question.returnPressed.connect(self._answer_question)
        ask_row.addWidget(self.assistant_button)
        assistant_layout.addLayout(ask_row)
        self.results_tabs.addTab(assistant_tab, "AI Assistant")

        layout.addWidget(self.results_tabs)
        return panel

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    def _normalize_ahp(self) -> None:
        total = self.w_hazard.value() + self.w_exposure.value() + self.w_vulnerability.value()
        if total > 0:
            self.w_hazard.setValue(round(self.w_hazard.value() / total, 2))
            self.w_exposure.setValue(round(self.w_exposure.value() / total, 2))
            self.w_vulnerability.setValue(round(self.w_vulnerability.value() / total, 2))

    def load_dataset(self, dataset: MapDataset) -> None:
        # Auto-merge shelters and roads when Pune wards are loaded
        features = list(dataset.features)
        if "pune" in dataset.name.lower() or "wards" in dataset.name.lower():
            try:
                shelters_ds = shelters_dataset()
                features.extend(shelters_ds.features)
                roads_ds = load_geojson(Path(__file__).parent.parent / "resources" / "data" / "pune_roads.geojson")
                features.extend(roads_ds.features)
                from crisismap.data_repository import MapDataset
                dataset = MapDataset(dataset.name, features, dataset.source + " + shelters + roads")
            except Exception:
                pass
        self.dataset = dataset
        self.location = None
        self.assessment = None
        self._assistant_history.clear()
        self._assistant_last_route = None
        self.map_view.set_dataset(dataset)
        self.location_label.setText("Select an area on the map")
        self.search.clear()
        self.clear_result()
        self.statusBar().showMessage(f"Loaded {dataset.name}")

    def _select_location(self, location: LocationProfile) -> None:
        if self.location and (self.location.latitude != location.latitude or self.location.longitude != location.longitude):
            self._assistant_history.clear()
            self._assistant_last_route = None
        self.location = location
        self.search.setText(location.name)
        self.location_label.setText(
            f"<b>{location.name}</b><br>"
            f"{location.latitude:.4f}, {location.longitude:.4f}<br>"
            f"Elevation {location.elevation_m:.0f} m Â· "
            f"Income {location.income_level:.0%} Â· Literacy {location.literacy_rate:.0%}"
        )
        self.statusBar().showMessage(f"Selected {location.name}")
        if hasattr(self, "auto_assess") and self.auto_assess.isChecked():
            QTimer.singleShot(0, self.run_assessment)

    def _on_hover_location(self, name: str) -> None:
        if self.location is None:
            self.location_label.setText(f"<b>{name}</b>")

    def search_location(self) -> None:
        if not self.dataset:
            return
        query = self.search.text().strip().casefold()
        matches = [loc for loc in self.dataset.locations if query in loc.name.casefold()]
        if not query or not matches:
            self.statusBar().showMessage("No matching place in the loaded map dataset")
            self.search.setFocus()
            return
        self.map_view.select_location(matches[0], emit=True)

    def _load_mitwpu(self) -> None:
        """Load MIT-WPU Kothrud as a preset test location."""
        if not self.dataset:
            return
        for loc in self.dataset.locations:
            if loc.name == "MIT-WPU Kothrud":
                self.map_view.select_location(loc, emit=True)
                self.statusBar().showMessage("Loaded MIT-WPU Kothrud preset")
                return
        self.statusBar().showMessage("MIT-WPU Kothrud not found in loaded dataset")

    def _quick_scenario(self, disaster: DisasterType, intensity: float, duration: float, prep: float) -> None:
        """Apply a quick preset scenario."""
        self.disaster.setCurrentText(disaster.value)
        self.intensity.setValue(intensity)
        self.duration.setValue(duration)
        self.preparedness.setValue(int(prep * 100))
        if self.location:
            self.run_assessment()

    def _toggle_heatmap(self, checked: bool) -> None:
        self.map_view.toggle_heatmap(checked)

    def _toggle_grid(self, checked: bool) -> None:
        self.map_view.toggle_grid(checked)

    def _toggle_multi_hazard(self, checked: bool) -> None:
        self.map_view.toggle_multi_hazard(checked)

    def _reset_map_view(self) -> None:
        self.map_view.reset_view()

    def _update_parameter_help(self) -> None:
        help_text = {
            "Flood": "Rainfall runoff, elevation, water proximity, drainage, impervious surface, monsoon season.",
            "Wildfire": "Fire weather, vegetation fuel, dryness, wind exposure, dry season.",
            "Earthquake": "Ground shaking, soil amplification, building quality, informal housing, fault proximity.",
        }
        if hasattr(self, "parameter_help"):
            self.parameter_help.setText(help_text.get(self.disaster.currentText(), ""))

    def run_assessment(self) -> None:
        if not self.location:
            QMessageBox.information(self, "Select a location", "Click an area on the map or search for a loaded place first.")
            return
        total = self.w_hazard.value() + self.w_exposure.value() + self.w_vulnerability.value()
        if abs(total - 1.0) > 0.05:
            QMessageBox.warning(self, "AHP weights must sum to 1.0", f"Current weights sum to {total:.2f}. They will be normalized automatically.")
        scenario = Scenario(
            disaster=DisasterType(self.disaster.currentText()),
            intensity=self.intensity.value(),
            duration_hours=self.duration.value(),
            preparedness=self.preparedness.value() / 100,
        )
        # Apply time/season to location context (updates weights automatically)
        loc = LocationProfile(
            name=self.location.name,
            longitude=self.location.longitude,
            latitude=self.location.latitude,
            elevation_m=self.location.elevation_m,
            vegetation=self.location.vegetation,
            population_density=self.location.population_density,
            soil_softness=self.location.soil_softness,
            water_distance=self.location.water_distance,
            income_level=self.location.income_level,
            literacy_rate=self.location.literacy_rate,
            elderly_share=self.location.elderly_share,
            child_share=self.location.child_share,
            disability_share=self.location.disability_share,
            hospital_capacity=self.location.hospital_capacity,
            fire_station_proximity=self.location.fire_station_proximity,
            shelter_capacity=self.location.shelter_capacity,
            road_density=self.location.road_density,
            informal_settlement=self.location.informal_settlement,
            building_quality=self.location.building_quality,
            roof_type_score=self.location.roof_type_score,
            time_of_day=self.time_of_day.value(),
            season=self.season.currentText().lower(),
        )
        self.location = loc
        self.assessment = assess(self.location, scenario)
        self._assistant_context_revision += 1
        # Assessment context is rebuilt from the latest result on every question;
        # discard conversation snippets that could contradict the new result.
        self._assistant_history.clear()
        self._assistant_last_route = None
        self._append_chat_message(
            "system",
            f"Assessment context refreshed Â· {loc.name} Â· {self.assessment.risk_level.value} risk Â· {self.assessment.overall_score:.0f}/100",
        )
        self.map_view.show_assessment(self.assessment)
        self._show_result(self.assessment)
        self.statusBar().showMessage(f"Assessment complete Â· {self.assessment.risk_level.value} risk")

    def _show_result(self, result: Assessment) -> None:
        color = RISK_COLORS[result.risk_level].name()
        self.risk_badge.setText(f"{result.risk_level.value.upper()} RISK")
        self.risk_badge.setStyleSheet(f"background:{color}; color:#000000; border: 1px solid #22252b; padding:8px; font-weight:800;")
        self.score.setText(f"{result.overall_score:.0f}<span style='font-size:14px;color:#8a8f98'>/100</span>")
        ci = int(result.confidence_interval * 100)
        self.confidence.setText(f"{ci}% confidence: {result.confidence_lower:.0f}â€“{result.confidence_upper:.0f} (Ïƒ={result.mc_std:.1f}, n={result.mc_samples})")
        self.weights_label.setText(f"Weights: H={result.scenario.weight_hazard:.2f} E={result.scenario.weight_exposure:.2f} V={result.scenario.weight_vulnerability:.2f}")
        self.metrics["Hazard"].setValue(round(result.hazard_score))
        self.metrics["Exposure"].setValue(round(result.exposure_score))
        self.metrics["Vulnerability"].setValue(round(result.vulnerability_score))
        # Color-code progress bars based on score
        for key, score in (("Hazard", result.hazard_score), ("Exposure", result.exposure_score), ("Vulnerability", result.vulnerability_score)):
            bar = self.metrics[key]
            if score < 33:
                color = "#1e7d32"  # green
            elif score < 66:
                color = "#d4a017"  # amber
            else:
                color = "#d9534f"  # red
            bar.setStyleSheet(f"QProgressBar::chunk {{ background: {color}; border: none; border-radius: 3px; }}")
        impact_text = (
            f"Estimated affected radius: {result.affected_radius_km:.1f} km Â· "
            f"People affected: {result.people_affected:,} Â· "
            f"Estimated property loss: â‚¹{result.property_loss_inr:,.0f}"
        )
        self.summary.setText(result.summary + " " + impact_text)
        self.actions.setText("<b>Suggested actions</b><br>â€¢ " + "<br>â€¢ ".join(result.recommendations))
        self._generate_suggestions(result)
        self._start_pulse_animation()

        # Push to analysis tab
        self.analysis_panel.update_assessment(result, self.location)

    def _answer_question(self) -> None:
        question = self.assistant_question.text().strip()
        if not question or (hasattr(self, "_assistant_worker") and self._assistant_worker.isRunning()):
            return
        self.assistant_question.clear()
        if self._is_time_question(question):
            self._append_assistant_turn(question, self._assessment_time_answer())
            return
        if self._is_evacuation_question(question):
            self._append_assistant_turn(question, self._evacuation_answer())
            return
        if "shelter" in question.casefold():
            self._append_assistant_turn(question, self._shelter_data_answer(question))
            return
        self._append_chat_message("you", question)
        self._assistant_pending_question = question
        self._assistant_pending_revision = self._assistant_context_revision
        self.assistant_button.setText("Thinkingâ€¦")
        self.assistant_button.setEnabled(False)
        self.assistant_worker = AssistantWorker(question, self._assistant_context(question), self)
        self._assistant_worker = self.assistant_worker
        self.assistant_worker.answered.connect(self._finish_assistant_turn)
        self.assistant_worker.finished.connect(self._assistant_ready)
        self.assistant_worker.start()

    @staticmethod
    def _is_time_question(question: str) -> bool:
        q = question.casefold()
        return "time of day" in q or ("time" in q and any(word in q for word in ("assessment", "conducted", "run")))

    def _assessment_time_answer(self) -> str:
        loc = self.assessment.location if self.assessment else self.location
        configured_time = f"{loc.time_of_day:02d}:00" if loc else f"{self.time_of_day.value():02d}:00"
        if not self.assessment:
            return f"No assessment has been run. The scenario time is set to {configured_time}."
        return f"The assessment used the configured time-of-day input: {configured_time}."

    @staticmethod
    def _is_evacuation_question(question: str) -> bool:
        q = question.casefold()
        return (
            "evacuat" in q
            or "safe place" in q
            or "where is safe" in q
            or "where is it safe" in q
            or "where should i go" in q
            or "where do i go" in q
            or ("where" in q and any(word in q for word in ("go", "head", "evacuat", "safe")))
            or ("shelter" in q and any(word in q for word in ("should", "go to", "nearest", "closest", "near me", "where")))
        )

    def _shelter_data_answer(self, question: str) -> str:
        shelters = [
            f for f in (self.dataset.features if self.dataset else [])
            if (f.get("geometry") or {}).get("type") == "Point" and (f.get("properties") or {}).get("shelter_type")
        ] or shelters_dataset().features
        q = question.casefold()
        if not shelters:
            return "No shelter records are present in the current map data."
        if any(term in q for term in ("how many", "count", "number of")):
            return f"The map data lists {len(shelters)} shelters. These records are not live-verified."
        ignored = {"shelter", "capacity", "contact", "address", "listed", "please", "what", "where", "which", "tell", "about", "nearest", "closest"}
        query_words = {word for word in q.replace("?", " ").replace(",", " ").split() if len(word) > 3 and word not in ignored}
        matches = []
        for feature in shelters:
            props = feature.get("properties") or {}
            name = props.get("name", "Unnamed shelter")
            score = len(query_words.intersection(name.casefold().split()))
            if score:
                matches.append((score, feature))
        if matches:
            feature = max(matches, key=lambda item: item[0])[1]
            props = feature.get("properties") or {}
            return (
                f"{props.get('name', 'Unnamed shelter')}: {props.get('address', 'address not listed')}; "
                f"capacity {props.get('capacity', 'not listed')}; contact {props.get('contact', 'not listed')}."
            )
        names = "; ".join((f.get("properties") or {}).get("name", "Unnamed shelter") for f in shelters)
        return f"The bundled map lists {len(shelters)} shelters: {names}. Records are not live-verified."

    def _evacuation_answer(self) -> str:
        start = self.location or (self.assessment.location if self.assessment else None)
        if not start:
            return "Select your location on the map first so I can find the nearest listed shelter."
        shelter_features = [
            f for f in (self.dataset.features if self.dataset else [])
            if (f.get("geometry") or {}).get("type") == "Point"
            and (f.get("properties") or {}).get("shelter_type")
        ]
        if not shelter_features:
            shelter_features = shelters_dataset().features
        if not shelter_features:
            return "No listed shelter data is available. I can't name an evacuation destination."

        start_point = (start.longitude, start.latitude)
        distances = []
        for feature in shelter_features:
            xy = (feature["geometry"]["coordinates"][0], feature["geometry"]["coordinates"][1])
            dist = self.map_view._haversine_km(start_point, xy)
            distances.append((dist, feature))
        straight_km, nearest = min(distances, key=lambda entry: entry[0])
        route = self.map_view.compute_evacuation_route(start, shelter_features)
        has_roads = any((f.get("geometry") or {}).get("type") in ("LineString", "MultiLineString")
                        for f in (self.dataset.features if self.dataset else []))
        if route and has_roads:
            nearest = route["shelter"]
            distance_text = f"about {route['distance_km']:.1f} km by the stored road network"
            self._assistant_last_route = {"destination": (nearest.get("properties") or {}).get("name"), "distance_km": round(route["distance_km"], 1), "basis": "stored road network"}
            self.map_view.draw_evacuation_route(route)
        else:
            distance_text = f"about {straight_km:.1f} km straight-line; no mapped road route is available"
            self._assistant_last_route = {"destination": (nearest.get("properties") or {}).get("name"), "distance_km": round(straight_km, 1), "basis": "straight-line only; no mapped route"}

        props = nearest.get("properties") or {}
        address = props.get("address", "address not listed")
        details = [f"Nearest listed shelter: {props.get('name', 'Unnamed shelter')} â€” {address}.", distance_text + "."]
        if props.get("capacity") is not None:
            details.append(f"Listed capacity: {props['capacity']}.")
        if props.get("contact"):
            details.append(f"Listed contact: {props['contact']}.")
        details.append("This is the nearest shelter in the app data; follow current local-authority/emergency-service instructions.")
        return " ".join(details)

    def _assistant_context(self, question: str = "") -> str:
        lines = [
            "CrisisMap Pune disaster assessment application. Use the latest assessment as the source of truth.",
            "Assessment method: calculate hazard by disaster-specific factors, exposure from local population density, "
            "and vulnerability from community/building factors. Blend the three 0-100 scores with the assessment's "
            "AHP weights. When default weights are used, the app adjusts them for hazard, location, and season. "
            "A 500-run Monte Carlo calculation perturbs hazard/vulnerability by Â±15% and exposure by Â±10% to estimate "
            "a score interval. Radius is 0.3 + 0.3Ã—intensity + 0.1Ã—min(duration hours, 24) km. People estimate is "
            "circular impact area Ã— population-density input Ã— 5,000 people/kmÂ² Ã— intensity fraction. Property loss "
            "is impact area Ã— â‚¹500,000,000/kmÂ² Ã— min(10%, risk fraction Ã— intensity fraction Ã— 20% Ã— (1 âˆ’ building quality Ã— 0.4) "
            "Ã— (1 + informal-settlement share Ã— 0.5)); all impact values are rough "
            "scenario estimates, not forecasts or observed losses."
        ]
        if self.dataset:
            ward_count = sum((f.get("geometry") or {}).get("type") in ("Polygon", "MultiPolygon") for f in self.dataset.features)
            road_count = sum((f.get("geometry") or {}).get("type") in ("LineString", "MultiLineString") for f in self.dataset.features)
            lines.append(f"Loaded map: {self.dataset.name}; {ward_count} area features; {road_count} road features. Source: {self.dataset.source}.")
        loc = self.location or (self.assessment.location if self.assessment else None)
        if loc:
            lines.append(
                f"Selected: {loc.name}, {loc.latitude:.5f},{loc.longitude:.5f}; elevation {loc.elevation_m:.0f}m; "
                f"vegetation {loc.vegetation:.2f}; density {loc.population_density:.2f}; soil softness {loc.soil_softness:.2f}; "
                f"water distance {loc.water_distance:.2f}; building quality {loc.building_quality:.2f}; "
                f"configured time of day {loc.time_of_day:02d}:00; season {loc.season}."
            )
            lines.append("Full selected-location inputs: " + json.dumps({
                "name": loc.name,
                "elevation_m": loc.elevation_m,
                "vegetation": loc.vegetation,
                "population_density": loc.population_density,
                "soil_softness": loc.soil_softness,
                "water_distance": loc.water_distance,
                "income_level": loc.income_level,
                "literacy_rate": loc.literacy_rate,
                "elderly_share": loc.elderly_share,
                "child_share": loc.child_share,
                "disability_share": loc.disability_share,
                "hospital_capacity": loc.hospital_capacity,
                "fire_station_proximity": loc.fire_station_proximity,
                "shelter_capacity": loc.shelter_capacity,
                "road_density": loc.road_density,
                "informal_settlement": loc.informal_settlement,
                "building_quality": loc.building_quality,
                "roof_type_score": loc.roof_type_score,
                "time_of_day": loc.time_of_day,
                "season": loc.season,
            }, separators=(",", ":")))
        q = question.casefold()
        if any(word in q for word in ("shelter", "evacuat", "safe place")):
            shelters = [
                f for f in (self.dataset.features if self.dataset else [])
                if (f.get("geometry") or {}).get("type") == "Point" and (f.get("properties") or {}).get("shelter_type")
            ] or shelters_dataset().features
            shelter_facts = []
            for feature in shelters:
                props = feature.get("properties") or {}
                coord = (feature.get("geometry") or {}).get("coordinates", [])
                shelter_facts.append(
                    f"{props.get('name', 'Unnamed')}; {props.get('address', 'no address')}; "
                    f"capacity {props.get('capacity', 'unknown')}; contact {props.get('contact', 'unknown')}; "
                    f"coordinates {coord}."
                )
            lines.append(f"Shelter records in loaded/bundled data: {len(shelters)}. " + " ".join(shelter_facts))
            if loc:
                road_count = sum((f.get("geometry") or {}).get("type") in ("LineString", "MultiLineString") for f in (self.dataset.features if self.dataset else []))
                lines.append(f"Road-network features available: {road_count}.")
                route = self.map_view.compute_evacuation_route(loc, shelters)
                if route:
                    props = route["shelter"].get("properties") or {}
                    self._assistant_last_route = {
                        "destination": props.get("name", "Unnamed shelter"),
                        "address": props.get("address", "address not listed"),
                        "distance_km": round(route["distance_km"], 1),
                        "basis": "stored road network",
                    }
        a = self.assessment
        if a:
            s = a.scenario
            lines.append(
                f"Assessment: {s.disaster.value}, intensity {s.intensity:.1f}/10, duration {s.duration_hours:g}h, preparedness {s.preparedness:.0%}; "
                f"risk {a.risk_level.value}, score {a.overall_score:.1f}/100; hazard {a.hazard_score:.1f}, exposure {a.exposure_score:.1f}, vulnerability {a.vulnerability_score:.1f}; "
                f"score interval {a.confidence_lower:.1f}-{a.confidence_upper:.1f}; affected radius estimate {a.affected_radius_km:.1f}km; "
                f"people estimate {a.people_affected}; property-loss estimate INR {a.property_loss_inr:.0f}."
            )
            lines.append("Complete latest assessment record: " + json.dumps(a.to_dict(), separators=(",", ":")))
            if any(word in q for word in ("factor", "why", "driver", "cause", "contribut")):
                lines.append("Hazard factors: " + json.dumps(a.hazard_factors or {}, separators=(",", ":")))
                lines.append("Vulnerability factors: " + json.dumps(a.vulnerability_factors or {}, separators=(",", ":")))
            if any(word in q for word in ("recommend", "suggest", "action", "should", "prepare")):
                lines.append("Recommendations: " + " ".join(a.recommendations))
        else:
            lines.append("Assessment status: NOT RUN. Do not claim a risk score or assessment result.")
            lines.append(
                f"Current scenario inputs only: {self.disaster.currentText()}, intensity {self.intensity.value():g}/10, "
                f"duration {self.duration.value():g}h, preparedness {self.preparedness.value()}%."
            )
        if self._assistant_history:
            previous_q, previous_a = self._assistant_history[-1]
            lines.append(f"Previous conversation: Q {previous_q[:100]} A {previous_a[:140]}")
        if getattr(self, "_assistant_last_route", None):
            lines.append(f"Most recently computed evacuation route: {self._assistant_last_route}.")
        return "\n".join(lines)

    def _finish_assistant_turn(self, answer: str) -> None:
        if getattr(self, "_assistant_pending_revision", self._assistant_context_revision) != self._assistant_context_revision:
            answer = "The assessment changed while I was answering. Please ask again for an answer based on the latest results."
        self._append_chat_message("assistant", answer)
        self._assistant_history.append((self._assistant_pending_question, answer))
        self._assistant_history = self._assistant_history[-4:]

    def _assistant_ready(self) -> None:
        self.assistant_button.setEnabled(True)
        self.assistant_button.setText("Ask")

    def _append_assistant_turn(self, question: str, answer: str) -> None:
        self._append_chat_message("you", question)
        self._append_chat_message("assistant", answer)
        self._assistant_history.append((question, answer))
        self._assistant_history = self._assistant_history[-4:]

    def _append_chat_message(self, role: str, message: str) -> None:
        styles = {
            "system": ("SYSTEM", "#172335", "#a9c8f4", "left"),
            "you": ("YOU", "#163a5c", "#e7f3ff", "right"),
            "assistant": ("CRISISMAP AI", "#18231f", "#e7f8eb", "left"),
        }
        label, background, foreground, alignment = styles[role]
        safe_message = escape(message).replace("\n", "<br>")
        bubble = (
            f'<table width="100%" cellspacing="0"><tr><td align="{alignment}">'
            f'<table bgcolor="{background}" cellpadding="10"><tr><td>'
            f'<font color="{foreground}"><b>{label}</b><br>{safe_message}</font>'
            "</td></tr></table></td></tr></table><br>"
        )
        cursor = self.assistant_chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(bubble)
        self.assistant_chat.setTextCursor(cursor)
        self.assistant_chat.ensureCursorVisible()

    def _generate_suggestions(self, result: Assessment) -> None:
        suggestions = []
        loc = self.location
        if not loc:
            return

        if result.risk_level is RiskLevel.LOW:
            suggestions.append("Routine monitoring only. Standard preparedness measures are sufficient.")
        elif result.risk_level is RiskLevel.MODERATE:
            suggestions.append("Review evacuation routes and verify emergency supply kits.")
            suggestions.append("Ensure drainage systems are clear for potential flooding.")
        elif result.risk_level is RiskLevel.HIGH:
            suggestions.append("Prepare evacuation plans and identify the nearest shelter immediately.")
            suggestions.append("Secure loose outdoor objects and reinforce windows if high winds are expected.")
        else:
            suggestions.append("IMMEDIATE ACTION: Evacuate to designated shelter if instructed by authorities.")
            suggestions.append("Prepare emergency go-bags with water, food, medications, and documents.")
            suggestions.append("Shut off utilities if safe to do so before leaving the area.")

        if loc.elevation_m < 50:
            suggestions.append(f"Low elevation ({loc.elevation_m:.0f} m) increases flood exposure â€” prioritize higher ground routes.")
        if loc.vegetation > 0.6:
            suggestions.append("High vegetation density raises wildfire risk â€” create defensible space around structures.")
        if loc.population_density > 0.7:
            suggestions.append("High population density â€” plan staggered evacuation to avoid congestion.")
        if loc.informal_settlement > 0.3:
            suggestions.append("High informal settlement density â€” prioritize structural reinforcement and community alerts.")
        if loc.hospital_capacity < 0.3:
            suggestions.append("Low hospital capacity â€” pre-identify alternate medical facilities.")
        if loc.fire_station_proximity < 0.3:
            suggestions.append("Fire station far away â€” ensure on-site fire suppression equipment.")
        if loc.shelter_capacity < 0.3:
            suggestions.append("Limited shelter capacity â€” coordinate with nearby municipalities.")
        if loc.building_quality < 0.4:
            suggestions.append("Poor building quality â€” prioritize seismic retrofitting and wind bracing.")
        if loc.time_of_day >= 22 or loc.time_of_day <= 6:
            suggestions.append("Night-time scenario assumed â€” mobility is reduced; evacuate earlier.")
        if loc.season == "monsoon" and result.scenario.disaster is DisasterType.FLOOD:
            suggestions.append("Monsoon season â€” expect amplified flood risk; monitor river levels continuously.")

        # Infrastructure resilience suggestions
        if loc.road_density < 0.4:
            suggestions.append("Low road density may delay evacuation â€” identify alternative routes in advance.")
        if loc.hospital_capacity < 0.5:
            suggestions.append("Limited hospital capacity â€” coordinate with nearby medical centers for surge capacity.")
        if loc.fire_station_proximity < 0.4:
            suggestions.append("Fire station beyond optimal range â€” ensure on-site fire suppression equipment.")

        # Utility and service suggestions
        if result.scenario.disaster is DisasterType.EARTHQUAKE:
            suggestions.append("Post-earthquake: inspect gas lines, electrical systems, and water mains before re-entry.")
            suggestions.append("Expect aftershocks â€” keep evacuation routes clear for at least 24 hours.")
        if result.scenario.disaster is DisasterType.FLOOD:
            suggestions.append("Avoid walking or driving through floodwaters â€” as little as 15 cm can move a vehicle.")
            suggestions.append("Boil water or use purification tablets until authorities declare supply safe.")
        if result.scenario.disaster is DisasterType.WILDFIRE:
            suggestions.append("Monitor air quality â€” wear N95 masks if smoke levels are high.")
            suggestions.append("Create a defensible space of at least 9 meters around structures.")

        # Socioeconomic and community suggestions
        if loc.informal_settlement > 0.4:
            suggestions.append("High informal settlement density â€” prioritize community-based early warning systems.")
        if loc.population_density > 0.75:
            suggestions.append("Very high population density â€” establish multiple assembly points to prevent crowding.")
        if loc.elderly_share > 0.15:
            suggestions.append("Significant elderly population â€” prioritize mobility assistance in evacuation plans.")
        if loc.child_share > 0.2:
            suggestions.append("High child population â€” coordinate with schools for child-safe evacuation procedures.")

        # Economic impact suggestions
        if result.overall_score > 60:
            suggestions.append("High overall risk â€” consider business continuity planning and asset protection.")
            suggestions.append("Document property and assets with photos before the event for insurance claims.")

        # Environmental suggestions
        if loc.vegetation > 0.7:
            suggestions.append("Dense vegetation area â€” coordinate with forest department for firebreak maintenance.")
        if loc.water_distance < 0.2:
            suggestions.append("Close proximity to water body â€” monitor water levels and erosion risk during heavy rain.")

        self.suggestions.setText("<b>Suggestions</b><br>â€¢ " + "<br>â€¢ ".join(suggestions))

    def _start_pulse_animation(self) -> None:
        if self._anim_timer:
            self._anim_timer.stop()
        self._anim_timer = QTimer(self)
        self._pulse_state = 0
        self._anim_timer.timeout.connect(self._tick_pulse)
        self._anim_timer.start(60)

    def _tick_pulse(self) -> None:
        if not self._anim_timer or not self.assessment:
            return
        self._pulse_state = (self._pulse_state + 1) % 6
        opacity = 1.0 if self._pulse_state < 3 else 0.6
        self.risk_badge.setStyleSheet(
            f"background:{RISK_COLORS[self.assessment.risk_level].name()}; color:#000000; "
            f"border: 1px solid #22252b; padding:8px; font-weight:800; opacity:{opacity};"
        )
        if self._pulse_state == 5:
            self._anim_timer.stop()
            self.risk_badge.setStyleSheet(
                f"background:{RISK_COLORS[self.assessment.risk_level].name()}; color:#000000; "
                f"border: 1px solid #22252b; padding:8px; font-weight:800;"
            )

    def _save_baseline(self) -> None:
        """Save current assessment as baseline for comparison."""
        if not self.assessment:
            QMessageBox.information(self, "Nothing to save", "Run an assessment first.")
            return
        self._comparison = self.assessment
        self.statusBar().showMessage("Baseline saved for comparison")

    def _show_comparison(self) -> None:
        """Show comparison dialog between baseline and current assessment."""
        if not self._comparison:
            QMessageBox.information(self, "No baseline", "Save a baseline assessment first using 'Save as Baseline'.")
            return
        if not self.assessment:
            QMessageBox.information(self, "No current result", "Run an assessment to compare against the baseline.")
            return

        before = self._comparison
        after = self.assessment

        lines = ["Scenario Comparison", "=" * 40, ""]
        lines.append(f"Location: {after.location.name}")
        lines.append("")
        lines.append(f"{'Metric':<25} {'Before':>10} {'After':>10} {'Delta':>10}")
        lines.append("-" * 55)

        metrics = [
            ("Overall Score", before.overall_score, after.overall_score),
            ("Hazard Score", before.hazard_score, after.hazard_score),
            ("Exposure Score", before.exposure_score, after.exposure_score),
            ("Vulnerability Score", before.vulnerability_score, after.vulnerability_score),
            ("Affected Radius (km)", before.affected_radius_km, after.affected_radius_km),
            ("People Affected", before.people_affected, after.people_affected),
            ("Property Loss (â‚¹)", before.property_loss_inr, after.property_loss_inr),
        ]
        for name, b, a in metrics:
            delta = a - b
            delta_str = f"{delta:+.1f}" if isinstance(b, float) else f"{delta:+,}"
            lines.append(f"{name:<25} {b:>10.1f} {a:>10.1f} {delta_str:>10}")

        lines.append("")
        lines.append(f"Before: {before.scenario.disaster.value} {before.scenario.intensity}/10, "
                     f"{before.scenario.duration_hours}h, prep={before.scenario.preparedness:.0%}")
        lines.append(f"After:  {after.scenario.disaster.value} {after.scenario.intensity}/10, "
                     f"{after.scenario.duration_hours}h, prep={after.scenario.preparedness:.0%}")

        QMessageBox.information(self, "Scenario Comparison", "\n".join(lines))

    def clear_result(self) -> None:
        if self._anim_timer:
            self._anim_timer.stop()
        self.assessment = None
        self._comparison = None
        self.location = None
        if hasattr(self, "map_view"):
            self.map_view.clear_assessment()
            self.map_view.clear_selection()
        if hasattr(self, "risk_badge"):
            self.risk_badge.setText("NO RESULT")
            self.risk_badge.setStyleSheet("")
            self.score.setText("â€”")
            self.confidence.setText("")
            self.weights_label.setText("")
            for bar in self.metrics.values():
                bar.setValue(0)
            self.summary.setText("Configure a scenario and select a location to generate an assessment.")
            self.actions.clear()
            self.suggestions.setText("")
            if hasattr(self, "analysis_panel"):
                self.analysis_panel.clear()
        if hasattr(self, "location_label"):
            self.location_label.setText("Select an area on the map")
        if hasattr(self, "search"):
            self.search.clear()

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

    def export_pdf_report(self) -> None:
        """Export the current assessment as a PDF report."""
        if not self.assessment:
            QMessageBox.information(self, "Nothing to export", "Run an assessment before exporting a PDF report.")
            return
        safe_name = "".join(ch if ch.isalnum() else "-" for ch in self.assessment.location.name.lower()).strip("-")
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF report", f"crisismap-{safe_name}.pdf", "PDF (*.pdf)")
        if path:
            try:
                charts = {
                    "risk_gauge": self.analysis_panel.gauge.figure(),
                    "risk_bar": self.analysis_panel.bar_chart.figure(),
                    "risk_breakdown": self.analysis_panel.breakdown.figure(),
                    "vulnerability_radar": self.analysis_panel.radar.figure(),
                }
                export_pdf(self.assessment, path, charts=charts)
                self.statusBar().showMessage(f"Saved PDF report to {path}")
            except Exception as exc:
                QMessageBox.critical(self, "Could not export PDF", str(exc))

    def export_charts_report(self) -> None:
        """Export all chart images as PNG files."""
        if not self.assessment:
            QMessageBox.information(self, "Nothing to export", "Run an assessment before exporting charts.")
            return
        safe_name = "".join(ch if ch.isalnum() else "-" for ch in self.assessment.location.name.lower()).strip("-")
        directory = QFileDialog.getExistingDirectory(self, "Select folder to save charts")
        if not directory:
            return
        try:
            saved = self.analysis_panel.export_charts(directory)
            self.statusBar().showMessage(f"Exported {len(saved)} chart images to {directory}")
        except Exception as exc:
            QMessageBox.critical(self, "Could not export charts", str(exc))

    def export_html_report(self) -> None:
        """Export a print-friendly HTML report."""
        if not self.assessment:
            QMessageBox.information(self, "Nothing to export", "Run an assessment before exporting a report.")
            return
        safe_name = "".join(ch if ch.isalnum() else "-" for ch in self.assessment.location.name.lower()).strip("-")
        path, _ = QFileDialog.getSaveFileName(self, "Export HTML report", f"crisismap-{safe_name}.html", "HTML (*.html)")
        if not path:
            return
        try:
            html = self._build_html_report()
            Path(path).write_text(html, encoding="utf-8")
            self.statusBar().showMessage(f"Saved HTML report to {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Could not export HTML report", str(exc))

    def _build_html_report(self) -> str:
        """Build a print-friendly HTML report from the current assessment."""
        a = self.assessment
        loc = a.location
        sc = a.scenario
        risk_color = {
            "LOW": "#1e7d32",
            "MODERATE": "#d4a017",
            "HIGH": "#d9534f",
            "EXTREME": "#b00020",
        }.get(a.risk_level.value, "#64b5f6")

        # Time series data
        ts = simulate_time_series(loc, sc, steps=12)
        ts_rows = ""
        for point in ts:
            ts_rows += f"<tr><td>{point['hour']:.1f}</td><td>{point['hazard']:.1f}</td><td>{point['exposure']:.1f}</td><td>{point['vulnerability']:.1f}</td><td>{point['overall']:.1f}</td></tr>"

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CrisisMap Assessment Report</title>
<style>
  @page {{ size: A4; margin: 15mm; }}
  body {{ font-family: 'Segoe UI', 'DejaVu Sans', sans-serif; color: #202124; line-height: 1.5; }}
  .header {{ text-align: center; border-bottom: 3px solid #1a73e8; padding-bottom: 15px; margin-bottom: 25px; }}
  .header h1 {{ color: #1a73e8; margin: 0; font-size: 28px; }}
  .header .subtitle {{ color: #5f6368; font-size: 14px; }}
  .info-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 25px; }}
  .info-card {{ background: #f8f9fa; border: 1px solid #dadce0; border-radius: 8px; padding: 12px; }}
  .info-card .label {{ font-size: 11px; color: #5f6368; text-transform: uppercase; letter-spacing: 0.5px; }}
  .info-card .value {{ font-size: 15px; font-weight: 600; color: #202124; }}
  .risk-badge {{ display: inline-block; padding: 10px 20px; border-radius: 8px; color: #fff; font-weight: 700; font-size: 16px; }}
  .metrics-table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; }}
  .metrics-table th {{ background: #202124; color: #fff; padding: 10px; text-align: left; font-size: 13px; }}
  .metrics-table td {{ padding: 10px; border: 1px solid #dadce0; }}
  .metrics-table tr:nth-child(even) {{ background: #f8f9fa; }}
  .chart-section {{ margin-bottom: 25px; }}
  .chart-section h2 {{ color: #1a73e8; font-size: 18px; border-bottom: 2px solid #1a73e8; padding-bottom: 5px; }}
  .suggestions {{ background: #fffbeb; border: 1px solid #fcd34d; border-radius: 8px; padding: 15px; margin-bottom: 25px; }}
  .suggestions h2 {{ color: #92400e; font-size: 16px; margin-top: 0; }}
  .suggestions ul {{ margin: 0; padding-left: 20px; }}
  .suggestions li {{ margin-bottom: 6px; }}
  .footer {{ margin-top: 30px; border-top: 1px solid #dadce0; padding-top: 15px; font-size: 11px; color: #5f6368; }}
  .time-series-table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; }}
  .time-series-table th {{ background: #f1f3f4; padding: 8px; text-align: center; border: 1px solid #dadce0; font-size: 12px; }}
  .time-series-table td {{ padding: 8px; text-align: center; border: 1px solid #dadce0; font-size: 12px; }}
  .print-note {{ font-size: 11px; color: #5f6368; font-style: italic; text-align: center; margin-bottom: 20px; }}
</style>
</head>
<body>
  <div class="print-note">CrisisMap â€” Print-friendly Report. Print with background colors enabled.</div>

  <div class="header">
    <h1>CRISIS MAP</h1>
    <div class="subtitle">Pune Disaster Impact Assessment Report</div>
  </div>

  <div class="info-grid">
    <div class="info-card"><div class="label">Location</div><div class="value">{loc.name}</div></div>
    <div class="info-card"><div class="label">Coordinates</div><div class="value">{loc.latitude:.4f}Â°N, {loc.longitude:.4f}Â°E</div></div>
    <div class="info-card"><div class="label">Elevation</div><div class="value">{loc.elevation_m:.0f} m</div></div>
    <div class="info-card"><div class="label">Disaster</div><div class="value">{sc.disaster.value}</div></div>
    <div class="info-card"><div class="label">Intensity</div><div class="value">{sc.intensity:.1f} / 10</div></div>
    <div class="info-card"><div class="label">Duration</div><div class="value">{sc.duration_hours:.1f} h</div></div>
    <div class="info-card"><div class="label">Preparedness</div><div class="value">{sc.preparedness:.0%}</div></div>
    <div class="info-card"><div class="label">Time of Day</div><div class="value">{loc.time_of_day}:00 hrs</div></div>
    <div class="info-card"><div class="label">Season</div><div class="value">{loc.season.title()}</div></div>
    <div class="info-card"><div class="label">Generated</div><div class="value">{datetime.now().strftime('%d %b %Y, %I:%M %p')}</div></div>
  </div>

  <div style="text-align: center; margin-bottom: 25px;">
    <span class="risk-badge" style="background-color: {risk_color};">
      {a.risk_level.value.upper()} RISK â€” Score: {a.overall_score:.0f}/100
    </span>
  </div>

  <p><b>Summary:</b> {a.summary}</p>
  <p><b>Affected Radius:</b> {a.affected_radius_km:.1f} km &nbsp;|&nbsp; <b>People Affected:</b> {a.people_affected:,} &nbsp;|&nbsp; <b>Estimated Property Loss:</b> â‚¹{a.property_loss_inr:,.0f}</p>
  <p><b>Confidence:</b> {int(a.confidence_interval * 100)}% interval: {a.confidence_lower:.0f}â€“{a.confidence_upper:.0f} (Ïƒ={a.mc_std:.1f}, n={a.mc_samples})</p>

  <table class="metrics-table">
    <thead><tr><th>Component</th><th>Score</th><th>Weight</th></tr></thead>
    <tbody>
      <tr><td>Physical Hazard</td><td>{a.hazard_score:.1f}</td><td>{sc.weight_hazard:.0%}</td></tr>
      <tr><td>People Exposure</td><td>{a.exposure_score:.1f}</td><td>{sc.weight_exposure:.0%}</td></tr>
      <tr><td>Social Vulnerability</td><td>{a.vulnerability_score:.1f}</td><td>{sc.weight_vulnerability:.0%}</td></tr>
    </tbody>
  </table>

  <div class="chart-section">
    <h2>Risk Factor Breakdown</h2>
    <table class="time-series-table">
      <thead><tr><th>Hour</th><th>Hazard</th><th>Exposure</th><th>Vulnerability</th><th>Overall</th></tr></thead>
      <tbody>{ts_rows}</tbody>
    </table>
  </div>

  <div class="suggestions">
    <h2>Suggested Actions</h2>
    <ul>
      {"".join(f"<li>{r}</li>" for r in a.recommendations)}
    </ul>
  </div>

  <div class="footer">
    CrisisMap â€” Educational tool, not for emergency decisions
  </div>
</body>
</html>"""
        return html

    def save_scenario(self) -> None:
        """Save current scenario configuration to a local JSON file."""
        if not self.location:
            QMessageBox.information(self, "Nothing to save", "Select a location and configure a scenario first.")
            return
        scenario_data = {
            "location": {
                "name": self.location.name,
                "longitude": self.location.longitude,
                "latitude": self.location.latitude,
                "elevation_m": self.location.elevation_m,
                "vegetation": self.location.vegetation,
                "population_density": self.location.population_density,
                "soil_softness": self.location.soil_softness,
                "water_distance": self.location.water_distance,
                "income_level": self.location.income_level,
                "literacy_rate": self.location.literacy_rate,
                "elderly_share": self.location.elderly_share,
                "child_share": self.location.child_share,
                "disability_share": self.location.disability_share,
                "hospital_capacity": self.location.hospital_capacity,
                "fire_station_proximity": self.location.fire_station_proximity,
                "shelter_capacity": self.location.shelter_capacity,
                "road_density": self.location.road_density,
                "informal_settlement": self.location.informal_settlement,
                "building_quality": self.location.building_quality,
                "roof_type_score": self.location.roof_type_score,
                "time_of_day": self.location.time_of_day,
                "season": self.location.season,
            },
            "scenario": {
                "disaster": self.disaster.currentText(),
                "intensity": self.intensity.value(),
                "duration_hours": self.duration.value(),
                "preparedness": self.preparedness.value() / 100,
                "weight_hazard": self.w_hazard.value(),
                "weight_exposure": self.w_exposure.value(),
                "weight_vulnerability": self.w_vulnerability.value(),
            },
        }
        safe_name = "".join(ch if ch.isalnum() else "-" for ch in self.location.name.lower()).strip("-")
        path, _ = QFileDialog.getSaveFileName(self, "Save scenario", f"crisismap-scenario-{safe_name}.json", "JSON (*.json)")
        if path:
            try:
                Path(path).write_text(json.dumps(scenario_data, indent=2), encoding="utf-8")
                self.statusBar().showMessage(f"Saved scenario locally to {path}")
            except OSError as exc:
                QMessageBox.critical(self, "Could not save scenario", str(exc))

    def load_scenario(self) -> None:
        """Load scenario configuration from a local JSON file."""
        path, _ = QFileDialog.getOpenFileName(self, "Load scenario", str(Path.home()), "JSON (*.json)")
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            loc_data = data["location"]
            sc_data = data["scenario"]
            self.disaster.setCurrentText(sc_data["disaster"])
            self.intensity.setValue(sc_data["intensity"])
            self.duration.setValue(sc_data["duration_hours"])
            self.preparedness.setValue(int(sc_data["preparedness"] * 100))
            self.w_hazard.setValue(sc_data["weight_hazard"])
            self.w_exposure.setValue(sc_data["weight_exposure"])
            self.w_vulnerability.setValue(sc_data["weight_vulnerability"])
            self.time_of_day.setValue(loc_data.get("time_of_day", 12))
            self.season.setCurrentText(loc_data.get("season", "mixed").title())
            # Find matching location in dataset
            if self.dataset:
                for loc in self.dataset.locations:
                    if loc.name == loc_data["name"]:
                        self.map_view.select_location(loc, emit=True)
                        break
            self.statusBar().showMessage(f"Loaded scenario from {path}")
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            QMessageBox.critical(self, "Could not load scenario", str(exc))

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_F1:
            self.show_about()
        elif key == Qt.Key.Key_F5:
            if self.location:
                self.run_assessment()
            else:
                QMessageBox.information(self, "Select a location", "Click an area on the map or search for a loaded place first.")
        elif key == Qt.Key.Key_Escape:
            self.clear_result()
        elif key == Qt.Key.Key_1:
            self._quick_scenario(DisasterType.FLOOD, 7.0, 24, 0.45)
        elif key == Qt.Key.Key_2:
            self._quick_scenario(DisasterType.WILDFIRE, 6.0, 12, 0.50)
        elif key == Qt.Key.Key_3:
            self._quick_scenario(DisasterType.EARTHQUAKE, 7.0, 2, 0.55)
        elif key == Qt.Key.Key_H:
            self.heat_action.trigger()
        elif key == Qt.Key.Key_G:
            self.grid_action.trigger()
        super().keyPressEvent(event)

    def _compute_evacuation_route(self) -> None:
        """Compute evacuation route from selected location to nearest shelter."""
        if not self.location:
            QMessageBox.information(self, "Select a location", "Click an area on the map first to set your starting point.")
            return

        # Load shelters if not already loaded
        shelters = []
        for feature in (self.dataset.features if self.dataset else []):
            if feature.get("geometry", {}).get("type") == "Point":
                props = feature.get("properties") or {}
                if props.get("shelter_type"):
                    shelters.append(feature)

        if not shelters:
            QMessageBox.information(self, "No shelters", "Load Pune shelters first via Map â†’ Load Pune shelters.")
            return

        route = self.map_view.compute_evacuation_route(self.location, shelters)
        if not route:
            QMessageBox.warning(self, "No route found", "Could not compute evacuation route to the nearest shelter.")
            return

        self.map_view.draw_evacuation_route(route)
        shelter_name = route["shelter"]["properties"].get("name", "Unknown Shelter")
        capacity = route["shelter"]["properties"].get("capacity", "N/A")
        self.statusBar().showMessage(
            f"Evacuation route to {shelter_name} (capacity: {capacity}) â€” {route['distance_km']:.1f} km"
        )

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About CrisisMap",
            "<b>CrisisMap 0.3.0</b><br><br>Pune disaster-impact assessment with multi-factor hazard modeling, "
            "AHP weighting, Monte Carlo uncertainty, and real Pune map data.<br><br>"
            "Assessment only â€” not prediction or emergency advice.",
        )
