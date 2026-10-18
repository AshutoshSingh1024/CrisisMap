from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import LocationProfile


@dataclass(slots=True)
class MapDataset:
    name: str
    features: list[dict[str, Any]]
    source: str

    @property
    def locations(self) -> list[LocationProfile]:
        items: list[LocationProfile] = []
        for feature in self.features:
            geometry = feature.get("geometry") or {}
            props = feature.get("properties") or {}
            coordinate = _representative_coordinate(geometry)
            name = props.get("name") or props.get("Name2") or props.get("Name1") or props.get("wardnum")
            if coordinate is None or not name:
                continue
            items.append(LocationProfile(
                name=str(name),
                longitude=coordinate[0],
                latitude=coordinate[1],
                elevation_m=float(props.get("elevation", 30)),
                vegetation=_unit(props.get("vegetation", 0.45)),
                population_density=_unit(props.get("density", 0.5)),
                soil_softness=_unit(props.get("soil", 0.4)),
                water_distance=_unit(props.get("water_distance", 0.5)),
                income_level=_unit(props.get("income_level", 0.5)),
                literacy_rate=_unit(props.get("literacy_rate", 0.75)),
                elderly_share=_unit(props.get("elderly_share", 0.10)),
                child_share=_unit(props.get("child_share", 0.15)),
                disability_share=_unit(props.get("disability_share", 0.05)),
                hospital_capacity=_unit(props.get("hospital_capacity", 0.5)),
                fire_station_proximity=_unit(props.get("fire_station_proximity", 0.5)),
                shelter_capacity=_unit(props.get("shelter_capacity", 0.5)),
                road_density=_unit(props.get("road_density", 0.5)),
                informal_settlement=_unit(props.get("informal_settlement", 0.1)),
                building_quality=_unit(props.get("building_quality", 0.6)),
                roof_type_score=_unit(props.get("roof_type_score", 0.6)),
                time_of_day=int(props.get("time_of_day", 12)),
                season=_season_from_prop(props.get("season", "mixed")),
            ))
        return items


def _unit(value: Any) -> float:
    return max(0.0, min(1.0, float(value)))


def _season_from_prop(value: Any) -> str:
    """Convert season property to categorical string."""
    if isinstance(value, str):
        v = value.lower()
        if v in ("dry", "monsoon", "winter", "summer", "mixed"):
            return v
        return "mixed"
    # Numeric 0-1 mapping
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "mixed"
    if n < 0.2:
        return "dry"
    if n < 0.4:
        return "monsoon"
    if n < 0.6:
        return "winter"
    if n < 0.8:
        return "summer"
    return "mixed"


def _representative_coordinate(geometry: dict[str, Any]) -> tuple[float, float] | None:
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "Point" and coords and len(coords) >= 2:
        return float(coords[0]), float(coords[1])
    if kind == "LineString" and coords and len(coords) >= 2:
        return float(coords[0][0]), float(coords[0][1])
    if kind == "Polygon" and coords and coords[0]:
        ring = coords[0]
    elif kind == "MultiPolygon" and coords and coords[0] and coords[0][0]:
        ring = coords[0][0]
    else:
        return None
    return sum(float(p[0]) for p in ring) / len(ring), sum(float(p[1]) for p in ring) / len(ring)


def load_geojson(path: str | Path, swap_coords: bool = False) -> MapDataset:
    file_path = Path(path)
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read GeoJSON: {exc}") from exc
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ValueError("The selected file must contain a GeoJSON FeatureCollection.")
    features = payload["features"]
    if swap_coords:
        features = [_swap_coordinates(f) for f in features]
    return MapDataset(
        name=str(payload.get("name") or file_path.stem),
        features=features,
        source=str(payload.get("source") or file_path),
    )


def _swap_coordinates(feature: dict) -> dict:
    """Swap [lat, lon] to [lon, lon] for non-standard GeoJSON (e.g. KML exports)."""
    import copy
    feature = copy.deepcopy(feature)
    geometry = feature.get("geometry") or {}

    def swap_coords(coords):
        if isinstance(coords, list):
            if len(coords) >= 2 and all(isinstance(v, (int, float)) for v in coords):
                return [coords[1], coords[0]]
            return [swap_coords(c) for c in coords]
        return coords

    geometry["coordinates"] = swap_coords(geometry.get("coordinates", []))
    feature["geometry"] = geometry
    return feature


def bundled_dataset() -> MapDataset:
    return load_geojson(Path(__file__).parent / "resources" / "data" / "demo_region.geojson")


def pune_dataset() -> MapDataset:
    """Load the real Pune Municipal Corporation ward boundaries (58 wards, ODbL)."""
    dataset = load_geojson(Path(__file__).parent / "resources" / "data" / "pune_wards.geojson", swap_coords=True)
    return MapDataset(name="Pune Municipal Corporation · 58 wards", features=dataset.features, source="OpenCity / Oorvani Foundation · ODbL-1.0")


def streets_dataset() -> MapDataset:
    """Load a representative Pune street network (roads and localities)."""
    return load_geojson(Path(__file__).parent / "resources" / "data" / "pune_streets.geojson")


def procedural_dataset(seed: int = 42, size: int = 7) -> MapDataset:
    """Create a deterministic locally generated terrain grid (noise-like, no dependency)."""
    rng = random.Random(seed)
    phases = [rng.random() * math.tau for _ in range(4)]
    features: list[dict[str, Any]] = []
    for row in range(size):
        for col in range(size):
            x, y = col / size, row / size
            noise = (math.sin(x * 7 + phases[0]) + math.cos(y * 6 + phases[1]) + math.sin((x + y) * 4 + phases[2])) / 6 + .5
            x0, y0 = 72.72 + col * .025, 18.86 + row * .021
            features.append({
                "type": "Feature",
                "properties": {
                    "name": f"Terrain {row + 1}-{col + 1}",
                    "elevation": round(12 + noise * 220, 1),
                    "vegetation": round(_unit(.25 + noise * .7), 2),
                    "density": round(_unit(.75 - noise * .55), 2),
                    "soil": round(_unit(.65 - noise * .35), 2),
                    "water_distance": round(_unit(noise), 2),
                    "income_level": round(_unit(.4 + noise * .4), 2),
                    "literacy_rate": round(_unit(.6 + noise * .3), 2),
                    "elderly_share": round(_unit(.05 + noise * .1), 2),
                    "child_share": round(_unit(.1 + noise * .1), 2),
                    "disability_share": round(_unit(.02 + noise * .05), 2),
                    "hospital_capacity": round(_unit(.3 + noise * .5), 2),
                    "fire_station_proximity": round(_unit(.3 + noise * .5), 2),
                    "shelter_capacity": round(_unit(.3 + noise * .5), 2),
                    "road_density": round(_unit(.4 + noise * .4), 2),
                    "informal_settlement": round(_unit(.1 + noise * .2), 2),
                    "building_quality": round(_unit(.4 + noise * .4), 2),
                    "roof_type_score": round(_unit(.4 + noise * .4), 2),
                    "time_of_day": 12,
                    "season": "mixed",
                },
                "geometry": {"type": "Polygon", "coordinates": [[
                    [x0, y0], [x0 + .025, y0], [x0 + .025, y0 + .021], [x0, y0 + .021], [x0, y0]
                ]]},
            })
    return MapDataset(f"Procedural terrain · seed {seed}", features, "Locally generated synthetic terrain")
