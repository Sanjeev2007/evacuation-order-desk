"""Lock 1's rules. check_draft.py and issue_order.py both call draft_problems,
so the check and the issue can never disagree about what a good draft is.
"""
import hashlib
import json
import re

from eod.scenario import EodError, at_risk_towns, find_release, is_number, load_scenario
from eod.site_check import check_site

ISSUING_OFFICE = "DRILL: Emergency Duty Desk (fictional)"
BOOKEND = "DRILL, NOT A REAL ORDER"
REQUIRED_FIELDS = ["drill", "package_id", "stage", "release_id", "release_m3s", "towns",
                   "site_id", "text_en", "text_es", "issuing_office"]


def sha256_hex(raw):
    return hashlib.sha256(raw).hexdigest()


def is_valid_package_id(value):
    """Package ids become file names, so "../" and the like must never get through."""
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", value) is not None


def is_empty(value):
    """False and 0 are real values, not empty. drill: false gets its own message."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return not value
    return False


def has_replaces(draft):
    return draft.get("replaces") not in (None, "")


def draft_problems(raw, orders_dir):
    """Return every problem with a draft's raw bytes. An empty list means it is good.

    Values from the draft are printed with !r so a newline in one can't fake a line
    of output. Only the fields named here are read, so a "site passed" claim is ignored.
    """
    try:
        draft = json.loads(raw)
    except ValueError:
        return ["draft is not valid JSON"]
    if not isinstance(draft, dict):
        return ["draft must be a JSON object"]

    problems = []
    for field in REQUIRED_FIELDS:
        if is_empty(draft.get(field)):
            problems.append(f"{field} is missing or empty")

    if not is_empty(draft.get("drill")) and draft["drill"] is not True:
        problems.append("drill must be true")
    if not is_empty(draft.get("package_id")) and not is_valid_package_id(draft["package_id"]):
        problems.append(f"package_id {draft['package_id']!r} may only use letters, numbers, - and _")
    if not is_empty(draft.get("issuing_office")) and draft["issuing_office"] != ISSUING_OFFICE:
        problems.append(f"issuing_office must be exactly {ISSUING_OFFICE!r}")
    for field in ("text_en", "text_es"):
        if not is_empty(draft.get(field)) and not isinstance(draft[field], str):
            problems.append(f"{field} must be text")

    if has_replaces(draft):
        if not is_valid_package_id(draft["replaces"]):
            problems.append(f"replaces {draft['replaces']!r} may only use letters, numbers, - and _")
        elif not (orders_dir / f"order-{draft['replaces']}.md").exists():
            problems.append(f"replaces names order-{draft['replaces']}.md, which does not exist in orders/")

    problems.extend(scenario_problems(draft))
    return problems


def scenario_problems(draft):
    """Compare the draft with the scenario and rerun the site check from scratch."""
    if is_empty(draft.get("stage")) or is_empty(draft.get("release_id")):
        return []  # Already reported as missing, and nothing below can run without them.
    try:
        scenario = load_scenario()
        release = find_release(scenario, draft["stage"], draft["release_id"])
    except EodError as error:
        return [str(error)]

    problems = []
    claimed_release = draft.get("release_m3s")
    if not is_empty(claimed_release):
        if not is_number(claimed_release) or claimed_release != release["release_m3s"]:
            problems.append(f"release_m3s {claimed_release!r} does not match the scenario's {release['release_m3s']} for {release['id']}")

    towns = draft.get("towns")
    if not is_empty(towns):
        expected = [town["name"] for town in at_risk_towns(scenario, release["release_m3s"])]
        if not isinstance(towns, list) or not all(isinstance(town, str) for town in towns):
            problems.append("towns must be a list of town names")
        elif set(towns) != set(expected):
            problems.append(f"towns {sorted(set(towns))!r} do not match the at-risk towns {sorted(expected)!r} for {release['id']}")

    if not is_empty(draft.get("site_id")):
        try:
            result = check_site(draft["site_id"], draft["stage"], draft["release_id"])
        except EodError as error:
            problems.append(str(error))
        else:
            if result["status"] != "pass":
                problems.extend(result["reasons"])
    return problems


def render_order(draft, sha):
    """The order's text. It has no approver line: the script can't know who approved."""
    lines = [
        BOOKEND,
        "",
        f"Package: {draft['package_id']}",
        f"Issuing office: {draft['issuing_office']}",
        f"Stage: {draft['stage']}",
        f"Release: {draft['release_id']}, {draft['release_m3s']} m3/s (synthetic)",
        f"Towns: {', '.join(sorted(set(draft['towns'])))}",
        f"Site: Site {draft['site_id']}",
    ]
    if has_replaces(draft):
        lines.append(f"Replaces: {draft['replaces']}")
    lines += [
        "",
        "English:",
        draft["text_en"].strip(),
        "",
        "Spanish:",
        draft["text_es"].strip(),
        "",
        f"Draft sha256: {sha}",
        "",
        BOOKEND,
    ]
    return "\n".join(lines) + "\n"
