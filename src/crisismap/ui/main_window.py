from __future__ import annotations

import json
import random
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..data_repository import MapDataset, bundled_dataset, load_geojson, pune_dataset, procedural_dataset
from ..export import save_assessment
from ..export_pdf import export_pdf
from ..models import Assessment, DisasterType, LocationProfile, RiskLevel, Scenario
from ..simulation import assess
from .analysis_panel import AnalysisPanel
from .chart_widgets import BarChartWidget, RiskBreakdownWidget, RiskGaugeWidget
from .map_view import MapView, RISK_COLORS


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CrisisMap - Offline Impact Assessment")
        self.resize(1440, 850)
        self.setMinimumSize(1080, 680)
        self.dataset: MapDataset | None = None
        self.location: LocationProfile | None = None
        self.assessment: Assessment | None = None
        self._anim_timer: QTimer | None = None
        self._heat_enabled: bool = True
        self._grid_enabled: bool = True
        self._build_menu()
        self._build_ui()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("")
        self.load_dataset(pune_dataset())

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = QAction("Open GeoJSON…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_geojson)
        save_action = QAction("Save scenario…", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_scenario)
        load_action = QAction("Load scenario…", self)
        load_action.setShortcut(QKeySequence("Ctrl+O"))
        load_action.triggered.connect(self.load_scenario)
        export_action = QAction("Export assessment…", self)
        export_action.triggered.connect(self.export_assessment)
        export_pdf_action = QAction("Export PDF report…", self)
        export_pdf_action.triggered.connect(self.export_pdf_report)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addActions([open_action, save_action, load_action, export_action, export_pdf_action])
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        map_menu = self.menuBar().addMenu("&Map")
        demo_action = QAction("Load demo region", self)
        demo_action.triggered.connect(lambda: self.load_dataset(bundled_dataset()))
        pune_action = QAction("Load Pune wards (real map)", self)
        pune_action.triggered.connect(lambda: self.load_dataset(pune_dataset()))
        terrain_action = QAction("Generate procedural terrain", self)
        terrain_action.triggered.connect(self.generate_terrain)
        map_menu.addActions([demo_action, pune_action, terrain_action])

        view_menu = self.menuBar().addMenu("&View")
        self.heat_action = QAction("Heatmap layer", self, checkable=True)
        self.heat_action.setChecked(True)
        self.heat_action.triggered.connect(self._toggle_heatmap)
        self.grid_action = QAction("Coordinate grid", self, checkable=True)
        self.grid_action.setChecked(True)
        self.grid_action.triggered.connect(self._toggle_grid)
        view_menu.addActions([self.heat_action, self.grid_action])

        help_menu = self.menuBar().addMenu("&Help")
        about_action = QAction("About CrisisMap", self)
        about_action.triggered.connect(self.show_about)
        offline_status_action = QAction("Offline Status", self)
        offline_status_action.setToolTip("Verify app works fully offline")
        offline_status_action.triggered.connect(self.show_offline_status)
        help_menu.addActions([offline_status_action, about_action])

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

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._control_panel())

        map_container = QFrame()
        map_container.setObjectName("panel")
        map_layout = QVBoxLayout(map_container)
        map_layout.setContentsMargins(2, 2, 2, 2)
        self.map_view = MapView()
        self.map_view.location_selected.connect(self._select_location)
        self.map_view.hovered_location.connect(self._on_hover_location)
        map_layout.addWidget(self.map_view)
        # Map zoom controls
        zoom_row = QHBoxLayout()
        zoom_in = QPushButton("+")
        zoom_in.setObjectName("zoomButton")
        zoom_in.setToolTip("Zoom in")
        zoom_in.clicked.connect(lambda: self.map_view.scale(1.18, 1.18))
        zoom_out = QPushButton("-")
        zoom_out.setObjectName("zoomButton")
        zoom_out.setToolTip("Zoom out")
        zoom_out.clicked.connect(lambda: self.map_view.scale(1 / 1.18, 1 / 1.18))
        zoom_reset = QPushButton("↺")
        zoom_reset.setObjectName("zoomButton")
        zoom_reset.setToolTip("Reset view")
        zoom_reset.clicked.connect(self._reset_map_view)
        zoom_row.addWidget(zoom_in)
        zoom_row.addWidget(zoom_out)
        zoom_row.addWidget(zoom_reset)
        zoom_row.addStretch()
        map_layout.addLayout(zoom_row)
        splitter.addWidget(map_container)
        splitter.addWidget(self._results_panel())
        splitter.setSizes([340, 760, 340])
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
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        title = QLabel("Scenario setup")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        layout.addWidget(self._section_label("01  LOCATION"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search Pune locality…")
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

        self.score = QLabel("—")
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
        self.dataset = dataset
        self.location = None
        self.assessment = None
        self.map_view.set_dataset(dataset)
        self.location_label.setText("Select an area on the map")
        self.search.clear()
        self.clear_result()
        self.statusBar().showMessage(f"Loaded {dataset.name}")

    def _select_location(self, location: LocationProfile) -> None:
        self.location = location
        self.search.setText(location.name)
        self.location_label.setText(
            f"<b>{location.name}</b><br>"
            f"{location.latitude:.4f}, {location.longitude:.4f}<br>"
            f"Elevation {location.elevation_m:.0f} m · "
            f"Income {location.income_level:.0%} · Literacy {location.literacy_rate:.0%}"
        )
        self.statusBar().showMessage(f"Selected {location.name}")

    def _on_hover_location(self, name: str) -> None:
        if self.location is None:
            self.location_label.setText(f"<b>{name}</b>")

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

    def _reset_map_view(self) -> None:
        self.map_view.resetTransform()
        self.map_view.fitInView(self.map_view.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

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
        self.map_view.show_assessment(self.assessment)
        self._show_result(self.assessment)
        self.statusBar().showMessage(f"Assessment complete · {self.assessment.risk_level.value} risk")

    def _show_result(self, result: Assessment) -> None:
        color = RISK_COLORS[result.risk_level].name()
        self.risk_badge.setText(f"{result.risk_level.value.upper()} RISK")
        self.risk_badge.setStyleSheet(f"background:{color}; color:#000000; border: 1px solid #22252b; padding:8px; font-weight:800;")
        self.score.setText(f"{result.overall_score:.0f}<span style='font-size:14px;color:#8a8f98'>/100</span>")
        ci = int(result.confidence_interval * 100)
        self.confidence.setText(f"{ci}% confidence: {result.confidence_lower:.0f}–{result.confidence_upper:.0f} (σ={result.mc_std:.1f}, n={result.mc_samples})")
        self.weights_label.setText(f"Weights: H={result.scenario.weight_hazard:.2f} E={result.scenario.weight_exposure:.2f} V={result.scenario.weight_vulnerability:.2f}")
        self.metrics["Hazard"].setValue(round(result.hazard_score))
        self.metrics["Exposure"].setValue(round(result.exposure_score))
        self.metrics["Vulnerability"].setValue(round(result.vulnerability_score))
        impact_text = (
            f"Estimated affected radius: {result.affected_radius_km:.1f} km · "
            f"People affected: {result.people_affected:,} · "
            f"Estimated property loss: ₹{result.property_loss_inr:,.0f}"
        )
        self.summary.setText(result.summary + " " + impact_text)
        self.actions.setText("<b>Suggested actions</b><br>• " + "<br>• ".join(result.recommendations))
        self._generate_suggestions(result)
        self._start_pulse_animation()

        # Push to analysis tab
        self.analysis_panel.update_assessment(result, self.location)

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
            suggestions.append(f"Low elevation ({loc.elevation_m:.0f} m) increases flood exposure — prioritize higher ground routes.")
        if loc.vegetation > 0.6:
            suggestions.append("High vegetation density raises wildfire risk — create defensible space around structures.")
        if loc.population_density > 0.7:
            suggestions.append("High population density — plan staggered evacuation to avoid congestion.")
        if loc.informal_settlement > 0.3:
            suggestions.append("High informal settlement density — prioritize structural reinforcement and community alerts.")
        if loc.hospital_capacity < 0.3:
            suggestions.append("Low hospital capacity — pre-identify alternate medical facilities.")
        if loc.fire_station_proximity < 0.3:
            suggestions.append("Fire station far away — ensure on-site fire suppression equipment.")
        if loc.shelter_capacity < 0.3:
            suggestions.append("Limited shelter capacity — coordinate with nearby municipalities.")
        if loc.building_quality < 0.4:
            suggestions.append("Poor building quality — prioritize seismic retrofitting and wind bracing.")
        if loc.time_of_day >= 22 or loc.time_of_day <= 6:
            suggestions.append("Night-time scenario assumed — mobility is reduced; evacuate earlier.")
        if loc.season == "monsoon" and result.scenario.disaster is DisasterType.FLOOD:
            suggestions.append("Monsoon season — expect amplified flood risk; monitor river levels continuously.")

        # Infrastructure resilience suggestions
        if loc.road_density < 0.4:
            suggestions.append("Low road density may delay evacuation — identify alternative routes in advance.")
        if loc.hospital_capacity < 0.5:
            suggestions.append("Limited hospital capacity — coordinate with nearby medical centers for surge capacity.")
        if loc.fire_station_proximity < 0.4:
            suggestions.append("Fire station beyond optimal range — ensure on-site fire suppression equipment.")

        # Utility and service suggestions
        if result.scenario.disaster is DisasterType.EARTHQUAKE:
            suggestions.append("Post-earthquake: inspect gas lines, electrical systems, and water mains before re-entry.")
            suggestions.append("Expect aftershocks — keep evacuation routes clear for at least 24 hours.")
        if result.scenario.disaster is DisasterType.FLOOD:
            suggestions.append("Avoid walking or driving through floodwaters — as little as 15 cm can move a vehicle.")
            suggestions.append("Boil water or use purification tablets until authorities declare supply safe.")
        if result.scenario.disaster is DisasterType.WILDFIRE:
            suggestions.append("Monitor air quality — wear N95 masks if smoke levels are high.")
            suggestions.append("Create a defensible space of at least 9 meters around structures.")

        # Socioeconomic and community suggestions
        if loc.informal_settlement > 0.4:
            suggestions.append("High informal settlement density — prioritize community-based early warning systems.")
        if loc.population_density > 0.75:
            suggestions.append("Very high population density — establish multiple assembly points to prevent crowding.")
        if loc.elderly_share > 0.15:
            suggestions.append("Significant elderly population — prioritize mobility assistance in evacuation plans.")
        if loc.child_share > 0.2:
            suggestions.append("High child population — coordinate with schools for child-safe evacuation procedures.")

        # Economic impact suggestions
        if result.overall_score > 60:
            suggestions.append("High overall risk — consider business continuity planning and asset protection.")
            suggestions.append("Document property and assets with photos before the event for insurance claims.")

        # Environmental suggestions
        if loc.vegetation > 0.7:
            suggestions.append("Dense vegetation area — coordinate with forest department for firebreak maintenance.")
        if loc.water_distance < 0.2:
            suggestions.append("Close proximity to water body — monitor water levels and erosion risk during heavy rain.")

        self.suggestions.setText("<b>Suggestions</b><br>• " + "<br>• ".join(suggestions))

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

    def clear_result(self) -> None:
        if self._anim_timer:
            self._anim_timer.stop()
        self.assessment = None
        self.location = None
        if hasattr(self, "map_view"):
            self.map_view.clear_assessment()
            self.map_view.clear_selection()
        if hasattr(self, "risk_badge"):
            self.risk_badge.setText("NO RESULT")
            self.risk_badge.setStyleSheet("")
            self.score.setText("—")
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
                export_pdf(self.assessment, path)
                self.statusBar().showMessage(f"Saved PDF report to {path}")
            except Exception as exc:
                QMessageBox.critical(self, "Could not export PDF", str(exc))

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
        elif key == Qt.Key.Key_F2:
            self.show_offline_info()
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

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About CrisisMap",
            "<b>CrisisMap 0.3.0</b><br><br>Offline disaster-impact assessment with multi-factor hazard modeling, "
            "AHP weighting, Monte Carlo uncertainty, and real Pune map data.<br><br>"
            "Assessment only — not prediction or emergency advice.",
        )

    def show_offline_status(self) -> None:
        """Offline audit: lists every local resource with file sizes to justify offline capability."""
        lines = ["Offline Resource Audit", "=" * 40, ""]
        data_dir = Path(__file__).parent.parent / "resources" / "data"
        total_bytes = 0

        lines.append("Bundled map data (all local):")
        for fname in ["demo_region.geojson", "pune_wards.geojson"]:
            fpath = data_dir / fname
            if fpath.exists():
                size_kb = fpath.stat().st_size / 1024
                total_bytes += fpath.stat().st_size
                lines.append(f"  ✓ {fname} — {size_kb:.1f} KB")
            else:
                lines.append(f"  ✗ {fname} — MISSING")

        lines.append("")
        lines.append("Python modules (all local, no external APIs):")
        modules = [
            ("crisismap.simulation", "Hazard/vulnerability engine"),
            ("crisismap.export_pdf", "PDF report generator"),
            ("crisismap.export", "JSON export"),
            ("crisismap.models", "Data models"),
            ("crisismap.data_repository", "GeoJSON loader"),
        ]
        for mod_name, desc in modules:
            try:
                __import__(mod_name)
                lines.append(f"  ✓ {mod_name} — {desc}")
            except Exception:
                lines.append(f"  ✗ {mod_name} — ERROR")

        lines.append("")
        lines.append("External dependencies: NONE (no API keys, no cloud services, no telemetry)")
        lines.append("Network access: NOT REQUIRED — works fully offline (air-gapped)")
        total_mb = total_bytes / (1024 * 1024)
        lines.append(f"Total bundled data: {total_mb:.2f} MB")

        QMessageBox.information(
            self,
            "Offline Audit — Why this works without internet",
            "\n".join(lines),
        )
