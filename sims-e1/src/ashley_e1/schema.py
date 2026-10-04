"""Pure E1/E2 telemetry schema and bounded record validation."""

import json


OBSERVATION_SCHEMA_VERSION = 5
TELEMETRY_SCHEMA_ID = "e1.telemetry/v5"
PROBE_VERSION = "2.9.2"
ACCEPTED_SCHEMA_VERSIONS = (4, 5)
SIMS_BUILD = "1.128.90.1030"
MAX_SERIALIZED_RECORD_BYTES = 8 * 1024
MAX_ID_LENGTH = 64
MAX_DISPLAY_TEXT_LENGTH = 160
MAX_REASON_LENGTH = 128
MAX_DETAIL_LENGTH = 128
MAX_NOTE_LENGTH = 256
MAX_INTERACTIONS = 8
MAX_MOTIVES = 12
MAX_SEEN_GUIDS = 40
MOTIVE_DIAG_STAGES = (
    "ok", "no_component", "no_tracker", "commodities_error", "no_guid_match",
    "string_id_error", "component_error",
)
MOTIVE_ROW_FIELDS = (
    "_modified_value", "default_value", "_last_update", "min_value", "max_value",
)
MAX_SIGNALS = 16
MAX_PRESENCE = 8
MAX_SOCIAL = 4
MOTIVE_BANDS = ("distress", "low", "ok")
SIGNAL_KINDS = (
    "MOODLET", "WANT", "FEAR", "TRAIT_NOTE", "LIKE", "ASPIRATION_NOTE",
    "RELATIONSHIP_NOTE", "FAILURE_PRECURSOR",
)
SIGNAL_CONSEQUENCES = ("PARTIAL", "UNKNOWN")

EVENT_KINDS = (
    "session_open",
    "session_checkpoint",
    "session_close",
    "zone_snapshot",
    "presence_snapshot",
    "clock_snapshot",
    "save_observation",
    "guard_exhausted",
    "dropped_summary",
    "load_disabled",
    "cap_reached",
    "writer_failed",
    "experiment_event",
    "speed_event",
    "lineage_event",
    "command_event",
)
E2_EVENT_KINDS = ("experiment_event", "speed_event", "lineage_event", "command_event")
E2_PAYLOAD_KEYS = {
    "command_event": ("id", "issuer", "command", "status", "code"),
    "experiment_event": ("phase", "code", "experiment_id", "object_id", "token",
                         "interaction_id", "claims", "finishing_type", "detail",
                         "guid64", "card_class", "tuning_name", "ambiguous"),
    "speed_event": ("phase", "code", "detail"),
    "lineage_event": ("record", "guid", "slot_id", "sim_id", "ticks",
                      "loaded_from_slot_id", "lineage_class", "session_uuid"),
}
EXPERIMENT_PHASES = (
    "SIGNATURE_LEARNED", "CONTINUATION_LEARNED", "PREPARE_OK", "PREPARE_REJECT",
    "ADMIT_REJECT", "PUSHED", "PUSH_FAILED", "CLAIM", "FINISHED_CALLBACK",
    "VERDICT", "CALIBRATE_START", "CALIBRATE_SPEED", "TRIAL_REJECT",
)
COMMANDS = ("arm", "start", "stop", "disarm", "prepare", "sit", "pause",
            "release", "status", "sit_trial", "atlas_dump", "tuned_scan",
            "calibrate", "trial")


def _command_id(value):
    return (type(value) is str and len(value) == 32 and
            all(ch in "0123456789abcdef" for ch in value))


def _command_issuer(value):
    return (type(value) is str and (value in ("helper", "console") or
            (value.startswith("agent:") and 1 <= len(value[6:]) <= 34 and
             all(ch in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in value[6:]))))


SPEED_PHASES = ("REQUEST_PUSHED", "REQUEST_REMOVED", "REJECT",
                "RELEASED_ON_DISARM", "RELEASED_ON_STOP", "RELEASE_FAILED")
LINEAGE_RECORDS = ("LOAD_OBSERVED", "SAVE_OBSERVED", "DESIGNATED_BODY", "CLASSIFIED")
CLAIM_KEYS = ("REQUEST_ACCEPTED", "ENQUEUED", "STARTED", "EFFECT_OBSERVED",
              "ATTRIBUTED", "MAINTAINED_10S", "FINISHED")
