#!/usr/bin/env python3
"""Lock 2: write the DRILL order file, but only if nothing has changed since the check.

With Auto off, this command raises the card before it runs. The order of the steps
below matters: nothing is written until every check has passed.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from eod.order_rules import draft_problems, path_problems, render_order, sha256_hex
from eod.scenario import EodError, print_result

# Worked out from the repo, not from this file, so a copy of the script elsewhere can't pass.
WRITER_DIR = REPO / "desks" / "writer"
ORDERS_DIR = WRITER_DIR / "orders"
DRAFTS_DIR = WRITER_DIR / "drafts"


class RefusingParser(argparse.ArgumentParser):
    """Bad command-line use is a refusal too (argparse alone would exit 2)."""

    def error(self, message):
        refuse([message])


def refuse(reasons):
    print("REFUSED")
    for reason in reasons:
        print(reason)
    sys.exit(1)


def write_order_once(order_path, text):
    """Write to a temporary file, then link it into place. Linking fails if the order
    exists, and a failure part-way leaves nothing behind."""
    temporary = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=ORDERS_DIR, prefix=".tmp-", delete=False)
    try:
        with temporary:
            temporary.write(text)
        os.link(temporary.name, order_path)
    finally:
        os.unlink(temporary.name)


def main():
    sys.stdout.reconfigure(errors="backslashreplace")  # An odd character can't crash a message.
    parser = RefusingParser(description=__doc__)
    parser.add_argument("draft")
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()

    # 1. Only the writer's own folder may issue an order.
    try:
        in_writer_folder = Path.cwd().resolve() == WRITER_DIR and Path(__file__).resolve().parent == WRITER_DIR
    except OSError:
        in_writer_folder = False
    if not in_writer_folder:
        refuse(["issue_order.py must be run from desks/writer, not from this folder"])

    # 2. Read the file once. Everything below uses these bytes, so it can't change midway.
    draft_path = Path(args.draft)
    if path_problems(draft_path, DRAFTS_DIR):
        refuse(path_problems(draft_path, DRAFTS_DIR))
    try:
        raw = draft_path.read_bytes()
    except OSError as error:
        refuse([f"cannot read {args.draft!r}: {error.strerror}"])

    # 3. The file must be exactly the one that was checked and shown in chat.
    # The file's own hash is never printed: the way forward is a new check and a new post in chat.
    if not re.fullmatch(r"[0-9a-f]{64}", args.sha):
        refuse(["--sha must be exactly the 64-character hash that check_draft.py printed"])
    sha = sha256_hex(raw)
    if sha != args.sha:
        refuse(["draft changed after the check: rerun check_draft.py and post the new draft and hash in chat"])

    # 4. Rerun every Lock 1 check, using the same code as check_draft.py.
    problems = draft_problems(raw, ORDERS_DIR, draft_path)
    if problems:
        refuse(problems)

    # 5. Write it. An order that already exists is never overwritten.
    draft = json.loads(raw)
    order_path = ORDERS_DIR / f"order-{draft['package_id']}.md"
    try:
        text = render_order(draft, sha)
    except EodError as error:
        refuse([str(error)])
    try:
        ORDERS_DIR.mkdir(exist_ok=True)
    except OSError as error:
        refuse([f"cannot create orders/: {error.strerror}"])
    try:
        write_order_once(order_path, text)
    except FileExistsError:
        refuse([f"orders/{order_path.name} already exists, orders are never overwritten"])
    except OSError as error:
        refuse([f"cannot write orders/{order_path.name}: {error.strerror}"])

    print_result({"package_id": draft["package_id"], "order_file": f"orders/{order_path.name}", "sha256": sha})
    return 0


if __name__ == "__main__":
    sys.exit(main())
