"""Local SQLite atlas. stdlib only; the database lives outside the repo."""
import hashlib
import json
import sqlite3
import time
from pathlib import Path

from .vendor.e2_cards import validate_card

_DDL = """
CREATE TABLE IF NOT EXISTS affordances (
    build TEXT NOT NULL,
    guid64 INTEGER NOT NULL,
    name TEXT,
    is_super INTEGER,
    is_social INTEGER,
    target_type TEXT,
    allow_autonomous INTEGER,
    allow_user_directed INTEGER,
    require_current_posture INTEGER,
    posture_preferences TEXT,
    static_commodities_json TEXT,
    ladder TEXT NOT NULL DEFAULT 'KNOWN'
        CHECK (ladder IN ('KNOWN','OFFERED','OBSERVED','EXERCISED','QUALIFIED')),
    PRIMARY KEY (build, guid64)
);
CREATE TABLE IF NOT EXISTS imports (
    file_sha256 TEXT PRIMARY KEY,
    build TEXT,
    count INTEGER,
    errors INTEGER,
    imported_at_ms INTEGER,
    probe_version TEXT
);
CREATE TABLE IF NOT EXISTS cards (
    build TEXT NOT NULL,
    card_id TEXT NOT NULL,
    card_class TEXT NOT NULL,
    affordance_guid64 INTEGER,
    object_id TEXT,
    body_json TEXT NOT NULL,
    origin TEXT NOT NULL CHECK (origin IN ('learned','owner','proposed')),
    created_ms INTEGER NOT NULL,
    PRIMARY KEY (build, card_id)
);
CREATE TABLE IF NOT EXISTS trials (
    build TEXT,
    experiment_id TEXT PRIMARY KEY,
    guid64 INTEGER,
    object_id TEXT,
    outcome TEXT CHECK (outcome IN ('PASS','OUTCOME_UNKNOWN','TRIAL_REJECT','PUSH_FAILED','TIMEOUT')),
    code TEXT,
    ambiguous_json TEXT,
    tuning_name TEXT,
    session TEXT,
    created_ms INTEGER
);
PRAGMA user_version = 3;
"""

_CARDS_DDL = """
CREATE TABLE IF NOT EXISTS cards (
    build TEXT NOT NULL,
    card_id TEXT NOT NULL,
    card_class TEXT NOT NULL,
    affordance_guid64 INTEGER,
    object_id TEXT,
    body_json TEXT NOT NULL,
    origin TEXT NOT NULL CHECK (origin IN ('learned','owner','proposed')),
    created_ms INTEGER NOT NULL,
    PRIMARY KEY (build, card_id)
);
"""

_TRIALS_DDL = """
CREATE TABLE IF NOT EXISTS trials (
    build TEXT,
    experiment_id TEXT PRIMARY KEY,
    guid64 INTEGER,
    object_id TEXT,
    outcome TEXT CHECK (outcome IN ('PASS','OUTCOME_UNKNOWN','TRIAL_REJECT','PUSH_FAILED','TIMEOUT')),
    code TEXT,
    ambiguous_json TEXT,
    tuning_name TEXT,
    session TEXT,
    created_ms INTEGER
);
"""

_FLAGS = ("is_super", "is_social", "allow_autonomous", "allow_user_directed",
          "require_current_posture")


class AtlasImportError(ValueError):
    pass


def _connect(db_path):
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version == 0:
        connection.executescript(_DDL)
    elif version == 1:
        connection.executescript(_CARDS_DDL)
        connection.executescript(_TRIALS_DDL)
        connection.execute("PRAGMA user_version = 3")
        connection.commit()
    elif version == 2:
        connection.executescript(_TRIALS_DDL)
        connection.execute("PRAGMA user_version = 3")
        connection.commit()
    elif version != 3:
        connection.close()
        raise AtlasImportError("unsupported user_version")
    return connection


def _flag(value):
    if value is None:
        return None
    return 1 if value else 0


