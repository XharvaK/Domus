"""Relief survey: an opt-in crawl mode that measures what each cure refills.

Telemetry, not Ashley's policy (Owner, 2026-10-04). With real needs on, when a body
need is low the crawl pushes one probe-approved cure for it (toilet, bed, shower,
the fridge's snack) and logs needs before, at the verdict, and when she finishes.
That is the reference Ashley reads; her own Thought decides what she does. Off
unless `crawl --relief-survey`, and that crawl runs only with `--lab` (the lab save, never HOME: the User, 2026-10-12).
This module has no entry point of its own. Relief names are the probe's own (vendored e2_trial).
"""
from .vendor import e2_trial

BODY_MOTIVES = ("bladder", "hunger", "energy", "hygiene")
# Survey starts at this value (motive scale 0-100), well before distress (20).
SURVEY_AT = 35
SNACK_GUID = 13397
COOK_GUID = 13388
# Plain variants first; the steamy shower and the nap are surveyed when the plain
# one is not offered.
PREFERRED = {
    "energy": ("bed_sleep", "sleep", "nap"),
    "bladder": ("toilet-use-sitting", "toilet"),
    "hygiene": ("shower_takeshower", "takeshower", "bath"),
}


def motives_of(row):
    found = {}
    for item in (row or {}).get("motives") or ():
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        found[item.get("id")] = value
    return found


def low_need(motives):
    """The lowest body motive at or under SURVEY_AT, or None."""
    low = [(value, BODY_MOTIVES.index(key), key) for key, value in motives.items()
           if key in BODY_MOTIVES and value <= SURVEY_AT]
    if not low:
        return None
    low.sort()
    return low[0][2]


def _ok_rows(preflight_rows):
    for row in preflight_rows or ():
        if row.get("kind") != "preflight" or row.get("ok") is not True:
            continue
        try:
            guid = int(row.get("guid64"))
        except (TypeError, ValueError):
            continue
        yield guid, str(row.get("object_id")), str(row.get("name") or "")


def cure_for(motive, preflight_rows):
    """One preflight-approved cure for this motive: {guid64, object_id, name, relief}."""
    rows = list(_ok_rows(preflight_rows))
    if motive == "hunger":
        for wanted in (SNACK_GUID, COOK_GUID):
            for guid, object_id, name in rows:
                if guid == wanted:
                    return {"guid64": guid, "object_id": object_id, "name": name,
                            "relief": motive}
        return None
    cures = [(guid, object_id, name) for guid, object_id, name in rows
             if e2_trial.relieves(motive, name, None)]
    if not cures:
        return None

    def rank(item):
        low = item[2].lower()
        parts = PREFERRED.get(motive, ())
        for index, part in enumerate(parts):
            if part in low:
                return (index, len(low), item[0])
        return (len(parts), len(low), item[0])

    guid, object_id, name = min(cures, key=rank)
    return {"guid64": guid, "object_id": object_id, "name": name, "relief": motive}
