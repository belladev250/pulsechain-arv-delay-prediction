"""Unit tests for calibration, risk bands and the fallback score, without loading any model file."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from services.risk_model import RiskModel, heuristic_probability  # noqa: E402


def bare_model(calibration=None, high=0.5, medium=0.3):
    """A RiskModel with no files loaded, so tests control every input."""
    model = RiskModel.__new__(RiskModel)
    model.calibration = calibration
    model.high_threshold, model.medium_threshold = high, medium
    return model


class CalibrationTests(unittest.TestCase):
    CAL = {"x": [0.0, 0.5, 1.0], "y": [0.0, 0.2, 0.9]}

    def test_without_calibration_the_score_is_unchanged(self):
        self.assertEqual(bare_model().calibrate(0.37), 0.37)

    def test_interpolates_between_points(self):
        self.assertAlmostEqual(bare_model(self.CAL).calibrate(0.25), 0.10, places=6)

    def test_displayed_probability_is_capped_at_50_percent(self):
        self.assertEqual(bare_model(self.CAL).calibrate(1.0), 0.50)

    def test_displayed_probability_has_a_floor_of_2_percent(self):
        self.assertEqual(bare_model(self.CAL).calibrate(0.0), 0.02)


class RiskBandTests(unittest.TestCase):
    def test_bands_follow_the_thresholds(self):
        model = bare_model(high=0.6, medium=0.3)
        self.assertEqual(model.band_for(0.75), "high")
        self.assertEqual(model.band_for(0.6), "high")
        self.assertEqual(model.band_for(0.45), "medium")
        self.assertEqual(model.band_for(0.1), "low")


class FallbackScoreTests(unittest.TestCase):
    def test_score_rises_with_vendor_and_country_history(self):
        self.assertGreater(heuristic_probability(0.4, 0.3, "Air"), heuristic_probability(0.1, 0.1, "Air"))

    def test_truck_adds_risk(self):
        self.assertGreater(heuristic_probability(0.2, 0.2, "Truck"), heuristic_probability(0.2, 0.2, "Air"))

    def test_score_never_exceeds_95_percent(self):
        self.assertLessEqual(heuristic_probability(5.0, 5.0, "Truck"), 0.95)


if __name__ == "__main__":
    unittest.main()