MISSINGNESS_STATUSES = ("MISSING", "ABSENT", "UNSUPPORTED", "UNKNOWN")
REQUIRED_IMPORT_KEYS = (
    "alarms",
    "alarms.add_alarm_real_time",
    "alarms.cancel_alarm",
    "clock",
    "clock.interval_in_real_seconds",
    "date_and_time",
    "date_and_time.TimeSpan",
    "services",
    "services.sim_info_manager",
    "services.client_manager",
    "server.clientmanager",
    "sims.sim.Sim",
    "sims.sim_info.SimInfo",
    "interactions.context",
    "interactions.context.InteractionContext",
    "sims4.commands",
    "sims4.commands.CommandType",
    "sims4.commands.CommandRestrictionFlags",
    "sims4.commands.register",
    "sims4.commands.output",
    "e2.actuator",
)
SOURCE_NORMS = ("OWNER_UI", "SCRIPT_DIRECTED", "UNKNOWN")
SOURCE_CONFIDENCES = ("EXPOSED", "UNKNOWN")
MEMBERSHIPS = ("QUEUED", "RUNNING", "QUEUED_AND_RUNNING")
WRITER_STATES = ("OK", "CAP_REACHED", "FAILED_STICKY")
AVAILABILITY = ("AVAILABLE", "UNAVAILABLE_DEFERRED")
COMMON_KEYS = {
    "schema_version", "telemetry_session_id", "boot_id", "written_sequence",
    "wall_timestamp_ms", "monotonic_ns", "game", "probe_version", "sims_build",
    "event_kind", "reason", "checkpoint_reason", "close_reason",
    "observation_complete", "attestation", "save", "zone", "body",
    "interactions", "motives", "sim_signals", "presence", "social", "mood",
    "missingness", "unsupported",
    "availability", "counters", "writer", "note", "e2",
}


class SchemaError(ValueError):
    """Raised when a record violates the closed E1 schema."""


def _require(condition, message):
    if not condition:
        raise SchemaError(message)


def bounded_string(value, limit, field="value", allow_none=True):
    if value is None and allow_none:
        return None
    _require(isinstance(value, str), "%s must be a string" % field)
    _require(len(value) <= limit, "%s exceeds %d characters" % (field, limit))
    return value


ATLAS_STATES = ("idle", "running", "done", "error")


def validate_atlas(row):
    """Closed atlas progress on the status reply. Not a telemetry row."""
    _require(type(row) is dict and set(row) == {
        "state", "done", "total", "chunks", "max_chunk_ms", "file"}, "atlas")
    _require(row["state"] in ATLAS_STATES, "atlas.state")
    for key in ("done", "total", "chunks"):
        _require(type(row[key]) is int and row[key] >= 0, "atlas." + key)
    elapsed = row["max_chunk_ms"]
    _require(type(elapsed) in (int, float) and elapsed >= 0, "atlas.max_chunk_ms")
    _require(row["file"] is None or type(row["file"]) is str, "atlas.file")
    return {
        "state": row["state"],
        "done": row["done"],
        "total": row["total"],
        "chunks": row["chunks"],
        "max_chunk_ms": elapsed,
        "file": row["file"],
    }


def validate_tuned(row):
    """Closed tuned-scan progress on the status reply. Not a telemetry row."""
    _require(type(row) is dict and set(row) == {
        "state", "done", "total", "chunks", "max_chunk_ms", "file"}, "tuned")
    _require(row["state"] in ATLAS_STATES, "tuned.state")
    for key in ("done", "total", "chunks"):
        _require(type(row[key]) is int and row[key] >= 0, "tuned." + key)
    elapsed = row["max_chunk_ms"]
    _require(type(elapsed) in (int, float) and elapsed >= 0, "tuned.max_chunk_ms")
    _require(row["file"] is None or type(row["file"]) is str, "tuned.file")
    return {
        "state": row["state"],
        "done": row["done"],
        "total": row["total"],
        "chunks": row["chunks"],
        "max_chunk_ms": elapsed,
        "file": row["file"],
    }


def validate_motive_diag(row):
    """Closed status diagnostic. Not part of a telemetry row."""
    _require(type(row) is dict and set(row) == {"stage", "seen_guids", "matched"},
             "motive_diag")
    stage = row["stage"]
    _require(type(stage) is str, "motive_diag.stage")
    if stage.startswith("row_error:"):
        field = stage[len("row_error:"):]
        _require(field in MOTIVE_ROW_FIELDS and ":" not in field, "motive_diag.stage")
    else:
        _require(stage in MOTIVE_DIAG_STAGES, "motive_diag.stage")
    seen = row["seen_guids"]
    _require(type(seen) is list and len(seen) <= MAX_SEEN_GUIDS, "motive_diag.seen_guids")
    _require(all(type(item) is int for item in seen), "motive_diag.seen_guids")
    _require(seen == sorted(set(seen)), "motive_diag.seen_guids")
    matched = row["matched"]
    _require(type(matched) is int and 0 <= matched <= MAX_MOTIVES, "motive_diag.matched")
    return {
        "stage": stage,
        "seen_guids": list(seen),
        "matched": matched,
    }


def string_id(value, field="id"):
    if value is None:
        return None
    _require(not isinstance(value, bool), "%s must not be bool" % field)
    if not isinstance(value, str):
        value = str(value)
    return bounded_string(value, MAX_ID_LENGTH, field, allow_none=False)


def attestation(armed_name="UNARMED", armed_name_hash=None, snapshot_guid=None,
                snapshot_slot=None, snapshot_sim=None):
    _require(armed_name in ("LAB_E1", "LAB_E1_FORK", "UNARMED"),
             "invalid armed_name")
    return {
        "armed_name": armed_name,
        "armed_name_hash": (None if armed_name_hash is None else
                             bounded_string(armed_name_hash, 8, "armed_name_hash")),
        "snapshot_guid": string_id(snapshot_guid, "snapshot_guid"),
        "snapshot_slot": string_id(snapshot_slot, "snapshot_slot"),
        "snapshot_sim": string_id(snapshot_sim, "snapshot_sim"),
    }


