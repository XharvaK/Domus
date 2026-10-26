"""Domus ingress wire contract v1. Mirrors Ashley's parseObservation / parseHeartbeat."""
import json
import math
import re

MAX_WINDOW_MS = 600_000
MAX_SKEW_MS = 120_000
BODY_LIMIT = 64 * 1024
# 2.37.0 (W10 H2): a lot's options take at most this many objects and this many bytes (the contract's own limits).
OPTIONS_MAX_OBJECTS = 160
OPTIONS_MAX_BYTES = 32768

OBSERVATION_KEYS = frozenset({
    "v", "observation_id", "world", "branch", "session", "attachment", "body", "snapshot",
    "seq", "source_time_ms", "expires_at_ms", "lineage_class", "percepts", "portrait", "options", "options_cut", "day",
    "choices_pending",  # W14 (S2): true while the game's choices have not come in this helper session
})
HEARTBEAT_KEYS = frozenset({"v", "helper_session", "sent_at_ms", "attached", "world", "probe_version", "inputs"})
PERCEPT_KEYS = frozenset({"kind", "salience", "facts"})


class ContractError(ValueError):
    """A refusal. code is the contract's word (invalid_body, expired, ...); where (2.37.0, W10 H1) names the key it
    failed on, so the decision log can say which one."""

    def __init__(self, code, where=None):
        self.code = code
        self.where = where
        super().__init__(code)


def refusal_text(error):
    """2.37.0 (W10 H1): the decision log's words for a refusal: "ContractError: invalid_body (world)"."""
    text = "%s: %s" % (type(error).__name__, getattr(error, "code", error))
    where = getattr(error, "where", None)
    return text if where is None else "%s (%s)" % (text, where)


