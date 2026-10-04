"""Pure class cards for harness trials. No game imports and no I/O.

Posture repeats the seated test. Need, interaction, and social add no
actuation. An ambiguity is not an effect.
"""

NEED_MIN_NET_DELTA = 5.0
# Motive values are lazy caches. DA5 calibration 2026-10-04: median age_ticks
# 5417, median age when a value changes 2092, p90 19614. 30000 ticks is 20
# sim-minutes and blocks only readings staler than that observed tail.
NEED_FRESH_TICKS = 30000
NEED_CONTROL_TICKS = 45000  # 30 sim-minutes of control rows before the push
NEED_GRACE_TICKS = 15000  # 10 sim-minutes after our interaction leaves
GAP_SECONDS = 5.0

CARD_CLASSES = ("posture", "need", "interaction", "social")
CARD_KEYS = ("card_class", "affordance_guid64", "object_id", "signature",
             "motive", "direction", "min_net_delta")
MOTIVES = ("social", "hygiene", "bladder", "energy", "fun", "hunger")
RUNNING_MEMBERSHIPS = ("RUNNING", "QUEUED_AND_RUNNING")
POSTURE_SOURCE = "InteractionSource.POSTURE_GRAPH"

# Schema 4 social rows do not name the other Sim. Schema 5 adds actor_id.
# A social card stores that Sim id in object_id (see validate_card).
SOCIAL_UNOBSERVED = "social_target_unobserved"


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_card(card):
    """Closed card. For card_class "social", object_id is the other Sim's id."""
    if not isinstance(card, dict) or set(card) != set(CARD_KEYS):
        raise ValueError("card shape")
    kind = card.get("card_class")
    if kind not in CARD_CLASSES:
        raise ValueError("card_class")
    guid = card.get("affordance_guid64")
    if guid is not None and (isinstance(guid, bool) or type(guid) is not int):
        raise ValueError("affordance_guid64")
    if card.get("object_id") is not None and not isinstance(card.get("object_id"), str):
        raise ValueError("object_id")
    if not _number(card.get("min_net_delta")):
        raise ValueError("min_net_delta")
    signature = card.get("signature")
    motive = card.get("motive")
    direction = card.get("direction")
    if kind == "posture":
        if signature is not None and not isinstance(signature, str):
            raise ValueError("signature")
        if motive is not None or direction is not None:
            raise ValueError("posture fields")
        return card
    if signature is not None:
        raise ValueError("signature")
    if kind == "need":
        if motive not in MOTIVES:
            raise ValueError("motive")
        if type(direction) is not int or direction not in (1, -1):
            raise ValueError("direction")
        return card
    if motive is not None or direction is not None:
        raise ValueError("unused fields")
    return card


def posture_card(object_id, signature, affordance_guid64=None):
    card = {
        "card_class": "posture",
        "affordance_guid64": affordance_guid64,
        "object_id": object_id,
        "signature": signature,
        "motive": None,
        "direction": None,
        "min_net_delta": NEED_MIN_NET_DELTA,
    }
    return validate_card(card)


def _entries(row):
    return (row.get("interactions") or {}).get("observed") or []


def _posture(row):
    return ((row.get("body") or {}).get("posture")) or {}


def _motive(row, motive_id):
    for item in row.get("motives") or []:
        if isinstance(item, dict) and item.get("id") == motive_id:
            return item
    return None


def _ours(row, interaction_id):
    for entry in _entries(row):
        if entry.get("interaction_id") is not None and entry.get("interaction_id") == interaction_id:
            return entry
    return None


def _running(entry):
    return entry is not None and entry.get("membership") in RUNNING_MEMBERSHIPS


def _game(row):
    game = row.get("game")
    return game if isinstance(game, dict) else {}


def _ticks(row):
    ticks = _game(row).get("ticks")
    if type(ticks) is int:
        return ticks
    return None


def _paused(row):
    return _game(row).get("paused") is True


def _push_tick(rows):
    found = []
    for row in rows:
        ticks = _ticks(row)
        if ticks is not None:
            found.append(ticks)
    if not found:
        return None
    return min(found)


def _control_points(card, control_rows, push_tick):
    """Least-squares inputs in motive points per game tick. Paused rows add none."""
    if type(push_tick) is not int:
        return 0, []
    window_start = push_tick - NEED_CONTROL_TICKS
    points = []
    counted = 0
    for row in control_rows or []:
        if _paused(row):
            continue
        ticks = _ticks(row)
        if ticks is None or ticks >= push_tick or ticks < window_start:
            continue
        counted += 1
        item = _motive(row, card["motive"])
        if item is None or not _number(item.get("value")):
            continue
        points.append((float(ticks), float(item["value"])))
    return counted, points


