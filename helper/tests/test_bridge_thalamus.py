"""DT2C: spool v2, thalamus bridge, decision log, prune, shadow scorer."""
import json
import sqlite3

from domus_helper.spool import Spool


def _v1(path):
    con = sqlite3.connect(str(path))
    con.executescript("""
        CREATE TABLE rows (
            session TEXT NOT NULL, segment INTEGER NOT NULL, offset INTEGER NOT NULL,
            written_sequence INTEGER, event_kind TEXT, wall_ms INTEGER, json TEXT NOT NULL,
            PRIMARY KEY (session, segment, offset)
        );
        CREATE TABLE gaps (
            id INTEGER PRIMARY KEY, session TEXT,
            kind TEXT NOT NULL CHECK (kind IN ('gap', 'cap', 'drop')),
            detail_json TEXT, at_ms INTEGER
        );
        CREATE TABLE cursors (
            session TEXT NOT NULL, segment INTEGER NOT NULL, offset INTEGER NOT NULL,
            PRIMARY KEY (session, segment)
        );
        CREATE TABLE outbox (
            observation_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL,
            state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_ms INTEGER NOT NULL, last_status TEXT,
            expires_at_ms INTEGER NOT NULL, created_ms INTEGER NOT NULL
        );
    """)
    con.execute("PRAGMA user_version = 1")
    con.execute(
        "INSERT INTO rows (session, segment, offset, written_sequence, event_kind, wall_ms, json) "
        "VALUES ('s', 0, 0, 1, 'speed_event', 1, ?)",
        (json.dumps({"written_sequence": 1, "event_kind": "speed_event"}),))
    con.execute(
        "INSERT INTO outbox (observation_id, payload_json, state, attempts, next_attempt_ms, "
        "expires_at_ms, created_ms) VALUES ('obs-1', '{}', 'pending', 0, 0, 1, 1)")
    con.commit()
    con.close()


def test_spool_v1_upgrades_and_rows_after_respects_order_and_limit(tmp_path):
    path = tmp_path / "spool.db"
    _v1(path)
    spool = Spool(path)
    version = spool._con.execute("PRAGMA user_version").fetchone()[0]
    assert version == 2
    assert spool.row_count() == 1
    assert spool.outbox_counts()["pending"] == 1
    assert spool.get_kv("missing") is None
    spool.put_kv("last_rowid", "1")
    assert spool.get_kv("last_rowid") == "1"
    again = Spool(path)
    assert again.get_kv("last_rowid") == "1"
    spool.ingest("s", 0, 10, {"written_sequence": 2, "n": "b"}, raw_len=1, at_ms=2)
    spool.ingest("s", 0, 20, {"written_sequence": 3, "n": "c"}, raw_len=1, at_ms=3)
    paired = list(spool.rows_after(0, limit=2))
    assert [record["written_sequence"] for _rowid, record in paired] == [1, 2]
    assert paired[0][0] < paired[1][0]
    rest = list(spool.rows_after(paired[1][0]))
    assert [record["written_sequence"] for _rowid, record in rest] == [3]
    assert list(spool.rows_after(rest[-1][0])) == []
