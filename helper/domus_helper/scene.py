"""S2: the scene in three layers (near, far, available), from a situation scan.

Facts only, in the game's own terms. Deterministic order (layer, distance, id);
nothing ranked by what she might want; every omission is counted, never silent.

Near has two tiers so a lamp at 0.3 m cannot crowd out a meal at 2 m: every near
object first gets a short line (name, distance, condition, servings, maker); then
objects with a game condition, and after them the rest, each by distance, get
their full states and offers while the budget lasts.
Design: _Internal/papers/DOMUS_LIVED_WORLD_DESIGN_v0.2.md §3.

    python -m domus_helper.scene            # ask the probe for a scan, print the layers
    python -m domus_helper.scene --file F   # layers from an existing situation file
"""
import argparse
import json
import re
import time

NEAR_METERS = 4.0
BUDGET = {"near": 8192, "far": 1280, "available": 768}
# Game state values worth a far-layer line. These are the game's own value names,
# matched on the value's last word ("Freshness_Spoiled"), never inside a negation
# ("FireState_..._Not_Burning", "Brokenness_Unbroken").
NOTABLE = ("Spoiled", "Stale", "Dirty", "Broken", "Burning", "Fire", "Unflushed",
           "Flooded", "Smelly")
_NEGATIONS = ("Not", "No", "Non")
_FAMILY = re.compile(r"object_([A-Za-z]+)")


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def load(path):
    header, objects, footer = None, [], None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("kind") == "situation_header":
                header = row
            elif row.get("kind") == "object":
                objects.append(row)
            elif row.get("kind") == "situation_footer":
                footer = row
    return header, objects, footer


def family(class_name):
    match = _FAMILY.match(class_name or "")
    return match.group(1) if match else (class_name or "unknown")


def _distance(a, b):
    if not a or not b:
        return None
    return round(((a["x"] - b["x"]) ** 2 + (a["z"] - b["z"]) ** 2) ** 0.5, 1)


def _servings(stats):
    for name, value in (stats or {}).items():
        if "serving" in name.lower():
            return value
    return None


def _text(resolve, key):
    if resolve is None or not key:
        return None
    try:
        return resolve(key) or None
    except Exception:
        return None


def _name(row, resolve, catalog=None):
    """The game's display name: the recipe's for crafted things (multi_serving_name is
    the portion label, "Party Size (8)", never the dish's name), else the catalogue's
    ("Pure Simplicity Sink"), else the tuning name."""
    craft = row.get("craft") or {}
    text = _text(resolve, craft.get("name_key"))
    if text:
        return text, "GAME_TEXT"
    entry = _catalog(catalog, row)
    text = _text(resolve, entry.get("name_key")) if entry else None
    if text:
        return text, "CATALOG"
    if craft.get("recipe"):
        return craft["recipe"], "TUNING_NAME"
    return row.get("class") or "unknown", "TUNING_NAME"


def _catalog(catalog, row):
    if catalog is None or not row.get("definition_id"):
        return None
    try:
        return catalog(row["definition_id"])
    except Exception:
        return None


def _is_notable(value):
    words = (value or "").split("_")
    last = words[-1]
    if len(words) > 1 and words[-2] in _NEGATIONS:
        return False
    if any(last.startswith(neg) and last[len(neg):][:1].isupper() for neg in _NEGATIONS):
        return False
    return any(last.endswith(word) for word in NOTABLE)


def notable(states):
    return sorted(value for value in (states or {}).values() if _is_notable(value))


def condition(states):
    """Freshness as the game holds it, plus anything notable."""
    states = states or {}
    found = set(notable(states))
    if states.get("Freshness"):
        found.add(states["Freshness"])
    return sorted(found)


def near_line(row, body, resolve, catalog=None):
    """The short line every near object gets. `kind` is the tuning family, so a
    catalogue name ("The YumCooker") still reads as a stove."""
    name, source = _name(row, resolve, catalog)
    craft = row.get("craft") or {}
    fact = {"id": row["object_id"], "name": name, "name_source": source,
            "kind": family(row.get("class")), "room": row.get("room"),
            "distance_m": _distance(row.get("position"), (body or {}).get("position"))}
    marks = condition(row.get("states"))
    if marks:
        fact["condition"] = marks
    servings = _servings(row.get("stats"))
    if servings is not None:
        fact["servings_left"] = servings
    portion = _text(resolve, craft.get("multi_name_key"))
    if portion:
        fact["portion"] = portion
    if craft.get("crafter") or craft.get("crafter_id"):
        fact["made_by"] = craft.get("crafter") or craft.get("crafter_id")
    if row.get("in_use"):
        # S1 extras (2.14.0): who holds it, by Sim id.
        fact["in_use_by"] = row.get("used_by") or ["unknown"]
    freshness = (row.get("rates") or {}).get("commodity_freshness")
    if freshness is not None:
        fact["freshness_per_minute"] = freshness
    return fact


def near_fact(row, body, resolve, offers, catalog=None):
    fact = near_line(row, body, resolve, catalog)
    fact["class"] = row.get("class")
    entry = _catalog(catalog, row)
    if entry and entry.get("price") is not None:
        fact["catalog_price"] = entry["price"]
    fact["states"] = row.get("states") or {}
    if offers is not None:
        fact["offers"] = offers
    return fact


def _has_condition(row):
    return bool(notable(row.get("states")) or _servings(row.get("stats")) is not None
                or row.get("craft"))


