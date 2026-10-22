from __future__ import annotations

import math
import random

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


def _temporal_factor(location: LocationProfile) -> float:
    """Time-of-day multiplier: night hours (22-6) have higher risk due to reduced mobility."""
    hour = location.time_of_day
    if 22 <= hour or hour <= 6:
        return 1.25  # night - higher risk
    if 6 < hour <= 10:
        return 1.1  # morning rush
    if 10 < hour <= 17:
        return 1.0  # day - baseline
    if 17 < hour <= 22:
        return 1.15  # evening
    return 1.0


def _season_factor(location: LocationProfile, disaster: DisasterType) -> float:
    """Seasonal multiplier: monsoon amplifies flood, summer amplifies fire, winter amplifies earthquake (cold stress)."""
    season = location.season
    if disaster is DisasterType.FLOOD:
        if season == "monsoon":
            return 1.5
        if season == "winter":
            return 0.7
        if season == "summer":
            return 0.6
        if season == "dry":
            return 0.5
        return 1.0
    if disaster is DisasterType.WILDFIRE:
        if season == "summer":
            return 1.5
        if season == "dry":
            return 1.3
        if season == "winter":
            return 0.7
        if season == "monsoon":
            return 0.4
        return 1.0
    if disaster is DisasterType.EARTHQUAKE:
        if season == "winter":
            return 1.15  # cold stress, heating fires
        return 1.0
    return 1.0


def _suggest_weights(disaster: DisasterType, location: LocationProfile, season: str) -> tuple[float, float, float]:
    """Auto-suggest AHP weights based on disaster context, season, and local conditions."""
    w_h, w_e, w_v = 0.52, 0.25, 0.23

    # Disaster-specific adjustments
    if disaster is DisasterType.FLOOD:
        w_h = 0.60  # flood is heavily hazard-driven
        w_v = 0.20
        if season == "monsoon":
            w_h = 0.65
            w_v = 0.17
        if location.elevation_m < 50:
            w_v += 0.05  # low elevation increases social vulnerability weight
            w_h -= 0.05
    elif disaster is DisasterType.WILDFIRE:
        w_h = 0.55
        w_v = 0.22
        if season in ("summer", "dry"):
            w_h = 0.62
            w_e = 0.20
            w_v = 0.18
        if location.vegetation > 0.7:
            w_h += 0.05
            w_v -= 0.03
    elif disaster is DisasterType.EARTHQUAKE:
        w_h = 0.48
        w_v = 0.28  # earthquake vulnerability (building quality) matters more
        w_e = 0.24
        if location.building_quality < 0.4:
            w_v += 0.08
            w_h -= 0.06
        if location.population_density > 0.7:
            w_e += 0.05
            w_v -= 0.03

    # Time-of-day adjustments
    hour = location.time_of_day
    if 22 <= hour or hour <= 6:
        w_v += 0.04  # night = more people home, higher social vulnerability
        w_h -= 0.02
    elif 7 <= hour <= 10:
        w_e += 0.04  # rush hour = more people exposed on roads
        w_h -= 0.02

    # Normalize to sum to 1.0
    total = w_h + w_e + w_v
    w_h = round(w_h / total, 2)
    w_e = round(w_e / total, 2)
    w_v = max(0.0, round(1.0 - w_h - w_e, 2))  # ensure exact sum, non-negative
    return w_h, w_e, w_v


def _hazard_flood(location: LocationProfile, scenario: Scenario) -> tuple[float, dict[str, float]]:
    intensity = scenario.intensity / 10
    duration = min(scenario.duration_hours / 72, 1)
    terrain = (1 - min(max(location.elevation_m, 0) / 250, 1)) * 0.45
    proximity = (1 - location.water_distance) * 0.25
    drainage = 1 - location.road_density  # poor drainage = higher risk
    impervious = 1 - location.vegetation  # more concrete = more runoff
    monsoon = _season_factor(location, scenario.disaster)
    temporal = _temporal_factor(location)
    hazard = ((intensity * 0.40 + duration * 0.15 + terrain + proximity)
              * monsoon * temporal * (1 + drainage * 0.20 + impervious * 0.15)) / 2.1
    factors = {
        "rainfall_runoff": round(intensity * 100, 1),
        "elevation_terrain": round(terrain * 100, 1),
        "water_proximity": round(proximity * 100, 1),
        "drainage_quality": round((1 - drainage) * 100, 1),
        "impervious_surface": round(impervious * 100, 1),
        "season_factor": round(monsoon * 100, 1),
        "time_factor": round(temporal * 100, 1),
    }
    return hazard, factors


