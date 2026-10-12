"""Pure E1/E2 telemetry schema and bounded record validation."""

import json


# 2.37.0 (schema 19, W10): the act menu's `cached` count and `excluded_phone` names. Rows of schema 18 still validate.
# 2.39.0 (schema 20, W12): optional keys only (variants, refusals, names, hold_left_s, dropped); rows of 19 validate.
OBSERVATION_SCHEMA_VERSION = 21
TELEMETRY_SCHEMA_ID = "e1.telemetry/v21"
PROBE_VERSION = "2.40.0"
# 2.15.3: HOME is Ashley's own save; only LAB_E1 and LAB_E1_FORK allow the lab-only tools.
ARM_NAMES = ("LAB_E1", "LAB_E1_FORK", "HOME")
ACCEPTED_SCHEMA_VERSIONS = (4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21)
SIMS_BUILD = "1.128.90.1030"
# DS3: rows grew with place, company and moodlet blueprints (p50 4.4 KB before);
# 1024 queued x 16 KiB = 16 MiB worst-case writer queue.
# 2.18.0: 32 KiB (was 16): picker rows of an open dialog fit beside everything else.
# 2.19.0: 48 KiB: a 24-object act menu (48 MiB worst-case queue).
MAX_SERIALIZED_RECORD_BYTES = 48 * 1024
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
    "act_event",
    "act_menu",
    # 2.40.0 (W13 P1): the discovery record (once per zone load), the lists her view counts, and a text or call.
    "discovery",
    "lists",
    "phone",
)
E2_EVENT_KINDS = ("experiment_event", "speed_event", "lineage_event", "command_event",
                  "act_event", "act_menu", "discovery", "lists", "phone")
E2_PAYLOAD_KEYS = {
    "command_event": ("id", "issuer", "command", "status", "code"),
    "experiment_event": ("phase", "code", "experiment_id", "object_id", "token",
                         "interaction_id", "claims", "finishing_type", "detail",
                         "guid64", "card_class", "tuning_name", "ambiguous"),
    "speed_event": ("phase", "code", "detail"),
    # 2.32.0 (schema 15): reason, for BODY_GONE (her body died); None on every other record.
    "lineage_event": ("record", "guid", "slot_id", "sim_id", "ticks",
                      "loaded_from_slot_id", "lineage_class", "session_uuid", "reason"),
    # 2.16.0 (schema 10): Ashley's own acts (8f) and what she can do near her body.
    # 2.22.0: reason_key is optional (None when the tooltip has no string key).
    # 2.23.0: closed and resumed are optional on FINISHED (None on earlier rows
    # and on every other phase). Filled in below, so schema stays 12, as 2.9.2
    # added experiment fields without a version bump. Schema 11 and 12 bumped
    # because a closed observation shape gained a key old rows must not carry.
    # 2.24.0: owner (ACCEPTED: pushed at Critical because the User asked) and started
    # (FINISHED of a pushed act: did the game ever begin it) are optional the same way.
    # 2.28.0: aliases (PUSHED: the other interaction ids the push put in her queue, at most
    # ACT_MAX_ALIASES; None when there are none) is optional the same way.
    "act_event": ("act_id", "phase", "code", "object_id", "guid64", "interaction_id",
                  "tuning_name", "finishing_type", "detail", "reason_key",
                  "closed", "resumed", "owner", "started", "aliases"),
    # 2.35.0 (D3): refused_phone is on part 0 (None on the other parts, and on older rows).
    # 2.37.0 (schema 19, W10): cached (candidates the far cache answered; None on older rows) and excluded_phone
    # (part 0 only, like refused_phone).
    # 2.39.0 (W12 C8, C11): dropped and spot_stages are on part 0 (None on the other parts, and on older rows).
    "act_menu": ("menu_rev", "room", "objects", "tested", "cached", "refused", "build_ms", "part", "parts",
                 "refused_phone", "excluded_phone", "dropped", "spot_stages"),
}
# 2.40.0 (W13 P1): the payloads of the discovery record, the lists and a phone event. The act_event row gains
# result (the facts of a verb's FINISHED or REJECTED row; None on every other row and on older rows).
E2_PAYLOAD_KEYS.update({
    "discovery": ("discovery_rev", "sections"),
    "lists": ("kind", "list_rev", "part", "parts", "digest", "count", "items"),
    "phone": ("kind", "from_sim_id", "notifies"),
})
E2_PAYLOAD_KEYS["act_event"] = E2_PAYLOAD_KEYS["act_event"] + ("result",)
# 2.40.0 (W13 P2, home): the catalogue record (`catalog`), in parts. The things list is a `lists` record (kind things).
EVENT_KINDS = EVENT_KINDS + ("catalog",)
E2_EVENT_KINDS = E2_EVENT_KINDS + ("catalog",)
E2_PAYLOAD_KEYS["catalog"] = ("catalog_rev", "part", "parts", "items")
ACT_PHASES = ("ACCEPTED", "REJECTED", "PUSHED", "FINISHED", "UNKNOWN", "WAITING", "NOTED")
# 2.28.0: the queue entries a pushed act was seen to add, recorded beside its interaction id.
ACT_MAX_ALIASES = 4
# 2.23.0: what her answer did to the pause the dialog made.
RESUME_RESULTS = ("released", "restored", "not_hers", "not_paused", "player_paused",
                  "other_dialog_open", "failed")
# 2.19.0: 12 left the kitchen and the bedroom out of a nine-room house.
# 2.34.0 (N8, F4): every object on the lot with acts for her (the probe keeps rows under the record limit in parts).
# 2.39.0 (W12 C8): 512 (was 256: whole rooms were dropped); what the cap leaves out is counted in part 0's dropped.
MENU_MAX_OBJECTS = 512
MENU_MAX_PARTS = 64
MENU_MAX_ACTS = 8
# 2.37.0 (W10 P3): her phone is one entry for all its acts, so it has its own cap (call and invite came after the 8th).
MENU_MAX_PHONE_ACTS = 48
# 2.25.0: reach (the game's own connectivity check from her to the object; None when unread).
# 2.29.0: phone (True on her own phone's entry, None on every other object) is optional the same way.
# 2.35.0 (D3): spot and level are the spot's kind ("room" or "front_door") and its level; None on every object.
MENU_OBJECT_KEYS = ("object_id", "definition_id", "class", "distance_m", "same_room", "room", "reach", "acts", "phone",
                    "spot", "level")
MENU_SPOT_KINDS = ("room", "front_door")
# 2.35.0 (D3): the phone's offers the game's preflight refuses, by tuning name and reason key (a diagnostic).
# 2.37.0 (W10 P3): at most 64 (was 16: a phone with more than 16 acts lost the later ones).
MENU_MAX_REFUSED_PHONE = 64
MENU_REFUSED_KEYS = ("name", "reason_key")
# 2.37.0 (W10 P3): the phone's acts the guard excluded before the game's test, by name and why (at most 64).
MENU_MAX_EXCLUDED_PHONE = 64
MENU_EXCLUDED_KEYS = ("name", "why")
MENU_EXCLUDED_WHY = ("pie_picker", "deny_name", "travel", "not_user_directed", "hidden")
MENU_ACT_KEYS = ("guid64", "name", "text_key")
# 2.39.0 (W12 G1, C4, C10, C12): optional on older rows. An act's variant is a pie-menu choice's index (0..999);
# an object's on_lot (bool or None), acts_cut (passing acts the per-object cap left out, after folding texts) and
# refusals (near objects only: at most 8 {text_key, reason_key} of the acts the game refused).
MENU_ACT_OPTIONAL_KEYS = ("variant", "needs_sim")
MENU_MAX_VARIANT = 999
MENU_OBJECT_OPTIONAL_KEYS = ("on_lot", "acts_cut", "refusals")
MENU_MAX_REFUSALS = 8
MENU_REFUSAL_KEYS = ("text_key", "reason_key")
# 2.39.0 (W12 C8, C11): part 0's dropped {objects, rooms} and spot_stages counters.
MENU_DROPPED_KEYS = ("objects", "rooms")
MENU_MAX_DROPPED_ROOMS = 64
MENU_MAX_SPOT_STAGES = 16
EXPERIMENT_PHASES = (
    "SIGNATURE_LEARNED", "CONTINUATION_LEARNED", "PREPARE_OK", "PREPARE_REJECT",
    "ADMIT_REJECT", "PUSHED", "PUSH_FAILED", "CLAIM", "FINISHED_CALLBACK",
    "VERDICT", "CALIBRATE_START", "CALIBRATE_SPEED", "TRIAL_REJECT",
    "TRIAL_CLEANUP", "PUSH_REFUSED",
)
COMMANDS = ("arm", "start", "stop", "disarm", "prepare", "sit", "pause",
            "release", "status", "sit_trial", "atlas_dump", "tuned_scan",
            "calibrate", "trial", "preflight", "food_scan", "situation_scan", "act", "camera", "talk",
            "pace", "answer", "cancel", "menu_near")
