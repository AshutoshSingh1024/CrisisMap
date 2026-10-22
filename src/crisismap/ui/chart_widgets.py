from __future__ import annotations

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.patches import Wedge

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ChartWidget(QWidget):
    """Base widget embedding a matplotlib figure with dark theme."""

    def __init__(self, parent=None, figsize=(4, 3), dpi=100) -> None:
        super().__init__(parent)
        self._fig = Figure(figsize=figsize, dpi=dpi, facecolor="#0f1115")
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._canvas)

    def figure(self) -> Figure:
        return self._fig

    def canvas(self) -> FigureCanvasQTAgg:
        return self._canvas

    def redraw(self) -> None:
        self._canvas.draw_idle()


class RiskGaugeWidget(ChartWidget):
    """Donut gauge showing overall risk score."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, figsize=(3.4, 3.4), dpi=100)
        self._ax = self._fig.add_subplot(111)
        self._score = 0.0
        self._level = "LOW"

    def set_risk(self, score: float, level: str) -> None:
        self._score = max(0.0, min(100.0, float(score)))
        self._level = str(level)
        self._draw()

    def _draw(self) -> None:
        ax = self._ax
        ax.clear()
        ax.set_facecolor("#0f1115")

        level_colors = {
            "LOW": "#1e7d32",
            "MODERATE": "#d4a017",
            "HIGH": "#d9534f",
            "EXTREME": "#b00020",
        }
        color = level_colors.get(self._level, "#64b5f6")

        # Background track (subtle)
        track = Wedge(
            (0.5, 0.5), 0.44, 90, -270,
            width=0.14, facecolor="#22252b", edgecolor="none",
        )
        ax.add_patch(track)

        # Score wedge
        theta = 360 * (self._score / 100.0)
        wedge = Wedge(
            (0.5, 0.5), 0.44, 90, 90 - theta,
            width=0.14, facecolor=color, edgecolor="none",
        )
        ax.add_patch(wedge)

        # Center score text
        ax.text(0.5, 0.54, f"{self._score:.0f}", ha="center", va="center",
                fontsize=20, fontweight="bold", color="#e8eaed")
        ax.text(0.5, 0.46, self._level, ha="center", va="center",
                fontsize=9, color="#8a8f98")

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect("equal")
        ax.axis("off")
        self.redraw()


class BarChartWidget(ChartWidget):
    """Horizontal bar chart for component scores."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, figsize=(5.2, 3.0), dpi=100)
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor("#0f1115")

    def set_values(self, values: dict) -> None:
        self._values = dict(values or {})
        self._draw()

    def _draw(self) -> None:
        ax = self._ax
        ax.clear()
        ax.set_facecolor("#0f1115")

        if not self._values:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color="#8a8f98", fontsize=11)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
            self.redraw()
            return

        labels = list(self._values.keys())
        values = [float(v) for v in self._values.values()]

        colors = ["#ef5350", "#ffa726", "#66bb6a", "#42a5f5"]
        bar_colors = [colors[i % len(colors)] for i in range(len(labels))]

        y_pos = range(len(labels))
        bars = ax.barh(y_pos, values, color=bar_colors, height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, color="#e8eaed", fontsize=9)
        ax.set_xlim(0, max(100, max(values) * 1.25))
        ax.set_xlabel("Risk Score", color="#8a8f98", fontsize=9)
        ax.tick_params(axis="x", colors="#8a8f98", labelsize=8)
        ax.spines["bottom"].set_color("#2d3239")
        ax.spines["left"].set_color("#2d3239")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        for bar, val in zip(bars, values):
            ax.text(val + 1, bar.get_y() + bar.get_height() / 2,
                    f"{val:.0f}", va="center",
                    fontsize=9, fontweight="bold", color="#e8eaed")

        self._fig.tight_layout()
        self.redraw()


class RiskBreakdownWidget(ChartWidget):
    """Donut pie chart showing risk factor contribution."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, figsize=(3.4, 3.4), dpi=100)
        self._ax = self._fig.add_subplot(111)
        self._ax.set_facecolor("#0f1115")

    def set_values(self, hazard: float, exposure: float, vulnerability: float) -> None:
        self._hazard = float(hazard)
        self._exposure = float(exposure)
        self._vulnerability = float(vulnerability)
        self._draw()

    def _draw(self) -> None:
        ax = self._ax
        ax.clear()
        ax.set_facecolor("#0f1115")

        values = [self._hazard, self._exposure, self._vulnerability]
        labels = ["Physical Hazard", "People Exposure", "Social Vulnerability"]
        colors = ["#ef5350", "#ffa726", "#66bb6a"]

        if max(values) <= 0:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color="#8a8f98", fontsize=11)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis("off")
            self.redraw()
            return

        total = sum(values)
        wedges, texts, autotexts = ax.pie(
            values, labels=labels, colors=colors,
            autopct=lambda pct: f"{pct:.1f}%", startangle=90,
            wedgeprops=dict(width=0.45, edgecolor="#0f1115"),
            textprops=dict(color="#e8eaed", fontsize=8),
            pctdistance=0.78,
        )
        for autotext in autotexts:
            autotext.set_color("#ffffff")
            autotext.set_fontsize(8)
            autotext.set_fontweight("bold")

        ax.set_title("Risk Factor Split", color="#e8eaed",
                     fontsize=10, fontweight="bold", pad=10)
        self._fig.tight_layout()
        self.redraw()


class VulnerabilityRadarWidget(ChartWidget):
    """Radar/spider chart showing vulnerability factors."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, figsize=(4.2, 4.2), dpi=100)
        self._ax = self._fig.add_subplot(111, polar=True)

    def set_values(self, factors: dict) -> None:
        self._factors = dict(factors or {})
        self._draw()

    def _draw(self) -> None:
        ax = self._ax
        ax.clear()
        ax.set_facecolor("#0f1115")

        if not self._factors:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    color="#8a8f98", fontsize=11)
            ax.set_xticklabels([])
            ax.set_yticklabels([])
            self.redraw()
            return

        labels = list(self._factors.keys())
        values = [float(v) for v in self._factors.values()]
        n = len(labels)

        angles = [i * 2 * 3.14159 / n for i in range(n)]
        angles += angles[:1]
        values_plot = values + values[:1]

        colors = ["#ef5350", "#ffa726", "#66bb6a", "#42a5f5", "#ab47bc"]
        color = colors[0]

        ax.plot(angles, values_plot, color=color, linewidth=2, linestyle="solid")
        ax.fill(angles, values_plot, color=color, alpha=0.25)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, color="#8a8f98", fontsize=7)
        ax.set_yticks([0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["25%", "50%", "75%", "100%"],
                           color="#8a8f98", fontsize=7)
        ax.set_ylim(0, 1)
        ax.set_title("Vulnerability Profile", color="#e8eaed",
                     fontsize=10, fontweight="bold", pad=20)
        ax.grid(color="#2d3239", linewidth=0.5)
        self._fig.tight_layout()
        self.redraw()
