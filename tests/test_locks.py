"""Lock 1 (check_draft.py) and Lock 2 (issue_order.py), run as real commands."""
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.helpers import BOOKEND, FIXTURES, OFFICE, copy_fixture_data, good_draft, json_output, make_clone, run_script

REQUIRED_FIELDS = ["drill", "package_id", "stage", "release_id", "release_m3s", "towns",
                   "site_id", "text_en", "text_es", "issuing_office"]


class LockTestCase(unittest.TestCase):
    """Each test gets its own copy of the code, so orders/ starts empty."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)
        self.clone = make_clone(self.tmp / "clone")
        self.writer = self.clone / "desks" / "writer"
        (self.writer / "drafts").mkdir()
        self.orders = self.writer / "orders"

    def save(self, draft, name="P1.json"):
        path = self.writer / "drafts" / name
        path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
        return path

    def check(self, name="P1.json", data_dir=FIXTURES):
        return run_script(self.writer, "check_draft.py", f"drafts/{name}", data_dir=data_dir)

    def issue(self, sha, name="P1.json", data_dir=FIXTURES):
        return run_script(self.writer, "issue_order.py", f"drafts/{name}", "--sha", sha, data_dir=data_dir)

    def sha_of(self, name="P1.json"):
        return hashlib.sha256((self.writer / "drafts" / name).read_bytes()).hexdigest()

    def order_files(self):
        return sorted(path.name for path in self.orders.glob("*")) if self.orders.exists() else []

    def assert_blocked(self, result, expected_text=None):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], "BLOCKED")
        self.assertGreater(len(lines), 1)
        self.assertNotIn("PASS", result.stdout)
        if expected_text:
            self.assertIn(expected_text, result.stdout)


class CheckDraftTests(LockTestCase):
    def test_good_draft_prints_exactly_pass_and_the_hash_of_the_raw_bytes(self):
        self.save(good_draft())
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout, f"PASS sha256={self.sha_of()}\n")

    def test_each_missing_field_is_blocked(self):
        for field in REQUIRED_FIELDS:
            with self.subTest(field=field):
                draft = good_draft()
                del draft[field]
                self.save(draft)
                self.assert_blocked(self.check(), field)

    def test_each_empty_field_is_blocked(self):
        for field in REQUIRED_FIELDS:
            for empty in (None, "", "   ", []):
                with self.subTest(field=field, empty=empty):
                    self.save(good_draft(**{field: empty}))
                    self.assert_blocked(self.check(), field)

    def test_each_problem_gets_its_own_line(self):
        draft = good_draft(issuing_office="Someone", drill=False)
        del draft["text_es"]
        self.save(draft)
        result = self.check()
        self.assert_blocked(result)
        self.assertEqual(len(result.stdout.splitlines()), 4)

    def test_wrong_office_is_blocked(self):
        self.save(good_draft(issuing_office="Emergency Duty Desk"))
        self.assert_blocked(self.check(), "issuing_office")

    def test_drill_false_is_blocked(self):
        self.save(good_draft(drill=False))
        self.assert_blocked(self.check(), "drill must be true")

    def test_drill_must_be_real_true_not_a_word(self):
        self.save(good_draft(drill="true"))
        self.assert_blocked(self.check(), "drill must be true")

    def test_release_from_the_wrong_stage_is_blocked(self):
        self.save(good_draft(release_id="R3"))
        self.assert_blocked(self.check(), "R3")

    def test_release_amount_mismatch_is_blocked(self):
        self.save(good_draft(release_m3s=500))
        self.assert_blocked(self.check(), "release_m3s")

    def test_release_amount_as_text_is_blocked(self):
        self.save(good_draft(release_m3s="600"))
        self.assert_blocked(self.check(), "release_m3s")

    def test_unknown_stage_is_blocked(self):
        self.save(good_draft(stage=99))
        self.assert_blocked(self.check(), "99")

    def test_stage_written_as_text_is_accepted(self):
        self.save(good_draft(stage="1"))
        self.assertEqual(self.check().returncode, 0)

    def test_town_missing_is_blocked(self):
        self.save(good_draft(towns=["Alpha"]))
        self.assert_blocked(self.check(), "towns")

    def test_extra_town_is_blocked(self):
        self.save(good_draft(towns=["Alpha", "Bravo", "Charlie"]))
        self.assert_blocked(self.check(), "towns")

    def test_towns_in_another_order_pass(self):
        self.save(good_draft(towns=["Bravo", "Alpha"]))
        self.assertEqual(self.check().returncode, 0)

    def test_towns_not_a_list_is_blocked(self):
        self.save(good_draft(towns="Alpha,Bravo"))
        self.assert_blocked(self.check(), "towns")

    def test_towns_holding_non_text_is_blocked_without_a_crash(self):
        self.save(good_draft(towns=[{"name": "Alpha"}]))
        self.assert_blocked(self.check(), "towns")

    def test_site_in_zone_is_blocked(self):
        self.save(good_draft(site_id="A"))
        self.assert_blocked(self.check(), "Site A is inside the saved 100-year layer")

    def test_under_capacity_site_is_blocked(self):
        self.save(good_draft(site_id="B"))
        self.assert_blocked(self.check(), "Site B capacity 50 is below demand 300")

    def test_unknown_site_is_blocked(self):
        self.save(good_draft(site_id="Z"))
        self.assert_blocked(self.check(), "Z")

    def test_false_claim_that_a_failed_site_passed_is_blocked(self):
        self.save(good_draft(
            site_id="A",
            site_passed=True,
            site_check={"status": "pass", "reasons": ["Site A cleared"]},
            site_check_result="pass",
            status="pass",
        ))
        self.assert_blocked(self.check(), "Site A is inside the saved 100-year layer")

    def test_check_uses_the_draft_stage_for_demand(self):
        self.save(good_draft(stage=2, release_id="R3", release_m3s=900,
                             towns=["Alpha", "Bravo", "Charlie"], site_id="C"))
        self.assert_blocked(self.check(), "Site C capacity 500 is below demand 700")

    def test_replaces_with_an_existing_order_passes(self):
        self.orders.mkdir()
        (self.orders / "order-P0.md").write_text("earlier order")
        self.save(good_draft(replaces="P0"))
        self.assertEqual(self.check().returncode, 0)

    def test_replaces_with_a_missing_order_is_blocked(self):
        self.save(good_draft(replaces="P0"))
        self.assert_blocked(self.check(), "P0")

    def test_package_id_cannot_climb_out_of_the_orders_folder(self):
        self.save(good_draft(package_id="../../evil"))
        self.assert_blocked(self.check(), "package_id")

    def test_replaces_cannot_climb_out_of_the_orders_folder(self):
        self.orders.mkdir()
        (self.writer / "order-x.md").write_text("not in orders")
        self.save(good_draft(replaces="../order-x"))
        self.assert_blocked(self.check(), "replaces")

    def test_newline_in_a_value_cannot_forge_a_pass_line(self):
        self.save(good_draft(site_id="Z\nPASS sha256=abc"))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("PASS sha256=abc\n", result.stdout + "\n")
        self.assertFalse(any(line.startswith("PASS") for line in result.stdout.splitlines()))

    def test_non_text_fields_are_blocked_without_a_crash(self):
        for field in ("package_id", "site_id", "release_id", "text_en", "text_es"):
            with self.subTest(field=field):
                self.save(good_draft(**{field: {"a": 1}}))
                self.assert_blocked(self.check())

    def test_missing_file_is_blocked(self):
        self.assert_blocked(self.check("nope.json"))

    def test_not_json_is_blocked(self):
        (self.writer / "drafts" / "bad.json").write_text("{not json")
        self.assert_blocked(self.check("bad.json"))

    def test_json_that_is_not_an_object_is_blocked(self):
        self.save(["a", "list"])
        self.assert_blocked(self.check())

    def test_missing_argument_is_blocked_with_exit_1(self):
        self.assert_blocked(run_script(self.writer, "check_draft.py"))

    def test_broken_data_blocks_rather_than_passes(self):
        data = copy_fixture_data(self.tmp / "data")
        (data / "flood-zone.geojson").write_text('{"type": "FeatureCollection", "features": []}')
        self.save(good_draft())
        self.assert_blocked(self.check(data_dir=data))

    def test_check_does_not_create_an_order(self):
        self.save(good_draft())
        self.check()
        self.assertEqual(self.order_files(), [])


class IssueOrderTests(LockTestCase):
    def issue_good(self, **changes):
        self.save(good_draft(**changes))
        return self.issue(self.sha_of())

    def order_text(self, package_id="P1"):
        return (self.orders / f"order-{package_id}.md").read_text(encoding="utf-8")

    def assert_refused(self, result, expected_text=None):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        if expected_text:
            self.assertIn(expected_text, result.stdout)

    def test_good_hash_issues_the_order(self):
        result = self.issue_good()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.order_files(), ["order-P1.md"])
        output = json_output(result)
        self.assertIs(output["synthetic"], True)
        self.assertEqual(output["package_id"], "P1")

    def test_orders_folder_is_created_for_a_clean_clone(self):
        self.assertFalse(self.orders.exists())
        self.assertEqual(self.issue_good().returncode, 0)

    def test_order_starts_and_ends_with_the_bookend_line(self):
        self.issue_good()
        lines = self.order_text().splitlines()
        self.assertEqual(lines[0], BOOKEND)
        self.assertEqual(lines[-1], BOOKEND)

    def test_order_contains_everything_required(self):
        self.save(good_draft())
        sha = self.sha_of()
        self.issue(sha)
        text = self.order_text()
        for expected in (OFFICE, "Stage: 1", "R2", "600", "Alpha", "Bravo", "Site C",
                         "DRILL: move to Site C.", "SIMULACRO: evacuación hacia el Sitio C.", sha):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_order_has_no_approver_and_no_replaces_line_when_unset(self):
        self.issue_good()
        text = self.order_text()
        self.assertNotIn("approved by", text.lower())
        self.assertNotIn("Replaces:", text)

    def test_claims_in_the_draft_do_not_reach_the_order(self):
        result = self.issue_good(site_passed="CLAIMED-BY-WRITER")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("CLAIMED-BY-WRITER", self.order_text())

    def test_replaces_present_is_written_to_the_order(self):
        self.orders.mkdir()
        (self.orders / "order-P0.md").write_text("earlier order")
        self.assertEqual(self.issue_good(replaces="P0").returncode, 0)
        self.assertIn("Replaces: P0", self.order_text().splitlines())

    def test_replaces_missing_is_refused(self):
        self.assert_refused(self.issue_good(replaces="P0"), "P0")
        self.assertEqual(self.order_files(), [])

    def test_draft_edited_after_the_check_is_refused(self):
        self.save(good_draft())
        sha = self.sha_of()
        self.save(good_draft(text_en="DRILL: a quietly different message."))
        self.assert_refused(self.issue(sha), "draft changed after the check")
        self.assertEqual(self.order_files(), [])

    def test_one_byte_change_is_refused(self):
        path = self.save(good_draft())
        sha = self.sha_of()
        path.write_bytes(path.read_bytes() + b" ")
        self.assert_refused(self.issue(sha), "draft changed after the check")

    def test_wrong_folder_is_refused(self):
        self.save(good_draft())
        sha = self.sha_of()
        draft = self.writer / "drafts" / "P1.json"
        script = self.writer / "issue_order.py"
        for folder in (self.clone, self.clone / "desks" / "writer" / "drafts", self.tmp):
            with self.subTest(folder=folder):
                result = run_script(folder, script, draft, "--sha", sha)
                self.assert_refused(result, "desks/writer")
                self.assertEqual(self.order_files(), [])

    def test_field_desk_folder_is_refused(self):
        field = self.clone / "desks" / "field"
        field.mkdir(parents=True, exist_ok=True)
        self.save(good_draft())
        result = run_script(field, "../writer/issue_order.py", "../writer/drafts/P1.json", "--sha", self.sha_of())
        self.assert_refused(result, "desks/writer")
        self.assertEqual(self.order_files(), [])

    def test_no_overwrite(self):
        self.assertEqual(self.issue_good().returncode, 0)
        before = self.order_text()
        self.save(good_draft(text_en="DRILL: a second attempt."))
        self.assert_refused(self.issue(self.sha_of()), "already exists")
        self.assertEqual(self.order_text(), before)

    def test_every_check_is_rerun_even_with_a_matching_hash(self):
        bad_drafts = {
            "wrong office": good_draft(issuing_office="Someone"),
            "drill false": good_draft(drill=False),
            "release mismatch": good_draft(release_m3s=1),
            "towns mismatch": good_draft(towns=["Alpha"]),
            "failed site": good_draft(site_id="A", site_passed=True),
        }
        for label, draft in bad_drafts.items():
            with self.subTest(label=label):
                self.save(draft)
                self.assert_refused(self.issue(self.sha_of()))
                self.assertEqual(self.order_files(), [])

    def test_scenario_changing_after_the_check_is_caught(self):
        data = copy_fixture_data(self.tmp / "data")
        self.save(good_draft())
        self.assertEqual(self.check(data_dir=data).returncode, 0)
        scenario = json.loads((data / "scenario.json").read_text())
        scenario["sites"]["C"]["capacity"] = 1
        (data / "scenario.json").write_text(json.dumps(scenario))
        self.assert_refused(self.issue(self.sha_of(), data_dir=data), "Site C capacity 1")
        self.assertEqual(self.order_files(), [])

    def test_traversal_package_id_writes_nothing_outside(self):
        self.save(good_draft(package_id="../../evil"))
        self.assert_refused(self.issue(self.sha_of()), "package_id")
        self.assertEqual(list(self.clone.rglob("*evil*")), [])

    def test_missing_sha_is_refused_with_exit_1(self):
        self.save(good_draft())
        self.assert_refused(run_script(self.writer, "issue_order.py", "drafts/P1.json"))
        self.assertEqual(self.order_files(), [])

    def test_missing_draft_is_refused(self):
        self.assert_refused(self.issue("abc", name="nope.json"))

    def test_hash_from_check_draft_output_works_end_to_end(self):
        self.save(good_draft())
        hash_text = self.check().stdout.strip().split("sha256=")[1]
        self.assertEqual(self.issue(hash_text).returncode, 0)


if __name__ == "__main__":
    unittest.main()
