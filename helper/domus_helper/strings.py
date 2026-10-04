"""S0: the game's own words, resolved from its local string tables.

In-game Python never sees text: a tuned string keeps a 32-bit key (`_string_id`,
or `.hash` on a built LocalizedString) and the client renders it. The probe sends
keys; this module resolves them from the game's own `Strings_<LOCALE>.package`
files (DBPF 2.1; STBL tables, mostly EA RefPack-compressed). The index lives in
the helper's data folder. Game text is EA content: it is never written into a
repository or published.

    python -m domus_helper.strings --build
    python -m domus_helper.strings --key 0xc4338c38
    python -m domus_helper.strings --find "Eggs and Toast"
"""
import argparse
import os
import sqlite3
import struct
import zlib
from pathlib import Path

from .paths import Paths

STBL_TYPE = 0x220557DA
# The game's locale (registry `locale`) to its string package suffix.
LOCALE_SUFFIX = {
    "en_US": "ENG_US", "de_DE": "GER_DE", "fr_FR": "FRE_FR", "es_ES": "SPA_ES",
    "it_IT": "ITA_IT", "nl_NL": "DUT_NL", "pl_PL": "POL_PL", "pt_BR": "POR_BR",
    "ru_RU": "RUS_RU", "sv_SE": "SWE_SE", "da_DK": "DAN_DK", "fi_FI": "FIN_FI",
    "no_NO": "NOR_NO", "cs_CZ": "CZE_CZ", "ja_JP": "JPN_JP", "ko_KR": "KOR_KR",
    "zh_TW": "CHT_CN", "zh_CN": "CHS_CN",
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS strings (key INTEGER PRIMARY KEY, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


class StringsError(RuntimeError):
    pass


def refpack(src):
    """EA RefPack (QFS) decompression, used by compression type 0xFFFF."""
    if len(src) < 5:
        raise StringsError("refpack header")
    flags = src[0]
    pos = 2
    size_len = 4 if flags & 0x80 else 3
    out_len = int.from_bytes(src[pos:pos + size_len], "big")
    pos += size_len
    if flags & 0x01:
        pos += size_len
    out = bytearray()
    while pos < len(src):
        b0 = src[pos]
        if b0 < 0x80:
            b1 = src[pos + 1]
            pos += 2
            plain, length = b0 & 3, ((b0 & 0x1C) >> 2) + 3
            offset = ((b0 & 0x60) << 3) + b1 + 1
        elif b0 < 0xC0:
            b1, b2 = src[pos + 1], src[pos + 2]
            pos += 3
            plain, length = b1 >> 6, (b0 & 0x3F) + 4
            offset = ((b1 & 0x3F) << 8) + b2 + 1
        elif b0 < 0xE0:
            b1, b2, b3 = src[pos + 1], src[pos + 2], src[pos + 3]
            pos += 4
            plain, length = b0 & 3, ((b0 & 0x0C) << 6) + b3 + 5
            offset = ((b0 & 0x10) << 12) + (b1 << 8) + b2 + 1
        elif b0 < 0xFC:
            plain, length, offset = ((b0 & 0x1F) << 2) + 4, 0, 0
            pos += 1
        else:
            plain, length, offset = b0 & 3, 0, 0
            pos += 1
        out += src[pos:pos + plain]
        pos += plain
        if offset > len(out):
            raise StringsError("refpack offset")
        for _ in range(length):
            out.append(out[-offset])
        if b0 >= 0xFC:
            break
    if len(out) != out_len:
        raise StringsError("refpack length %d != %d" % (len(out), out_len))
    return bytes(out)


def _resources(data):
    """(type, group, instance, raw bytes) for each DBPF 2.1 index entry."""
    if data[:4] != b"DBPF" or struct.unpack_from("<II", data, 4) != (2, 1):
        raise StringsError("not a DBPF 2.1 package")
    count = struct.unpack_from("<I", data, 36)[0]
    position = struct.unpack_from("<Q", data, 64)[0] or struct.unpack_from("<I", data, 40)[0]
    flags = struct.unpack_from("<I", data, position)[0]
    offset = position + 4
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
        instance_lo, start, file_size, mem_size = struct.unpack_from("<IIII", data, offset)
        offset += 16
        compression = 0
        if file_size & 0x80000000:
            compression = struct.unpack_from("<H", data, offset)[0]
            offset += 4
        raw = data[start:start + (file_size & 0x7FFFFFFF)]
        if compression == 0x5A42:
            raw = zlib.decompress(raw)
        elif compression == 0xFFFF:
            raw = refpack(raw)
        elif compression not in (0, 0xFFFE):
            continue
        yield entry["type"], entry["group"], (entry["instance_hi"] << 32) | instance_lo, raw


def stbl_entries(raw):
    """(key, text) pairs of one STBL resource (format version 5)."""
    if raw[:4] != b"STBL":
        raise StringsError("not an STBL resource")
    count = struct.unpack_from("<Q", raw, 7)[0]
    offset = 21
    for _ in range(count):
        key, _, size = struct.unpack_from("<IBH", raw, offset)
        offset += 7
        yield key, raw[offset:offset + size].decode("utf-8", "replace")
        offset += size


def read_package(path):
    data = Path(path).read_bytes()
    strings = {}
    for kind, _, _, raw in _resources(data):
        if kind != STBL_TYPE:
            continue
        for key, text in stbl_entries(raw):
            strings.setdefault(key, text)
    return strings


def game_locale():
    """The game's own locale from the registry (`locale`, e.g. en_US), else en_US."""
    configured = os.environ.get("DOMUS_LOCALE")
    if configured:
        return configured
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Maxis\The Sims 4") as key:
            return winreg.QueryValueEx(key, "locale")[0]
    except (ImportError, OSError):
        return "en_US"


def packages(game_root, locale):
    suffix = LOCALE_SUFFIX.get(locale, "ENG_US")
    name = "Strings_%s.package" % suffix
    root = Path(game_root)
    found = [root / "Data" / "Client" / name]
    delta = root / "Delta"
    if delta.is_dir():
        found.extend(sorted(delta.glob("*/" + name)))
    return [path for path in found if path.is_file()]


def _fingerprint(paths):
    return ";".join("%s:%d:%d" % (path.name if path.parent.name == "Client" else
                                  path.parent.name, path.stat().st_size,
                                  int(path.stat().st_mtime)) for path in paths)


def index_path(paths, locale):
    return paths.data_dir / ("strings_%s.db" % locale)


def build(paths, *, locale=None, force=False):
    """Build or refresh the index. Returns (count, rebuilt)."""
    if paths.game_root is None:
        raise StringsError("DOMUS_GAME_ROOT is not set")
    locale = locale or game_locale()
    found = packages(paths.game_root, locale)
    if not found:
        raise StringsError("no string packages for %s" % locale)
    fingerprint = _fingerprint(found)
    target = index_path(paths, locale)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(target)
    try:
        connection.executescript(SCHEMA)
        row = connection.execute("SELECT value FROM meta WHERE name = 'fingerprint'").fetchone()
        if row is not None and row[0] == fingerprint and not force:
            return connection.execute("SELECT COUNT(*) FROM strings").fetchone()[0], False
        merged = {}
        for path in found:
            for key, text in read_package(path).items():
                merged.setdefault(key, text)
        with connection:
            connection.execute("DELETE FROM strings")
            connection.executemany("INSERT INTO strings (key, text) VALUES (?, ?)",
                                   sorted(merged.items()))
            connection.execute("INSERT OR REPLACE INTO meta VALUES ('fingerprint', ?)",
                               (fingerprint,))
            connection.execute("INSERT OR REPLACE INTO meta VALUES ('locale', ?)", (locale,))
        return len(merged), True
    finally:
        connection.close()


class Resolver(object):
    """Key -> game text. Unknown keys give None; callers mark them UNRESOLVED."""

    def __init__(self, paths, locale=None):
        self._path = index_path(paths, locale or game_locale())
        self._cache = {}

    def __call__(self, key):
        try:
            number = int(key, 0) if isinstance(key, str) else int(key)
        except (TypeError, ValueError):
            return None
        if number in self._cache:
            return self._cache[number]
        if not self._path.is_file():
            return None
        connection = sqlite3.connect("file:%s?mode=ro" % self._path.as_posix(), uri=True)
        try:
            row = connection.execute("SELECT text FROM strings WHERE key = ?", (number,)).fetchone()
        finally:
            connection.close()
        text = None if row is None else row[0]
        if len(self._cache) < 4096:
            self._cache[number] = text
        return text


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--key")
    parser.add_argument("--find")
    args = parser.parse_args(argv)
    paths = Paths.from_env()
    if paths.game_root is None:
        from .paths import DEFAULT_GAME_ROOT
        paths = Paths(paths.sims_root, Path(DEFAULT_GAME_ROOT))
    if args.build or args.force:
        count, rebuilt = build(paths, force=args.force)
        print("%s %d strings" % ("built" if rebuilt else "current", count))
    if args.key:
        print(Resolver(paths)(args.key))
    if args.find:
        connection = sqlite3.connect(index_path(paths, game_locale()))
        for key, text in connection.execute(
                "SELECT key, text FROM strings WHERE text = ? LIMIT 5", (args.find,)):
            print("0x%08x %s" % (key, text))
        connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
