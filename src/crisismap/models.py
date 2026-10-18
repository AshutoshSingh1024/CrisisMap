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
    # Socioeconomic factors
    income_level: float = 0.50
    literacy_rate: float = 0.75
    elderly_share: float = 0.10
    child_share: float = 0.15
    disability_share: float = 0.05
    # Infrastructure factors
    hospital_capacity: float = 0.50
    fire_station_proximity: float = 0.50
    shelter_capacity: float = 0.50
    road_density: float = 0.50
    # Housing factors
    informal_settlement: float = 0.10
    building_quality: float = 0.60
    roof_type_score: float = 0.60
    # Time/season
    time_of_day: int = 12  # 0-23 hour
    season: str = "mixed"  # dry, monsoon, winter, summer, mixed

    def __post_init__(self) -> None:
        if not -180 <= self.longitude <= 180 or not -90 <= self.latitude <= 90:
            raise ValueError("Location coordinates are outside valid geographic bounds.")
        for field in ("vegetation", "population_density", "soil_softness", "water_distance",
                       "income_level", "literacy_rate", "elderly_share", "child_share",
                       "disability_share", "hospital_capacity", "fire_station_proximity",
                       "shelter_capacity", "road_density", "informal_settlement",
                       "building_quality", "roof_type_score"):
            value = getattr(self, field)
            if not 0 <= value <= 1:
                raise ValueError(f"{field} must be between 0 and 1.")
        if not 0 <= self.time_of_day <= 23:
            raise ValueError("time_of_day must be between 0 and 23.")
        if self.season not in ("dry", "monsoon", "winter", "summer", "mixed"):
            raise ValueError("season must be one of: dry, monsoon, winter, summer, mixed")


@dataclass(slots=True, frozen=True)
class Scenario:
    disaster: DisasterType
    intensity: float
    duration_hours: float
    preparedness: float
    # AHP weights (user adjustable, auto-suggested by context)
    weight_hazard: float = 0.52
    weight_exposure: float = 0.25
    weight_vulnerability: float = 0.23
    # Uncertainty
    confidence_interval: float = 0.9

    def __post_init__(self) -> None:
        if not 0 <= self.intensity <= 10:
            raise ValueError("Intensity must be between 0 and 10.")
        if not 0.5 <= self.duration_hours <= 168:
            raise ValueError("Duration must be between 0.5 and 168 hours.")
        if not 0 <= self.preparedness <= 1:
            raise ValueError("Preparedness must be between 0 and 1.")
        if not 0 <= self.confidence_interval <= 1:
            raise ValueError("Confidence interval must be between 0 and 1.")
        total = self.weight_hazard + self.weight_exposure + self.weight_vulnerability
        if not 0.95 <= total <= 1.05:
            raise ValueError("AHP weights must sum to 1.0.")


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
    # Impact estimates
    people_affected: int = 0
    property_loss_inr: float = 0.0
    # Uncertainty
    confidence_lower: float = 0.0
    confidence_upper: float = 100.0
    confidence_interval: float = 0.9
    # Monte Carlo details
    mc_samples: int = 0
    mc_std: float = 0.0
    # Multi-hazard
    hazard_factors: dict[str, float] | None = None
    vulnerability_factors: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["scenario"]["disaster"] = self.scenario.disaster.value
        result["risk_level"] = self.risk_level.value
        return result