def _default_game():
    return {"ticks": None, "calendar": None, "clock_speed": None, "paused": None}


def _default_save():
    return {"save_slot_guid": None, "slot_id": None}


def _default_zone():
    return {"zone_id": None, "lot_id": None, "room": None, "position": None}


def _default_body():
    return {"sim_id": None, "instantiated": None, "is_selectable": None,
            "is_selected": None, "posture": None}


def _default_interactions():
    return {"observed": [], "queue_truncated": False, "running_truncated": False,
            "observation_complete": False}


def _default_counters():
    return {"dropped_queue": 0, "dropped_overrun": 0, "dropped_serialize": 0,
            "redundant_starts": 0}


def _default_writer():
    return {"state": "OK", "rotation_index": 0}


def make_record(event_kind, telemetry_session_id=None, boot_id=None,
                wall_timestamp_ms=0, monotonic_ns=0, probe_version=PROBE_VERSION,
                sims_build=SIMS_BUILD, **payload):
    _require(event_kind in EVENT_KINDS, "unknown event_kind: %s" % event_kind)
    row = {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "telemetry_session_id": telemetry_session_id,
        "boot_id": boot_id,
        "written_sequence": 0,
        "wall_timestamp_ms": wall_timestamp_ms,
        "monotonic_ns": monotonic_ns,
        "game": _default_game(),
        "probe_version": probe_version,
        "sims_build": sims_build,
        "event_kind": event_kind,
        "reason": None,
        "checkpoint_reason": None,
        "close_reason": None,
        "observation_complete": None,
        "attestation": attestation(),
        "save": _default_save(),
        "zone": _default_zone(),
        "body": _default_body(),
        "interactions": _default_interactions(),
        "motives": [],
        "sim_signals": [],
        "presence": [],
        "social": [],
        "mood": None,
        "missingness": {},
        "unsupported": [],
        "availability": "AVAILABLE",
        "counters": _default_counters(),
        "writer": _default_writer(),
        "note": None,
        "e2": None,
    }
    for key, value in payload.items():
        if key in row and isinstance(row[key], dict) and isinstance(value, dict):
            merged = dict(row[key])
            merged.update(value)
            row[key] = merged
        else:
            row[key] = value
    return row


def make_load_disabled_record(boot_id, wall_timestamp_ms, monotonic_ns, runtime,
                              probe_version=PROBE_VERSION, sims_build=SIMS_BUILD):
    _require(isinstance(runtime, dict), "runtime must be a dict")
    _validate_load_disabled_runtime(runtime)
    return {
        "schema_version": OBSERVATION_SCHEMA_VERSION,
        "telemetry_session_id": None,
        "boot_id": bounded_string(boot_id, MAX_ID_LENGTH, "boot_id", False),
        "written_sequence": 0,
        "wall_timestamp_ms": wall_timestamp_ms,
        "monotonic_ns": monotonic_ns,
        "probe_version": bounded_string(probe_version, MAX_ID_LENGTH, "probe_version", False),
        "sims_build": bounded_string(sims_build, MAX_ID_LENGTH, "sims_build", False),
        "event_kind": "load_disabled",
        "reason": None,
        "attestation": attestation(),
        "runtime": dict(runtime),
    }


def _validate_load_disabled_runtime(runtime):
    _require(set(runtime) in ({"python_version", "perf_counter", "required_imports"},
                              {"python_version", "perf_counter", "required_imports",
                               "inbox_autostart"}),
             "load_disabled runtime shape")
    bounded_string(runtime.get("python_version"), MAX_ID_LENGTH,
                   "runtime.python_version", False)
    _require(type(runtime.get("perf_counter")) is bool,
             "runtime.perf_counter")
    if "inbox_autostart" in runtime:
        _require(runtime["inbox_autostart"] in
                 ("STARTED",  # legacy: written by probe 2.2.0
                  "MANAGER_UNAVAILABLE", "NOT_STARTED", "CONSOLE",
                  "ZONE:import", "ZONE:tuning", "ZONE:posture",
                  "ZONE:household", "ZONE:transition", "ZONE:manager"),
                 "runtime.inbox_autostart")
    required_imports = runtime.get("required_imports")
    _require(isinstance(required_imports, dict),
             "runtime.required_imports")
    _require(set(required_imports) == set(REQUIRED_IMPORT_KEYS),
             "runtime.required_imports keys")
    for key in REQUIRED_IMPORT_KEYS:
        _require(type(required_imports[key]) is bool,
                 "runtime.required_imports.%s" % key)


