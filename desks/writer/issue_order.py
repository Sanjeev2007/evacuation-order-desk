#!/usr/bin/env python3
"""Lock 2: write the DRILL order file, but only if nothing has changed since the check.

With Auto off, this command raises the card before it runs. The order of the steps
below matters: nothing is written until every check has passed.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eod.order_rules import draft_problems, render_order, sha256_hex
from eod.scenario import print_result

WRITER_DIR = Path(__file__).resolve().parent
ORDERS_DIR = WRITER_DIR / "orders"


class RefusingParser(argparse.ArgumentParser):
    """Bad command-line use is a refusal too (argparse alone would exit 2)."""

    def error(self, message):
        refuse([message])


def refuse(reasons):
    print("REFUSED")
    for reason in reasons:
        print(reason)
    sys.exit(1)


def main():
    parser = RefusingParser(description=__doc__)
    parser.add_argument("draft")
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()

    # 1. Only the writer's own folder may issue an order.
    if Path.cwd().resolve() != WRITER_DIR:
        refuse(["issue_order.py must be run from desks/writer, not from this folder"])

    # 2. Read the file once. Everything below uses these bytes, so it can't change midway.
    try:
        raw = Path(args.draft).read_bytes()
    except OSError as error:
        refuse([f"cannot read {args.draft!r}: {error.strerror}"])

    # 3. The file must be exactly the one that was checked and shown in chat.
    sha = sha256_hex(raw)
    if sha != args.sha:
        refuse([f"draft changed after the check: the file's hash is {sha}"])

    # 4. Rerun every Lock 1 check, using the same code as check_draft.py.
    problems = draft_problems(raw, ORDERS_DIR)
    if problems:
        refuse(problems)

    # 5. Exclusive-create mode ("x") fails if the file exists, so an order is never overwritten.
    draft = json.loads(raw)
    order_path = ORDERS_DIR / f"order-{draft['package_id']}.md"
    try:
        ORDERS_DIR.mkdir(exist_ok=True)
        with open(order_path, "x", encoding="utf-8") as order_file:
            order_file.write(render_order(draft, sha))
    except FileExistsError:
        refuse([f"orders/{order_path.name} already exists, orders are never overwritten"])
    except OSError as error:
        refuse([f"cannot write orders/{order_path.name}: {error.strerror}"])

    print_result({"package_id": draft["package_id"], "order_file": f"orders/{order_path.name}", "sha256": sha})
    return 0


if __name__ == "__main__":
    sys.exit(main())