def import_tuning(db_path, file_path):
    path = Path(file_path)
    if path.name.endswith(".partial"):
        raise AtlasImportError("partial")
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    connection = _connect(db_path)
    try:
        if connection.execute(
                "SELECT 1 FROM imports WHERE file_sha256 = ?", (digest,)).fetchone():
            return {"status": "duplicate"}
        lines = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
        if (not lines or lines[0].get("kind") != "atlas_header"
                or lines[-1].get("kind") != "atlas_footer"):
            raise AtlasImportError("shape")
        header, footer = lines[0], lines[-1]
        body = lines[1:-1]
        affordances = [row for row in body if row.get("kind") == "affordance"]
        errors = [row for row in body if row.get("kind") == "affordance_error"]
        if (len(body) != len(affordances) + len(errors)
                or footer.get("count") != len(affordances)
                or header.get("total") != len(affordances) + len(errors)):
            raise AtlasImportError("count_mismatch")
        build = header["sims_build"]
        with connection:
            for row in affordances:
                connection.execute(
                    """
                    INSERT INTO affordances (
                        build, guid64, name, is_super, is_social, target_type,
                        allow_autonomous, allow_user_directed, require_current_posture,
                        posture_preferences, static_commodities_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(build, guid64) DO UPDATE SET
                        name = excluded.name,
                        is_super = excluded.is_super,
                        is_social = excluded.is_social,
                        target_type = excluded.target_type,
                        allow_autonomous = excluded.allow_autonomous,
                        allow_user_directed = excluded.allow_user_directed,
                        require_current_posture = excluded.require_current_posture,
                        posture_preferences = excluded.posture_preferences,
                        static_commodities_json = excluded.static_commodities_json
                    """,
                    (build, row.get("guid64"), row.get("name"),
                     _flag(row.get("is_super")), _flag(row.get("is_social")),
                     row.get("target_type"), _flag(row.get("allow_autonomous")),
                     _flag(row.get("allow_user_directed")),
                     _flag(row.get("require_current_posture")),
                     row.get("posture_preferences"),
                     json.dumps(row.get("static_commodities"))))
            connection.execute(
                """
                INSERT INTO imports (
                    file_sha256, build, count, errors, imported_at_ms, probe_version)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (digest, build, footer.get("count"), footer.get("errors"),
                 int(time.time() * 1000), header.get("probe_version")))
        return {"status": "imported", "build": build,
                "count": footer.get("count"), "errors": footer.get("errors")}
    finally:
        connection.close()


def latest_build(db_path):
    connection = _connect(db_path)
    try:
        row = connection.execute(
            "SELECT build FROM imports ORDER BY imported_at_ms DESC LIMIT 1").fetchone()
    finally:
        connection.close()
    if row is None:
        raise AtlasImportError("no import")
    return row["build"]


def query(db_path, *, build, name_contains=None, is_super=None, is_social=None,
          allow_autonomous=None, allow_user_directed=None, ladder=None, limit=50):
    if type(limit) is not int:
        raise AtlasImportError("limit")
    limit = min(200, max(1, limit))
    clauses = ["build = ?"]
    params = [build]
    if name_contains is not None:
        clauses.append("instr(name, ?) > 0")
        params.append(name_contains)
    for column, value in (("is_super", is_super), ("is_social", is_social),
                          ("allow_autonomous", allow_autonomous),
                          ("allow_user_directed", allow_user_directed)):
        if value is not None:
            clauses.append(column + " = ?")
            params.append(1 if value else 0)
    if ladder is not None:
        clauses.append("ladder = ?")
        params.append(ladder)
    params.append(limit)
    connection = _connect(db_path)
    try:
        rows = connection.execute(
            "SELECT * FROM affordances WHERE " + " AND ".join(clauses)
            + " ORDER BY guid64 LIMIT ?", params).fetchall()
    finally:
        connection.close()
    decoded = []
    for row in rows:
        item = {key: row[key] for key in row.keys() if key != "static_commodities_json"}
        raw = row["static_commodities_json"]
        item["static_commodities"] = json.loads(raw) if raw is not None else None
        for column in _FLAGS:
            if item[column] is not None:
                item[column] = bool(item[column])
        decoded.append(item)
    return decoded


_ORIGINS = ("learned", "owner", "proposed")


def upsert_card(db_path, build, card_id, card, origin):
    if origin not in _ORIGINS:
        raise AtlasImportError("origin")
    if not isinstance(build, str) or not isinstance(card_id, str) or not card_id:
        raise AtlasImportError("card key")
    validate_card(card)
    body = json.dumps(card, sort_keys=True, separators=(",", ":"))
    connection = _connect(db_path)
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO cards (
                    build, card_id, card_class, affordance_guid64, object_id,
                    body_json, origin, created_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(build, card_id) DO UPDATE SET
                    card_class = excluded.card_class,
                    affordance_guid64 = excluded.affordance_guid64,
                    object_id = excluded.object_id,
                    body_json = excluded.body_json,
                    origin = excluded.origin
                """,
                (build, card_id, card["card_class"], card.get("affordance_guid64"),
                 card.get("object_id"), body, origin, int(time.time() * 1000)))
    finally:
        connection.close()
    return {"build": build, "card_id": card_id, "origin": origin}


