from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Qt, Signal, Slot
from PySide6.QtWidgets import QVBoxLayout, QWidget
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

from ..models import Assessment, LocationProfile


class JSBridge(QObject):
    """Bridge between JavaScript and Python for map interactions."""

    wardClicked = Signal(str)
    mapClicked = Signal(float, float)

    @Slot(str)
    def onWardClick(self, feature_json: str) -> None:
        self.wardClicked.emit(feature_json)

    @Slot(float, float)
    def onMapClick(self, latitude: float, longitude: float) -> None:
        self.mapClicked.emit(latitude, longitude)


class OSMMap(QWidget):
    """OpenStreetMap-based map widget using Leaflet.js with Google Maps-like styling."""

    location_selected = Signal(object)
    hovered_location = Signal(str)
    evacuation_message = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._web_view = QWebEngineView()
        self._web_view.setMinimumSize(500, 420)
        self._layout.addWidget(self._web_view)
        self._web_view.loadFinished.connect(self._on_load_finished)

        self._dataset = None
        self._locations = []
        self._selected = None
        self._assessment = None
        self._center_lat = 18.52
        self._center_lon = 73.85
        self._zoom = 12

        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        self._channel = QWebChannel()
        self._web_view.page().setWebChannel(self._channel)
        self._bridge = JSBridge()
        self._bridge.wardClicked.connect(self._on_ward_clicked)
        self._bridge.mapClicked.connect(self._on_map_clicked)
        self._channel.registerObject("pywebview", self._bridge)

        self._load_map()

    def zoom_in(self) -> None:
        self._run_map_js("map.zoomIn()")

    def zoom_out(self) -> None:
        self._run_map_js("map.zoomOut()")

    def reset_view(self) -> None:
        self._run_map_js("map.setView([18.5204, 73.8567], 12)")

    def _run_map_js(self, source: str) -> None:
        self._web_view.page().runJavaScript(f"if (window.map) {{ {source} }}")

    def _on_load_finished(self, ok: bool) -> None:
        if ok and self._dataset:
            self.set_dataset(self._dataset)

    def _load_map(self) -> None:
        html = self._build_html()
        self._web_view.setHtml(html, QUrl.fromLocalFile(str(Path(__file__).parent)))

    def _build_html(self) -> str:
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OSM Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        html, body {{ margin: 0; padding: 0; height: 100%; width: 100%; overflow: hidden; }}
        #map {{ height: 100%; width: 100%; }}
        .leaflet-tooltip {{
            background-color: rgba(0, 0, 0, 0.85);
            border: none;
            border-radius: 4px;
            color: #fff;
            font-family: 'Segoe UI', sans-serif;
            font-size: 12px;
            padding: 6px 10px;
            white-space: nowrap;
        }}
    </style>
</head>
<body>
    <div id="map"></div>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        window.map = L.map('map', {{
            zoomControl: true,
            doubleClickZoom: true,
            dragging: true,
            keyboard: true,
            tap: true
        }}).setView([{self._center_lat}, {self._center_lon}], {self._zoom});

        var baseLayers = {{
            'Street map': L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 19, subdomains: 'abc'
            }}),
            'Satellite': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
                attribution: 'Tiles &copy; Esri', maxZoom: 19
            }}),
            'Terrain': L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
                attribution: '&copy; OpenTopoMap contributors', maxZoom: 17
            }})
        }};
        baseLayers['Street map'].addTo(map);

        L.control.scale({{position: 'bottomleft', metric: true, imperial: false}}).addTo(map);

        window.wardLayer = L.layerGroup().addTo(map);
        window.shelterLayer = L.layerGroup().addTo(map);
        window.routeLayer = L.layerGroup().addTo(map);
        window.assessmentLayer = L.layerGroup().addTo(map);
        window.selectionLayer = L.layerGroup().addTo(map);
        window.pendingMapClick = null;
        map.on('click', function(e) {{
            var point = [e.latlng.lat, e.latlng.lng];
            if (window.pywebview) window.pywebview.onMapClick(point[0], point[1]);
            else window.pendingMapClick = point;
        }});

        L.control.layers(baseLayers, {{
            'Ward boundaries': window.wardLayer,
            'Shelters': window.shelterLayer,
            'Routes': window.routeLayer,
            'Assessment': window.assessmentLayer
        }}, {{position: 'topright', collapsed: true}}).addTo(map);
        new QWebChannel(qt.webChannelTransport, function(channel) {{
            window.pywebview = channel.objects.pywebview;
            if (window.pendingMapClick) {{
                window.pywebview.onMapClick(window.pendingMapClick[0], window.pendingMapClick[1]);
                window.pendingMapClick = null;
            }}
        }});
    </script>