# 2.40.0 (W13 P1): travel, a planned event, and a fresh read of the lists. Own line, so the commands of other blocks merge.
COMMANDS = COMMANDS + ("go", "event", "lists_now")
# 2.40.0 (W13 P2, home): her save and her home edits, and the catalogue dump (home.COMMANDS).
COMMANDS = COMMANDS + ("save", "buy", "place", "move", "sell", "catalog_dump")


def _command_id(value):
    return (type(value) is str and len(value) == 32 and
            all(ch in "0123456789abcdef" for ch in value))


def _command_issuer(value):
    return (type(value) is str and (value in ("helper", "console") or
            (value.startswith("agent:") and 1 <= len(value[6:]) <= 34 and
             all(ch in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in value[6:]))))


# 2.27.0: DIALOG_HELD (a picker her act opened, kept off the User's screen) and DIALOG_SHOWN
# (shown to the User after all: unanswered in time, or at a stop).
SPEED_PHASES = ("REQUEST_PUSHED", "REQUEST_REMOVED", "REJECT",
                "RELEASED_ON_DISARM", "RELEASED_ON_STOP", "RELEASE_FAILED",
                "DIALOG_HELD", "DIALOG_SHOWN", "SCREEN_WITHHELD", "UNKNOWN_SCREEN",
                # 2.31.0 (W3p): the probe refused the game clock because another mod sets it.
                # 2.31.0 (W4): the probe could not read the game clock (its own reason), and a held window
                # that vanished or was dropped by a zone change (ids only).
                "CLOCK_FOREIGN", "CLOCK_UNREADABLE", "DIALOG_DROPPED")
LINEAGE_RECORDS = ("LOAD_OBSERVED", "SAVE_OBSERVED", "DESIGNATED_BODY", "CLASSIFIED", "BODY_GONE")
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
    "event_kind", "reason", "checkpoint_reason", "close_reason", "drop_detail",
    "observation_complete", "attestation", "save", "zone", "body",
    "interactions", "motives", "sim_signals", "presence", "social", "mood",
    "missingness", "unsupported",
    "availability", "counters", "writer", "note", "e2",
    # S5 (schema 7): what appeared, vanished or changed on the lot; observation rows only.
    "objects",
    # 2.15.0 (schema 8): her traits, skills and household money; observation rows only.
    "self",
    # 2.15.2 (schema 9): whose lot and what venue; the game's pop-ups; observation rows.
    "place", "dialogs",
    # 2.31.0 (schema 14): her pace, as the probe applied it; observation rows only.
    "pace",
    # 2.36.0 (schema 18, D6): the weather and season now; the game's notices about her. Observation rows only.
    "weather", "notices",
}
MAX_OBJECT_EVENTS = 8
# 2.32.0 (HE7, schema 15): the notable states of one near object, and the near objects a sample names.
MAX_NEAR_STATES = 4
MAX_NEAR_CONDITIONS = 16
MAX_REL_TRACKS = 4
MAX_REL_LABELS = 6
MAX_KNOWN_TRAITS = 6
MAX_SENTIMENTS = 3
MAX_SELF_TRAITS = 12
MAX_SELF_SKILLS = 12
# 2.32.0 (PR13, schema 15): the occult types a presence entry names (a form of her own or another Sim's).
MAX_OCCULT_KINDS = 4
MAX_SELF_CAREERS = 4
MAX_SELF_WANTS = 8
# 2.36.0 (D6, schema 18): her aspiration's objectives, what she carries, the weather types and the notices.
MAX_SELF_OBJECTIVES = 6
MAX_SELF_INVENTORY = 24
MAX_WEATHER_TYPES = 6
MAX_NOTICES = 4
MAX_SITUATIONS = 3
MAX_DIALOGS = 4
MAX_DIALOG_RESPONSES = 6
# 2.18.0 (schema 11): the rows a picker dialog offers (a recipe, a Sim, an object), so she can answer.
MAX_DIALOG_ROWS = 40
DIALOG_ROW_KEYS = ("option_id", "name_key", "enabled", "price")
# 2.31.0 (schema 14, DOMUS_DEEP_DESIGN §11): who holds a window, and what she may answer. The text
# limits come from the held message (bytecode ui/ui_text_input.UiTextInput.build_msg); numbers and
# flags only, never game text.
WINDOW_KEYS = frozenset(("held", "cause", "select", "counts", "text_inputs"))
WINDOW_CAUSES = ("hers", "user", "identity_user")
MAX_TEXT_INPUTS = 8
MAX_TEXT_LIMIT = 4096
MAX_TEXT_VALUE = 2 ** 53
MAX_WINDOW_COUNT = 999
TEXT_FIELD_KEYS = frozenset(("name", "min_length", "max_length", "numeric", "min_value",
                             "max_value", "profanity_checked", "restricted", "default_key"))
FIELD_NAME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-")


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
    _require(armed_name in ARM_NAMES + ("UNARMED",),
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
    return {"ticks": None, "calendar": None, "clock_speed": None, "paused": None,
            "build_mode": None, "fire": None}


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
        "drop_detail": None,
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
                      "posture_name", "detail_text", "finishing_type", "type",
                      # DS3: names and texts that are not ids.
                      "name", "doing", "mood_type", "tuning_name",
                      # S5: tuning names of tracks, labels, classes and states.
                      "track", "label", "class", "state", "from", "to",
                      # 2.15.0: tuning names of traits, skills, sentiments, careers.
                      "trait", "skill", "sentiment", "careers",
                      # 2.15.2: situations, roles, venues, dialog classes and answers.
                      "situation", "role", "venue", "kind", "response",
                      # 2.30.0: tuning names of her wants and fears.
                      "want"):
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
    _require(value.get("armed_name") in ARM_NAMES + ("UNARMED",),
             "invalid attestation armed_name")
    for key in ("armed_name_hash", "snapshot_guid", "snapshot_slot", "snapshot_sim"):
        _require(key in value, "missing attestation.%s" % key)
        if value[key] is not None:
            _require(isinstance(value[key], str), "attestation.%s must be a string" % key)
            if key == "armed_name_hash":
                _require(len(value[key]) == 8, "attestation.armed_name_hash must be 8 characters")
            else:
                string_id(value[key], "attestation.%s" % key)


def _validate_zone(row):
    if row["schema_version"] >= 6:
        # DS3: zone, lot and room are ids; position is {x, y, z, level}.
        _validate_id_fields(row.get("zone"), ("zone_id", "lot_id", "room"), "zone")
        _validate_position(row["zone"].get("position"), "zone.position")
    else:
        _validate_id_fields(row.get("zone"), ("zone_id", "lot_id", "room", "position"), "zone")


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
    elif kind == "act_menu" and isinstance(payload, dict):
        # 2.35.0: refused_phone is optional; rows before schema 17 omit it.
        if "refused_phone" not in payload:
            payload["refused_phone"] = None
        # 2.37.0 (schema 19): cached and excluded_phone are optional; rows before schema 19 omit them.
        for key in ("cached", "excluded_phone"):
            if key not in payload:
                payload[key] = None
        # 2.39.0 (W12): dropped and spot_stages are optional; rows before schema 20 omit them.
        for key in ("dropped", "spot_stages"):
            if key not in payload:
                payload[key] = None
        # 2.25.0: reach is optional; older menu rows omit it. 2.29.0: so is phone. 2.35.0: so are spot and level.
        for item in payload.get("objects") or ():
            if isinstance(item, dict):
                if "reach" not in item:
                    item["reach"] = None
                if "phone" not in item:
                    item["phone"] = None
                if "spot" not in item:
                    item["spot"] = None
                if "level" not in item:
                    item["level"] = None
                # 2.39.0 (W12): on_lot, acts_cut and refusals are optional; a variant is optional on each act.
                for key in MENU_OBJECT_OPTIONAL_KEYS:
                    if key not in item:
                        item[key] = None
                for act in item.get("acts") or ():
                    if isinstance(act, dict) and "variant" not in act:
                        act["variant"] = None
    elif kind == "lineage_event" and isinstance(payload, dict):
        # 2.32.0: reason is optional; rows before schema 15 omit it.
        if "reason" not in payload:
            payload["reason"] = None
    elif kind == "act_event" and isinstance(payload, dict):
        # 2.22.0 / 2.23.0: optional. Older act rows omit them.
        if "reason_key" not in payload:
            payload["reason_key"] = None
        if "closed" not in payload:
            payload["closed"] = None
        if "resumed" not in payload:
            payload["resumed"] = None
        if "owner" not in payload:
            payload["owner"] = None
        if "started" not in payload:
            payload["started"] = None
        if "aliases" not in payload:
            payload["aliases"] = None
        # 2.40.0 (W13 P1): result is optional; rows before schema 21 omit it.
        if "result" not in payload:
            payload["result"] = None
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
    elif kind == "act_event":
        _require(_command_id(payload["act_id"]), "act id")
        _require(payload["phase"] in ACT_PHASES, "act phase")
        for key in ("code", "object_id", "guid64", "interaction_id"):
            if payload[key] is not None:
                _require(isinstance(payload[key], str), "act %s" % key)
                string_id(payload[key], "act %s" % key)
        if payload["tuning_name"] is not None:
            bounded_string(payload["tuning_name"], 128, "act tuning_name", False)
        if payload["finishing_type"] is not None:
            bounded_string(payload["finishing_type"], MAX_DISPLAY_TEXT_LENGTH,
                           "act finishing_type", False)
        if payload["detail"] is not None:
            bounded_string(payload["detail"], MAX_DETAIL_LENGTH, "act detail", False)
        if payload["reason_key"] is not None:
            _require(isinstance(payload["reason_key"], str), "act reason_key must be a string")
            string_id(payload["reason_key"], "act reason_key")
        if payload["closed"] is not None:
            _require(type(payload["closed"]) is bool, "act closed")
        if payload["resumed"] is not None:
            _require(payload["resumed"] in RESUME_RESULTS, "act resumed")
        for key in ("owner", "started"):
            if payload[key] is not None:
                _require(type(payload[key]) is bool, "act %s" % key)
        if payload["aliases"] is not None:
            _require(type(payload["aliases"]) is list and len(payload["aliases"]) <= ACT_MAX_ALIASES,
                     "act aliases")
            for item in payload["aliases"]:
                _require(isinstance(item, str), "act alias must be a string")
                string_id(item, "act alias")
        _validate_result(payload["result"])
    elif kind == "act_menu":
        _validate_menu(payload)
    elif kind in ("discovery", "lists", "phone"):
        _validate_reach(kind, payload)
        if kind == "lists" and payload["kind"] == "things":
            # 2.40.0 (W13 P2): each things row has the things keys.
            for item in payload["items"]:
                _validate_thing(item)
    elif kind == "catalog":
        _validate_catalog_record(payload)
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
        bounded_string(payload.get("reason"), MAX_REASON_LENGTH, "lineage reason")


