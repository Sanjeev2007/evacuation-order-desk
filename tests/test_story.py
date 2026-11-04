"""The full demo story, run offline as commands from each desk's folder, on the real data.

Each test gets a throwaway copy of the code and of the real data/ files, with no
EOD_DATA_DIR set, so the scripts find their data the way they do for an agent and
every draft, order and record lands in the temporary folder.

Each step can run alone: a helper replays the earlier steps as real commands. Values
in drafts come from the scripts' own output, not from this file. The expected values
below come from the scenario brief, so a change to data/ makes these tests fail.
"""
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.helpers import BOOKEND, OFFICE, REPO, json_output, make_clone, run_script

R1_TOWNS = ["Montroi", "Alfarb", "Carlet"]
R2_TOWNS = ["Montroi", "Alfarb", "Carlet", "l'Alcúdia", "Algemesí"]
R1_DEMAND = 1830
R2_DEMAND = 3950
IN_LAYER_A = "Site A is inside the saved 100-year layer, not cleared for this drill"
UNDER_CAPACITY_B = f"Site B capacity 2200 is below demand {R2_DEMAND} in this synthetic drill, not cleared"


class StoryTestCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        clone = make_clone(Path(folder.name) / "clone")
        shutil.copytree(REPO / "data", clone / "data")
        self.reservoir = clone / "desks" / "reservoir"
        self.field = clone / "desks" / "field"
        self.writer = clone / "desks" / "writer"
        self.record = clone / "desks" / "record"
        (self.writer / "drafts").mkdir()
        self.orders = self.writer / "orders"
        self.records = self.record / "records"

    # Running the commands

    def read_command(self, desk, script, *args):
        """Run a read-only script that must succeed, and return its JSON."""
        result = run_script(desk, script, *args, data_dir=None)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = json_output(result)
        self.assertIs(output["synthetic"], True)
        return output

    def towns(self, release_id, stage):
        return self.read_command(self.field, "towns.py", "--release-id", release_id, "--stage", stage)

    def readiness(self, towns):
        output = self.read_command(self.field, "readiness.py", "--towns", ",".join(towns))
        return {town["name"]: (town["staff"], town["boats"]) for town in output["towns"]}

    def try_sites(self, sites, stage, release_id):
        """Check sites in the order given and stop at the first pass, as the writer does."""
        results = []
        for site in sites:
            result = self.read_command(self.field, "check_site.py", "--site", site,
                                       "--release-id", release_id, "--stage", stage)
            results.append(result)
            if result["status"] == "pass":
                break
        return results

    def save_draft(self, name, draft):
        path = self.writer / "drafts" / name
        path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
        return path

    def check(self, name):
        return run_script(self.writer, "check_draft.py", f"drafts/{name}", data_dir=None)

    def issue(self, name, sha):
        return run_script(self.writer, "issue_order.py", f"drafts/{name}", "--sha", sha, data_dir=None)

    def write_record(self, notes):
        (self.record / "notes.json").write_text(json.dumps(notes), encoding="utf-8")
        return run_script(self.record, "write_record.py", "--input", "notes.json", data_dir=None)

    # Building the story's drafts from the scripts' output

    def draft_for(self, package_id, stage, release_id, site, **extra):
        towns = self.towns(release_id, stage)
        draft = {
            "drill": True,
            "package_id": package_id,
            "stage": stage,
            "release_id": release_id,
            "release_m3s": towns["release_m3s"],
            "towns": towns["towns"],
            "site_id": site,
            "text_en": f"DRILL: people in {', '.join(towns['towns'])} move to Site {site}.",
            "text_es": f"SIMULACRO: evacuación de {', '.join(towns['towns'])} hacia el Sitio {site}.",
            "issuing_office": OFFICE,
        }
        draft.update(extra)
        return draft

    def order_1_draft(self):
        return self.draft_for("P1", 1, "R1", self.try_sites(["A", "B", "C"], 1, "R1")[-1]["site"])

    def order_2_draft(self):
        return self.draft_for("P2", 2, "R2", self.try_sites(["B", "C"], 2, "R2")[-1]["site"], replaces="P1")

    def pass_lock_1(self, name, draft):
        path = self.save_draft(name, draft)
        result = self.check(name)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        match = re.fullmatch(r"PASS sha256=([0-9a-f]{64})\n", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        self.assertEqual(match.group(1), hashlib.sha256(path.read_bytes()).hexdigest())
        return match.group(1)

    def issue_through_both_locks(self, name, draft):
        sha = self.pass_lock_1(name, draft)
        result = self.issue(name, sha)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = json_output(result)
        self.assertEqual(output["order_file"], f"orders/order-{draft['package_id']}.md")
        self.assertEqual(output["sha256"], sha)
        return sha

    def record_notes(self, sha):
        return {
            "package_id": "P1",
            "order_file": "desks/writer/orders/order-P1.md",
            "entries": [
                {"time": "10:02", "who": "site checker", "decision": "Site A rejected, Site B cleared",
                 "why": "check_site.py results for R1", "source": "Field room message 14"},
                {"time": "10:09", "who": "duty officer", "decision": f"Order P1 approved, draft sha256 {sha}",
                 "why": "Full draft and hash read in chat", "source": "Decision room card A1"},
            ],
        }

    # Reading the results

    def order_files(self):
        return sorted(path.name for path in self.orders.glob("*")) if self.orders.exists() else []

    def record_files(self):
        return sorted(path.name for path in self.records.glob("*")) if self.records.exists() else []

    def order_lines(self, package_id):
        return (self.orders / f"order-{package_id}.md").read_text(encoding="utf-8").splitlines()

    def assert_blocked(self, result, expected_line):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], "BLOCKED")
        self.assertIn(expected_line, lines[1:])
        self.assertNotIn("sha256=", result.stdout)

    def assert_order_says(self, package_id, sha, expected_lines, towns):
        lines = self.order_lines(package_id)
        self.assertEqual(lines[0], BOOKEND)
        self.assertEqual(lines[-1], BOOKEND)
        self.assertIn(f"Issuing office: {OFFICE}", lines)
        self.assertIn(f"Draft sha256: {sha}", lines)
        for line in expected_lines:
            self.assertIn(line, lines)
        town_line = next(line for line in lines if line.startswith("Towns: "))
        self.assertEqual(set(town_line[len("Towns: "):].split(", ")), set(towns))