def _hazard_wildfire(location: LocationProfile, scenario: Scenario) -> tuple[float, dict[str, float]]:
    intensity = scenario.intensity / 10
    duration = min(scenario.duration_hours / 72, 1)
    dryness = min(0.35 + duration * 0.30, 0.65)
    fuel = location.vegetation
    wind_exposure = location.income_level  # proxy for open vs dense area
    dry_season = _season_factor(location, scenario.disaster)
    temporal = _temporal_factor(location)
    hazard = (intensity * 0.45 + fuel * 0.30 + dryness * 0.15 + wind_exposure * 0.10) * dry_season * temporal
    factors = {
        "fire_weather": round(intensity * 100, 1),
        "vegetation_fuel": round(fuel * 100, 1),
        "dryness": round(dryness * 100, 1),
        "wind_exposure": round(wind_exposure * 100, 1),
        "season_factor": round(dry_season * 100, 1),
        "time_factor": round(temporal * 100, 1),
    }
    return hazard, factors


def _hazard_earthquake(location: LocationProfile, scenario: Scenario) -> tuple[float, dict[str, float]]:
    intensity = scenario.intensity / 10
    amplification = location.soil_softness * 0.30
    building_quality = 1 - location.building_quality
    informal = location.informal_settlement
    distance_fault = location.water_distance  # proxy
    temporal = _temporal_factor(location)
    season_factor = _season_factor(location, scenario.disaster)
    hazard = (intensity * 0.60 + amplification + building_quality * 0.15 + informal * 0.10) * season_factor * temporal
    factors = {
        "ground_shaking": round(intensity * 100, 1),
        "soil_amplification": round(amplification * 100, 1),
        "building_quality": round((1 - building_quality) * 100, 1),
        "informal_housing": round(informal * 100, 1),
        "fault_proximity": round((1 - distance_fault) * 100, 1),
        "season_factor": round(season_factor * 100, 1),
        "time_factor": round(temporal * 100, 1),
    }
    return hazard, factors


def _vulnerability(location: LocationProfile, scenario: Scenario) -> tuple[float, dict[str, float]]:
    pop_density = location.population_density
    prep = 1 - scenario.preparedness
    # Socioeconomic
    low_income = 1 - location.income_level
    low_literacy = 1 - location.literacy_rate
    vulnerable_age = location.elderly_share + location.child_share
    disability = location.disability_share
    # Infrastructure
    low_hospital = 1 - location.hospital_capacity
    low_fire = 1 - location.fire_station_proximity
    low_shelter = 1 - location.shelter_capacity
    # Housing
    informal = location.informal_settlement
    poor_building = 1 - location.building_quality
    poor_roof = 1 - location.roof_type_score
    # Temporal
    temporal = _temporal_factor(location)

    vulnerability = (
        0.30 * pop_density
        + 0.20 * low_income
        + 0.15 * low_literacy
        + 0.10 * vulnerable_age
        + 0.10 * disability
        + 0.10 * low_hospital
        + 0.05 * low_fire
        + 0.10 * low_shelter
        + 0.15 * informal
        + 0.10 * poor_building
        + 0.05 * poor_roof
    ) * temporal * prep

    factors = {
        "population_density": round(pop_density * 100, 1),
        "low_income": round(low_income * 100, 1),
        "low_literacy": round(low_literacy * 100, 1),
        "vulnerable_age": round(vulnerable_age * 100, 1),
        "disability": round(disability * 100, 1),
        "hospital_access": round((1 - low_hospital) * 100, 1),
        "fire_station_access": round((1 - low_fire) * 100, 1),
        "shelter_access": round((1 - low_shelter) * 100, 1),
        "informal_housing": round(informal * 100, 1),
        "building_quality": round((1 - poor_building) * 100, 1),
        "temporal_factor": round(temporal * 100, 1),
    }
    return vulnerability, factors