# 2.40.0 (W13 P1, schema 21): the discovery record, the lists, a phone event, and the facts of a verb's row.
# Pure shape checks; the probe's reads are in observers.py and its records are built in reach.py.
RESULT_MAX_KEYS = 16
RESULT_MAX_BYTES = 512
RESULT_LIST_MAX = 4
# A list item in a result is a game id (at most 20 digits, as _is_digits allows) or a short word: 20 characters.
RESULT_LIST_ITEM_MAX = 20
DISCOVERY_MAX_RECORD_BYTES = 40 * 1024 + 4096
LIST_PART_MAX = 128
LIST_KIND_NAMES = ("people", "places", "things", "events")
# 2.40.0 (W13 P1 fix): a phone row is a notice on her phone or a call held for her.
PHONE_KIND_NAMES = ("notice", "call")
DISCOVERY_KEY_NAMES = frozenset(("pickers", "phone_tests", "off_lot", "save", "situations", "career",
                                 "population", "dropped", "unread"))
PLACE_KIND_NAMES = ("home", "household", "venue")
PERSON_KEYS = frozenset(("sim_id", "first_name", "last_name", "labels", "tracks", "household_id", "has_home", "on_lot",
                         "waiting"))
PLACE_KEYS = frozenset(("zone_id", "kind", "lot_name", "venue", "household_id"))
EVENT_KEYS = frozenset(("situation_id", "name_key", "cost", "schedulable"))


def _validate_result(value):
    """2.40.0 (W13 P1): a verb's facts (plain values only, never text beyond short words); None when there are none."""
    if value is None:
        return
    _require(isinstance(value, dict) and len(value) <= RESULT_MAX_KEYS, "act result")
    _require(set(value) <= RESULT_KEY_NAMES, "act result keys")
    for key, item in value.items():
        bounded_string(key, 32, "act result key", False)
        if item is None or type(item) in (int, bool):
            continue
        if type(item) is str:
            _require(len(item) <= 64, "act result word")
            continue
        _require(type(item) is list and len(item) <= RESULT_LIST_MAX and
                 all(type(x) is str and len(x) <= RESULT_LIST_ITEM_MAX for x in item), "act result value")
    _require(len(json.dumps(value, separators=(",", ":"))) <= RESULT_MAX_BYTES, "act result size")
    _validate_home_facts(value)


def _validate_reach(kind, payload):
    if kind == "discovery":
        _require(type(payload["discovery_rev"]) is int and payload["discovery_rev"] >= 1, "discovery rev")
        sections = payload["sections"]
        _require(isinstance(sections, dict) and set(sections) <= DISCOVERY_KEY_NAMES, "discovery sections")
        for name, value in sections.items():
            _require(type(value) in (dict, list), "discovery section %s" % name)
        _require(len(json.dumps(payload, separators=(",", ":"))) <= DISCOVERY_MAX_RECORD_BYTES, "discovery size")
    elif kind == "lists":
        _require(payload["kind"] in LIST_KIND_NAMES, "list kind")
        _require(type(payload["list_rev"]) is int and payload["list_rev"] >= 1, "list rev")
        _require(type(payload["parts"]) is int and 1 <= payload["parts"] <= MENU_MAX_PARTS, "list parts")
        _require(type(payload["part"]) is int and 0 <= payload["part"] < payload["parts"], "list part")
        _require(isinstance(payload["digest"], str) and len(payload["digest"]) == 64 and
                 all(ch in "0123456789abcdef" for ch in payload["digest"]), "list digest")
        _require(type(payload["count"]) is int and payload["count"] >= 0, "list count")
        items = payload["items"]
        _require(isinstance(items, list) and len(items) <= LIST_PART_MAX and
                 all(isinstance(item, dict) for item in items), "list items")
        # 2.40.0 (W13 P1 fix): each item of a people, places or events list has its keys and value shapes (things: below).
        for item in items if payload["kind"] in LIST_ITEM_VALIDATORS else ():
            LIST_ITEM_VALIDATORS[payload["kind"]](item)
    else:
        _require(payload["kind"] in PHONE_KIND_NAMES, "phone kind")
        for key in ("from_sim_id", "notifies"):
            if payload[key] is not None:
                string_id(payload[key], "phone %s" % key)


def _is_flag_or_none(value):
    return value is None or type(value) is bool


def _is_short_text_or_none(value, limit):
    return value is None or (type(value) is str and len(value) <= limit)


def _validate_person(item):
    """2.40.0 (W13 P1 fix): a person she knows, as reach.person_item writes it."""
    _require(set(item) == PERSON_KEYS, "person keys")
    _require(_is_digits(item["sim_id"]), "person sim_id")
    _require(item["household_id"] is None or _is_digits(item["household_id"]), "person household_id")
    for key in ("first_name", "last_name"):
        _require(_is_short_text_or_none(item[key], 64), "person %s" % key)
    labels = item["labels"]
    _require(type(labels) is list and len(labels) <= 4 and
             all(type(label) is str and 1 <= len(label) <= 40 for label in labels), "person labels")
    tracks = item["tracks"]
    _require(type(tracks) is dict and len(tracks) <= 4 and
             all(type(name) is str and len(name) <= 40 and type(value) is int for name, value in tracks.items()),
             "person tracks")
    for key in ("has_home", "on_lot", "waiting"):
        _require(_is_flag_or_none(item[key]), "person %s" % key)


def _validate_place_item(item):
    """2.40.0 (W13 P1 fix): a place she can go, as reach.place_item writes it. 2.40.0 (W13 R2): renamed from
    _validate_place, which is the self-place row's name."""
    _require(set(item) == PLACE_KEYS, "place keys")
    _require(_is_digits(item["zone_id"]), "place zone_id")
    _require(item["kind"] in PLACE_KIND_NAMES, "place kind")
    _require(_is_short_text_or_none(item["lot_name"], 64), "place lot_name")
    _require(_is_short_text_or_none(item["venue"], 64), "place venue")
    _require(item["household_id"] is None or _is_digits(item["household_id"]), "place household_id")


def _validate_event(item):
    """2.40.0 (W13 P1 fix): an event type she may plan, as reach.event_item writes it."""
    _require(set(item) == EVENT_KEYS, "event keys")
    _require(_is_digits(item["situation_id"]), "event situation_id")
    _require(_is_short_text_or_none(item["name_key"], 32), "event name_key")
    _require(_is_int_or_none(item["cost"]), "event cost")
    _require(_is_flag_or_none(item["schedulable"]), "event schedulable")


LIST_ITEM_VALIDATORS = {"people": _validate_person, "places": _validate_place_item, "events": _validate_event}


