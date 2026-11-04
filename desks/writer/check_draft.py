#!/usr/bin/env python3
"""Lock 1: check a draft. Prints PASS sha256=<hash>, or BLOCKED and each problem.

Agents run this without a card. It never writes anything.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eod.order_rules import draft_problems, sha256_hex

ORDERS_DIR = Path(__file__).resolve().parent / "orders"


class BlockingParser(argparse.ArgumentParser):
    """Bad command-line use is a BLOCKED result too (argparse alone would exit 2)."""

    def error(self, message):
        block([message])


def block(problems):
    print("BLOCKED")
    for problem in problems:
        print(problem)
    sys.exit(1)


def main():
    parser = BlockingParser(description=__doc__)
    parser.add_argument("draft")
    args = parser.parse_args()

    try:
        raw = Path(args.draft).read_bytes()
    except OSError as error:
        block([f"cannot read {args.draft!r}: {error.strerror}"])

    # The hash and the checks both use these same bytes, so they can't describe different files.
    problems = draft_problems(raw, ORDERS_DIR)
    if problems:
        block(problems)

    print(f"PASS sha256={sha256_hex(raw)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
