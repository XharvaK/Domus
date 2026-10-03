import json

import pytest

from domus_helper import atlas, mcp_server as mcp
from conftest import replier


def _row(guid, name="sit", **extra):
    row = {
        "kind": "affordance", "guid64": guid, "name": name, "is_super": False,
        "is_social": False, "target_type": "OBJECT", "allow_autonomous": True,
        "allow_user_directed": True, "require_current_posture": False,
        "posture_preferences": "Posture", "static_commodities": [1, 2],
    }
    row.update(extra)
    return row


def _write(directory, build, rows, errors=(), total=None, count=None, name=None):
    errors = list(errors)
    lines = [{
        "kind": "atlas_header", "probe_version": "2.4.0", "sims_build": build,
        "total": len(rows) + len(errors) if total is None else total, "started_ms": 1,
    }]
    lines.extend(rows)
    lines.extend(errors)
    lines.append({
        "kind": "atlas_footer", "count": len(rows) if count is None else count,
        "errors": len(errors), "chunks": 1, "max_chunk_ms": 1, "p50_chunk_ms": 1,
    })
    path = directory / (name or f"tuning_{build}.jsonl")
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


def test_import_rows_and_imports_table(tmp_path):
    db = tmp_path / "atlas.db"
    path = _write(tmp_path, "1.100.0", [_row(10, "watch")])
    result = atlas.import_tuning(db, path)
    assert result == {"status": "imported", "build": "1.100.0", "count": 1, "errors": 0}
    rows = atlas.query(db, build="1.100.0")
    assert rows[0]["name"] == "watch"
    assert rows[0]["static_commodities"] == [1, 2]
    assert rows[0]["ladder"] == "KNOWN"
    import sqlite3
    recorded = sqlite3.connect(db).execute("SELECT build, count, errors FROM imports").fetchone()
    assert recorded == ("1.100.0", 1, 0)


def test_reimport_is_duplicate(tmp_path):
    db = tmp_path / "atlas.db"
    path = _write(tmp_path, "1.100.0", [_row(10)])
    atlas.import_tuning(db, path)
    assert atlas.import_tuning(db, path) == {"status": "duplicate"}


def test_count_mismatch_writes_nothing(tmp_path):
    db = tmp_path / "atlas.db"
    path = _write(tmp_path, "1.100.0", [_row(10)], count=2)
    with pytest.raises(atlas.AtlasImportError, match="count_mismatch"):
        atlas.import_tuning(db, path)
    assert atlas.query(db, build="1.100.0") == []


def test_partial_refused(tmp_path):
    db = tmp_path / "atlas.db"
    path = _write(tmp_path, "1.100.0", [_row(10)], name="tuning_1.100.0.jsonl.partial")
    with pytest.raises(atlas.AtlasImportError, match="partial"):
        atlas.import_tuning(db, path)
    assert not db.exists()


def test_new_build_keeps_other_ladder(tmp_path):
    db = tmp_path / "atlas.db"
    atlas.import_tuning(db, _write(tmp_path, "1.1", [_row(10)]))
    import sqlite3
    connection = sqlite3.connect(db)
    connection.execute("UPDATE affordances SET ladder='OFFERED' WHERE build='1.1'")
    connection.commit()
    atlas.import_tuning(db, _write(tmp_path, "1.2", [_row(10, "other")], name="b.jsonl"))
    old = atlas.query(db, build="1.1")[0]
    new = atlas.query(db, build="1.2")[0]
    assert old["ladder"] == "OFFERED"
    assert new["ladder"] == "KNOWN"


def test_upsert_keeps_ladder(tmp_path):
    db = tmp_path / "atlas.db"
    atlas.import_tuning(db, _write(tmp_path, "1.1", [_row(10, "old")]))
    import sqlite3
    connection = sqlite3.connect(db)
    connection.execute("UPDATE affordances SET ladder='EXERCISED'")
    connection.commit()
    changed = _write(tmp_path, "1.1", [_row(10, "new")], name="again.jsonl")
    atlas.import_tuning(db, changed)
    row = atlas.query(db, build="1.1")[0]
    assert row["name"] == "new"
    assert row["ladder"] == "EXERCISED"


def test_query_filters_and_limit_clamp(tmp_path):
    db = tmp_path / "atlas.db"
    rows = [_row(i, "super" if i < 3 else "plain", is_super=i < 3) for i in range(5)]
    atlas.import_tuning(db, _write(tmp_path, "1.1", rows))
    found = atlas.query(db, build="1.1", name_contains="super", is_super=True, limit=1)
    assert [row["guid64"] for row in found] == [0]
    many = [_row(i, f"n{i}") for i in range(201)]
    atlas.import_tuning(db, _write(tmp_path, "9.9", many, name="wide.jsonl"))
    assert len(atlas.query(db, build="9.9", limit=10_000)) == 200


def test_name_contains_is_bound(tmp_path):
    db = tmp_path / "atlas.db"
    atlas.import_tuning(db, _write(tmp_path, "1.1", [_row(1, "sit"), _row(2, "watch")]))
    assert atlas.query(db, build="1.1", name_contains="x' OR 1=1 --") == []


def test_tuned_scan_is_readonly_command(paths, monkeypatch):
    assert "tuned_scan" not in mcp.ACTUATING
    monkeypatch.setattr(mcp, "game_running", lambda: True)
    seen = []

    def handler(row):
        seen.append(row)
        return dict(status="OK", code=None, result={"tuned": {"state": "idle"}})

    with replier(paths, handler):
        mcp.tuned_scan()
    commands = [(row["command"], row["args"]) for row in seen]
    assert ("tuned_scan", {}) in commands


def test_atlas_dump_is_readonly_command(paths, monkeypatch):
    assert "atlas_dump" not in mcp.ACTUATING
    monkeypatch.setattr(mcp, "game_running", lambda: True)
    seen = []

    def handler(row):
        seen.append(row)
        return dict(status="OK", code=None, result={"atlas": {"state": "idle"}})

    with replier(paths, handler):
        mcp.atlas_dump()
    commands = [(row["command"], row["args"]) for row in seen]
    assert ("atlas_dump", {}) in commands
