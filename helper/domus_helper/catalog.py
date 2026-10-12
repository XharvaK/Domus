"""The game's catalogue: an object definition id to its catalogue name, description and price.

An object's catalogue entry (COBJ, type 0x319E4F1D) shares its definition's instance id.
COBJ starts with its version, the common block version, then the name and description
string keys and the price (verified 2026-10-05 against live definitions: 9929 reads
"Pure Simplicity Sink"). Delta packages carry newer copies of FullBuild entries, so a
Delta copy wins. Only the package index is read whole; each entry is read by seeking.
The index lives in the helper's data folder; names resolve through the S0 string index,
and none of the game's text is written into a repository.

    python -m domus_helper.catalog --build
    python -m domus_helper.catalog --id 9929
"""
import argparse
import json
import re
import sqlite3
import struct
import zlib
from pathlib import Path

from .paths import Paths
from .strings import StringsError, refpack

COBJ_TYPE = 0x319E4F1D
# Common block versions seen in 1.128 (FullBuild 9, DeltaBuild 11). An unknown version
# is skipped, never guessed at.
COMMON_VERSIONS = range(9, 16)
SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog (definition_id INTEGER PRIMARY KEY, name_key INTEGER,
    description_key INTEGER, price INTEGER, source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value TEXT NOT NULL);
-- W13 (H): the probe's flags for each buyable item, per game version, beside the names above.
CREATE TABLE IF NOT EXISTS catalog_flags (game_version TEXT NOT NULL, definition_id INTEGER NOT NULL,
    price INTEGER, buy_category TEXT NOT NULL, placement TEXT NOT NULL, tags TEXT NOT NULL,
    purchasable INTEGER NOT NULL, PRIMARY KEY (game_version, definition_id));