class ScenarioValueTests(StoryTestCase):
    def test_0_the_real_data_holds_the_brief_values(self):
        scenario = json.loads((REPO / "data" / "scenario.json").read_text(encoding="utf-8"))
        self.assertEqual({site: scenario["sites"][site]["capacity"] for site in scenario["sites"]},
                         {"A": 2600, "B": 2200, "C": 4400})

    def test_0_the_staged_down_release_puts_only_montroi_at_risk(self):
        output = self.towns("R1-S", 1)
        self.assertEqual(output["release_m3s"], 180)
        self.assertEqual(output["towns"], ["Montroi"])
        self.assertEqual(output["demand"], 420)


class ReservoirStep(StoryTestCase):
    def test_1_inflow_by_stage_offers_release_r1(self):
        stage_1 = self.read_command(self.reservoir, "inflow.py", "--stage", 1)
        self.assertEqual(stage_1["inflow_m3s"], 420)
        self.assertEqual(stage_1["level_m"], 61.5)
        self.assertEqual(stage_1["releases"], [{"id": "R1", "release_m3s": 300}, {"id": "R1-S", "release_m3s": 180}])

    def test_1_inflow_rises_at_stage_2_and_offers_r2(self):
        stage_2 = self.read_command(self.reservoir, "inflow.py", "--stage", 2)
        self.assertEqual(stage_2["inflow_m3s"], 640)
        self.assertEqual(stage_2["level_m"], 64.8)
        self.assertEqual(stage_2["releases"], [{"id": "R2", "release_m3s": 480}])


