from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QFrame,
)

from ..data_repository import MapDataset
from ..models import Assessment, LocationProfile, RiskLevel


RISK_COLORS = {
    RiskLevel.LOW: QColor("#1e7d32"),
    RiskLevel.MODERATE: QColor("#d4a017"),
    RiskLevel.HIGH: QColor("#d9534f"),
    RiskLevel.EXTREME: QColor("#b00020"),
}


def _road_style(highway: str) -> tuple[QColor, float]:
    styles = {
        "primary": (QColor("#ff5722"), 2.0),
        "secondary": (QColor("#ff7043"), 1.5),
        "tertiary": (QColor("#ffab91"), 1.0),
    }
    return styles.get(highway, (QColor("#e0e0e0"), 0.75))


def _elevation_color(elevation_m: float) -> QColor:
    if elevation_m < 20:
        return QColor("#e6f3ff")   # lowland - light blue
    if elevation_m < 80:
        return QColor("#f0f0e0")   # plains - light gray-green
    if elevation_m < 200:
        return QColor("#d8e4bc")   # hills - light green
    if elevation_m < 400:
        return QColor("#c7b398")   # uplands - tan
    return QColor("#a98a6d")        # highlands - muted brown


def _water_color() -> QColor:
    return QColor("#a2d2ff")


