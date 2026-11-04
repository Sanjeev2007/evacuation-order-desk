"""Shared test tools: run the scripts as real commands against small fixtures.

Writing tests run inside a throwaway copy of the code (make_clone), so they
never touch the real desks/writer/orders or desks/record/records folders.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
OFFICE = "DRILL: Emergency Duty Desk (fictional)"
BOOKEND = "DRILL, NOT A REAL ORDER"


def make_clone(target):
    """Copy only the code (eod/ and desks/**/*.py) into an empty folder."""
    target = Path(target)
    shutil.copytree(REPO / "eod", target / "eod", ignore=shutil.ignore_patterns("__pycache__"))
    for script in (REPO / "desks").rglob("*.py"):
        destination = target / script.relative_to(REPO)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(script, destination)
    return target


def copy_fixture_data(target):
    """Copy the fixture data somewhere a test can safely change it."""
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    for name in ("scenario.json", "sites.geojson", "flood-zone.geojson"):
        shutil.copy(FIXTURES / name, target / name)
    return target


def run_script(cwd, script, *args, data_dir=FIXTURES):
    """Run a script as an agent would: python3 <script> ... from cwd."""
    env = dict(os.environ)
    env.pop("EOD_DATA_DIR", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if data_dir is not None:
        env["EOD_DATA_DIR"] = str(data_dir)
    return subprocess.run(
        [sys.executable, str(script), *[str(arg) for arg in args]],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    )


def good_draft(**changes):
    """A draft that passes every check against the fixture data."""
    draft = {
        "drill": True,
        "package_id": "P1",
        "stage": 1,
        "release_id": "R2",
        "release_m3s": 600,
        "towns": ["Alpha", "Bravo"],
        "site_id": "C",
        "text_en": "DRILL: move to Site C.",
        "text_es": "SIMULACRO: evacuación hacia el Sitio C.",
        "issuing_office": OFFICE,
    }
    draft.update(changes)
    return draft


def json_output(result):
    return json.loads(result.stdout)
