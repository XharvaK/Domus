"""Game-thread snapshot helpers that return immutable plain data."""


def entry_key(entry):
    return hex(id(entry))


def minimal_interaction(entry):
    return {
        "entry_key": entry_key(entry),
        "interaction_id": None,
        "affordance_id": None,
        "affordance_text": None,
        "target_id": None,
        "source_raw": None,
        "source_norm": "UNKNOWN",
        "source_confidence": "UNKNOWN",
        "present": True,
    }


def merge_interactions(queued, running, describe):
    """Merge two bounded ordered views while retaining membership provenance."""
    queue_items, queue_truncated = _bounded_items(queued)
    running_items, running_truncated = _bounded_items(running)
    merged = {}
    order = []
    for item, membership in tuple((item, "QUEUED") for item in queue_items) + \
            tuple((item, "RUNNING") for item in running_items):
        key = entry_key(item)
        if key not in merged:
            row = dict(describe(item))
            row["entry_key"] = key
            row["membership"] = membership
            merged[key] = row
            order.append(key)
        elif merged[key]["membership"] != membership:
            merged[key]["membership"] = "QUEUED_AND_RUNNING"
    return [merged[key] for key in order], queue_truncated, running_truncated


def _bounded_items(items):
    bounded = []
    try:
        known_length = len(items)
    except (TypeError, AttributeError):
        known_length = None
    iterator = iter(items)
    while len(bounded) < 8:
        try:
            bounded.append(next(iterator))
        except StopIteration:
            break
    if known_length is None:
        # An unsized live iterator cannot prove that its eighth item is the
        # complete view without consuming an unbounded tail. Keep the sample
        # bounded and report the conservative completeness result.
        truncated = len(bounded) == 8
    else:
        truncated = known_length > 8
    return bounded, truncated


def interactions_complete(queue_truncated, running_truncated, capture_complete):
    return bool(capture_complete) and not queue_truncated and not running_truncated


def _complete_observation(observation):
    if not isinstance(observation, dict):
        return False
    interactions = observation.get("interactions")
    return (observation.get("observation_complete") is True and
            isinstance(interactions, dict) and
            interactions.get("observation_complete") is True)


def appeared_entry_keys(previous, current):
    if not _complete_observation(previous) or not _complete_observation(current):
        return []
    if previous.get("telemetry_session_id") != current.get("telemetry_session_id"):
        return []
    old = set()
    for item in previous["interactions"].get("observed", []):
        if item.get("entry_key") is not None:
            old.add(item["entry_key"])
    result = []
    for item in current["interactions"].get("observed", []):
        key = item.get("entry_key")
        if key is not None and key not in old and item.get("present") is True:
            result.append(key)
    return result