def _validate_string_tree(value, key="value"):
    if isinstance(value, str):
        if key in ("reason", "checkpoint_reason", "close_reason"):
            bounded_string(value, MAX_REASON_LENGTH, key, False)
        elif key in ("detail",):
            bounded_string(value, MAX_DETAIL_LENGTH, key, False)
        elif key in ("note",):
            bounded_string(value, MAX_NOTE_LENGTH, key, False)
        elif key in ("affordance_text", "game_text", "calendar", "posture", "room",
                      "posture_name", "detail_text", "finishing_type", "type"):
            bounded_string(value, MAX_DISPLAY_TEXT_LENGTH, key, False)
        else:
            bounded_string(value, MAX_ID_LENGTH, key, False)
    elif isinstance(value, dict):
        for child_key, child_value in value.items():
            _validate_string_tree(child_value, child_key)
    elif isinstance(value, list):
        for child in value:
            _validate_string_tree(child, key)


def _validate_attestation(value):
    _require(isinstance(value, dict), "attestation must be an object")
    _require(set(value) == {"armed_name", "armed_name_hash", "snapshot_guid",
                            "snapshot_slot", "snapshot_sim"},
             "attestation shape")
    _require(value.get("armed_name") in ("LAB_E1", "LAB_E1_FORK", "UNARMED"),
             "invalid attestation armed_name")
    for key in ("armed_name_hash", "snapshot_guid", "snapshot_slot", "snapshot_sim"):
        _require(key in value, "missing attestation.%s" % key)
        if value[key] is not None:
            _require(isinstance(value[key], str), "attestation.%s must be a string" % key)
            if key == "armed_name_hash":
                _require(len(value[key]) == 8, "attestation.armed_name_hash must be 8 characters")
            else:
                string_id(value[key], "attestation.%s" % key)


def _validate_id_fields(value, fields, label):
    _require(isinstance(value, dict), "%s must be an object" % label)
    expected = {
        "save": {"save_slot_guid", "slot_id"},
        "zone": {"zone_id", "lot_id", "room", "position"},
        "body": {"sim_id", "instantiated", "is_selectable", "is_selected", "posture"},
    }.get(label)
    if expected is not None:
        _require(set(value) == expected, "%s shape" % label)
    for field in fields:
        _require(field in value, "missing %s.%s" % (label, field))
        if value[field] is not None:
            _require(isinstance(value[field], str), "%s.%s must be a string" % (label, field))
            string_id(value[field], "%s.%s" % (label, field))


def _validate_interactions(value):
    _require(isinstance(value, dict), "interactions must be an object")
    observed = value.get("observed")
    _require(isinstance(observed, list) and len(observed) <= MAX_INTERACTIONS,
             "interactions.observed exceeds cap")
    _require(type(value.get("queue_truncated")) is bool, "queue_truncated must be bool")
    _require(type(value.get("running_truncated")) is bool, "running_truncated must be bool")
    _require(type(value.get("observation_complete")) is bool,
             "interactions.observation_complete must be bool")
    for item in observed:
        _require(isinstance(item, dict), "interaction must be an object")
        _require(set(item) == {"entry_key", "interaction_id", "affordance_id",
                               "affordance_text", "target_id", "source_raw",
                               "source_norm", "source_confidence", "present",
                               "membership"},
                 "interaction shape")
        _require(item.get("membership") in MEMBERSHIPS, "invalid interaction membership")
        _require(item.get("source_norm") in SOURCE_NORMS, "invalid source_norm")
        _require(item.get("source_confidence") in SOURCE_CONFIDENCES,
                 "invalid source_confidence")
        _require(type(item.get("present")) is bool, "interaction.present must be bool")


def _validate_posture(value):
    if value is None:
        return
    _require(isinstance(value, dict) and set(value) == {"posture_name", "target_id"},
             "body.posture shape")
    if value["posture_name"] is not None:
        bounded_string(value["posture_name"], MAX_DISPLAY_TEXT_LENGTH,
                       "body.posture.posture_name", False)
    if value["target_id"] is not None:
        _require(isinstance(value["target_id"], str), "body.posture.target_id")
        string_id(value["target_id"], "body.posture.target_id")


