from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
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
    RiskLevel.LOW: QColor("#22c55e"),
    RiskLevel.MODERATE: QColor("#fbbf24"),
    RiskLevel.HIGH: QColor("#f97316"),
    RiskLevel.EXTREME: QColor("#ef4444"),
}


class MapView(QGraphicsView):
    location_selected = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#07131f"))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumSize(500, 420)
        self._dataset: MapDataset | None = None
        self._locations: list[LocationProfile] = []
        self._bounds = (0.0, 0.0, 1.0, 1.0)
        self._selected: LocationProfile | None = None
        self._selection_item: QGraphicsEllipseItem | None = None
        self._risk_group: QGraphicsItemGroup | None = None

    def set_dataset(self, dataset: MapDataset) -> None:
        self._dataset = dataset
        self._locations = dataset.locations
        self._selected = None
        self._selection_item = None
        self._risk_group = None
        self.scene().clear()
        self._bounds = self._calculate_bounds(dataset.features)
        self._draw_features(dataset.features)
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-45, -45, 45, 45))
        self.resetTransform()
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

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
        area_palette = ["#12314a", "#173b50", "#19384a", "#20455a", "#15364b"]
        area_index = 0
        for feature in features:
            geometry = feature.get("geometry") or {}
            props = feature.get("properties") or {}
            kind, coords = geometry.get("type"), geometry.get("coordinates")
            name = str(props.get("name", "Unnamed feature"))
            if kind in {"Polygon", "MultiPolygon"} and coords:
                polygons = coords if kind == "MultiPolygon" else [coords]
                for polygon in polygons:
                    if not polygon:
                        continue
                    item = QGraphicsPolygonItem(self._polygon(polygon[0]))
                    item.setPen(QPen(QColor("#3d647a"), 1.25))
                    item.setBrush(QBrush(QColor(area_palette[area_index % len(area_palette)])))
                    item.setToolTip(f"{name}\nElevation: {props.get('elevation', '—')} m")
                    self.scene().addItem(item)
                center = self._feature_center(geometry)
                if center and len(features) < 20:
                    label = QGraphicsTextItem(name)
                    label.setDefaultTextColor(QColor("#c5d8e5"))
                    label.setPos(self._project(*center) + QPointF(-24, -10))
                    label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                    self.scene().addItem(label)
                area_index += 1
            elif kind in {"LineString", "MultiLineString"} and coords:
                lines = coords if kind == "MultiLineString" else [coords]
                for line in lines:
                    path = QPainterPath()
                    for index, point in enumerate(line):
                        projected = self._project(float(point[0]), float(point[1]))
                        path.moveTo(projected) if index == 0 else path.lineTo(projected)
                    item = QGraphicsPathItem(path)
                    item.setPen(QPen(QColor("#38bdf8"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    item.setToolTip(name)
                    self.scene().addItem(item)
            elif kind == "Point" and coords:
                point = self._project(float(coords[0]), float(coords[1]))
                marker = self.scene().addEllipse(QRectF(point.x() - 6, point.y() - 6, 12, 12), QPen(QColor("#d9f99d"), 2), QBrush(QColor("#65a30d")))
                marker.setToolTip(name)

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
            QRectF(point.x() - 11, point.y() - 11, 22, 22),
            QPen(QColor("#ffffff"), 3), QBrush(QColor("#22d3ee")),
        )
        self._selection_item.setZValue(20)
        self.centerOn(point)
        if emit:
            self.location_selected.emit(location)

    def show_assessment(self, assessment: Assessment) -> None:
        if self._risk_group:
            self.scene().removeItem(self._risk_group)
        group = QGraphicsItemGroup()
        center = self._project(assessment.location.longitude, assessment.location.latitude)
        radius = 45 + assessment.affected_radius_km * 3.5
        color = RISK_COLORS[assessment.risk_level]
        for scale, alpha in ((1.0, 42), (.68, 58), (.36, 82)):
            ring_color = QColor(color)
            ring_color.setAlpha(alpha)
            ellipse = QGraphicsEllipseItem(QRectF(center.x() - radius * scale, center.y() - radius * scale, radius * scale * 2, radius * scale * 2))
            ellipse.setPen(QPen(QColor(color), 2 if scale == 1 else 1))
            ellipse.setBrush(QBrush(ring_color))
            group.addToGroup(ellipse)
        group.setZValue(10)
        self.scene().addItem(group)
        self._risk_group = group
        if self._selection_item:
            self._selection_item.setZValue(20)

    def clear_assessment(self) -> None:
        if self._risk_group:
            self.scene().removeItem(self._risk_group)
            self._risk_group = None

    def wheelEvent(self, event) -> None:
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        if .35 < self.transform().m11() * factor < 18:
            self.scale(factor, factor)

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
