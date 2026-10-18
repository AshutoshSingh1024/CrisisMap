from __future__ import annotations

from .models import Assessment, DisasterType, LocationProfile, RiskLevel, Scenario


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def classify_risk(score: float) -> RiskLevel:
    if score < 25:
        return RiskLevel.LOW
    if score < 50:
        return RiskLevel.MODERATE
    if score < 75:
        return RiskLevel.HIGH
    return RiskLevel.EXTREME


def assess(location: LocationProfile, scenario: Scenario) -> Assessment:
    intensity = scenario.intensity / 10
    duration = min(scenario.duration_hours / 72, 1)

    if scenario.disaster is DisasterType.FLOOD:
        terrain = (1 - min(max(location.elevation_m, 0) / 250, 1)) * 0.45
        proximity = (1 - location.water_distance) * 0.25
        hazard = (intensity * 0.55 + duration * 0.20 + terrain + proximity) / 1.45
        vulnerability = 0.55 * location.population_density + 0.45 * (1 - scenario.preparedness)
        actions = ("Move people and assets toward higher ground.", "Inspect drainage and protect low-lying routes.")
    elif scenario.disaster is DisasterType.WILDFIRE:
        dryness = min(0.35 + duration * 0.30, 0.65)
        hazard = intensity * 0.50 + location.vegetation * 0.35 + dryness * 0.15
        vulnerability = 0.45 * location.population_density + 0.35 * location.vegetation + 0.20 * (1 - scenario.preparedness)
        actions = ("Clear combustible material along evacuation routes.", "Stage water and monitor downwind areas.")
    else:
        amplification = location.soil_softness * 0.30
        hazard = intensity * 0.70 + amplification
        vulnerability = 0.60 * location.population_density + 0.40 * (1 - scenario.preparedness)
        actions = ("Inspect structures and utilities after strong shaking.", "Keep assembly areas clear of damaged buildings.")

    hazard_score = _clamp(hazard * 100)
    exposure_score = _clamp(location.population_density * 100)
    vulnerability_score = _clamp(vulnerability * 100)
    overall = _clamp(hazard_score * 0.52 + exposure_score * 0.25 + vulnerability_score * 0.23)
    level = classify_risk(overall)
    radius = round(1.5 + scenario.intensity * 1.6 + duration * 7, 1)
    summary = (
        f"{level.value} {scenario.disaster.value.lower()} risk at {location.name}. "
        f"The assessment score is {overall:.0f}/100 across hazard, exposure, and vulnerability factors."
    )
    return Assessment(
        location=location,
        scenario=scenario,
        hazard_score=round(hazard_score, 1),
        exposure_score=round(exposure_score, 1),
        vulnerability_score=round(vulnerability_score, 1),
        overall_score=round(overall, 1),
        risk_level=level,
        affected_radius_km=radius,
        summary=summary,
        recommendations=actions,
    )