def _monte_carlo(
    location: LocationProfile,
    scenario: Scenario,
    hazard_fn,
    vuln_fn,
    samples: int = 500,
    seed: int = 42,
) -> tuple[float, float, float]:
    rng = random.Random(seed)
    scores = []
    for _ in range(samples):
        h, _ = hazard_fn(location, scenario)
        v, _ = vuln_fn(location, scenario)
        e = location.population_density
        # Add noise to each factor
        h_n = h * (1 + rng.uniform(-0.15, 0.15))
        v_n = v * (1 + rng.uniform(-0.15, 0.15))
        e_n = e * (1 + rng.uniform(-0.10, 0.10))
        w_h, w_e, w_v = scenario.weight_hazard, scenario.weight_exposure, scenario.weight_vulnerability
        score = _clamp(h_n * 100 * w_h + e_n * 100 * w_e + v_n * 100 * w_v)
        scores.append(score)
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std = math.sqrt(variance)
    ci = scenario.confidence_interval if hasattr(scenario, "confidence_interval") else 0.9
    z = 1.645 if ci >= 0.9 else 1.282
    lower = _clamp(mean - z * std)
    upper = _clamp(mean + z * std)
    return mean, lower, upper, std


def assess(location: LocationProfile, scenario: Scenario) -> Assessment:
    intensity = scenario.intensity / 10
    duration = min(scenario.duration_hours / 72, 1)

    # Auto-suggest AHP weights if using defaults (context-aware weighting)
    default_weights = (0.52, 0.25, 0.23)
    current_weights = (scenario.weight_hazard, scenario.weight_exposure, scenario.weight_vulnerability)
    if current_weights == default_weights:
        suggested = _suggest_weights(scenario.disaster, location, location.season)
        scenario = Scenario(
            disaster=scenario.disaster,
            intensity=scenario.intensity,
            duration_hours=scenario.duration_hours,
            preparedness=scenario.preparedness,
            weight_hazard=suggested[0],
            weight_exposure=suggested[1],
            weight_vulnerability=suggested[2],
            confidence_interval=scenario.confidence_interval,
        )

    if scenario.disaster is DisasterType.FLOOD:
        hazard, h_factors = _hazard_flood(location, scenario)
        vulnerability, v_factors = _vulnerability(location, scenario)
        actions = (
            "Move people and assets toward higher ground.",
            "Inspect drainage and protect low-lying routes.",
            "Pre-position sandbags at vulnerable choke points.",
        )
    elif scenario.disaster is DisasterType.WILDFIRE:
        hazard, h_factors = _hazard_wildfire(location, scenario)
        vulnerability, v_factors = _vulnerability(location, scenario)
        actions = (
            "Clear combustible material along evacuation routes.",
            "Stage water and monitor downwind areas.",
            "Create defensible space around structures.",
        )
    else:
        hazard, h_factors = _hazard_earthquake(location, scenario)
        vulnerability, v_factors = _vulnerability(location, scenario)
        actions = (
            "Inspect structures and utilities after strong shaking.",
            "Keep assembly areas clear of damaged buildings.",
            "Shut off gas and electricity if leaks are suspected.",
        )

    exposure = location.population_density

    # Monte Carlo uncertainty
    mean_score, ci_lower, ci_upper, mc_std = _monte_carlo(
        location, scenario,
        lambda l, s: (hazard, h_factors) if False else (hazard, {}),
        lambda l, s: (vulnerability, v_factors),
        samples=500,
    )

    # Apply AHP weights
    w_h, w_e, w_v = scenario.weight_hazard, scenario.weight_exposure, scenario.weight_vulnerability
    hazard_score = _clamp(hazard * 100)
    exposure_score = _clamp(exposure * 100)
    vulnerability_score = _clamp(vulnerability * 100)
    overall = _clamp(hazard_score * w_h + exposure_score * w_e + vulnerability_score * w_v)

    level = classify_risk(overall)
    radius = round(0.3 + scenario.intensity * 0.3 + min(scenario.duration_hours, 24) * 0.1, 1)

    # Impact estimates
    area_sq_km = 3.14159 * radius * radius
    intensity_factor = scenario.intensity / 10
    base_density = location.population_density * 5000  # people per sq km max
    people_affected = int(area_sq_km * base_density * intensity_factor)

    property_value_per_sq_km = 500_000_000  # ₹50 crore per sq km (urban Pune baseline)
    damage_factor = (overall / 100) * (1 - location.building_quality * 0.4)
    damage_factor *= (1 + location.informal_settlement * 0.5)
    property_loss_inr = area_sq_km * property_value_per_sq_km * damage_factor

    summary = (
        f"{level.value} {scenario.disaster.value.lower()} risk at {location.name}. "
        f"The assessment score is {overall:.0f}/100 across hazard, exposure, and vulnerability factors."
        f" Confidence interval ({int(scenario.confidence_interval * 100)}%): {ci_lower:.0f}–{ci_upper:.0f}."
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
        people_affected=people_affected,
        property_loss_inr=round(property_loss_inr, 0),
        confidence_lower=round(ci_lower, 1),
        confidence_upper=round(ci_upper, 1),
        confidence_interval=scenario.confidence_interval,
        mc_samples=500,
        mc_std=round(mc_std, 1),
        hazard_factors=h_factors,
        vulnerability_factors=v_factors,
    )


