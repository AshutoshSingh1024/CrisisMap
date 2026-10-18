import unittest

from crisismap.models import DisasterType, LocationProfile, RiskLevel, Scenario
from crisismap.simulation import assess, classify_risk


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.location = LocationProfile(
            name="Test Ward",
            longitude=72.88,
            latitude=19.05,
            elevation_m=12,
            vegetation=.7,
            population_density=.8,
            soil_softness=.6,
            water_distance=.1,
        )

    def test_classification_boundaries(self):
        self.assertEqual(classify_risk(0), RiskLevel.LOW)
        self.assertEqual(classify_risk(25), RiskLevel.MODERATE)
        self.assertEqual(classify_risk(50), RiskLevel.HIGH)
        self.assertEqual(classify_risk(75), RiskLevel.EXTREME)

    def test_assessment_is_bounded_and_explained(self):
        result = assess(self.location, Scenario(DisasterType.FLOOD, 8, 36, .3))
        self.assertGreaterEqual(result.overall_score, 0)
        self.assertLessEqual(result.overall_score, 100)
        self.assertIn("Test Ward", result.summary)
        self.assertEqual(len(result.recommendations), 2)

    def test_higher_intensity_increases_flood_risk(self):
        low = assess(self.location, Scenario(DisasterType.FLOOD, 2, 12, .5))
        high = assess(self.location, Scenario(DisasterType.FLOOD, 9, 12, .5))
        self.assertGreater(high.overall_score, low.overall_score)

    def test_preparedness_reduces_vulnerability(self):
        weak = assess(self.location, Scenario(DisasterType.EARTHQUAKE, 7, 2, .1))
        strong = assess(self.location, Scenario(DisasterType.EARTHQUAKE, 7, 2, .9))
        self.assertLess(strong.vulnerability_score, weak.vulnerability_score)

    def test_invalid_scenario_is_rejected(self):
        with self.assertRaises(ValueError):
            Scenario(DisasterType.WILDFIRE, 11, 10, .5)


if __name__ == "__main__":
    unittest.main()
