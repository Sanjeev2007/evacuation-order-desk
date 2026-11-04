#!/usr/bin/env python3
"""Show a stage's inflow, level and possible releases."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eod.scenario import EodError, find_stage, load_scenario, print_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, required=True)
    args = parser.parse_args()

    try:
        stage = find_stage(load_scenario(), args.stage)
    except EodError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print_result({
        "stage": args.stage,
        "inflow_m3s": stage["inflow_m3s"],
        "level_m": stage["level_m"],
        "releases": stage["releases"],
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