class FieldStep(StoryTestCase):
    def test_2_towns_at_risk_for_r1(self):
        output = self.towns("R1", 1)
        self.assertEqual(output["release_m3s"], 300)
        self.assertEqual(output["towns"], R1_TOWNS)
        self.assertEqual(output["demand"], R1_DEMAND)

    def test_2_readiness_for_the_r1_towns(self):
        self.assertEqual(self.readiness(self.towns("R1", 1)["towns"]),
                         {"Montroi": (14, 2), "Alfarb": (9, 1), "Carlet": (32, 6)})

    def test_2_site_search_rejects_a_passes_b_and_stops(self):
        results = self.try_sites(["A", "B", "C"], 1, "R1")
        self.assertEqual([(result["site"], result["status"]) for result in results], [("A", "fail"), ("B", "pass")])
        self.assertEqual(results[0]["reasons"], [IN_LAYER_A])
        self.assertEqual(results[1]["reasons"], ["Site B cleared for this drill against synthetic data only"])
        self.assertEqual({result["demand"] for result in results}, {R1_DEMAND})


class WriterStep(StoryTestCase):
    def test_3_draft_missing_a_required_field_is_blocked(self):
        draft = self.order_1_draft()
        del draft["text_es"]
        self.save_draft("P1.json", draft)
        self.assert_blocked(self.check("P1.json"), "text_es is missing or empty")
        self.assertEqual(self.order_files(), [])

    def test_3_draft_claiming_a_failed_site_passed_is_blocked(self):
        draft = self.draft_for("P1", 1, "R1", "A", site_passed=True,
                               site_check={"status": "pass", "reasons": ["Site A cleared"]})
        self.save_draft("P1.json", draft)
        self.assert_blocked(self.check("P1.json"), IN_LAYER_A)
        self.assertEqual(self.order_files(), [])

    def test_3_complete_draft_gets_pass_and_its_hash_and_no_order_yet(self):
        self.pass_lock_1("P1.json", self.order_1_draft())
        self.assertEqual(self.order_files(), [])

    def test_3_edit_after_the_check_is_refused(self):
        draft = self.order_1_draft()
        sha = self.pass_lock_1("P1.json", draft)
        self.save_draft("P1.json", {**draft, "text_en": "DRILL: a quietly different message."})
        result = self.issue("P1.json", sha)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], "REFUSED")
        self.assertIn("draft changed after the check", result.stdout)
        self.assertEqual(self.order_files(), [])

    def test_3_correct_hash_writes_the_order(self):
        draft = self.order_1_draft()
        sha = self.issue_through_both_locks("P1.json", draft)
        self.assertEqual(self.order_files(), ["order-P1.md"])
        self.assert_order_says("P1", sha, ["Package: P1", "Stage: 1", "Release: R1, 300 m3/s (synthetic)",
                                           "Site: Site B", draft["text_en"], draft["text_es"]], R1_TOWNS)
        self.assertFalse(any(line.startswith("Replaces:") for line in self.order_lines("P1")))


