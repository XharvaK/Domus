"""Pure v1 observation builder. No clock and no I/O."""
import json
import re

_LINEAGE = re.compile(r"[A-Z_]{1,32}")
_FACTS_LIMIT = 2048
_PORTRAIT_LIMIT = 8192
_WINDOW_MS = 600_000


def _bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _text(value, fallback, limit=64):
    if value is None:
        return fallback
    text = str(value)
    if not 1 <= len(text) <= limit:
        return fallback
    return text


def _fit_strings(facts):
    fitted = dict(facts)
    while _bytes(fitted) > _FACTS_LIMIT:
        key = None
        longest = 0
        for name, value in fitted.items():
            if isinstance(value, str) and len(value) > longest:
                key = name
                longest = len(value)
        if key is None or longest == 0:
            break
        excess = _bytes(fitted) - _FACTS_LIMIT
        fitted[key] = fitted[key][:-excess] if excess < longest else ""
    return fitted


def _portrait(row):
    row = row or {}
    needs = {}
    for item in row.get("motives") or []:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        needs[str(item["id"])] = {"value": item.get("value"), "band": item.get("band")}
    posture = ((row.get("body") or {}).get("posture") or {}).get("posture_name")
    running = []
    for entry in ((row.get("interactions") or {}).get("observed")) or []:
        if not isinstance(entry, dict) or entry.get("membership") not in ("RUNNING", "QUEUED_AND_RUNNING"):
            continue
        text = entry.get("affordance_text")
        if text is None:
            continue
        running.append(str(text)[:80])
    zone = row.get("zone") or {}
    game = row.get("game") or {}
    portrait = {
        "needs": needs,
        "posture": posture,
        "running": running[:8],
        "zone": {"zone_id": zone.get("zone_id"), "lot_id": zone.get("lot_id")},
        "clock_speed": game.get("clock_speed"),
        "paused": game.get("paused") is True,
    }
    while portrait["running"] and _bytes(portrait) > _PORTRAIT_LIMIT:
        portrait["running"].pop()
    return portrait


def build(decision, ctx):
    row = ctx.get("row") or {}
    source = row.get("wall_timestamp_ms")
    if type(source) is not int or source < 0:
        source = 0
    lineage = ctx.get("lineage_class")
    if not isinstance(lineage, str) or _LINEAGE.fullmatch(lineage) is None:
        lineage = "PENDING"
    percepts = []
    for percept, salience in decision.percepts[:32]:
        try:
            score = float(salience)
        except (TypeError, ValueError):
            score = 0.0
        if score < 0:
            score = 0.0
        if score > 1:
            score = 1.0
        facts = dict(percept.facts)
        facts.update({
            "subject": percept.subject,
            "object": percept.object,
            "bucket": percept.bucket,
            "urgency": percept.urgency,
            "reason": decision.reason,
        })
        percepts.append({"kind": percept.kind, "salience": score, "facts": _fit_strings(facts)})
    seq = ctx["obs_seq"]
    return {
        "v": 1,
        "observation_id": "%s.%s" % (ctx["helper_session"], seq),
        "world": _text(None if ctx.get("slot_id") is None else "slot%s" % ctx.get("slot_id"), "unknown"),
        "branch": _text(ctx.get("guid"), "unknown"),
        "session": _text(row.get("telemetry_session_id"), "unknown"),
        "attachment": _text(ctx["helper_session"], "unknown"),
        "body": _text((row.get("body") or {}).get("sim_id"), "unknown"),
        "snapshot": _text(None if row.get("written_sequence") is None else str(row.get("written_sequence")), "unknown"),
        "seq": seq,
        "source_time_ms": source,
        "expires_at_ms": source + _WINDOW_MS,
        "lineage_class": lineage,
        "percepts": percepts,
        "portrait": _portrait(row),
    }
