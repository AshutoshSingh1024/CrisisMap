import unittest

from crisismap.models import DisasterType, LocationProfile, RiskLevel, Scenario
from crisismap.simulation import assess, classify_risk, _suggest_weights


class EdgeCaseTests(unittest.TestCase):
    """Edge case and negative filtering tests for the risk assessment engine."""

    def setUp(self):
        self.base_location = LocationProfile(
            name="Test Ward",
            longitude=72.88,
            latitude=19.05,
            elevation_m=12,
            vegetation=.7,
            population_density=.8,
            soil_softness=.6,
            water_distance=.1,
            income_level=.5,
            literacy_rate=.75,
            elderly_share=.10,
            child_share=.15,
            disability_share=.05,
            hospital_capacity=.5,
            fire_station_proximity=.5,
            shelter_capacity=.5,
            road_density=.5,
            informal_settlement=.1,
            building_quality=.6,
            roof_type_score=.6,
            time_of_day=12,
            season="mixed",
        )

    # --- Risk level suggestions ---
    def test_suggestion_low_risk(self):
        loc = LocationProfile(
            name="Safe", longitude=73.0, latitude=18.5, elevation_m=500,
            vegetation=0.1, population_density=0.2, soil_softness=0.2, water_distance=0.9,
            income_level=0.9, literacy_rate=0.95, elderly_share=0.05, child_share=0.1,
            disability_share=0.02, hospital_capacity=0.9, fire_station_proximity=0.9,
            shelter_capacity=0.9, road_density=0.9, informal_settlement=0.05,
            building_quality=0.9, roof_type_score=0.9, time_of_day=12, season="dry",
        )
        result = assess(loc, Scenario(DisasterType.FLOOD, 1, 1, 0.9))
        # Low risk should still have recommendations from assess()
        self.assertGreaterEqual(len(result.recommendations), 1)
        self.assertIsInstance(result.recommendations, tuple)

    def test_suggestion_moderate_risk(self):
        loc = LocationProfile(
            name="Mod", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=0.3, population_density=0.5, soil_softness=0.4, water_distance=0.6,
            income_level=0.6, literacy_rate=0.8, elderly_share=0.1, child_share=0.15,
            disability_share=0.04, hospital_capacity=0.6, fire_station_proximity=0.6,
            shelter_capacity=0.6, road_density=0.6, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        result = assess(loc, Scenario(DisasterType.FLOOD, 4, 6, 0.5))
        self.assertGreaterEqual(len(result.recommendations), 1)

    def test_suggestion_high_risk(self):
        loc = LocationProfile(
            name="High", longitude=73.0, latitude=18.5, elevation_m=100,
            vegetation=0.5, population_density=0.7, soil_softness=0.5, water_distance=0.4,
            income_level=0.4, literacy_rate=0.6, elderly_share=0.12, child_share=0.18,
            disability_share=0.06, hospital_capacity=0.4, fire_station_proximity=0.4,
            shelter_capacity=0.4, road_density=0.4, informal_settlement=0.15,
            building_quality=0.4, roof_type_score=0.4, time_of_day=12, season="mixed",
        )
        result = assess(loc, Scenario(DisasterType.FLOOD, 7, 12, 0.3))
        self.assertGreaterEqual(len(result.recommendations), 1)

    def test_suggestion_extreme_risk(self):
        loc = LocationProfile(
            name="Extreme", longitude=73.0, latitude=18.5, elevation_m=10,
            vegetation=0.9, population_density=0.95, soil_softness=0.8, water_distance=0.1,
            income_level=0.1, literacy_rate=0.4, elderly_share=0.2, child_share=0.25,
            disability_share=0.1, hospital_capacity=0.1, fire_station_proximity=0.1,
            shelter_capacity=0.1, road_density=0.1, informal_settlement=0.5,
            building_quality=0.1, roof_type_score=0.1, time_of_day=3, season="monsoon",
        )
        result = assess(loc, Scenario(DisasterType.FLOOD, 9, 48, 0.1))
        self.assertGreaterEqual(len(result.recommendations), 1)

    # --- Elevation suggestion (low elevation → flood exposure) ---
    def test_low_elevation_increases_flood_hazard(self):
        low_loc = LocationProfile(
            name="Low", longitude=73.0, latitude=18.5, elevation_m=10,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="dry",
        )
        high_loc = LocationProfile(
            name="High", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="dry",
        )
        low_result = assess(low_loc, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        high_result = assess(high_loc, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        self.assertGreater(low_result.hazard_score, high_result.hazard_score)

    # --- Vegetation suggestion (high vegetation → wildfire risk) ---
    def test_high_vegetation_increases_wildfire_hazard(self):
        low_veg = LocationProfile(
            name="LowVeg", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=0.5, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="summer",
        )
        high_veg = LocationProfile(
            name="HighVeg", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=0.9, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="summer",
        )
        low_result = assess(low_veg, Scenario(DisasterType.WILDFIRE, 6, 24, 0.5))
        high_result = assess(high_veg, Scenario(DisasterType.WILDFIRE, 6, 24, 0.5))
        self.assertGreater(high_result.hazard_score, low_result.hazard_score)

    # --- Population density suggestion (congestion) ---
    def test_high_population_density_increases_vulnerability(self):
        low_density = LocationProfile(
            name="LowDen", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        high_density = LocationProfile(
            name="HighDen", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.9, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        low_result = assess(low_density, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        high_result = assess(high_density, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        self.assertGreater(high_result.vulnerability_score, low_result.vulnerability_score)

    # --- Informal settlement suggestion ---
    def test_high_informal_settlement_increases_vulnerability(self):
        low_informal = LocationProfile(
            name="Formal", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.05,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        high_informal = LocationProfile(
            name="Informal", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.5,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        low_result = assess(low_informal, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        high_result = assess(high_informal, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        self.assertGreater(high_result.vulnerability_score, low_result.vulnerability_score)

    # --- Hospital capacity suggestion ---
    def test_low_hospital_capacity_increases_vulnerability(self):
        good_hospital = LocationProfile(
            name="GoodHosp", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.9, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        poor_hospital = LocationProfile(
            name="PoorHosp", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.1, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        good_result = assess(good_hospital, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        poor_result = assess(poor_hospital, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        self.assertGreater(poor_result.vulnerability_score, good_result.vulnerability_score)

    # --- Fire station proximity suggestion ---
    def test_far_fire_station_increases_vulnerability(self):
        near_fire = LocationProfile(
            name="NearFire", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.9,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        far_fire = LocationProfile(
            name="FarFire", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.1,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        near_result = assess(near_fire, Scenario(DisasterType.WILDFIRE, 6, 24, 0.5))
        far_result = assess(far_fire, Scenario(DisasterType.WILDFIRE, 6, 24, 0.5))
        self.assertGreater(far_result.vulnerability_score, near_result.vulnerability_score)

    # --- Shelter capacity suggestion ---
    def test_low_shelter_capacity_increases_vulnerability(self):
        good_shelter = LocationProfile(
            name="GoodShelter", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.9, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        poor_shelter = LocationProfile(
            name="PoorShelter", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.1, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        good_result = assess(good_shelter, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        poor_result = assess(poor_shelter, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        self.assertGreater(poor_result.vulnerability_score, good_result.vulnerability_score)

    # --- Building quality suggestion ---
    def test_poor_building_quality_increases_vulnerability(self):
        good_building = LocationProfile(
            name="GoodBuild", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.9, roof_type_score=0.9, time_of_day=12, season="mixed",
        )
        poor_building = LocationProfile(
            name="PoorBuild", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.2, roof_type_score=0.2, time_of_day=12, season="mixed",
        )
        good_result = assess(good_building, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        poor_result = assess(poor_building, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        self.assertGreater(poor_result.vulnerability_score, good_result.vulnerability_score)

    # --- Time of day suggestion (night) ---
    def test_night_time_increases_vulnerability(self):
        day_loc = LocationProfile(
            name="Day", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=14, season="mixed",
        )
        night_loc = LocationProfile(
            name="Night", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=3, season="mixed",
        )
        day_result = assess(day_loc, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        night_result = assess(night_loc, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        self.assertGreaterEqual(night_result.overall_score, day_result.overall_score)

    # --- Monsoon + flood suggestion ---
    def test_monsoon_increases_flood_hazard(self):
        dry_loc = LocationProfile(
            name="Dry", longitude=73.0, latitude=18.5, elevation_m=50,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="dry",
        )
        monsoon_loc = LocationProfile(
            name="Monsoon", longitude=73.0, latitude=18.5, elevation_m=50,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="monsoon",
        )
        dry_result = assess(dry_loc, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        monsoon_result = assess(monsoon_loc, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        self.assertGreater(monsoon_result.hazard_score, dry_result.hazard_score)

    # --- Road density suggestion (low density → drainage) ---
    def test_low_road_density_increases_flood_hazard(self):
        good_road = LocationProfile(
            name="GoodRoad", longitude=73.0, latitude=18.5, elevation_m=100,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.9, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="dry",
        )
        poor_road = LocationProfile(
            name="PoorRoad", longitude=73.0, latitude=18.5, elevation_m=100,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.1, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="dry",
        )
        good_result = assess(good_road, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        poor_result = assess(poor_road, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        self.assertGreater(poor_result.hazard_score, good_result.hazard_score)

    # --- Disaster-specific recommendations (flood) ---
    def test_flood_recommendations(self):
        loc = LocationProfile(
            name="Test", longitude=73.0, latitude=18.5, elevation_m=100,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        result = assess(loc, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        self.assertTrue(any("higher ground" in r.lower() for r in result.recommendations))
        self.assertTrue(any("drainage" in r.lower() for r in result.recommendations))

    # --- Disaster-specific recommendations (wildfire) ---
    def test_wildfire_recommendations(self):
        loc = LocationProfile(
            name="Test", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        result = assess(loc, Scenario(DisasterType.WILDFIRE, 6, 24, 0.5))
        self.assertTrue(any("combustible" in r.lower() for r in result.recommendations))
        self.assertTrue(any("defensible" in r.lower() for r in result.recommendations))

    # --- Disaster-specific recommendations (earthquake) ---
    def test_earthquake_recommendations(self):
        loc = LocationProfile(
            name="Test", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        result = assess(loc, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        self.assertTrue(any("structures" in r.lower() or "shaking" in r.lower() for r in result.recommendations))
        self.assertTrue(any("gas" in r.lower() or "electric" in r.lower() for r in result.recommendations))

    # --- Elderly share suggestion ---
    def test_high_elderly_share_increases_vulnerability(self):
        low_elderly = LocationProfile(
            name="Young", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.05, child_share=0.1,
            disability_share=0.02, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        high_elderly = LocationProfile(
            name="Old", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.2, child_share=0.1,
            disability_share=0.02, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        low_result = assess(low_elderly, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        high_result = assess(high_elderly, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        self.assertGreater(high_result.vulnerability_score, low_result.vulnerability_score)

    # --- Child share suggestion ---
    def test_high_child_share_increases_vulnerability(self):
        low_child = LocationProfile(
            name="FewChild", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.1,
            disability_share=0.02, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        high_child = LocationProfile(
            name="ManyChild", longitude=73.0, latitude=18.5, elevation_m=200,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.3,
            disability_share=0.02, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="mixed",
        )
        low_result = assess(low_child, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        high_result = assess(high_child, Scenario(DisasterType.EARTHQUAKE, 6, 24, 0.5))
        self.assertGreater(high_result.vulnerability_score, low_result.vulnerability_score)

    # --- Overall score > 60 suggestion ---
    def test_high_overall_score_impact(self):
        low_risk_loc = LocationProfile(
            name="Safe", longitude=73.0, latitude=18.5, elevation_m=500,
            vegetation=0.1, population_density=0.2, soil_softness=0.2, water_distance=0.9,
            income_level=0.9, literacy_rate=0.95, elderly_share=0.05, child_share=0.1,
            disability_share=0.02, hospital_capacity=0.9, fire_station_proximity=0.9,
            shelter_capacity=0.9, road_density=0.9, informal_settlement=0.05,
            building_quality=0.9, roof_type_score=0.9, time_of_day=12, season="dry",
        )
        high_risk_loc = LocationProfile(
            name="Risk", longitude=73.0, latitude=18.5, elevation_m=10,
            vegetation=0.9, population_density=0.95, soil_softness=0.8, water_distance=0.1,
            income_level=0.1, literacy_rate=0.4, elderly_share=0.2, child_share=0.25,
            disability_share=0.1, hospital_capacity=0.1, fire_station_proximity=0.1,
            shelter_capacity=0.1, road_density=0.1, informal_settlement=0.5,
            building_quality=0.1, roof_type_score=0.1, time_of_day=3, season="monsoon",
        )
        low_result = assess(low_risk_loc, Scenario(DisasterType.FLOOD, 3, 6, 0.9))
        high_result = assess(high_risk_loc, Scenario(DisasterType.FLOOD, 9, 48, 0.1))
        self.assertLess(low_result.overall_score, 60)
        self.assertGreaterEqual(high_result.overall_score, 60)

    # --- Dense vegetation suggestion (vegetation > 0.7) ---
    def test_dense_vegetation_increases_wildfire_hazard(self):
        mod_veg = LocationProfile(
            name="ModVeg", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=0.6, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="summer",
        )
        dense_veg = LocationProfile(
            name="DenseVeg", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=0.9, population_density=0.5, soil_softness=0.4, water_distance=0.5,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="summer",
        )
        mod_result = assess(mod_veg, Scenario(DisasterType.WILDFIRE, 6, 24, 0.5))
        dense_result = assess(dense_veg, Scenario(DisasterType.WILDFIRE, 6, 24, 0.5))
        self.assertGreater(dense_result.hazard_score, mod_result.hazard_score)

    # --- Water distance suggestion (close to water) ---
    def test_close_to_water_increases_flood_hazard(self):
        far_water = LocationProfile(
            name="FarWater", longitude=73.0, latitude=18.5, elevation_m=100,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.9,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="dry",
        )
        near_water = LocationProfile(
            name="NearWater", longitude=73.0, latitude=18.5, elevation_m=100,
            vegetation=0.4, population_density=0.5, soil_softness=0.4, water_distance=0.1,
            income_level=0.5, literacy_rate=0.75, elderly_share=0.1, child_share=0.15,
            disability_share=0.05, hospital_capacity=0.5, fire_station_proximity=0.5,
            shelter_capacity=0.5, road_density=0.5, informal_settlement=0.1,
            building_quality=0.6, roof_type_score=0.6, time_of_day=12, season="dry",
        )
        far_result = assess(far_water, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        near_result = assess(near_water, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        self.assertGreater(near_result.hazard_score, far_result.hazard_score)

    # --- Risk classification boundaries ---
    def test_classification_exact_boundaries(self):
        self.assertEqual(classify_risk(0), RiskLevel.LOW)
        self.assertEqual(classify_risk(24.99), RiskLevel.LOW)
        self.assertEqual(classify_risk(25), RiskLevel.MODERATE)
        self.assertEqual(classify_risk(49.99), RiskLevel.MODERATE)
        self.assertEqual(classify_risk(50), RiskLevel.HIGH)
        self.assertEqual(classify_risk(74.99), RiskLevel.HIGH)
        self.assertEqual(classify_risk(75), RiskLevel.EXTREME)
        self.assertEqual(classify_risk(100), RiskLevel.EXTREME)

    def test_classification_negative_clamped(self):
        # Scores below 0 should still classify as LOW
        self.assertEqual(classify_risk(-10), RiskLevel.LOW)
        self.assertEqual(classify_risk(-100), RiskLevel.LOW)

    def test_classification_above_100(self):
        self.assertEqual(classify_risk(150), RiskLevel.EXTREME)
        self.assertEqual(classify_risk(1000), RiskLevel.EXTREME)

    # --- Assessment bounds ---
    def test_assessment_always_within_0_100(self):
        for disaster in DisasterType:
            for intensity in (0, 1, 5, 10):
                for duration in (0.5, 24, 168):
                    for prep in (0, 0.5, 1):
                        loc = LocationProfile(
                            name="Edge", longitude=73.0, latitude=18.5,
                            elevation_m=0, vegetation=1.0, population_density=1.0,
                            soil_softness=1.0, water_distance=0.0,
                            income_level=0.0, literacy_rate=0.0, elderly_share=1.0,
                            child_share=1.0, disability_share=1.0,
                            hospital_capacity=0.0, fire_station_proximity=0.0,
                            shelter_capacity=0.0, road_density=0.0,
                            informal_settlement=1.0, building_quality=0.0,
                            roof_type_score=0.0, time_of_day=3, season="monsoon",
                        )
                        result = assess(loc, Scenario(disaster, intensity, duration, prep))
                        self.assertGreaterEqual(result.overall_score, 0.0)
                        self.assertLessEqual(result.overall_score, 100.0)
                        self.assertGreaterEqual(result.hazard_score, 0.0)
                        self.assertLessEqual(result.hazard_score, 100.0)
                        self.assertGreaterEqual(result.exposure_score, 0.0)
                        self.assertLessEqual(result.exposure_score, 100.0)
                        self.assertGreaterEqual(result.vulnerability_score, 0.0)
                        self.assertLessEqual(result.vulnerability_score, 100.0)

    # --- Intensity monotonicity ---
    def test_higher_intensity_increases_all_disasters(self):
        for disaster in DisasterType:
            low = assess(self.base_location, Scenario(disaster, 2, 12, 0.5))
            high = assess(self.base_location, Scenario(disaster, 9, 12, 0.5))
            self.assertGreater(high.overall_score, low.overall_score)

    # --- Preparedness reduces vulnerability ---
    def test_preparedness_reduces_overall(self):
        weak = assess(self.base_location, Scenario(DisasterType.EARTHQUAKE, 7, 2, 0.1))
        strong = assess(self.base_location, Scenario(DisasterType.EARTHQUAKE, 7, 2, 0.9))
        self.assertLess(strong.overall_score, weak.overall_score)

    # --- Elevation reduces flood risk ---
    def test_higher_elevation_reduces_flood_risk(self):
        low_loc = LocationProfile(
            name="Low", longitude=73.0, latitude=18.5, elevation_m=5,
            vegetation=.4, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="dry",
        )
        high_loc = LocationProfile(
            name="High", longitude=73.0, latitude=18.5, elevation_m=500,
            vegetation=.4, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="dry",
        )
        low_risk = assess(low_loc, Scenario(DisasterType.FLOOD, 7, 24, 0.5))
        high_risk = assess(high_loc, Scenario(DisasterType.FLOOD, 7, 24, 0.5))
        self.assertLess(high_risk.hazard_score, low_risk.hazard_score)

    # --- Vegetation increases wildfire risk ---
    def test_higher_vegetation_increases_wildfire(self):
        low_veg = LocationProfile(
            name="LowVeg", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=0.1, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="summer",
        )
        high_veg = LocationProfile(
            name="HighVeg", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=0.9, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="summer",
        )
        low_risk = assess(low_veg, Scenario(DisasterType.WILDFIRE, 7, 24, 0.5))
        high_risk = assess(high_veg, Scenario(DisasterType.WILDFIRE, 7, 24, 0.5))
        self.assertGreater(high_risk.hazard_score, low_risk.hazard_score)

    # --- Soil softness increases earthquake risk ---
    def test_softer_soil_increases_earthquake(self):
        hard = LocationProfile(
            name="Hard", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=.4, population_density=.5, soil_softness=0.1, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="mixed",
        )
        soft = LocationProfile(
            name="Soft", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=.4, population_density=.5, soil_softness=0.9, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="mixed",
        )
        hard_risk = assess(hard, Scenario(DisasterType.EARTHQUAKE, 7, 24, 0.5))
        soft_risk = assess(soft, Scenario(DisasterType.EARTHQUAKE, 7, 24, 0.5))
        self.assertGreater(soft_risk.hazard_score, hard_risk.hazard_score)

    # --- Invalid scenarios rejected ---
    def test_invalid_intensity_rejected(self):
        with self.assertRaises(ValueError):
            Scenario(DisasterType.FLOOD, 11, 12, 0.5)
        with self.assertRaises(ValueError):
            Scenario(DisasterType.FLOOD, -1, 12, 0.5)

    def test_invalid_duration_rejected(self):
        with self.assertRaises(ValueError):
            Scenario(DisasterType.FLOOD, 5, 0.4, 0.5)
        with self.assertRaises(ValueError):
            Scenario(DisasterType.FLOOD, 5, 200, 0.5)

    def test_invalid_preparedness_rejected(self):
        with self.assertRaises(ValueError):
            Scenario(DisasterType.FLOOD, 5, 12, 1.5)
        with self.assertRaises(ValueError):
            Scenario(DisasterType.FLOOD, 5, 12, -0.1)

    def test_invalid_weights_rejected(self):
        with self.assertRaises(ValueError):
            Scenario(DisasterType.FLOOD, 5, 12, 0.5, weight_hazard=0.8, weight_exposure=0.2, weight_vulnerability=0.2)

    # --- Location coordinate validation ---
    def test_invalid_coordinates_rejected(self):
        with self.assertRaises(ValueError):
            LocationProfile(name="Bad", longitude=200, latitude=10)
        with self.assertRaises(ValueError):
            LocationProfile(name="Bad", longitude=10, latitude=100)

    def test_invalid_unit_fields_rejected(self):
        with self.assertRaises(ValueError):
            LocationProfile(name="Bad", longitude=73, latitude=18, population_density=1.5)

    # --- Time of day effects ---
    def test_night_higher_risk_than_day(self):
        night_loc = LocationProfile(
            name="Night", longitude=73.0, latitude=18.5, elevation_m=100,
            vegetation=.4, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=3, season="mixed",
        )
        day_loc = LocationProfile(
            name="Day", longitude=73.0, latitude=18.5, elevation_m=100,
            vegetation=.4, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=14, season="mixed",
        )
        night_risk = assess(night_loc, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        day_risk = assess(day_loc, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        self.assertGreaterEqual(night_risk.overall_score, day_risk.overall_score)

    # --- Season effects ---
    def test_monsoon_increases_flood_risk(self):
        monsoon_loc = LocationProfile(
            name="M", longitude=73.0, latitude=18.5, elevation_m=50,
            vegetation=.4, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="monsoon",
        )
        dry_loc = LocationProfile(
            name="D", longitude=73.0, latitude=18.5, elevation_m=50,
            vegetation=.4, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="dry",
        )
        m_risk = assess(monsoon_loc, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        d_risk = assess(dry_loc, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        self.assertGreater(m_risk.hazard_score, d_risk.hazard_score)

    def test_summer_increases_wildfire_risk(self):
        summer_loc = LocationProfile(
            name="S", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=.7, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="summer",
        )
        winter_loc = LocationProfile(
            name="W", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=.7, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="winter",
        )
        s_risk = assess(summer_loc, Scenario(DisasterType.WILDFIRE, 6, 24, 0.5))
        w_risk = assess(winter_loc, Scenario(DisasterType.WILDFIRE, 6, 24, 0.5))
        self.assertGreater(s_risk.hazard_score, w_risk.hazard_score)

    # --- Auto weight suggestion ---
    def test_suggest_weights_sums_to_one(self):
        for disaster in DisasterType:
            for season in ("dry", "monsoon", "winter", "summer", "mixed"):
                w_h, w_e, w_v = _suggest_weights(disaster, self.base_location, season)
                total = w_h + w_e + w_v
                self.assertAlmostEqual(total, 1.0, places=2)

    def test_flood_low_elevation_increases_vulnerability_weight(self):
        low_loc = LocationProfile(
            name="Low", longitude=73.0, latitude=18.5, elevation_m=10,
            vegetation=.4, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="mixed",
        )
        high_loc = LocationProfile(
            name="High", longitude=73.0, latitude=18.5, elevation_m=600,
            vegetation=.4, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=.6, roof_type_score=.6, time_of_day=12, season="mixed",
        )
        _, w_e_low, w_v_low = _suggest_weights(DisasterType.FLOOD, low_loc, "mixed")
        _, w_e_high, w_v_high = _suggest_weights(DisasterType.FLOOD, high_loc, "mixed")
        self.assertGreaterEqual(w_v_low, w_v_high)

    def test_poor_building_quality_increases_earthquake_vulnerability(self):
        poor_loc = LocationProfile(
            name="Poor", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=.4, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=0.1, roof_type_score=.6, time_of_day=12, season="mixed",
        )
        good_loc = LocationProfile(
            name="Good", longitude=73.0, latitude=18.5, elevation_m=300,
            vegetation=.4, population_density=.5, soil_softness=.4, water_distance=.5,
            income_level=.5, literacy_rate=.75, elderly_share=.1, child_share=.15,
            disability_share=.05, hospital_capacity=.5, fire_station_proximity=.5,
            shelter_capacity=.5, road_density=.5, informal_settlement=.1,
            building_quality=0.9, roof_type_score=.6, time_of_day=12, season="mixed",
        )
        _, _, w_v_poor = _suggest_weights(DisasterType.EARTHQUAKE, poor_loc, "mixed")
        _, _, w_v_good = _suggest_weights(DisasterType.EARTHQUAKE, good_loc, "mixed")
        self.assertGreaterEqual(w_v_poor, w_v_good)

    # --- Assessment has all required fields ---
    def test_assessment_has_confidence_and_factors(self):
        result = assess(self.base_location, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        self.assertIsNotNone(result.confidence_lower)
        self.assertIsNotNone(result.confidence_upper)
        self.assertGreaterEqual(result.mc_samples, 100)
        self.assertIsNotNone(result.hazard_factors)
        self.assertIsNotNone(result.vulnerability_factors)
        self.assertIsInstance(result.recommendations, tuple)
        self.assertGreater(len(result.recommendations), 0)

    # --- MIT-WPU Kothrud specific ---
    def test_mitwpu_location_valid(self):
        mitwpu = LocationProfile(
            name="MIT-WPU Kothrud",
            longitude=73.8203,
            latitude=18.5087,
            elevation_m=575,
            vegetation=0.30,
            population_density=0.85,
            soil_softness=0.45,
            water_distance=0.60,
            income_level=0.75,
            literacy_rate=0.90,
            elderly_share=0.08,
            child_share=0.10,
            disability_share=0.03,
            hospital_capacity=0.70,
            fire_station_proximity=0.60,
            shelter_capacity=0.50,
            road_density=0.70,
            informal_settlement=0.05,
            building_quality=0.85,
            roof_type_score=0.80,
            time_of_day=12,
            season="mixed",
        )
        self.assertAlmostEqual(mitwpu.longitude, 73.8203)
        self.assertAlmostEqual(mitwpu.latitude, 18.5087)
        self.assertEqual(mitwpu.elevation_m, 575)
        result = assess(mitwpu, Scenario(DisasterType.FLOOD, 6, 24, 0.5))
        self.assertGreaterEqual(result.overall_score, 0)
        self.assertLessEqual(result.overall_score, 100)


if __name__ == "__main__":
    unittest.main()