def options_why(options, where):
    """2.37.0 (W10 H2): why a view's options (or their cut) were refused, in one word for her percept: too_large when
    the list is past the contract's object or byte limit, else malformed."""
    if where != "options" or not isinstance(options, list):
        return "malformed"
    if len(options) > OPTIONS_MAX_OBJECTS:
        return "too_large"
    if len(json.dumps(options, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > OPTIONS_MAX_BYTES:
        return "too_large"
    return "malformed"


def _record(value):
    return isinstance(value, dict)


def _text(value, min_len, max_len, pattern=None, where=None):
    if not isinstance(value, str) or not min_len <= len(value) <= max_len:
        raise ContractError("invalid_body", where)
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ContractError("invalid_body", where)
    return value


def _safe_int(value, where=None):
    if type(value) is not int or value < 0 or value > 2**53 - 1:
        raise ContractError("invalid_body", where)
    return value


def _json_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _json_object(value, max_bytes, where=None):
    if not _record(value) or _json_bytes(value) > max_bytes:
        raise ContractError("invalid_body", where)
    return value


def _options_cut(value):
    """N8 (F4): what the view's options left out: {"objects": count, "rooms": [labels]}, nothing else."""
    if not _record(value) or set(value) != {"objects", "rooms"}:
        raise ContractError("invalid_body", "options_cut")
    rooms = value.get("rooms")
    if type(value.get("objects")) is not int or value["objects"] < 1 or not isinstance(rooms, list) or len(rooms) > 16:
        raise ContractError("invalid_body", "options_cut")
    for name in rooms:
        _text(name, 1, 64, where="options_cut")
    return {"objects": value["objects"], "rooms": list(rooms)}


def validate_observation(body, now_ms):
    if _json_bytes(body) > BODY_LIMIT:
        raise ContractError("payload_too_large", "body")
    if not _record(body) or any(key not in OBSERVATION_KEYS for key in body):
        raise ContractError("invalid_body", "body")
    if body.get("v") != 1 or type(body.get("v")) is not int:
        raise ContractError("invalid_body", "v")
    observation_id = _text(body.get("observation_id"), 1, 128, re.compile(r"[A-Za-z0-9._:-]+"), "observation_id")
    world = _text(body.get("world"), 1, 64, where="world")
    branch = _text(body.get("branch"), 1, 64, where="branch")
    session = _text(body.get("session"), 1, 64, where="session")
    attachment = _text(body.get("attachment"), 1, 64, where="attachment")
    snapshot = _text(body.get("snapshot"), 1, 64, where="snapshot")
    text_body = _text(body.get("body"), 1, 64, where="body")
    seq = _safe_int(body.get("seq"), "seq")
    source_time_ms = _safe_int(body.get("source_time_ms"), "source_time_ms")
    expires_at_ms = _safe_int(body.get("expires_at_ms"), "expires_at_ms")
    lineage = _text(body.get("lineage_class"), 1, 32, re.compile(r"[A-Z_]+"), "lineage_class")
    percepts_in = body.get("percepts")
    if not isinstance(percepts_in, list) or not 1 <= len(percepts_in) <= 32:
        raise ContractError("invalid_body", "percepts")
    percepts = []
    for index, item in enumerate(percepts_in):
        if not _record(item) or any(key not in PERCEPT_KEYS for key in item):
            raise ContractError("invalid_body", "percepts[%d]" % index)
        salience = item.get("salience")
        if isinstance(salience, bool) or not isinstance(salience, (int, float)) or not math.isfinite(salience):
            raise ContractError("invalid_body", "percepts[%d].salience" % index)
        if salience < 0 or salience > 1:
            raise ContractError("invalid_body", "percepts[%d].salience" % index)
        percepts.append({
            "kind": _text(item.get("kind"), 1, 32, re.compile(r"[a-z0-9_]+"), "percepts[%d].kind" % index),
            "salience": salience,
            "facts": _json_object(item.get("facts"), 2048, "percepts[%d].facts" % index),
        })
    normalized = {
        "v": 1,
        "observation_id": observation_id,
        "world": world,
        "branch": branch,
        "session": session,
        "attachment": attachment,
        "body": text_body,
        "snapshot": snapshot,
        "seq": seq,
        "source_time_ms": source_time_ms,
        "expires_at_ms": expires_at_ms,
        "lineage_class": lineage,
        "percepts": percepts,
    }
    if "portrait" in body:
        normalized["portrait"] = _json_object(body.get("portrait"), 8192, "portrait")
    if "options" in body:
        # N8 (F4): a lot's options take up to 160 objects and 32,768 bytes; a cut is named in options_cut.
        options = body.get("options")
        if (not isinstance(options, list) or len(options) > OPTIONS_MAX_OBJECTS
                or not all(_record(item) for item in options)
                or len(json.dumps(options, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                > OPTIONS_MAX_BYTES):
            raise ContractError("invalid_body", "options")
        normalized["options"] = options
    if "options_cut" in body:
        normalized["options_cut"] = _options_cut(body.get("options_cut"))
    if "choices_pending" in body:
        # W14 (S2): the flag is sent only when it is true (absent once the game's choices have come).
        if body.get("choices_pending") is not True:
            raise ContractError("invalid_body", "choices_pending")
        normalized["choices_pending"] = True
    if "day" in body:
        normalized["day"] = _json_object(body.get("day"), 16384, "day")
    if expires_at_ms <= source_time_ms or expires_at_ms - source_time_ms > MAX_WINDOW_MS:
        raise ContractError("invalid_body", "expires_at_ms")
    if source_time_ms > now_ms + MAX_SKEW_MS:
        raise ContractError("clock_skew", "source_time_ms")
    if now_ms > expires_at_ms:
        raise ContractError("expired", "expires_at_ms")
    return normalized


def validate_heartbeat(body):
    if not _record(body) or any(key not in HEARTBEAT_KEYS for key in body):
        raise ContractError("invalid_body", "body")
    if _json_bytes(body) > BODY_LIMIT:
        raise ContractError("payload_too_large", "body")
    if body.get("v") != 1 or type(body.get("v")) is not int or type(body.get("attached")) is not bool:
        raise ContractError("invalid_body", "v")
    normalized = {
        "v": 1,
        "helper_session": _text(body.get("helper_session"), 1, 64, where="helper_session"),
        "sent_at_ms": _safe_int(body.get("sent_at_ms"), "sent_at_ms"),
        "attached": body["attached"],
    }
    if "world" in body:
        normalized["world"] = _text(body.get("world"), 0, 64, where="world")
    if "probe_version" in body:
        normalized["probe_version"] = _text(body.get("probe_version"), 0, 16, where="probe_version")
    if "inputs" in body:
        if body.get("inputs") not in ("full", "game_only"):
            raise ContractError("invalid_body", "inputs")
        normalized["inputs"] = body["inputs"]
    return normalized