def freeze_plain(value):
    """Copy only JSON-like data so live game objects cannot cross the queue."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [freeze_plain(item) for item in value]
    if isinstance(value, tuple):
        return [freeze_plain(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("plain-data keys must be strings")
            result[key] = freeze_plain(item)
        return result
    raise TypeError("live object escaped snapshot copy-out")


def _encoded_bytes(row):
    import json
    return len(json.dumps(row, ensure_ascii=True, separators=(",", ":"),
                          sort_keys=False).encode("utf-8"))


def _mark_truncated(row):
    interactions = row.get("interactions")
    if interactions is not None:
        interactions = dict(interactions)
        interactions["observation_complete"] = False
        row["interactions"] = interactions
    row["observation_complete"] = False


def apply_size_budget(row):
    """Trim a presence_snapshot until it fits the record cap.

    DS3 drop order: signals beyond 8 (hidden and light ones sort last), then
    presence beyond 4 (farthest sort last), then game_text, and social last:
    someone addressing her is the most important fact in the row. Sets the
    existing truncation flags and returns the row.
    """
    from . import schema
    if row.get("event_kind") != "presence_snapshot":
        return row
    if _encoded_bytes(row) <= schema.MAX_SERIALIZED_RECORD_BYTES:
        return row
    if len(row.get("sim_signals", ())) > 8:
        row["sim_signals"] = list(row["sim_signals"][:8])
        _mark_truncated(row)
        if _encoded_bytes(row) <= schema.MAX_SERIALIZED_RECORD_BYTES:
            return row
    objects = row.get("objects")
    if isinstance(objects, dict) and (objects.get("changed") or objects.get("created")
                                      or objects.get("destroyed")):
        # S5: object events go before company; a truncated list says so.
        row["objects"] = dict(objects, changed=[], created=objects["created"][:2],
                              destroyed=objects["destroyed"][:2], truncated=True)
        if _encoded_bytes(row) <= schema.MAX_SERIALIZED_RECORD_BYTES:
            return row
    if len(row.get("presence", ())) > 4:
        row["presence"] = list(row["presence"][:4])
        _mark_truncated(row)
        if _encoded_bytes(row) <= schema.MAX_SERIALIZED_RECORD_BYTES:
            return row
    # S5: relationship detail of the farthest Sims next: labels go, two tracks stay.
    # 2.15.0: so do the traits and careers she knows and her sentiments (flags stay).
    for item in reversed(row.get("presence", ())):
        if _encoded_bytes(row) <= schema.MAX_SERIALIZED_RECORD_BYTES:
            return row
        relationship = item.get("relationship") if isinstance(item, dict) else None
        if not isinstance(relationship, dict):
            continue
        knows = relationship.get("knows")
        if (relationship.get("labels") or len(relationship.get("tracks") or ()) > 2 or
                relationship.get("sentiments") or
                (isinstance(knows, dict) and (knows.get("traits") or knows.get("careers")))):
            trimmed = dict(relationship, labels=[],
                           tracks=list(relationship.get("tracks") or ())[:2])
            if "sentiments" in relationship:
                trimmed["sentiments"] = []
            if isinstance(knows, dict):
                trimmed["knows"] = dict(knows, traits=[],
                                        careers=None if knows.get("careers") is None else [])
            item["relationship"] = trimmed
            _mark_truncated(row)
    # 2.15.2: the situations of other Sims, farthest first, down to the first one each
    # (her own stay whole).
    for item in reversed(row.get("presence", ())):
        if _encoded_bytes(row) <= schema.MAX_SERIALIZED_RECORD_BYTES:
            return row
        if isinstance(item, dict) and not item.get("is_body") and \
                len(item.get("situations") or ()) > 1:
            item["situations"] = item["situations"][:1]
            _mark_truncated(row)
    # 2.15.0: her own traits and skills, the first four of each (personality and
    # highest skills sort first).
    own = row.get("self")
    if isinstance(own, dict) and _encoded_bytes(row) > schema.MAX_SERIALIZED_RECORD_BYTES:
        row["self"] = dict(own, traits=None if own.get("traits") is None else own["traits"][:4],
                           skills=None if own.get("skills") is None else own["skills"][:4])
        _mark_truncated(row)
    for signal in row.get("sim_signals", ()):
        if _encoded_bytes(row) <= schema.MAX_SERIALIZED_RECORD_BYTES:
            return row
        if isinstance(signal, dict) and signal.get("game_text") is not None:
            signal["game_text"] = None
            _mark_truncated(row)
    # 2.15.2: other Sims' situations go before someone addressing her does.
    for item in reversed(row.get("presence", ())):
        if _encoded_bytes(row) <= schema.MAX_SERIALIZED_RECORD_BYTES:
            return row
        if isinstance(item, dict) and not item.get("is_body") and item.get("situations"):
            item["situations"] = []
            _mark_truncated(row)
    # 2.15.2: then the pop-ups, down to the newest two open and two closed (flagged).
    dialogs = row.get("dialogs")
    if isinstance(dialogs, dict) and _encoded_bytes(row) > schema.MAX_SERIALIZED_RECORD_BYTES \
            and (len(dialogs.get("open") or ()) > 2 or len(dialogs.get("closed") or ()) > 2):
        row["dialogs"] = dict(dialogs, open=list(dialogs.get("open") or ())[-2:],
                              closed=list(dialogs.get("closed") or ())[-2:], truncated=True)
    # 2.18.0: picker rows next: the older open dialog's rows first, then the newest one's
    # down to 10, which is still enough to answer from (enabled rows sort first).
    dialogs = row.get("dialogs")
    if isinstance(dialogs, dict):
        opened = list(dialogs.get("open") or ())
        last = len(opened) - 1
        for index, keep in [(i, 0) for i in range(last)] + [(last, 20), (last, 10), (last, 5), (last, 0)]:
            if index < 0 or _encoded_bytes(row) <= schema.MAX_SERIALIZED_RECORD_BYTES:
                break
            entry = opened[index]
            if isinstance(entry, dict) and len(entry.get("rows") or ()) > keep:
                opened[index] = dict(entry, rows=list(entry["rows"])[:keep])
                row["dialogs"] = dict(dialogs, open=opened, truncated=True)
                dialogs = row["dialogs"]
    if _encoded_bytes(row) > schema.MAX_SERIALIZED_RECORD_BYTES and row.get("social"):
        row["social"] = []
        _mark_truncated(row)
    return row


# End of pure snapshot helpers.
