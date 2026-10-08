"""One food scan and one hunger trial. The crawl does not push these guids."""
import argparse
import json
import re
import sys
import time
from pathlib import Path

from . import atlas, pace, telemetry
from .crawl import _classify, _from_verdict, _live_rows, _verdict_row
from .mcp_server import CommandFailed, DomusTools, SafetyError
from .paths import Paths
from .vendor.schema import PROBE_VERSION

SNACK_GUID = 13397
COOK_GUID = 13388
# Real seconds at normal pace (the verdict comes when the game finishes the meal). W3h: the wait
# is stretched by slow_time (pace.game_budget), so it covers the same game time when the clock is slowed.
EAT_TIMEOUT_S = 700.0


def _rows(path):
    found = []
    with Path(path).open("rb") as handle:
        for raw in handle:
            if not raw.endswith(b"\n"):
                break
            found.append(json.loads(raw))
    return found


def _newest_preflight(atlas_dir):
    folder = Path(atlas_dir)
    files = [path for path in folder.glob("preflight_*.jsonl")
             if path.is_file() and not path.name.endswith(".partial")]
    if not files:
        return None
    newest = max(files, key=lambda path: (path.stat().st_mtime_ns, path.name))
    return _rows(newest)


def latest_food(atlas_dir):
    folder = Path(atlas_dir)
    files = [path for path in folder.glob("food_*.jsonl")
             if path.is_file() and not path.name.endswith(".partial")]
    if not files:
        raise FileNotFoundError("no food scan")
    return max(files, key=lambda path: (path.stat().st_mtime_ns, path.name))


def _footer(path):
    rows = _rows(path)
    if rows and rows[-1].get("kind") == "food_footer":
        return rows
    return None


def wait_footer(atlas_dir, since, timeout, sleep):
    deadline = time.monotonic() + timeout
    while True:
        folder = Path(atlas_dir)
        files = [path for path in folder.glob("food_*.jsonl")
                 if path.is_file() and not path.name.endswith(".partial")
                 and path.stat().st_mtime >= since]
        files.sort(key=lambda path: (path.stat().st_mtime_ns, path.name))
        for path in reversed(files):
            rows = _footer(path)
            if rows is not None:
                return path, rows
        if time.monotonic() >= deadline:
            raise TimeoutError("food scan footer")
        sleep(0.25)


def errors_of(rows):
    """D10: an all-error scan printed 706 rows of None. Count and show the reasons."""
    found = {}
    for row in rows:
        if row.get("kind") in ("food_affordance", "food_menu") and row.get("error"):
            key = str(row.get("error"))[:120]
            found[key] = found.get(key, 0) + 1
    return sorted(found.items(), key=lambda item: -item[1])


def summarize(rows):
    menus = {}
    for row in rows:
        if row.get("kind") != "food_menu" or row.get("error"):
            continue
        menus.setdefault(str(row.get("object_id")), []).append(row)
    table = []
    for row in rows:
        if row.get("kind") != "food_affordance" or row.get("error"):
            continue
        items = menus.get(str(row.get("object_id")), [])
        enabled = [item for item in items if item.get("is_enable") is True]
        prices = [item.get("price") for item in enabled
                  if isinstance(item.get("price"), (int, float)) and not isinstance(item.get("price"), bool)]
        table.append({
            "route": row.get("food_route"),
            "guid64": row.get("guid64"),
            "name": row.get("name"),
            "excluded": row.get("excluded"),
            "object_id": row.get("object_id"),
            "menu": len(items),
            "enabled": len(enabled),
            "cheapest": min(prices) if prices else None,
        })
    return table


def menus_of(rows):
    """D19-D21: one line per scanned menu (object, the class that offers it)."""
    found = {}
    for row in rows:
        if row.get("kind") != "food_menu" or row.get("error"):
            continue
        key = (str(row.get("object_id")), row.get("guid64"))
        item = found.setdefault(key, {"object_id": key[0], "guid64": key[1], "recipes": 0,
                                      "enabled": 0, "prices": [], "names": []})
        item["recipes"] += 1
        if row.get("is_enable") is True:
            item["enabled"] += 1
        price = row.get("price")
        if isinstance(price, (int, float)) and not isinstance(price, bool):
            item["prices"].append(price)
        if len(item["names"]) < 5 and row.get("recipe_name"):
            item["names"].append(row.get("recipe_name"))
    menus = []
    for item in found.values():
        prices = item.pop("prices")
        item["price_min"] = min(prices) if prices else None
        item["price_max"] = max(prices) if prices else None
        menus.append(item)
    return menus


def report(rows):
    """D21: label every column; food routes first, then the rest, then menus."""
    table = summarize(rows)
    table.sort(key=lambda row: (row["route"] is None, str(row["name"])))
    lines = []
    for row in table:
        lines.append("route=%s guid=%s %s obj=%s excluded=%s" % (
            row["route"], row["guid64"], row["name"], row["object_id"], row["excluded"]))
    menus = menus_of(rows)
    for menu in menus:
        lines.append("menu obj=%s via=%s recipes=%d enabled=%d price=%s-%s e.g. %s" % (
            menu["object_id"], menu["guid64"], menu["recipes"], menu["enabled"],
            menu["price_min"], menu["price_max"], ", ".join(menu["names"])))
    errors = errors_of(rows)
    for text, count in errors[:5]:
        lines.append("error x%d %s" % (count, text))
    lines.append("rows %d routes %d menus %d errors %d" % (
        len(table), sum(1 for row in table if row["route"]), len(menus),
        sum(count for _text, count in errors)))
    return lines