def simulate_time_series(location: LocationProfile, scenario: Scenario, steps: int = 24) -> list[dict]:
    """Model risk evolution over the duration hours.

    Returns a list of dicts with 'hour', 'hazard', 'exposure', 'vulnerability', 'overall'
    for each time step. Useful for showing how risk builds or decays over the event duration.
    """
    results = []
    duration_hours = scenario.duration_hours
    if duration_hours <= 0:
        return results

    step_hours = duration_hours / steps
    base_intensity = scenario.intensity / 10

    for i in range(steps + 1):
        t = i * step_hours
        # Progress through the event (0 = start, 1 = end)
        progress = t / duration_hours if duration_hours > 0 else 1.0

        # Hazard typically builds then plateaus/decays depending on disaster type
        if scenario.disaster is DisasterType.FLOOD:
            # Flood risk builds as water accumulates, peaks near end
            intensity_factor = 0.4 + 0.6 * progress
        elif scenario.disaster is DisasterType.WILDFIRE:
            # Wildfire risk builds fast early, then may plateau
            intensity_factor = 0.5 + 0.5 * (1 - math.exp(-3 * progress))
        else:  # Earthquake
            # Earthquake risk is immediate, doesn't build over time
            intensity_factor = 1.0

        current_intensity = base_intensity * intensity_factor

        # Create a modified scenario for this time step
        ts_scenario = Scenario(
            disaster=scenario.disaster,
            intensity=current_intensity * 10,
            duration_hours=step_hours,
            preparedness=scenario.preparedness,
            weight_hazard=scenario.weight_hazard,
            weight_exposure=scenario.weight_exposure,
            weight_vulnerability=scenario.weight_vulnerability,
            confidence_interval=scenario.confidence_interval,
        )

        # Compute scores directly without Monte Carlo for speed
        if scenario.disaster is DisasterType.FLOOD:
            hazard, _ = _hazard_flood(location, ts_scenario)
        elif scenario.disaster is DisasterType.WILDFIRE:
            hazard, _ = _hazard_wildfire(location, ts_scenario)
        else:
            hazard, _ = _hazard_earthquake(location, ts_scenario)

        vulnerability, _ = _vulnerability(location, ts_scenario)
        exposure = location.population_density

        w_h, w_e, w_v = ts_scenario.weight_hazard, ts_scenario.weight_exposure, ts_scenario.weight_vulnerability
        h_score = _clamp(hazard * 100)
        e_score = _clamp(exposure * 100)
        v_score = _clamp(vulnerability * 100)
        overall = _clamp(h_score * w_h + e_score * w_e + v_score * w_v)

        results.append({
            "hour": round(t, 1),
            "hazard": round(h_score, 1),
            "exposure": round(e_score, 1),
            "vulnerability": round(v_score, 1),
            "overall": round(overall, 1),
        })

    return results
