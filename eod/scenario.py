"""Read the synthetic scenario and answer: which towns are at risk, and how many people?"""
import json
import math
import os
from pathlib import Path


class EodError(Exception):
    """Bad input or bad data. Scripts turn this into a refusal, never a pass."""


def data_dir():
    """data/ beside this code. Only the tests can point elsewhere, so a stray setting can't."""
    override = os.environ.get("EOD_DATA_DIR")
    if override and os.environ.get("EOD_TESTING") == "1":
        return Path(override)
    return Path(__file__).resolve().parent.parent / "data"


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise EodError(f"cannot read {path}: {error.strerror}")
    except ValueError:
        raise EodError(f"{path} is not valid JSON")


def is_number(value):
    # In Python True counts as a number, and JSON readers accept NaN, so both are ruled out by hand.
    if isinstance(value, float):
        return math.isfinite(value)
    return isinstance(value, int) and not isinstance(value, bool)


def load_scenario():
    scenario = load_json(data_dir() / "scenario.json")
    check_scenario_shape(scenario)
    return scenario


def check_scenario_shape(scenario):
    """Stop early with a clear message if a field the checks rely on is missing."""
    if not isinstance(scenario, dict):
        raise EodError("scenario.json must hold an object")
    stages = scenario.get("stages")
    towns = scenario.get("towns")
    sites = scenario.get("sites")
    if not isinstance(stages, dict) or not isinstance(towns, list) or not isinstance(sites, dict):
        raise EodError("scenario.json needs stages, towns and sites")
    for number, stage in stages.items():
        require_numbers(stage, ["inflow_m3s", "level_m"], f"stage {number}")
        if not isinstance(stage.get("releases"), list):
            raise EodError(f"stage {number} in scenario.json has no releases list")
        for release in stage["releases"]:
            require_numbers(release, ["release_m3s"], f"a release in stage {number}")
            if not isinstance(release.get("id"), str):
                raise EodError(f"a release in stage {number} has no id")
    for town in towns:
        require_numbers(town, ["threshold_release_m3s", "evacuees", "staff", "boats"], "a town")
        if not isinstance(town.get("name"), str):
            raise EodError("a town in scenario.json has no name")
    for site_id, site in sites.items():
        require_numbers(site, ["capacity"], f"site {site_id}")


def require_numbers(item, fields, label):
    for field in fields:
        if not isinstance(item, dict) or not is_number(item.get(field)):
            raise EodError(f"{label} in scenario.json needs a number for {field}")


def find_stage(scenario, stage):
    """The JSON keys are text, so stage 1 and "1" find the same stage."""
    key = str(stage)
    if key not in scenario["stages"]:
        raise EodError(f"unknown stage {stage!r}")
    return scenario["stages"][key]


def find_release(scenario, stage, release_id):
    for release in find_stage(scenario, stage)["releases"]:
        if release["id"] == release_id:
            return release
    raise EodError(f"release {release_id!r} does not exist in stage {stage!r}")


def at_risk_towns(scenario, release_m3s):
    """A town is at risk when the release reaches its threshold, exactly at it included."""
    return [town for town in scenario["towns"] if release_m3s >= town["threshold_release_m3s"]]


def demand_for(scenario, release_m3s):
    return sum(town["evacuees"] for town in at_risk_towns(scenario, release_m3s))


def print_result(result):
    """Every JSON output from these scripts says the numbers are synthetic."""
    print(json.dumps({**result, "synthetic": True}, indent=2))