"""


def index_entries(handle):
    """(type, instance, start, size, compression) for each DBPF 2.1 index entry."""
    header = handle.read(96)
    if header[:4] != b"DBPF" or struct.unpack_from("<II", header, 4) != (2, 1):
        raise StringsError("not a DBPF 2.1 package")
    count = struct.unpack_from("<I", header, 36)[0]
    position = struct.unpack_from("<Q", header, 64)[0] or struct.unpack_from("<I", header, 40)[0]
    size = struct.unpack_from("<I", header, 44)[0]
    if count == 0 or size < 4:
        return  # an empty package (some packs ship one)
    handle.seek(position)
    data = handle.read(size)
    flags = struct.unpack_from("<I", data, 0)[0]
    offset = 4
    constant = {}
    for bit, name in enumerate(("type", "group", "instance_hi")):
        if flags & (1 << bit):
            constant[name] = struct.unpack_from("<I", data, offset)[0]
            offset += 4
    for _ in range(count):
        entry = {}
        for name in ("type", "group", "instance_hi"):
            if name in constant:
                entry[name] = constant[name]
            else:
                entry[name] = struct.unpack_from("<I", data, offset)[0]
                offset += 4
        instance_lo, start, file_size, _ = struct.unpack_from("<IIII", data, offset)
        offset += 16
        compression = 0
        if file_size & 0x80000000:
            compression = struct.unpack_from("<H", data, offset)[0]
            offset += 4
        yield (entry["type"], (entry["instance_hi"] << 32) | instance_lo, start,
               file_size & 0x7FFFFFFF, compression)


def _decode(raw, compression):
    if compression == 0x5A42:
        return zlib.decompress(raw)
    if compression == 0xFFFF:
        return refpack(raw)
    if compression in (0, 0xFFFE):
        return raw
    return None


def cobj_fields(raw):
    """(name_key, description_key, price) or None when the layout is not one we know."""
    if raw is None or len(raw) < 20:
        return None
    _, common, name_key, description_key, price = struct.unpack_from("<5I", raw, 0)
    if common not in COMMON_VERSIONS:
        return None
    return name_key, description_key, price


def packages(game_root):
    """Delta packages first (they win), then FullBuild, each in a stable order."""
    root = Path(game_root)
    found = sorted(root.glob("Data/Client/Client*Build*.package")) + sorted(
        root.glob("Delta/*/Client*Build*.package"))
    return sorted(found, key=lambda path: (0 if "Delta" in path.name else 1, str(path)))


def _fingerprint(found):
    return ";".join("%s/%s:%d:%d" % (path.parent.name, path.name, path.stat().st_size,
                                     int(path.stat().st_mtime)) for path in found)


def index_path(paths):
    return paths.data_dir / "catalog.db"


def read_catalog(found):
    """definition_id -> (name_key, description_key, price, source); first package wins."""
    catalog = {}
    for path in found:
        with open(path, "rb") as handle:
            try:
                entries = [entry for entry in index_entries(handle) if entry[0] == COBJ_TYPE]
            except (StringsError, struct.error):
                continue
            for _, instance, start, size, compression in sorted(entries, key=lambda e: e[2]):
                if instance in catalog:
                    continue
                handle.seek(start)
                try:
                    fields = cobj_fields(_decode(handle.read(size), compression))
                except (StringsError, zlib.error, struct.error):
                    fields = None
                if fields is not None:
                    catalog[instance] = fields + ("%s/%s" % (path.parent.name, path.name),)
    return catalog


def build(paths, *, force=False):
    """Build or refresh the index. Returns (count, rebuilt)."""
    if paths.game_root is None:
        raise StringsError("DOMUS_GAME_ROOT is not set")
    found = packages(paths.game_root)
    if not found:
        raise StringsError("no client packages")
    fingerprint = _fingerprint(found)
    target = index_path(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    try:
        connection.executescript(SCHEMA)
        row = connection.execute("SELECT value FROM meta WHERE name = 'fingerprint'").fetchone()
        if row is not None and row[0] == fingerprint and not force:
            return connection.execute("SELECT COUNT(*) FROM catalog").fetchone()[0], False
        catalog = read_catalog(found)
        with connection:
            connection.execute("DELETE FROM catalog")
            connection.executemany(
                "INSERT INTO catalog VALUES (?, ?, ?, ?, ?)",
                sorted((key,) + value for key, value in catalog.items()))
            connection.execute("INSERT OR REPLACE INTO meta VALUES ('fingerprint', ?)",
                               (fingerprint,))
        return len(catalog), True
    finally:
        connection.close()


class Catalog(object):
    """definition id -> {"name_key", "description_key", "price"}, or None when unknown."""

    def __init__(self, paths):
        self._path = index_path(paths)
        self._cache = {}

    def __call__(self, definition_id):
        try:
            number = int(definition_id)
        except (TypeError, ValueError):
            return None
        if number in self._cache:
            return self._cache[number]
        if not self._path.is_file():
            return None
        connection = sqlite3.connect("file:%s?mode=ro" % self._path.as_posix(), uri=True)
        try:
            row = connection.execute(
                "SELECT name_key, description_key, price FROM catalog WHERE definition_id = ?",
                (number,)).fetchone()
        finally:
            connection.close()
        entry = None if row is None else {"name_key": str(row[0]),
                                          "description_key": str(row[1]), "price": row[2]}
        if len(self._cache) < 4096:
            self._cache[number] = entry
        return entry


# W13 (H): the game's buy categories of furniture and decor (build_buy), surfaces (tables, counters) among them. Build
# items (walls, floors, doors, windows, stairs, roofs, terrain) and vehicles are none of them, so the search never
# offers them.
FURNITURE = frozenset({"APPLIANCES", "COMFORT", "DECOR", "ELECTRONICS", "ENTERTAINMENT", "KIDS", "LIGHTING",
                       "PLUMBING", "STORAGE", "SURFACE"})
SEARCH_SHOWN = 12
_WORDS = re.compile(r"[\W_]+")
_DIGITS = re.compile(r"[0-9]{1,20}")


def _strings(value, limit):
    """W13 (H): the probe's list of names, at most limit of them (the non-text ones dropped)."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item][:limit]


def _definition(value):
    """W13 (H, A6-2): a definition id from the probe as an int: the probe writes its ids as digit strings, and a
    plain int is taken too. Anything else is None."""
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and _DIGITS.fullmatch(value):
        return int(value)
    return None


