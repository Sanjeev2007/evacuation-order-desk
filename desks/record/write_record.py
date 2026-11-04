#!/usr/bin/env python3
"""Write the decision record from notes. Every entry must cite its source.

It only copies what the notes say: it never works out or adds who approved anything.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eod.order_rules import is_valid_package_id, sha256_hex
from eod.scenario import EodError, load_json, print_result

RECORDS_DIR = Path(__file__).resolve().parent / "records"
ORDERS_DIR = Path(__file__).resolve().parents[1] / "writer" / "orders"
HEADING_NOTE = "DRILL record. Synthetic scenario. Nothing was sent."
ENTRY_FIELDS = ["time", "who", "decision", "why", "source"]


def is_filled_text(value):
    return isinstance(value, str) and bool(value.strip())


def check_notes(notes):
    """Raise EodError naming the first problem found."""
    if not isinstance(notes, dict):
        raise EodError("notes must be a JSON object")
    if not is_valid_package_id(notes.get("package_id")):
        raise EodError("package_id is missing or invalid (letters, numbers, - and _ only)")
    if not is_filled_text(notes.get("order_file")):
        raise EodError("order_file is missing or empty")
    entries = notes.get("entries")
    if not isinstance(entries, list) or not entries:
        raise EodError("entries is missing or empty")
    for number, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise EodError(f"entry {number} must be an object")
        for field in ENTRY_FIELDS:
            if not is_filled_text(entry.get(field)):
                raise EodError(f"entry {number} is missing {field}")


def table_cell(text):
    """Keep a value on one line, and stop a | in it from starting a new column."""
    return " ".join(text.split()).replace("|", "\\|")


def issued_order_hash(package_id):
    """A record can only describe an order that was issued, and it pins that exact file."""
    try:
        return sha256_hex((ORDERS_DIR / f"order-{package_id}.md").read_bytes())
    except OSError:
        raise EodError(f"order {package_id} has not been issued, so there is nothing to record")


def render_record(notes, order_hash):
    lines = [
        f"# {HEADING_NOTE}",
        "",
        f"Package: {notes['package_id']}",
        f"Order file: {table_cell(notes['order_file'])}",
        f"Order file sha256: {order_hash}",
        "",
        "| Time | Who | Decision | Why | Source |",
        "|---|---|---|---|---|",
    ]
    for entry in notes["entries"]:
        cells = [table_cell(entry[field]) for field in ENTRY_FIELDS]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="path to notes.json")
    args = parser.parse_args()

    try:
        notes = load_json(args.input)
        check_notes(notes)
        order_hash = issued_order_hash(notes["package_id"])
        record_path = RECORDS_DIR / f"record-{notes['package_id']}.md"
        RECORDS_DIR.mkdir(exist_ok=True)
        # Exclusive-create mode ("x") fails if the file exists, so a record is never overwritten.
        with open(record_path, "x", encoding="utf-8") as record_file:
            record_file.write(render_record(notes, order_hash))
    except EodError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    except FileExistsError:
        print(f"ERROR: records/{record_path.name} already exists, records are never overwritten", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"ERROR: cannot write the record: {error.strerror}", file=sys.stderr)
        return 2

    print_result({"package_id": notes["package_id"], "record_file": f"records/{record_path.name}"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
