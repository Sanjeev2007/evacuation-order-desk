#!/usr/bin/env python3
"""Show which towns a release puts at risk, and how many people that means."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from eod.scenario import EodError, at_risk_towns, demand_for, find_release, load_scenario, print_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--stage", type=int, required=True)
    args = parser.parse_args()

    try:
        scenario = load_scenario()
        release = find_release(scenario, args.stage, args.release_id)
    except EodError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    amount = release["release_m3s"]
    print_result({
        "stage": args.stage,
        "release_id": args.release_id,
        "release_m3s": amount,
        "towns": [town["name"] for town in at_risk_towns(scenario, amount)],
        "demand": demand_for(scenario, amount),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