def _validate_e2(row):
    kind = row.get("event_kind")
    payload = row.get("e2")
    if kind not in E2_EVENT_KINDS:
        _require(payload is None, "%s carries e2 payload" % kind)
        return
    if kind == "experiment_event" and isinstance(payload, dict):
        # Probe 2.9.2 adds these. Schema 5 rows written before that omit them.
        for key in ("guid64", "card_class", "tuning_name", "ambiguous"):
            if key not in payload:
                payload[key] = None
    _require(isinstance(payload, dict) and
             set(payload) == set(E2_PAYLOAD_KEYS[kind]), "%s e2 shape" % kind)
    _require(row.get("telemetry_session_id") is not None, "%s session id" % kind)
    if kind == "command_event":
        _require(_command_id(payload["id"]), "command id")
        _require(_command_issuer(payload["issuer"]), "command issuer")
        _require(payload["command"] in COMMANDS, "command vocabulary")
        _require(payload["status"] in ("OK", "REJECTED", "ERROR"), "command status")
        bounded_string(payload["code"], 64, "command code")
    elif kind == "experiment_event":
        _require(payload["phase"] in EXPERIMENT_PHASES, "experiment phase")
        claims = payload["claims"]
        if claims is not None:
            _require(isinstance(claims, dict) and set(claims) == set(CLAIM_KEYS),
                     "experiment claims shape")
            for value in claims.values():
                _require(type(value) is bool, "experiment claim value")
        for key in ("code", "experiment_id", "object_id", "token", "interaction_id"):
            if payload[key] is not None:
                _require(isinstance(payload[key], str), "experiment %s" % key)
                string_id(payload[key], "experiment %s" % key)
        if payload["finishing_type"] is not None:
            bounded_string(payload["finishing_type"], MAX_DISPLAY_TEXT_LENGTH,
                           "finishing_type", False)
        if payload["detail"] is not None:
            bounded_string(payload["detail"], MAX_DETAIL_LENGTH, "detail", False)
        if payload["guid64"] is not None:
            string_id(payload["guid64"], "experiment guid64")
        if payload["card_class"] is not None:
            _require(payload["card_class"] in ("posture", "need", "interaction", "social"),
                     "experiment card_class")
        if payload["tuning_name"] is not None:
            bounded_string(payload["tuning_name"], 128, "experiment tuning_name", False)
        ambiguous = payload["ambiguous"]
        if ambiguous is not None:
            _require(type(ambiguous) is list and len(ambiguous) <= 16, "experiment ambiguous")
            for item in ambiguous:
                bounded_string(item, 64, "experiment ambiguous", False)
    elif kind == "speed_event":
        _require(payload["phase"] in SPEED_PHASES, "speed phase")
        for key in ("code", "detail"):
            if payload[key] is not None:
                bounded_string(payload[key], MAX_DETAIL_LENGTH, "speed %s" % key, False)
    else:
        _require(payload["record"] in LINEAGE_RECORDS, "lineage record")
        for key in ("guid", "slot_id", "sim_id", "loaded_from_slot_id",
                    "lineage_class", "session_uuid"):
            if payload[key] is not None:
                _require(isinstance(payload[key], str), "lineage %s" % key)
                string_id(payload[key], "lineage %s" % key)
        if payload["ticks"] is not None:
            _require(type(payload["ticks"]) is int, "lineage ticks")


def _validate_motives(value):
    _require(isinstance(value, list) and len(value) <= MAX_MOTIVES, "motives")
    for item in value:
        _require(isinstance(item, dict), "motive must be an object")
        _require(set(item) == {"id", "value", "band", "age_ticks"}, "motive shape")
        _require(isinstance(item.get("id"), str), "motive.id must be a string")
        string_id(item["id"], "motive.id")
        if item.get("value") is not None:
            _require(isinstance(item["value"], (int, float)) and
                     not isinstance(item["value"], bool),
                     "motive.value must be numeric")
        if item.get("band") is not None:
            bounded_string(item["band"], MAX_ID_LENGTH, "motive.band", False)
            _require(item["band"] in MOTIVE_BANDS, "invalid motive band")
        if item.get("age_ticks") is not None:
            _require(type(item["age_ticks"]) is int and item["age_ticks"] >= 0,
                     "motive.age_ticks must be a non-negative int")


def _validate_presence(value):
    _require(isinstance(value, list) and len(value) <= MAX_PRESENCE, "presence")
    for item in value:
        _require(isinstance(item, dict), "presence entry must be an object")
        _require(set(item) == {"id", "active_household", "level"},
                 "presence shape")
        _require(isinstance(item.get("id"), str), "presence.id must be a string")
        string_id(item["id"], "presence.id")
        _require(type(item.get("active_household")) is bool,
                 "presence.active_household must be bool")
        if item.get("level") is not None:
            _require(type(item["level"]) is int, "presence.level must be int")


def _validate_social(value, version):
    _require(isinstance(value, list) and len(value) <= MAX_SOCIAL, "social")
    fields = {"entry_key", "interaction_id", "affordance_id",
              "affordance_text", "target_id", "source_raw",
              "source_norm", "source_confidence", "present",
              "membership"}
    if version == 5:
        fields = set(fields)
        fields.add("actor_id")
    for item in value:
        _require(isinstance(item, dict), "social entry must be an object")
        _require(set(item) == fields, "social interaction shape")
        _require(item.get("membership") in MEMBERSHIPS, "invalid social membership")
        _require(item.get("source_norm") in SOURCE_NORMS, "invalid social source_norm")
        _require(item.get("source_confidence") in SOURCE_CONFIDENCES,
                 "invalid social source_confidence")
        _require(type(item.get("present")) is bool, "social.present must be bool")
        if version == 5:
            _require(isinstance(item.get("actor_id"), str), "social.actor_id must be a string")
            string_id(item["actor_id"], "social.actor_id")


def _validate_mood(value, version):
    if value is None:
        return
    fields = {"type", "intensity"}
    if version == 5:
        fields = set(fields)
        fields.add("name")
    _require(isinstance(value, dict) and set(value) == fields, "mood shape")
    if value["type"] is not None:
        bounded_string(value["type"], MAX_ID_LENGTH, "mood.type", False)
    if value["intensity"] is not None:
        _require(isinstance(value["intensity"], (int, float)) and
                 not isinstance(value["intensity"], bool),
                 "mood.intensity must be numeric")
    if version == 5 and value["name"] is not None:
        bounded_string(value["name"], 128, "mood.name", False)


