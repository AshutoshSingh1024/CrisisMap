from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Assessment, LocationProfile
from .chart_widgets import (
    BarChartWidget,
    ConfidenceRangeWidget,
    RiskBreakdownWidget,
    RiskGaugeWidget,
    VulnerabilityRadarWidget,
)


class MetricCard(QFrame):
    """A styled metric card showing a single value."""

    def __init__(self, title: str, value: str, subtitle: str = "", color: str = "#64b5f6",
                 parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setFixedHeight(100)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        title_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #8a8f98;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        value_label.setFont(QFont("Segoe UI", 19, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {color};")
        value_label.setWordWrap(True)
        layout.addWidget(value_label)

        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("metricSubtitle")
            sub_label.setFont(QFont("Segoe UI", 8))
            sub_label.setStyleSheet("color: #8a8f98;")
            sub_label.setWordWrap(True)
            layout.addWidget(sub_label)


class LocationInfoCard(QFrame):
    """Minimal locality label for the assessment."""

    def __init__(self, location: LocationProfile, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("locationCard")
        self.setFixedHeight(90)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(5)
        heading = QLabel("ASSESSED AREA")
        heading.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        heading.setStyleSheet("color: #8a8f98;")
        layout.addWidget(heading)
        name = QLabel(location.name)
        name.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        name.setStyleSheet("color: #e8eaed;")
        name.setWordWrap(True)
        layout.addWidget(name)


class AnalysisPanel(QScrollArea):
    """Full-blown analysis tab with charts, metrics, and detailed breakdowns."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setObjectName("analysisPanel")
        self._widget = QWidget()
        self._widget.setObjectName("analysisPanelContent")
        self.setWidget(self._widget)
        self._layout = QVBoxLayout(self._widget)
        self._layout.setContentsMargins(14, 14, 14, 14)
        self._layout.setSpacing(16)

        # Header
        self._header_label = QLabel("Risk Dashboard")
        self._header_label.setObjectName("analysisHeader")
        self._header_label.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        self._header_label.setStyleSheet("color: #e8eaed;")
        self._layout.addWidget(self._header_label)

        # Top metrics row
        self._metrics_row = QHBoxLayout()
        self._metrics_row.setSpacing(10)
        self._layout.addLayout(self._metrics_row)

        self._interpretation = QLabel("Run an assessment to see the main drivers and scenario assumptions.")
        self._interpretation.setWordWrap(True)
        self._interpretation.setStyleSheet("background:#121a24; border:1px solid #263447; border-radius:8px; padding:12px; color:#dce6f2;")
        self._layout.addWidget(self._interpretation)

        self._impact_summary = QLabel("Impact estimates and recommendations will appear here.")
        self._impact_summary.setWordWrap(True)
        self._impact_summary.setStyleSheet("background:#10151b; border:1px solid #26303b; border-radius:8px; padding:12px; color:#dce6f2;")
        self._layout.addWidget(self._impact_summary)

        # Charts row - larger charts
        self._charts_row = QGridLayout()
        self._charts_row.setSpacing(12)
        self._layout.addLayout(self._charts_row)

        # Bottom: Location info + tables
        self._bottom_row = QHBoxLayout()
        self._bottom_row.setSpacing(12)
        self._layout.addLayout(self._bottom_row)

        self._location_card = LocationInfoCard(LocationProfile(
            name="—", longitude=0.0, latitude=0.0,
        ))
        self._bottom_row.addWidget(self._location_card, 1)

        # Table container
        table_container = QFrame()
        table_container.setObjectName("tableContainer")
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        table_title = QLabel("Factor Breakdown")
        table_title.setObjectName("tableTitle")
        table_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        table_title.setStyleSheet("color: #e8eaed;")
        table_layout.addWidget(table_title)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Factor", "Value", "Impact"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setWordWrap(True)
        self._table.setMinimumHeight(420)
        self._table.verticalHeader().setDefaultSectionSize(28)
        self._table.horizontalHeader().setMinimumSectionSize(130)
        table_layout.addWidget(self._table)

        self._bottom_row.addWidget(table_container, 2)

        self._layout.addStretch()

        # Initialize charts - larger sizes for readable text
        self.gauge = RiskGaugeWidget()
        self.bar_chart = BarChartWidget()
        self.breakdown = RiskBreakdownWidget()
        self.confidence_chart = ConfidenceRangeWidget()
        self.radar = VulnerabilityRadarWidget()

        self._charts_row.addWidget(self.gauge, 0, 0)
        self._charts_row.addWidget(self.bar_chart, 0, 1)
        self._charts_row.addWidget(self.confidence_chart, 1, 0)
        self._charts_row.addWidget(self.radar, 1, 1)

    def clear(self) -> None:
        """Reset all charts and metrics to empty state."""
        self.gauge.set_risk(0, "LOW")
        self.bar_chart.set_values({})
        self.breakdown.set_values(0.0, 0.0, 0.0)
        self.confidence_chart.set_range(0, 100, 0)
        self.radar.set_values({})

        while self._metrics_row.count():
            item = self._metrics_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._table.setRowCount(0)
        self._interpretation.setText("Run an assessment to see the main drivers and scenario assumptions.")
        self._impact_summary.setText("Impact estimates and recommendations will appear here.")

    def update_assessment(self, assessment: Assessment, location: LocationProfile) -> None:
        """Populate all charts and metrics from an assessment result."""
        # Update location card
        self._location_card = LocationInfoCard(location)
        self._bottom_row.replaceWidget(self._bottom_row.itemAt(0).widget(), self._location_card)

        # Clear existing metric cards
        while self._metrics_row.count():
            item = self._metrics_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        risk_color = {
            "LOW": "#1e7d32",
            "MODERATE": "#d4a017",
            "HIGH": "#d9534f",
            "EXTREME": "#b00020",
        }.get(assessment.risk_level.value, "#64b5f6")
        scenario = assessment.scenario
        drivers = sorted(
            (("Hazard", assessment.hazard_score), ("Exposure", assessment.exposure_score),
             ("Vulnerability", assessment.vulnerability_score)), key=lambda item: item[1], reverse=True
        )
        self._interpretation.setText(
            f"<b>{location.name}</b>　·　{scenario.disaster.value} {scenario.intensity:.0f}/10 "
            f"·　{scenario.duration_hours:g} h　·　Preparedness {scenario.preparedness:.0%}　·　"
            f"Top driver: {drivers[0][0]}"
        )
        recommendations = "<br>".join(f"• {item}" for item in assessment.recommendations[:2])
        self._impact_summary.setText(
            f"<b>IMPACT ZONE</b>　{assessment.affected_radius_km:.1f} km　·　"
            f"<b>MODEL ESTIMATES</b>　{assessment.people_affected:,} people　·　"
            f"₹{assessment.property_loss_inr:,.0f}<br>{recommendations}"
        )

        # Metric cards
        self._metrics_row.addWidget(MetricCard(
            "RISK SCORE", f"{assessment.overall_score:.0f}/100",
            assessment.risk_level.value.upper(), risk_color,
        ), 1)
        self._metrics_row.addWidget(MetricCard(
            f"{assessment.confidence_interval:.0%} SCORE RANGE", f"{assessment.confidence_lower:.0f}–{assessment.confidence_upper:.0f}",
            f"σ {assessment.mc_std:.1f} · {assessment.mc_samples} runs", "#42a5f5",
        ), 1)
        self._metrics_row.addWidget(MetricCard(
            "PEOPLE EXPOSED", f"{assessment.people_affected:,}",
            "Scenario estimate", "#ffa726",
        ), 1)
        self._metrics_row.addWidget(MetricCard(
            "PROPERTY LOSS", f"\u20b9{assessment.property_loss_inr:,.0f}",
            "Scenario estimate", "#ef5350",
        ), 1)

        # Charts
        self.gauge.set_risk(assessment.overall_score, assessment.risk_level.value)
        self.bar_chart.set_values({
            "Physical Hazard": round(assessment.hazard_score, 1),
            "People Exposure": round(assessment.exposure_score, 1),
            "Social Vulnerability": round(assessment.vulnerability_score, 1),
        })
        self.breakdown.set_values(
            assessment.hazard_score, assessment.exposure_score, assessment.vulnerability_score,
        )
        self.confidence_chart.set_range(assessment.confidence_lower, assessment.confidence_upper, assessment.overall_score)

        # Radar chart - vulnerability factors
        factors = {
            "Population Density": location.population_density,
            "Vegetation": location.vegetation,
            "Soil Softness": location.soil_softness,
            "Informal Settlement": location.informal_settlement,
            "Building Quality": 1 - location.building_quality,
            "Water Distance": location.water_distance,
        }
        self.radar.set_values(factors)

        # Table
        self._table.setRowCount(0)
        rows = [
            ("Physical Hazard", f"{assessment.hazard_score:.1f}/100", "Scenario hazard magnitude"),
            ("People Exposure", f"{assessment.exposure_score:.1f}/100", "Estimated population exposure"),
            ("Social Vulnerability", f"{assessment.vulnerability_score:.1f}/100", "Community susceptibility"),
            ("Elevation", f"{location.elevation_m:.0f} m", "Flood risk factor"),
            ("Vegetation", f"{location.vegetation:.0%}", "Wildfire fuel"),
            ("Population Density", f"{location.population_density:.0%}", "Exposure multiplier"),
            ("Soil Softness", f"{location.soil_softness:.0%}", "Earthquake amplification"),
            ("Building Quality", f"{location.building_quality:.0%}", "Structural resilience"),
            ("Informal Settlement", f"{location.informal_settlement:.0%}", "Housing vulnerability"),
            ("Hospital Capacity", f"{location.hospital_capacity:.0%}", "Medical response"),
            ("Fire Station Proximity", f"{location.fire_station_proximity:.0%}", "Fire response"),
            ("Shelter Capacity", f"{location.shelter_capacity:.0%}", "Evacuation capacity"),
        ]
        for factor, value in (assessment.hazard_factors or {}).items():
            rows.append((f"Hazard · {factor.replace('_', ' ').title()}", f"{value:.2f}", "Normalized model input"))
        for factor, value in (assessment.vulnerability_factors or {}).items():
            rows.append((f"Vulnerability · {factor.replace('_', ' ').title()}", f"{value:.2f}", "Normalized model input"))
        self._table.setRowCount(len(rows))
        for r, (factor, val, impact) in enumerate(rows):
            item0 = QTableWidgetItem(factor)
            item1 = QTableWidgetItem(val)
            item2 = QTableWidgetItem(impact)
            for item in (item0, item1, item2):
                item.setFont(QFont("Segoe UI", 10))
                item.setForeground(QColor("#e8eaed"))
            self._table.setItem(r, 0, item0)
            self._table.setItem(r, 1, item1)
            self._table.setItem(r, 2, item2)

    def export_charts(self, directory: str | Path) -> list[str]:
        """Export all charts as PNG images to the given directory.

        Returns a list of saved file paths.
        """
        from datetime import datetime
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved = []

        charts = [
            ("risk_gauge", self.gauge),
            ("risk_bar", self.bar_chart),
            ("risk_breakdown", self.breakdown),
            ("vulnerability_radar", self.radar),
        ]
        for name, widget in charts:
            fpath = directory / f"crisismap_{name}_{timestamp}.png"
            widget.figure().savefig(str(fpath), dpi=150, bbox_inches="tight",
                                    facecolor="#0f1115")
            saved.append(str(fpath))
        return saved
