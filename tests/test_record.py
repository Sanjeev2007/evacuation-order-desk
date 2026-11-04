import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.helpers import json_output, make_clone, run_script

HEADING_NOTE = "DRILL record. Synthetic scenario. Nothing was sent."


def good_notes():
    return {
        "package_id": "P1",
        "order_file": "orders/order-P1.md",
        "entries": [{
            "time": "10:02",
            "who": "site checker",
            "decision": "Site A rejected",
            "why": "Inside the saved layer",
            "source": "Field room message 14",
        }],
    }


class WriteRecordTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)
        self.desk = make_clone(self.tmp / "clone") / "desks" / "record"
        self.records = self.desk / "records"

    def write(self, notes):
        path = self.desk / "notes.json"
        path.write_text(json.dumps(notes), encoding="utf-8")
        return run_script(self.desk, "write_record.py", "--input", "notes.json")

    def record_files(self):
        return sorted(path.name for path in self.records.glob("*")) if self.records.exists() else []

    def assert_refused(self, result):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.record_files(), [])

    def test_writes_a_markdown_table_with_the_heading_note(self):
        result = self.write(good_notes())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(json_output(result)["synthetic"], True)
        text = (self.records / "record-P1.md").read_text(encoding="utf-8")
        self.assertIn(HEADING_NOTE, text.splitlines()[0])
        self.assertIn("orders/order-P1.md", text)
        self.assertIn("| Time | Who | Decision | Why | Source |", text)
        self.assertIn("| 10:02 | site checker | Site A rejected | Inside the saved layer | Field room message 14 |", text)

    def test_each_missing_top_level_field_is_refused(self):
        for field in ("package_id", "order_file", "entries"):
            with self.subTest(field=field):
                notes = good_notes()
                del notes[field]
                self.assert_refused(self.write(notes))

    def test_each_missing_entry_field_is_refused(self):
        for field in ("time", "who", "decision", "why", "source"):
            with self.subTest(field=field):
                notes = good_notes()
                del notes["entries"][0][field]
                self.assert_refused(self.write(notes))

    def test_missing_source_is_refused_and_named(self):
        notes = good_notes()
        del notes["entries"][0]["source"]
        result = self.write(notes)
        self.assert_refused(result)
        self.assertIn("source", result.stderr)

    def test_blank_source_is_refused(self):
        notes = good_notes()
        notes["entries"][0]["source"] = "   "
        self.assert_refused(self.write(notes))

    def test_empty_entries_is_refused(self):
        notes = good_notes()
        notes["entries"] = []
        self.assert_refused(self.write(notes))

    def test_entries_that_are_not_objects_are_refused(self):
        notes = good_notes()
        notes["entries"] = ["just text"]
        self.assert_refused(self.write(notes))

    def test_no_overwrite(self):
        self.assertEqual(self.write(good_notes()).returncode, 0)
        before = (self.records / "record-P1.md").read_text(encoding="utf-8")
        notes = good_notes()
        notes["entries"][0]["decision"] = "Changed later"
        self.assertEqual(self.write(notes).returncode, 2)
        self.assertEqual((self.records / "record-P1.md").read_text(encoding="utf-8"), before)

    def test_does_not_invent_an_approver(self):
        notes = good_notes()
        notes["approved_by"] = "SOMEONE"
        self.assertEqual(self.write(notes).returncode, 0)
        text = (self.records / "record-P1.md").read_text(encoding="utf-8")
        self.assertNotIn("approved by", text.lower())
        self.assertNotIn("SOMEONE", text)

    def test_pipes_and_newlines_cannot_break_the_table(self):
        notes = good_notes()
        notes["entries"][0]["why"] = "one | two\nthree"
        self.assertEqual(self.write(notes).returncode, 0)
        text = (self.records / "record-P1.md").read_text(encoding="utf-8")
        self.assertIn(r"one \| two three", text)

    def test_package_id_cannot_climb_out_of_the_records_folder(self):
        notes = good_notes()
        notes["package_id"] = "../../evil"
        self.assert_refused(self.write(notes))
        self.assertEqual(list(self.tmp.rglob("*evil*")), [])

    def test_missing_input_file_exits_2(self):
        result = run_script(self.desk, "write_record.py", "--input", "nope.json")
        self.assert_refused(result)

    def test_input_that_is_not_json_exits_2(self):
        (self.desk / "notes.json").write_text("{not json")
        result = run_script(self.desk, "write_record.py", "--input", "notes.json")
        self.assert_refused(result)


if __name__ == "__main__":
    unittest.main()
