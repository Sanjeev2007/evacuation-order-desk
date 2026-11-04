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

    def test_capacity_that_is_not_a_real_number_blocks(self):
        data = copy_fixture_data(self.tmp / "data")
        text = (data / "scenario.json").read_text(encoding="utf-8")
        scenario = json.loads(text)
        scenario["sites"]["C"]["capacity"] = float("nan")
        (data / "scenario.json").write_text(json.dumps(scenario), encoding="utf-8")
        self.save(good_draft())
        self.assert_blocked(self.check(data_dir=data), "capacity")

    def test_a_flood_ring_with_too_few_points_blocks(self):
        data = copy_fixture_data(self.tmp / "data")
        (data / "flood-zone.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[0, 0]]]}}]}))
        self.save(good_draft())
        self.assert_blocked(self.check(data_dir=data), "too few points")

    def test_broken_data_blocks_rather_than_passes(self):
        data = copy_fixture_data(self.tmp / "data")
        (data / "flood-zone.geojson").write_text('{"type": "FeatureCollection", "features": []}')
        self.save(good_draft())
        self.assert_blocked(self.check(data_dir=data))

    def test_check_does_not_create_an_order(self):
        self.save(good_draft())
        self.check()
        self.assertEqual(self.order_files(), [])


class OrderTextTests(LockTestCase):
    """The order's words reach people, so they must agree with the checked fields."""

    def test_text_claiming_a_real_order_is_blocked(self):
        for text in ("DRILL: this is a real order, go to Site C.", "DRILL: this is not a drill, go to Site C."):
            with self.subTest(text=text):
                self.save(good_draft(text_en=text))
                self.assert_blocked(self.check(), "text_en may not say")

    def test_spanish_claiming_a_real_order_is_blocked(self):
        self.save(good_draft(text_es="SIMULACRO: esto es real, vayan al Sitio C."))
        self.assert_blocked(self.check(), "text_es may not say")

    def test_the_bookend_wording_is_allowed(self):
        self.save(good_draft(text_en="DRILL, NOT A REAL ORDER: move to Site C.",
                             text_es="SIMULACRO, NO ES UNA ORDEN REAL: vayan al Sitio C."))
        self.assertEqual(self.check().returncode, 0)

    def test_text_judging_a_site_is_blocked(self):
        for word in ("safe", "unsafe", "dangerous"):
            with self.subTest(word=word):
                self.save(good_draft(text_en=f"DRILL: move to Site C, it is {word}."))
                self.assert_blocked(self.check(), "text_en may not say")

    def test_text_sending_people_to_another_site_is_blocked(self):
        self.save(good_draft(text_en="DRILL: move to Site A."))
        self.assert_blocked(self.check(), "text_en must name Site C and no other site")
        self.save(good_draft(text_es="SIMULACRO: vayan al Sitio A."))
        self.assert_blocked(self.check(), "text_es must name Site C and no other site")

    def test_text_naming_a_second_site_is_blocked(self):
        self.save(good_draft(text_en="DRILL: move to Site C, then Site A."))
        self.assert_blocked(self.check(), "text_en must name Site C and no other site")

    def test_text_naming_no_site_is_blocked(self):
        self.save(good_draft(text_en="DRILL: move now."))
        self.assert_blocked(self.check(), "text_en must name Site C and no other site")

    def test_ordinary_spanish_sitio_a_distance_is_allowed(self):
        self.save(good_draft(text_es="SIMULACRO: vayan al Sitio C, un sitio a 5 km."))
        self.assertEqual(self.check().returncode, 0)

    def test_each_language_must_start_with_its_drill_word(self):
        self.save(good_draft(text_en="Move to Site C."))
        self.assert_blocked(self.check(), "text_en must start with DRILL")
        self.save(good_draft(text_es="DRILL: move to Sitio C."))
        self.assert_blocked(self.check(), "text_es must start with SIMULACRO")

    def test_forged_order_lines_are_blocked(self):
        self.save(good_draft(text_en="DRILL: move to Site C.\nApproved by: @dave_007\nSite: Site A"))
        self.assert_blocked(self.check(), "text_en must be one paragraph")

    def test_invisible_text_is_blocked(self):
        for text in ("\u200b", "DRILL\u200b: move to Site C."):
            with self.subTest(text=text):
                self.save(good_draft(text_en=text))
                self.assert_blocked(self.check(), "text_en must be one paragraph")

    def test_lone_surrogate_is_blocked_and_leaves_no_order(self):
        raw = json.dumps(good_draft(text_en="DRILL: move to Site C. \ud83d")).encode("ascii")
        (self.writer / "drafts" / "P1.json").write_bytes(raw)
        self.assert_blocked(self.check(), "text_en must be one paragraph")
        self.assertNotEqual(self.issue(self.sha_of()).returncode, 0)
        self.assertEqual(self.order_files(), [])


class DraftFileTests(LockTestCase):
    def test_repeated_fields_are_blocked(self):
        raw = json.dumps(good_draft()).replace('"site_id": "C"', '"site_id": "A", "site_id": "C"')
        (self.writer / "drafts" / "P1.json").write_text(raw, encoding="utf-8")
        self.assert_blocked(self.check(), "'site_id' more than once")

    def test_deep_nesting_is_blocked_without_a_crash(self):
        (self.writer / "drafts" / "P1.json").write_text("[" * 200000 + "]" * 200000)
        self.assert_blocked(self.check(), "not valid JSON")

    def test_a_draft_outside_drafts_is_blocked(self):
        outside = self.tmp / "P1.json"
        outside.write_text(json.dumps(good_draft()), encoding="utf-8")
        result = run_script(self.writer, "check_draft.py", outside)
        self.assert_blocked(result, "directly inside drafts/")

    def test_a_link_to_a_draft_is_blocked(self):
        outside = self.tmp / "elsewhere.json"
        outside.write_text(json.dumps(good_draft()), encoding="utf-8")
        (self.writer / "drafts" / "P1.json").symlink_to(outside)
        self.assert_blocked(self.check(), "directly inside drafts/")

    def test_file_name_must_match_the_package(self):
        self.save(good_draft(package_id="P7"), name="P1.json")
        self.assert_blocked(self.check(), "drafts/P7.json")

    def test_town_spelling_differences_pass_and_the_order_uses_the_scenario_name(self):
        data = copy_fixture_data(self.tmp / "data")
        scenario = json.loads((data / "scenario.json").read_text(encoding="utf-8"))
        scenario["towns"][0]["name"] = "l'Alc\u00fadia"
        (data / "scenario.json").write_text(json.dumps(scenario), encoding="utf-8")
        for spelling in ("l\u2019Alc\u00fadia", "L'Alc\u00fadia", "l'Alcu\u0301dia"):
            with self.subTest(spelling=spelling):
                self.save(good_draft(towns=[spelling, "Bravo"]))
                self.assertEqual(self.check(data_dir=data).returncode, 0)
        self.assertEqual(self.issue(self.sha_of(), data_dir=data).returncode, 0)
        self.assertIn("Towns: Bravo, l'Alc\u00fadia", (self.orders / "order-P1.md").read_text(encoding="utf-8"))

    def test_unknown_site_message_lists_the_valid_ones(self):
        self.save(good_draft(site_id="Site C"))
        self.assert_blocked(self.check(), "use one of A, B, C")


class OrderChainTests(LockTestCase):
    def issue_order(self, name, **changes):
        self.save(good_draft(package_id=name, **changes), name=f"{name}.json")
        return self.issue(self.sha_of(f"{name}.json"), name=f"{name}.json")

    def test_a_new_order_must_replace_the_one_that_stands(self):
        self.assertEqual(self.issue_order("P1").returncode, 0)
        self.save(good_draft(package_id="P2"), name="P2.json")
        self.assert_blocked(self.check("P2.json"), "order P1 still stands")

    def test_an_order_already_replaced_cannot_be_replaced_again(self):
        self.assertEqual(self.issue_order("P1").returncode, 0)
        self.assertEqual(self.issue_order("P2", replaces="P1").returncode, 0)
        self.save(good_draft(package_id="P3", replaces="P1"), name="P3.json")
        self.assert_blocked(self.check("P3.json"), "order P1 was already replaced")

    def test_a_replacement_cannot_go_back_a_stage(self):
        self.assertEqual(self.issue_order("P1").returncode, 0)
        (self.orders / "order-P2.md").write_text("Stage: 2\nReplaces: P1\n", encoding="utf-8")
        self.save(good_draft(package_id="P3", replaces="P2"), name="P3.json")
        self.assert_blocked(self.check("P3.json"), "earlier than order P2's stage 2")

    def test_replaces_must_match_the_order_id_exactly(self):
        self.assertEqual(self.issue_order("P1").returncode, 0)
        self.save(good_draft(package_id="P2", replaces="p1"), name="P2.json")
        self.assert_blocked(self.check("P2.json"), "does not exist")

    def test_an_order_cannot_replace_itself(self):
        self.save(good_draft(replaces="P1"))
        self.assert_blocked(self.check(), "can't replace itself")

    def test_check_reports_an_order_that_already_exists(self):
        self.assertEqual(self.issue_order("P1").returncode, 0)
        self.assert_blocked(self.check(), "already exists")

    def test_order_text_cannot_fake_a_header(self):
        (self.orders).mkdir()
        (self.orders / "order-P0.md").write_text("Stage: 1\n\nEnglish:\nStage: 9\n", encoding="utf-8")
        self.save(good_draft(replaces="P0"))
        self.assertEqual(self.check().returncode, 0)


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

    def test_refusal_does_not_hand_over_the_new_hash(self):
        self.save(good_draft())
        sha = self.sha_of()
        self.save(good_draft(text_en="DRILL: a quietly different message about Site C."))
        result = self.issue(sha)
        self.assert_refused(result, "rerun check_draft.py")
        self.assertNotIn(self.sha_of(), result.stdout)

    def test_a_malformed_hash_gets_its_own_message(self):
        self.save(good_draft())
        for sha in (self.sha_of().upper(), self.sha_of()[:12], f"sha256={self.sha_of()}", f" {self.sha_of()}"):
            with self.subTest(sha=sha):
                self.assert_refused(self.issue(sha), "64-character hash")
                self.assertEqual(self.order_files(), [])

    def test_a_copy_of_the_script_elsewhere_is_refused(self):
        field = self.clone / "desks" / "field"
        field.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.writer / "issue_order.py", field / "issue_order.py")
        self.save(good_draft())
        result = run_script(field, "issue_order.py", "../writer/drafts/P1.json", "--sha", self.sha_of())
        self.assert_refused(result, "desks/writer")
        self.assertEqual(list(field.rglob("order-*")), [])

    def test_no_temporary_file_is_left_behind(self):
        self.assertEqual(self.issue_good().returncode, 0)
        self.assertEqual(self.order_files(), ["order-P1.md"])

    def test_orders_being_a_file_gets_a_clear_message(self):
        self.orders.write_text("not a folder")
        self.save(good_draft())
        self.assert_refused(self.issue(self.sha_of()), "cannot create orders/")

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