class MapView(QGraphicsView):
    location_selected = Signal(object)
    hovered_location = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#ffffff"))
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(1)
        self.setMinimumSize(500, 420)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)

        self._dataset: MapDataset | None = None
        self._locations: list[LocationProfile] = []
        self._bounds = (0.0, 0.0, 1.0, 1.0)
        self._selected: LocationProfile | None = None
        self._selection_item: QGraphicsEllipseItem | None = None
        self._risk_group: QGraphicsItemGroup | None = None
        self._heat_group: QGraphicsItemGroup | None = None
        self._grid_items: list[QGraphicsLineItem] = []
        self._pulse_timer: QTimer | None = None
        self._pulse_scale = 1.0
        self._pulse_dir = 1.0
        self._heat_enabled: bool = True
        self._last_assessment: Assessment | None = None

    def set_dataset(self, dataset: MapDataset) -> None:
        self._dataset = dataset
        self._locations = dataset.locations
        self._selected = None
        self._selection_item = None
        self._risk_group = None
        self._heat_group = None
        self._last_assessment = None
        self._clear_grid()
        self.scene().clear()
        self._bounds = self._calculate_bounds(dataset.features)
        self._draw_features(dataset.features)
        self._draw_grid()
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-30, -30, 30, 30))
        self.resetTransform()
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._start_flash_animation()

    def _start_flash_animation(self) -> None:
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._tick_pulse)
        self._pulse_timer.start(40)

    def _tick_pulse(self) -> None:
        if self._selection_item is None:
            return
        self._pulse_scale += 0.05 * self._pulse_dir
        if self._pulse_scale > 1.35:
            self._pulse_dir = -1.0
        elif self._pulse_scale < 0.75:
            self._pulse_dir = 1.0
        size = 10 * self._pulse_scale
        point = self._project(self._selected.longitude, self._selected.latitude)
        self._selection_item.setRect(QRectF(
            point.x() - size / 2,
            point.y() - size / 2,
            size,
            size,
        ))

    def _calculate_bounds(self, features: Iterable[dict]) -> tuple[float, float, float, float]:
        points: list[tuple[float, float]] = []

        def collect(value) -> None:
            if isinstance(value, list) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
                points.append((float(value[0]), float(value[1])))
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        for feature in features:
            collect((feature.get("geometry") or {}).get("coordinates", []))
        if not points:
            return (0, 0, 1, 1)
        xs, ys = zip(*points)
        return min(xs), min(ys), max(xs), max(ys)

    def _project(self, lon: float, lat: float) -> QPointF:
        min_x, min_y, max_x, max_y = self._bounds
        width, height = max(max_x - min_x, 1e-8), max(max_y - min_y, 1e-8)
        return QPointF((lon - min_x) / width * 920, (max_y - lat) / height * 620)

    def _polygon(self, ring: list[list[float]]) -> QPolygonF:
        return QPolygonF([self._project(float(point[0]), float(point[1])) for point in ring if len(point) >= 2])

    def _draw_features(self, features: list[dict]) -> None:
        for feature in features:
            geometry = feature.get("geometry") or {}
            props = feature.get("properties") or {}
            kind, coords = geometry.get("type"), geometry.get("coordinates")
            name = str(props.get("name") or props.get("Name2") or props.get("Name1") or props.get("wardnum") or "Unnamed feature")
            if kind in {"Polygon", "MultiPolygon"} and coords:
                polygons = coords if kind == "MultiPolygon" else [coords]
                for polygon in polygons:
                    if not polygon:
                        continue
                    elevation = float(props.get("elevation", 30)) if "elevation" in props else 30.0
                    item = QGraphicsPolygonItem(self._polygon(polygon[0]))
                    item.setPen(QPen(QColor("#9aa5b1"), 0.75))
                    item.setBrush(QBrush(_elevation_color(elevation)))
                    tooltip = f"{name}\nElevation: {elevation:.0f} m"
                    item.setToolTip(tooltip)
                    item.setAcceptHoverEvents(True)
                    item.setZValue(1)
                    self.scene().addItem(item)
            elif kind in {"LineString", "MultiLineString"} and coords:
                lines = coords if kind == "MultiLineString" else [coords]
                for line in lines:
                    path = QPainterPath()
                    for index, point in enumerate(line):
                        projected = self._project(float(point[0]), float(point[1]))
                        path.moveTo(projected) if index == 0 else path.lineTo(projected)
                    item = QGraphicsPathItem(path)
                    highway = str(props.get("highway", "tertiary"))
                    color, width = _road_style(highway)
                    item.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    item.setToolTip(name)
                    item.setZValue(2)
                    item.setAcceptHoverEvents(True)
                    self.scene().addItem(item)
            elif kind == "Point" and coords:
                point = self._project(float(coords[0]), float(coords[1]))
                marker = self.scene().addEllipse(
                    QRectF(point.x() - 4, point.y() - 4, 8, 8),
                    QPen(QColor("#000000"), 1),
                    QBrush(QColor("#dc143c")),
                )
                marker.setToolTip(name)
                marker.setZValue(3)

    def _draw_grid(self) -> None:
        if not self._locations:
            return
        min_lon = min(loc.longitude for loc in self._locations)
        max_lon = max(loc.longitude for loc in self._locations)
        min_lat = min(loc.latitude for loc in self._locations)
        max_lat = max(loc.latitude for loc in self._locations)

        step_lon = max((max_lon - min_lon) / 4, 0.001)
        step_lat = max((max_lat - min_lat) / 4, 0.001)

        pen = QPen(QColor("#b8c4d0"), 0.5, Qt.PenStyle.DotLine)
        for i in range(5):
            lon = min_lon + step_lon * i
            lat = min_lat + step_lat * i
            p_top = self._project(lon, max_lat)
            p_bot = self._project(lon, min_lat)
            v_line = QGraphicsLineItem(p_top.x(), p_top.y(), p_bot.x(), p_bot.y())
            v_line.setPen(pen)
            v_line.setZValue(0)
            self.scene().addItem(v_line)
            self._grid_items.append(v_line)

            p_left = self._project(min_lon, lat)
            p_right = self._project(max_lon, lat)
            h_line = QGraphicsLineItem(p_left.x(), p_left.y(), p_right.x(), p_right.y())
            h_line.setPen(pen)
            h_line.setZValue(0)
            self.scene().addItem(h_line)
            self._grid_items.append(h_line)

    def _clear_grid(self) -> None:
        for item in self._grid_items:
            self.scene().removeItem(item)
        self._grid_items.clear()

    @staticmethod
    def _feature_center(geometry: dict) -> tuple[float, float] | None:
        coords = geometry.get("coordinates") or []
        if geometry.get("type") == "Point" and len(coords) >= 2:
            return float(coords[0]), float(coords[1])
        if geometry.get("type") == "Polygon" and coords:
            ring = coords[0]
        elif geometry.get("type") == "MultiPolygon" and coords:
            ring = coords[0][0]
        else:
            return None
        if not ring:
            return None
        return sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)

    def select_location(self, location: LocationProfile, emit: bool = False) -> None:
        self._selected = location
        point = self._project(location.longitude, location.latitude)
        if self._selection_item:
            self.scene().removeItem(self._selection_item)
        self._selection_item = self.scene().addEllipse(
            QRectF(point.x() - 8, point.y() - 8, 16, 16),
            QPen(QColor("#ffffff"), 2),
            QBrush(QColor("#0078d7")),
        )
        self._selection_item.setZValue(20)
        self.centerOn(point)
        if emit:
            self.location_selected.emit(location)

    def show_assessment(self, assessment: Assessment) -> None:
        self._last_assessment = assessment
        if self._risk_group:
            self.scene().removeItem(self._risk_group)
        self.clear_heatmap()
        group = QGraphicsItemGroup()
        center = self._project(assessment.location.longitude, assessment.location.latitude)
        radius = 50 + assessment.affected_radius_km * 4
        color = RISK_COLORS[assessment.risk_level]
        # Heatmap gradient rings
        for scale, alpha in ((1.0, 26), (.72, 38), (.44, 52), (.28, 62)):
            ring_color = QColor(color)
            ring_color.setAlpha(alpha)
            ellipse = QGraphicsEllipseItem(
                QRectF(center.x() - radius * scale, center.y() - radius * scale,
                       radius * scale * 2, radius * scale * 2)
            )
            ellipse.setPen(QPen(QColor(color), 2 if scale == 1 else 1))
            ellipse.setBrush(QBrush(ring_color))
            ellipse.setZValue(10)
            group.addToGroup(ellipse)
        group.setZValue(10)
        self.scene().addItem(group)
        self._risk_group = group
        # Heatmap across all locations based on population density
        if self._heat_enabled:
            self._draw_location_heatmap()
        if self._selection_item:
            self._selection_item.setZValue(25)

    def toggle_grid(self, enabled: bool) -> None:
        """Show or hide the coordinate grid overlay."""
        self._clear_grid()
        if enabled:
            self._draw_grid()

    def toggle_heatmap(self, enabled: bool) -> None:
        """Show or hide the population heatmap layer."""
        self._heat_enabled = enabled
        if not enabled:
            self.clear_heatmap()
        elif self._last_assessment:
            self._draw_location_heatmap()

    def _draw_location_heatmap(self) -> None:
        """Draw a heat gradient at each location based on population density."""
        group = QGraphicsItemGroup()
        for loc in self._locations:
            center = self._project(loc.longitude, loc.latitude)
            intensity = loc.population_density
            radius = 30 + intensity * 40
            for scale, alpha in ((1.0, 18), (.6, 28), (.3, 38)):
                heat_color = QColor("#ff5722")
                heat_color.setAlpha(int(alpha * intensity))
                ellipse = QGraphicsEllipseItem(
                    QRectF(center.x() - radius * scale, center.y() - radius * scale,
                           radius * scale * 2, radius * scale * 2)
                )
                ellipse.setPen(QPen(Qt.PenStyle.NoPen))
                ellipse.setBrush(QBrush(heat_color))
                ellipse.setZValue(5)
                group.addToGroup(ellipse)
        group.setZValue(5)
        self.scene().addItem(group)
        self._heat_group = group

    def clear_assessment(self) -> None:
        if self._risk_group:
            self.scene().removeItem(self._risk_group)
            self._risk_group = None
        self.clear_heatmap()

    def clear_selection(self) -> None:
        if self._selection_item:
            self.scene().removeItem(self._selection_item)
            self._selection_item = None
        self._selected = None

    def clear_heatmap(self) -> None:
        if self._heat_group:
            self.scene().removeItem(self._heat_group)
            self._heat_group = None

    def wheelEvent(self, event) -> None:
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        if .35 < self.transform().m11() * factor < 18:
            self.scale(factor, factor)

    def mouseMoveEvent(self, event) -> None:
        scene_point = self.mapToScene(event.position().toPoint())
        items = self.scene().items(scene_point)
        for item in items:
            if item.zValue() == 1:  # polygon layer
                tooltip = item.toolTip()
                if tooltip:
                    name = tooltip.split("\n")[0]
                    self.hovered_location.emit(name)
                break
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._locations:
            scene_point = self.mapToScene(event.position().toPoint())
            nearest = min(self._locations, key=lambda loc: self._distance(scene_point, self._project(loc.longitude, loc.latitude)))
            self.select_location(nearest, emit=True)
        super().mousePressEvent(event)

    @staticmethod
    def _distance(a: QPointF, b: QPointF) -> float:
        return (a.x() - b.x()) ** 2 + (a.y() - b.y()) ** 2

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.scene() and not self._selected:
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)