def _validate_signals(value, version):
    _require(isinstance(value, list) and len(value) <= MAX_SIGNALS, "sim_signals")
    fields = {"kind", "tuning_id", "game_text", "magnitude", "consequences",
              "native_override"}
    if version == 5:
        fields = set(fields)
        fields.add("tuning_name")
    for item in value:
        _require(isinstance(item, dict), "signal must be an object")
        _require(set(item) == fields, "signal shape")
        _require(item.get("kind") in SIGNAL_KINDS, "invalid signal kind")
        for key in ("tuning_id", "magnitude"):
            if item.get(key) is not None:
                bounded_string(item[key], MAX_ID_LENGTH, "signal.%s" % key, False)
        if item.get("game_text") is not None:
            bounded_string(item["game_text"], MAX_DISPLAY_TEXT_LENGTH,
                           "signal.game_text", False)
        if version == 5 and item.get("tuning_name") is not None:
            bounded_string(item["tuning_name"], 128, "signal.tuning_name", False)
        if item.get("consequences") is not None:
            bounded_string(item["consequences"], MAX_ID_LENGTH,
                           "signal.consequences", False)
            _require(item["consequences"] in SIGNAL_CONSEQUENCES,
                     "invalid signal consequences")
        if item.get("native_override") is not None:
            _require(item["native_override"] == "UNKNOWN",
                     "invalid signal native_override")


def _validate_payload_contracts(row):
    """Keep event-specific ownership explicit: only observation rows carry payload."""
    kind = row["event_kind"]
    if kind in ("session_close", "guard_exhausted", "dropped_summary",
                "cap_reached", "writer_failed"):
        _require(row.get("game") == _default_game(), "%s game payload" % kind)
        _require(row.get("save") == _default_save(), "%s save payload" % kind)
        _require(row.get("zone") == _default_zone(), "%s zone payload" % kind)
        _require(row.get("body") == _default_body(), "%s body payload" % kind)
        _require(row.get("interactions") == _default_interactions(),
                 "%s interactions payload" % kind)
        _require(row.get("motives") == [], "%s motives payload" % kind)
        _require(row.get("sim_signals") == [], "%s sim_signals payload" % kind)
        _require(row.get("presence") == [], "%s presence payload" % kind)
        _require(row.get("social") == [], "%s social payload" % kind)
        _require(row.get("mood") is None, "%s mood payload" % kind)
        _require(row.get("observation_complete") is None,
                 "%s observation payload" % kind)
        _require(row.get("attestation") == attestation(),
                 "%s attestation payload" % kind)
    elif kind == "session_checkpoint":
        if row.get("checkpoint_reason") != "PERIODIC_60S":
            _require(row.get("game") == _default_game(), "%s game payload" % kind)
        _require(row.get("save") == _default_save(), "%s save payload" % kind)
        _require(row.get("zone") == _default_zone(), "%s zone payload" % kind)
        _require(row.get("body") == _default_body(), "%s body payload" % kind)
        _require(row.get("interactions") == _default_interactions(),
                 "%s interactions payload" % kind)
        _require(row.get("motives") == [], "%s motives payload" % kind)
        _require(row.get("sim_signals") == [], "%s sim_signals payload" % kind)
        _require(row.get("presence") == [], "%s presence payload" % kind)
        _require(row.get("social") == [], "%s social payload" % kind)
        _require(row.get("mood") is None, "%s mood payload" % kind)
        _require(row.get("observation_complete") is None,
                 "%s observation payload" % kind)
        _require(row.get("attestation") == attestation(),
                 "%s attestation payload" % kind)
    elif kind == "clock_snapshot":
        _require(row.get("save") == _default_save(), "clock save payload")
        _require(row.get("zone") == _default_zone(), "clock zone payload")
        _require(row.get("body") == _default_body(), "clock body payload")
        _require(row.get("interactions") == _default_interactions(),
                 "clock interactions payload")
        _require(row.get("motives") == [] and row.get("sim_signals") == [],
                 "clock semantic payload")
        _require(row.get("presence") == [] and row.get("social") == [] and
                 row.get("mood") is None, "clock sense payload")
    elif kind == "zone_snapshot":
        _require(row.get("save") == _default_save(), "zone save payload")
        _require(row.get("body") == _default_body(), "zone body payload")
        _require(row.get("interactions") == _default_interactions(),
                 "zone interactions payload")
        _require(row.get("motives") == [] and row.get("sim_signals") == [],
                 "zone semantic payload")
        _require(row.get("presence") == [] and row.get("social") == [] and
                 row.get("mood") is None, "zone sense payload")
    elif kind == "save_observation":
        _require(row.get("zone") == _default_zone(), "save zone payload")
        _require(row.get("body") == _default_body(), "save body payload")
        _require(row.get("interactions") == _default_interactions(),
                 "save interactions payload")
        _require(row.get("motives") == [] and row.get("sim_signals") == [],
                 "save semantic payload")
        _require(row.get("presence") == [] and row.get("social") == [] and
                 row.get("mood") is None, "save sense payload")
    elif kind == "session_open":
        _require(row.get("motives") == [] and row.get("sim_signals") == [],
                 "session open semantic payload")
        _require(row.get("presence") == [] and row.get("social") == [] and
                 row.get("mood") is None, "session open sense payload")
    elif kind in E2_EVENT_KINDS:
        _require(row.get("save") == _default_save(), "%s save payload" % kind)
        _require(row.get("zone") == _default_zone(), "%s zone payload" % kind)
        _require(row.get("body") == _default_body(), "%s body payload" % kind)
        _require(row.get("interactions") == _default_interactions(),
                 "%s interactions payload" % kind)
        _require(row.get("motives") == [] and row.get("sim_signals") == [],
                 "%s semantic payload" % kind)
        _require(row.get("presence") == [] and row.get("social") == [] and
                 row.get("mood") is None, "%s sense payload" % kind)
        _require(row.get("attestation") == attestation(),
                 "%s attestation payload" % kind)