def _slope(points):
    if len(points) < 2:
        return None
    count = float(len(points))
    sum_t = 0.0
    sum_v = 0.0
    sum_tt = 0.0
    sum_tv = 0.0
    for stamp, value in points:
        sum_t += stamp
        sum_v += value
        sum_tt += stamp * stamp
        sum_tv += stamp * value
    denom = count * sum_tt - sum_t * sum_t
    if denom == 0.0:
        return 0.0
    return (count * sum_tv - sum_t * sum_v) / denom


def _posture_effect(card, row):
    posture = _posture(row)
    return (posture.get("target_id") == card.get("object_id") and
            card.get("signature") is not None and
            posture.get("posture_name") == card.get("signature"))


def _interaction_effect(card, state, row):
    del card
    running = _running(_ours(row, state.get("interaction_id")))
    foreign = state.get("foreign_roots") or []
    return bool(running and not foreign), None


def _stale(item):
    if item is None:
        return False
    age = item.get("age_ticks")
    return type(age) is int and age > NEED_FRESH_TICKS


def _since_start(rows, started, start_row):
    since = []
    seen = False
    for item in rows:
        if item is start_row or item.get("monotonic_ns") == started:
            seen = True
        if seen:
            since.append(item)
    return since


def _end_tick(rows, interaction_id):
    """Tick of the first row after our interaction has left, if it has left."""
    seen_running = False
    for item in rows:
        if _paused(item):
            continue
        running = _running(_ours(item, interaction_id))
        if running:
            seen_running = True
            continue
        if seen_running:
            return _ticks(item)
    return None


def _need_effect(card, state, row):
    rows = list(state.get("rows_since_push") or [])
    if not rows or rows[-1] is not row:
        rows.append(row)
    counted, points = _control_points(card, state.get("control_rows"), _push_tick(rows))
    if counted < 2:
        return False, "no_control"
    motive_id = card["motive"]
    for item in rows:
        if _motive(item, motive_id) is None:
            return False, "missing_motive"
    started = state.get("started_ns")
    start_row = None
    if started is not None:
        for item in rows:
            if item.get("monotonic_ns") == started:
                start_row = item
                break
    for item in rows:
        if item.get("observation_complete") is not True:
            return False, "incomplete_row"
    previous = None
    for item in rows:
        mono = item.get("monotonic_ns")
        if previous is not None and type(mono) is int and mono - previous > GAP_SECONDS * 1e9:
            return False, "gap"
        if type(mono) is int:
            previous = mono
    interaction_id = state.get("interaction_id")
    for item in rows:
        for entry in _entries(item):
            if entry.get("interaction_id") == interaction_id:
                continue
            if (entry.get("membership") in RUNNING_MEMBERSHIPS and
                    entry.get("source_raw") != POSTURE_SOURCE):
                return False, "overlapping_si"
    if started is None or start_row is None:
        return False, None
    since = _since_start(rows, started, start_row)
    if not any(not _paused(item) for item in since):
        return False, "paused_only"
    if _paused(row):
        return False, None
    origin = start_row if not _paused(start_row) else next(
        item for item in since if not _paused(item))
    if _stale(_motive(origin, motive_id)) or _stale(_motive(row, motive_id)):
        return False, "stale_value"
    if not _running(_ours(row, interaction_id)):
        end_tick = _end_tick(rows, interaction_id)
        now_tick = _ticks(row)
        if (end_tick is None or now_tick is None or
                now_tick - end_tick > NEED_GRACE_TICKS):
            return False, None
    start_value = _motive(origin, motive_id).get("value")
    now_value = _motive(row, motive_id).get("value")
    if not _number(start_value) or not _number(now_value):
        return False, "missing_motive"
    slope = _slope(points)
    if slope is None:
        return False, "no_control"
    origin_tick = _ticks(origin)
    now_tick = _ticks(row)
    if origin_tick is None or now_tick is None:
        return False, None
    elapsed = now_tick - origin_tick
    net = card["direction"] * (float(now_value) - float(start_value) - slope * elapsed)
    return net >= card["min_net_delta"], None


def _social_effect(card, state, row):
    if row.get("schema_version") != 5:
        return False, SOCIAL_UNOBSERVED
    target = card.get("object_id")
    ours = _ours(row, state.get("interaction_id"))
    if not _running(ours) or ours.get("target_id") != target:
        return False, None
    for entry in row.get("social") or []:
        if not isinstance(entry, dict):
            continue
        if (entry.get("actor_id") == target and
                entry.get("membership") in RUNNING_MEMBERSHIPS):
            return True, None
    return False, None


def evaluate_effect(card, experiment_state, row):
    """Return (effect, ambiguous_reason). Ambiguous is never an effect."""
    kind = card.get("card_class")
    state = experiment_state or {}
    if kind == "posture":
        return _posture_effect(card, row), None
    if kind == "interaction":
        return _interaction_effect(card, state, row)
    if kind == "need":
        return _need_effect(card, state, row)
    if kind == "social":
        return _social_effect(card, state, row)
    return False, "bad_card"
