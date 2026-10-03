"""Local SQLite atlas. stdlib only; the database lives outside the repo."""
import hashlib
import json
import sqlite3
import time
from pathlib import Path

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
PRAGMA user_version = 1;
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
    elif version != 1:
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