def offers_for(object_id, preflight_rows, resolve=None):
    """The game's own options for one object: allowed by name, refused with reason."""
    if preflight_rows is None:
        return None
    allowed, refused, seen = [], [], False
    for row in preflight_rows:
        if row.get("kind") != "preflight" or str(row.get("object_id")) != object_id:
            continue
        seen = True
        reason = row.get("reason") or ""
        if reason in ("deny_name", "picker") or str(reason).startswith("Interaction is not valid"):
            continue
        if row.get("ok"):
            allowed.append(row.get("name"))
        else:
            sentence = _text(resolve, row.get("reason_key"))
            if isinstance(sentence, str) and sentence.strip():
                game_reason = sentence.strip()[:200]
            else:
                game_reason = str(reason)[:100]
            refused.append({"name": row.get("name"), "game_reason": game_reason})
    if not seen:
        return None  # not checked (e.g. the object is newer than the preflight), not "no options"
    return {"allowed": sorted(set(allowed)), "refused": refused[:6]}


def seen_here(item, body):
    """SS4-v2: is this Sim one she can see? Indoors (her body in a real room): the same room and the
    same level. Outdoors (her room None or "0"): within NEAR_METERS and on the same level. Being
    addressed does not make a Sim seen, and nothing is seen through a wall."""
    if not isinstance(item, dict) or not isinstance(body, dict):
        return False
    level = item.get("level")
    if type(level) is not int or level != body.get("level"):
        return False
    body_room = body.get("room")
    if body_room is not None and str(body_room) != "0":
        return item.get("room") is not None and str(item["room"]) == str(body_room)
    distance = item.get("distance_m")
    if isinstance(distance, bool) or not isinstance(distance, (int, float)):
        return False
    return distance <= NEAR_METERS


def layers(header, objects, *, resolve=None, preflight_rows=None, catalog=None):
    body = (header or {}).get("body") or {}
    body_room = body.get("room")
    near, far = [], []
    for row in objects:
        distance = _distance(row.get("position"), body.get("position"))
        same_room = body_room is not None and row.get("room") == body_room
        close = distance is not None and distance <= NEAR_METERS
        (near if same_room or close else far).append((distance if distance is not None else 1e9,
                                                      row["object_id"], row))
    near.sort(key=lambda item: (item[0], item[1]))
    far.sort(key=lambda item: (item[0], item[1]))
    scene = {"body": {"room": body_room, "position": body.get("position")},
             "near": [], "near_omitted": 0, "near_detail_omitted": 0,
             "far": [], "far_omitted": 0, "available": {}}
    kept = []
    for _, object_id, row in near:
        line = near_line(row, body, resolve, catalog)
        if _bytes(scene["near"] + [line]) > BUDGET["near"]:
            scene["near_omitted"] += 1
            continue
        scene["near"].append(line)
        kept.append(row)
    order = ([i for i, row in enumerate(kept) if _has_condition(row)]
             + [i for i, row in enumerate(kept) if not _has_condition(row)])
    for index in order:
        row = kept[index]
        fact = near_fact(row, body, resolve, offers_for(row["object_id"], preflight_rows, resolve),
                         catalog)
        trial = list(scene["near"])
        trial[index] = fact
        if _bytes(trial) > BUDGET["near"]:
            scene["near_detail_omitted"] += 1
            continue
        scene["near"] = trial
    for distance, object_id, row in far:
        marks = notable(row.get("states"))
        servings = _servings(row.get("stats"))
        if not marks and servings is None and not row.get("craft"):
            continue
        name, _ = _name(row, resolve, catalog)
        line = {"id": object_id, "name": name, "kind": family(row.get("class")),
                "room": row.get("room"),
                "distance_m": None if distance >= 1e9 else distance}
        if marks:
            line["states"] = marks
        if servings is not None:
            line["servings_left"] = servings
        if _bytes(scene["far"] + [line]) > BUDGET["far"]:
            scene["far_omitted"] += 1
            continue
        scene["far"].append(line)
    counts = {}
    for row in objects:
        kind = family(row.get("class"))
        counts[kind] = counts.get(kind, 0) + 1
    for kind in sorted(counts, key=lambda name: (-counts[name], name)):
        trial = dict(scene["available"])
        trial[kind] = counts[kind]
        if _bytes(trial) > BUDGET["available"]:
            scene["available_omitted_kinds"] = len(counts) - len(scene["available"])
            break
        scene["available"] = trial
    return scene


def _latest(folder, prefix):
    found = sorted(folder.glob(prefix + "_*.jsonl"), key=lambda path: path.stat().st_mtime)
    return found[-1] if found else None


def main(argv=None):
    from .mcp_server import tools
    from .paths import Paths
    from .catalog import Catalog
    from .strings import Resolver
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--file")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    path = args.file
    if path is None:
        client = tools()
        client.command("situation_scan", {})
        deadline = time.time() + args.timeout_s
        while time.time() < deadline:
            state = client.command("status", {}).result.get("situation", {})
            if state.get("state") in ("done", "error"):
                path = state.get("file")
                break
            time.sleep(1)
        if path is None:
            raise SystemExit("situation scan did not finish")
    header, objects, _ = load(path)
    preflight = _latest(paths.atlas_dir, "preflight")
    rows = None
    if preflight is not None:
        with open(preflight, encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
    scene = layers(header, objects, resolve=Resolver(paths), preflight_rows=rows,
                   catalog=Catalog(paths))
    print(json.dumps(scene, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
