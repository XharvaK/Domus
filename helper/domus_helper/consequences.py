"""S3: what leads where, from two sources that are never mixed.

DECLARED: what the game advertises to its autonomy scorer for an interaction (atlas
autonomy ads). Ads are not rates; they are labelled "advertised".
OBSERVED: what our outcome records saw (S6), grouped by interaction and by origin,
because compound behaviour differs by who started it (C3). Every line carries n, the
conditions known, and the act ids it came from. One observation is labelled as one.
Anything not sensed yet (objects, relationships until S5) is UNKNOWN, never guessed.
Learned consequences belong to her memory, not here.
Design: _Internal/papers/DOMUS_LIVED_WORLD_DESIGN_v0.2.md §4.

    python -m domus_helper.consequences generic_food_Grab
"""
import argparse
import json
import sqlite3
import statistics

from .paths import Paths

CONSEQUENCE_VERSION = 1
FIRST_FOLLOWER_MIN = 15
MAX_PROVENANCE = 5


def declared(atlas_connection, name=None, guid64=None, build=None):
    """The game's own advertised effects for one interaction (by tuning name or guid)."""
    query = "SELECT build, guid64, name, autonomy_ads_json FROM affordances WHERE "
    if guid64 is not None:
        query, args = query + "guid64 = ?", [int(guid64)]
    else:
        query, args = query + "name = ?", [name]
    if build is not None:
        query, args = query + " AND build = ?", args + [build]
    lines = []
    for row_build, row_guid, row_name, ads_json in atlas_connection.execute(query + " ORDER BY build", args):
        try:
            ads = json.loads(ads_json) if ads_json else None
        except ValueError:
            ads = None
        for ad in ads or []:
            amounts = sorted({op.get("amount") for op in ad.get("ops") or []
                              if op.get("advertise") and isinstance(op.get("amount"), (int, float))})
            if not amounts:
                continue
            lines.append({"v": CONSEQUENCE_VERSION, "kind": "DECLARED",
                          "interaction": row_name, "guid64": str(row_guid),
                          "effect": {"type": "NEED", "stat": ad.get("name"),
                                     "advertised": amounts},
                          "provenance": {"atlas_build": row_build}})
    return lines


def _conditions(records):
    company = {"solo" if not r.get("company") else "with company"
               for r in records if r.get("company") is not None}
    return {"origin": records[0]["origin"],
            "company": sorted(company) or ["unknown"]}


def _provenance(records):
    return {"act_ids": [r["act_id"] for r in records[:MAX_PROVENANCE]],
            "more": max(0, len(records) - MAX_PROVENANCE)}


def observed(records, name):
    """Observed consequences of one interaction, one group per origin."""
    groups = {}
    for record in records:
        if record["interaction"]["name"] == name:
            groups.setdefault(record["origin"], []).append(record)
    lines = []
    for origin in sorted(groups):
        group = sorted(groups[origin], key=lambda r: r["act_id"])
        n = len(group)
        base = {"v": CONSEQUENCE_VERSION, "kind": "OBSERVED", "interaction": name, "n": n,
                "conditions": _conditions(group), "provenance": _provenance(group)}
        durations = [r["span"]["game_minutes"] for r in group if r["span"]["game_minutes"] is not None]
        if durations:
            lines.append(dict(base, effect={"type": "DURATION",
                                            "game_minutes_median": statistics.median(durations)}))
        deltas = {}
        for record in group:
            for stat, value in record["needs"]["delta"].items():
                deltas.setdefault(stat, []).append(value)
        for stat in sorted(deltas):
            values = deltas[stat]
            lines.append(dict(base, effect={"type": "NEED", "stat": stat,
                                            "change_median": statistics.median(values),
                                            "seen_in": len(values)}))
        followers = {}
        for record in group:
            first = next((item for item in record["followed_by"]
                          if item["after_minutes"] is not None
                          and item["after_minutes"] <= FIRST_FOLLOWER_MIN), None)
            key = (first["name"], first["origin"]) if first else (None, None)
            followers[key] = followers.get(key, 0) + 1
        for (follower, by), count in sorted(followers.items(), key=lambda kv: (-kv[1], str(kv[0]))):
            effect = ({"type": "FOLLOWED_BY", "interaction": follower, "by": by,
                       "within_game_minutes": FIRST_FOLLOWER_MIN, "times": count}
                      if follower else
                      {"type": "NOTHING_FOLLOWED", "within_game_minutes": FIRST_FOLLOWER_MIN,
                       "times": count})
            lines.append(dict(base, effect=effect))
        gained = {}
        sensed = [r for r in group if r.get("moodlets") is not None]
        for record in sensed:
            for moodlet in record["moodlets"]["gained"]:
                gained[moodlet["name"]] = gained.get(moodlet["name"], 0) + 1
        for moodlet, count in sorted(gained.items()):
            lines.append(dict(base, effect={"type": "MOODLET", "name": moodlet, "times": count,
                                            "sensed_in": len(sensed)}))
        lines.append(dict(base, effect={"type": "UNKNOWN",
                                        "what": sorted({item for r in group for item in r["unknown"]})}))
    return lines


def for_interaction(name, records, atlas_connection=None):
    return {"interaction": name,
            "declared": declared(atlas_connection, name=name) if atlas_connection else [],
            "observed": observed(records, name)}


def load_records(paths):
    folder = paths.data_dir / "outcomes"
    records = []
    for path in sorted(folder.glob("*.jsonl")) if folder.is_dir() else []:
        with path.open(encoding="utf-8") as handle:
            records.extend(json.loads(line) for line in handle if line.strip())
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name")
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    atlas = paths.data_dir / "atlas.db"
    connection = sqlite3.connect("file:%s?mode=ro" % atlas.as_posix(), uri=True) if atlas.is_file() else None
    try:
        print(json.dumps(for_interaction(args.name, load_records(paths), connection), indent=1))
    finally:
        if connection is not None:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
