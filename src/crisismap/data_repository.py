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
            if coordinate is None or not props.get("name"):
                continue
            items.append(LocationProfile(
                name=str(props["name"]),
                longitude=coordinate[0],
                latitude=coordinate[1],
                elevation_m=float(props.get("elevation", 30)),
                vegetation=_unit(props.get("vegetation", 0.45)),
                population_density=_unit(props.get("density", 0.5)),
                soil_softness=_unit(props.get("soil", 0.4)),
                water_distance=_unit(props.get("water_distance", 0.5)),
            ))
        return items


def _unit(value: Any) -> float:
    return max(0.0, min(1.0, float(value)))


def _representative_coordinate(geometry: dict[str, Any]) -> tuple[float, float] | None:
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "Point" and coords and len(coords) >= 2:
        return float(coords[0]), float(coords[1])
    if kind == "Polygon" and coords and coords[0]:
        ring = coords[0]
    elif kind == "MultiPolygon" and coords and coords[0] and coords[0][0]:
        ring = coords[0][0]
    else:
        return None
    return sum(float(p[0]) for p in ring) / len(ring), sum(float(p[1]) for p in ring) / len(ring)


def load_geojson(path: str | Path) -> MapDataset:
    file_path = Path(path)
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read GeoJSON: {exc}") from exc
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ValueError("The selected file must contain a GeoJSON FeatureCollection.")
    return MapDataset(
        name=str(payload.get("name") or file_path.stem),
        features=payload["features"],
        source=str(payload.get("source") or file_path),
    )


def bundled_dataset() -> MapDataset:
    return load_geojson(Path(__file__).parent / "resources" / "data" / "demo_region.geojson")


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
                },
                "geometry": {"type": "Polygon", "coordinates": [[
                    [x0, y0], [x0 + .025, y0], [x0 + .025, y0 + .021], [x0, y0 + .021], [x0, y0]
                ]]},
            })
    return MapDataset(f"Procedural terrain · seed {seed}", features, "Locally generated synthetic terrain")
