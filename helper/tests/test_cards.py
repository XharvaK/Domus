"""Atlas cards table and the read-only MCP cards tool. No game process."""
import sqlite3

import pytest

from domus_helper import atlas, mcp_server
from domus_helper.paths import Paths
from domus_helper.vendor.e2_cards import posture_card

from test_fingerprints import make_tree, write_game


def _posture(object_id="chair"):
    return posture_card(object_id, "sit")


def _need():
    return {"card_class": "need", "affordance_guid64": None, "object_id": None,
            "signature": None, "motive": "hunger", "direction": 1, "min_net_delta": 5.0}


def test_migration_keeps_affordances_and_imports(tmp_path):
    db = tmp_path / "atlas.db"
    connection = sqlite3.connect(db)
    connection.executescript(
        """
        CREATE TABLE affordances (build TEXT, guid64 INTEGER, name TEXT, PRIMARY KEY (build, guid64));
        CREATE TABLE imports (file_sha256 TEXT PRIMARY KEY, build TEXT);
        INSERT INTO affordances VALUES ('1.1', 10, 'sit');
        INSERT INTO imports VALUES ('abc', '1.1');
        PRAGMA user_version = 1;
        """)
    connection.commit()
    connection.close()
    atlas.list_cards(db, "1.1")
    connection = sqlite3.connect(db)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
    assert connection.execute("SELECT name FROM affordances").fetchone()[0] == "sit"
    assert connection.execute("SELECT build FROM imports").fetchone()[0] == "1.1"
    connection.close()


def test_upsert_list_and_filter(tmp_path):
    db = tmp_path / "atlas.db"
    atlas.upsert_card(db, "1.1", "sit-chair", _posture(), "learned")
    atlas.upsert_card(db, "1.1", "hunger-up", _need(), "proposed")
    atlas.upsert_card(db, "9.9", "other", _posture("other"), "owner")
    listed = atlas.list_cards(db, "1.1")
    assert [item["card_id"] for item in listed] == ["hunger-up", "sit-chair"]
    posture = atlas.list_cards(db, "1.1", "posture")
    assert len(posture) == 1
    assert posture[0]["card"]["signature"] == "sit"
    assert posture[0]["origin"] == "learned"
    again = dict(_posture(), signature="sit_lean")
    atlas.upsert_card(db, "1.1", "sit-chair", again, "owner")
    updated = atlas.list_cards(db, "1.1", "posture")[0]
    assert updated["card"]["signature"] == "sit_lean"
    assert updated["origin"] == "owner"
    assert updated["created_ms"] == posture[0]["created_ms"]


def test_invalid_card_rejected(tmp_path):
    db = tmp_path / "atlas.db"
    with pytest.raises(ValueError):
        atlas.upsert_card(db, "1.1", "bad", {"card_class": "mood"}, "learned")
    assert atlas.list_cards(db, "1.1") == []


def test_mcp_cards_without_the_game(tmp_path, monkeypatch):
    game, sims = make_tree(tmp_path)
    write_game(game, sims, monkeypatch, exe_version="1.2.3.4")
    monkeypatch.setenv("DOMUS_SIMS_ROOT", str(sims))
    monkeypatch.setenv("DOMUS_GAME_ROOT", str(game))
    monkeypatch.setenv("DOMUS_DATA_DIR", str(tmp_path / "data"))
    paths = Paths.from_env()
    atlas.upsert_card(paths.atlas_db, "1.2.3.4", "sit-chair", _posture(), "learned")
    monkeypatch.setattr(mcp_server, "tools", lambda: mcp_server.DomusTools(paths=paths))
    found = mcp_server.cards("posture")
    assert len(found) == 1
    assert found[0]["card_id"] == "sit-chair"
    assert mcp_server.cards("social") == []
