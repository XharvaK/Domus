"""Durable telemetry spool and observation outbox."""
import json
import sqlite3
import time

from .contract import validate_observation

ROW_CAP = 200_000
DROP_KINDS = frozenset({"dropped_summary"})


class OutboxConflict(ValueError):
    pass


def _canonical(payload):
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class Spool:
    def __init__(self, path, *, row_cap=ROW_CAP):
        self.row_cap = row_cap
        self._con = sqlite3.connect(str(path))
        self._con.row_factory = sqlite3.Row
        version = self._con.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2):
            raise RuntimeError("unsupported spool user_version %s" % version)
        if version == 0:
            self._con.executescript("""
                CREATE TABLE rows (
                    session TEXT NOT NULL,
                    segment INTEGER NOT NULL,
                    offset INTEGER NOT NULL,
                    written_sequence INTEGER,
                    event_kind TEXT,
                    wall_ms INTEGER,
                    json TEXT NOT NULL,
                    PRIMARY KEY (session, segment, offset)
                );
                CREATE TABLE gaps (
                    id INTEGER PRIMARY KEY,
                    session TEXT,
                    kind TEXT NOT NULL CHECK (kind IN ('gap', 'cap', 'drop')),
                    detail_json TEXT,
                    at_ms INTEGER
                );
                CREATE TABLE cursors (
                    session TEXT NOT NULL,
                    segment INTEGER NOT NULL,
                    offset INTEGER NOT NULL,
                    PRIMARY KEY (session, segment)
                );
                CREATE TABLE outbox (
                    observation_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('pending', 'acked', 'conflict', 'expired', 'rejected')),
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_ms INTEGER NOT NULL,
                    last_status TEXT,
                    expires_at_ms INTEGER NOT NULL,
                    created_ms INTEGER NOT NULL
                );
            """)
            self._con.execute("PRAGMA user_version = 1")
            self._con.commit()
            version = 1
        if version < 2:
            self._con.execute(
                "CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
            self._con.execute("PRAGMA user_version = 2")
            self._con.commit()

    def close(self):
        self._con.close()

    def cursor_offset(self, session, segment):
        row = self._con.execute(
            "SELECT offset FROM cursors WHERE session=? AND segment=?",
            (session, segment)).fetchone()
        return int(row["offset"]) if row else 0

    def _put_cursor(self, session, segment, offset):
        self._con.execute(
            """INSERT INTO cursors (session, segment, offset) VALUES (?, ?, ?)
               ON CONFLICT(session, segment) DO UPDATE SET offset=excluded.offset""",
            (session, segment, offset))

    def note_cursor(self, session, segment, offset):
        self._put_cursor(session, segment, offset)
        self._con.commit()

    def ingest(self, session, segment, offset, record, *, raw_len, at_ms=None):
        at_ms = int(time.time() * 1000) if at_ms is None else at_ms
        seq = record.get("written_sequence") if isinstance(record, dict) else None
        if type(seq) is not int:
            seq = None
        kind = record.get("event_kind") if isinstance(record, dict) else None
        wall = record.get("wall_timestamp_ms") if isinstance(record, dict) else None
        if type(wall) is not int:
            wall = None
        previous = self._con.execute(
            "SELECT written_sequence FROM rows WHERE session=? AND written_sequence IS NOT NULL "
            "ORDER BY rowid DESC LIMIT 1",
            (session,)).fetchone()
        with self._con:
            if previous is not None and seq is not None and seq != previous["written_sequence"] + 1:
                self._gap(session, "gap", {"from": previous["written_sequence"], "to": seq}, at_ms)
            if kind in DROP_KINDS:
                detail = {"event_kind": kind}
                if isinstance(record, dict) and record.get("reason") is not None:
                    detail["reason"] = record.get("reason")
                self._gap(session, "drop", detail, at_ms)
            self._enforce_cap(session, at_ms)
            self._con.execute(
                """INSERT OR IGNORE INTO rows
                   (session, segment, offset, written_sequence, event_kind, wall_ms, json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session, segment, offset, seq, kind, wall, json.dumps(record, ensure_ascii=False)))
            self._put_cursor(session, segment, offset + raw_len)

    def _gap(self, session, kind, detail, at_ms):
        self._con.execute(
            "INSERT INTO gaps (session, kind, detail_json, at_ms) VALUES (?, ?, ?, ?)",
            (session, kind, json.dumps(detail, sort_keys=True), at_ms))

    def _enforce_cap(self, session, at_ms):
        count = self._con.execute("SELECT COUNT(*) AS n FROM rows").fetchone()["n"]
        extra = count - self.row_cap + 1
        if extra <= 0 or self.row_cap < 1:
            return
        self._con.execute(
            "DELETE FROM rows WHERE rowid IN (SELECT rowid FROM rows ORDER BY rowid ASC LIMIT ?)",
            (extra,))
        self._gap(session, "cap", {"count": extra}, at_ms)

    def gaps(self):
        return [dict(row) for row in self._con.execute("SELECT * FROM gaps ORDER BY id")]

    def row_count(self):
        return self._con.execute("SELECT COUNT(*) AS n FROM rows").fetchone()["n"]

    def latest_record(self):
        row = self._con.execute("SELECT json FROM rows ORDER BY rowid DESC LIMIT 1").fetchone()
        return json.loads(row["json"]) if row else None

    def rows_after(self, rowid, limit=500):
        rows = self._con.execute(
            "SELECT rowid AS rid, json FROM rows WHERE rowid > ? ORDER BY rowid LIMIT ?",
            (int(rowid), int(limit))).fetchall()
        for row in rows:
            yield int(row["rid"]), json.loads(row["json"])

    def get_kv(self, key):
        row = self._con.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
        return None if row is None else row["v"]

    def put_kv(self, key, value):
        self.put_many_kv({key: value})

    def put_many_kv(self, items):
        with self._con:
            for key, value in items.items():
                # HE17: a value that is already stored is not rewritten.
                stored = self._con.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
                if stored is not None and stored["v"] == value:
                    continue
                self._con.execute(
                    """INSERT INTO kv (k, v) VALUES (?, ?)
                       ON CONFLICT(k) DO UPDATE SET v=excluded.v""",
                    (key, value))

    def enqueue_observation(self, obs, now_ms):
        normalized = validate_observation(obs, now_ms)
        payload = _canonical(normalized)
        existing = self._con.execute(
            "SELECT payload_json FROM outbox WHERE observation_id=?",
            (normalized["observation_id"],)).fetchone()
        if existing is not None:
            if existing["payload_json"] != payload:
                raise OutboxConflict(normalized["observation_id"])
            return
        with self._con:
            self._con.execute(
                """INSERT INTO outbox
                   (observation_id, payload_json, state, attempts, next_attempt_ms,
                    last_status, expires_at_ms, created_ms)
                   VALUES (?, ?, 'pending', 0, ?, NULL, ?, ?)""",
                (normalized["observation_id"], payload, now_ms, normalized["expires_at_ms"], now_ms))

    def set_expires(self, observation_id, expires_at_ms):
        with self._con:
            self._con.execute(
                "UPDATE outbox SET expires_at_ms=? WHERE observation_id=?",
                (expires_at_ms, observation_id))

    def outbox_counts(self):
        counts = {state: 0 for state in ("pending", "acked", "conflict", "expired", "rejected")}
        for row in self._con.execute("SELECT state, COUNT(*) AS n FROM outbox GROUP BY state"):
            counts[row["state"]] = row["n"]
        return counts

    def outbox_row(self, observation_id):
        row = self._con.execute("SELECT * FROM outbox WHERE observation_id=?", (observation_id,)).fetchone()
        return dict(row) if row else None

    def flush(self, client, now_ms, batch=20):
        due = self._con.execute(
            """SELECT * FROM outbox WHERE state='pending' AND next_attempt_ms<=?
               ORDER BY created_ms, observation_id LIMIT ?""",
            (now_ms, batch)).fetchall()
        for row in due:
            if now_ms > row["expires_at_ms"]:
                self._finish(row["observation_id"], "expired", row["attempts"], row["next_attempt_ms"], "expired")
                continue
            result = client.post_observation(json.loads(row["payload_json"]), now_ms=now_ms)
            kind = result.kind
            if kind in ("admitted", "duplicate"):
                self._finish(row["observation_id"], "acked", row["attempts"] + 1, row["next_attempt_ms"], kind)
            elif kind == "conflict":
                self._finish(row["observation_id"], "conflict", row["attempts"] + 1, row["next_attempt_ms"], kind)
            elif kind == "expired":
                self._finish(row["observation_id"], "expired", row["attempts"] + 1, row["next_attempt_ms"], kind)
            elif kind in ("rejected", "too_large"):
                self._finish(row["observation_id"], "rejected", row["attempts"] + 1, row["next_attempt_ms"], kind)
            elif kind == "unauthorized":
                return "auth_failed"
            else:
                attempts = row["attempts"]
                delay = 300_000 if attempts >= 9 else 1000 * (2 ** attempts)
                self._finish(row["observation_id"], "pending", attempts + 1, now_ms + delay, kind)
        return None

    def _finish(self, observation_id, state, attempts, next_attempt_ms, last_status):
        with self._con:
            self._con.execute(
                """UPDATE outbox SET state=?, attempts=?, next_attempt_ms=?, last_status=?
                   WHERE observation_id=?""",
                (state, attempts, next_attempt_ms, last_status, observation_id))
