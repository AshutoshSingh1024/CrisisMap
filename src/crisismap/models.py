from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class DisasterType(StrEnum):
    FLOOD = "Flood"
    WILDFIRE = "Wildfire"
    EARTHQUAKE = "Earthquake"


class RiskLevel(StrEnum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    EXTREME = "Extreme"


@dataclass(slots=True, frozen=True)
class LocationProfile:
    name: str
    longitude: float
    latitude: float
    elevation_m: float = 30.0
    vegetation: float = 0.45
    population_density: float = 0.50
    soil_softness: float = 0.40
    water_distance: float = 0.50

    def __post_init__(self) -> None:
        if not -180 <= self.longitude <= 180 or not -90 <= self.latitude <= 90:
            raise ValueError("Location coordinates are outside valid geographic bounds.")
        for field in ("vegetation", "population_density", "soil_softness", "water_distance"):
            value = getattr(self, field)
            if not 0 <= value <= 1:
                raise ValueError(f"{field} must be between 0 and 1.")


@dataclass(slots=True, frozen=True)
class Scenario:
    disaster: DisasterType
    intensity: float
    duration_hours: float
    preparedness: float

    def __post_init__(self) -> None:
        if not 0 <= self.intensity <= 10:
            raise ValueError("Intensity must be between 0 and 10.")
        if not 0.5 <= self.duration_hours <= 168:
            raise ValueError("Duration must be between 0.5 and 168 hours.")
        if not 0 <= self.preparedness <= 1:
            raise ValueError("Preparedness must be between 0 and 1.")


@dataclass(slots=True, frozen=True)
class Assessment:
    location: LocationProfile
    scenario: Scenario
    hazard_score: float
    exposure_score: float
    vulnerability_score: float
    overall_score: float
    risk_level: RiskLevel
    affected_radius_km: float
    summary: str
    recommendations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["scenario"]["disaster"] = self.scenario.disaster.value
        result["risk_level"] = self.risk_level.value
        return result
