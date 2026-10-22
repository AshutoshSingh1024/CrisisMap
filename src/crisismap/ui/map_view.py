from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
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
from ..models import Assessment, DisasterType, LocationProfile, RiskLevel
from ..simulation import assess, Scenario, _hazard_flood, _hazard_wildfire, _hazard_earthquake


RISK_COLORS = {
    RiskLevel.LOW: QColor("#1e7d32"),
    RiskLevel.MODERATE: QColor("#d4a017"),
    RiskLevel.HIGH: QColor("#d9534f"),
    RiskLevel.EXTREME: QColor("#b00020"),
}

# Google Maps-inspired color palette for elevations
ELEVATION_COLORS = [
    (0,   QColor("#e3f2fd")),   # lowland - light blue
    (50,  QColor("#e8f5e9")),   # plains - light green
    (150, QColor("#c8e6c9")),   # hills - medium green
    (300, QColor("#fff9c4")),   # uplands - light yellow
    (500, QColor("#ffe0b2")),   # highlands - light orange
    (9999, QColor("#d7ccc8")),  # mountains - muted gray-brown
]

WATER_COLOR = QColor("#b3e5fc")
ROAD_STYLES = {
    "primary":   (QColor("#546e7a"), 2.2),   # dark slate gray-blue for arterial
    "secondary": (QColor("#78909c"), 1.6),   # slate gray for secondary
    "tertiary":  (QColor("#b0bec5"), 1.1),   # light slate gray for tertiary
    "residential": (QColor("#cfd8dc"), 0.8), # very light gray for residential
}


def _elevation_color(elevation_m: float) -> QColor:
    for threshold, color in ELEVATION_COLORS:
        if elevation_m < threshold:
            return color
    return ELEVATION_COLORS[-1][1]


def _road_style(highway: str | None) -> tuple[QColor, float]:
    if not highway:
        highway = "tertiary"
    return ROAD_STYLES.get(highway, ROAD_STYLES["tertiary"])