def _validate_menu(payload):
    _require(type(payload["menu_rev"]) is int and payload["menu_rev"] >= 0, "menu rev")
    if payload["room"] is not None:
        _require(isinstance(payload["room"], str), "menu room")
        string_id(payload["room"], "menu room")
    for key in ("tested", "refused"):
        _require(type(payload[key]) is int and payload[key] >= 0, "menu %s" % key)
    if payload["cached"] is not None:
        _require(type(payload["cached"]) is int and payload["cached"] >= 0, "menu cached")
    _number_or_none(payload["build_ms"], "menu build_ms")
    objects = payload["objects"]
    _require(type(payload["part"]) is int and type(payload["parts"]) is int, "menu part")
    _require(0 <= payload["part"] < payload["parts"] <= MENU_MAX_PARTS, "menu part range")
    refused = payload["refused_phone"]
    if refused is not None:
        _require(type(refused) is list and len(refused) <= MENU_MAX_REFUSED_PHONE, "menu refused_phone")
        for item in refused:
            _require(isinstance(item, dict) and set(item) == set(MENU_REFUSED_KEYS), "menu refused shape")
            bounded_string(item["name"], 128, "menu refused name", False)
            if item["reason_key"] is not None:
                _require(isinstance(item["reason_key"], str), "menu refused reason_key")
                string_id(item["reason_key"], "menu refused reason_key")
    excluded = payload["excluded_phone"]
    if excluded is not None:
        _require(type(excluded) is list and len(excluded) <= MENU_MAX_EXCLUDED_PHONE, "menu excluded_phone")
        for item in excluded:
            _require(isinstance(item, dict) and set(item) == set(MENU_EXCLUDED_KEYS), "menu excluded shape")
            bounded_string(item["name"], 128, "menu excluded name", False)
            _require(item["why"] in MENU_EXCLUDED_WHY, "menu excluded why")
    _menu_dropped(payload.get("dropped"))
    _menu_spot_stages(payload.get("spot_stages"))
    _require(isinstance(objects, list) and len(objects) <= MENU_MAX_OBJECTS, "menu objects")
    for item in objects:
        _require(isinstance(item, dict) and set(item) - set(MENU_OBJECT_OPTIONAL_KEYS) == set(MENU_OBJECT_KEYS),
                 "menu object shape")
        _require(isinstance(item["object_id"], str), "menu object_id")
        string_id(item["object_id"], "menu object_id")
        if item["room"] is not None:
            _require(isinstance(item["room"], str), "menu object room")
            string_id(item["room"], "menu object room")
        if item["definition_id"] is not None:
            _require(isinstance(item["definition_id"], str), "menu definition_id")
            string_id(item["definition_id"], "menu definition_id")
        bounded_string(item["class"], 96, "menu class", False)
        _number_or_none(item["distance_m"], "menu distance_m")
        _require(item["same_room"] in (True, False, None), "menu same_room")
        _require(item["reach"] in (True, False, None), "menu reach")
        _require(item["phone"] in (True, False, None), "menu phone")
        _require(item["spot"] in MENU_SPOT_KINDS + (None,), "menu spot")
        _require(item["level"] is None or type(item["level"]) is int, "menu level")
        _require(item["spot"] is None or item["class"] == "spot", "menu spot class")
        acts = item["acts"]
        cap = MENU_MAX_PHONE_ACTS if item["phone"] is True else MENU_MAX_ACTS
        _require(item.get("on_lot") in (True, False, None), "menu on_lot")
        if item.get("acts_cut") is not None:
            _require(type(item["acts_cut"]) is int and item["acts_cut"] >= 0, "menu acts_cut")
        _menu_refusals(item.get("refusals"))
        _require(isinstance(acts, list) and len(acts) <= cap and (acts or item.get("refusals")), "menu acts")
        for act in acts:
            _require(isinstance(act, dict) and set(act) - set(MENU_ACT_OPTIONAL_KEYS) == set(MENU_ACT_KEYS),
                     "menu act shape")
            if act.get("variant") is not None:
                _require(type(act["variant"]) is int and 0 <= act["variant"] <= MENU_MAX_VARIANT, "menu variant")
            # 2.40.0 (W13 P1): a phone act that opens a Sim picker is listed with needs_sim (absent on every other act).
            if "needs_sim" in act:
                _require(act["needs_sim"] is True, "menu needs_sim")
            _require(isinstance(act["guid64"], str), "menu guid64")
            string_id(act["guid64"], "menu guid64")
            bounded_string(act["name"], 128, "menu act name", False)
            if act["text_key"] is not None:
                _require(isinstance(act["text_key"], str), "menu text_key")
                string_id(act["text_key"], "menu text_key")


def _menu_dropped(dropped):
    """2.39.0 (W12 C8): None, or {objects: int, rooms: [room ids]} for what the object cap left out."""
    if dropped is None:
        return
    _require(isinstance(dropped, dict) and set(dropped) == set(MENU_DROPPED_KEYS), "menu dropped shape")
    _require(type(dropped["objects"]) is int and dropped["objects"] >= 0, "menu dropped objects")
    rooms = dropped["rooms"]
    _require(type(rooms) is list and len(rooms) <= MENU_MAX_DROPPED_ROOMS, "menu dropped rooms")
    for room in rooms:
        _require(isinstance(room, str), "menu dropped room")
        string_id(room, "menu dropped room")


def _menu_spot_stages(stages):
    """2.39.0 (W12 C11): None, or a small dict of counters and flags (how far each spot got)."""
    if stages is None:
        return
    _require(isinstance(stages, dict) and len(stages) <= MENU_MAX_SPOT_STAGES, "menu spot_stages")
    for key, value in stages.items():
        _require(isinstance(key, str) and len(key) <= 32, "menu spot_stages key")
        _require(isinstance(value, bool) or (type(value) is int and value >= 0), "menu spot_stages value")


def _menu_refusals(refusals):
    """2.39.0 (W12 C4): None (a far object), or at most MENU_MAX_REFUSALS refusals of a near object's acts."""
    if refusals is None:
        return
    _require(type(refusals) is list and len(refusals) <= MENU_MAX_REFUSALS, "menu refusals")
    for item in refusals:
        _require(isinstance(item, dict) and set(item) == set(MENU_REFUSAL_KEYS), "menu refusal shape")
        for key in MENU_REFUSAL_KEYS:
            if item[key] is not None:
                _require(isinstance(item[key], str), "menu refusal key")
                string_id(item[key], "menu refusal key")


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


PRESENCE_V6 = {"id", "active_household", "level", "is_body", "household_id", "name",
               "position", "room", "posture", "doing", "doing_target", "distance_m"}
PRESENCE_V7 = PRESENCE_V6 | {"relationship"}
PRESENCE_V8 = PRESENCE_V7 | {"on_lot"}
PRESENCE_V9 = PRESENCE_V8 | {"situations"}
# 2.32.0 (PR13, schema 15): a pet flag, the species name and the occult types of the Sim (None when unreadable).
PRESENCE_V15 = PRESENCE_V9 | {"is_pet", "species", "occult_kinds"}
# 2.39.0 (W12 E4, E5): the game's own name fields, on each presence item and on her body (self). Optional: a key
# is there when the game could read it, and a row without them is still valid. Gender is "F", "M" or None.
PRESENCE_NAME_KEYS = frozenset(("first_name", "last_name"))
SELF_PEOPLE_KEYS = frozenset(("gender", "first_name", "last_name"))
GENDER_CODES = ("F", "M")
MAX_NAME_PART_LENGTH = 64
# 2.39.0 (W12 A9): the seconds left on a held window until the fallback hands it to the User (optional).
DIALOG_HOLD_KEYS = frozenset(("hold_left_s",))
MAX_HOLD_LEFT_SECONDS = 3600


def _number_or_none(value, label):
    if value is not None:
        _require(isinstance(value, (int, float)) and not isinstance(value, bool),
                 "%s must be numeric" % label)


def _validate_position(value, label):
    """DS3: {x, y, z, level} in game units, or None."""
    if value is None:
        return
    _require(isinstance(value, dict) and set(value) == {"x", "y", "z", "level"},
             "%s shape" % label)
    for axis in ("x", "y", "z"):
        _require(isinstance(value[axis], (int, float)) and not isinstance(value[axis], bool),
                 "%s.%s must be numeric" % (label, axis))
    if value["level"] is not None:
        _require(type(value["level"]) is int, "%s.level must be int" % label)


def _validate_named(items, key, limit, label):
    _require(isinstance(items, list) and len(items) <= limit, label)
    for item in items:
        _require(isinstance(item, dict) and key in item, "%s entry" % label)
        bounded_string(item[key], 128, "%s.%s" % (label, key), False)
        if item.get("text_key") is not None:
            _require(isinstance(item["text_key"], str), "%s.text_key must be a string" % label)
            string_id(item["text_key"], "%s.text_key" % label)


def _validate_knows(value):
    """2.15.0: what she has learned about the other Sim; None when unreadable."""
    if value is None:
        return
    _require(isinstance(value, dict) and set(value) == {
        "traits", "careers", "relationship_status", "romantic_preference", "net_worth"},
        "relationship.knows shape")
    _validate_named(value["traits"], "trait", MAX_KNOWN_TRAITS, "knows.traits")
    for item in value["traits"]:
        _require(set(item) == {"trait", "text_key"}, "knows.traits entry")
    if value["careers"] is not None:
        _require(isinstance(value["careers"], list) and len(value["careers"]) <= 4,
                 "knows.careers")
        for career in value["careers"]:
            bounded_string(career, 128, "knows.career", False)
    for key in ("relationship_status", "romantic_preference"):
        _require(type(value[key]) is bool, "knows.%s" % key)
    if value["net_worth"] is not None:
        _require(type(value["net_worth"]) is int, "knows.net_worth")