def _refused(preflight_rows, object_id, guid):
    for row in preflight_rows or ():
        if row.get("kind") != "preflight":
            continue
        try:
            same = str(row.get("object_id")) == str(object_id) and int(row.get("guid64")) == int(guid)
        except (TypeError, ValueError):
            continue
        if same and row.get("ok") is False:
            return True
    return False


def _rank(row):
    route = row.get("food_route")
    name = str(row.get("name") or "").lower()
    try:
        guid = int(row.get("guid64"))
    except (TypeError, ValueError):
        return None
    if route == "auto_pick" and ("leftover" in name or "snack" in name):
        return 0
    if route == "auto_craft" and guid == SNACK_GUID:
        return 1
    if route == "auto_craft" and guid == COOK_GUID:
        return 2
    return None


def choose(rows, preflight_rows):
    ranked = []
    for row in rows:
        if row.get("kind") != "food_affordance" or row.get("error"):
            continue
        rank = _rank(row)
        if rank is None:
            continue
        if _refused(preflight_rows, row.get("object_id"), row.get("guid64")):
            continue
        ranked.append((rank, row))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]


def _hunger_text(detail):
    found = re.search(r"hunger=([^\s]+)", detail or "")
    if not found:
        return "?->?"
    return found.group(1)


def _session(paths):
    try:
        return telemetry.latest_session(paths=paths).stem
    except FileNotFoundError:
        return "none"


def scan(client, timeout=120, sleep=time.sleep):
    since = time.time()
    client.command("food_scan", {})
    _path, rows = wait_footer(client.paths.atlas_dir, since, timeout, sleep)
    return rows


def fallback_rows(preflight_rows):
    """D10: without a usable scan, the probe-approved fridge routes still feed her.
    The probe decides the card from the class (food_route), not from this row."""
    found = []
    for row in preflight_rows or ():
        if row.get("kind") != "preflight" or row.get("ok") is not True:
            continue
        try:
            guid = int(row.get("guid64"))
        except (TypeError, ValueError):
            continue
        if guid in (SNACK_GUID, COOK_GUID):
            found.append({"kind": "food_affordance", "object_id": row.get("object_id"),
                          "guid64": guid, "name": row.get("name"),
                          "food_route": "auto_craft"})
    return found


def eat(client, timeout=EAT_TIMEOUT_S, sleep=time.sleep, monotonic=time.monotonic,
        telemetry_rows=None, slow_time=1.0):
    status = client.checked_status().result
    if status.get("state") != "SAMPLING":
        raise SafetyError("state=%s" % status.get("state"))
    if status.get("armed_name") != "LAB_E1_FORK":
        raise SafetyError("armed_name=%s" % status.get("armed_name"))
    if status.get("calibrate"):
        raise SafetyError("calibrate")
    path = latest_food(client.paths.atlas_dir)
    rows = _rows(path)
    build = None
    for row in rows:
        if row.get("kind") == "food_header":
            build = row.get("sims_build")
    if not build:
        raise ValueError("food scan has no sims_build")
    preflight = _newest_preflight(path.parent)
    picked = choose(rows, preflight)
    if picked is None:
        picked = choose(fallback_rows(preflight), preflight)
    if picked is None:
        print("eat no-route")
        return 2
    try:
        reply = client.command("trial", {
            "object_id": str(picked["object_id"]), "guid64": str(picked["guid64"])})
    except CommandFailed as error:
        reply = error.reply
    kind, experiment_id, code = _classify((reply.result or {}).get("lines"))
    session = _session(client.paths)
    if kind == "TRIAL_PUSHED":
        deadline = monotonic() + pace.game_budget(timeout, slow_time)
        found = None
        while monotonic() < deadline:
            source = telemetry_rows() if telemetry_rows else _live_rows(client.paths)
            found = _verdict_row(source, experiment_id)
            if found:
                break
            sleep(0.25)
        source = telemetry_rows() if telemetry_rows else _live_rows(client.paths)
        if found is None:
            outcome, code, ambiguous, tuning = "TIMEOUT", "TIMEOUT", None, picked.get("name")
            detail = ""
        else:
            outcome, code, ambiguous, tuning = _from_verdict(found, picked.get("name"))
            detail = (found.get("e2") or {}).get("detail") or ""
        experiment_key = experiment_id
    else:
        outcome = kind if kind in ("PUSH_FAILED", "TRIAL_REJECT", "STALE_TARGET", "PUSH_REFUSED") else "TRIAL_REJECT"
        experiment_key = "%s:food:%s" % (session, picked.get("guid64"))
        ambiguous = None
        tuning = picked.get("name")
        detail = ""
        code = code or outcome
    atlas.record_trial(
        client.paths.atlas_db, build, experiment_key, int(picked["guid64"]),
        str(picked["object_id"]), outcome, code, ambiguous, tuning, session,
        probe_version=PROBE_VERSION)
    print("eat route=%s verdict=%s hunger=%s" % (
        picked.get("food_route"), outcome, _hunger_text(detail)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--eat", action="store_true")
    args = parser.parse_args(argv)
    if args.scan == args.eat:
        print("pass one of --scan or --eat", file=sys.stderr)
        return 1
    client = DomusTools(paths=Paths.from_env())
    try:
        if args.scan:
            for line in report(scan(client)):
                print(line)
            return 0
        return eat(client, slow_time=pace.configured_slow_time(client.paths.data_dir))
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