def _validate_common(row):
    _require(set(row).issubset(COMMON_KEYS), "unknown schema field")
    _require(type(row.get("schema_version")) is int and
             row["schema_version"] in ACCEPTED_SCHEMA_VERSIONS, "schema_version")
    version = row["schema_version"]
    _require(row.get("event_kind") in EVENT_KINDS, "event_kind")
    _require(type(row.get("written_sequence")) is int and row["written_sequence"] >= 0,
             "written_sequence")
    _require(type(row.get("wall_timestamp_ms")) is int, "wall_timestamp_ms")
    _require(type(row.get("monotonic_ns")) is int, "monotonic_ns")
    bounded_string(row.get("probe_version"), MAX_ID_LENGTH, "probe_version", False)
    bounded_string(row.get("sims_build"), MAX_ID_LENGTH, "sims_build", False)
    game = row.get("game")
    _require(isinstance(game, dict) and set(game) ==
             {"ticks", "calendar", "clock_speed", "paused"}, "game")
    if game["ticks"] is not None:
        _require(type(game["ticks"]) is int, "game.ticks")
    for field in ("calendar", "clock_speed"):
        if game[field] is not None:
            bounded_string(game[field], MAX_DISPLAY_TEXT_LENGTH, "game.%s" % field, False)
    if game["paused"] is not None:
        _require(type(game["paused"]) is bool, "game.paused")
    if row.get("telemetry_session_id") is not None:
        string_id(row["telemetry_session_id"], "telemetry_session_id")
    if row.get("boot_id") is not None:
        _require(isinstance(row["boot_id"], str), "boot_id must be a string")
        string_id(row["boot_id"], "boot_id")
    if row.get("telemetry_session_id") is not None:
        _require(isinstance(row["telemetry_session_id"], str),
                 "telemetry_session_id must be a string")
    _validate_id_fields(row.get("save"), ("save_slot_guid", "slot_id"), "save")
    _validate_id_fields(row.get("zone"), ("zone_id", "lot_id", "room", "position"), "zone")
    _validate_id_fields(row.get("body"), ("sim_id",), "body")
    if row.get("body").get("instantiated") is not None:
        _require(type(row["body"]["instantiated"]) is bool, "body.instantiated")
    if row.get("body").get("is_selectable") is not None:
        _require(type(row["body"]["is_selectable"]) is bool, "body.is_selectable")
    if row.get("body").get("is_selected") is not None:
        _require(type(row["body"]["is_selected"]) is bool, "body.is_selected")
    _validate_posture(row["body"].get("posture"))
    _validate_e2(row)
    _validate_attestation(row.get("attestation"))
    _require(row.get("availability") in AVAILABILITY, "availability")
    _require(isinstance(row.get("counters"), dict) and
             set(row["counters"]) == {"dropped_queue", "dropped_overrun",
                                       "dropped_serialize", "redundant_starts"},
             "counters")
    for counter in row["counters"].values():
        _require(type(counter) is int and counter >= 0, "counter value")
    _require(isinstance(row.get("writer"), dict) and
             set(row["writer"]) == {"state", "rotation_index"}, "writer")
    _require(row["writer"].get("state") in WRITER_STATES, "writer.state")
    _require(type(row["writer"].get("rotation_index")) is int and
             row["writer"]["rotation_index"] >= 0, "writer.rotation_index")
    _validate_interactions(row.get("interactions"))
    _validate_motives(row.get("motives"))
    _validate_signals(row.get("sim_signals"), version)
    _validate_presence(row.get("presence"))
    _validate_social(row.get("social"), version)
    _validate_mood(row.get("mood"), version)
    _require(isinstance(row.get("missingness"), dict), "missingness")
    for field, item in row["missingness"].items():
        bounded_string(field, MAX_ID_LENGTH, "missingness field", False)
        _require(isinstance(item, dict), "missingness item")
        _require(item.get("status") in MISSINGNESS_STATUSES, "missingness status")
        if item.get("detail") is not None:
            bounded_string(item["detail"], MAX_DETAIL_LENGTH, "missingness detail", False)