</body>
</html>"""

    def set_dataset(self, dataset) -> None:
        self._dataset = dataset
        self._locations = dataset.locations if dataset else []

        if self._locations:
            self._center_lat = sum(loc.latitude for loc in self._locations) / len(self._locations)
            self._center_lon = sum(loc.longitude for loc in self._locations) / len(self._locations)

        self._send_geojson(dataset)
        if dataset:
            bounds = []
            for feature in dataset.features:
                geom = feature.get("geometry") or {}
                if geom.get("type") not in ("Polygon", "MultiPolygon"):
                    continue
                def collect(value):
                    if isinstance(value, list) and len(value) >= 2 and all(isinstance(v, (int, float)) for v in value[:2]):
                        bounds.append([float(value[1]), float(value[0])])
                    elif isinstance(value, list):
                        for child in value:
                            collect(child)
                collect(geom.get("coordinates", []))
            if bounds:
                self._run_map_js(f"map.fitBounds({json.dumps(bounds)}, {{padding:[24,24], maxZoom:13}})")

    def _send_geojson(self, dataset) -> None:
        if not dataset:
            return

        wards = []
        shelters = []
        for feature in dataset.features:
            geometry = feature.get("geometry") or {}
            props = feature.get("properties") or {}
            kind = geometry.get("type")

            if props.get("shelter_type") and kind == "Point":
                shelters.append(feature)
            elif kind in ("Polygon", "MultiPolygon"):
                wards.append(feature)

        ward_geojson = {"type": "FeatureCollection", "features": wards}
        shelter_geojson = {"type": "FeatureCollection", "features": shelters}

        js_code = f"""
        if (window.wardLayer) {{
            window.wardLayer.clearLayers();
            var wardData = {json.dumps(ward_geojson)};
            L.geoJSON(wardData, {{
                style: function(feature) {{
                    return {{
                        color: '#78909c',
                        weight: 0.6,
                        fillColor: '#e8f5e9',
                        fillOpacity: 0.5
                    }};
                }},
                onEachFeature: function(feature, layer) {{
                    if (feature.properties) {{
                        var name = feature.properties.name || feature.properties.Name2 || feature.properties.Name1 || 'Unnamed';
                        layer.bindTooltip(name, {{direction: 'center'}});
                        layer.on('click', function(e) {{
                            L.DomEvent.stopPropagation(e);
                            if (window.pywebview) {{
                                window.pywebview.onWardClick(JSON.stringify(feature));
                            }}
                        }});
                    }}
                }}
            }}).addTo(window.wardLayer);
        }}

        if (window.shelterLayer) {{
            window.shelterLayer.clearLayers();
            var shelterData = {json.dumps(shelter_geojson)};
            L.geoJSON(shelterData, {{
                pointToLayer: function(feature, latlng) {{
                    return L.circleMarker(latlng, {{
                        radius: 6,
                        fillColor: '#1e7d32',
                        color: '#ffffff',
                        weight: 2,
                        fillOpacity: 1.0
                    }});
                }}
            }}).addTo(window.shelterLayer);
        }}
        """
        self._run_map_js(js_code)

    def select_location(self, location, emit: bool = False) -> None:
        self._selected = location

        js_code = f"""
        if (window.selectionLayer) {{
            window.selectionLayer.clearLayers();
        }}
        var marker = L.circleMarker([{location.latitude}, {location.longitude}], {{
            radius: 8,
            fillColor: '#0078d7',
            color: '#ffffff',
            weight: 2,
            fillOpacity: 1.0
        }}).addTo(window.selectionLayer);
        marker.bindTooltip({json.dumps(location.name)}, {{direction: 'top'}});
        map.panTo([{location.latitude}, {location.longitude}]);
        """
        self._run_map_js(js_code)

        if emit:
            self.location_selected.emit(location)

    def show_assessment(self, assessment: Assessment) -> None:
        self._assessment = assessment

        risk_color = {
            "LOW": "#1e7d32",
            "MODERATE": "#d4a017",
            "HIGH": "#d9534f",
            "EXTREME": "#b00020",
        }.get(assessment.risk_level.value, "#64b5f6")

        js_code = f"""
        if (window.assessmentLayer) {{
            window.assessmentLayer.clearLayers();
            var center = [{assessment.location.latitude}, {assessment.location.longitude}];
            var radius = {max(assessment.affected_radius_km * 1000, 250):.1f};
            var zone = L.circle(center, {{radius: radius, color: '{risk_color}', weight: 2,
                fillColor: '{risk_color}', fillOpacity: 0.22}}).addTo(window.assessmentLayer);
            var pulse = L.circleMarker(center, {{radius: 8, color: '#fff', weight: 2,
                fillColor: '{risk_color}', fillOpacity: 1}}).addTo(window.assessmentLayer);
            window.pulseTimer && clearInterval(window.pulseTimer);
            var growing = true;
            window.pulseTimer = setInterval(function() {{
                var r = pulse.getRadius();
                pulse.setRadius(growing ? r + 1 : r - 1);
                if (pulse.getRadius() >= 14) growing = false;
                if (pulse.getRadius() <= 7) growing = true;
            }}, 90);
            pulse.bindTooltip(
                {json.dumps(assessment.location.name + '<br>' + assessment.risk_level.value.upper() + ' RISK<br>Score: ' + f'{assessment.overall_score:.0f}/100')}
            );
        }}
        """
        self._run_map_js(js_code)

    def clear_assessment(self) -> None:
        self._assessment = None
        js_code = """
        if (window.pulseTimer) { clearInterval(window.pulseTimer); window.pulseTimer = null; }
        if (window.assessmentLayer) {
            window.assessmentLayer.clearLayers();
        }
        if (window.selectionLayer) {
            window.selectionLayer.clearLayers();
        }
        """
        self._run_map_js(js_code)

    def clear_selection(self) -> None:
        self._selected = None
        js_code = """
        if (window.selectionLayer) {
            window.selectionLayer.clearLayers();
        }
        """
        self._run_map_js(js_code)

    def toggle_heatmap(self, enabled: bool) -> None:
        pass

    def toggle_grid(self, enabled: bool) -> None:
        pass

    def toggle_multi_hazard(self, enabled: bool) -> None:
        pass

    def clear_evacuation_route(self) -> None:
        js_code = """
        if (window.routeLayer) {
            window.routeLayer.clearLayers();
        }
        """
        self._run_map_js(js_code)

    def draw_evacuation_route(self, route: dict) -> None:
        path = route.get("path", [])
        if len(path) < 2:
            return

        coords_js = json.dumps([[lat, lon] for lon, lat in path])

        js_code = f"""
        if (window.routeLayer) {{
            window.routeLayer.clearLayers();
            var routeCoords = {coords_js};
            var polyline = L.polyline(routeCoords, {{
                color: '#0078d7',
                weight: 3,
                dashArray: '5, 10'
            }}).addTo(window.routeLayer);
        }}
        """
        self._run_map_js(js_code)

    def compute_evacuation_route(self, start_location: LocationProfile, shelters: list[dict]) -> dict | None:
        if not self._dataset:
            return None

        start_point = (start_location.longitude, start_location.latitude)

        graph = {}
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

        if has_roads:
            import heapq

            start_node = None
            start_node_dist = float("inf")
            for node in graph:
                d = self._haversine_km(start_point, node)
                if d < start_node_dist:
                    start_node_dist = d
                    start_node = node

            shelter_node = None
            shelter_node_dist = float("inf")
            for node in graph:
                d = self._haversine_km(shelter_point, node)
                if d < shelter_node_dist:
                    shelter_node_dist = d
                    shelter_node = node

            if start_node is None or shelter_node is None:
                return None

            open_set = [(0.0, start_node)]
            came_from = {start_node: None}
            g_score = {start_node: 0.0}

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

            path = []
            current = shelter_node
            while current is not None:
                path.append(current)
                current = came_from[current]
            path.reverse()

            full_path = [start_point] + path + [shelter_point]
            total_dist = self._haversine_km(start_point, start_node) + g_score[shelter_node] + self._haversine_km(shelter_node, shelter_point)

            return {
                "path": full_path,
                "shelter": shelter,
                "distance_km": total_dist,
            }
        else:
            return {
                "path": [start_point, shelter_point],
                "shelter": shelter,
                "distance_km": best_dist,
            }

    @staticmethod
    def _haversine_km(p1: tuple[float, float], p2: tuple[float, float]) -> float:
        import math
        lat1, lon1 = math.radians(p1[1]), math.radians(p1[0])
        lat2, lon2 = math.radians(p2[1]), math.radians(p2[0])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        return 6371.0 * c

    def _on_ward_clicked(self, feature_json: str) -> None:
        try:
            feature = json.loads(feature_json)
            geometry = feature.get("geometry") or {}
            props = feature.get("properties") or {}

            center = self._feature_center(geometry)
            if center is None:
                return

            lon, lat = center
            name = props.get("name") or props.get("Name2") or props.get("Name1") or "Unknown"

            location = LocationProfile(
                name=str(name),
                longitude=lon,
                latitude=lat,
                elevation_m=float(props.get("elevation", 30)),
                vegetation=float(props.get("vegetation", 0.45)),
                population_density=float(props.get("density", 0.5)),
                soil_softness=float(props.get("soil", 0.4)),
                water_distance=float(props.get("water_distance", 0.5)),
                income_level=float(props.get("income_level", 0.5)),
                literacy_rate=float(props.get("literacy_rate", 0.75)),
                elderly_share=float(props.get("elderly_share", 0.1)),
                child_share=float(props.get("child_share", 0.15)),
                disability_share=float(props.get("disability_share", 0.05)),
                hospital_capacity=float(props.get("hospital_capacity", 0.5)),
                fire_station_proximity=float(props.get("fire_station_proximity", 0.5)),
                shelter_capacity=float(props.get("shelter_capacity", 0.5)),
                road_density=float(props.get("road_density", 0.5)),
                informal_settlement=float(props.get("informal_settlement", 0.1)),
                building_quality=float(props.get("building_quality", 0.6)),
                roof_type_score=float(props.get("roof_type_score", 0.6)),
                time_of_day=12,
                season="mixed",
            )

            self.select_location(location, emit=True)
        except Exception:
            pass

    def _on_map_clicked(self, latitude: float, longitude: float) -> None:
        nearest = min(
            self._locations,
            key=lambda loc: (loc.latitude - latitude) ** 2 + ((loc.longitude - longitude) * 0.6) ** 2,
            default=None,
        )
        if nearest is not None and self._point_in_dataset(latitude, longitude):
            location = LocationProfile(
                name=nearest.name, longitude=longitude, latitude=latitude,
                elevation_m=nearest.elevation_m, vegetation=nearest.vegetation,
                population_density=nearest.population_density, soil_softness=nearest.soil_softness,
                water_distance=nearest.water_distance, income_level=nearest.income_level,
                literacy_rate=nearest.literacy_rate, elderly_share=nearest.elderly_share,
                child_share=nearest.child_share, disability_share=nearest.disability_share,
                hospital_capacity=nearest.hospital_capacity,
                fire_station_proximity=nearest.fire_station_proximity,
                shelter_capacity=nearest.shelter_capacity, road_density=nearest.road_density,
                informal_settlement=nearest.informal_settlement,
                building_quality=nearest.building_quality, roof_type_score=nearest.roof_type_score,
                time_of_day=nearest.time_of_day, season=nearest.season,
            )
        else:
            location = LocationProfile(name="Map selection", longitude=longitude, latitude=latitude)
        self.select_location(location, emit=True)

    def _point_in_dataset(self, latitude: float, longitude: float) -> bool:
        """Return true when a click falls inside a bundled ward polygon."""
        def ring_contains(ring):
            inside = False
            for i, point in enumerate(ring):
                x1, y1 = point[0], point[1]
                x2, y2 = ring[(i + 1) % len(ring)][0], ring[(i + 1) % len(ring)][1]
                if (y1 > latitude) != (y2 > latitude):
                    cross = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
                    if longitude < cross:
                        inside = not inside
            return inside
        for feature in (self._dataset.features if self._dataset else []):
            geometry = feature.get("geometry") or {}
            coords = geometry.get("coordinates") or []
            polygons = coords if geometry.get("type") == "MultiPolygon" else [coords]
            if geometry.get("type") not in ("Polygon", "MultiPolygon"):
                continue
            for polygon in polygons:
                if polygon and ring_contains(polygon[0]):
                    return True
        return False

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

    def resetTransform(self) -> None:
        self.reset_view()

    def scale(self, sx: float, sy: float) -> None:
        self._run_map_js(f"map.setZoom(map.getZoom() + ({1 if sx > 1 else -1}))")

    def fitInView(self, rect, aspect_ratio) -> None:
        pass

    def centerOn(self, point) -> None:
        pass

    def grab(self):
        return self._web_view.grab()
