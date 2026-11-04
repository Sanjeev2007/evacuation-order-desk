#!/usr/bin/env python3
"""Show the staff and boats for each named town."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eod.scenario import EodError, load_scenario, print_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--towns", required=True, help='comma-separated, for example "A,B"')
    args = parser.parse_args()

    names = [name.strip() for name in args.towns.split(",") if name.strip()]
    try:
        if not names:
            raise EodError("no towns given")
        towns_by_name = {town["name"]: town for town in load_scenario()["towns"]}
        for name in names:
            if name not in towns_by_name:
                raise EodError(f"unknown town {name!r}")
    except EodError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print_result({
        "towns": [
            {"name": name, "staff": towns_by_name[name]["staff"], "boats": towns_by_name[name]["boats"]}
            for name in names
        ],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