class RecordStep(StoryTestCase):
    def test_4_record_is_written_for_the_order(self):
        sha = self.issue_through_both_locks("P1.json", self.order_1_draft())
        notes = self.record_notes(sha)
        result = self.write_record(notes)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json_output(result)["record_file"], "records/record-P1.md")
        lines = (self.records / "record-P1.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "# DRILL record. Synthetic scenario. Nothing was sent.")
        self.assertIn("Package: P1", lines)
        self.assertIn(f"Order file: {notes['order_file']}", lines)
        for entry in notes["entries"]:
            self.assertIn(f"| {entry['time']} | {entry['who']} | {entry['decision']} | {entry['why']} | {entry['source']} |", lines)


class TwistStep(StoryTestCase):
    def test_5_r2_adds_towns(self):
        output = self.towns("R2", 2)
        self.assertEqual(output["release_m3s"], 480)
        self.assertEqual(output["towns"], R2_TOWNS)
        self.assertEqual(output["demand"], R2_DEMAND)
        self.assertEqual(self.readiness(output["towns"]),
                         {"Montroi": (14, 2), "Alfarb": (9, 1), "Carlet": (32, 6),
                          "l'Alcúdia": (21, 4), "Algemesí": (38, 8)})

    def test_5_b_now_fails_on_capacity_and_c_passes(self):
        results = self.try_sites(["B", "C"], 2, "R2")
        self.assertEqual([(result["site"], result["status"]) for result in results], [("B", "fail"), ("C", "pass")])
        self.assertEqual(results[0]["reasons"], [UNDER_CAPACITY_B])
        self.assertEqual(results[1]["reasons"], ["Site C cleared for this drill against synthetic data only"])
        self.assertEqual({result["demand"] for result in results}, {R2_DEMAND})

    def test_5_site_a_stays_rejected_under_r2(self):
        result = self.try_sites(["A"], 2, "R2")[0]
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["reasons"], [IN_LAYER_A, f"Site A capacity 2600 is below demand {R2_DEMAND} in this synthetic drill, not cleared"])

    def test_5_keeping_site_b_for_r2_is_blocked(self):
        self.issue_through_both_locks("P1.json", self.order_1_draft())
        self.save_draft("P2.json", self.draft_for("P2", 2, "R2", "B", replaces="P1"))
        self.assert_blocked(self.check("P2.json"), UNDER_CAPACITY_B)
        self.assertEqual(self.order_files(), ["order-P1.md"])

    def test_5_order_2_goes_through_both_locks_and_names_order_1_as_replaced(self):
        self.issue_through_both_locks("P1.json", self.order_1_draft())
        order_1_before = (self.orders / "order-P1.md").read_bytes()
        draft = self.order_2_draft()
        sha = self.issue_through_both_locks("P2.json", draft)
        self.assertEqual(self.order_files(), ["order-P1.md", "order-P2.md"])
        self.assert_order_says("P2", sha, ["Package: P2", "Stage: 2", "Release: R2, 480 m3/s (synthetic)",
                                           "Site: Site C", "Replaces: P1", draft["text_en"], draft["text_es"]], R2_TOWNS)
        self.assertEqual((self.orders / "order-P1.md").read_bytes(), order_1_before)

    def test_5_order_2_cannot_replace_an_order_that_was_never_issued(self):
        self.save_draft("P2.json", self.order_2_draft())
        self.assert_blocked(self.check("P2.json"), "replaces names order-P1.md, which does not exist in orders/")
        self.assertEqual(self.order_files(), [])


class WholeStory(StoryTestCase):
    def test_6_the_story_runs_start_to_finish_in_one_clone(self):
        # Reservoir
        stage_1 = self.read_command(self.reservoir, "inflow.py", "--stage", 1)
        self.assertIn({"id": "R1", "release_m3s": 300}, stage_1["releases"])

        # Field
        towns = self.towns("R1", 1)
        self.assertEqual(self.readiness(towns["towns"]).keys(), set(R1_TOWNS))
        sites = self.try_sites(["A", "B", "C"], 1, "R1")
        self.assertEqual([result["site"] for result in sites], ["A", "B"])

        # Writer: blocked twice on the same draft file, then a clean check, edit and issue
        good = self.draft_for("P1", 1, "R1", sites[-1]["site"])
        incomplete = {field: value for field, value in good.items() if field != "issuing_office"}
        self.save_draft("P1.json", incomplete)
        self.assert_blocked(self.check("P1.json"), "issuing_office is missing or empty")
        self.save_draft("P1.json", {**good, "site_id": "A", "site_passed": True})
        self.assert_blocked(self.check("P1.json"), IN_LAYER_A)
        sha = self.pass_lock_1("P1.json", good)
        self.save_draft("P1.json", {**good, "text_es": "SIMULACRO: otro mensaje."})
        self.assertEqual(self.issue("P1.json", sha).returncode, 1)
        self.assertEqual(self.order_files(), [])
        self.save_draft("P1.json", good)
        self.assertEqual(self.issue("P1.json", sha).returncode, 0)

        # Record
        self.assertEqual(self.write_record(self.record_notes(sha)).returncode, 0)

        # Twist
        stage_2 = self.read_command(self.reservoir, "inflow.py", "--stage", 2)
        self.assertGreater(stage_2["inflow_m3s"], stage_1["inflow_m3s"])
        self.issue_through_both_locks("P2.json", self.order_2_draft())
        self.assertIn("Replaces: P1", self.order_lines("P2"))

        self.assertEqual(self.order_files(), ["order-P1.md", "order-P2.md"])
        self.assertEqual(self.record_files(), ["record-P1.md"])


if __name__ == "__main__":
    unittest.main()