def _validate_life(value):
    """2.32.0 (PR12, schema 15): her life state. Each flag is a bool or None (unreadable); age is a stage name or None."""
    _require(isinstance(value, dict) and set(value) == {"age", "pregnant", "sick", "dead", "ghost", "npc"},
             "self.life shape")
    bounded_string(value["age"], 128, "self.life.age")
    for key in ("pregnant", "sick", "dead", "ghost", "npc"):
        _require(value[key] is None or type(value[key]) is bool, "self.life.%s" % key)


def _validate_self(row):
    """2.15.0 (schema 8 presence_snapshot only): her traits, skills and money."""
    if "self" not in row:
        return
    _require(row["event_kind"] == "presence_snapshot" and row["schema_version"] >= 8,
             "self outside a schema 8 observation")
    value = row["self"]
    if value is None:
        return
    keys = ({"traits", "skills", "funds"} | ({"careers"} if row["schema_version"] >= 12 else set()) |
            ({"wants"} if row["schema_version"] >= 13 else set()) |
            ({"life"} if row["schema_version"] >= 15 else set()))
    # 2.36.0 (D6): the aspiration, the bills and the inventory are optional: a key is there only when readable.
    optional = {"aspiration", "bills", "inventory"} if row["schema_version"] >= 18 else set()
    # 2.39.0 (W12 E4, E5): her gender and name fields are optional, validated when present.
    optional = optional | SELF_PEOPLE_KEYS
    _require(isinstance(value, dict) and keys <= set(value) <= keys | optional, "self shape")
    _validate_self_people(value)
    if "life" in value:
        _validate_life(value["life"])
    if "aspiration" in value:
        _validate_self_aspiration(value["aspiration"])
    if "bills" in value:
        _validate_self_bills(value["bills"])
    if "inventory" in value:
        _validate_self_inventory(value["inventory"])
    if value["traits"] is not None:
        _validate_named(value["traits"], "trait", MAX_SELF_TRAITS, "self.traits")
        for item in value["traits"]:
            _require(set(item) == {"trait", "text_key", "personality"} and
                     type(item["personality"]) is bool, "self.traits entry")
    if value["skills"] is not None:
        _validate_named(value["skills"], "skill", MAX_SELF_SKILLS, "self.skills")
        for item in value["skills"]:
            _require(set(item) == {"skill", "text_key", "level"} and
                     type(item["level"]) is int, "self.skills entry")
    if value["funds"] is not None:
        _require(type(value["funds"]) is int, "self.funds")
    if value.get("careers") is not None:
        _validate_named(value["careers"], "career", MAX_SELF_CAREERS, "self.careers")
        for item in value["careers"]:
            _require(set(item) - {"until_min"} == {"career", "text_key", "title_key", "level", "at_work"} and
                     type(item["at_work"]) is bool and
                     (item["level"] is None or type(item["level"]) is int), "self.careers entry")
            # 2.40.0 (W13 P1): until_min, the game minute of the day her work session ends (while at_work); None when unread.
            if "until_min" in item:
                _require(item["until_min"] is None or
                         (type(item["until_min"]) is int and 0 <= item["until_min"] < 1440), "self.careers until_min")
            if item["title_key"] is not None:
                string_id(item["title_key"], "self.careers.title_key")
    if value.get("wants") is not None:
        # 2.30.0: what she wants and fears now (the game's wants and fears panel).
        _validate_named(value["wants"], "want", MAX_SELF_WANTS, "self.wants")
        for item in value["wants"]:
            _require(set(item) == {"want", "text_key", "tip_key", "fear", "locked", "done", "of", "until"} and
                     type(item["fear"]) is bool and type(item["locked"]) is bool and
                     all(item[key] is None or type(item[key]) is int for key in ("done", "of")),
                     "self.wants entry")
            if item["tip_key"] is not None:
                string_id(item["tip_key"], "self.wants.tip_key")
            until = item["until"]
            _require(until is None or (isinstance(until, list) and len(until) == 2 and
                                       all(type(part) is int for part in until) and
                                       0 <= until[0] < 24 and 0 <= until[1] < 60), "self.wants.until")


def _validate_self_aspiration(value):
    """2.36.0 (D6, P1): her primary aspiration's display text and the current milestone's objectives."""
    _require(isinstance(value, dict) and set(value) == {"name_key", "objectives"}, "self.aspiration")
    string_id(value["name_key"], "self.aspiration.name_key")
    _require(isinstance(value["objectives"], list) and len(value["objectives"]) <= MAX_SELF_OBJECTIVES,
             "self.aspiration.objectives")
    for item in value["objectives"]:
        _require(isinstance(item, dict) and set(item) == {"text_key", "done"} and type(item["done"]) is bool,
                 "self.aspiration.objectives entry")
        string_id(item["text_key"], "self.aspiration.objectives.text_key")


def _validate_self_bills(value):
    """2.36.0 (D6, P1): what her household owes now and whether the bills came and whether a utility is late."""
    _require(isinstance(value, dict) and set(value) == {"owed", "delivered", "late"}, "self.bills")
    _require(value["owed"] is None or (type(value["owed"]) is int and value["owed"] >= 0), "self.bills.owed")
    _require(type(value["delivered"]) is bool and type(value["late"]) is bool, "self.bills flags")


def _validate_self_inventory(value):
    """2.36.0 (D6, P1): the objects her Sim carries, by name, with the count each holds."""
    _require(isinstance(value, list) and len(value) <= MAX_SELF_INVENTORY, "self.inventory")
    for item in value:
        _require(isinstance(item, dict) and set(item) == {"name", "count"} and
                 type(item["count"]) is int and item["count"] >= 0, "self.inventory entry")
        bounded_string(item["name"], 128, "self.inventory.name", False)


def _validate_weather(row):
    """2.36.0 (D6, P1): the weather types now (names) and the season (a name); absent when neither service can say."""
    if "weather" not in row:
        return
    _observation_only(row, "weather", 18)
    value = row["weather"]
    if value is None:
        return
    _require(isinstance(value, dict) and set(value) == {"types", "season"}, "weather shape")
    if value["types"] is not None:
        _require(isinstance(value["types"], list) and len(value["types"]) <= MAX_WEATHER_TYPES,
                 "weather.types")
        for name in value["types"]:
            bounded_string(name, 128, "weather.type", False)
    bounded_string(value["season"], 128, "weather.season")


def _validate_notices(row):
    """2.36.0 (D6, P2): the game's notices about her found since the last row: title and text as string keys."""
    if "notices" not in row:
        return
    _observation_only(row, "notices", 18)
    value = row["notices"]
    if value is None:
        return
    _require(isinstance(value, list) and len(value) <= MAX_NOTICES, "notices")
    for item in value:
        _require(isinstance(item, dict) and set(item) == {"title_key", "text_key"}, "notices entry")
        string_id(item["title_key"], "notices.title_key")
        string_id(item["text_key"], "notices.text_key")


def _validate_situations(value):
    """2.15.2: the game situations a Sim is in (a visit, a party) and its role there;
    None when unreadable."""
    if value is None:
        return
    _require(isinstance(value, list) and len(value) <= MAX_SITUATIONS, "presence.situations")
    for item in value:
        # 2.40.0 (W13 P1): waiting (a visitor waiting at her door, from the visitor's situation job) is optional.
        _require(isinstance(item, dict) and set(item) - {"waiting"} == {"situation", "role"},
                 "situation entry")
        if "waiting" in item:
            _require(type(item["waiting"]) is bool, "situation.waiting")
        bounded_string(item["situation"], 128, "situation", False)
        if item["role"] is not None:
            bounded_string(item["role"], 128, "situation.role", False)


def _observation_only(row, key, version):
    _require(row["event_kind"] == "presence_snapshot" and row["schema_version"] >= version,
             "%s outside a schema %d observation" % (key, version))


def _validate_place(row):
    """2.15.2: whose lot she is on and what kind of place it is."""
    if "place" not in row:
        return
    _observation_only(row, "place", 9)
    value = row["place"]
    if value is None:
        return
    _require(isinstance(value, dict) and set(value) == {"owner_household_id", "her_home",
                                                        "venue"}, "place shape")
    if value["owner_household_id"] is not None:
        _require(isinstance(value["owner_household_id"], str), "place.owner_household_id")
        string_id(value["owner_household_id"], "place.owner_household_id")
    _require(value["her_home"] is None or type(value["her_home"]) is bool, "place.her_home")
    if value["venue"] is not None:
        bounded_string(value["venue"], 128, "place.venue", False)


def _validate_dialog_text(item, label):
    for key in ("title_key", "text_key"):
        if item[key] is not None:
            _require(isinstance(item[key], str), "%s.%s" % (label, key))
            string_id(item[key], "%s.%s" % (label, key))
    bounded_string(item["kind"], 128, "%s.kind" % label, False)
    _require(isinstance(item["dialog_id"], str), "%s.dialog_id" % label)
    string_id(item["dialog_id"], "%s.dialog_id" % label)