def validate_row(row):
    """Validate one telemetry row. Schema 4 keeps its old shapes; schema 5 adds names."""
    validate_record(row)
    return row


def validate_record(row):
    _require(isinstance(row, dict), "record must be an object")
    _require(row.get("event_kind") in EVENT_KINDS, "event_kind")
    if row["event_kind"] == "load_disabled":
        _require(set(row).issubset({
            "schema_version", "telemetry_session_id", "boot_id", "written_sequence",
            "wall_timestamp_ms", "monotonic_ns", "probe_version", "sims_build",
            "event_kind", "reason", "attestation", "runtime",
        }), "unknown load_disabled field")
        _require(row.get("telemetry_session_id") is None, "load_disabled session id")
        _require(row.get("boot_id") is not None, "load_disabled boot id")
        _require(type(row.get("schema_version")) is int and
                 row["schema_version"] in ACCEPTED_SCHEMA_VERSIONS,
                 "load_disabled schema_version")
        _require(type(row.get("written_sequence")) is int and row["written_sequence"] >= 0,
                 "load_disabled written_sequence")
        _require(type(row.get("wall_timestamp_ms")) is int, "load_disabled wall")
        _require(type(row.get("monotonic_ns")) is int, "load_disabled monotonic")
        _require(isinstance(row.get("boot_id"), str), "load_disabled boot id type")
        bounded_string(row.get("probe_version"), MAX_ID_LENGTH, "probe_version", False)
        bounded_string(row.get("sims_build"), MAX_ID_LENGTH, "sims_build", False)
        _validate_attestation(row.get("attestation"))
        _require(row.get("attestation", {}).get("armed_name") == "UNARMED",
                 "load_disabled armed_name")
        _require(isinstance(row.get("runtime"), dict), "load_disabled runtime")
        _validate_load_disabled_runtime(row["runtime"])
        for forbidden in ("save", "zone", "body", "interactions", "motives", "sim_signals",
                            "presence", "social", "mood"):
            _require(forbidden not in row, "load_disabled contains %s" % forbidden)
    else:
        _validate_common(row)
    _validate_string_tree(row)
    encoded = json.dumps(row, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode("utf-8")
    _require(len(encoded) <= MAX_SERIALIZED_RECORD_BYTES, "serialized record exceeds 8 KiB")
    kind = row["event_kind"]
    if kind in ("session_open", "presence_snapshot", "save_observation"):
        _require(row.get("telemetry_session_id") is not None, "%s session id" % kind)
    if kind == "session_open":
        _require(row["attestation"]["armed_name"] in ("LAB_E1", "LAB_E1_FORK"),
                 "session_open attestation")
        _require(row["attestation"]["snapshot_guid"] is not None and
                 row["attestation"]["snapshot_slot"] is not None and
                 row["attestation"]["snapshot_sim"] is not None,
                 "session_open snapshot")
        _validate_id_fields(row.get("save"), ("save_slot_guid", "slot_id"), "save")
        _validate_id_fields(row.get("zone"), ("zone_id", "lot_id", "room", "position"), "zone")
        _validate_id_fields(row.get("body"), ("sim_id",), "body")
    if kind == "presence_snapshot":
        _require(type(row.get("observation_complete")) is bool,
                 "presence observation_complete")
        _require(isinstance(row.get("save"), dict) and isinstance(row.get("zone"), dict) and
                 isinstance(row.get("body"), dict), "presence payload")
    if kind == "save_observation":
        _require(row.get("observation_complete") is True, "save observation complete")
        _validate_id_fields(row.get("save"), ("save_slot_guid", "slot_id"), "save")
    if kind == "session_checkpoint":
        _require(row.get("telemetry_session_id") is not None, "checkpoint session id")
        _require(row.get("checkpoint_reason") in ("PERIODIC_60S", "ROTATION", "PRE_DISARM"),
                 "checkpoint_reason")
    if kind == "session_close":
        _require(row.get("telemetry_session_id") is not None, "close session id")
        _require(row.get("close_reason") in ("DISARM_CLEAN", "CAP_REACHED",
                                               "FAILED_STICKY", "ARMED_NEVER_STARTED"),
                 "close_reason")
    if kind == "clock_snapshot":
        _require(row.get("telemetry_session_id") is not None and isinstance(row.get("game"), dict),
                 "clock payload")
    if kind == "zone_snapshot":
        _require(row.get("telemetry_session_id") is not None and isinstance(row.get("zone"), dict),
                 "zone payload")
    if kind == "guard_exhausted":
        _require(row.get("reason") is not None, "guard reason")
    if kind == "dropped_summary":
        _require(row.get("reason") in ("QUEUE_SATURATION", "SAMPLER_OVERRUN", "SERIALIZE_FAILURE"),
                 "drop reason")
    if kind in ("cap_reached", "writer_failed"):
        expected = "CAP_REACHED" if kind == "cap_reached" else "FAILED_STICKY"
        _require(row.get("writer", {}).get("state") == expected, "diagnostic writer state")
    _validate_payload_contracts(row)
    return row


def serialize_record(row):
    validate_record(row)
    return json.dumps(row, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode("utf-8")