def list_cards(db_path, build, card_class=None):
    if card_class is not None and card_class not in ("posture", "need", "interaction", "social"):
        raise AtlasImportError("card_class")
    clauses = ["build = ?"]
    params = [build]
    if card_class is not None:
        clauses.append("card_class = ?")
        params.append(card_class)
    connection = _connect(db_path)
    try:
        rows = connection.execute(
            "SELECT * FROM cards WHERE " + " AND ".join(clauses) + " ORDER BY card_id",
            params).fetchall()
    finally:
        connection.close()
    found = []
    for row in rows:
        found.append({
            "build": row["build"],
            "card_id": row["card_id"],
            "origin": row["origin"],
            "created_ms": row["created_ms"],
            "card": json.loads(row["body_json"]),
        })
    return found


def _open(db_path, *, readonly):
    if not readonly:
        return _connect(db_path)
    path = Path(db_path).resolve()
    uri = "file:///" + path.as_posix() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def record_trial(db_path, build, experiment_id, guid64, object_id, outcome, code,
                 ambiguous_json, tuning_name, session, created_ms=None):
    if outcome not in ("PASS", "OUTCOME_UNKNOWN", "TRIAL_REJECT", "PUSH_FAILED", "TIMEOUT"):
        raise AtlasImportError("outcome")
    if not isinstance(experiment_id, str) or not experiment_id:
        raise AtlasImportError("experiment_id")
    connection = _connect(db_path)
    try:
        with connection:
            connection.execute(
                """
                INSERT INTO trials (
                    build, experiment_id, guid64, object_id, outcome, code,
                    ambiguous_json, tuning_name, session, created_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (build, experiment_id, guid64, object_id, outcome, code,
                 ambiguous_json, tuning_name, session,
                 int(time.time() * 1000) if created_ms is None else created_ms))
    finally:
        connection.close()


def trials_for(db_path, build, guid64=None, *, readonly=False):
    connection = _open(db_path, readonly=readonly)
    try:
        if not _has(connection, "trials"):
            return []
        clauses = ["build = ?"]
        params = [build]
        if guid64 is not None:
            clauses.append("guid64 = ?")
            params.append(int(guid64))
        rows = connection.execute(
            "SELECT * FROM trials WHERE " + " AND ".join(clauses)
            + " ORDER BY created_ms, experiment_id", params).fetchall()
    finally:
        connection.close()
    return [{key: row[key] for key in row.keys()} for row in rows]


def _has(connection, table):
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,)).fetchone()
    return row is not None


def qualification(db_path, build, *, readonly=False):
    connection = _open(db_path, readonly=readonly)
    try:
        guids = []
        if _has(connection, "affordances"):
            guids.extend(row["guid64"] for row in connection.execute(
                "SELECT guid64 FROM affordances WHERE build = ?", (build,)))
        trials = []
        if _has(connection, "trials"):
            trials = connection.execute(
                "SELECT guid64, outcome, code FROM trials WHERE build = ?",
                (build,)).fetchall()
    finally:
        connection.close()
    buckets = {}
    for guid in guids:
        buckets.setdefault(int(guid), [])
    for row in trials:
        buckets.setdefault(int(row["guid64"]), []).append(row)
    found = []
    for guid, rows in buckets.items():
        pass_n = sum(row["outcome"] == "PASS" for row in rows)
        unknown_n = sum(row["outcome"] == "OUTCOME_UNKNOWN" for row in rows)
        reject_n = sum(row["outcome"] == "TRIAL_REJECT" for row in rows)
        push_failed_n = sum(row["outcome"] == "PUSH_FAILED" for row in rows)
        excluded = any(row["code"] == "TRIAL_EXCLUDED" for row in rows)
        if unknown_n >= 3 or push_failed_n >= 2 or excluded:
            state = "FAILED"
        elif pass_n >= 3 and unknown_n == 0:
            state = "QUALIFIED"
        elif not rows:
            state = "UNTESTED"
        else:
            state = "IN_PROGRESS"
        found.append({
            "guid64": guid, "pass_n": pass_n, "unknown_n": unknown_n,
            "reject_n": reject_n, "push_failed_n": push_failed_n, "state": state,
        })
    found.sort(key=lambda item: item["guid64"])
    return found