def _int_between(value, low, high, label):
    _require(type(value) is int and low <= value <= high, label)


def _is_int_between(value, low, high):
    return type(value) is int and low <= value <= high


def _validate_self_people(value):
    """2.39.0 (W12 E4, E5): her gender ("F", "M" or None) and name fields, when the row carries them."""
    if "gender" in value:
        _require(value["gender"] is None or value["gender"] in GENDER_CODES, "self.gender")
    for key in ("first_name", "last_name"):
        if value.get(key) is not None:
            bounded_string(value[key], MAX_NAME_PART_LENGTH, "self.%s" % key, False)


def _validate_window(item):
    """2.31.0 (schema 14): her window attribution and the answer shapes its dialog offers."""
    _require(type(item["held"]) is bool, "dialogs.held")
    if "hold_left_s" in item:
        _require(item["hold_left_s"] is None or (item["held"] is True and
                                                 _is_int_between(item["hold_left_s"], 0, MAX_HOLD_LEFT_SECONDS)),
                 "dialogs.hold_left_s")
    _require(item["cause"] is None or item["cause"] in WINDOW_CAUSES, "dialogs.cause")
    if item["select"] is not None:
        _require(isinstance(item["select"], dict) and set(item["select"]) == {"min", "max"},
                 "dialogs.select shape")
        for number in item["select"].values():
            _int_between(number, 0, MAX_DIALOG_ROWS, "dialogs.select")
    if item["counts"] is not None:
        _require(isinstance(item["counts"], dict) and set(item["counts"]) == {"max_in_row", "max_rows"},
                 "dialogs.counts shape")
        for number in item["counts"].values():
            _int_between(number, 0, MAX_WINDOW_COUNT, "dialogs.counts")
    fields = item["text_inputs"]
    if fields is None:
        return
    _require(item["held"] is True and isinstance(fields, list) and 1 <= len(fields) <= MAX_TEXT_INPUTS,
             "dialogs.text_inputs")
    for field in fields:
        _require(isinstance(field, dict) and set(field) == TEXT_FIELD_KEYS, "dialogs.text_input entry")
        bounded_string(field["name"], 32, "dialogs.text_input.name", False)
        _require(set(field["name"]) <= FIELD_NAME_CHARS, "dialogs.text_input.name characters")
        _int_between(field["min_length"], 0, MAX_TEXT_LIMIT, "dialogs.text_input.min_length")
        if field["max_length"] is not None:
            _int_between(field["max_length"], 0, MAX_TEXT_LIMIT, "dialogs.text_input.max_length")
        for key in ("min_value", "max_value"):
            if field[key] is not None:
                _int_between(field[key], -MAX_TEXT_VALUE, MAX_TEXT_VALUE, "dialogs.text_input.%s" % key)
        for key in ("numeric", "profanity_checked", "restricted"):
            _require(type(field[key]) is bool, "dialogs.text_input.%s" % key)
        if field["default_key"] is not None:
            _require(isinstance(field["default_key"], str), "dialogs.text_input.default_key")
            string_id(field["default_key"], "dialogs.text_input.default_key")


# 2.31.0 (W3p, schema 14): the pace block of an observation row. need_drain and slow_time are the wanted
# factors (1.0 is normal pace); drain_measured is the effective factor one motive shows (None when its
# decay is not running); clock_scale is the value the game multiplies by (None when unread).
PACE_KEYS = ("need_drain", "motives_modified", "drain_measured", "slow_time", "clock_scale", "clock_foreign",
             "clock_unreadable")
PACE_MEASURE_LIMIT = 100


def _pace_factor(value, label):
    _require(type(value) in (int, float) and 0.25 <= value <= 1.0, label)


def _validate_pace(row):
    """2.31.0 (schema 14): the probe's pace block, observation rows only."""
    if "pace" not in row:
        return
    _observation_only(row, "pace", 14)
    value = row["pace"]
    if value is None:
        return
    _require(isinstance(value, dict) and set(value) == set(PACE_KEYS), "pace shape")
    _pace_factor(value["need_drain"], "pace.need_drain")
    _pace_factor(value["slow_time"], "pace.slow_time")
    _int_between(value["motives_modified"], 0, MAX_MOTIVES, "pace.motives_modified")
    for key in ("drain_measured", "clock_scale"):
        if value[key] is not None:
            _require(type(value[key]) in (int, float) and 0 <= value[key] <= PACE_MEASURE_LIMIT,
                     "pace.%s" % key)
    _require(type(value["clock_foreign"]) is bool, "pace.clock_foreign")
    _require(type(value["clock_unreadable"]) is bool, "pace.clock_unreadable")


def _validate_dialogs(row):
    """2.15.2: the game's pop-ups. `open` lists those showing now (with the choices the
    game offers), `closed` those gone since the last sample, with the answer read from
    the dialog (`response`, None when it was dismissed without one)."""
    if "dialogs" not in row:
        return
    _observation_only(row, "dialogs", 9)
    value = row["dialogs"]
    if value is None:
        return
    _require(isinstance(value, dict) and set(value) == {"open", "closed", "truncated"},
             "dialogs shape")
    _require(type(value["truncated"]) is bool, "dialogs.truncated")
    _require(isinstance(value["open"], list) and len(value["open"]) <= MAX_DIALOGS,
             "dialogs.open")
    for item in value["open"]:
        keys = {"dialog_id", "kind", "owner_id", "title_key", "text_key", "responses", "auto_respond"}
        if row["schema_version"] >= 11:
            keys.add("rows")
        if row["schema_version"] >= 14:
            keys = keys | WINDOW_KEYS
        # 2.39.0 (W12 A9): hold_left_s is optional (a held window only).
        _require(isinstance(item, dict) and keys <= set(item) <= keys | DIALOG_HOLD_KEYS, "dialogs.open entry")
        if "rows" in keys:
            _require(isinstance(item["rows"], list) and len(item["rows"]) <= MAX_DIALOG_ROWS,
                     "dialogs.rows")
            for entry in item["rows"]:
                _require(isinstance(entry, dict) and set(entry) == set(DIALOG_ROW_KEYS),
                         "dialogs.row entry")
                _require(isinstance(entry["option_id"], str) and entry["option_id"].isdigit()
                         and len(entry["option_id"]) <= 20, "dialogs.row.option_id")
                if entry["name_key"] is not None:
                    string_id(entry["name_key"], "dialogs.row.name_key")
                _require(type(entry["enabled"]) is bool, "dialogs.row.enabled")
                _require(entry["price"] is None or (type(entry["price"]) is int and entry["price"] >= 0),
                         "dialogs.row.price")
        _validate_dialog_text(item, "dialogs.open")
        if "held" in keys:
            _validate_window(item)
        if item["owner_id"] is not None:
            _require(isinstance(item["owner_id"], str), "dialogs.owner_id")
            string_id(item["owner_id"], "dialogs.owner_id")
        _require(type(item["auto_respond"]) is bool, "dialogs.auto_respond")
        _require(isinstance(item["responses"], list) and
                 len(item["responses"]) <= MAX_DIALOG_RESPONSES, "dialogs.responses")
        for response in item["responses"]:
            _require(isinstance(response, dict) and set(response) == {"response", "text_key"},
                     "dialogs.response entry")
            bounded_string(response["response"], 16, "dialogs.response", False)
            if response["text_key"] is not None:
                string_id(response["text_key"], "dialogs.response.text_key")
    _require(isinstance(value["closed"], list) and len(value["closed"]) <= MAX_DIALOGS,
             "dialogs.closed")
    for item in value["closed"]:
        _require(isinstance(item, dict) and set(item) == {
            "dialog_id", "kind", "title_key", "text_key", "response"}, "dialogs.closed entry")
        _validate_dialog_text(item, "dialogs.closed")
        if item["response"] is not None:
            bounded_string(item["response"], 16, "dialogs.closed.response", False)


def _validate_relationship(value, version=7):
    """S5: None for her own body; else what the game holds between her and this Sim.
    Schema 8 adds what she knows about them and her sentiments toward them."""
    if value is None:
        return
    keys = {"known", "tracks", "labels"}
    if version >= 8:
        keys = keys | {"knows", "sentiments"}
    _require(isinstance(value, dict) and set(value) == keys,
             "presence.relationship shape")
    if version >= 8:
        _validate_knows(value["knows"])
        _validate_named(value["sentiments"], "sentiment", MAX_SENTIMENTS,
                        "relationship.sentiments")
        for item in value["sentiments"]:
            _require(set(item) == {"sentiment", "text_key"}, "sentiment entry")
    _require(type(value["known"]) is bool, "relationship.known")
    _require(isinstance(value["tracks"], list) and len(value["tracks"]) <= MAX_REL_TRACKS,
             "relationship.tracks")
    for track in value["tracks"]:
        _require(isinstance(track, dict) and set(track) == {"track", "value"}, "track shape")
        bounded_string(track["track"], 128, "relationship.track", False)
        _number_or_none(track["value"], "relationship.value")
    _require(isinstance(value["labels"], list) and len(value["labels"]) <= MAX_REL_LABELS,
             "relationship.labels")
    for label in value["labels"]:
        _require(isinstance(label, dict) and set(label) == {"label", "text_key"}, "label shape")
        bounded_string(label["label"], 128, "relationship.label", False)
        if label["text_key"] is not None:
            _require(isinstance(label["text_key"], str), "label.text_key must be a string")
            string_id(label["text_key"], "label.text_key")