class MapView(QGraphicsView):
    location_selected = Signal(object)
    hovered_location = Signal(str)
    evacuation_message = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#f5f5f5"))
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
        self._shelter_items: list[QGraphicsEllipseItem] = []
        self._pulse_timer: QTimer | None = None
        self._pulse_scale = 1.0
        self._pulse_dir = 1.0
        self._heat_enabled: bool = False
        self._last_assessment: Assessment | None = None
        self._multi_hazard_group: QGraphicsItemGroup | None = None
        self._evacuation_route_item: QGraphicsPathItem | None = None
        self._evacuation_shelter_item: QGraphicsEllipseItem | None = None

    def set_dataset(self, dataset: MapDataset) -> None:
        self._dataset = dataset
        self._locations = dataset.locations
        self._selected = None
        self._selection_item = None
        self._risk_group = None
        self._heat_group = None
        self._last_assessment = None
        self._multi_hazard_group = None
        self._evacuation_route_item = None
        self._evacuation_shelter_item = None
        self._shelter_items = []
        self._clear_grid()
        self.scene().clear()
        # Calculate bounds only from ward/Polygon features (not roads or points)
        self._bounds = self._calculate_bounds(dataset.features, use_polygons_only=True)
        self._draw_features(dataset.features)
        self._draw_shelter_markers(dataset.features)
        self.scene().setSceneRect(self.scene().itemsBoundingRect().adjusted(-30, -30, 30, 30))
        self.resetTransform()
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _tick_pulse(self) -> None:
        pass

    def _calculate_bounds(self, features: Iterable[dict], use_polygons_only: bool = False) -> tuple[float, float, float, float]:
        points: list[tuple[float, float]] = []

        def collect(value) -> None:
            if isinstance(value, list) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
                points.append((float(value[0]), float(value[1])))
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        for feature in features:
            geometry = feature.get("geometry") or {}
            kind = geometry.get("type")
            if use_polygons_only and kind not in {"Polygon", "MultiPolygon"}:
                continue
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
        # Group road segments by highway type for batched drawing
        road_groups: dict[str, list[list[list[float]]]] = {}
        ward_items: list[QGraphicsPolygonItem] = []

        for feature in features:
            geometry = feature.get("geometry") or {}
            props = feature.get("properties") or {}
            kind, coords = geometry.get("type"), geometry.get("coordinates")
            name = str(props.get("name") or props.get("Name2") or props.get("Name1") or props.get("wardnum") or "Unnamed feature")

            # Water features
            if props.get("water") == "yes" or props.get("natural") == "water":
                if kind in {"Polygon", "MultiPolygon"} and coords:
                    polygons = coords if kind == "MultiPolygon" else [coords]
                    for polygon in polygons:
                        if not polygon:
                            continue
                        item = QGraphicsPolygonItem(self._polygon(polygon[0]))
                        item.setPen(QPen(QColor("#4fc3f7"), 0.5))
                        item.setBrush(QBrush(WATER_COLOR))
                        item.setToolTip(f"{name}\nWater body")
                        item.setZValue(0)
                        self.scene().addItem(item)
                continue

            if kind in {"Polygon", "MultiPolygon"} and coords:
                polygons = coords if kind == "MultiPolygon" else [coords]
                for polygon in polygons:
                    if not polygon:
                        continue
                    elevation = float(props.get("elevation", 30)) if "elevation" in props else 30.0
                    density = float(props.get("density", 0.5)) if "density" in props else 0.5
                    vegetation = float(props.get("vegetation", 0.45)) if "vegetation" in props else 0.45
                    item = QGraphicsPolygonItem(self._polygon(polygon[0]))
                    item.setPen(QPen(QColor("#78909c"), 0.6))
                    item.setBrush(QBrush(_elevation_color(elevation)))
                    tooltip = (
                        f"{name}\n"
                        f"Elevation: {elevation:.0f} m\n"
                        f"Population Density: {density:.0%}\n"
                        f"Vegetation: {vegetation:.0%}"
                    )
                    item.setToolTip(tooltip)
                    item.setAcceptHoverEvents(True)
                    item.setZValue(1)
                    ward_items.append(item)
                    self.scene().addItem(item)

            elif kind in {"LineString", "MultiLineString"} and coords:
                lines = coords if kind == "MultiLineString" else [coords]
                highway = str(props.get("highway", "tertiary"))
                if highway not in road_groups:
                    road_groups[highway] = []
                for line in lines:
                    if len(line) < 2:
                        continue
                    projected_line = [self._project(float(p[0]), float(p[1])) for p in line]
                    road_groups[highway].append(projected_line)

            elif kind == "Point" and coords:
                point = self._project(float(coords[0]), float(coords[1]))
                marker = self.scene().addEllipse(
                    QRectF(point.x() - 4, point.y() - 4, 8, 8),
                    QPen(QColor("#000000"), 1),
                    QBrush(QColor("#dc143c")),
                )
                marker.setToolTip(name)
                marker.setZValue(3)

        # Batch draw roads: one QGraphicsPathItem per highway type
        for highway, lines in road_groups.items():
            color, width = _road_style(highway)
            path = QPainterPath()
            for line in lines:
                if not line:
                    continue
                path.moveTo(line[0])
                for pt in line[1:]:
                    path.lineTo(pt)
            item = QGraphicsPathItem(path)
            item.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            item.setZValue(2)
            self.scene().addItem(item)

    def _draw_shelter_markers(self, features: list[dict]) -> None:
        """Draw shelter location markers on the map."""
        for feature in features:
            props = feature.get("properties") or {}
            if not props.get("shelter_type"):
                continue
            geometry = feature.get("geometry") or {}
            if geometry.get("type") != "Point":
                continue
            coords = geometry.get("coordinates")
            if not coords or len(coords) < 2:
                continue
            name = str(props.get("name", "Shelter"))
            capacity = props.get("capacity", "N/A")
            point = self._project(float(coords[0]), float(coords[1]))
            marker = self.scene().addEllipse(
                QRectF(point.x() - 7, point.y() - 7, 14, 14),
                QPen(QColor("#ffffff"), 2),
                QBrush(QColor("#1e7d32")),
            )
            marker.setZValue(40)
            marker.setToolTip(f"{name}\nShelter (Capacity: {capacity})")
            self._shelter_items.append(marker)

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
        self._selection_item.setZValue(25)
        self.centerOn(point)
        if emit:
            self.location_selected.emit(location)

    def show_assessment(self, assessment: Assessment) -> None:
        self._last_assessment = assessment
        if self._risk_group:
            self.scene().removeItem(self._risk_group)
        self.clear_heatmap()
        # Just mark the assessed location with a small dot, no big bubble rings
        center = self._project(assessment.location.longitude, assessment.location.latitude)
        color = RISK_COLORS[assessment.risk_level]
        marker = self.scene().addEllipse(
            QRectF(center.x() - 4, center.y() - 4, 8, 8),
            QPen(QColor("#ffffff"), 2),
            QBrush(color),
        )
        marker.setZValue(25)
        marker.setToolTip(f"{assessment.location.name}\n{assessment.risk_level.value} Risk\nScore: {assessment.overall_score:.0f}/100")
        self._risk_group = self.scene().createItemGroup([marker])
        group = self._risk_group
        self.scene().addItem(group)
        # Auto-compute evacuation route to nearest shelter
        self._auto_evacuation_route(assessment.location)

    def _auto_evacuation_route(self, location: LocationProfile) -> None:
        """Auto-compute evacuation route to nearest shelter when assessment runs."""
        self.clear_evacuation_route()
        shelters = []
        for feature in (self._dataset.features if self._dataset else []):
            props = feature.get("properties") or {}
            if props.get("shelter_type") and feature.get("geometry", {}).get("type") == "Point":
                shelters.append(feature)
        if not shelters:
            return
        route = self.compute_evacuation_route(location, shelters)
        if route:
            self.draw_evacuation_route(route)
            self.evacuation_message.emit(
                f"Evacuation route to {route['shelter']['properties'].get('name', 'Shelter')} "
                f"— {route['distance_km']:.1f} km"
            )

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

    def toggle_multi_hazard(self, enabled: bool) -> None:
        """Show or hide multi-hazard overlay coloring wards by combined risk."""
        if self._multi_hazard_group:
            self.scene().removeItem(self._multi_hazard_group)
            self._multi_hazard_group = None
        if not enabled:
            return
        group = QGraphicsItemGroup()
        for feature in (self._dataset.features if self._dataset else []):
            geometry = feature.get("geometry") or {}
            props = feature.get("properties") or {}
            kind = geometry.get("type")
            if kind not in {"Polygon", "MultiPolygon"}:
                continue
            coords = geometry.get("coordinates")
            if not coords:
                continue
            elev = float(props.get("elevation", 30)) if "elevation" in props else 30.0
            density = float(props.get("density", 0.5)) if "density" in props else 0.5
            vegetation = float(props.get("vegetation", 0.45)) if "vegetation" in props else 0.45
            soil = float(props.get("soil", 0.4)) if "soil" in props else 0.4
            water_dist = float(props.get("water_distance", 0.5)) if "water_distance" in props else 0.5
            income = float(props.get("income_level", 0.5)) if "income_level" in props else 0.5
            literacy = float(props.get("literacy_rate", 0.75)) if "literacy_rate" in props else 0.75
            informal = float(props.get("informal_settlement", 0.1)) if "informal_settlement" in props else 0.1
            building_q = float(props.get("building_quality", 0.6)) if "building_quality" in props else 0.6
            loc = LocationProfile(
                name=str(props.get("name", "Unknown")),
                longitude=self._feature_center(geometry)[0] if self._feature_center(geometry) else 0.0,
                latitude=self._feature_center(geometry)[1] if self._feature_center(geometry) else 0.0,
                elevation_m=elev, vegetation=vegetation, population_density=density,
                soil_softness=soil, water_distance=water_dist, income_level=income,
                literacy_rate=literacy, elderly_share=0.1, child_share=0.15,
                disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
                shelter_capacity=0.5, road_density=float(props.get("road_density", 0.5)),
                informal_settlement=informal, building_quality=building_q,
                roof_type_score=0.6, time_of_day=12, season="mixed",
            )
            scores = {}
            for dtype in (DisasterType.FLOOD, DisasterType.WILDFIRE, DisasterType.EARTHQUAKE):
                scen = Scenario(disaster=dtype, intensity=6.0, duration_hours=24.0,
                                preparedness=0.5, weight_hazard=0.52, weight_exposure=0.25,
                                weight_vulnerability=0.23)
                if dtype is DisasterType.FLOOD:
                    h, _ = _hazard_flood(loc, scen)
                elif dtype is DisasterType.WILDFIRE:
                    h, _ = _hazard_wildfire(loc, scen)
                else:
                    h, _ = _hazard_earthquake(loc, scen)
                scores[dtype.value] = h * 100
            multi_score = sum(scores.values()) / 3.0
            if multi_score < 33:
                color = QColor("#1e7d32")
            elif multi_score < 66:
                color = QColor("#d4a017")
            else:
                color = QColor("#d9534f")
            polygons = coords if kind == "MultiPolygon" else [coords]
            for polygon in polygons:
                if not polygon:
                    continue
                item = QGraphicsPolygonItem(self._polygon(polygon[0]))
                item.setPen(QPen(QColor("#000000"), 0.5))
                item.setBrush(QBrush(color))
                item.setToolTip(f"{props.get('name', 'Unknown')}\nMulti-Hazard Score: {multi_score:.0f}/100")
                item.setZValue(15)
                group.addToGroup(item)
        group.setZValue(15)
        self.scene().addItem(group)
        self._multi_hazard_group = group

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
        if self._multi_hazard_group:
            self.scene().removeItem(self._multi_hazard_group)
            self._multi_hazard_group = None
        self.clear_heatmap()
        self.clear_evacuation_route()

    def clear_selection(self) -> None:
        if self._selection_item:
            self.scene().removeItem(self._selection_item)
            self._selection_item = None
        self._selected = None

    def clear_heatmap(self) -> None:
        if self._heat_group:
            self.scene().removeItem(self._heat_group)
            self._heat_group = None

    def clear_evacuation_route(self) -> None:
        """Remove evacuation route from map."""
        if self._evacuation_route_item:
            self.scene().removeItem(self._evacuation_route_item)
            self._evacuation_route_item = None
        if self._evacuation_shelter_item:
            self.scene().removeItem(self._evacuation_shelter_item)
            self._evacuation_shelter_item = None

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

    def compute_evacuation_route(self, start_location: LocationProfile, shelters: list[dict]) -> dict | None:
        """Compute evacuation route from start_location to nearest shelter using A* pathfinding.

        Uses road network features (LineString geometries) as the graph edges.
        Returns a dict with 'path' (list of (lon, lat)), 'shelter' (dict), 'distance_km' (float),
        or None if no route found.
        """
        if not self._dataset:
            return None

    def compute_evacuation_route(self, start_location: LocationProfile, shelters: list[dict]) -> dict | None:
        """Compute evacuation route from start_location to nearest shelter using A* pathfinding.

        Uses road network features (LineString geometries) as the graph edges.
        Returns a dict with 'path' (list of (lon, lat)), 'shelter' (dict), 'distance_km' (float),
        or None if no route found.
        """
        if not self._dataset:
            return None

        start_point = (start_location.longitude, start_location.latitude)

        # Build graph from road features
        graph: dict[tuple[float, float], list[tuple[tuple[float, float], float]]] = {}
        has_roads = False
        for feature in self._dataset.features:
            geometry = feature.get("geometry") or {}
            if geometry.get("type") not in {"LineString", "MultiLineString"}:
                continue
            has_roads = True
            coords = geometry.get("coordinates") or []
            lines = coords if geometry.get("type") == "MultiLineString" else [coords]
            for line in lines:
                if not line or len(line) < 2:
                    continue
                for i in range(len(line) - 1):
                    p1 = (float(line[i][0]), float(line[i][1]))
                    p2 = (float(line[i + 1][0]), float(line[i + 1][1]))
                    dist = self._haversine_km(p1, p2)
                    graph.setdefault(p1, []).append((p2, dist))
                    graph.setdefault(p2, []).append((p1, dist))

        # Find nearest shelter
        best = None
        best_dist = float("inf")
        for shelter in shelters:
            s_point = (float(shelter["geometry"]["coordinates"][0]), float(shelter["geometry"]["coordinates"][1]))
            dist = self._haversine_km(start_point, s_point)
            if dist < best_dist:
                best_dist = dist
                best = (shelter, s_point)

        if not best:
            return None

        shelter, shelter_point = best

        # If road network exists, use A* pathfinding; otherwise fall back to direct line
        if has_roads:
            import heapq

            # Snap start point to nearest road node
            start_node = None
            start_node_dist = float("inf")
            for node in graph:
                d = self._haversine_km(start_point, node)
                if d < start_node_dist:
                    start_node_dist = d
                    start_node = node

            # Snap shelter point to nearest road node
            shelter_node = None
            shelter_node_dist = float("inf")
            for node in graph:
                d = self._haversine_km(shelter_point, node)
                if d < shelter_node_dist:
                    shelter_node_dist = d
                    shelter_node = node

            if start_node is None or shelter_node is None:
                return None

            open_set: list[tuple[float, tuple[float, float]]] = [(0.0, start_node)]
            came_from: dict[tuple[float, float], tuple[float, float] | None] = {start_node: None}
            g_score: dict[tuple[float, float], float] = {start_node: 0.0}

            while open_set:
                _, current = heapq.heappop(open_set)
                if current == shelter_node:
                    break
                for neighbor, weight in graph.get(current, []):
                    tentative_g = g_score[current] + weight
                    if tentative_g < g_score.get(neighbor, float("inf")):
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g
                        f = tentative_g + self._haversine_km(neighbor, shelter_node)
                        heapq.heappush(open_set, (f, neighbor))

            if shelter_node not in came_from:
                return None

            path: list[tuple[float, float]] = []
            current: tuple[float, float] | None = shelter_node
            while current is not None:
                path.append(current)
                current = came_from[current]
            path.reverse()

            # Prepend start point and append shelter point for complete route
            full_path = [start_point] + path + [shelter_point]
            total_dist = self._haversine_km(start_point, start_node) + g_score[shelter_node] + self._haversine_km(shelter_node, shelter_point)

            return {
                "path": full_path,
                "shelter": shelter,
                "distance_km": total_dist,
            }
        else:
            # No road network - direct line fallback
            return {
                "path": [start_point, shelter_point],
                "shelter": shelter,
                "distance_km": best_dist,
            }

    @staticmethod
    def _haversine_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
        """Great-circle distance between two points in km."""
        import math
        lat1, lon1 = math.radians(p1[1]), math.radians(p1[0])
        lat2, lon2 = math.radians(p2[1]), math.radians(p2[0])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        return 6371.0 * c

    def draw_evacuation_route(self, route: dict) -> None:
        """Draw evacuation route on the map."""
        if self._evacuation_route_item:
            self.scene().removeItem(self._evacuation_route_item)

        path = route["path"]
        if len(path) < 2:
            return

        path_item = QGraphicsPathItem()
        path_painter = QPainterPath()
        first = self._project(path[0][0], path[0][1])
        path_painter.moveTo(first)
        for lon, lat in path[1:]:
            pt = self._project(lon, lat)
            path_painter.lineTo(pt)

        path_item.setPath(path_painter)
        path_item.setPen(QPen(QColor("#0078d7"), 3, Qt.PenStyle.DashLine))
        path_item.setZValue(25)
        self.scene().addItem(path_item)
        self._evacuation_route_item = path_item

        shelter = route["shelter"]
        s_coords = shelter["geometry"]["coordinates"]
        s_point = self._project(s_coords[0], s_coords[1])
        marker = self.scene().addEllipse(
            QRectF(s_point.x() - 7, s_point.y() - 7, 14, 14),
            QPen(QColor("#ffffff"), 2),
            QBrush(QColor("#1e7d32")),
        )
        marker.setZValue(30)
        marker.setToolTip(f"{shelter['properties'].get('name', 'Shelter')}\nCapacity: {shelter['properties'].get('capacity', 'N/A')}")
        self._evacuation_shelter_item = marker
