"""Unit tests for the plain-language explanation wording."""
import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from services.explanations import clean_name, plain_reason  # noqa: E402


class ExplanationTests(unittest.TestCase):
    ROW = pd.Series({"vendor_recent_late_rate": 0.25, "country_recent_late_rate": 0.10,
                     "global_recent_late_rate": 0.17, "weight_kg": None})

    def test_prefixes_and_underscores_are_cleaned(self):
        self.assertEqual(clean_name("num__vendor_recent_late_rate"), "vendor recent late rate")
        self.assertEqual(clean_name("cat__Country_Rwanda"), "Country Rwanda")

    def test_vendor_rate_is_shown_as_a_percentage(self):
        text = plain_reason("num__vendor_recent_late_rate", self.ROW, "raises risk")
        self.assertIn("25%", text)
        self.assertIn("raises", text)

    def test_direction_changes_the_verb(self):
        self.assertIn("lowers", plain_reason("country_recent_late_rate", self.ROW, "lowers risk"))

    def test_missing_value_has_a_safe_message(self):
        self.assertIn("missing", plain_reason("weight_kg", self.ROW, "raises risk").lower())

    def test_categorical_feature_names_the_category(self):
        text = plain_reason("cat__Shipment Mode_Air", self.ROW, "raises risk")
        self.assertIn("Shipment Mode: Air", text)


if __name__ == "__main__":
    unittest.main()
