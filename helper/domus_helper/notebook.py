"""The helper's notebook of her world. It is never deleted and it grows with play.

Facts are what she sees for herself, each with valid-from and valid-until. A changed
fact is closed (valid-until set) and a new one opened; nothing is deleted. v1 kinds:
object_room (which room an object is in, from her act menu) and lives_here (who lives
in the home she is in, from presence rows). Procedures are interactions that held up,
learned from S6 outcome records: for an interaction seen at least twice, each need
that moved the same way every time. One observation is never a procedure. Procedures
are about her body and the game's interactions, so they are not per world. Facts are
per world (the save slot).

W2h: withheld records are the interactions whose act ended on a screen only the User's hands can
use: the tuning name, the screen name, first and last seen, and how often. They are about the
interaction, not the world, and nothing is deleted. Her options keep them listed, marked.

Run: python -m domus_helper.notebook show [--world W] | rebuild
"""
import argparse
import json
import sqlite3
import statistics
import time

from .consequences import load_records
from .paths import Paths
from .scene import family

DB_NAME = "notebook.db"
SLICE_LIMIT = 1024
SLICE_PROCEDURES = 6
SLICE_MOVED = 3
MOVED_RECENT_MS = 24 * 3_600_000
MIN_N = 2
MIN_CHANGE = 5

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('object_room', 'lives_here', 'object_condition')),
  subject TEXT NOT NULL,
  value TEXT NOT NULL,
  label TEXT,
  valid_from_ms INTEGER NOT NULL,
  valid_until_ms INTEGER,
  seen_ms INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS facts_open ON facts (world, kind, subject) WHERE valid_until_ms IS NULL;
