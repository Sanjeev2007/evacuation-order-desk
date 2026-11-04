#!/usr/bin/env python3
"""Check one site against the flood layer and a release's demand.

A site failing the check is a normal result (exit 0). Exit 2 means bad input.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eod.scenario import EodError, print_result
from eod.site_check import check_site


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--stage", type=int, required=True)
    args = parser.parse_args()

    try:
        result = check_site(args.site, args.stage, args.release_id)
    except EodError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