def store_flags(paths, game_version, items):
    """W13 (H): the probe's catalogue flags for one game version, replacing that version's earlier ones. An item
    without a definition id is skipped. The rows are built first: a dump with no usable row keeps the earlier flags, and
    the replace is one transaction. Returns the number of items stored."""
    rows = []
    for item in items if isinstance(items, list) else []:
        definition = _definition(item.get("definition_id")) if isinstance(item, dict) else None
        if definition is None:
            continue
        price = item.get("price") if type(item.get("price")) is int else None
        rows.append((game_version, definition, price,
                     json.dumps(_strings(item.get("buy_category"), 4)),
                     json.dumps(_strings(item.get("placement"), 1)),
                     json.dumps(_strings(item.get("tags"), 8)),
                     1 if item.get("purchasable") is True else 0))
    if not rows:
        return 0
    target = index_path(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    try:
        connection.executescript(SCHEMA)
        with connection:
            connection.execute("DELETE FROM catalog_flags WHERE game_version = ?", (game_version,))
            connection.executemany("INSERT INTO catalog_flags VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    finally:
        connection.close()
    return len(rows)


def _read_only(paths):
    return sqlite3.connect("file:%s?mode=ro" % index_path(paths).as_posix(), uri=True)


def has_flags(paths, game_version):
    """W13 (H): whether the catalogue holds the probe's flags for this game version."""
    if game_version is None or not index_path(paths).is_file():
        return False
    connection = _read_only(paths)
    try:
        return connection.execute("SELECT 1 FROM catalog_flags WHERE game_version = ? LIMIT 1",
                                  (game_version,)).fetchone() is not None
    except sqlite3.OperationalError:
        return False
    finally:
        connection.close()


def search(paths, game_version, words, *, max_price=None, placement=None, resolve=None, shown=SEARCH_SHOWN):
    """W13 (H): the purchasable furniture and decor whose names share words with `words`, filtered by max_price and
    placement, ordered by how many of the words each name has (then by name). Returns (matched, items): the count of
    every match, and at most `shown` items as {definition_id, name, price, placement, category}. Items are matched on
    their names only; nothing ranks by taste, price or what suits her. resolve gives the game's text for a name key."""
    query = set(word for word in _WORDS.split(words.casefold()) if word) if isinstance(words, str) else set()
    if not query or not index_path(paths).is_file():
        return 0, []
    connection = _read_only(paths)
    try:
        rows = connection.execute(
            "SELECT f.definition_id, f.price, f.buy_category, f.placement, c.name_key, c.price "
            "FROM catalog_flags f JOIN catalog c ON c.definition_id = f.definition_id "
            "WHERE f.game_version = ? AND f.purchasable = 1", (game_version,)).fetchall()
    except sqlite3.OperationalError:
        return 0, []
    finally:
        connection.close()
    found = []
    for definition_id, probe_price, categories_raw, placements_raw, name_key, catalog_price in rows:
        categories = [name for name in json.loads(categories_raw) if name in FURNITURE]
        placements = json.loads(placements_raw)
        if not categories or (placement is not None and placement not in placements):
            continue
        price = probe_price if probe_price is not None else catalog_price
        if price is None or (max_price is not None and price > max_price):
            continue
        text = resolve(str(name_key)) if resolve is not None else None
        name = clean_name(text)
        if name is None:
            continue
        score = len(query & set(word for word in _WORDS.split(name.casefold()) if word))
        if score:
            found.append((score, name, definition_id, price, placements, categories))
    found.sort(key=lambda row: (-row[0], row[1].casefold(), row[2]))
    items = [{"definition_id": definition_id, "name": name, "price": price,
              "placement": _placement_text(placements),
              "category": ", ".join(kind.lower() for kind in sorted(categories))[:40]}
             for _score, name, definition_id, price, placements, categories in found[:shown]]
    return len(found), items


def _placement_text(placements):
    """W13 (H, S3): the one placement word of an item (floor, wall or surface), or None when it has none."""
    return placements[0] if placements else None


def clean_name(text):
    """W13 (H): a game name in words, cut to 64 characters, or None when nothing is left."""
    from .acts import clean_text
    if not isinstance(text, str):
        return None
    cleaned = clean_text(text)
    return cleaned[:64] if cleaned else None


def main(argv=None):
    from .strings import Resolver
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--id")
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    if paths.game_root is None:
        from .paths import DEFAULT_GAME_ROOT
        paths = Paths(paths.sims_root, Path(DEFAULT_GAME_ROOT))
    if args.build or args.force:
        count, rebuilt = build(paths, force=args.force)
        print("%s %d catalogue entries" % ("built" if rebuilt else "current", count))
    if args.id:
        entry = Catalog(paths)(args.id)
        print(entry, Resolver(paths)(entry["name_key"]) if entry else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