def _validate_objects(row):
    """S5: object events since the previous sample (schema 7 presence_snapshot only)."""
    if "objects" not in row:
        return
    _require(row["event_kind"] == "presence_snapshot" and row["schema_version"] >= 7,
             "objects outside a schema 7 observation")
    value = row["objects"]
    if value is None:
        return
    keys = {"baseline", "created", "destroyed", "changed", "truncated"}
    if row["schema_version"] >= 15:
        keys = keys | {"near_conditions", "near_rooms", "moved", "owner_changed"}
    _require(isinstance(value, dict) and set(value) == keys, "objects shape")
    _require(type(value["baseline"]) is bool and type(value["truncated"]) is bool,
             "objects flags")
    if "near_conditions" in value:
        _validate_near_conditions(value["near_conditions"])
    if "moved" in value:
        # 2.32.0 (HE5, schema 15): an object moved (over 0.5 m, or into another room); rooms are the game's ids.
        _require(isinstance(value["moved"], list) and len(value["moved"]) <= MAX_OBJECT_EVENTS, "objects.moved")
        for item in value["moved"]:
            _require(isinstance(item, dict) and set(item) == {"object_id", "class", "from_room", "to_room"},
                     "objects.moved entry")
            string_id(item["object_id"], "objects.moved.object_id")
            for text in ("from_room", "to_room"):
                if item[text] is not None:
                    string_id(item[text], "objects.moved.%s" % text)
            bounded_string(item["class"], 128, "objects.moved.class")
    if "owner_changed" in value:
        # 2.32.0 (PR15, schema 15): an object of the nearest changed household (plain household ids).
        _require(isinstance(value["owner_changed"], list) and len(value["owner_changed"]) <= MAX_OBJECT_EVENTS,
                 "objects.owner_changed")
        for item in value["owner_changed"]:
            _require(isinstance(item, dict) and set(item) == {"object_id", "class", "from_owner", "to_owner"},
                     "objects.owner_changed entry")
            string_id(item["object_id"], "objects.owner_changed.object_id")
            string_id(item["from_owner"], "objects.owner_changed.from_owner")
            string_id(item["to_owner"], "objects.owner_changed.to_owner")
            bounded_string(item["class"], 128, "objects.owner_changed.class")
    if "near_rooms" in value:
        _require(isinstance(value["near_rooms"], list) and len(value["near_rooms"]) <= MAX_NEAR_CONDITIONS,
                 "objects.near_rooms")
        for item in value["near_rooms"]:
            _require(isinstance(item, dict) and set(item) == {"object_id", "class", "room"},
                     "objects.near_rooms entry")
            string_id(item["object_id"], "objects.near_rooms.object_id")
            string_id(item["room"], "objects.near_rooms.room")
            bounded_string(item["class"], 128, "objects.near_rooms.class")
    shapes = {"created": {"object_id", "class", "definition_id"},
              "destroyed": {"object_id", "class"},
              "changed": {"object_id", "class", "state", "from", "to"}}
    for key, fields in shapes.items():
        _require(isinstance(value[key], list) and len(value[key]) <= MAX_OBJECT_EVENTS,
                 "objects.%s" % key)
        for item in value[key]:
            _require(isinstance(item, dict) and set(item) == fields, "objects.%s entry" % key)
            _require(isinstance(item["object_id"], str), "objects object_id")
            string_id(item["object_id"], "objects.object_id")
            if item.get("definition_id") is not None:
                string_id(item["definition_id"], "objects.definition_id")
            for text in ("class", "state", "from", "to"):
                if item.get(text) is not None:
                    bounded_string(item[text], 128, "objects.%s" % text, False)


def _validate_near_conditions(value):
    """2.32.0 (HE7): each near object names its notable states (state and value, the game's own names)."""
    _require(isinstance(value, list) and len(value) <= MAX_NEAR_CONDITIONS, "objects.near_conditions")
    for item in value:
        _require(isinstance(item, dict) and set(item) == {"object_id", "class", "states"},
                 "objects.near_conditions entry")
        string_id(item["object_id"], "objects.near_conditions.object_id")
        bounded_string(item["class"], 128, "objects.near_conditions.class")
        _require(isinstance(item["states"], list) and 1 <= len(item["states"]) <= MAX_NEAR_STATES,
                 "objects.near_conditions.states")
        for state in item["states"]:
            _require(isinstance(state, dict) and set(state) == {"state", "value"},
                     "objects.near_conditions.state entry")
            bounded_string(state["state"], 128, "objects.near_conditions.state", False)
            bounded_string(state["value"], 128, "objects.near_conditions.value", False)


def _validate_presence(value, version=5):
    _require(isinstance(value, list) and len(value) <= MAX_PRESENCE, "presence")
    for item in value:
        _require(isinstance(item, dict), "presence entry must be an object")
        expected = (PRESENCE_V15 if version >= 15 else
                    PRESENCE_V9 if version >= 9 else
                    PRESENCE_V8 if version >= 8 else
                    PRESENCE_V7 if version >= 7 else
                    PRESENCE_V6 if version >= 6 else
                    {"id", "active_household", "level"})
        # 2.39.0 (W12 E5): the game's first and last names are there only when readable.
        _require(expected <= set(item) <= expected | PRESENCE_NAME_KEYS, "presence shape")
        for key in PRESENCE_NAME_KEYS & set(item):
            if item[key] is not None:
                bounded_string(item[key], MAX_NAME_PART_LENGTH, "presence.%s" % key, False)
        if version >= 8 and item.get("on_lot") is not None:
            _require(type(item["on_lot"]) is bool, "presence.on_lot must be bool")
        if version >= 15:
            _require(item["is_pet"] is None or type(item["is_pet"]) is bool, "presence.is_pet must be bool")
            if item["species"] is not None:
                bounded_string(item["species"], 128, "presence.species", False)
            if item["occult_kinds"] is not None:
                _require(isinstance(item["occult_kinds"], list) and len(item["occult_kinds"]) <= MAX_OCCULT_KINDS,
                         "presence.occult_kinds")
                for name in item["occult_kinds"]:
                    bounded_string(name, 128, "presence.occult_kinds", False)
        if version >= 9:
            _validate_situations(item["situations"])
        if version >= 7:
            _validate_relationship(item.get("relationship"), version)
        if version >= 6:
            _require(type(item.get("is_body")) is bool, "presence.is_body must be bool")
            for key in ("household_id", "room", "doing_target"):
                if item.get(key) is not None:
                    _require(isinstance(item[key], str), "presence.%s must be a string" % key)
                    string_id(item[key], "presence.%s" % key)
            if item.get("name") is not None:
                bounded_string(item["name"], 128, "presence.name", False)
            for key in ("posture", "doing"):
                if item.get(key) is not None:
                    bounded_string(item[key], MAX_DISPLAY_TEXT_LENGTH, "presence.%s" % key, False)
            _validate_position(item.get("position"), "presence.position")
            _number_or_none(item.get("distance_m"), "presence.distance_m")
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
    if version >= 5:
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
        if version >= 5:
            _require(isinstance(item.get("actor_id"), str), "social.actor_id must be a string")
            string_id(item["actor_id"], "social.actor_id")


def _validate_mood(value, version):
    if value is None:
        return
    fields = {"type", "intensity"}
    if version >= 5:
        fields = set(fields)
        fields.add("name")
    _require(isinstance(value, dict) and set(value) == fields, "mood shape")
    if value["type"] is not None:
        bounded_string(value["type"], MAX_ID_LENGTH, "mood.type", False)
    if value["intensity"] is not None:
        _require(isinstance(value["intensity"], (int, float)) and
                 not isinstance(value["intensity"], bool),
                 "mood.intensity must be numeric")
    if version >= 5 and value["name"] is not None:
        bounded_string(value["name"], 128, "mood.name", False)