CREATE TABLE IF NOT EXISTS withheld (
  tuning TEXT NOT NULL,
  screen TEXT NOT NULL,
  n INTEGER NOT NULL,
  first_ms INTEGER NOT NULL,
  last_ms INTEGER NOT NULL,
  PRIMARY KEY (tuning, screen)
);
CREATE TABLE IF NOT EXISTS procedures (
  interaction TEXT PRIMARY KEY,
  n INTEGER NOT NULL,
  needs TEXT NOT NULL,
  conditions TEXT NOT NULL,
  act_ids TEXT NOT NULL,
  updated_ms INTEGER NOT NULL,
  first_ms INTEGER
);
"""
# HE13: a notebook made before first_ms existed gets the column; its first-seen time is the last update known.
_MIGRATIONS = (
    ("procedures", "first_ms", "ALTER TABLE procedures ADD COLUMN first_ms INTEGER"),
)
# 2.32.0 (HE7): a notebook made before the object_condition kind gets its facts table rebuilt (SQLite cannot
# widen a CHECK in place). The rows keep their ids and their open and closed facts.
_CONDITION_KIND = "object_condition"
_FACTS_COLUMNS = ("id, world, kind, subject, value, label, valid_from_ms, valid_until_ms, seen_ms")
_FACTS_TABLE = """CREATE TABLE facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  world TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('object_room', 'lives_here', 'object_condition')),
  subject TEXT NOT NULL,
  value TEXT NOT NULL,
  label TEXT,
  valid_from_ms INTEGER NOT NULL,
  valid_until_ms INTEGER,
  seen_ms INTEGER NOT NULL
)"""
_FACTS_OPEN = ("CREATE UNIQUE INDEX IF NOT EXISTS facts_open ON facts (world, kind, subject)"
               " WHERE valid_until_ms IS NULL")
# An object_condition fact closes when its object has not been named as notable for this long (wall ms).
CONDITION_STALE_MS = 600_000


class Notebook:
    def __init__(self, path):
        self._con = sqlite3.connect(str(path), check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self):
        for table, column, statement in _MIGRATIONS:
            names = {row["name"] for row in self._con.execute("PRAGMA table_info(%s)" % table)}
            if column not in names:
                with self._con:
                    self._con.execute(statement)
                    self._con.execute("UPDATE %s SET first_ms = updated_ms WHERE first_ms IS NULL" % table)
        ddl = self._con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'facts'").fetchone()
        if ddl is not None and _CONDITION_KIND not in (ddl["sql"] or ""):
            with self._con:
                self._con.execute("ALTER TABLE facts RENAME TO facts_before_condition")
                self._con.execute("DROP INDEX IF EXISTS facts_open")
                self._con.execute(_FACTS_TABLE)
                self._con.execute("INSERT INTO facts (%s) SELECT %s FROM facts_before_condition"
                                  % (_FACTS_COLUMNS, _FACTS_COLUMNS))
                self._con.execute("DROP TABLE facts_before_condition")
                self._con.execute(_FACTS_OPEN)

    def close(self):
        self._con.close()

    def _assert(self, world, kind, subject, value, label, now_ms):
        with self._con:
            row = self._con.execute(
                "SELECT id, value FROM facts WHERE world = ? AND kind = ? AND subject = ?"
                " AND valid_until_ms IS NULL",
                (world, kind, subject)).fetchone()
            if row is None:
                self._con.execute(
                    "INSERT INTO facts (world, kind, subject, value, label, valid_from_ms,"
                    " valid_until_ms, seen_ms) VALUES (?, ?, ?, ?, ?, ?, NULL, ?)",
                    (world, kind, subject, value, label, now_ms, now_ms))
                return "new"
            if row["value"] == value:
                self._con.execute("UPDATE facts SET seen_ms = ? WHERE id = ?", (now_ms, row["id"]))
                return "same"
            self._con.execute(
                "UPDATE facts SET valid_until_ms = ? WHERE id = ?", (now_ms, row["id"]))
            self._con.execute(
                "INSERT INTO facts (world, kind, subject, value, label, valid_from_ms,"
                " valid_until_ms, seen_ms) VALUES (?, ?, ?, ?, ?, ?, NULL, ?)",
                (world, kind, subject, value, label, now_ms, now_ms))
            return "changed"

    def observe_menu(self, world, payload, now_ms):
        """HE5: a menu no longer sets where things are. Object rooms come from the 16 nearest objects of the
        sample (observe_near_rooms), not from the four objects a menu offers."""
        return None

    def observe_near_rooms(self, world, row, now_ms):
        """HE5 (schema 15): where the 16 nearest objects are. A moved object closes its old room fact and opens
        the new one; an object that did not move keeps its fact (seen again)."""
        objects = row.get("objects") if isinstance(row, dict) else None
        if not isinstance(objects, dict):
            return
        for item in objects.get("moved") or []:
            if not isinstance(item, dict) or not isinstance(item.get("object_id"), str):
                continue
            with self._con:
                self._con.execute(
                    "UPDATE facts SET valid_until_ms = ? WHERE world = ? AND kind = 'object_room'"
                    " AND subject = ? AND valid_until_ms IS NULL", (now_ms, world, item["object_id"]))
        for item in objects.get("near_rooms") or []:
            if not isinstance(item, dict):
                continue
            object_id, room = item.get("object_id"), item.get("room")
            if not isinstance(object_id, str) or not object_id.isdigit() or not isinstance(room, str):
                continue
            self._assert(world, "object_room", object_id, room, family(item.get("class")), now_ms)

    def observe_conditions(self, world, row, now_ms):
        """2.32.0 (HE7): a notable condition of a near object (spoiled, dirty, broken) is a fact about that object.
        A fact closes once its object has not been named as notable for CONDITION_STALE_MS (it is no longer near,
        or it was cleaned)."""
        objects = row.get("objects") if isinstance(row, dict) else None
        if not isinstance(objects, dict) or not isinstance(objects.get("near_conditions"), list):
            return
        with self._con:
            self._con.execute(
                "UPDATE facts SET valid_until_ms = ? WHERE world = ? AND kind = ? AND valid_until_ms IS NULL"
                " AND seen_ms < ?", (now_ms, world, _CONDITION_KIND, now_ms - CONDITION_STALE_MS))
        for item in objects["near_conditions"]:
            if not isinstance(item, dict):
                continue
            object_id = item.get("object_id")
            if not isinstance(object_id, str) or not object_id.isdigit():
                continue
            text = "; ".join("%s=%s" % (state.get("state"), state.get("value"))
                             for state in item.get("states") or [] if isinstance(state, dict))
            if text:
                self._assert(world, _CONDITION_KIND, object_id, text[:256], family(item.get("class")), now_ms)

    def observe_presence(self, world, row, now_ms):
        if not isinstance(row, dict):
            return
        self.observe_conditions(world, row, now_ms)
        self.observe_near_rooms(world, row, now_ms)
        place = row.get("place")
        if not isinstance(place, dict) or place.get("her_home") is not True:
            return
        owner = place.get("owner_household_id")
        if owner is None:
            return
        for item in row.get("presence") or []:
            if not isinstance(item, dict) or item.get("id") is None:
                continue
            if item.get("household_id") != owner:
                continue
            self._assert(world, "lives_here", str(item["id"]), str(owner), item.get("name"), now_ms)

    def observe_withheld(self, tuning, screen, now_ms):
        """W2h: an act of this interaction ended on a screen the User's hands had to use."""
        if not isinstance(tuning, str) or not tuning or not isinstance(screen, str) or not screen:
            return
        tuning, screen = tuning[:80], screen[:128]
        with self._con:
            row = self._con.execute(
                "SELECT n FROM withheld WHERE tuning = ? AND screen = ?", (tuning, screen)).fetchone()
            if row is None:
                self._con.execute(
                    "INSERT INTO withheld (tuning, screen, n, first_ms, last_ms) VALUES (?, ?, 1, ?, ?)",
                    (tuning, screen, now_ms, now_ms))
            else:
                self._con.execute(
                    "UPDATE withheld SET n = n + 1, last_ms = ? WHERE tuning = ? AND screen = ?",
                    (now_ms, tuning, screen))

    def withheld_names(self):
        """W2h: the tuning names of interactions that have ended on such a screen."""
        return {row["tuning"] for row in self._con.execute("SELECT DISTINCT tuning FROM withheld")}

    def rebuild_procedures(self, records, now_ms):
        groups = {}
        for record in records or []:
            # HE13: a development trial is not something she learned.
            if not isinstance(record, dict) or record.get("origin") == "experiment":
                continue
            name = (record.get("interaction") or {}).get("name")
            if name:
                groups.setdefault(name, []).append(record)
        rows = []
        for name, group in groups.items():
            if len(group) < MIN_N:
                continue
            deltas = {}
            for record in group:
                for stat, value in ((record.get("needs") or {}).get("delta") or {}).items():
                    deltas.setdefault(stat, []).append(value)
            needs = {}
            for stat, values in deltas.items():
                if len(values) < MIN_N:
                    continue
                if not (all(value > 0 for value in values) or all(value < 0 for value in values)):
                    continue
                median = statistics.median(values)
                if abs(median) < MIN_CHANGE:
                    continue
                needs[stat] = int(round(median))
            if not needs:
                continue
            origins = sorted({record["origin"] for record in group if record.get("origin")})
            company = sorted({
                "with company" if record.get("company") else "solo"
                for record in group if record.get("company") is not None
            }) or ["unknown"]
            act_ids = sorted(record["act_id"] for record in group if record.get("act_id"))[:5]
            rows.append((name, len(group), json.dumps(needs, sort_keys=True),
                         json.dumps({"origins": origins, "company": company}),
                         json.dumps(act_ids), now_ms, now_ms))
        # HE13: a procedure keeps the time she first had it; one that no longer holds is dropped.
        held = {row[0] for row in rows}
        with self._con:
            gone = [row["interaction"] for row in self._con.execute("SELECT interaction FROM procedures")
                    if row["interaction"] not in held]
            self._con.executemany("DELETE FROM procedures WHERE interaction = ?", [(name,) for name in gone])
            self._con.executemany(
                "INSERT INTO procedures"
                " (interaction, n, needs, conditions, act_ids, updated_ms, first_ms)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (interaction) DO UPDATE SET n = excluded.n, needs = excluded.needs,"
                " conditions = excluded.conditions, act_ids = excluded.act_ids,"
                " updated_ms = excluded.updated_ms",
                rows)
        return len(rows)

    def room_labels(self, world):
        """HE6: an interim name for each room, from the object families of its open object_room facts: "the room
        with the fridge and the stove". The game's own room names are not read (UNKNOWN whether it exposes them).
        A room with no known object has no label."""
        families = {}
        for row in self._con.execute(
                "SELECT value, label FROM facts WHERE world = ? AND kind = 'object_room'"
                " AND valid_until_ms IS NULL", (world,)).fetchall():
            if row["label"]:
                families.setdefault(row["value"], set()).add(row["label"])
        return {room: "the room with the " + " and the ".join(sorted(names)[:3])
                for room, names in families.items()}

    def slice(self, world, payload, now_ms):
        offered = set()
        if isinstance(payload, dict):
            for obj in payload.get("objects") or []:
                if not isinstance(obj, dict):
                    continue
                for act in obj.get("acts") or []:
                    name = act.get("name") if isinstance(act, dict) else None
                    if name:
                        offered.add(name)
        procedures = []
        if offered:
            found = self._con.execute(
                "SELECT interaction, n, needs, conditions FROM procedures"
            ).fetchall()
            found = [row for row in found if row["interaction"] in offered]
            found.sort(key=lambda row: (-row["n"], row["interaction"]))
            for row in found[:SLICE_PROCEDURES]:
                conditions = json.loads(row["conditions"])
                procedures.append({
                    "interaction": row["interaction"],
                    "n": row["n"],
                    "needs": json.loads(row["needs"]),
                    "by": conditions.get("origins") or [],
                })
        moved_rows = self._con.execute(
            "SELECT closed.subject AS subject, closed.label AS label,"
            " closed.value AS was_in, open.value AS now_in"
            " FROM facts AS closed"
            " JOIN facts AS open ON open.world = closed.world AND open.kind = closed.kind"
            " AND open.subject = closed.subject AND open.valid_until_ms IS NULL"
            " WHERE closed.world = ? AND closed.kind = 'object_room'"
            " AND closed.valid_until_ms IS NOT NULL AND closed.valid_until_ms >= ?"
            " ORDER BY closed.valid_until_ms DESC",
            (world, now_ms - MOVED_RECENT_MS)).fetchall()
        moved = [
            {"object_id": row["subject"], "what": row["label"],
             "was_in": row["was_in"], "now_in": row["now_in"]}
            for row in moved_rows[:SLICE_MOVED]
        ]
        result = {}
        if procedures:
            result["procedures"] = procedures
        if moved:
            result["moved"] = moved
        while result and len(json.dumps(result, separators=(",", ":")).encode()) > SLICE_LIMIT:
            if result.get("moved"):
                result["moved"].pop()
                if not result["moved"]:
                    del result["moved"]
            elif result.get("procedures"):
                result["procedures"].pop()
                if not result["procedures"]:
                    del result["procedures"]
            else:
                break
        return result or None

    def show(self, world=None):
        where = ""
        args = ()
        if world is not None:
            where = " WHERE world = ?"
            args = (world,)
        facts_open = self._con.execute(
            "SELECT COUNT(*) FROM facts%s%s" % (where, " AND" if where else " WHERE")
            + " valid_until_ms IS NULL", args).fetchone()[0]
        facts_closed = self._con.execute(
            "SELECT COUNT(*) FROM facts%s%s" % (where, " AND" if where else " WHERE")
            + " valid_until_ms IS NOT NULL", args).fetchone()[0]
        procedures = []
        for row in self._con.execute(
                "SELECT interaction, n, needs, conditions, act_ids, updated_ms, first_ms"
                " FROM procedures ORDER BY n DESC, interaction"):
            procedures.append({
                "interaction": row["interaction"],
                "n": row["n"],
                "needs": json.loads(row["needs"]),
                "conditions": json.loads(row["conditions"]),
                "act_ids": json.loads(row["act_ids"]),
                "updated_ms": row["updated_ms"],
                "first_ms": row["first_ms"],
            })
        withheld = [dict(row) for row in self._con.execute(
            "SELECT tuning, screen, n, first_ms, last_ms FROM withheld ORDER BY last_ms DESC, tuning LIMIT 50")]
        open_where = "WHERE valid_until_ms IS NULL"
        open_args = ()
        if world is not None:
            open_where += " AND world = ?"
            open_args = (world,)
        open_facts = []
        for row in self._con.execute(
                "SELECT world, kind, subject, value, label, valid_from_ms, seen_ms"
                " FROM facts %s ORDER BY seen_ms DESC LIMIT 50" % open_where, open_args):
            open_facts.append(dict(row))
        return {
            "facts_open": facts_open,
            "facts_closed": facts_closed,
            "procedures": procedures,
            "withheld": withheld,
            "open": open_facts,
        }


def load_outcome_records(paths):
    return load_records(paths)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m domus_helper.notebook")
    sub = parser.add_subparsers(dest="cmd", required=True)
    show = sub.add_parser("show")
    show.add_argument("--world")
    sub.add_parser("rebuild")
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    book = Notebook(paths.data_dir / DB_NAME)
    try:
        if args.cmd == "show":
            print(json.dumps(book.show(args.world)))
        else:
            count = book.rebuild_procedures(load_outcome_records(paths), int(time.time() * 1000))
            print(json.dumps({"procedures": count}))
        return 0
    finally:
        book.close()


if __name__ == "__main__":
    raise SystemExit(main())
