"""Run each read-only command as a real subprocess from its own desk folder."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.helpers import FIXTURES, REPO, copy_fixture_data, json_output, make_clone, run_script

RESERVOIR = REPO / "desks" / "reservoir"
FIELD = REPO / "desks" / "field"


class InflowTests(unittest.TestCase):
    def test_returns_the_stage(self):
        result = run_script(RESERVOIR, "inflow.py", "--stage", 1)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json_output(result)
        self.assertEqual(output["inflow_m3s"], 500)
        self.assertEqual(output["level_m"], 80)
        self.assertEqual(output["releases"][1], {"id": "R1", "release_m3s": 300})
        self.assertIs(output["synthetic"], True)

    def test_unknown_stage_exits_2(self):
        self.assertEqual(run_script(RESERVOIR, "inflow.py", "--stage", 99).returncode, 2)

    def test_non_number_stage_exits_2(self):
        self.assertEqual(run_script(RESERVOIR, "inflow.py", "--stage", "x").returncode, 2)


class TownsTests(unittest.TestCase):
    def test_returns_towns_demand_and_release(self):
        result = run_script(FIELD, "towns.py", "--release-id", "R2", "--stage", 1)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json_output(result)
        self.assertEqual(output["towns"], ["Alpha", "Bravo"])
        self.assertEqual(output["demand"], 300)
        self.assertEqual(output["release_m3s"], 600)
        self.assertIs(output["synthetic"], True)

    def test_exactly_at_threshold_through_the_command(self):
        output = json_output(run_script(FIELD, "towns.py", "--release-id", "R1", "--stage", 1))
        self.assertEqual(output["towns"], ["Alpha"])

    def test_unknown_release_exits_2(self):
        result = run_script(FIELD, "towns.py", "--release-id", "R9", "--stage", 1)
        self.assertEqual(result.returncode, 2)


class ReadinessTests(unittest.TestCase):
    def test_returns_staff_and_boats(self):
        result = run_script(FIELD, "readiness.py", "--towns", "Alpha, Bravo")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json_output(result)
        self.assertEqual(output["towns"], [
            {"name": "Alpha", "staff": 4, "boats": 1},
            {"name": "Bravo", "staff": 6, "boats": 2},
        ])
        self.assertIs(output["synthetic"], True)

    def test_unknown_town_exits_2(self):
        self.assertEqual(run_script(FIELD, "readiness.py", "--towns", "Alpha,Nowhere").returncode, 2)

    def test_empty_list_exits_2(self):
        self.assertEqual(run_script(FIELD, "readiness.py", "--towns", " , ").returncode, 2)


class CheckSiteCommandTests(unittest.TestCase):
    def run_check(self, site, release, stage):
        return run_script(FIELD, "check_site.py", "--site", site, "--release-id", release, "--stage", stage)

    def test_failing_site_is_a_normal_result(self):
        result = self.run_check("A", "R1", 1)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json_output(result)
        self.assertEqual(output["site"], "A")
        self.assertEqual(output["status"], "fail")
        self.assertEqual(output["demand"], 100)
        self.assertIs(output["synthetic"], True)

    def test_passing_site(self):
        output = json_output(self.run_check("C", "R2", 1))
        self.assertEqual(output["status"], "pass")

    def test_unknown_site_exits_2(self):
        self.assertEqual(self.run_check("Z", "R1", 1).returncode, 2)

    def test_unknown_release_exits_2(self):
        self.assertEqual(self.run_check("C", "R9", 1).returncode, 2)

    def test_output_never_says_safe_or_names_a_building(self):
        for site in "ABCDEF":
            result = self.run_check(site, "R2", 1)
            self.assertNotIn("safe", result.stdout.lower())
            self.assertNotIn("BUILDING", result.stdout)


class DefaultDataFolderTests(unittest.TestCase):
    def test_finds_data_next_to_the_code_from_the_desk_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            clone = make_clone(Path(folder) / "clone")
            copy_fixture_data(clone / "data")
            result = run_script(clone / "desks" / "reservoir", "inflow.py", "--stage", 1, data_dir=None)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json_output(result)["inflow_m3s"], 500)

    def test_missing_data_exits_2_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            clone = make_clone(Path(folder) / "clone")
            result = run_script(clone / "desks" / "reservoir", "inflow.py", "--stage", 1, data_dir=None)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)


class BadScenarioTests(unittest.TestCase):
    def test_scenario_missing_a_town_field_exits_2_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            data = copy_fixture_data(folder)
            scenario = json.loads((data / "scenario.json").read_text())
            del scenario["towns"][0]["evacuees"]
            (data / "scenario.json").write_text(json.dumps(scenario))
            result = run_script(FIELD, "towns.py", "--release-id", "R1", "--stage", 1, data_dir=data)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
