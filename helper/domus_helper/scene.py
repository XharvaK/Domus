"""S2: the scene in three layers (near, far, available), from a situation scan.

Facts only, in the game's own terms. Deterministic order (layer, distance, id);
nothing ranked by what she might want; every omission is counted, never silent.
Design: _Internal/papers/DOMUS_LIVED_WORLD_DESIGN_v0.2.md §3.

    python -m domus_helper.scene            # ask the probe for a scan, print the layers
    python -m domus_helper.scene --file F   # layers from an existing situation file
"""
import argparse
import json
import re
import time

NEAR_METERS = 4.0
BUDGET = {"near": 4096, "far": 1280, "available": 768}
# Game state values worth a far-layer line. These are the game's own value names.
NOTABLE = ("Spoiled", "Stale", "Dirty", "Broken", "Burning", "Fire", "Unflushed",
           "Flooded", "Smelly")
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


def _name(row, resolve):
    craft = row.get("craft") or {}
    servings = _servings(row.get("stats"))
    keys = ([craft.get("multi_name_key")] if servings and servings > 1 else []) + [craft.get("name_key")]
    if resolve is not None:
        for key in keys:
            if key:
                try:
                    text = resolve(key)
                except Exception:
                    text = None
                if text:
                    return text, "GAME_TEXT"
    if craft.get("recipe"):
        return craft["recipe"], "TUNING_NAME"
    return row.get("class") or "unknown", "TUNING_NAME"


def notable(states):
    return sorted(value for value in (states or {}).values()
                  if value and any(word in value for word in NOTABLE))


def near_fact(row, body, resolve, offers):
    name, source = _name(row, resolve)
    craft = row.get("craft") or {}
    fact = {"id": row["object_id"], "name": name, "name_source": source,
            "class": row.get("class"), "room": row.get("room"),
            "distance_m": _distance(row.get("position"), (body or {}).get("position")),
            "states": row.get("states") or {}}
    servings = _servings(row.get("stats"))
    if servings is not None:
        fact["servings_left"] = servings
    if craft.get("crafter") or craft.get("crafter_id"):
        fact["made_by"] = craft.get("crafter") or craft.get("crafter_id")
    if offers is not None:
        fact["offers"] = offers
    return fact


def offers_for(object_id, preflight_rows):
    """The game's own options for one object: allowed by name, refused with reason."""
    if preflight_rows is None:
        return None
    allowed, refused = [], []
    for row in preflight_rows:
        if row.get("kind") != "preflight" or str(row.get("object_id")) != object_id:
            continue
        reason = row.get("reason") or ""
        if reason in ("deny_name", "picker") or str(reason).startswith("Interaction is not valid"):
            continue
        if row.get("ok"):
            allowed.append(row.get("name"))
        else:
            refused.append({"name": row.get("name"), "game_reason": str(reason)[:100]})
    return {"allowed": sorted(set(allowed)), "refused": refused[:6]}


def layers(header, objects, *, resolve=None, preflight_rows=None):
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
             "near": [], "near_omitted": 0, "far": [], "far_omitted": 0, "available": {}}
    for _, object_id, row in near:
        fact = near_fact(row, body, resolve, offers_for(object_id, preflight_rows))
        if _bytes(scene["near"] + [fact]) > BUDGET["near"]:
            scene["near_omitted"] += 1
            continue
        scene["near"].append(fact)
    for distance, object_id, row in far:
        marks = notable(row.get("states"))
        servings = _servings(row.get("stats"))
        if not marks and servings is None and not row.get("craft"):
            continue
        name, _ = _name(row, resolve)
        line = {"id": object_id, "name": name, "room": row.get("room"),
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
    scene = layers(header, objects, resolve=Resolver(paths), preflight_rows=rows)
    print(json.dumps(scene, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
