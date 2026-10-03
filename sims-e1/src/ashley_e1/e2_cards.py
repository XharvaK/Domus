"""Pure class cards for harness trials. No game imports and no I/O.

Posture repeats the seated test. Need, interaction, and social add no
actuation. An ambiguity is not an effect.
"""

NEED_MIN_NET_DELTA = 5.0
NEED_FRESH_TICKS = 2000
NEED_CONTROL_SECONDS = 20.0
GAP_SECONDS = 5.0

CARD_CLASSES = ("posture", "need", "interaction", "social")
CARD_KEYS = ("card_class", "affordance_guid64", "object_id", "signature",
             "motive", "direction", "min_net_delta")
MOTIVES = ("social", "hygiene", "bladder", "energy", "fun", "hunger")
RUNNING_MEMBERSHIPS = ("RUNNING", "QUEUED_AND_RUNNING")
POSTURE_SOURCE = "InteractionSource.POSTURE_GRAPH"

# Social rows (schema._validate_social) carry entry_key, interaction_id,
# affordance, target_id, source, and membership. They do not name the other
# Sim as a participant, so a matching target_id only restates our target.
# The class cannot see that the target Sim is in the interaction.
SOCIAL_UNOBSERVED = "social_target_unobserved"


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_card(card):
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


def _control_points(card, control_rows, pushed_ns):
    window = NEED_CONTROL_SECONDS * 1e9
    points = []
    counted = 0
    for row in control_rows or []:
        mono = row.get("monotonic_ns")
        if type(mono) is not int:
            continue
        if mono >= pushed_ns or mono < pushed_ns - window:
            continue
        counted += 1
        item = _motive(row, card["motive"])
        if item is None or not _number(item.get("value")):
            continue
        points.append((mono / 1e9, float(item["value"])))
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


def _need_effect(card, state, row):
    rows = list(state.get("rows_since_push") or [])
    if not rows or rows[-1] is not row:
        rows.append(row)
    counted, points = _control_points(card, state.get("control_rows"), state.get("pushed_mono_ns"))
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
    if _stale(_motive(start_row, motive_id)) or _stale(_motive(row, motive_id)):
        return False, "stale_value"
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
    for entry in _entries(row):
        if entry.get("interaction_id") == interaction_id:
            continue
        if (entry.get("membership") in RUNNING_MEMBERSHIPS and
                entry.get("source_raw") != POSTURE_SOURCE):
            return False, "overlapping_si"
    if started is None or start_row is None:
        return False, None
    if not _running(_ours(row, interaction_id)):
        return False, None
    start_value = _motive(start_row, motive_id).get("value")
    now_value = _motive(row, motive_id).get("value")
    if not _number(start_value) or not _number(now_value):
        return False, "missing_motive"
    slope = _slope(points)
    if slope is None:
        return False, "no_control"
    elapsed = (row.get("monotonic_ns") - started) / 1e9
    net = card["direction"] * (float(now_value) - float(start_value) - slope * elapsed)
    return net >= card["min_net_delta"], None


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
        return False, SOCIAL_UNOBSERVED
    return False, "bad_card"