def _validate_signals(value, version):
    _require(isinstance(value, list) and len(value) <= MAX_SIGNALS, "sim_signals")
    fields = {"kind", "tuning_id", "game_text", "magnitude", "consequences",
              "native_override"}
    if version >= 5:
        fields = set(fields)
        fields.add("tuning_name")
    if version >= 6:
        # DS3: the moodlet's own blueprint (name, string key, mood, visibility).
        fields |= {"text_key", "mood_type", "visible"}
    if version >= 7:
        # S5: the game's reason for it and the game minutes it has left (timed ones).
        fields |= {"reason_key", "minutes_left"}
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
        if version >= 5 and item.get("tuning_name") is not None:
            bounded_string(item["tuning_name"], 128, "signal.tuning_name", False)
        if item.get("consequences") is not None:
            bounded_string(item["consequences"], MAX_ID_LENGTH,
                           "signal.consequences", False)
            _require(item["consequences"] in SIGNAL_CONSEQUENCES,
                     "invalid signal consequences")
        if item.get("native_override") is not None:
            _require(item["native_override"] == "UNKNOWN",
                     "invalid signal native_override")
        if version >= 6:
            if item.get("text_key") is not None:
                _require(isinstance(item["text_key"], str), "signal.text_key must be a string")
                string_id(item["text_key"], "signal.text_key")
            if item.get("mood_type") is not None:
                bounded_string(item["mood_type"], 128, "signal.mood_type", False)
            if item.get("visible") is not None:
                _require(type(item["visible"]) is bool, "signal.visible must be bool")
        if version >= 7:
            if item.get("reason_key") is not None:
                _require(isinstance(item["reason_key"], str), "signal.reason_key must be a string")
                string_id(item["reason_key"], "signal.reason_key")
            _number_or_none(item.get("minutes_left"), "signal.minutes_left")


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
    # 2.32.0 (PR10, PR11, schema 15): build mode and a fire on the lot, each a bool or None.
    _require(isinstance(game, dict) and set(game) ==
             {"ticks", "calendar", "clock_speed", "paused"} | (
                 {"build_mode", "fire"} if row["schema_version"] >= 15 else set()), "game")
    for field in ("build_mode", "fire"):
        if game.get(field) is not None:
            _require(type(game[field]) is bool, "game.%s" % field)
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
    _validate_zone(row)
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
    _validate_presence(row.get("presence"), version)
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
    _validate_objects(row)
    _validate_self(row)
    _validate_place(row)
    _validate_dialogs(row)
    _validate_weather(row)
    _validate_notices(row)
    _validate_pace(row)
    _validate_string_tree(row)
    encoded = json.dumps(row, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode("utf-8")
    _require(len(encoded) <= MAX_SERIALIZED_RECORD_BYTES, "serialized record exceeds the record limit")
    kind = row["event_kind"]
    if kind in ("session_open", "presence_snapshot", "save_observation"):
        _require(row.get("telemetry_session_id") is not None, "%s session id" % kind)
    if kind == "session_open":
        _require(row["attestation"]["armed_name"] in ARM_NAMES,
                 "session_open attestation")
        _require(row["attestation"]["snapshot_guid"] is not None and
                 row["attestation"]["snapshot_slot"] is not None and
                 row["attestation"]["snapshot_sim"] is not None,
                 "session_open snapshot")
        _validate_id_fields(row.get("save"), ("save_slot_guid", "slot_id"), "save")
        _validate_zone(row)  # D39: was the v5 check, which refused every v6 session_open
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
        _require(row.get("checkpoint_reason") in ("PERIODIC_60S", "ROTATION", "PRE_DISARM",
                                                   "SAMPLER_RESTARTED", "ZONE_RESUMED",
                                                   "AUTOSTARTED", "WAITING_FOR_BODY",
                                                   "TELEMETRY_DIR_75", "BODY_GONE"),
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
        # 2.32.0 (PR18): a serialize drop names its row kind and the field that failed (optional).
        bounded_string(row.get("drop_detail"), MAX_REASON_LENGTH, "drop_detail")
    else:
        _require(row.get("drop_detail") is None, "drop_detail outside a dropped_summary")
    if kind in ("cap_reached", "writer_failed"):
        expected = "CAP_REACHED" if kind == "cap_reached" else "FAILED_STICKY"
        _require(row.get("writer", {}).get("state") == expected, "diagnostic writer state")
    _validate_payload_contracts(row)
    return row


def serialize_record(row):
    validate_record(row)
    return json.dumps(row, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode("utf-8")


# 2.40.0 (W13 P2, home): the things list, the catalogue record and an act's result. Plain values only; bounded.
THING_WHERE = ("room", "inventory", "outside")
THING_KEYS = ("object_id", "definition_id", "name_key", "where", "room_id", "value", "made_by_her", "states",
              "in_use", "count", "placement")
THING_MAX_STATES = 4
CATALOG_KEYS = ("definition_id", "price", "buy_category", "placement", "tags", "purchasable")
CATALOG_MAX_PART_ITEMS = 256
LIST_MAX_PARTS = 64
PLACEMENT_WORDS = ("floor", "wall", "surface")
ROUTE_WORDS = ("door", "bed", "toilet", "fridge")
RESULT_KEYS = ("room_id", "wall", "wall_has", "wall_kinds", "beside", "facing_id", "routes_lost", "price", "funds",
               "value")
# Every key an act result may carry: the home facts (P2) and the go/event facts (P1).
RESULT_KEY_NAMES = frozenset(RESULT_KEYS + ("zone_id", "cost", "start_min"))
RESULT_MAX_IDS = 4


def _is_digits(value):
    # 2.40.0 (W13 R2): ASCII digits only (str.isdigit also takes other scripts' digits).
    return type(value) is str and 1 <= len(value) <= 20 and all(ch in "0123456789" for ch in value)


def _is_int_or_none(value):
    return value is None or (type(value) is int and not isinstance(value, bool))


def _validate_part(payload, label):
    _require(type(payload["part"]) is int and type(payload["parts"]) is int, "%s part" % label)
    _require(0 <= payload["part"] < payload["parts"] <= LIST_MAX_PARTS, "%s part range" % label)


def _validate_thing(item):
    _require(set(item) == set(THING_KEYS), "thing keys")
    _require(_is_digits(item["object_id"]), "thing object_id")
    for key in ("definition_id", "name_key", "room_id"):
        _require(item[key] is None or _is_digits(item[key]), "thing %s" % key)
    _require(item["where"] in THING_WHERE, "thing where")
    _require((item["where"] == "room") == (item["room_id"] is not None), "thing room")
    _require(_is_int_or_none(item["value"]), "thing value")
    _require(item["made_by_her"] is None or type(item["made_by_her"]) is bool, "thing made_by_her")
    _require(type(item["states"]) is list and len(item["states"]) <= THING_MAX_STATES, "thing states")
    for state in item["states"]:
        _require(type(state) is dict and set(state) == {"state", "value"} and type(state["state"]) is str and
                 len(state["state"]) <= 64, "thing state")
        _require(state["value"] is None or type(state["value"]) in (int, float, str), "thing state value")
    _require(item["in_use"] is None or type(item["in_use"]) is bool, "thing in_use")
    _require(_is_int_or_none(item["count"]), "thing count")
    _require(item["placement"] is None or item["placement"] in PLACEMENT_WORDS, "thing placement")


def _validate_catalog_record(payload):
    """2.40.0: one part of the catalogue: at most CATALOG_MAX_PART_ITEMS items, each with the catalogue keys."""
    bounded_string(payload["catalog_rev"], 64, "catalog rev", False)
    _validate_part(payload, "catalog")
    items = payload["items"]
    _require(type(items) is list and len(items) <= CATALOG_MAX_PART_ITEMS, "catalog items")
    for item in items:
        _require(type(item) is dict and set(item) == set(CATALOG_KEYS), "catalog item keys")
        _require(_is_digits(item["definition_id"]), "catalog definition_id")
        _require(type(item["price"]) is int and item["price"] >= 0, "catalog price")
        _require(type(item["buy_category"]) is list or item["buy_category"] is None, "catalog buy_category")
        # S3: a placement is exactly one word (wall, surface or floor), or None when it was unread.
        _require(item["placement"] is None or (type(item["placement"]) is list and len(item["placement"]) == 1 and
                 all(flag in PLACEMENT_WORDS for flag in item["placement"])), "catalog placement")
        _require(type(item["tags"]) is list and len(item["tags"]) <= 8, "catalog tags")
        _require(type(item["purchasable"]) is bool, "catalog purchasable")


def _validate_home_facts(result):
    """2.40.0 (W13 P2): the home facts of a result, where present: ids as digits, the routes as their words, no text."""
    for key in ("room_id", "facing_id"):
        if result.get(key) is not None:
            _require(_is_digits(result[key]), "act result %s" % key)
    if result.get("wall") is not None:
        _require(type(result["wall"]) is bool, "act result wall")
    for key in ("wall_has", "beside"):
        ids = result.get(key)
        if ids is not None:
            _require(type(ids) is list and len(ids) <= RESULT_MAX_IDS and all(_is_digits(i) for i in ids),
                     "act result %s" % key)
    kinds = result.get("wall_kinds")
    if kinds is not None:
        # S2: one word per wall_has id, parallel to it: a door or a window.
        _require(type(kinds) is list and len(kinds) <= RESULT_MAX_IDS and
                 all(kind in ("door", "window") for kind in kinds) and
                 len(kinds) == len(result.get("wall_has") or ()), "act result wall_kinds")
    lost = result.get("routes_lost")
    if lost is not None:
        _require(type(lost) is list and all(word in ROUTE_WORDS for word in lost), "act result routes_lost")
    for key in ("price", "funds", "value"):
        _require(_is_int_or_none(result.get(key)), "act result %s" % key)
