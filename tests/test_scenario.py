import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eod import scenario
from tests.helpers import FIXTURES, REPO


class DataDirTests(unittest.TestCase):
    def test_default_is_data_next_to_the_code_not_the_current_folder(self):
        environment = {k: v for k, v in os.environ.items() if k != "EOD_DATA_DIR"}
        with mock.patch.dict(os.environ, environment, clear=True):
            self.assertEqual(scenario.data_dir(), REPO / "data")

    def test_env_var_overrides(self):
        with mock.patch.dict(os.environ, {"EOD_DATA_DIR": "/some/where"}):
            self.assertEqual(scenario.data_dir(), Path("/some/where"))


class AtRiskTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"EOD_DATA_DIR": str(FIXTURES)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.data = scenario.load_scenario()

    def names(self, release_m3s):
        return [town["name"] for town in scenario.at_risk_towns(self.data, release_m3s)]

    def test_exactly_at_threshold_is_at_risk(self):
        self.assertEqual(self.names(300), ["Alpha"])

    def test_just_below_threshold_is_not_at_risk(self):
        self.assertEqual(self.names(299), [])

    def test_demand_sums_evacuees_of_at_risk_towns(self):
        self.assertEqual(scenario.demand_for(self.data, 600), 300)
        self.assertEqual(scenario.demand_for(self.data, 900), 700)

    def test_unknown_stage_is_an_error(self):
        with self.assertRaises(scenario.EodError):
            scenario.find_stage(self.data, 99)

    def test_unknown_release_is_an_error(self):
        with self.assertRaises(scenario.EodError):
            scenario.find_release(self.data, 1, "R9")

    def test_release_from_another_stage_is_an_error(self):
        with self.assertRaises(scenario.EodError):
            scenario.find_release(self.data, 1, "R3")


if __name__ == "__main__":
    unittest.main()
