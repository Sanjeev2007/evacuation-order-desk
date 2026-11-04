"""Lock 1's rules. check_draft.py and issue_order.py both call draft_problems,
so the check and the issue can never disagree about what a good draft is.
"""
import hashlib
import json
import re
import unicodedata

from eod.scenario import EodError, at_risk_towns, find_release, is_number, load_scenario
from eod.site_check import check_site

ISSUING_OFFICE = "DRILL: Emergency Duty Desk (fictional)"
BOOKEND = "DRILL, NOT A REAL ORDER"
REQUIRED_FIELDS = ["drill", "package_id", "stage", "release_id", "release_m3s", "towns",
                   "site_id", "text_en", "text_es", "issuing_office"]

# (field, required first word, how the text names a site, words it may not use).
# Spanish "sitio a 5 km" is ordinary text, so only a capital letter counts there.
# A word list can't catch a building's name: the person reading the draft is the check for that.
TEXT_RULES = [
    ("text_en", "DRILL", re.compile(r"\bsite\s+([a-z])\b", re.IGNORECASE),
     re.compile(r"\b(real order|not a drill|safe|unsafe|dangerous)\b", re.IGNORECASE),
     "not a real order"),
    ("text_es", "SIMULACRO", re.compile(r"\b(?:[Ss]itio|[Ss]ite)\s+([A-Z])\b"),
     re.compile(r"\b(orden real|no es un simulacro|es real|segur[oa]|insegur[oa]|peligros[oa])\b", re.IGNORECASE),
     "no es una orden real"),
]
HIDDEN_CATEGORIES = {"Cc", "Cf", "Cs", "Zl", "Zp"}


def sha256_hex(raw):
    return hashlib.sha256(raw).hexdigest()


def is_valid_package_id(value):
    """Package ids become file names, so "../" and the like must never get through."""
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value) is not None


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


class RepeatedField(ValueError):
    pass


def refuse_repeated_fields(pairs):
    """JSON keeps the last of two same-named fields, so a reader could see the other one."""
    fields = {}
    for name, value in pairs:
        if name in fields:
            raise RepeatedField(name)
        fields[name] = value
    return fields


def path_problems(path, drafts_dir):
    """A draft must be a plain file directly inside drafts/, not a link or anything else."""
    if path.is_symlink() or not path.is_file() or path.resolve().parent != drafts_dir.resolve():
        return [f"{str(path)!r} must be a file directly inside drafts/"]
    return []


def draft_problems(raw, orders_dir, draft_path=None):
    """Return every problem with a draft's raw bytes. An empty list means it is good.

    Values from the draft are printed with !r so a newline in one can't fake a line
    of output. Only the fields named here are read, so a "site passed" claim is ignored.
    """
    try:
        draft = json.loads(raw, object_pairs_hook=refuse_repeated_fields)
    except RepeatedField as error:
        return [f"draft has the field {str(error)!r} more than once"]
    except (ValueError, RecursionError):
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

    if (draft_path is not None and is_valid_package_id(draft.get("package_id"))
            and draft_path.name != f"{draft['package_id']}.json"):
        problems.append(f"the draft for {draft['package_id']} must be saved as drafts/{draft['package_id']}.json")

    problems.extend(text_problems(draft))
    problems.extend(order_chain_problems(draft, orders_dir))
    problems.extend(scenario_problems(draft))
    return problems


def text_problems(draft):
    """The order's words go to people, so they must agree with the checked fields."""
    problems = []
    site = draft.get("site_id")
    for field, first_word, site_pattern, banned, allowed in TEXT_RULES:
        text = draft.get(field)
        if is_empty(text) or not isinstance(text, str):
            continue  # Already reported.
        text = text.strip()
        if any(unicodedata.category(character) in HIDDEN_CATEGORIES for character in text):
            problems.append(f"{field} must be one paragraph, with no hidden or control characters")
        if not re.match(rf"{first_word}\b", text):
            problems.append(f"{field} must start with {first_word}")
        # An unknown site is reported elsewhere, and its text must never be printed unquoted.
        if isinstance(site, str) and re.fullmatch("[A-Z]", site) and set(site_pattern.findall(text)) != {site}:
            problems.append(f"{field} must name Site {site} and no other site")
        match = banned.search(re.sub(allowed, "", text, flags=re.IGNORECASE))
        if match:
            problems.append(f"{field} may not say {match.group(0)!r}: it must stay a drill and never judge a site's safety")
    return problems


def read_orders(orders_dir):
    """Issued orders as {package id: header lines}. Listing the folder keeps names exact."""
    orders = {}
    if not orders_dir.is_dir():
        return orders
    for path in orders_dir.iterdir():
        match = re.fullmatch(r"order-(.+)\.md", path.name)
        if not match:
            continue
        header = {}
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line == "English:":
                break  # The order's own text can't count as a header.
            name, separator, value = line.partition(": ")
            if separator:
                header[name] = value
        orders[match.group(1)] = header
    return orders


def order_chain_problems(draft, orders_dir):
    """One order stands at a time: a new one must replace it, and can't go back a stage."""
    package_id = draft.get("package_id")
    orders = read_orders(orders_dir)
    if is_valid_package_id(package_id) and package_id in orders:
        return [f"orders/order-{package_id}.md already exists, orders are never overwritten"]

    standing = sorted(set(orders) - {header.get("Replaces") for header in orders.values()})
    if not has_replaces(draft):
        if standing:
            return [f"order {', '.join(standing)} still stands, so this draft must name it in replaces"]
        return []

    replaces = draft["replaces"]
    if not is_valid_package_id(replaces):
        return [f"replaces {replaces!r} may only use letters, numbers, - and _"]
    if replaces == package_id:
        return ["an order can't replace itself"]
    if replaces not in orders:
        return [f"replaces names order-{replaces}.md, which does not exist in orders/"]
    if replaces not in standing:
        return [f"order {replaces} was already replaced, so name the order that stands: {', '.join(standing)}"]
    try:
        going_back = int(draft.get("stage")) < int(orders[replaces].get("Stage"))
    except (TypeError, ValueError):
        return []  # A bad stage is reported by the scenario check.
    if going_back:
        return [f"stage {draft['stage']} is earlier than order {replaces}'s stage {orders[replaces]['Stage']}"]
    return []


def town_key(name):
    """The same town typed with other accents, apostrophes or capitals is still that town."""
    return unicodedata.normalize("NFC", name).replace("\u2019", "'").casefold()


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
        elif {town_key(town) for town in towns} != {town_key(town) for town in expected}:
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
    """The order's text. It has no approver line: the script can't know who approved.

    Town names come from the scenario, so a draft's spelling never reaches the order.
    """
    scenario = load_scenario()
    release = find_release(scenario, draft["stage"], draft["release_id"])
    towns = sorted(town["name"] for town in at_risk_towns(scenario, release["release_m3s"]))
    lines = [
        BOOKEND,
        "",
        f"Package: {draft['package_id']}",
        f"Issuing office: {draft['issuing_office']}",
        f"Stage: {draft['stage']}",
        f"Release: {draft['release_id']}, {draft['release_m3s']} m3/s (synthetic)",
        f"Towns: {', '.join(towns)}",
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
