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
    """Card showing selected location details."""

    def __init__(self, location: LocationProfile, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("locationCard")
        self.setMinimumHeight(130)
        layout = QGridLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(5)

        fields = [
            ("Name", location.name),
            ("Latitude", f"{location.latitude:.4f}\u00b0N"),
            ("Longitude", f"{location.longitude:.4f}\u00b0E"),
            ("Elevation", f"{location.elevation_m:.0f} m"),
            ("Vegetation", f"{location.vegetation:.0%}"),
            ("Population Density", f"{location.population_density:.0%}"),
            ("Soil Softness", f"{location.soil_softness:.0%}"),
            ("Water Distance", f"{location.water_distance:.0%}"),
        ]

        for i, (key, val) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            key_label = QLabel(key)
            key_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            key_label.setStyleSheet("color: #8a8f98;")
            key_label.setWordWrap(True)
            val_label = QLabel(val)
            val_label.setFont(QFont("Segoe UI", 10))
            val_label.setStyleSheet("color: #e8eaed;")
            val_label.setWordWrap(True)
            layout.addWidget(key_label, row, col)
            layout.addWidget(val_label, row, col + 1)


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
        self._header_label = QLabel("Detailed Risk Analysis")
        self._header_label.setObjectName("analysisHeader")
        self._header_label.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        self._header_label.setStyleSheet("color: #e8eaed;")
        self._layout.addWidget(self._header_label)

        # Top metrics row
        self._metrics_row = QHBoxLayout()
        self._metrics_row.setSpacing(10)
        self._layout.addLayout(self._metrics_row)

        # Charts row - larger charts
        self._charts_row = QHBoxLayout()
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
        self._table.verticalHeader().setDefaultSectionSize(28)
        table_layout.addWidget(self._table)

        self._bottom_row.addWidget(table_container, 2)

        self._layout.addStretch()

        # Initialize charts - larger sizes for readable text
        self.gauge = RiskGaugeWidget()
        self.bar_chart = BarChartWidget()
        self.breakdown = RiskBreakdownWidget()
        self.radar = VulnerabilityRadarWidget()

        self._charts_row.addWidget(self.gauge, 1)
        self._charts_row.addWidget(self.bar_chart, 1)
        self._charts_row.addWidget(self.breakdown, 1)
        self._charts_row.addWidget(self.radar, 1)

    def clear(self) -> None:
        """Reset all charts and metrics to empty state."""
        self.gauge.set_risk(0, "LOW")
        self.bar_chart.set_values({})
        self.breakdown.set_values(0.0, 0.0, 0.0)
        self.radar.set_values({})

        while self._metrics_row.count():
            item = self._metrics_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._table.setRowCount(0)

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

        # Metric cards
        self._metrics_row.addWidget(MetricCard(
            "Overall Risk Score", f"{assessment.overall_score:.0f}",
            "Composite score / 100", risk_color,
        ), 1)
        self._metrics_row.addWidget(MetricCard(
            "Risk Level", assessment.risk_level.value.upper(),
            "Classification", risk_color,
        ), 1)
        self._metrics_row.addWidget(MetricCard(
            "Confidence", f"{int(assessment.confidence_interval * 100)}%",
            f"\u03c3={assessment.mc_std:.1f}", "#42a5f5",
        ), 1)
        self._metrics_row.addWidget(MetricCard(
            "Affected Radius", f"{assessment.affected_radius_km:.1f} km",
            "Estimated impact area", "#ab47bc",
        ), 1)
        self._metrics_row.addWidget(MetricCard(
            "People Affected", f"{assessment.people_affected:,}",
            "Estimated exposure", "#ffa726",
        ), 1)
        self._metrics_row.addWidget(MetricCard(
            "Property Loss", f"\u20b9{assessment.property_loss_inr:,.0f}",
            "Estimated damage", "#ef5350",
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
            ("Physical Hazard", f"{assessment.hazard_score:.1f}", "Primary threat level"),
            ("People Exposure", f"{assessment.exposure_score:.1f}", "Population at risk"),
            ("Social Vulnerability", f"{assessment.vulnerability_score:.1f}", "Susceptibility"),
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
