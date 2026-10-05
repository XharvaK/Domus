"""Domus ingress wire contract v1. Mirrors Ashley's parseObservation / parseHeartbeat."""
import json
import math
import re

MAX_WINDOW_MS = 600_000
MAX_SKEW_MS = 120_000
BODY_LIMIT = 64 * 1024

OBSERVATION_KEYS = frozenset({
    "v", "observation_id", "world", "branch", "session", "attachment", "body", "snapshot",
    "seq", "source_time_ms", "expires_at_ms", "lineage_class", "percepts", "portrait", "options",
})
HEARTBEAT_KEYS = frozenset({"v", "helper_session", "sent_at_ms", "attached", "world", "probe_version"})
PERCEPT_KEYS = frozenset({"kind", "salience", "facts"})


class ContractError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _record(value):
    return isinstance(value, dict)


def _text(value, min_len, max_len, pattern=None):
    if not isinstance(value, str) or not min_len <= len(value) <= max_len:
        raise ContractError("invalid_body")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise ContractError("invalid_body")
    return value


def _safe_int(value):
    if type(value) is not int or value < 0 or value > 2**53 - 1:
        raise ContractError("invalid_body")
    return value


def _json_bytes(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def _json_object(value, max_bytes):
    if not _record(value) or _json_bytes(value) > max_bytes:
        raise ContractError("invalid_body")
    return value


def validate_observation(body, now_ms):
    if _json_bytes(body) > BODY_LIMIT:
        raise ContractError("payload_too_large")
    if not _record(body) or any(key not in OBSERVATION_KEYS for key in body):
        raise ContractError("invalid_body")
    if body.get("v") != 1 or type(body.get("v")) is not int:
        raise ContractError("invalid_body")
    observation_id = _text(body.get("observation_id"), 1, 128, re.compile(r"[A-Za-z0-9._:-]+"))
    world = _text(body.get("world"), 1, 64)
    branch = _text(body.get("branch"), 1, 64)
    session = _text(body.get("session"), 1, 64)
    attachment = _text(body.get("attachment"), 1, 64)
    snapshot = _text(body.get("snapshot"), 1, 64)
    text_body = _text(body.get("body"), 1, 64)
    seq = _safe_int(body.get("seq"))
    source_time_ms = _safe_int(body.get("source_time_ms"))
    expires_at_ms = _safe_int(body.get("expires_at_ms"))
    lineage = _text(body.get("lineage_class"), 1, 32, re.compile(r"[A-Z_]+"))
    percepts_in = body.get("percepts")
    if not isinstance(percepts_in, list) or not 1 <= len(percepts_in) <= 32:
        raise ContractError("invalid_body")
    percepts = []
    for item in percepts_in:
        if not _record(item) or any(key not in PERCEPT_KEYS for key in item):
            raise ContractError("invalid_body")
        salience = item.get("salience")
        if isinstance(salience, bool) or not isinstance(salience, (int, float)) or not math.isfinite(salience):
            raise ContractError("invalid_body")
        if salience < 0 or salience > 1:
            raise ContractError("invalid_body")
        percepts.append({
            "kind": _text(item.get("kind"), 1, 32, re.compile(r"[a-z0-9_]+")),
            "salience": salience,
            "facts": _json_object(item.get("facts"), 2048),
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
        normalized["portrait"] = _json_object(body.get("portrait"), 8192)
    if "options" in body:
        options = body.get("options")
        if (not isinstance(options, list) or len(options) > 32 or not all(_record(item) for item in options)
                or len(json.dumps(options, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) > 8192):
            raise ContractError("invalid_body")
        normalized["options"] = options
    if expires_at_ms <= source_time_ms or expires_at_ms - source_time_ms > MAX_WINDOW_MS:
        raise ContractError("invalid_body")
    if source_time_ms > now_ms + MAX_SKEW_MS:
        raise ContractError("clock_skew")
    if now_ms > expires_at_ms:
        raise ContractError("expired")
    return normalized


def validate_heartbeat(body):
    if not _record(body) or any(key not in HEARTBEAT_KEYS for key in body):
        raise ContractError("invalid_body")
    if _json_bytes(body) > BODY_LIMIT:
        raise ContractError("payload_too_large")
    if body.get("v") != 1 or type(body.get("v")) is not int or type(body.get("attached")) is not bool:
        raise ContractError("invalid_body")
    normalized = {
        "v": 1,
        "helper_session": _text(body.get("helper_session"), 1, 64),
        "sent_at_ms": _safe_int(body.get("sent_at_ms")),
        "attached": body["attached"],
    }
    if "world" in body:
        normalized["world"] = _text(body.get("world"), 0, 64)
    if "probe_version" in body:
        normalized["probe_version"] = _text(body.get("probe_version"), 0, 16)
    return normalized
